#!/usr/bin/env python3
"""Veille / SKB Evidence guard — PreToolUse Write|Edit.

Enforces Workflows.md "Veille/SKB Evidence Protocol" with 3 hardening layers
(2026-05-19 — Option C):

  Layer A — Closed enum for SKIP motifs
    [VEILLE-SKIP] motif: <enum> where enum is one of:
      typo, internal-refactor-no-new-deps, hotfix-known-root-cause,
      test-only, methodology-edit, generated-artifact
    Any other motif text -> BLOCK.

  Layer B — Diff-aware: force REAL veille when content is sensitive
    Triggers (read the target file content / Edit diff):
      - Target is a dependency manifest (package.json, pyproject.toml,
        mix.exs, Cargo.toml, go.mod, requirements*.txt, Gemfile, ...)
      - New non-relative / non-stdlib import added vs old_string
      - Version pin pattern present in the diff (@X.Y.Z, ^X.Y, ~= X.Y)
    When triggered: ONLY [VEILLE] <techno>@<version> verifie <date> via <source>
    is accepted. SKB and VEILLE-SKIP are refused.

  Layer C — Session skip counter
    State file .claude/state/veille-skips-<session>.json tracks
    consecutive VEILLE-SKIP markers. The 3rd consecutive SKIP -> BLOCK
    even for trivial changes; a real [VEILLE] or [SKB] resets the counter.
    A given marker is counted ONCE (hashed) — repeated tool calls under
    the same marker do not re-increment.

Markers (case-sensitive, line-start or whitespace prefix):
  [VEILLE] <techno>@<version> verifie <date> via <source>
  [SKB] consulte: <paths>
  [VEILLE-SKIP] motif: <enum>

Layout (split 2026-08-18, the file had passed the 500-line BLOCKING limit it
helps enforce — and it ships to every Shinkofa repo, so it counted 33 times):
  lib/veille_config.py   — constants, regexes, closed enums
  lib/veille_detect.py   — needs_evidence + Layer B sensitivity
  lib/veille_markers.py  — transcript marker scan + web-call proof
  this file              — decision, state, block messages

Hook exit codes:
  0 = pass
  2 = block (stderr message printed)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root  # noqa: E402
from session_state import read_state, write_state  # noqa: E402
from veille_config import (  # noqa: E402
    ALLOWED_SKIP_MOTIFS,
    SKIP_COUNT_THRESHOLD,
    SKIP_MOTIF_RE,
)
from veille_detect import (  # noqa: E402
    file_is_dep_manifest,
    needs_evidence,
    sensitive_change,
)
from veille_markers import DIGEST_ALGO, has_web_veille_call, latest_marker  # noqa: E402


# --- Input -------------------------------------------------------------------


def read_input() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return {}


def get_tool_input(data: dict) -> dict:
    return data.get("tool_input") or data


def get_file_info(data: dict) -> tuple[str, str, str]:
    ti = get_tool_input(data)
    file_path = (ti.get("file_path", "") or "").replace("\\", "/")
    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)
    return file_path, filename, ext.lstrip(".").lower()


def get_new_content(data: dict) -> str:
    ti = get_tool_input(data)
    return ti.get("content") or ti.get("new_string") or ""


def get_old_content(data: dict) -> str:
    ti = get_tool_input(data)
    return ti.get("old_string") or ""


# --- Counter state -----------------------------------------------------------


STATE_NAME = "veille-skips"


def load_counter(session_id: str | None, repo_root: Path) -> dict:
    """Read the session counter, flagging a state written before the digest change.

    `legacy_digest` is True when a stored fingerprint exists but was produced by
    another algorithm. Its value cannot be recomputed, so comparing it to a fresh
    digest would read an UNCHANGED marker as a new one and cost a false block
    (independent review, 2026-08-18). The caller grants one free pass, then the
    state is rewritten with its algorithm and the counter resumes normally.
    """
    data = read_state(STATE_NAME, session_id, repo_root)
    stored_hash = str(data.get("last_marker_hash", ""))
    stored_algo = str(data.get("digest_algo", ""))
    return {
        "skip_count": int(data.get("skip_count", 0)),
        "last_marker_hash": stored_hash,
        "veille_seen": bool(data.get("veille_seen", False)),
        "legacy_digest": bool(stored_hash) and stored_algo != DIGEST_ALGO,
    }


def _persist(session_id: str | None, repo_root: Path, *, skip_count: int,
             marker_hash: str, veille_seen: bool) -> None:
    write_state(
        STATE_NAME,
        {
            "skip_count": skip_count,
            "last_marker_hash": marker_hash,
            "veille_seen": veille_seen,
            "digest_algo": DIGEST_ALGO,
        },
        session_id,
        repo_root,
    )


# --- Block messages ----------------------------------------------------------


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def _block_missing_marker(file_path: str) -> None:
    block(
        "BLOCKED: Veille / SKB evidence missing before writing source code.\n"
        f"Target: {file_path}\n"
        "RECOVERY: Output one of the strict markers BEFORE retrying:\n"
        "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>\n"
        "  [SKB] consulte: <chemin1>, <chemin2>\n"
        f"  [VEILLE-SKIP] motif: <one of {sorted(ALLOWED_SKIP_MOTIFS)}>\n"
        "See rules/Workflows.md -> 'Veille/SKB Evidence Protocol'."
    )


# --- Enforcement -------------------------------------------------------------


def _enforce_sensitive(file_path: str, reason: str, marker_type: str, transcript_path: str) -> None:
    """A sensitive change requires a real [VEILLE] backed by a real web call."""
    if marker_type != "VEILLE":
        block(
            "BLOCKED: Sensitive change detected — real [VEILLE] required.\n"
            f"Target: {file_path}\n"
            f"Trigger: {reason}\n"
            f"Latest marker: [{marker_type}] (insufficient for sensitive change)\n"
            "RECOVERY: Output a real veille marker BEFORE retrying:\n"
            "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>\n"
            "Layer B refuses [SKB] and [VEILLE-SKIP] on sensitive content."
        )
    if not has_web_veille_call(transcript_path):
        block(
            "BLOCKED: [VEILLE] marker present but no web veille was actually performed.\n"
            f"Target: {file_path}\n"
            f"Trigger: {reason}\n"
            "No WebSearch / WebFetch (or MCP web) tool call found in this session.\n"
            "RECOVERY: actually run the veille — WebSearch/WebFetch the registry "
            "(hex.pm, npmjs, pypi, crates.io...) to confirm the current version, "
            "THEN re-emit [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>.\n"
            "The marker text alone is not proof; the tool call is."
        )


def _enforce_skip(file_path: str, marker_line: str, marker_hash: str,
                  counter: dict, session_id: str | None, repo_root: Path) -> None:
    """Layer A (motif enum) + Layer C (session skip counter). Preserves the
    sticky veille_seen flag across SKIPs (Jay 2026-06-16)."""
    m = SKIP_MOTIF_RE.search(marker_line)
    motif = m.group(1).lower() if m else ""
    if motif not in ALLOWED_SKIP_MOTIFS:
        block(
            "BLOCKED: VEILLE-SKIP motif is not in the closed enum.\n"
            f"Target: {file_path}\n"
            f"Motif found: '{motif or '(empty)'}'\n"
            f"RECOVERY: use one of {sorted(ALLOWED_SKIP_MOTIFS)}\n"
            "Or emit a real [VEILLE] / [SKB] marker instead."
        )
    # A legacy fingerprint is not comparable: never read it as a new marker.
    if counter["last_marker_hash"] != marker_hash and not counter.get("legacy_digest"):
        counter["skip_count"] += 1
    seen = counter.get("veille_seen", False)
    if counter["skip_count"] >= SKIP_COUNT_THRESHOLD:
        _persist(session_id, repo_root, skip_count=counter["skip_count"], marker_hash=marker_hash, veille_seen=seen)
        block(
            "BLOCKED: VEILLE-SKIP threshold reached.\n"
            f"Consecutive SKIPs this session: {counter['skip_count']} "
            f"(threshold {SKIP_COUNT_THRESHOLD}).\n"
            f"Target: {file_path}\n"
            "RECOVERY: Emit a real [VEILLE] or [SKB] marker — the counter "
            "resets only with verified evidence, not with another SKIP."
        )
    _persist(session_id, repo_root, skip_count=counter["skip_count"], marker_hash=marker_hash, veille_seen=seen)


def _session_ctx(data: dict) -> tuple[str, str, Path]:
    transcript = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    return transcript, session_id, find_repo_root()


def _handle_no_marker(file_path: str, sensitive_reason: str | None, counter: dict) -> None:
    """No marker in scan range. Sticky: a real [VEILLE]/[SKB] seen earlier this
    session covers a NON-sensitive write even if the marker scrolled out of the
    200-line scan window (Jay 2026-06-16). Sensitive changes always need a fresh
    real [VEILLE] + web call, so the sticky bypass never applies to them."""
    if not sensitive_reason and counter.get("veille_seen"):
        sys.exit(0)
    _block_missing_marker(file_path)


def _record_real_marker(session_id: str | None, repo_root: Path, counter: dict, marker_hash: str) -> None:
    """A real [VEILLE]/[SKB]: reset the skip counter and remember (sticky) that
    veille was performed this session."""
    if counter["last_marker_hash"] != marker_hash or not counter.get("veille_seen"):
        _persist(session_id, repo_root, skip_count=0, marker_hash=marker_hash, veille_seen=True)


# --- Main --------------------------------------------------------------------


def main() -> None:
    data = read_input()
    file_path, filename, ext = get_file_info(data)
    if not file_path:
        sys.exit(0)
    is_dep = file_is_dep_manifest(filename)
    if not is_dep and not needs_evidence(file_path, filename, ext):
        sys.exit(0)
    old_content = get_old_content(data)
    new_content = get_new_content(data)
    sensitive_reason = sensitive_change(file_path, filename, ext, old_content, new_content)
    # Dep manifest with no dependency change = internal edit -> no evidence (Jay 2026-06-13).
    if is_dep and sensitive_reason is None:
        sys.exit(0)
    transcript_path, session_id, repo_root = _session_ctx(data)
    counter = load_counter(session_id, repo_root)
    latest = latest_marker(transcript_path)
    if latest is None:
        _handle_no_marker(file_path, sensitive_reason, counter)
    marker_type, marker_line, marker_hash = latest
    if sensitive_reason:
        _enforce_sensitive(file_path, sensitive_reason, marker_type, transcript_path)
    if marker_type == "VEILLE-SKIP":
        _enforce_skip(file_path, marker_line, marker_hash, counter, session_id, repo_root)
        sys.exit(0)
    _record_real_marker(session_id, repo_root, counter, marker_hash)
    sys.exit(0)


if __name__ == "__main__":
    main()
