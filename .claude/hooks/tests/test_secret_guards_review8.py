"""Independent review 2026-10-19 on c5927e5 (FAIL, famille: masquage-altere-code-lu).

Seven earlier rounds hunted ways to LEAK a secret; none tried ordinary work. Two defects:
1. the output filter rewrote source code read with Read/Grep (test fixtures with passwords,
   dev compose files): an Edit then fails on the masked line, or writes the mask into the file;
2. the secret-file guard refused Claude Code's default commit form, a heredoc inside -m/--body.
Each acceptance case below has a refusal case next to it, so the fix cannot open a leak.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
REDACT = HOOKS / "guards" / "post-tool-secret-redact.py"
READ_GUARD = HOOKS / "guards" / "secret-file-read-guard.py"

FIXTURES = (
    'register_user(%{email: "not valid", password: "not valid"})\n'
    'json={"username": "a", "password": "wrongpass"}\n'
    "- POSTGRES_PASSWORD=postgres\n"
    "DATABASE_URL=postgres://postgres:postgres@localhost:5432/app_dev\n"
    "        token = self.get_token()\n"
)
VENDOR = "ghp_" + "Ab3" * 8  # fabricated, vendor-prefixed


def _redact(tool: str, response):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_response": response}
    r = subprocess.run([sys.executable, str(REDACT)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    out = r.stdout.decode("utf-8").strip()
    return json.loads(out)["hookSpecificOutput"]["updatedToolOutput"] if out else response


def _read_response(text: str) -> dict:
    return {"type": "text", "file": {"filePath": "/repo/test/auth_test.exs", "content": text}}


def test_source_code_read_comes_back_byte_for_byte():
    # Grep answers `path:n:text` lines, not this shape: covered in test_secret_guards_review10.py.
    for tool in ("Read", "Edit", "Write", "MultiEdit"):
        assert _redact(tool, _read_response(FIXTURES)) == _read_response(FIXTURES), tool


def test_a_vendor_token_in_a_read_file_is_still_masked():
    out = _redact("Read", _read_response(f"const k = '{VENDOR}'\n"))
    assert VENDOR not in json.dumps(out) and "<masque:" in json.dumps(out)


def test_bash_output_keeps_the_strict_profile():
    out = _redact("Bash", {"stdout": "POSTGRES_PASSWORD=s3cr3t-value\n", "stderr": ""})
    assert "s3cr3t-value" not in json.dumps(out)


def _guard(command: str) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(READ_GUARD)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10).returncode


def test_default_commit_and_pr_forms_are_accepted():
    # Option A (Jay 2026-10-19, after a 3rd FAIL): no message exemption. A message that does not
    # name a secret passes in every form; one that names it passes through `-F -` (see review9).
    for cmd in (
        "git commit -m \"$(cat <<'EOF'\nfix(config): read DATABASE_URL in dev\nEOF\n)\"",
        "gh pr create --title x --body \"$(cat <<'EOF'\n- secrets no longer committed\nEOF\n)\"",
        "git commit -q -F - <<'EOF'\nchore: ignore *.pem and .env\nEOF",
    ):
        assert _guard(cmd) == 0, cmd


def test_a_message_that_really_reads_the_secret_is_still_refused():
    for cmd in (
        "git commit -m \"$(cat <<EOF\n$(cat .env)\nEOF\n)\"",  # multi-line: judged on its raw text
        "gh pr create --body \"$(cat <<EOF\n`cat id_rsa`\nEOF\n)\"",
        "cat .env",
    ):
        assert _guard(cmd) == 2, cmd
