"""hook-blocks-stats.py — SessionEnd observability: count hook blocks/warns per signature.

Behavior under test (A2 — guardrail-fatigue instrumentation):
- Scan the session transcript for hook BLOCKED:/WARNING: lines.
- Count ONLY real hook output (tool results / non-assistant entries), so that
  Takumi's own citations of "BLOCKED:" in assistant text are NOT counted.
- Ignore template/RECOVERY lines (those containing <...> placeholders).
- Group by a normalized signature (the short reason after BLOCKED:/WARNING:).
- Append one cumulative entry per session to .claude/state/hook-blocks.jsonl.
- NEVER block: this is observability, it must always exit 0.

Tests isolate state by running the hook with cwd set to a temp repo (with a
.git marker) so find_repo_root() resolves there — no pollution of the real
.claude/state/.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "hook-blocks-stats.py"


# --- Helpers ----------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """A temp dir that looks like a git repo so find_repo_root() stops here."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _tool_result(text: str) -> dict:
    """A transcript entry shaped like a tool result (real hook output lands here)."""
    return {"message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}}


def _assistant(text: str) -> dict:
    """A transcript entry shaped like assistant text (Takumi citing a message)."""
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _make_transcript(tmp_path: Path, *entries: dict) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return transcript


def _run(repo: Path, transcript: Path | None, session_id: str) -> subprocess.CompletedProcess:
    payload: dict = {"session_id": session_id}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(repo),
    )


def _journal(repo: Path) -> list[dict]:
    p = repo / ".claude" / "state" / "hook-blocks.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


VEILLE_BLOCK = (
    "BLOCKED: Veille / SKB evidence missing before writing source code.\n"
    "Target: src/x.py\n"
    "RECOVERY: Output one of the strict markers BEFORE retrying:\n"
    "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>"
)


# --- Tests ------------------------------------------------------------------


def test_counts_block_from_tool_result(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    journal = _journal(repo)
    assert len(journal) == 1
    counts = journal[0]["blocks"]
    # one signature derived from the first BLOCKED line, counted once
    assert sum(counts.values()) == 1
    assert any("veille" in sig.lower() for sig in counts)


def test_ignores_assistant_citation(tmp_path):
    repo = _make_repo(tmp_path)
    # Same BLOCKED text, but in ASSISTANT output (Takumi quoting it) -> not counted.
    tr = _make_transcript(tmp_path, _assistant(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    journal = _journal(repo)
    # entry may exist but with zero blocks, or no entry at all
    total = sum(sum(e["blocks"].values()) for e in journal)
    assert total == 0


def test_counts_warning_separately(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(
        tmp_path,
        _tool_result("WARNING: source code write with no sibling test. ACTION: add a test."),
    )
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    journal = _journal(repo)
    assert len(journal) == 1
    assert sum(journal[0]["blocks"].values()) == 0
    assert sum(journal[0]["warns"].values()) == 1


def test_same_signature_accumulates(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(VEILLE_BLOCK), _tool_result(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    counts = _journal(repo)[0]["blocks"]
    assert sum(counts.values()) == 2
    # same reason -> single signature key
    assert len(counts) == 1


def test_ignores_template_recovery_lines(tmp_path):
    repo = _make_repo(tmp_path)
    # A message whose ONLY BLOCKED-ish lines are template placeholders must not count.
    template_only = (
        "RECOVERY: Output one of the strict markers:\n"
        "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>"
    )
    tr = _make_transcript(tmp_path, _tool_result(template_only))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    total = sum(sum(e["blocks"].values()) for e in _journal(repo))
    assert total == 0


def test_never_blocks_without_transcript(tmp_path):
    repo = _make_repo(tmp_path)
    res = _run(repo, None, f"s-{uuid.uuid4()}")
    assert res.returncode == 0


def test_summary_on_stderr(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    # a human-readable one-liner is surfaced for the session-end summary
    assert b"veille" in res.stderr.lower() or b"block" in res.stderr.lower()


# --- Overcome (friction) detection wired into the journal + summary ----------


def _tool_use(tool: str, target: str, tid: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": tool, "input": {"file_path": target}}]}}


def _tool_result_id(tid: str, is_error: bool, text: str) -> dict:
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


def test_overcome_block_recorded_and_surfaced(tmp_path):
    repo = _make_repo(tmp_path)
    # Block on src/x.py, then a retry on the SAME target succeeds -> overcome.
    tr = _make_transcript(
        tmp_path,
        _tool_use("Edit", "src/x.py", "t1"),
        _tool_result_id("t1", True, VEILLE_BLOCK),
        _tool_use("Edit", "src/x.py", "t2"),
        _tool_result_id("t2", False, "ok"),
    )
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    entry = _journal(repo)[0]
    assert "overcome" in entry
    assert sum(entry["overcome"].values()) == 1
    assert b"hook-friction" in res.stderr


# --- Defauts mesures le 2026-09-07 -----------------------------------------
#
# Jay a demande ce que valait ce compteur avant de generaliser quoi que ce soit.
# Mesure sur une session reelle : 92 marqueurs presents, 30 comptes. Il en ratait
# les deux tiers, et surtout les BLOCAGES — ceux qui comptent le plus.
#
# Les tests d'origine passaient tous : ils nourrissaient le compteur avec la
# forme IDEALE du message, jamais avec celle que le harnais produit vraiment.
# Un test ecrit a partir de sa propre attente ne peut pas trouver ce defaut-la.

PREFIXE = (
    'PreToolUse:Bash hook error: [bash "$(git rev-parse --show-toplevel)'
    '/.claude/hooks/_run.sh" guards/bash-guard.py]: BLOCKED: Broad git add detected.'
)
AVEC_GABARIT = (
    "BLOCKED: destructive delete on a work directory. "
    "RECOVERY: Use 'mv <target> <target>-backup' instead."
)


def test_a_prefixed_block_is_counted(tmp_path):
    """Le harnais prefixe le message ; exiger un debut de ligne en perd les deux tiers."""
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(PREFIXE))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    entrees = _journal(repo)
    assert entrees, "un blocage prefixe n'etait pas compte du tout"
    assert sum(entrees[0]["blocks"].values()) == 1


def test_a_real_block_is_kept_even_with_a_placeholder_in_its_recovery(tmp_path):
    """Ecarter les gabarits ne doit pas ecarter les vrais blocages.

    Nos messages d'aide portent presque tous un exemple entre chevrons. Le tri
    d'origine jetait 12 occurrences reelles sur la seule session mesuree.
    """
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(AVEC_GABARIT))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    entrees = _journal(repo)
    assert entrees, "un vrai blocage etait jete a cause de son texte d'aide"
    assert sum(entrees[0]["blocks"].values()) == 1


def test_reading_source_code_that_mentions_a_marker_is_not_an_event(tmp_path):
    """Defaut que MON PROPRE correctif a cree, trouve avant de le livrer.

    En elargissant naivement a « le marqueur n'importe ou dans la ligne », le
    compteur s'est mis a compter le code source qu'on venait de LIRE : 69
    blocages annonces au lieu de 26 sur la meme session. Un compteur qui gonfle
    ment autant qu'un compteur muet — et il ment dans le sens rassurant.
    """
    repo = _make_repo(tmp_path)
    code_lu = (
        '    MARKER_RE = re.compile(r"(BLOCKED|WARNING):")\n'
        '    # une ligne de doc qui parle de "BLOCKED:" sans en etre un\n'
    )
    tr = _make_transcript(tmp_path, _tool_result(code_lu))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    entrees = _journal(repo)
    assert entrees[0]["blocks"] == {}, "lire du code n'est pas subir un blocage"


def test_code_that_talks_about_a_block_is_not_an_event(tmp_path):
    """Lire un fichier qui PARLE de blocage n'est pas subir un blocage.

    Les quatre formes ci-dessous viennent d'une mesure reelle, pas d'une
    imagination : un commentaire, une chaine citee, une affectation, et une
    ligne de diff. Les deux premieres, ma premiere tentative les ecartait ; les
    deux dernieres passaient encore — 26 % de gonflement restant, trouve par
    relecture independante. Une liste de ce qu'il faut ECARTER est ouverte, donc
    toujours depassee par la forme suivante.
    """
    repo = _make_repo(tmp_path)
    code = (
        "#   PreToolUse:Bash hook error: [x]: BLOCKED: exemple\n"
        "    'PreToolUse:Bash hook error: [x]: BLOCKED: exemple'\n"
        '    msg = "PreToolUse:Bash hook error: [x]: BLOCKED: Broad git add detected."\n'
        '+           "PreToolUse:[x]: BLOCKED: destructive sql detected."\n'
    )
    tr = _make_transcript(tmp_path, _tool_result(code))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    assert _journal(repo)[0]["blocks"] == {}, "du code qui cite un blocage n'est pas un blocage"


def test_the_four_real_shapes_of_an_event_are_counted(tmp_path):
    """La liste des formes acceptees est FERMEE — et elle doit toutes les couvrir.

    Un critere positif trop etroit perd de vrais blocages : la premiere version
    proposee en relecture oubliait le crochet du lanceur, et perdait le
    depassement de lisibilite que j'avais reellement subi.
    """
    repo = _make_repo(tmp_path)
    formes = (
        "PreToolUse:Bash hook error: [x]: BLOCKED: premier motif\n"
        "PostToolUse:Edit hook blocking error: [x]: BLOCKED: deuxieme motif\n"
        "BLOCKED: troisieme motif\n"
        '[bash ".../_run.sh" quality/function-complexity-check.py]: BLOCKED: quatrieme motif\n'
    )
    tr = _make_transcript(tmp_path, _tool_result(formes))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    assert sum(_journal(repo)[0]["blocks"].values()) == 4


def test_one_entry_counts_a_reason_once(tmp_path):
    """Un resultat d'outil porte le meme texte a deux endroits — un evenement, pas deux.

    Mesure du 2026-09-07 : chaque blocage etait compte double, sur les trois
    entrees concernees. Un compteur exact a 2x pres est un compteur qui ment.
    """
    repo = _make_repo(tmp_path)
    msg = "PreToolUse:Bash hook error: [.../_run.sh guards/x.py]: BLOCKED: Broad git add detected."
    entree = {"message": {"role": "user", "content": [{"type": "tool_result", "content": msg}]},
              "toolUseResult": msg}
    tr = _make_transcript(tmp_path, entree)
    _run(repo, tr, f"s-{uuid.uuid4()}")
    assert sum(_journal(repo)[0]["blocks"].values()) == 1


def test_two_different_reasons_in_one_entry_both_count(tmp_path):
    """Compter une fois par motif, jamais une fois par entree."""
    repo = _make_repo(tmp_path)
    msg = ("PreToolUse:Bash hook error: [x]: BLOCKED: Broad git add detected.\n"
           "PreToolUse:Bash hook error: [x]: BLOCKED: destructive sql detected.")
    tr = _make_transcript(tmp_path, _tool_result(msg))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    assert sum(_journal(repo)[0]["blocks"].values()) == 2


def test_a_quiet_session_is_written_too(tmp_path):
    """Sans ligne, « rien ne s'est passe » et « le compteur est casse » se ressemblent.

    C'est ce qui a laisse croire que nos garde-fous se taisaient : 115 sessions
    ecrites dans ce depot, 5 lignes au journal.
    """
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result("rien a signaler ici"))
    _run(repo, tr, f"s-{uuid.uuid4()}")
    entrees = _journal(repo)
    assert entrees, "une session calme doit laisser une trace, sinon le silence ment"
    assert entrees[0]["blocks"] == {} and entrees[0]["warns"] == {}
    assert entrees[0]["lues"] >= 1, "le nombre d'entrees lues rend le zero verifiable"
