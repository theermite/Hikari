"""quality/serveur-web-d-abord.py — PreToolUse WebSearch|WebFetch: warn once when the web server is declared.

Jay 2026-10-31 : « si on utilise en priorité le MCP Shinkofa Web, les recherches ne nous coûtent rien ».
Règle 06-Capacites § 1 : le serveur web d'abord, l'outil intégré en repli déclaré. Ce crochet ne bloque
jamais : il rappelle une fois par séance et par outil, seulement si le serveur est déclaré dans la configuration.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "serveur-web-d-abord.py"


def _home(tmp_path: Path, serveurs: dict) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(json.dumps({"mcpServers": serveurs}), encoding="utf-8")
    return home


def _run(tmp_path: Path, home: Path, outil: str, session: str = "s1") -> subprocess.CompletedProcess:
    depot = tmp_path / "depot"
    (depot / ".git").mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    payload = {"hook_event_name": "PreToolUse", "tool_name": outil, "session_id": session,
               "tool_input": {"query": "pg async io"}, "cwd": str(depot)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=15, cwd=depot, env=env)


def test_warns_when_the_server_is_declared(tmp_path):
    r = _run(tmp_path, _home(tmp_path, {"shinkofa-web": {}}), "WebSearch")
    assert r.returncode == 0
    assert b"web_search" in r.stdout + r.stderr


def test_silent_when_the_server_is_not_declared(tmp_path):
    r = _run(tmp_path, _home(tmp_path, {"autre": {}}), "WebSearch")
    assert r.returncode == 0 and (r.stdout + r.stderr).strip() == b""


def test_warns_only_once_per_session_and_tool(tmp_path):
    home = _home(tmp_path, {"shinkofa-web": {}})
    assert b"web_search" in (_run(tmp_path, home, "WebSearch").stdout)
    assert _run(tmp_path, home, "WebSearch").stdout.strip() == b""
    assert b"web_read" in (_run(tmp_path, home, "WebFetch").stdout)


def test_never_blocks_and_fails_open_on_garbage(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True, timeout=15)
    assert r.returncode == 0


def test_ignores_other_tools(tmp_path):
    r = _run(tmp_path, _home(tmp_path, {"shinkofa-web": {}}), "Read")
    assert r.returncode == 0 and r.stdout.strip() == b""
