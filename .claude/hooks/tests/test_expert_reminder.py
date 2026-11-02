"""expert-reminder.py — un fichier touché rappelle son expert, une fois par séance, et le rappel laisse une trace.

Remplace matter-expert-suggest (2026-11-01) : il ne se souvenait qu'une fois PAR DÉPÔT (le fichier d'état n'était jamais
vidé) et ne laissait aucune trace, donc personne ne pouvait dire si un rappel était suivi. Ici : une fois par séance,
un registre unique (agents-wiring.json), et un journal des rappels que le garde hebdomadaire croise avec les lancements.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "expert-reminder.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import agent_wiring  # noqa: E402


def _lancer(repo: Path, fichier: str, session: str = "s1"):
    entree = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": session, "cwd": str(repo),
                         "tool_input": {"file_path": str(repo / fichier)}})
    return subprocess.run([sys.executable, str(HOOK)], input=entree, capture_output=True, text=True, cwd=str(repo))


def _contexte(fait) -> str:
    if not fait.stdout.strip():
        return ""
    return json.loads(fait.stdout)["hookSpecificOutput"]["additionalContext"]


def _depot(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


def _rappels(repo: Path) -> list[dict]:
    chemin = repo / ".claude" / "state" / "expert-reminders.jsonl"
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()] if chemin.exists() else []


# ---------------------------------------------------------------- le registre

def test_a_tsx_file_reminds_the_interface_experts():
    agents = {a for a, _ in agent_wiring.reminders_for("src/ui/Card.tsx")}
    assert {"Frontend Master", "Accessibility Master", "UX Design Master"} <= agents


def test_an_elixir_file_reminds_the_elixir_expert():
    assert {a for a, _ in agent_wiring.reminders_for("lib/app/accounts.ex")} == {"Elixir Phoenix Master"}


def test_a_test_file_reminds_nobody():
    assert agent_wiring.reminders_for("src/ui/Card.test.tsx") == []
    assert agent_wiring.reminders_for("tests/test_accounts.exs") == []


def test_a_blocking_only_path_is_not_a_reminder():
    assert agent_wiring.reminders_for("src/payment/hook.py") == []


# ---------------------------------------------------------------- le rappel sur de vrais fichiers

def test_editing_an_elixir_file_adds_a_reminder_and_a_trace(tmp_path):
    repo = _depot(tmp_path)
    fait = _lancer(repo, "lib/app/accounts.ex")
    assert fait.returncode == 0 and "Elixir Phoenix Master" in _contexte(fait)
    trace = _rappels(repo)
    assert [t["agent"] for t in trace] == ["Elixir Phoenix Master"] and trace[0]["file"].endswith("accounts.ex")


def test_the_reminder_comes_once_per_session_and_agent(tmp_path):
    repo = _depot(tmp_path)
    assert _contexte(_lancer(repo, "lib/a.ex")) != ""
    assert _contexte(_lancer(repo, "lib/b.ex")) == ""
    assert len(_rappels(repo)) == 1


def test_a_new_session_reminds_again(tmp_path):
    repo = _depot(tmp_path)
    _lancer(repo, "lib/a.ex", session="s1")
    assert _contexte(_lancer(repo, "lib/a.ex", session="s2")) != ""
    assert len(_rappels(repo)) == 2


def test_several_experts_for_one_file_share_one_message(tmp_path):
    repo = _depot(tmp_path)
    contexte = _contexte(_lancer(repo, "src/Card.tsx"))
    assert "Frontend Master" in contexte and "Accessibility Master" in contexte
    assert len(_rappels(repo)) == 3


def test_an_ordinary_file_says_nothing(tmp_path):
    repo = _depot(tmp_path)
    fait = _lancer(repo, "src/a.py")
    assert fait.returncode == 0 and _contexte(fait) == "" and _rappels(repo) == []


def test_the_message_never_blocks_and_names_the_way_to_launch(tmp_path):
    repo = _depot(tmp_path)
    fait = _lancer(repo, "lib/a.ex")
    assert fait.returncode == 0
    assert "Agent" in _contexte(fait)
