"""Third independent review (2026-10-18): a password that LOOKS like a call is still a password.

`DB_PASSWORD=Monkey(42)xyz!` came out in clear because the call-shape test ran before the
"ENV_STYLE name holds a literal" rule. Also: DB_PASS / PG_PWD / MYSQL_ROOT_PW were not secret names.
Values are fabricated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import secret_mask as sm  # noqa: E402

LEAKS = [
    ("DB_PASSWORD=Monkey(42)xyz!", "Monkey(42)xyz!"),
    ('{"password": "Monkey(42)xyz"}', "Monkey(42)xyz"),
    ("API_KEY: Sunrise(7)abc#", "Sunrise(7)abc#"),
    ("DB_PASS=Tulip9876Zq", "Tulip9876Zq"),
    ("PG_PWD=Tulip9876Zq", "Tulip9876Zq"),
    ("MYSQL_ROOT_PW=Tulip9876Zq", "Tulip9876Zq"),
]

CODE = [
    'API_KEY=os.environ.get("API_KEY")',
    "API_KEY = getenv('API_KEY')",
    'DB_PASSWORD=get_password(user)',
    'password: str = Field(min_length=8)',
    "token = get_token(user)",
    "PWD=/home/jay/work",
]


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("line,secret", LEAKS)
def test_call_shaped_and_short_named_secrets_are_masked(line, secret, strict):
    assert secret not in sm.mask_text(line, strict=strict)


@pytest.mark.parametrize("line", CODE)
def test_real_code_and_the_working_directory_stay_readable(line):
    assert sm.mask_text(line, strict=True) == line
