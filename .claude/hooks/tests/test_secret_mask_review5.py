"""Fifth round (2026-10-18): real lines of this repository that the strict profile masked by mistake.

The third reviewer ran the mask over every tracked source line and found 17 changed. The cause was
shape tests that stripped a closing bracket before judging an identifier, a quoted key holding a
bare identifier (Python dict), and version ranges under a `*-key` name. Values are fabricated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import secret_mask as sm  # noqa: E402

CODE = [
    "token = args[i]",
    "token = tokens[i]",
    '"client_secret": client_secret,',
    "project_canonical_keys: set[tuple[str, str, str]] = set()",
    '"path-key": "^3.1.0",',
    "def f(token: Optional[str] = None):",
    'secret = cfg["secret"]',
]

STILL_MASKED = [
    ('{"password": "hunter2xyzQ"}', "hunter2xyzQ"),
    ("DB_PASSWORD=Monkey(42)xyz!", "Monkey(42)xyz!"),
    ('"api_key": "Qwerty123456789"', "Qwerty123456789"),
    ("API_KEY=Tulip9876Zq", "Tulip9876Zq"),
]


@pytest.mark.parametrize("line", CODE)
def test_real_code_lines_are_not_masked(line):
    assert sm.mask_text(line, strict=True) == line


@pytest.mark.parametrize("line,secret", STILL_MASKED)
def test_literal_secrets_stay_masked(line, secret):
    assert secret not in sm.mask_text(line, strict=True)
