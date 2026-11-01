#!/usr/bin/env python3
"""Dependency audit gate — PreToolUse Bash, blocking.

Security.md promised « zero critical/high CVEs at deploy time » and admitted that no guard
ran the check (measured 2026-09-05): an unproven « zero CVE » was a claim, not a gate.

This gate sits where the review gate sits (a deploy, a package publication) and asks for an
artefact instead of a sentence. Two things must be true:

  1. the audit tool REALLY ran in this session (a Bash call in the journal), and
  2. its result is quoted on a line that OPENS with the marker, naming the commit it covered:

     [AUDIT] outil: <tool> sur <empreinte> — critiques: <N>, hautes: <N>[, acceptees: <ids>]
     [AUDIT-SKIP] motif: <closed enum> sur <empreinte>

Findings (critiques + hautes > 0) block unless each one is named in `acceptees:` by its
advisory identifier (GHSA-…, CVE-…). An audit of an older commit holds only while no
dependency manifest or lock file changed since: the audit's subject is the lock file.

Limits, written: one audit tool is enough (the gate does not know which stacks a repository
carries) · the counts are quoted, not parsed from the tool's output · `find -exec` and
`bash -c` are read the way the review gate reads them, no further.

Exit codes: 0 = pass · 2 = block (stderr message printed).
Source: Jay 2026-10-31, brief « Sécurité automatique des dépôts », step 2.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Sentinel: « nobody said » differs from « could not read » (same convention as the review gate).
_ABSENT = object()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    find_repo_root,
    get_command,
    looks_like_deploy,
    pass_through,
    read_hook_input,
)
from shell_parse import simple_commands  # noqa: E402
from transcript_reader import iter_spoken_text, iter_tool_calls  # noqa: E402

TRANSCRIPT_LOOKBACK = 30

# Closed on purpose: an open motif field becomes « pas le temps » within a week.
SKIP_MOTIFS = (
    "rollback",  # going back to a state already audited and shipped
    "hotfix-production-down",  # service is down; the audit follows immediately after
    "no-dependencies",  # the project declares no dependency to audit
    "no-code-change",  # docs or content only: no dependency can have moved
    "local-dev",  # a compose file started on this machine: nothing leaves it (refused for any remote or publication)
)

# What each tool is recognised by in a REAL command, and the line to run when it is missing.
TOOLS = {
    "npm-audit": (re.compile(r"\bnpm\s+audit\b"), "npm audit --omit=dev"),
    "pnpm-audit": (re.compile(r"\bpnpm\s+audit\b"), "pnpm audit --prod"),
    "pip-audit": (re.compile(r"\bpip[-_]audit\b"), "pip-audit"),
    "mix-deps-audit": (re.compile(r"\bmix\s+(?:deps|hex)\.audit\b"), "mix deps.audit"),
    "cargo-audit": (re.compile(r"\bcargo\s+audit\b"), "cargo audit"),
    "osv-scanner": (re.compile(r"\bosv-scanner\b"), "osv-scanner scan --lockfile=<lock file>"),
}

# The marker OPENS its line (Tests-Et-Mesures: select on the structure, never on a word).
_AUDIT = re.compile(
    r"^\[AUDIT\][ \t]+outil[ \t]*:[ \t]*(?P<tool>[a-z-]+)[ \t]+sur[ \t]+(?P<commit>[0-9a-f]{7,40})\b"
    r"(?:(?!hautes)[^\n])*?critiques[ \t]*:[ \t]*(?P<crit>\d+)[ \t]*,[ \t]*hautes[ \t]*:[ \t]*(?P<high>\d+)(?P<rest>[^\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)
_ACCEPTED = re.compile(r"acceptees[ \t]*:[ \t]*(?P<ids>[^\n]+)", re.IGNORECASE)
_ADVISORY_ID = re.compile(r"(?:GHSA|CVE|OSV|RUSTSEC|PYSEC|GO)-[\w-]+", re.IGNORECASE)
# The list must be identifiers and nothing else: prose beside an identifier is not an acceptance.
_ID_LIST = re.compile(rf"(?:{_ADVISORY_ID.pattern}[ \t,]*)+", re.IGNORECASE)
_SKIP = re.compile(
    r"^\[AUDIT-SKIP\][ \t]+motif[ \t]*:[ \t]*(?P<motif>[a-z-]+)(?:[ \t]+sur[ \t]+(?P<commit>[0-9a-f]{7,40})\b)?",
    re.IGNORECASE | re.MULTILINE,
)
_CODE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)

# Files whose change can move an audit's result.
_DEPENDENCY_FILES = re.compile(
    r"(^|/)(package(-lock)?\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|pyproject\.toml|"
    r"uv\.lock|poetry\.lock|Pipfile(\.lock)?|mix\.exs|mix\.lock|Cargo\.(toml|lock)|go\.(mod|sum)|"
    r"(requirements|constraints)[\w.-]*\.txt|requirements/[\w./-]+\.txt)$"
)
# A runner in front of the tool does not change what ran.
_RUNNER = re.compile(r"^(?:npx|uvx|pnpm\s+dlx|python3?\s+-m)\s+")

_PUBLISH = re.compile(
    r"npm\s+publish|pnpm\s+(?:(?:-r|--recursive)\s+)?publish|yarn\s+publish|twine\s+upload|cargo\s+publish|"
    r"mix\s+hex\.publish|uv\s+publish|poetry\s+publish|hatch\s+publish",
    re.IGNORECASE,
)
# These read a file or print an argument; they never run it.
_PRINTERS = {
    "echo", "print", "printf", "cat", "grep", "rg", "head", "tail", "less", "more", "sed", "awk", "nl",
    "sort", "uniq", "cut", "tr", "jq", "ls", "wc", "diff", "stat", "file", "basename", "dirname", "realpath",
}
_SUBSTITUTION = re.compile(r"\$\(|`")
_RUNS_WHAT_FOLLOWS = {"-exec", "-execdir", "-ok", "-okdir"}


def _program_name(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _after_exec_flag(segment):
    """What `find -exec` hands to the shell: the search itself ships nothing, only what it runs can."""
    for i, token in enumerate(segment):
        if token in _RUNS_WHAT_FOLLOWS and i + 1 < len(segment):
            command = [t for t in segment[i + 1 :] if t not in ("{}", ";", "\\", "+")]
            matched = [t for t in segment[:i] if not t.startswith("-")]
            return command + matched
    return None


def _ships(segment, printers_are_safe=True):
    if not segment:
        return False
    if _program_name(segment[0]) == "find":
        nested = _after_exec_flag(segment)
        return _ships(nested, printers_are_safe) if nested is not None else False
    if _program_name(segment[0]) in _PRINTERS and printers_are_safe:
        return False
    if _program_name(segment[0]) == "git" or segment[:2] == ["gh", "pr"] or segment[:2] == ["gh", "issue"]:
        return False  # a commit message or a log search that names « npm publish » ships nothing
    text = " ".join(segment)
    return looks_like_deploy(text) or bool(_PUBLISH.search(text))


def _is_gated(command):
    """True when any real command in the line deploys or publishes. Unparseable input is read raw."""
    try:
        segments = simple_commands(command)
    except ValueError:
        segments = [[command or ""]]  # fail closed
    printers_are_safe = not _SUBSTITUTION.search(command or "")
    return any(_ships(segment, printers_are_safe) for segment in segments)


def _spoken(text):
    """Text minus code samples: quoting the format is not running the audit."""
    return _CODE.sub(" ", text or "")


def find_audits(text):
    """Every complete audit marker of `text`, in order of appearance, as dicts."""
    audits = []
    for match in _AUDIT.finditer(_spoken(text)):
        tool = match.group("tool").lower()
        if tool not in TOOLS:
            continue
        accepted = _ACCEPTED.search(match.group("rest"))
        listed = accepted.group("ids").strip() if accepted else ""
        ids = set(_ADVISORY_ID.findall(listed)) if _ID_LIST.fullmatch(listed) else set()
        audits.append({
            "tool": tool,
            "commit": match.group("commit").lower(),
            "findings": int(match.group("crit")) + int(match.group("high")),
            "accepted": len(ids),
            "line": match.group(0).strip()[:160],
        })
    return audits


def find_skip(text):
    """The dispense match, only when its motif belongs to the closed list."""
    match = _SKIP.search(_spoken(text))
    if match and match.group("motif").lower() in SKIP_MOTIFS:
        return match
    return None


def head_courant():
    """The current commit, read from the repository root; None when unreadable (never a refusal)."""
    try:
        racine = find_repo_root()
    except Exception:
        racine = None
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False,
                             cwd=str(racine) if racine else None)
    except OSError:
        return None
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else None


def changed_files(old, new):
    """Paths changed between two commits, or None when git cannot say."""
    try:
        racine = find_repo_root()
        out = subprocess.run(["git", "diff", "--name-only", f"{old}..{new}"], capture_output=True, text=True,
                             check=False, cwd=str(racine))
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return [line for line in out.stdout.splitlines() if line.strip()]


def dirty_dependency_files():
    """Dependency files modified in the working tree but not committed; [] when git cannot say."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False,
                             cwd=str(find_repo_root()))
    except Exception:
        return []
    paths = [line[3:].strip().strip('"') for line in out.stdout.splitlines() if len(line) > 3]
    return [p for p in paths if _DEPENDENCY_FILES.search(p.replace("\\", "/"))]


def _ran_tool(pattern, commands):
    """True when a real command RUNS the tool: it opens a command of the line, not an argument of another."""
    for command in commands:
        try:
            segments = simple_commands(command)
        except ValueError:
            continue
        for segment in segments:
            text = _RUNNER.sub("", " ".join(segment))
            if pattern.match(text) and "--help" not in segment:
                return True
    return False


def _same_commit(a, b):
    a, b = a.lower(), b.lower()
    return a.startswith(b) or b.startswith(a)


_WHEN_TO_WRITE = (
    "Write the marker in a message that comes BEFORE the command (a harmless call can carry it), "
    "never in the message that runs it."
)


def _no_evidence_message(command):
    motifs = " | ".join(SKIP_MOTIFS)
    return (
        "BLOCKED: shipping without a dependency audit. "
        f"COMMAND: {command.strip()[:120]}. "
        "RECOVERY: run the audit tool for this repository (npm audit --omit=dev, pnpm audit --prod, pip-audit, "
        "mix deps.audit, cargo audit or osv-scanner) on the code being shipped, then emit, on a line of its own: "
        "'[AUDIT] outil: <npm-audit|pnpm-audit|pip-audit|mix-deps-audit|cargo-audit|osv-scanner> sur <empreinte> "
        "— critiques: <N>, hautes: <N>' and retry. "
        f"Legitimate skip: '[AUDIT-SKIP] motif: <{motifs}> sur <empreinte>'. {_WHEN_TO_WRITE} "
        "Why: « zero CVE at deploy » was a claim no guard checked (measured 2026-09-05)."
    )


def _tool_not_run_message(audit):
    hint = TOOLS[audit["tool"]][1]
    return (
        f"BLOCKED: the audit marker names `{audit['tool']}`, but no such command ran in this session. "
        f"RECOVERY: run it ({hint}), then emit the marker with what it printed. "
        "Why: a marker without the run behind it is a sentence, and a sentence is what this gate replaces."
    )


def _findings_message(audit):
    return (
        f"BLOCKED: the audit reports {audit['findings']} critical/high finding(s) and names {audit['accepted']} "
        f"accepted advisory identifier(s). LINE READ: {audit['line']}. "
        "RECOVERY: update the dependency, or accept each finding on purpose by naming its identifier: "
        "'... — critiques: 0, hautes: 1, acceptees: GHSA-xxxx-xxxx-xxxx'. "
        "Why: zero critical/high at deploy time is the rule; an accepted one is a decision written down."
    )


def _coverage_message(audit, head, changed):
    if _same_commit(audit["commit"], head):
        return None
    files = changed(audit["commit"], head)
    if files is None:
        return (
            f"BLOCKED: the audit covers {audit['commit']}, the code ships {head[:7]}, and git cannot say what "
            f"changed between them. RECOVERY: rerun the audit on {head[:7]} and quote it."
        )
    touched = sorted({f for f in files if _DEPENDENCY_FILES.search(f.replace("\\", "/"))})
    if not touched:
        return None
    return (
        f"BLOCKED: the audit covers {audit['commit']}, the code ships {head[:7]}, and these dependency files "
        f"changed since: {', '.join(touched[:6])}. RECOVERY: rerun the audit on {head[:7]} and quote it. "
        "Why: the audit's subject is the lock file; a newer lock file is an audit nobody ran."
    )


# What leaves the machine : « local-dev » never covers it, the audit does.
_LEAVES_THE_MACHINE = re.compile(
    r"(?i)\b(?:ssh|scp|rsync|sftp|kubectl|helm|ansible-playbook|fly|vercel|netlify|railway|twine|publish)\b|\bgh\s+workflow\b"
    r"|\bdocker\s+stack\s+deploy\b|\bdeploy\.sh\b"
)


def _local_dev_misused(skip, command):
    if skip.group("motif").lower() != "local-dev" or not _LEAVES_THE_MACHINE.search(command):
        return None
    return (
        "BLOCKED: the dispense 'local-dev' covers a compose file started on THIS machine; this command reaches a "
        "server, a registry or a platform. RECOVERY: run the audit and quote "
        "'[AUDIT] outil: <tool> sur <commit> — critiques: N, hautes: N' before it."
    )


def _skip_verdict(skip, head, command=""):
    misuse = _local_dev_misused(skip, command)
    if misuse:
        return misuse
    commit = skip.group("commit")
    if not head:
        return None
    if not commit:
        return (
            "BLOCKED: the dispense names no commit — it would lift the gate for all code posted after it. "
            f"RECOVERY: emit '[AUDIT-SKIP] motif: {skip.group('motif')} sur {head[:7]}'."
        )
    if not _same_commit(commit, head):
        return f"BLOCKED: the dispense covers {commit}, the code now ships {head[:7]}. RECOVERY: restate it on {head[:7]}."
    return None


def _latest_audits(texts):
    """(audits, skip): the newest audit per tool, and a dispense only when it is newer than every audit."""
    latest = {}
    for text in texts:  # most recent first
        skip = find_skip(text)
        if skip and not latest:
            return {}, skip
        for audit in reversed(find_audits(text)):
            latest.setdefault(audit["tool"], audit)
        if skip:
            break
    return latest, None


def _audit_refusal(audit, ran, head, changed):
    """The reason one quoted audit does not hold, or None when it does."""
    if not _ran_tool(TOOLS[audit["tool"]][0], ran):
        return _tool_not_run_message(audit)
    if audit["findings"] > audit["accepted"]:
        return _findings_message(audit)
    return _coverage_message(audit, head, changed) if head else None


def _dirty_message(dirty):
    return (
        f"BLOCKED: dependency files are modified and not committed ({', '.join(dirty[:6])}): the audit "
        "covers a commit, not what is on disk. RECOVERY: commit them (or restore them), rerun the audit, quote it."
    )


def verdict(command, recent_texts, ran=(), head=_ABSENT, changed=None, dirty_files=None):
    """A block message, or None when the command may proceed. Texts arrive most recent first."""
    if not _is_gated(command):
        return None
    if head is _ABSENT:
        head = head_courant()
    audits, skip = _latest_audits(recent_texts)
    if skip:
        return _skip_verdict(skip, head, command)
    return _judge_audits(command, audits, ran, head, changed or changed_files, dirty_files or dirty_dependency_files)


def _judge_audits(command, audits, ran, head, changed, dirty_files):
    """No dispense: the working tree must be clean of dependency changes, and every quoted audit must hold."""
    dirty = dirty_files()
    if dirty:
        return _dirty_message(dirty)
    if not audits:
        return _no_evidence_message(command)
    refusals = (_audit_refusal(a, ran, head, changed) for a in audits.values())
    return next((message for message in refusals if message), None)


def main():
    _raw, data = read_hook_input()
    command = get_command(data)
    if not _is_gated(command):
        pass_through()  # most Bash calls ship nothing: do not read the journal
    transcript = data.get("transcript_path", "")
    texts = list(iter_spoken_text(transcript, limit=TRANSCRIPT_LOOKBACK)) if transcript else []
    ran = [str(call.get("input", {}).get("command", "")) for call in iter_tool_calls(transcript, "Bash")] if transcript else []
    message = verdict(command, texts, ran=ran)
    if message:
        block(message)
    pass_through()


if __name__ == "__main__":
    main()
