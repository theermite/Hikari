"""La trace des modeles est ecrite par le code, lue dans le journal de la seance (2026-10-29).

Constat de l'audit du 28 octobre : le relecteur ecrivait « redacteur : Opus » alors qu'il ne pouvait pas le
savoir (le redacteur etait Sonnet 5.5). Le journal porte le modele de chaque message ; personne ne l'y lisait.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import model_trace as mt  # noqa: E402


def _journal(chemin: Path, *modeles):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    lignes = [json.dumps({"message": {"role": "assistant", "model": m}}) for m in modeles]
    lignes.append(json.dumps({"message": {"role": "user", "content": "salut"}}))   # sans modele : ignore
    chemin.write_text("\n".join(lignes), encoding="utf-8")


def test_the_writer_is_the_model_that_spoke_in_the_session(tmp_path):
    _journal(tmp_path / "s.jsonl", "claude-sonnet-5-5", "claude-sonnet-5-5", "<synthetic>")
    assert mt.session_models(tmp_path / "s.jsonl")["redacteur"] == {"claude-sonnet-5-5": 2}


def test_reviewers_are_read_from_the_subagent_journals(tmp_path):
    _journal(tmp_path / "s.jsonl", "claude-sonnet-5-5")
    _journal(tmp_path / "s" / "subagents" / "a.jsonl", "claude-opus-5-5", "claude-opus-5-5")
    _journal(tmp_path / "s" / "subagents" / "b.jsonl", "claude-haiku-5-5")
    assert mt.session_models(tmp_path / "s.jsonl")["sous_agents"] == {"claude-opus-5-5": 2, "claude-haiku-5-5": 1}


def test_a_missing_or_unreadable_journal_gives_empty_models_never_an_error(tmp_path):
    assert mt.session_models(tmp_path / "absent.jsonl") == {"redacteur": {}, "sous_agents": {}}
    (tmp_path / "x.jsonl").write_text("pas du json\n{\n", encoding="utf-8")
    assert mt.session_models(tmp_path / "x.jsonl")["redacteur"] == {}


def test_the_trace_line_is_appended_with_models_head_and_kind(tmp_path):
    _journal(tmp_path / "s.jsonl", "claude-sonnet-5-5")
    _journal(tmp_path / "s" / "subagents" / "a.jsonl", "claude-opus-5-5")
    racine = tmp_path / "depot"
    mt.write_trace(racine, tmp_path / "s.jsonl", head="abc1234", kind="PASS", date="2026-10-29")
    mt.write_trace(racine, tmp_path / "s.jsonl", head="def5678", kind="SKIP", date="2026-10-29")
    lignes = [json.loads(l) for l in (racine / ".claude" / "state" / "modeles-relectures.jsonl").read_text().splitlines()]
    assert [l["head"] for l in lignes] == ["abc1234", "def5678"]
    assert lignes[0]["redacteur"] == "claude-sonnet-5-5" and lignes[0]["sous_agents"] == ["claude-opus-5-5"]
    assert lignes[1]["kind"] == "SKIP"


def test_writing_the_trace_never_raises_when_the_folder_is_unwritable(tmp_path):
    fichier = tmp_path / "pas-un-dossier"
    fichier.write_text("x", encoding="utf-8")
    mt.write_trace(fichier, tmp_path / "absent.jsonl", head="a", kind="PASS", date="2026-10-29")   # ne leve rien


# --- le garde de relecture ecrit la trace quand il laisse passer -----------------------------

def _garde():
    import importlib.util
    chemin = Path(__file__).resolve().parents[1] / "guards" / "pre-deploy-review-check.py"
    spec = importlib.util.spec_from_file_location("garde_relecture_trace", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_clearance_kind_is_read_from_the_most_recent_marker():
    garde = _garde()
    pass_ = "[REVIEW] par x le 2026-10-29 sur abc1234 — verdict: PASS, ok"
    assert mt.kind_of_clearance([pass_]) == "PASS"
    assert mt.kind_of_clearance(["[REVIEW-SKIP] motif: no-code-change"]) == "SKIP"
    assert mt.kind_of_clearance(["rien"]) == "?"


def test_record_clearance_writes_one_line_in_the_repo_state(tmp_path):
    _journal(tmp_path / "s.jsonl", "claude-sonnet-5-5")
    racine = tmp_path / "depot"
    racine.mkdir()
    mt.record_clearance(["[REVIEW] par x le 2026-10-29 sur abc1234 — verdict: PASS, ok"], tmp_path / "s.jsonl",
                        "abc1234def", lambda: racine)
    ligne = json.loads((racine / ".claude" / "state" / "modeles-relectures.jsonl").read_text().splitlines()[0])
    assert ligne["head"] == "abc1234" and ligne["kind"] == "PASS" and ligne["redacteur"] == "claude-sonnet-5-5"


def test_record_clearance_never_raises_when_the_root_is_unknown(tmp_path):
    def sans_racine():
        raise RuntimeError("pas de depot")

    mt.record_clearance(["x"], tmp_path / "s.jsonl", "abc", sans_racine)    # ne leve rien


def test_the_guard_calls_the_trace_when_it_lets_a_command_through():
    source = (Path(__file__).resolve().parents[1] / "guards" / "pre-deploy-review-check.py").read_text(encoding="utf-8")
    assert "record_clearance(texts, transcript" in source


# --- remarques de la relecture du lot A (2026-10-29) ---------------------------------------------

def test_a_message_that_is_not_an_object_is_ignored_not_raised(tmp_path):
    (tmp_path / "s.jsonl").write_text(
        json.dumps({"type": "x", "message": "texte"}) + "\n"
        + json.dumps({"message": {"role": "assistant", "model": "claude-sonnet-5-5"}}) + "\n", encoding="utf-8")
    assert mt.session_models(tmp_path / "s.jsonl")["redacteur"] == {"claude-sonnet-5-5": 1}
    mt.record_clearance(["x"], tmp_path / "s.jsonl", "abc", lambda: tmp_path / "depot")     # ne leve rien


def test_a_quoted_skip_marker_is_not_read_as_a_clearance():
    citation = "il a ecrit [REVIEW-SKIP] motif: rollback sur abc1234 dans son texte"
    assert mt.kind_of_clearance([citation, "[REVIEW] par x le 2026-10-29 sur abc1234 — verdict: PASS, ok"]) == "PASS"
    assert mt.kind_of_clearance(["[REVIEW-SKIP] motif: rollback sur abc1234"]) == "SKIP"
