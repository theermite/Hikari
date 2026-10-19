#!/usr/bin/env python3
"""PostToolUse Bash — warn (never block) when a secret survived into output.

Fallback net for pre-bash-secret-mask.py: that hook only wraps a fixed list
of suspicious commands (docker exec, docker compose config, ssh+docker, cat
.env, printenv). Any OTHER command can still print a secret nobody expected.

This hook only warns. The redaction itself is guards/post-tool-secret-redact.py
(PostToolUse on every tool, `updatedToolOutput`, verified live 2026-10-18 on a
Read; the 2026-08-30 "no effect" finding no longer holds on this build). This
net stays for what the strict profile lets through (a secret with the 32+ chars
shape and no name or prefix): warn loudly so the value gets rotated.

RECOVERY PRINCIPLE: never blocks — the leak already happened, blocking now
protects nothing (same principle as pre-bash-secret-mask.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import common  # noqa: E402
import secret_mask  # noqa: E402


def build_decision(data: dict) -> dict | None:
    response = data.get("tool_response") or {}
    stdout = response.get("stdout") or ""
    stderr = response.get("stderr") or ""
    combined = f"{stdout}\n{stderr}"
    if not secret_mask.has_secret(combined):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "systemMessage": (
                "WARNING: this command's output contained a value shaped like a "
                "secret (recognizable name or form). It already reached the "
                "conversation — this hook cannot mask it after the fact. "
                "Rotate/renouveler the credential now. See "
                "docs/Briefs/Hook-Masquage-Secrets-Sorties-Bash-2026-08-30.md §6."
            ),
        }
    }


def main() -> None:
    _, data = common.read_hook_input()
    decision = build_decision(data)
    if decision is not None:
        print(json.dumps(decision))
    sys.exit(0)


if __name__ == "__main__":
    main()
