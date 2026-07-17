"""Tests for .claude/hooks/lifecycle/hook-blocks-report.py — A2-v2 cumulative guardrail report.

Reads the per-session journal written by hook-blocks-stats.py (A2):
  {"session_id","ts","blocks":{sig:count},"warns":{sig:count}}
and aggregates a cumulative leaderboard across sessions, plus a friction proxy:
how often a signature blocks/warns 2+ times within a single session.

Pure-function level: the script is loaded via importlib (hyphenated filename),
and aggregate()/load_entries() are exercised directly.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "lifecycle" / "hook-blocks-report.py"


def _load():
    spec = importlib.util.spec_from_file_location("hook_blocks_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load()


def _entry(session: str, blocks: dict | None = None, warns: dict | None = None,
           overcome: dict | None = None) -> dict:
    e = {"session_id": session, "ts": "2026-06-13T10:00:00Z"}
    if blocks is not None:
        e["blocks"] = blocks
    if warns is not None:
        e["warns"] = warns
    if overcome is not None:
        e["overcome"] = overcome
    return e


# --- aggregate --------------------------------------------------------------


def test_aggregate_orders_by_total_desc():
    entries = [
        _entry("s1", blocks={"veille missing": 1, "reformulation needed": 3}),
        _entry("s2", blocks={"veille missing": 1}),
    ]
    rows = report.aggregate(entries)
    assert [r["signature"] for r in rows] == ["reformulation needed", "veille missing"]
    assert rows[0]["total"] == 3
    assert rows[1]["total"] == 2


def test_aggregate_counts_distinct_sessions():
    entries = [
        _entry("s1", blocks={"veille missing": 1}),
        _entry("s2", blocks={"veille missing": 1}),
        _entry("s3", warns={"veille missing": 1}),
    ]
    rows = report.aggregate(entries)
    row = next(r for r in rows if r["signature"] == "veille missing")
    assert row["sessions"] == 3


def test_aggregate_detects_repeat_within_session():
    # 3 occurrences in ONE session -> friction proxy (repeat) counts that session.
    entries = [
        _entry("s1", blocks={"reformulation needed": 3}),
        _entry("s2", blocks={"reformulation needed": 1}),
    ]
    rows = report.aggregate(entries)
    row = next(r for r in rows if r["signature"] == "reformulation needed")
    assert row["repeat_sessions"] == 1  # only s1 had >= 2
    assert row["sessions"] == 2


def test_aggregate_separates_blocks_and_warns():
    entries = [
        _entry("s1", blocks={"veille missing": 2}, warns={"safari test": 1}),
    ]
    rows = report.aggregate(entries)
    veille = next(r for r in rows if r["signature"] == "veille missing")
    safari = next(r for r in rows if r["signature"] == "safari test")
    assert veille["blocks"] == 2 and veille["warns"] == 0
    assert safari["warns"] == 1 and safari["blocks"] == 0


def test_aggregate_repeat_counts_combined_kinds_per_session():
    # 1 block + 1 warn of same sig in same session = 2 occurrences -> repeat.
    entries = [_entry("s1", blocks={"sig x": 1}, warns={"sig x": 1})]
    rows = report.aggregate(entries)
    row = next(r for r in rows if r["signature"] == "sig x")
    assert row["repeat_sessions"] == 1


def test_aggregate_empty():
    assert report.aggregate([]) == []


def test_aggregate_sums_overcome_per_signature():
    # overcome (block retried-and-passed) accumulates across sessions per signature.
    entries = [
        _entry("s1", blocks={"veille missing": 1}, overcome={"veille missing": 1}),
        _entry("s2", blocks={"veille missing": 1}, overcome={"veille missing": 1}),
        _entry("s3", blocks={"safari test": 1}),  # no overcome key
    ]
    rows = report.aggregate(entries)
    veille = next(r for r in rows if r["signature"] == "veille missing")
    safari = next(r for r in rows if r["signature"] == "safari test")
    assert veille["overcome"] == 2
    assert safari["overcome"] == 0


def test_overcome_rendered_as_parasite_candidate(capsys):
    rows = report.aggregate([_entry("s1", blocks={"x gate": 1}, overcome={"x gate": 1})])
    report.render(rows, n_sessions=1, top=0)
    out = capsys.readouterr().out
    assert "Parasite candidates" in out
    assert "x gate" in out


# --- load_entries -----------------------------------------------------------


def test_load_entries_skips_malformed_lines(tmp_path):
    journal = tmp_path / "hook-blocks.jsonl"
    journal.write_text(
        json.dumps(_entry("s1", blocks={"a": 1})) + "\n"
        + "this is not json\n"
        + json.dumps(_entry("s2", blocks={"b": 1})) + "\n",
        encoding="utf-8",
    )
    entries = report.load_entries(journal)
    assert len(entries) == 2


def test_load_entries_tolerates_missing_keys(tmp_path):
    journal = tmp_path / "hook-blocks.jsonl"
    # entry with only blocks, entry with only warns
    journal.write_text(
        json.dumps(_entry("s1", blocks={"a": 1})) + "\n"
        + json.dumps(_entry("s2", warns={"b": 1})) + "\n",
        encoding="utf-8",
    )
    entries = report.load_entries(journal)
    rows = report.aggregate(entries)
    assert {r["signature"] for r in rows} == {"a", "b"}


def test_load_entries_missing_file_returns_empty(tmp_path):
    assert report.load_entries(tmp_path / "nope.jsonl") == []
