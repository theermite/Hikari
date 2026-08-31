#!/usr/bin/env python3
"""PostToolUse Bash — warn (never block) when a secret survived into output.

Fallback net for pre-bash-secret-mask.py: that hook only wraps a fixed list
of suspicious commands (docker exec, docker compose config, ssh+docker, cat
.env, printenv). Any OTHER command can still print a secret nobody expected.

This hook CANNOT redact what already ran — `updatedToolOutput` is ignored on
this Claude Code build (verified live, 2026-08-30: a PostToolUse hook that
returns it has zero effect, the model still receives the real output). All
it can do is warn loudly so the value gets rotated (brief §6, honest limit).

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
