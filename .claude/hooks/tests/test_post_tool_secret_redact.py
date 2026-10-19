"""guards/post-tool-secret-redact.py — PostToolUse on EVERY tool.

Replaces a recognizable secret with <masque:N car.> in the tool output before
Claude sees it (`updatedToolOutput`), keeping the structure. The strict profile
leaves long test names and commit hashes alone (the 32+ chars rule is off).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "post-tool-secret-redact.py"
SECRET = "API_TOKEN=Zq8" + "x" * 20 + "R2m"  # fabricated
LONG_NAME = "test_literal_dollars_and_quoted_heredocs_stay_accepted"
SHA = "a" * 40


def _run(response, tool="Bash") -> tuple[int, dict | None]:
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_response": response}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    out = r.stdout.decode("utf-8").strip()
    return r.returncode, (json.loads(out) if out else None)


def _updated(out):
    return out["hookSpecificOutput"]["updatedToolOutput"]


def test_bash_stdout_secret_is_masked_and_shape_kept():
    rc, out = _run({"stdout": f"ok\n{SECRET}\n", "stderr": "", "interrupted": False, "isImage": False})
    assert rc == 0
    u = _updated(out)
    assert "Zq8" not in json.dumps(u) and "<masque:" in u["stdout"]
    assert set(u) == {"stdout", "stderr", "interrupted", "isImage"} and u["interrupted"] is False


def test_read_tool_nested_content_is_masked():
    rc, out = _run({"type": "text", "file": {"filePath": "/x/.env", "content": SECRET, "numLines": 1}}, tool="Read")
    assert "Zq8" not in json.dumps(_updated(out))
    assert _updated(out)["file"]["filePath"] == "/x/.env"


def test_mcp_block_list_is_masked():
    rc, out = _run([{"type": "text", "text": f"value {SECRET}"}], tool="mcp__x__get")
    u = _updated(out)
    assert u[0]["type"] == "text" and "Zq8" not in u[0]["text"]


def test_plain_string_output_is_masked():
    rc, out = _run(f"x {SECRET}", tool="WebFetch")
    assert "Zq8" not in _updated(out)


def test_known_prefix_token_without_a_name_is_masked():
    tok = "ghp_" + "A1b2C3d4E5" * 3 + "zz"
    rc, out = _run({"stdout": f"found {tok} here"})
    assert tok not in _updated(out)["stdout"]


def test_long_test_names_and_commit_hashes_are_left_alone():
    rc, out = _run({"stdout": f"FAILED {LONG_NAME}\ncommit {SHA}\n"})
    assert rc == 0 and out is None


def test_clean_output_answers_nothing():
    rc, out = _run({"stdout": "hello", "stderr": ""})
    assert rc == 0 and out is None


def test_unreadable_input_fails_open():
    for raw in (b"", b"not json", b'{"tool_response": 5}'):
        r = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, timeout=10)
        assert r.returncode == 0 and r.stdout.strip() == b""


def test_image_blocks_are_never_touched():
    img = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AKIA" + "A" * 40}}
    rc, out = _run([img], tool="Read")
    assert rc == 0 and out is None
