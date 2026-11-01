"""function-complexity-check — a violation the edit did not cause is not the edit's to pay.

Measured 2026-10-31: 28 blocks in 5 sessions, most of them on a function that was already over the
limit before the edit (the gate reads the whole file). The gate now compares with the committed
version: a function over the limit that is not WORSE than before is an inherited one — reported, not
blocking. A new function, or one made longer / more complex, still blocks.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "function-complexity-check.py"
_spec = importlib.util.spec_from_file_location("function_complexity_check", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _long(name: str, lines: int = 31) -> str:
    return f"def {name}():\n" + "".join(f"    x{i} = {i}\n" for i in range(lines))


def _split(now: str, before: str | None):
    return gate.split_violations(now, before)


def test_a_long_function_that_was_already_long_is_inherited():
    new, inherited = _split(_long("big") + "\ndef small():\n    return 1\n", _long("big"))
    assert new == [] and len(inherited) == 1


def test_a_function_made_longer_is_new():
    new, inherited = _split(_long("big", 40), _long("big", 31))
    assert len(new) == 1 and inherited == []


def test_a_function_made_shorter_but_still_long_is_inherited():
    new, inherited = _split(_long("big", 33), _long("big", 40))
    assert new == [] and len(inherited) == 1


def test_a_new_long_function_is_new():
    new, _ = _split(_long("big") + "\n" + _long("another"), _long("big"))
    assert len(new) == 1 and "another" in new[0]


def test_without_a_committed_version_everything_is_new():
    new, inherited = _split(_long("big"), None)
    assert len(new) == 1 and inherited == []


def test_an_unparseable_committed_version_counts_as_none():
    new, inherited = _split(_long("big"), "def broken(:\n")
    assert len(new) == 1 and inherited == []


def test_complexity_follows_the_same_rule():
    branches = "def f(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(11)) + "    return 0\n"
    new, inherited = _split(branches, branches)
    assert new == [] and len(inherited) == 1
    more = branches[: -len("    return 0\n")] + "    if x == 99:\n        return 1\n    return 0\n"
    new, _ = _split(more, branches)
    assert len(new) == 1
