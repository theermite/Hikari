"""Fourth round (2026-10-18): the round-3 fix masked ordinary code.

An unquoted value stops at its first quote, so `X = re.compile(r"...")` reads as the value
`re.compile(r`. A call whose value was cut by a quote is code. Also: bare PASS is a test-runner word
(`--- PASS: TestLogin`), only `*_PASS` names a secret. Values are fabricated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import secret_mask as sm  # noqa: E402

CODE = [
    '_ISOLATED_TOKEN_RE = re.compile(r"(?<![\\w/])[A-Za-z0-9]{32,}")',
    'API_KEY_PATTERN = re.compile(r"sk-[a-z]+")',
    'JWT_SECRET = settings.get_secret(name="jwt")',
    'DB_PWD_FILE = Path("/run/secrets/db")',
    "TOKEN_COUNT = len(tokens)",
    "--- PASS: TestLogin (0.00s)",
    "PASS: tests/test_x.py::test_ok",
    "PASS=12 FAIL=0",
]

LEAKS = [
    ("DB_PASSWORD=Monkey(42)xyz!", "Monkey(42)xyz!"),
    ("DB_PASS=Tulip9876Zq", "Tulip9876Zq"),
    ("ROOT-PW=Tulip9876Zq", "Tulip9876Zq"),
    ("MYSQL_ROOT_PW=Tulip9876Zq", "Tulip9876Zq"),
]


@pytest.mark.parametrize("line", CODE)
def test_ordinary_code_and_test_runner_words_are_not_masked(line):
    """Strict profile only: it runs on every tool's output, code included. The default profile serves a
    few suspicious commands and never judged code."""
    assert sm.mask_text(line, strict=True) == line


@pytest.mark.parametrize("line,secret", LEAKS)
def test_the_secrets_stay_masked(line, secret):
    assert secret not in sm.mask_text(line, strict=True)
