"""lifecycle/pasted-secret-alert.py — UserPromptSubmit: Jay pasted a secret.

A prompt cannot be rewritten, so the secret is already in the conversation. The hook
cannot undo that; it tells Jay to rotate it (systemMessage) and tells Takumi never to
repeat, write or send it (additionalContext). Silent on an ordinary prompt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "pasted-secret-alert.py"


def _run(prompt):
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    out = r.stdout.decode("utf-8").strip()
    return r.returncode, (json.loads(out) if out else None)


def test_a_pasted_assignment_triggers_both_messages():
    rc, out = _run("voilà la clé : API_TOKEN=Zq8xxxxxxxxxxxxxxxxxR2m")
    assert rc == 0
    assert "renouvel" in out["systemMessage"].lower()
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "jamais" in ctx.lower() and "Zq8" not in json.dumps(out)


def test_a_pasted_vendor_token_triggers():
    rc, out = _run("mon jeton ghp_" + "A1b2C3d4E5" * 3 + "zz")
    assert out is not None and "ghp_" not in json.dumps(out)


def test_ordinary_prompts_stay_silent():
    for p in ("peux-tu vérifier le build ?", "le test_literal_dollars_and_quoted_heredocs_stay_accepted échoue",
              "commit " + "a" * 40, "password: str dans la signature", ""):
        rc, out = _run(p)
        assert rc == 0 and out is None, p


def test_unreadable_input_fails_open():
    for raw in (b"", b"not json", b'{"prompt": 5}'):
        r = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, timeout=10)
        assert r.returncode == 0 and r.stdout.strip() == b""


def test_messages_that_are_not_jays_stay_silent():
    secretish = "API_TOKEN=Zq8xxxxxxxxxxxxxxxxxR2m"
    for frame in ("<agent-message from=\"a\">%s</agent-message>", "Another Claude session sent:\n<agent-message>%s",
                  "<task-notification>%s</task-notification>", "<system-reminder>%s</system-reminder>",
                  "[Subagent hand-back] %s", "<cross-session-message from=\"x\">%s"):
        rc, out = _run(frame % secretish if "%s" in frame else frame)
        assert rc == 0 and out is None, frame
