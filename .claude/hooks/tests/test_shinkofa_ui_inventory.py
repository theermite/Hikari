"""Tests for lego/shinkofa-ui-inventory.py — do not redefine a library component.

This guard had no test at all until 2026-08-30, and it carried its inventory as a
hand-written list of 79 names while the library exported 149. It could therefore
warn about barely half of what it was meant to protect: 146 files across the
workspace redefine something @shinkofa/ui already ships, and the top offenders
(ThemeProvider 12 times, Skeleton and Input 8 times each) were all in the list —
but 70 other components were not, so nothing ever flagged them.

The inventory now comes from the code (lib/ui_inventory.py). These tests hold the
behaviour that had none.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lego" / "shinkofa-ui-inventory.py"
SNAPSHOT = Path(__file__).resolve().parents[1] / "lego" / "ui-inventory.json"


def _run(file_path: str, content: str) -> subprocess.CompletedProcess:
    payload = {"tool_input": {"file_path": file_path, "content": content}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
    )


def _inventory() -> list[str]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["components"]


# --- the guard warns on a local redefinition ----------------------------------


def test_should_warn_when_a_library_component_is_redefined_locally():
    r = _run("src/components/Button.tsx", "export function Button() { return null; }")
    assert r.returncode == 0  # warning, never a block
    assert b"WARNING" in r.stderr
    assert b"Button" in r.stderr


def test_should_warn_on_a_const_arrow_component():
    content = "export const Skeleton = () => <div />;"
    r = _run("src/ui/Skeleton.tsx", content)
    assert b"WARNING" in r.stderr


def test_should_stay_silent_when_the_file_imports_the_library():
    content = "import { Button } from '@shinkofa/ui';\nexport function Button() {}"
    r = _run("src/components/Button.tsx", content)
    assert r.stderr.strip() == b""


def test_should_stay_silent_on_a_project_specific_component():
    content = "export function SpellCard() { return null; }"
    r = _run("src/components/SpellCard.tsx", content)
    assert r.stderr.strip() == b""


def test_should_stay_silent_inside_the_library_itself():
    content = "export function Button() { return null; }"
    r = _run("Shinkofa-Shared/packages/ui/src/Button.tsx", content)
    assert r.stderr.strip() == b""


def test_should_name_the_import_to_write_instead():
    r = _run("src/components/Button.tsx", "export function Button() {}")
    assert b"@shinkofa/ui" in r.stderr


# --- the inventory comes from the code, never from a copy ---------------------


def test_should_know_every_component_the_library_exports():
    """The old hand-written list held 79 of 149. A component it never heard of
    is a component it can never warn about."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("guard", HOOK)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert set(_inventory()) <= set(guard.UI_COMPONENTS)


def test_should_warn_on_a_component_the_old_hand_written_list_never_carried():
    """`WeekAgenda` ships in the library and was absent from the old list."""
    r = _run("src/components/WeekAgenda.tsx", "export function WeekAgenda() {}")
    assert b"WARNING" in r.stderr
    assert b"WeekAgenda" in r.stderr


def test_should_warn_on_another_component_absent_from_the_old_list():
    r = _run("src/games/ReactionTime.tsx", "export function ReactionTime() {}")
    assert b"WARNING" in r.stderr


# --- scope ---------------------------------------------------------------------


def test_should_ignore_non_react_files():
    for path in ("scripts/tool.py", "docs/page.html", "src/lib/button.ts"):
        r = _run(path, "export function Button() {}")
        assert r.stderr.strip() == b"", path


def test_should_ignore_tests_and_stories():
    for path in ("src/Button.test.tsx", "src/Button.stories.tsx"):
        r = _run(path, "export function Button() {}")
        assert r.stderr.strip() == b"", path


def test_should_survive_an_empty_payload():
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=b"{}", capture_output=True
    )
    assert r.returncode == 0
