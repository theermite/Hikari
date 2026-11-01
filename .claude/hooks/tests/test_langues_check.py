"""quality/langues-check.py — Stop hook: a claimed language coverage must match the searches made.

Jay 2026-05-26 (feedback « Research quality enforcement ») : les agents « prétendent avoir cherché
en 7 langues sans le faire ». Décision de Jay 2026-10-31 : règle ciblée (recherche de fond) avec un
rapport de couverture. Le marqueur `[LANGUES] EN=ok FR=ok ZH=rien ...` est tenu par ce garde-fou :
une langue annoncée `ok` exige au moins une requête réellement lancée dans cette écriture.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))
import langues_couverture as lc  # noqa: E402

HOOK = HOOKS / "quality" / "langues-check.py"

TOUT_OK = "[LANGUES] EN=ok FR=ok ZH=ok JA=ok KO=ok DE=ok RU=ok"


# --- le marqueur ---------------------------------------------------------------


def test_parse_reads_all_seven_languages():
    m = lc.parse_marker("Bilan.\n[LANGUES] EN=ok FR=ok ZH=ok JA=rien KO=rien DE=ok RU=ok")
    assert m == {"EN": "ok", "FR": "ok", "ZH": "ok", "JA": "rien", "KO": "rien", "DE": "ok", "RU": "ok"}


def test_parse_tolerates_bold_backticks_and_colons():
    m = lc.parse_marker("**[LANGUES]** EN: ok · FR: ok · ZH: rien · JA: rien · KO: rien · DE: ok · RU: ok")
    assert m is not None and m["ZH"] == "rien" and m["EN"] == "ok"


def test_parse_returns_none_without_marker():
    assert lc.parse_marker("Aucune recherche de fond ici.") is None


def test_missing_language_in_marker_is_a_defect():
    marqueur = lc.parse_marker("[LANGUES] EN=ok FR=ok ZH=ok")
    assert any("JA" in p for p in lc.problemes(marqueur, queries=["pg async io", "pg 并行 性能"]))


def test_unknown_value_is_a_defect():
    marqueur = lc.parse_marker("[LANGUES] EN=peut-etre FR=ok ZH=ok JA=ok KO=ok DE=ok RU=ok")
    assert any("EN" in p for p in lc.problemes(marqueur, queries=[]))


# --- la langue d'une requête ---------------------------------------------------


def test_script_detection():
    assert "ZH" in lc.langues_de("PostgreSQL 18 异步 I/O 性能 实测")
    assert "JA" in lc.langues_de("PostgreSQL 18 の async I/O 性能を確認してみた")
    assert "KO" in lc.langues_de("PostgreSQL 18 비동기 I/O 성능")
    assert "RU" in lc.langues_de("PostgreSQL 18 асинхронный ввод-вывод производительность")
    assert "DE" in lc.langues_de("PostgreSQL 18 Leistung der asynchronen Ein- und Ausgabe für Anfänger")
    assert "FR" in lc.langues_de("PostgreSQL 18 performances des entrées sorties asynchrones avec exemples")
    assert "EN" in lc.langues_de("PostgreSQL 18 async io performance benchmark")


def test_japanese_is_not_counted_as_chinese():
    assert "ZH" not in lc.langues_de("非同期 I/O のベンチマーク")


# --- la couverture annoncée contre les requêtes faites --------------------------


def test_claim_without_matching_query_is_refused():
    marqueur = lc.parse_marker(TOUT_OK)
    faits = lc.problemes(marqueur, queries=["pg async io performance benchmark"])
    assert any("ZH" in p for p in faits) and any("RU" in p for p in faits)


def test_claim_with_matching_queries_passes():
    marqueur = lc.parse_marker(TOUT_OK)
    queries = [
        "pg async io performance benchmark",
        "PostgreSQL 18 performances des entrées sorties asynchrones avec exemples",
        "PostgreSQL 18 异步 I/O 性能 实测",
        "PostgreSQL 18 の async I/O 性能を確認してみた",
        "PostgreSQL 18 비동기 I/O 성능",
        "PostgreSQL 18 Leistung der asynchronen Ein- und Ausgabe für Anfänger",
        "PostgreSQL 18 асинхронный ввод-вывод производительность",
    ]
    assert lc.problemes(marqueur, queries) == []


def test_a_language_declared_empty_needs_no_query():
    marqueur = lc.parse_marker("[LANGUES] EN=ok FR=rien ZH=rien JA=rien KO=rien DE=rien RU=rien")
    assert lc.problemes(marqueur, queries=["pg async io performance benchmark"]) == []


def test_delegated_searches_are_not_judged():
    marqueur = lc.parse_marker(TOUT_OK)
    assert lc.problemes(marqueur, queries=[], delegue=True) == []


# --- le crochet de fin de tour ---------------------------------------------------


def _journal(tmp_path: Path, queries: list[str], outil="WebSearch") -> Path:
    lignes = []
    for q in queries:
        lignes.append(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": outil, "input": {"query": q, "mode": "standard"}}]}}))
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return p


def _run(payload) -> subprocess.CompletedProcess:
    raw = json.dumps(payload).encode("utf-8")
    return subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, timeout=10)


def test_hook_blocks_a_claim_the_searches_do_not_back(tmp_path):
    p = _journal(tmp_path, ["pg async io performance benchmark"])
    r = _run({"last_assistant_message": TOUT_OK, "transcript_path": str(p)})
    assert r.returncode == 2 and b"ZH" in r.stderr + r.stdout


def test_hook_passes_a_backed_claim(tmp_path):
    p = _journal(tmp_path, ["pg async io performance benchmark", "PostgreSQL 18 异步 I/O 性能 实测"])
    r = _run({"last_assistant_message": "[LANGUES] EN=ok FR=rien ZH=ok JA=rien KO=rien DE=rien RU=rien",
              "transcript_path": str(p)})
    assert r.returncode == 0


def test_hook_counts_the_server_search_tool_too(tmp_path):
    p = _journal(tmp_path, ["PostgreSQL 18 异步 I/O 性能 实测"], outil="mcp__shinkofa-web__web_search")
    r = _run({"last_assistant_message": "[LANGUES] EN=rien FR=rien ZH=ok JA=rien KO=rien DE=rien RU=rien",
              "transcript_path": str(p)})
    assert r.returncode == 0


def test_hook_ignores_a_reply_without_marker(tmp_path):
    p = _journal(tmp_path, [])
    assert _run({"last_assistant_message": "Rien à signaler.", "transcript_path": str(p)}).returncode == 0


def test_hook_never_loops(tmp_path):
    p = _journal(tmp_path, [])
    r = _run({"last_assistant_message": TOUT_OK, "transcript_path": str(p), "stop_hook_active": True})
    assert r.returncode == 0


def test_hook_fails_open_on_garbage():
    r = subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True, timeout=10)
    assert r.returncode == 0


def _ligne(role: str, bloc: dict) -> str:
    return json.dumps({"type": role, "message": {"role": role, "content": [bloc]}})


def test_hook_does_not_judge_when_a_subagent_ran_since_jay_spoke(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join([
        _ligne("user", {"type": "text", "text": "fais une recherche de fond"}),
        _ligne("assistant", {"type": "tool_use", "name": "Agent", "input": {"prompt": "cherche"}}),
    ]) + "\n", encoding="utf-8")
    r = _run({"last_assistant_message": TOUT_OK, "transcript_path": str(p)})
    assert r.returncode == 0


def test_hook_counts_searches_made_before_jays_last_message(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join([
        _ligne("assistant", {"type": "tool_use", "name": "WebSearch", "input": {"query": "PostgreSQL 18 异步 I/O 性能 实测"}}),
        _ligne("user", {"type": "text", "text": "et alors ?"}),
    ]) + "\n", encoding="utf-8")
    r = _run({"last_assistant_message": "[LANGUES] EN=rien FR=rien ZH=ok JA=rien KO=rien DE=rien RU=rien",
              "transcript_path": str(p)})
    assert r.returncode == 0



# --- le marqueur cité n'est pas un marqueur émis (relecture indépendante, 2026-10-31) --------------

FENCE = "`" * 3


def test_a_quoted_marker_is_not_read_as_emitted():
    for citation in (
        "Le marqueur se pose ainsi : `[LANGUES] EN=ok FR=ok ZH=rien JA=rien KO=rien DE=ok RU=ok`",
        "- `[LANGUES] EN=ok FR=ok`",
        "Le marqueur [LANGUES] dit la couverture.",
        FENCE + "\n[LANGUES] EN=ok FR=ok ZH=ok JA=ok KO=ok DE=ok RU=ok\n" + FENCE,
    ):
        assert lc.parse_marker(citation) is None, citation


def test_an_emitted_marker_on_its_own_line_is_read():
    assert lc.parse_marker("Bilan.\n[LANGUES] EN=ok FR=rien ZH=rien JA=rien KO=rien DE=rien RU=rien")["EN"] == "ok"
    assert lc.parse_marker("**[LANGUES]** EN=ok")["EN"] == "ok"


def test_hook_lets_an_explanation_of_the_marker_through(tmp_path):
    p = _journal(tmp_path, [])
    texte = "Voici la règle : `[LANGUES] EN=ok FR=ok ZH=ok JA=ok KO=ok DE=ok RU=ok` se pose en fin de recherche."
    assert _run({"last_assistant_message": texte, "transcript_path": str(p)}).returncode == 0


# --- les langues latines sans accent ni mot-outil : échec ouvert -------------------------------------


def test_undecidable_latin_queries_cover_en_fr_de():
    for requete in ("OBS images perdues NVENC", "PySide6 QThread Speicherleck", "OBS verworfene Frames NVENC"):
        assert {"EN", "FR", "DE"} <= lc.langues_de(requete), requete


def test_french_with_function_words_is_french():
    assert lc.langues_de("PostgreSQL 18 performance de io_uring en production") == {"FR"}


def test_an_honest_ok_on_an_undecidable_latin_query_passes():
    marqueur = lc.parse_marker("[LANGUES] EN=rien FR=rien ZH=rien JA=rien KO=rien DE=ok RU=rien")
    assert lc.problemes(marqueur, queries=["PySide6 QThread Speicherleck"]) == []


# --- les sous-agents : leurs recherches sont dans leur propre journal --------------------------------


def _journal_agent(tmp_path: Path, queries: list[str]) -> Path:
    p = tmp_path / "agent.jsonl"
    p.write_text("\n".join(
        _ligne("assistant", {"type": "tool_use", "name": "WebSearch", "input": {"query": q}}) for q in queries
    ) + "\n", encoding="utf-8")
    return p


def test_subagent_stop_reads_the_agent_transcript_not_the_main_one(tmp_path):
    principal = _journal(tmp_path, [])
    agent = _journal_agent(tmp_path, ["PostgreSQL 18 异步 I/O 性能 实测"])
    marque = "[LANGUES] EN=rien FR=rien ZH=ok JA=rien KO=rien DE=rien RU=rien"
    r = _run({"hook_event_name": "SubagentStop", "last_assistant_message": marque,
              "transcript_path": str(principal), "agent_transcript_path": str(agent)})
    assert r.returncode == 0


def test_subagent_stop_refuses_a_claim_its_own_searches_do_not_back(tmp_path):
    principal = _journal(tmp_path, ["PostgreSQL 18 异步 I/O 性能 实测"])
    agent = _journal_agent(tmp_path, ["pg async io performance benchmark"])
    marque = "[LANGUES] EN=ok FR=rien ZH=ok JA=rien KO=rien DE=rien RU=rien"
    r = _run({"hook_event_name": "SubagentStop", "last_assistant_message": marque,
              "transcript_path": str(principal), "agent_transcript_path": str(agent)})
    assert r.returncode == 2 and b"ZH" in r.stderr + r.stdout


# --- seconde relecture (2026-10-31) : dernier marqueur, clôtures, journal absent ------------------------

TILDES = "~" * 3


def test_the_last_emitted_marker_wins():
    texte = ("[LANGUES] EN=ok FR=ok ZH=ok JA=ok KO=ok DE=ok RU=ok\n\nEn réalité :\n"
             "[LANGUES] EN=ok FR=rien ZH=rien JA=rien KO=rien DE=rien RU=rien")
    assert lc.parse_marker(texte)["ZH"] == "rien"


def test_tilde_and_unclosed_fences_hide_a_quoted_marker():
    assert lc.parse_marker(TILDES + "\n[LANGUES] EN=ok\n" + TILDES) is None
    assert lc.parse_marker("Voici l'exemple :\n" + FENCE + "\n[LANGUES] EN=ok FR=ok") is None


def test_an_indented_code_block_is_not_an_emitted_marker():
    assert lc.parse_marker("Exemple :\n\n    [LANGUES] EN=ok FR=ok ZH=ok JA=ok KO=ok DE=ok RU=ok") is None


def test_hook_passes_when_the_journal_is_missing():
    r = _run({"hook_event_name": "SubagentStop", "last_assistant_message": TOUT_OK,
              "agent_transcript_path": "/nope/x.jsonl"})
    assert r.returncode == 0
    assert _run({"last_assistant_message": TOUT_OK}).returncode == 0
