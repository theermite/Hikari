"""Tests for lifecycle/agent-invocation-journal.py — le nerf sensitif.

Plan d'action point 1, brique 1.1 (`docs/Plan-Action-Methodologie-2026-09.md`).

Pourquoi ce hook existe : l'audit du 2026-09-03 a mesuré « 2 agents sur 56 cités
dans 112 rapports » et a dû écrire que ce chiffre est un PLANCHER, pas une
vérité — il vient d'une recherche de texte dans les comptes rendus, parce
qu'aucun journal d'invocation n'existe. On ne peut pas piloter une convocation
qu'on ne mesure pas. Ce hook produit la mesure manquante.

Contrat : il OBSERVE, il ne bloque jamais. Un journal qui peut faire échouer une
délégation transformerait l'instrument de mesure en panne.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "agent-invocation-journal.py"
_spec = importlib.util.spec_from_file_location("agent_invocation_journal", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _data(subagent_type="Security Master", description="audit auth", ok=True, session="s-1"):
    return {
        "session_id": session,
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": subagent_type,
            "description": description,
            "prompt": "audite le chemin d'authentification",
        },
        "tool_response": {"content": "rapport" if ok else "", "is_error": not ok},
    }


def _subagent_event(event="SubagentStop", **fields):
    """Événement du cycle de vie des sous-agents.

    Mesuré le 2026-09-05 : `PostToolUse` avec le matcher `Agent|Task` n'a RIEN
    écrit sur deux délégations réelles, dans deux sessions différentes dont une
    démarrée après l'ajout du hook. Le harnais expose des événements dédiés —
    `SubagentStart` / `SubagentStop` — et c'est eux qui portent la délégation.
    """
    base = {"hook_event_name": event, "session_id": "s-9"}
    base.update(fields)
    return base


# --- l'entrée du journal -----------------------------------------------------


def test_records_the_agent_that_was_called():
    entry = mod.build_entry(_data())
    assert entry is not None
    assert entry["agent"] == "Security Master"
    assert entry["description"] == "audit auth"
    assert entry["session_id"] == "s-1"


def test_entry_carries_an_iso_timestamp():
    entry = mod.build_entry(_data())
    # AAAA-MM-JJT... — falsifiable, pas une coche
    assert entry["at"][:4].isdigit()
    assert entry["at"][4] == "-"


def test_entry_records_failure_so_a_broken_agent_is_visible():
    entry = mod.build_entry(_data(ok=False))
    assert entry["ok"] is False


def test_entry_is_json_serialisable():
    # Le journal est relu par une machine ; une entrée non sérialisable
    # casserait la mesure en silence.
    json.dumps(mod.build_entry(_data()))


# --- ce que le hook ignore ---------------------------------------------------


def test_ignores_a_non_agent_tool():
    data = _data()
    data["tool_name"] = "Bash"
    assert mod.build_entry(data) is None


def test_unnamed_agent_is_recorded_as_unknown_never_dropped():
    # Une délégation sans type déclaré reste une délégation : la compter
    # « inconnu » dit la vérité, la jeter fabrique un faux zéro.
    entry = mod.build_entry(_data(subagent_type=""))
    assert entry is not None
    assert entry["agent"] == "inconnu"


# --- l'événement de sous-agent (le vrai porteur, mesuré le 2026-09-05) -------


def test_records_a_subagent_stop_event():
    entry = mod.build_entry(_subagent_event(subagent_type="Explore"))
    assert entry is not None
    assert entry["agent"] == "Explore"
    assert entry["event"] == "SubagentStop"


def test_records_a_subagent_start_event():
    entry = mod.build_entry(_subagent_event(event="SubagentStart", subagent_type="Explore"))
    assert entry is not None
    assert entry["agent"] == "Explore"


def test_finds_the_agent_name_under_any_known_key():
    # Le nom du champ n'est pas documenté pour ces événements. Chercher sous
    # plusieurs clés coûte trois lignes ; se tromper de clé mesure zéro et se
    # lit comme « personne n'a délégué » — le défaut qu'on vient de payer.
    for key in ("subagent_type", "agent_type", "agent_name", "agent", "name"):
        entry = mod.build_entry(_subagent_event(**{key: "Frontend Master"}))
        assert entry is not None, key
        assert entry["agent"] == "Frontend Master", key


def test_finds_the_agent_name_nested_in_tool_input():
    entry = mod.build_entry(_subagent_event(tool_input={"subagent_type": "Plan"}))
    assert entry["agent"] == "Plan"


def test_unknown_shape_is_still_recorded_with_its_keys_for_diagnosis():
    # Une délégation dont on ne sait pas lire le nom reste une délégation.
    # On enregistre les CLÉS (jamais les valeurs — elles peuvent contenir des
    # données) pour apprendre la forme réelle au premier événement.
    entry = mod.build_entry(_subagent_event(mystere="valeur-sensible"))
    assert entry is not None
    assert entry["agent"] == "inconnu"
    assert "mystere" in entry["unknown_keys"]
    assert "valeur-sensible" not in json.dumps(entry)


def test_ignores_an_unrelated_lifecycle_event():
    assert mod.build_entry(_subagent_event(event="SessionStart")) is None


# --- le contrat de non-blocage ----------------------------------------------


def test_hook_never_blocks_even_on_garbage_input():
    # Toute entrée malformée doit produire None, jamais une exception :
    # un instrument de mesure ne casse pas ce qu'il mesure.
    for junk in ({}, {"tool_name": "Agent"}, {"tool_name": "Agent", "tool_input": None}):
        assert mod.build_entry(junk) is None or isinstance(mod.build_entry(junk), dict)


# --- la lecture du journal (c'est elle qui produit le chiffre) ---------------


def test_reads_back_the_rate_over_sessions(tmp_path):
    journal = tmp_path / "agent-invocations.jsonl"
    lines = [
        {"at": "2026-09-05T10:00:00", "agent": "Security Master", "session_id": "s-1", "ok": True},
        {"at": "2026-09-05T10:05:00", "agent": "Frontend Master", "session_id": "s-1", "ok": True},
        {"at": "2026-09-05T11:00:00", "agent": "Security Master", "session_id": "s-2", "ok": False},
    ]
    journal.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")

    stats = mod.read_stats(journal)
    assert stats["invocations"] == 3
    assert stats["sessions"] == 2
    assert stats["agents"]["Security Master"] == 2
    assert stats["failures"] == 1


def test_stats_on_a_missing_journal_are_zero_not_an_error(tmp_path):
    stats = mod.read_stats(tmp_path / "nope.jsonl")
    assert stats["invocations"] == 0
    assert stats["sessions"] == 0


def test_corrupt_line_does_not_lose_the_whole_journal(tmp_path):
    journal = tmp_path / "agent-invocations.jsonl"
    journal.write_text(
        json.dumps({"at": "x", "agent": "A", "session_id": "s", "ok": True})
        + "\nligne cassée non-json\n"
        + json.dumps({"at": "y", "agent": "B", "session_id": "s", "ok": True})
        + "\n",
        encoding="utf-8",
    )
    stats = mod.read_stats(journal)
    assert stats["invocations"] == 2
    assert stats["corrupt_lines"] == 1
