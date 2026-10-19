"""Second independent review (2026-10-18): the strict profile must not trade one
defect for another. Code stays untouched AND passwords with symbols are masked.

Values are fabricated. The measure that caught the regression: random passwords,
one assignment per line, .env / JSON / YAML shapes.
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import secret_mask as sm  # noqa: E402

SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/|~"
ALNUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _password(rng: random.Random, alphabet: str, n: int = 20) -> str:
    # a quote or backslash would end a quoted value: not a leak of the mask
    return "".join(rng.choice(alphabet) for _ in range(n))


def _leaks(line: str, secret: str) -> bool:
    return secret in sm.mask_text(line, strict=True)


@pytest.mark.parametrize("alphabet", [ALNUM + SYMBOLS, ALNUM + "!@#$%^&*", ALNUM + "_"])
def test_symbol_passwords_are_masked_in_every_config_shape(alphabet):
    rng = random.Random(7)
    leaked = 0
    total = 0
    for _ in range(300):
        pw = _password(rng, alphabet)
        for line in (f"DB_PASSWORD={pw}", f'"password": "{pw}"', f"password: {pw}", f"API_KEY: {pw}"):
            total += 1
            leaked += _leaks(line, pw)
    assert leaked / total < 0.02, f"{leaked}/{total} leaked"


def test_words_joined_by_underscores_are_masked_for_an_env_name():
    assert not _leaks("DB_PASSWORD=correct_horse_battery_staple", "correct_horse_battery_staple")


def test_lowercase_yaml_password_with_symbols_is_masked():
    assert not _leaks("password: p@ss$word*1x", "p@ss$word*1x")


@pytest.mark.parametrize("line", [
    "token = self.get_token()",
    "def f(password: str, api_key: str):",
    "  password: string;",
    "secret_key_base: System.get_env(\"X\")",
    "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}",
    "client = Client(api_key=api_key)",
    "auth = os.environ.get",
    "self.token = token",
    "password = userPassword",
    "_AUTH_COMPOUND = r\"AUTHORI[SZ]ATION|AUTHENTICATE\"",
    "headers = {\"Authorization\": f\"Bearer {token}\"}",
    "req.getHeader(\"Authorization\")",
    "Refresh token: rotated on each use.",
    "auth : factuel, sans prefixe.",
])
def test_ordinary_code_and_prose_stay_untouched(line):
    assert sm.mask_text(line, strict=True) == line


def test_a_real_authorization_header_is_still_masked():
    assert "abc123def456" not in sm.mask_text("Authorization: Bearer abc123def456", strict=True)


def test_a_secret_straddling_a_chunk_boundary_is_still_masked():
    pw = "Zq8" + "x" * 30 + "R2m"
    line = "a" * 995 + " DB_PASSWORD=" + pw + " " + "b" * 50
    assert pw not in sm.mask_text(line, strict=True)


def test_many_word_boundaries_stay_fast():
    # "a-" * N has a \b every other char: the input that defeats a single-word test
    t0 = time.time()
    sm.mask_text("a-" * 80_000, strict=True)
    assert time.time() - t0 < 3.0
