"""Tests de `quality/matter-expert-suggest.py` — la convocation par la matière.

Plan d'action point 1 (`docs/Routage-Experts.md`, famille MATIÈRE).

Ce que ça ferme : le texte des commandes ne peut pas prévoir quel fichier tu vas
toucher. Aucune commande ne dira jamais « si tu ouvres un fichier Elixir, convoque
l'expert Elixir » au bon moment — seul le fichier le sait, à l'instant où on l'écrit.

CONTRAT — il SUGGÈRE, il ne bloque JAMAIS. Mesure du 2026-08-30 : un garde-fou fait de
mots génériques bloquait une fiche produit banale, et « un garde-fou qui gêne le travail
légitime finit débranché, et emporte la détection réelle avec lui ». Une suggestion par
expert et par session, pas une par fichier.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "matter-expert-suggest.py"
_spec = importlib.util.spec_from_file_location("matter_expert_suggest", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# --- la matière désigne son expert -------------------------------------------


def test_elixir_file_designates_the_elixir_expert():
    assert mod.expert_pour("lib/mon_app/accounts.ex") == "Elixir / Phoenix"
    assert mod.expert_pour("mix.exs") == "Elixir / Phoenix"


def test_rust_file_designates_the_rust_expert():
    assert mod.expert_pour("native/nif/src/lib.rs") == "Rust"
    assert mod.expert_pour("Cargo.toml") == "Rust"


def test_interface_component_designates_the_frontend_expert():
    assert mod.expert_pour("src/components/UserCard.tsx") == "facade"


def test_dependency_manifest_designates_the_dependency_expert():
    for chemin in ("package.json", "pnpm-lock.yaml", "uv.lock", "pyproject.toml"):
        assert mod.expert_pour(chemin) == "dependances", chemin


def test_ci_workflow_designates_the_ci_expert():
    assert mod.expert_pour(".github/workflows/tests.yml") == "integration continue"


def test_payment_path_designates_the_payment_expert():
    # Chemin Critical au sens de Quality.md : la matière prime sur l'extension.
    assert mod.expert_pour("src/api/stripe/webhook.ts") == "paiement (chemin Critical)"


def test_infrastructure_files_designate_the_infra_expert():
    for chemin in ("Dockerfile", "docker-compose.yml", "nginx/site.conf"):
        assert mod.expert_pour(chemin) == "infrastructure", chemin


def test_an_ordinary_file_designates_nobody():
    # Ne rien dire est la bonne réponse la plupart du temps.
    for chemin in ("README.md", "docs/note.md", "scripts/petit.sh", ""):
        assert mod.expert_pour(chemin) is None, chemin


def test_a_test_file_designates_nobody():
    # Un test Elixir n'appelle pas l'architecte Elixir : c'est du test, pas une
    # décision d'architecture.
    assert mod.expert_pour("test/mon_app/accounts_test.exs") is None


# --- il suggère une fois, pas à chaque fichier -------------------------------


def test_suggests_once_then_stays_quiet(tmp_path):
    etat = tmp_path / "suggested.json"
    assert mod.doit_suggerer("Elixir / Phoenix", etat) is True
    assert mod.doit_suggerer("Elixir / Phoenix", etat) is False
    # un AUTRE expert reste annoncable
    assert mod.doit_suggerer("Rust", etat) is True


def test_a_corrupt_state_file_does_not_silence_the_hook(tmp_path):
    etat = tmp_path / "suggested.json"
    etat.write_text("ceci n est pas du json", encoding="utf-8")
    assert mod.doit_suggerer("Rust", etat) is True


# --- le contrat de non-blocage ----------------------------------------------


def test_the_decision_is_a_warning_never_a_block():
    decision = mod.build_decision(
        {"tool_name": "Edit", "tool_input": {"file_path": "lib/app.ex"}},
        deja_suggere=lambda _: True,
    )
    assert decision is not None
    texte = str(decision)
    assert "Elixir" in texte
    # aucune forme de refus : ni blocage, ni interruption
    assert '"permissionDecision": "deny"' not in texte
    assert "continue" not in texte or "false" not in texte


def test_no_decision_on_an_ordinary_file():
    decision = mod.build_decision(
        {"tool_name": "Write", "tool_input": {"file_path": "docs/note.md"}},
        deja_suggere=lambda _: True,
    )
    assert decision is None


def test_no_decision_when_already_suggested():
    decision = mod.build_decision(
        {"tool_name": "Edit", "tool_input": {"file_path": "lib/app.ex"}},
        deja_suggere=lambda _: False,
    )
    assert decision is None


def test_garbage_input_never_raises():
    for junk in ({}, {"tool_name": "Edit"}, {"tool_name": "Edit", "tool_input": None}):
        assert mod.build_decision(junk, deja_suggere=lambda _: True) is None
