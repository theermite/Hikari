"""Tests for quality/logs-first.py — LOGS FIRST heuristic.

Refactored 2026-09-15 (independent review, 2nd pass) while closing the same
missing-guard family as transcript_reader.py's other readers: the original
`analyze_recent_sequence` was a single 73-line, complexity-35 function, split
here into small named steps.

4th independent review (2026-09-15) caught two things the first refactor got
wrong, both fixed here:
  1. An end-to-end comparison against 5 synthetic transcripts is NOT a
     behaviour proof on this function: `_entries_since_last_user` stops at
     the first role == "user" entry, and a tool_result delivery IS role ==
     "user" in the real transcript shape. `had_failed_bash` can therefore
     never become True on a realistic transcript (the tool_result that would
     set it always falls exactly on the cutoff) -- measured on 40 real
     session transcripts, 2507 tool_result blocks, 0 exceptions, both old and
     new code return (False, False) every time. An end-to-end check that
     cannot distinguish two implementations proves nothing; the tests below
     target the small steps directly instead.
  2. The split accidentally RESURRECTED a dead branch: the pre-refactor code
     had `if name == "Bash": pass`, so a Bash command was never treated as a
     log read. `_reads_logs` restores that (Bash absent from its map) rather
     than silently widening what the gate accepts.

Pre-existing, unrelated to tonight's fix, deliberately not touched here: the
window-cutting behaviour itself (point 1 above) makes this gate a no-op on
real transcripts today. Flagged for a separate decision, not redesigned.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "logs-first.py"
_spec = importlib.util.spec_from_file_location("logs_first", HOOK)
logs_first = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(logs_first)


def _bash_use(tid: str, command: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command}}]}}


def _bash_result(tid: str, text: str, is_error: bool = False) -> dict:
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


def _read(path: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": path}}]}}


def _write(tmp_path: Path, *entries) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


# --- les briques, testees directement --------------------------------------


def test_reads_logs_detects_a_log_path_on_read():
    assert logs_first._reads_logs("Read", {"file_path": "server.log"}) is True


def test_reads_logs_is_silent_on_an_unrelated_path():
    assert logs_first._reads_logs("Read", {"file_path": "app.py"}) is False


def test_reads_logs_ignores_bash_even_when_the_command_mentions_logs():
    # Le branchement Bash etait mort dans le code d'origine (`if name ==
    # "Bash": pass`) -- la refonte l'a ressuscite par erreur, 4e relecture
    # independante (2026-09-15). Reste mort, delibere.
    assert logs_first._reads_logs("Bash", {"command": "tail -f server.log"}) is False


def test_looks_like_failure_on_is_error_flag():
    assert logs_first._looks_like_failure({"is_error": True, "content": "ok"}) is True


def test_looks_like_failure_on_traceback_text():
    assert logs_first._looks_like_failure({"is_error": False, "content": "Traceback: boom"}) is True


def test_looks_like_failure_is_silent_on_a_clean_result():
    assert logs_first._looks_like_failure({"is_error": False, "content": "a.txt\nb.txt"}) is False


def test_scan_block_flags_a_failing_tool_result():
    failed, read_after = logs_first._scan_block(
        {"type": "tool_result", "is_error": True, "content": "boom"}, had_failed_bash=False
    )
    assert (failed, read_after) == (True, False)


def test_scan_block_flags_a_log_read_once_a_failure_is_known():
    failed, read_after = logs_first._scan_block(
        {"type": "tool_use", "name": "Read", "input": {"file_path": "app.log"}}, had_failed_bash=True
    )
    assert (failed, read_after) == (False, True)


def test_entries_since_last_user_stops_at_the_last_user_message(tmp_path):
    t = _write(tmp_path, {"message": {"role": "user", "content": "go"}}, _read("app.log"))
    after = logs_first._entries_since_last_user(str(t))
    assert len(after) == 1


# --- la fonction complete : pas de plantage, comportement inchange ----------


def test_no_transcript_passes():
    assert logs_first.analyze_recent_sequence("") == (False, True)


def test_a_non_object_entry_does_not_crash_the_scan(tmp_path):
    # 2e relecture independante (2026-09-15) : meme motif non garde ici.
    t = _write(tmp_path, _bash_use("t1", "pytest"), _read("app.log"), None)
    # Ne doit pas lever -- la valeur exacte depend du comportement preexistant
    # de la fenetre (voir docstring du module), non modifie ici.
    logs_first.analyze_recent_sequence(str(t))


def test_clean_sequence_has_no_failure(tmp_path):
    t = _write(tmp_path, _bash_use("t1", "ls"))
    assert logs_first.analyze_recent_sequence(str(t)) == (False, False)
