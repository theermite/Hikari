#!/usr/bin/env python3
"""Deploy hook: warn if a deploy was performed without a smoke test.

Trigger: PreToolUse Bash.
Logic:
- If the current command looks like a smoke test (curl/health/status verbs
  against a known production host or local port) → mark smoke-done and pass.
- If the current command looks like a deploy verb (docker compose up,
  deploy.sh, vercel --prod, fly deploy, ssh ... docker compose up, etc.)
  → mark deploy-pending in session state.
- If a deploy is pending and the next non-deploy non-trivial Bash command
  is not a smoke test, emit a one-shot WARNING with recovery instructions.

This is heuristic: it does NOT enforce success of the smoke test, only
its presence. Reference: rules/Workflows.md > Post-Deploy Smoke Test.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    format_warn,
    get_command,
    looks_like_deploy,
    pass_through,
    read_hook_input,
    warn,
)
from session_state import mark_once, read_state, write_state  # noqa: E402

STATE_NAME = "deploy-smoke"


_SMOKE_PATTERNS = [
    re.compile(r"\bcurl\b[^\n]*\b(?:health|status|ready|alive|smoke)\b", re.IGNORECASE),
    re.compile(r"\bcurl\b[^\n]*\b-(?:I|-head)\b", re.IGNORECASE),  # HEAD check
    re.compile(r"\bcurl\b[^\n]*\bhttps?://[^\s]+/(?:health|status|api/health)"),
    re.compile(r"\bwget\b[^\n]*\b--spider\b"),
    re.compile(r"\bnpm\s+run\s+(?:smoke|e2e:prod|post-deploy)\b"),
    re.compile(r"\bpytest\b[^\n]*\b(?:smoke|post_deploy|postdeploy)\b"),
    re.compile(r"\bplaywright\s+test\b[^\n]*\bsmoke\b"),
]


def _looks_like_smoke(cmd: str) -> bool:
    return any(p.search(cmd) for p in _SMOKE_PATTERNS)


def _session_id(data: dict) -> str | None:
    return data.get("session_id") or None


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd:
        pass_through()

    sid = _session_id(data)
    state = read_state(STATE_NAME, sid)
    pending = state.get("pending_deploy", False)

    if _looks_like_smoke(cmd):
        # Smoke test ran — clear pending and remember.
        if pending or not state.get("smoke_seen", False):
            state.update({"pending_deploy": False, "smoke_seen": True})
            write_state(STATE_NAME, state, sid)
        pass_through()

    if looks_like_deploy(cmd):
        state.update({"pending_deploy": True, "smoke_seen": False})
        write_state(STATE_NAME, state, sid)
        pass_through()

    # Generic command. If a deploy is pending and we have done >= 3 commands
    # since the deploy without a smoke test, warn once.
    if pending:
        steps = int(state.get("steps_since_deploy", 0)) + 1
        state["steps_since_deploy"] = steps
        write_state(STATE_NAME, state, sid)
        if steps >= 3 and mark_once(STATE_NAME + "-warned", "warned", sid):
            warn(format_warn(
                reason=f"deploy was performed {steps} step(s) ago without a smoke test",
                action="run a smoke test now: `curl -fsS https://<host>/health` "
                       "or `npm run smoke`. Verify auth integrity, API connections, "
                       "and reverse proxy routing within 5 minutes of deploy.",
                reference="rules/Workflows.md > Post-Deploy Smoke Test",
            ))

    sys.exit(0)


if __name__ == "__main__":
    main()
