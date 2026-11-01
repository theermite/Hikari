"""Corrections after the independent review of 2026-10-31 (echo channel, complexity key, ports measure)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))
import echoed_text as et  # noqa: E402

_s = importlib.util.spec_from_file_location("fcc", HOOKS / "quality" / "function-complexity-check.py")
fcc = importlib.util.module_from_spec(_s)
_s.loader.exec_module(fcc)

BACKSLASH = chr(92)


def test_printf_as_typed_in_a_shell_is_heard():
    assert et.echoed_text("printf '%s" + BACKSLASH + "n' '[REVIEW] x'") == "[REVIEW] x"


def test_a_newline_outside_quotes_chains_a_second_command():
    assert et.echoed_text("echo a\ntouch y") == ""
    assert et.echoed_text("echo a\r\ntouch y") == ""


def test_a_newline_inside_quotes_is_kept():
    assert et.echoed_text('echo "a\nb"') == "a\nb"


def _long(name, lines=31, indent=""):
    return f"{indent}def {name}():\n" + "".join(f"{indent}    x{i} = {i}\n" for i in range(lines))


def test_a_method_of_the_same_name_in_another_class_is_new():
    before = "class A:\n" + _long("run", 60, "    ")
    now = before + "class B:\n" + _long("run", 50, "    ")
    new, inherited = fcc.split_violations(now, before)
    assert len(new) == 1 and "B.run" in new[0] and len(inherited) == 1


def test_the_same_method_not_worsened_is_inherited():
    code = "class A:\n" + _long("run", 40, "    ")
    new, inherited = fcc.split_violations(code, code)
    assert new == [] and len(inherited) == 1
