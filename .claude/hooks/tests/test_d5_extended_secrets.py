"""D5 — write-guard.py extended secret patterns.

Tests that check_secrets_in_files now blocks on a wider set of known credential
patterns (AWS, OpenAI, Anthropic, DeepSeek, Groq, Slack, generic JWT secrets,
SSH private keys).

Each test imports the function directly and asserts the BLOCKED message format.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "guards" / "write-guard.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("write_guard", HOOK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["write_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def wg():
    return _load_module()


# --- Existing patterns still blocked (regression) -----------------------------


def test_stripe_live_key_still_blocked(wg):
    msg = wg.check_secrets_in_files("STRIPE_KEY = 'sk_live_abcdefghij1234567890'")
    assert msg is not None
    assert "Stripe live key" in msg
    assert "RECOVERY:" in msg


def test_github_token_still_blocked(wg):
    msg = wg.check_secrets_in_files("TOKEN = 'ghp_" + "A" * 36 + "'")
    assert msg is not None
    assert "GitHub token" in msg


def test_private_key_still_blocked(wg):
    msg = wg.check_secrets_in_files("-----BEGIN RSA PRIVATE KEY-----\n...\n-----END")
    assert msg is not None
    assert "Private key" in msg


# --- New patterns (D5) --------------------------------------------------------


def test_aws_access_key_blocked(wg):
    msg = wg.check_secrets_in_files("AWS_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE'")
    assert msg is not None
    assert "AWS access key" in msg


def test_aws_secret_key_blocked(wg):
    msg = wg.check_secrets_in_files(
        "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
    )
    assert msg is not None
    assert "AWS secret" in msg


def test_openai_key_blocked(wg):
    msg = wg.check_secrets_in_files("OPENAI_KEY = 'sk-proj-" + "A" * 48 + "'")
    assert msg is not None
    assert "OpenAI" in msg


def test_anthropic_key_blocked(wg):
    msg = wg.check_secrets_in_files(
        "ANTHROPIC = 'sk-ant-api03-" + "A" * 80 + "'"
    )
    assert msg is not None
    assert "Anthropic" in msg


def test_groq_key_blocked(wg):
    msg = wg.check_secrets_in_files("GROQ = 'gsk_" + "A" * 52 + "'")
    assert msg is not None
    assert "Groq" in msg


def test_slack_bot_token_blocked(wg):
    msg = wg.check_secrets_in_files(
        "SLACK = 'xoxb-1234567890-1234567890123-abcdefghijkl" + "mnopqrstuvwx'"
    )
    assert msg is not None
    assert "Slack" in msg


def test_openssh_private_key_blocked(wg):
    msg = wg.check_secrets_in_files(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXkt...\n-----END"
    )
    assert msg is not None
    assert "Private key" in msg or "SSH" in msg


# --- False positive guard -----------------------------------------------------


def test_no_match_on_safe_code(wg):
    safe = """
    function getUser() {
      const token = process.env.API_TOKEN;
      return fetch('/api/user', { headers: { Authorization: `Bearer ${token}` } });
    }
    """
    assert wg.check_secrets_in_files(safe) is None


def test_no_match_on_placeholder(wg):
    placeholder = "API_KEY=your_key_here  # replace with real one"
    assert wg.check_secrets_in_files(placeholder) is None


def test_no_match_on_documentation(wg):
    doc = "Stripe keys look like sk_live_XXXXX (not a real key)."
    # XXXXX is < 10 chars so the pattern requires more
    assert wg.check_secrets_in_files(doc) is None
