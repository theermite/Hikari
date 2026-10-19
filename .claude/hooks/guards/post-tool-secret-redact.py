#!/usr/bin/env python3
"""PostToolUse, every tool — replace a recognizable secret before Claude sees it.

Official hooks doc (checked 2026-10-18): `hookSpecificOutput.updatedToolOutput`
replaces the output of any tool, built-in or MCP, keeping the tool's output
shape (a value that does not match is ignored). So the walk below changes only
the text leaves of the response and keeps every key, list and type.

Strict profile of secret_mask (names, PEM, credentialed URL, JWT, vendor
prefixes): no "isolated 32+ chars" rule, which also eats test names and hashes.
Never blocks; fails open on anything unreadable. The platform's own telemetry
keeps the original output (doc caveat) — this protects the conversation only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import common  # noqa: E402
import secret_mask  # noqa: E402
import secret_files  # noqa: E402


# Tools whose output is a file's text: the next Edit must find that text byte for byte
# (independent review 2026-10-19). Only CODE gets the light mask (unambiguous forms only): a
# closed list of extensions, because the fifth review showed that granting it to "anything the
# secret-file list does not recognise" let a dated rclone.conf backup through in clear. Config,
# JSON, ini, files without extension keep the strict mask, as before. So do docs, shell and SQL
# scripts and notebooks (sixth review: a session report held a real registry password) — people
# paste credentials there; they are not the test fixtures the light mask exists for.
_FILE_TOOLS = frozenset({"Read", "Grep", "Glob", "Edit", "MultiEdit", "Write", "NotebookEdit", "NotebookRead"})
_CODE_EXTENSIONS = frozenset(
    ".py .pyi .ex .exs .heex .eex .leex .ts .tsx .mts .cts .js .jsx .mjs .cjs .vue .svelte .astro "
    ".rs .go .rb .php .java .kt .swift .c .h .cpp .hpp .cs .css .scss .html .lua .dart .zig".split())
# `path:12:text` (match) or `path-12-text` (context line, -A/-B/-C); a Windows drive keeps its colon.
_GREP_PATH = re.compile(r"^((?:[A-Za-z]:[\\/])?[^:\n]*?)(?::\d+:|-\d+-)")


def _walk(value, mask):
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, list):
        return [_walk(v, mask) for v in value]
    if isinstance(value, dict):
        if value.get("type") == "image":  # base64 payload: a rewrite would corrupt it
            return value
        return {k: _walk(v, mask) for k, v in value.items()}
    return value


def _read_path(response) -> str:
    """Read answers {"file": {"filePath"}}; Edit/Write answer {"filePath"} at the top."""
    if not isinstance(response, dict):
        return ""
    file = response.get("file")
    inner = file.get("filePath") if isinstance(file, dict) else None
    return str(inner or response.get("filePath") or "")


def _strict(text: str) -> str:
    return secret_mask.mask_text(text, strict=True)


def _is_plain_code(path: str) -> bool:
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return "." in name and "." + name.rsplit(".", 1)[-1] in _CODE_EXTENSIONS and not secret_files.is_secret_file(path)


def _mask_for_path(path: str):
    return secret_mask.mask_unambiguous if _is_plain_code(path) else _strict


def _grep_line(line: str) -> str:
    """A line whose path is not read, or not plain code, keeps the strict mask."""
    m = _GREP_PATH.match(line)
    return _mask_for_path(m.group(1) if m else "")(line)


def _mask_for(tool, response):
    """Code read by a file tool: unambiguous forms only. Everything else: the strict mask."""
    if tool == "Grep":
        return lambda text: "\n".join(_grep_line(line) for line in text.split("\n"))
    if tool in _FILE_TOOLS:
        return _mask_for_path(_read_path(response))
    return _strict


def build_decision(data: dict) -> dict | None:
    response = data.get("tool_response")
    if not isinstance(response, (str, list, dict)):
        return None
    cleaned = _walk(response, _mask_for(data.get("tool_name"), response))
    if cleaned == response:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": cleaned}}


def main() -> None:
    _, data = common.read_hook_input()
    try:
        decision = build_decision(data if isinstance(data, dict) else {})
    except Exception as exc:  # noqa: BLE001 — fail open, never break a tool result
        print(f"[post-tool-secret-redact] passing through: {exc}", file=sys.stderr)
        decision = None
    if decision is not None:
        print(json.dumps(decision))
    sys.exit(0)


if __name__ == "__main__":
    main()
