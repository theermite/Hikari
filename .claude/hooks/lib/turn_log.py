"""Read the CURRENT turn in the session journal: tool calls paired with their results, test-run detection.

Born 2026-11-04 (proof before writing). A tool result is itself a « user » entry of the journal: only a real message
from Jay (text, no tool result) opens a new turn (the older `logs-first` guard breaks at every tool result). Everything
fails open: a missing or broken journal gives no runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from transcript_reader import entry_message, iter_entries


@dataclass(frozen=True)
class Run:
    name: str
    command: str      # the Bash command, else ""
    path: str         # file_path / path of the call, else ""
    output: str
    is_error: bool
    background: bool = False  # a Bash call started with run_in_background


_NOT_JAY = ("Stop hook feedback", "Another Claude session sent a message", "[SYSTEM NOTIFICATION", "<system-reminder>")


def _is_jay_message(entry) -> bool:
    """A real message from Jay: not a tool result, not a meta entry, not a hook or a sub-agent speaking as « user »."""
    msg = entry_message(entry)
    if not msg or msg.get("role") != "user" or (isinstance(entry, dict) and entry.get("isMeta") is True):
        return False
    content = msg.get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        content = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return isinstance(content, str) and bool(content.strip()) and not content.lstrip().startswith(_NOT_JAY)


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def tool_runs(transcript_path: str) -> list[Run]:
    """The tool calls of the current turn, oldest first, each with its result (empty if not written yet)."""
    if not transcript_path:
        return []
    entries: list = []
    try:
        for entry in iter_entries(transcript_path):
            if _is_jay_message(entry):
                break
            entries.append(entry)
    except Exception:  # noqa: BLE001 - fail open
        return []
    calls: dict = {}
    order: list = []
    for entry in reversed(entries):
        msg = entry_message(entry)
        content = msg.get("content") if msg else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                calls[block.get("id")] = [block.get("name", ""), str(inp.get("command", "") or ""),
                                          str(inp.get("file_path") or inp.get("path") or ""), "", False,
                                          inp.get("run_in_background") is True]
                order.append(block.get("id"))
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                call = calls[block["tool_use_id"]]
                call[3], call[4] = _text_of(block.get("content")), block.get("is_error") is True
    return [Run(*calls[i]) for i in order]


_RUNNER = (r"(?:python3?\s+-m\s+pytest|pytest|mix\s+(?:test|coveralls)|pnpm\s+(?:run\s+)?test|npm\s+(?:run\s+)?test|yarn\s+test|"
           r"vitest|jest|cargo\s+test|go\s+test|make\s+test|rspec|phpunit|(?:\S*/)?ci-local\.sh)")
_WRAP = r"(?:\w+=\S+\s+|timeout\s+\d+\s+|uv\s+run\s+|npx\s+|time\s+)*"
_TEST_CMD = re.compile(r"(?:^|[;&|(\n]\s*|\bcd\s+\S+\s*&&\s*)" + _WRAP + _RUNNER + r"\b")


def is_test_command(command: str) -> bool:
    return bool(_TEST_CMD.search(command or ""))


# A runner ends with a SUMMARY line; that line is the verdict. Words like FAILED earlier in the output (a mutation script
# that shows a red case on purpose, a commit message citing « FAIL ») do not make the run red.
_SUMMARY = re.compile(
    r"(?i)\b\d+\s+(?:passed|failed|failures?|errors?|skipped|tests?)\b|\btest result:\s|^(?:ok|FAIL)\s+\S+|\bTests?:\s|"
    r"\bTest Files\b|\bno tests ran\b"
)
_RED_SUMMARY = re.compile(r"(?i)\b[1-9]\d*\s+(?:failed|failures?|errors?|failing)\b|test result:\s+FAILED|^FAIL\b")
_RED_ANYWHERE = re.compile(
    r"\bFAILED\b|Traceback \(most recent call last\)|^E\s{2,}|\berror:\s|\bFAIL\b|\b[1-9]\d*\s+(?:failed|failures?|errors?|failing)\b",
    re.MULTILINE,
)


_PROBE = re.compile(r"->|→|^\s*mutant\b", re.IGNORECASE)


def looks_red(output: str, is_error: bool = False) -> bool:
    """Red or in error. With a summary line, ONLY the last real one decides; without, the broad signals and the error flag.

    A line labelled with an arrow (`mutant -> 1 failed`) is a probe printed on purpose by a mutation script: it is not
    the verdict; a run made only of such lines is not judged red.
    """
    lines = (output or "").splitlines()
    for line in reversed(lines):
        if _SUMMARY.search(line) and not _PROBE.search(line):
            return bool(_RED_SUMMARY.search(line))
    if any(_SUMMARY.search(line) and _PROBE.search(line) for line in lines):
        return False
    return bool(_RED_ANYWHERE.search(output or "")) or is_error
