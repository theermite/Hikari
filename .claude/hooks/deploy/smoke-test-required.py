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
    pass_through,
    read_hook_input,
    warn,
)
from deploy_reader import is_gated  # noqa: E402
from shell_parse import simple_commands  # noqa: E402
from session_state import mark_once, read_state, write_state  # noqa: E402

STATE_NAME = "deploy-smoke"


_SMOKE_PATTERNS = [
    re.compile(r"\bcurl\b[^\n]*\b(?:health|status|ready|alive|smoke)\b", re.IGNORECASE),
    re.compile(r"\bcurl\b[^\n]*\b-(?:I|-head)\b", re.IGNORECASE),  # HEAD check
    re.compile(r"\bcurl\b[^\n]*\bhttps?://[^\s]+/(?:health|status|api/health)"),
    # Le repli que prescrit le garde « en ligne » lui-même : curl -fsS -o /dev/null -w "%{http_code}" <url>, sur l'adresse ou sur un
    # parcours critique (relecture indépendante du 2026-11-02, D1). Tout curl vers une adresse http(s) lancé APRÈS la mise en ligne
    # est un contrôle ; le garde pèse la sortie citée, pas la forme de la commande.
    re.compile(r"\bcurl(?:\.exe)?\b[^\n]*\bhttps?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])"),   # un serveur de dev n'est pas « en ligne »
    re.compile(r"\bwget\b[^\n]*\bhttps?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])"),
    re.compile(r"\bwget\b[^\n]*\b--spider\b"),
    re.compile(r"\bnpm\s+run\s+(?:smoke|e2e:prod|post-deploy)\b"),
    re.compile(r"\bpytest\b[^\n]*\b(?:smoke|post_deploy|postdeploy)\b"),
    re.compile(r"\bplaywright\s+test\b[^\n]*\bsmoke\b"),
]


def _looks_like_smoke(cmd: str) -> bool:
    return any(p.search(cmd) for p in _SMOKE_PATTERNS)


def _session_id(data: dict) -> str | None:
    return data.get("session_id") or None


# Un appel au serveur web de Jay est un contrôle réel (décision du 2026-10-30) : `web_check` sur l'adresse publique,
# ou un vrai navigateur sans écran sur le VPS. Le garde ne lisait que `curl`.
_SMOKE_TOOLS = ("web_check", "browser_open", "browser_act", "browser_screenshot")


def _is_smoke_tool(data: dict) -> bool:
    name = str(data.get("tool_name") or "")
    return name.startswith("mcp__shinkofa-web__") and name.rsplit("__", 1)[-1] in _SMOKE_TOOLS


def _mark_checked(state: dict, sid: str | None) -> None:
    state.update({"pending_deploy": False, "smoke_seen": True})
    write_state(STATE_NAME, state, sid)


def _warn_late(state: dict, sid: str | None) -> None:
    """A deploy is pending and a few commands later still no check: warn once."""
    steps = int(state.get("steps_since_deploy", 0)) + 1
    state["steps_since_deploy"] = steps
    write_state(STATE_NAME, state, sid)
    if steps >= 3 and mark_once(STATE_NAME + "-warned", "warned", sid):
        warn(format_warn(
            reason=f"deploy was performed {steps} step(s) ago without a smoke test",
            action="run a smoke test now: `web_check` (shinkofa-web) on the public URL and one critical path, or "
                   "`curl -fsS https://<host>/health`. « Online » means reachable AND working: quote the output "
                   "before telling Jay it is online.",
            reference="rules/Workflows.md > Post-Deploy Smoke Test",
        ))


_NOT_RUNNERS = {"git", "gh", "echo", "printf", "cat", "grep", "rg", "tee", "sed", "awk"}   # they QUOTE a command, they do not run it


def _runs_a_check(cmd: str) -> bool:
    """A smoke-test command among the REAL commands of the line (a commit message that cites `curl https://…` is not one)."""
    try:
        segments = simple_commands(cmd)
    except ValueError:
        return _looks_like_smoke(cmd)   # unreadable: read it raw, as before
    return any(_looks_like_smoke(" ".join(s)) for s in segments
               if s and s[0].replace("\\", "/").rsplit("/", 1)[-1].lower() not in _NOT_RUNNERS)


def _is_check(data: dict, cmd: str) -> bool:
    """A real check: a call to the web server's tools, or a smoke-test command line."""
    return _is_smoke_tool(data) or (bool(cmd) and _runs_a_check(cmd))


def main() -> None:
    _, data = read_hook_input()
    sid = _session_id(data)
    state = read_state(STATE_NAME, sid)
    cmd = "" if _is_smoke_tool(data) else get_command(data)
    if _is_check(data, cmd):
        _mark_checked(state, sid)
        pass_through()
    if not cmd:
        pass_through()
    if is_gated(cmd, publishes=False):  # une note qui CITE « docker compose up » n'est pas une mise en ligne
        state.update({"pending_deploy": True, "smoke_seen": False})
        write_state(STATE_NAME, state, sid)
        pass_through()
    if state.get("pending_deploy", False):
        _warn_late(state, sid)
    sys.exit(0)


if __name__ == "__main__":
    main()
