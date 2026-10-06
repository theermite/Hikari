"""hook_cost — what the guards cost in the conversation, read from the journal.

Jay, 2026-09-28: « Ce systeme, aussi bien les garde-fous que ce que tu as
propose, ca coute des tokens sur mes sessions ? » Running a guard costs
nothing; what it WRITES into the conversation does. This meter counts exactly
that, selected on the journal's own fields (Quality.md « measuring a thing,
never a word about it ») — never on a word found in the text:

- context the model receives: `hook_success.content`, `hook_additional_context`
- refusals: `hook_blocking_error`, and an errored tool_result that OPENS with
  the harness frame `PreToolUse:<tool> hook error` / `PostToolUse:...`

Shapes copied from a real journal (session f3acc97f, 2026-09-26/28).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import hook_cost  # noqa: E402


def _att(**fields) -> dict:
    return {"type": "attachment", "attachment": fields}


def _refusal(text: str, is_error: bool = True) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "is_error": is_error, "content": text}]}}


def _transcript(tmp_path: Path, *entries) -> str:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(p)


BLOCK = "PreToolUse:Edit hook error: [bash x]: BLOCKED: Non-trivial change"


def test_each_channel_is_counted(tmp_path):
    t = _transcript(
        tmp_path,
        _att(type="hook_success", hookEvent="UserPromptSubmit", content="[TIME] 21:21", stdout="x"),
        _att(type="hook_additional_context", hookEvent="PreToolUse", content=["[MEMOIRE] abc"]),
        _att(type="hook_blocking_error", hookEvent="PostToolUse",
             blockingError={"blockingError": "BLOCKED: too long"}),
        _refusal(BLOCK),
    )
    m = hook_cost.measure(t)
    assert m["context_chars"] == len("[TIME] 21:21") + len("[MEMOIRE] abc")
    assert m["refusals"] == 2
    assert m["refusal_chars"] == len("BLOCKED: too long") + len(BLOCK)
    assert m["tokens_est"] == (m["context_chars"] + m["refusal_chars"]) // hook_cost.CHARS_PER_TOKEN


def test_a_silent_hook_costs_nothing(tmp_path):
    # PreToolUse successes carry their output in stdout JSON, content "" —
    # nothing reaches the model through them.
    t = _transcript(tmp_path, _att(type="hook_success", hookEvent="PreToolUse", content="",
                                   stdout='{"hookSpecificOutput": {}}'))
    assert hook_cost.measure(t)["context_chars"] == 0


def test_talking_about_a_block_is_not_a_block(tmp_path):
    # An error that merely QUOTES the frame (a failed Bash that grepped a log)
    # does not open with it; a success result that opens with it is no refusal.
    t = _transcript(tmp_path, _refusal("grep said: " + BLOCK), _refusal(BLOCK, is_error=False))
    assert hook_cost.measure(t)["refusals"] == 0


def test_a_user_visible_system_message_is_not_model_context(tmp_path):
    t = _transcript(tmp_path, _att(type="hook_system_message", content="[GARDE-FOUS] 68"))
    assert hook_cost.measure(t)["context_chars"] == 0


HOOKS = Path(__file__).resolve().parents[1]


def _load(rel: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(rel.split("/")[-1][:-3].replace("-", "_"), HOOKS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_session_meter_records_the_cost(tmp_path):
    import subprocess
    (tmp_path / ".git").mkdir()
    t = _transcript(tmp_path, _att(type="hook_success", hookEvent="UserPromptSubmit", content="x" * 400),
                    _refusal(BLOCK))
    r = subprocess.run([sys.executable, str(HOOKS / "lifecycle/hook-blocks-stats.py")],
                       input=json.dumps({"session_id": "s1", "transcript_path": t}).encode(),
                       capture_output=True, cwd=str(tmp_path))
    journal = (tmp_path / ".claude/state/hook-blocks.jsonl").read_text(encoding="utf-8").splitlines()
    cost = json.loads(journal[-1])["cost"]
    assert cost["refusals"] == 1 and cost["context_chars"] == 400
    assert b"hook-cost:" in r.stderr and b"estimation" in r.stderr


def test_the_report_gives_the_cost_per_session():
    report = _load("lifecycle/hook-blocks-report.py")
    entries = [{"session_id": "a", "cost": {"tokens_est": 1000, "refusals": 2}},
               {"session_id": "b", "cost": {"tokens_est": 3000, "refusals": 0}},
               {"session_id": "old"}]  # recorded before the meter existed: not averaged in
    assert report.cost_summary(entries) == {"sessions": 2, "avg_tokens": 2000, "max_tokens": 3000,
                                            "refusals": 2}


def test_a_resumed_session_counts_once():
    # Each SessionEnd writes a CUMULATIVE measure of the same journal: a resumed
    # session keeps only its last entry (independent review, 2026-09-29).
    report = _load("lifecycle/hook-blocks-report.py")
    entries = [{"session_id": "a", "cost": {"tokens_est": 1000, "refusals": 2}},
               {"session_id": "a", "cost": {"tokens_est": 1500, "refusals": 3}},
               {"session_id": "b", "cost": {"tokens_est": 500, "refusals": 0}}]
    assert report.cost_summary(entries) == {"sessions": 2, "avg_tokens": 1000, "max_tokens": 1500,
                                            "refusals": 3}


def test_it_says_how_much_it_read(tmp_path):
    # A zero must be believable: "no guard spoke" vs "read nothing".
    t = _transcript(tmp_path, None, _refusal(BLOCK))
    assert hook_cost.measure(t)["lues"] == 2
    assert hook_cost.measure(str(tmp_path / "absent.jsonl"))["lues"] == 0
