"""Tests for lego/morphic-decoy-check.py — the morphic decoy gate.

Why this gate exists (2026-08-30 audit, 4 repos affected): the existing Lego
guard detects a duplicate by its NAME. A hand-rolled comfort-settings panel is
never named like the real one — that is precisely why it got rebuilt. So the
detection has to be on the axis VOCABULARY (theme / motion / contrast / density /
font / colorblind), which is stable and distinctive, and it has to read HTML
mockups too. Both misses were confirmed in production artefacts.

Semantics:
  - 3+ distinct axis labels and no morphic module reference -> BLOCK (exit 2)
  - 2 distinct axis labels and no morphic module reference  -> WARN (exit 0 + stderr)
  - any morphic module reference present                    -> PASS (silent)
  - non-UI file types (.md, .py, .json, ...)                -> PASS (silent)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "lego" / "morphic-decoy-check.py"


def _run(file_path: str, content: str) -> subprocess.CompletedProcess:
    payload = {"tool_input": {"file_path": file_path, "content": content}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
    )


# --- BLOCK: a full hand-rolled panel ------------------------------------------


def test_should_block_when_html_mockup_draws_three_axes_without_module():
    """The Boken / Hibiki / Hikari case: a static mockup popover, zero module."""
    content = """
    <div class="pop" id="morphicPop">
      <h4>Adaptation morphique</h4>
      <div class="seg"><button>Theme</button></div>
      <div class="seg"><button>Animation</button></div>
      <div class="seg"><button>Densite</button></div>
    </div>
    """
    r = _run("docs/maquette/index.html", content)
    assert r.returncode == 2
    assert b"BLOCKED" in r.stderr
    assert b"morphic" in r.stderr.lower()


def test_should_block_when_tsx_reimplements_axes_without_module():
    """The Shinkofa-Browser mockup case: React, home-made context, no package."""
    content = """
    import { useMorphic } from '../context/MorphicContext';
    export function AdaptationMorphiqueContenu() {
      return (<div>
        <section>Contraste eleve</section>
        <section>Densite</section>
        <section>Daltonisme</section>
      </div>);
    }
    """
    r = _run("mockup/src/components/AdaptationMorphiqueContenu.tsx", content)
    assert r.returncode == 2


def test_should_name_the_real_module_in_the_block_message():
    """A block that does not say what to use instead sends the reader nowhere."""
    content = "<h4>Adaptation morphique</h4><b>Densite</b><b>Contraste eleve</b><b>Daltonisme</b>"
    r = _run("docs/mockup.html", content)
    assert r.returncode == 2
    assert b"@theermite/morphic-adapter" in r.stderr
    assert b"RECOVERY" in r.stderr


# --- WARN: a partial signal ----------------------------------------------------


def test_should_warn_but_not_block_on_two_axes_without_module():
    """Two labels is a suspicion, not a panel. The 2026-08-19 decision applies:
    a blocking check founded on a guess costs more than it earns.

    One of the two must be an anchor (2026-08-30): two generic words are just an
    ordinary screen, and warning on those is noise that gets the gate ignored.
    """
    content = "<div><span>Daltonisme</span><span>Densite compacte</span></div>"
    r = _run("docs/mockup.html", content)
    assert r.returncode == 0
    assert b"WARNING" in r.stderr


def test_should_stay_silent_on_two_generic_axes_without_an_anchor():
    """The counterpart: no anchor, no accusation, not even a whisper."""
    content = "<div><span>Theme sombre</span><span>Densite compacte</span></div>"
    r = _run("docs/mockup.html", content)
    assert r.returncode == 0
    assert r.stderr.strip() == b""


def test_should_pass_silently_on_a_single_axis_label():
    content = "<div><span>Theme sombre</span></div>"
    r = _run("docs/mockup.html", content)
    assert r.returncode == 0
    assert r.stderr.strip() == b""


# --- PASS: the real module is referenced --------------------------------------


def test_should_pass_when_tsx_imports_the_real_adapter():
    content = """
    import { MorphicButton } from '@theermite/morphic-adapter/ui';
    export function Nav() {
      return (<div>Theme Densite Contraste eleve Daltonisme<MorphicButton /></div>);
    }
    """
    r = _run("src/components/TopNav.tsx", content)
    assert r.returncode == 0
    assert r.stderr.strip() == b""


def test_should_pass_when_html_mockup_loads_the_module_from_a_cdn():
    """A static mockup has no build step. Loading the published package from a
    CDN is the legitimate path; the rule must not demand the impossible."""
    content = """
    <script type="module"
      src="https://esm.sh/@theermite/morphic-adapter@2.0.0-beta.2"></script>
    <h4>Adaptation morphique</h4><b>Densite</b><b>Contraste eleve</b><b>Daltonisme</b>
    """
    r = _run("docs/maquette/index.html", content)
    assert r.returncode == 0
    assert r.stderr.strip() == b""


def test_should_pass_when_html_mockup_links_the_published_stylesheet():
    content = """
    <link rel="stylesheet" href="../vendor/@theermite/morphic-adapter/ui.css">
    <h4>Adaptation morphique</h4><b>Densite</b><b>Contraste eleve</b><b>Daltonisme</b>
    """
    r = _run("docs/maquette/index.html", content)
    assert r.returncode == 0


def test_should_pass_when_the_kotlin_android_port_is_used():
    """The Android port is the same module. Yomiraku consumes it via Gradle."""
    content = """
    import com.theermite.morphic.onboarding.MorphicOnboardingScreen
    // Theme, Densite, Contraste eleve, Daltonisme
    """
    r = _run("app/src/main/kotlin/MainActivity.kt", content)
    assert r.returncode == 0


# --- Scope: what the gate must NOT police -------------------------------------


def test_should_pass_on_markdown_documentation():
    """A CDC or a rule file names the axes to describe them. Policing prose
    would fire on every methodology doc and the gate would be turned off."""
    content = "Axes: Theme, Densite, Contraste eleve, Daltonisme, Animation."
    r = _run("docs/CDC.md", content)
    assert r.returncode == 0
    assert r.stderr.strip() == b""


def test_should_pass_on_the_morphic_engine_repo_itself():
    """The module defines these axes. It cannot be asked to import itself."""
    content = "<h4>Adaptation morphique</h4><b>Densite</b><b>Contraste eleve</b><b>Daltonisme</b>"
    r = _run("D:/30-Dev-Projects/morphic-engine/packages/adapter/src/ui/Panel.tsx", content)
    assert r.returncode == 0


def test_should_pass_on_node_modules_and_build_output():
    content = "<h4>Adaptation morphique</h4><b>Densite</b><b>Contraste eleve</b><b>Daltonisme</b>"
    for path in (
        "project/node_modules/x/index.html",
        "project/dist/app.js",
        "project/.next/static/chunk.js",
    ):
        r = _run(path, content)
        assert r.returncode == 0, path


def test_should_pass_on_a_python_or_json_file():
    content = "theme densite contraste eleve daltonisme adaptation morphique"
    for path in ("scripts/tool.py", "data/config.json"):
        r = _run(path, content)
        assert r.returncode == 0, path


# --- Robustness ----------------------------------------------------------------


def test_should_count_distinct_axes_not_repetitions():
    """Five mentions of the same axis is one axis, not five. Otherwise a page
    listing theme options in a loop would be blocked as a full panel."""
    content = "<b>Theme</b><b>Theme</b><b>Theme</b><b>Theme</b><b>Theme</b>"
    r = _run("docs/mockup.html", content)
    assert r.returncode == 0


def test_should_match_axis_labels_regardless_of_accents_and_case():
    """Jay writes French with accents; a mockup may or may not carry them.
    An accent must never be the difference between caught and missed."""
    content = "<h4>ADAPTATION MORPHIQUE</h4><b>Densité</b><b>Contraste élevé</b><b>Daltonisme</b>"
    r = _run("docs/mockup.html", content)
    assert r.returncode == 2


def test_should_handle_missing_file_path_without_crashing():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {}}).encode("utf-8"),
        capture_output=True,
    )
    assert r.returncode == 0


def test_should_handle_empty_stdin_without_crashing():
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=b"", capture_output=True
    )
    assert r.returncode == 0


def test_should_read_edit_payloads_via_new_string():
    """Edit sends new_string, not content. A gate that only reads `content`
    is blind to every Edit — the same miss that killed the 500-line guard."""
    payload = {
        "tool_input": {
            "file_path": "docs/mockup.html",
            "new_string": "<h4>Adaptation morphique</h4><b>Densite</b>"
                          "<b>Contraste eleve</b><b>Daltonisme</b>",
        }
    }
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
    )
    assert r.returncode == 2


@pytest.mark.parametrize(
    "ref",
    [
        "import x from '@theermite/morphic-engine'",
        "import { MorphicButton } from '@theermite/morphic-adapter/ui'",
        "import com.theermite.morphic.MorphicStore",
        "<MorphicProvider>",
        "<MorphicButton />",
    ],
)
def test_should_accept_every_legitimate_module_reference(ref: str):
    content = (
        f"{ref}\n<h4>Adaptation morphique</h4><b>Densite</b>"
        "<b>Contraste eleve</b><b>Daltonisme</b>"
    )
    r = _run("docs/mockup.html", content)
    assert r.returncode == 0, ref


# --- The decoy that quotes the real module -------------------------------------
#
# Found on a real artefact (Shinkofa-Shared Sakusen mockup, 2026-08-30), NOT by
# the tests above: a hand-rolled drawer carrying the comment "reproduction
# fidele de @morphic/adapter MorphicButton" passed the gate. A guard that
# accepts a MENTION as proof of use is defeated by the very thing it hunts --
# a decoy names the real module precisely to look real.
# Family: proof by name instead of proof by call.


@pytest.mark.parametrize(
    "mention",
    [
        "<!-- reproduction fidele de @morphic/adapter MorphicButton -->",
        "// Le vrai module Shinkofa, pas une simulation (MorphicProvider)",
        "/* inspire du MorphicButton officiel */",
        "<h5>MorphicButton</h5>",
    ],
)
def test_should_block_when_the_module_is_only_named_never_called(mention: str):
    content = (
        f"{mention}\n<h4>Adaptation morphique</h4><b>Densite</b>"
        "<b>Contraste eleve</b><b>Daltonisme</b>"
    )
    r = _run("docs/mockup.html", content)
    assert r.returncode == 2, mention


def test_should_block_on_a_lookalike_scope_that_does_not_exist():
    """`@morphic/adapter` is not our package. A near-miss scope must not pass."""
    content = """
    import { MorphicButton } from '@morphic/adapter/ui';
    <h4>Adaptation morphique</h4><b>Densite</b><b>Contraste eleve</b><b>Daltonisme</b>
    """
    r = _run("docs/mockup.html", content)
    assert r.returncode == 2


# --- a generic word is not a specific signal ----------------------------------
#
# Independent review 2026-08-30: an ordinary product page -- a dark/light theme
# toggle, a "hover animations" checkbox, a "compact view" checkbox -- was BLOCKED
# as a morphic decoy. `theme`, `animation` and `compacte` are generic UI
# vocabulary, present on any shop or admin screen.
#
# Family: a signal built from generic words, read as specific. A guard that stops
# legitimate work is a guard that gets switched off -- and it would have taken
# the real detection down with it.
#
# The fix keeps the detection but demands an ANCHOR: at least one word that only
# a morphic panel uses ("adaptation morphique", "confort & adaptation",
# colorblind mode, reading guide, WAI symbols, dyslexia-grade fonts). All six
# real decoys of the audit carry one; the product page carries none.

_PRODUCT_PAGE = """
<div class="produit">
  <button>Theme sombre</button><button>Theme clair</button>
  <label><input type="checkbox"> Animations au survol</label>
  <label><input type="checkbox"> Vue compacte du tableau des tailles</label>
</div>
"""

_ADMIN_TABLE = """
<table><caption>Reglages d'affichage</caption>
  <tr><td>Theme</td><td>Animation</td><td>Densite</td><td>Taille du texte</td></tr>
</table>
"""


def test_should_not_block_an_ordinary_product_page():
    r = _run("shop/product.html", _PRODUCT_PAGE)
    assert r.returncode == 0, r.stderr


def test_should_not_block_a_generic_admin_display_table():
    """Four generic axes, zero morphic anchor: still not a comfort panel."""
    r = _run("admin/settings.html", _ADMIN_TABLE)
    assert r.returncode == 0, r.stderr


def test_should_still_block_the_same_page_once_it_claims_to_be_morphic():
    """Add the anchor and the very same markup becomes a decoy."""
    r = _run("shop/product.html", "<h4>Adaptation morphique</h4>" + _PRODUCT_PAGE)
    assert r.returncode == 2


def test_should_block_on_a_colorblind_anchor_without_the_panel_wording():
    content = "<b>Daltonisme</b><b>Theme sombre</b><b>Vue compacte</b>"
    r = _run("app/settings.html", content)
    assert r.returncode == 2


def test_should_pass_when_the_anchor_stands_alone():
    """One anchor and nothing else is a mention, not a panel."""
    r = _run("docs/page.html", "<p>Daltonisme</p>")
    assert r.returncode == 0
