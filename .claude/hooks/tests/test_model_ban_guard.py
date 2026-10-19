"""guards/model-ban-guard.py — PreToolUse: the Fable model is never used (Jay 2026-10-19).

Brief: docs/Briefs/Interdiction-Modele-Fable-2026-10-19.md. Each refusal case has a pass case
next to it: the guard reads a MODEL OPTION, never the bare word (a prompt or a doc may name it).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "model-ban-guard.py"


def _run(tool: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10)


def _refused(r: subprocess.CompletedProcess) -> bool:
    return r.returncode == 2 and "Fable est interdit" in r.stderr.decode("utf-8")


# --- Agent / Task ------------------------------------------------------------


def test_agent_with_fable_model_is_refused_with_the_french_message():
    for tool in ("Agent", "Task"):
        for model in ("fable", "Fable", "FABLE", "claude-fable-5-1", "claude-fable-5"):
            r = _run(tool, {"description": "x", "prompt": "relis", "model": model})
            assert _refused(r), (tool, model)
            assert "cross-model-reviewer" in r.stderr.decode("utf-8")


def test_agent_with_an_allowed_model_or_no_model_passes():
    for model in ("opus", "sonnet", "haiku", "claude-opus-5-5", None):
        tool_input = {"description": "x", "prompt": "relis le fichier fable.md"}
        if model is not None:
            tool_input["model"] = model
        assert _run("Agent", tool_input).returncode == 0, model


# --- Workflow ----------------------------------------------------------------


def test_workflow_script_with_a_fable_model_option_is_refused():
    for script in ("agent('relis', {model: 'fable'})",
                   'agent("relis", { model: "claude-fable-5-1" })',
                   "const opts = {\"model\": \"Fable\"}"):
        assert _refused(_run("Workflow", {"script": script})), script


def test_workflow_script_naming_fable_only_in_text_passes():
    script = "agent('Ecris une fable de La Fontaine', {model: 'opus'})"
    assert _run("Workflow", {"script": script}).returncode == 0


def test_workflow_script_path_with_a_fable_model_is_refused(tmp_path):
    f = tmp_path / "flow.js"
    f.write_text("export default async () => agent('x', {model: 'fable'})\n", encoding="utf-8")
    assert _refused(_run("Workflow", {"scriptPath": str(f)}))


def test_workflow_script_path_missing_passes(tmp_path):
    assert _run("Workflow", {"scriptPath": str(tmp_path / "absent.js")}).returncode == 0


# --- Write / Edit on agent, skill and settings files -------------------------


def test_agent_file_declaring_fable_is_refused():
    content = "---\nname: X\nmodel: fable\ntools:\n  - Read\n---\n\n# X\n"
    for path in ("/repo/.claude/agents/x-master.md", "C:\\repo\\.claude\\agents\\x.md"):
        assert _refused(_run("Write", {"file_path": path, "content": content})), path
    assert _refused(_run("Edit", {"file_path": "/repo/.claude/agents/x.md",
                                  "old_string": "model: opus", "new_string": "model: claude-fable-5"}))


def test_skill_and_settings_declaring_fable_are_refused():
    assert _refused(_run("Write", {"file_path": "/repo/.claude/skills/dev/SKILL.md",
                                   "content": "---\nname: dev\nmodel: Fable\n---\n"}))
    assert _refused(_run("Edit", {"file_path": "/repo/.claude/settings.json",
                                  "old_string": "{", "new_string": '{\n  "model": "claude-fable-5-1",'}))
    assert _refused(_run("MultiEdit", {"file_path": "/home/u/.claude/settings.local.json",
                                       "edits": [{"old_string": "a", "new_string": '"model":"fable"'}]}))


def test_agent_file_with_an_allowed_model_passes():
    content = "---\nname: X\nmodel: opus\n---\n\nAncien relecteur : Fable (interdit 2026-10-19).\n"
    assert _run("Write", {"file_path": "/repo/.claude/agents/x.md", "content": content}).returncode == 0


def test_other_files_naming_fable_pass():
    # A brief, a test or a rule may quote the forbidden option; only config files are read.
    for path in ("/repo/docs/Briefs/b.md", "/repo/.claude/hooks/tests/test_x.py"):
        assert _run("Write", {"file_path": path, "content": "model: fable\n"}).returncode == 0, path


# --- Bash --------------------------------------------------------------------


def test_bash_calling_fable_is_refused():
    for cmd in ("claude -p --model fable 'relis'",
                "claude --model=claude-fable-5-1 -p x",
                "curl https://api.anthropic.com/v1/messages -d '{\"model\":\"claude-fable-5-1\"}'",
                "ANTHROPIC_MODEL=claude-fable-5 claude -p x",
                "CLAUDE_CODE_SUBAGENT_MODEL=fable claude",
                "export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-fable-5-1'"):
        assert _refused(_run("Bash", {"command": cmd})), cmd


def test_bash_merely_naming_fable_passes():
    for cmd in ("grep -rni fable .claude",
                "git commit -m 'docs: interdire claude-fable dans la methode'",
                "claude -p --model opus 'ecris une fable'"):
        assert _run("Bash", {"command": cmd}).returncode == 0, cmd


# --- robustness --------------------------------------------------------------


def test_unknown_tool_and_malformed_input_pass():
    assert _run("Read", {"file_path": "/x/fable.md"}).returncode == 0
    r = subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True, timeout=10)
    assert r.returncode == 0
