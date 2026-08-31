"""Tests for the generated @shinkofa/ui inventory — lib/ui_inventory.py.

Why this exists (measurement 2026-08-30). The Lego guard carried a hand-written
list of component names. Three numbers disagreed on the same day:

  rules/Quality.md ......... 79 components
  the package's own blurb ... 83 components
  what the code exports .... 148 components

So two thirds of the library were invisible to anyone consulting the rule, and
the guard could not warn about a component it had never heard of. Measured
consequence: 146 files across the workspace redefine something the library
already ships — ThemeProvider 12 times, Skeleton and Input 8 times each.

Family: an inventory copied by hand ages and lies. The cure is to read it from
the code. This module reads the live package when the sibling repo is present,
and falls back to a committed snapshot everywhere else (propagated repos, VPS).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))

import ui_inventory  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parents[1] / "lego" / "ui-inventory.json"


# --- reading exports out of TypeScript source ---------------------------------


def test_should_read_a_plain_named_export():
    assert "Button" in ui_inventory.exported_components("export { Button } from './Button';")


def test_should_read_several_names_from_one_export():
    line = "export { Card, CardHeader, CardTitle } from './Card';"
    names = ui_inventory.exported_components(line)
    assert {"Card", "CardHeader", "CardTitle"} <= names


def test_should_ignore_type_only_exports():
    """`export type { ButtonProps }` ships a type, never a component."""
    source = "export type { TimeInputProps } from './TimeInput';"
    assert ui_inventory.exported_components(source) == set()


def test_should_ignore_an_inline_type_inside_a_named_export():
    source = "export { Button, type ButtonProps } from './Button';"
    assert ui_inventory.exported_components(source) == {"Button"}


def test_should_ignore_lowercase_exports():
    """`cn`, `useToast`, `computeMastery` are helpers, not components."""
    source = "export { cn } from './cn';\nexport { useToast } from './toast';"
    assert ui_inventory.exported_components(source) == set()


def test_should_ignore_screaming_case_constants():
    source = "export { KI_TYPES, CENTERS } from './constants';"
    assert ui_inventory.exported_components(source) == set()


def test_should_read_a_renamed_export_under_its_public_name():
    """What consumers import is the name after `as`."""
    source = "export { InternalCard as Card } from './Card';"
    assert ui_inventory.exported_components(source) == {"Card"}


def test_should_ignore_a_commented_out_export():
    source = "// export { Retired } from './Retired';"
    assert ui_inventory.exported_components(source) == set()


def test_should_survive_an_empty_source():
    assert ui_inventory.exported_components("") == set()


# --- the snapshot shipped with the methodology ---------------------------------


def test_should_ship_a_snapshot_file():
    assert SNAPSHOT.exists(), "run scripts/generate-ui-inventory.py"


def test_should_ship_a_snapshot_that_is_valid_json_with_its_provenance():
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for key in ("generated", "source", "package_version", "components"):
        assert key in data, key
    assert isinstance(data["components"], list)


def test_should_ship_a_snapshot_far_larger_than_the_old_hand_written_list():
    """The hand-written list held 79 names; the code exports far more.

    This asserts the floor that made the old list a lie, not an exact count —
    an exact count would turn every legitimate addition into a red test.
    """
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert len(data["components"]) > 120


def test_should_ship_a_snapshot_carrying_the_most_recoded_components():
    """The three most-duplicated names of the 2026-08-30 measurement.

    If the guard cannot name these, it cannot warn about the duplication that
    actually happens.
    """
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    names = set(data["components"])
    assert {"ThemeProvider", "Skeleton", "Input"} <= names


def test_should_ship_a_sorted_snapshot_without_duplicates():
    """A stable order keeps the diff readable when the library grows."""
    names = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["components"]
    assert names == sorted(set(names))


# --- loading, wherever the methodology runs ------------------------------------


def test_should_load_the_inventory_without_the_shared_repo_present():
    """Propagated repos and the VPS have no sibling Shinkofa-Shared checkout."""
    names = ui_inventory.load(shared_root=Path("/nonexistent/Shinkofa-Shared"))
    assert len(names) > 120
    assert "ThemeProvider" in names


def test_should_prefer_the_live_package_when_it_is_present(tmp_path):
    """A snapshot ages. When the source is on disk, it wins."""
    ui = tmp_path / "packages" / "ui" / "src"
    ui.mkdir(parents=True)
    (ui / "index.ts").write_text("export { BrandNewThing } from './x';", encoding="utf-8")
    names = ui_inventory.load(shared_root=tmp_path)
    assert "BrandNewThing" in names


def test_should_fall_back_to_the_snapshot_when_the_live_package_reads_empty(tmp_path):
    """An empty or broken checkout must not silently disarm the guard."""
    (tmp_path / "packages" / "ui" / "src").mkdir(parents=True)
    names = ui_inventory.load(shared_root=tmp_path)
    assert len(names) > 120


@pytest.mark.parametrize("helper", ["cn", "useToast", "getCroppedImg", "computeMastery"])
def test_should_keep_helpers_out_of_the_snapshot(helper: str):
    names = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["components"]
    assert helper not in names


# --- the minimum-foundation list is bound to its rule, not copied from it ------
#
# Independent review 2026-08-30, SECOND failure of the same family named that
# day: "two copies of one truth drift apart". The CDC template printed a
# 15-line foundation claiming Quality.md as its source, while the rule listed 13
# different items — the copy had drifted before its first use.
#
# Patching the list would have reopened the family one edit later, so the
# approach changed: the two are now bound by this test. The rule is the source;
# the template mirrors it; a divergence turns the suite red.

REPO = Path(__file__).resolve().parents[3]
QUALITY_RULE = REPO / ".claude" / "rules" / "Quality.md"
CDC_TEMPLATE = REPO / "templates" / "docs-structure" / "CDC.md"

# `templates/` is Kata-only scaffolding — propagate-methodology.py rsyncs
# only rules/, agents/, hooks/, skills/ to the other 31 repos (its own
# docstring lists templates/ under "NOT touched"). This test's whole
# premise (Kata's CDC template mirroring Kata's own Quality.md) cannot
# apply to a repo that never received the template. Discovered 2026-08-31
# propagating the secret-masking guard: every single target repo failed
# this test identically, correctly blocking a broken sync — the file
# simply isn't there to fail against.
_TEMPLATE_MISSING_REASON = "templates/docs-structure/CDC.md is Kata-only, never propagated"


def _rule_checklist() -> list[str]:
    """The items of Quality.md > Universal Project Checklist, in order."""
    text = QUALITY_RULE.read_text(encoding="utf-8")
    start = text.index("## Universal Project Checklist")
    body = text[start:].split("\n\n", 2)[1]
    body = body.split("Every project from day 1:", 1)[-1]
    return [item.strip(" .\n") for item in body.replace("\n", " ").split("·") if item.strip(" .\n")]


def _template_foundation() -> list[str]:
    """The `Réf. règle` column of CDC 3bis, in order.

    The template carries the rule's own wording verbatim in its own column, so
    the binding is an exact string comparison — not a fuzzy guess that would
    quietly stop matching the day someone rephrases a row in French.
    """
    text = CDC_TEMPLATE.read_text(encoding="utf-8")
    start = text.index("## 3bis.")
    rows = []
    for line in text[start:].splitlines():
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) >= 3 and cells[0].isdigit():
            rows.append(cells[2].strip("`"))
    return rows


@pytest.mark.skipif(not CDC_TEMPLATE.exists(), reason=_TEMPLATE_MISSING_REASON)
def test_should_print_a_foundation_row_for_every_rule_item():
    assert len(_template_foundation()) == len(_rule_checklist())


@pytest.mark.skipif(not CDC_TEMPLATE.exists(), reason=_TEMPLATE_MISSING_REASON)
def test_should_mirror_the_rule_wording_verbatim_and_in_order():
    """An exact match both ways: rephrasing the rule turns this red at once."""
    assert _template_foundation() == _rule_checklist()


@pytest.mark.skipif(not CDC_TEMPLATE.exists(), reason=_TEMPLATE_MISSING_REASON)
def test_should_never_carry_a_foundation_row_absent_from_the_rule():
    """A row smuggled into the template is a rule nobody agreed to."""
    assert set(_template_foundation()) <= set(_rule_checklist())
