"""Fifth independent review 2026-10-19 on 187050e (FAIL, famille: masque-allege-sans-reconnaissance).

The light mask (written so that code read with Read can still be edited) was granted to every file
the secret-file list did not recognise. A real file on the server, a dated rclone.conf backup, came
back in clear where the strict mask hid it the day before. Inverted: the light mask is granted only
to a CLOSED list of code extensions; config, JSON, files without extension keep the strict mask.
Also: two ways to reach the Fable model that the ban guard missed (`--fallback-model`, a slash
command whose header sets the model).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
REDACT = HOOKS / "guards" / "post-tool-secret-redact.py"
BAN = HOOKS / "guards" / "model-ban-guard.py"
sys.path.insert(0, str(HOOKS / "lib"))
from secret_files import is_secret_file  # noqa: E402

TOKEN_LINE = 'token = {"access_token":"ya29.a0AfB_byC-fabricated-0123456789","refresh_token":"1//0fabricated"}\n'
FIXTURE = 'register_user(%{email: "not valid", password: "not valid"})\n'


def _redact(tool: str, response) -> str:
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_response": response}
    r = subprocess.run([sys.executable, str(REDACT)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    out = r.stdout.decode("utf-8").strip()
    return json.dumps(json.loads(out)["hookSpecificOutput"]["updatedToolOutput"] if out else response)


def _read(path: str, content: str) -> str:
    return _redact("Read", {"type": "text", "file": {"filePath": path, "content": content}})


def test_unrecognised_non_code_files_keep_the_strict_mask():
    for path in ("/home/u/.config/rclone/rclone.conf.backup-2026-05-21", "/repo/.git/config",
                 "/repo/alembic.ini", "/repo/docker-compose.yml", "/repo/secrets/creds"):
        assert "fabricated" not in _read(path, TOKEN_LINE + "password = hunter2-fabricated\n"), path


def test_code_files_get_the_light_mask():
    for path in ("/repo/test/auth_test.exs", "/repo/tests/test_login.py", "/repo/src/auth.test.ts"):
        assert 'password: \\"not valid\\"' in _read(path, FIXTURE), path


def test_grep_reads_the_path_of_context_lines_and_windows_drives():
    content = ("config/prod.secret.exs-4-  secret_key_base: \"fabricated-skb-0123456789\"\n"
               "C:\\Users\\u\\app\\.env:2:TOKEN=fabricated-tok-0123456789\n"
               "7:password = fabricated-nopath\n"
               "test/auth_test.exs:12:" + FIXTURE)
    out = _redact("Grep", {"mode": "content", "content": content})
    assert "fabricated" not in out
    assert 'password: \\"not valid\\"' in out


def test_more_secret_files_are_recognised():
    for p in ("rclone.conf.backup-2026-05-21", ".env.backup-2026-01-01", "client_secret_123.apps.googleusercontent.com.json",
              "client_secret.json", "myproj/local_settings.py", "wp-config.php"):
        assert is_secret_file(p), p
    for p in ("settings.py", "config.php", "client.json", "backup.py", "env.py"):
        assert not is_secret_file(p), p


def _ban(tool: str, tool_input: dict) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    return subprocess.run([sys.executable, str(BAN)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10).returncode


def test_other_ways_to_reach_the_banned_model_are_refused():
    word = "fa" + "ble"
    for cmd in (f"claude --fallback-model {word} -p x", f"claude --fallback-model=claude-{word}-5 -p x",
                f"claude config set model {word}", f"claude config set -g model claude-{word}-5"):
        assert _ban("Bash", {"command": cmd}) == 2, cmd
    assert _ban("Write", {"file_path": "/repo/.claude/commands/x.md",
                          "content": f"---\nmodel: {word}\n---\nfais\n"}) == 2
    assert _ban("Bash", {"command": "claude --fallback-model sonnet -p x"}) == 0


def test_the_ban_refusal_names_the_tools_to_fix_a_mention():
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent",
               "tool_input": {"description": "x", "prompt": "y", "model": "fa" + "ble"}}
    r = subprocess.run([sys.executable, str(BAN)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    assert r.returncode == 2 and "Grep" in r.stderr.decode("utf-8")


def test_files_where_people_copy_credentials_keep_the_strict_mask():
    # 6th review on ac1a88b (PASS, finding 1): a session report (.md) held a real registry password
    # that the light mask let through. Docs, shell and SQL scripts, notebooks: humans paste there.
    line = "npm login --registry https://npm.example.org  # password: Fabricated-Reg1stry-Pass\n"
    for path in ("/repo/docs/Sessions/Session-2026-04-12-004.md", "/repo/scripts/deploy.sh",
                 "/repo/db/seed.sql", "/repo/notebooks/explore.ipynb", "/repo/docs/guide.mdx"):
        assert "Fabricated-Reg1stry-Pass" not in _read(path, line), path
