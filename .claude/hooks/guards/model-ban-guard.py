#!/usr/bin/env python3
"""PreToolUse Agent|Task|Workflow|Write|Edit|MultiEdit|Bash — the Fable model is never used.

Jay 2026-10-19: « J'aimerais que tu INTERDISES à TOUS les agents et toi-même d'utiliser Fable. »
Reason: quota. Memory: Shinzo `05-Memoire/feedback-interdiction-fable.md`.
Brief: `docs/Briefs/Interdiction-Modele-Fable-2026-10-19.md`.

What is read is a MODEL OPTION, never the bare word (Quality.md « measuring a thing, never a
word about it »): a prompt, a commit message or a doc may say « fable » freely.

| Tool | Refused when |
|---|---|
| Agent, Task | `tool_input.model` contains `fable` |
| Workflow | the `script` (or the file at `scriptPath`) sets a `model` option to fable |
| Write, Edit, MultiEdit | an agent `.md`, a `SKILL.md`, a `.claude/commands/*.md` or a `settings*.json` sets `model` to fable |
| Bash | `--model fable`, `--fallback-model fable`, `claude config set model fable`, `model=`/`"model":` fable (API body, env var such as ANTHROPIC_MODEL) |

KNOWN LIMITS: a model chosen with `/model` in the interface is invisible to hooks; a value
built at run time (`'fa' + 'ble'`) passes; a script file launched by Bash is not opened.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402

MESSAGE = (
    "Fable est interdit (Jay, 2026-10-19, Shinzo feedback-interdiction-fable) : il consomme "
    "le quota. Utilise opus, sonnet ou haiku. Relecteur à utiliser : voir "
    "cross-model-reviewer-master § Relecteur égal ou supérieur. Pour corriger ou chercher une mention : "
    "outils Edit et Grep (le terminal est surveillé)."
)

# `model` (also inside ANTHROPIC_MODEL, "model", model=) followed by : or = then a fable value.
_OPTION = re.compile(r"model[\w\"']*\s*[:=]\s*\\?[\"'`]?\s*(?:claude-)?fable", re.I)
# CLI flag with a space: `claude --model X`, `--fallback-model X` (5th review 2026-10-19), and
# `claude config set [-g] model X`.
_FLAG = re.compile(r"--(?:fallback-)?model[\s=]+[\"']?(?:claude-)?fable"
                   r"|config\s+set\s+(?:-g\s+|--global\s+)?model\s+[\"']?(?:claude-)?fable", re.I)
_CONFIG_PATHS = (
    re.compile(r"/\.claude/agents/.+\.md$", re.I),
    re.compile(r"/skills/.+/SKILL\.md$"),
    re.compile(r"/\.claude/commands/.+\.md$", re.I),  # a slash command sets its model
    re.compile(r"/\.claude/settings[^/]*\.json$", re.I),
)


def _sets_fable(text: str) -> bool:
    return bool(_OPTION.search(text))


def _workflow_text(tool_input: dict) -> str:
    script = str(tool_input.get("script") or "")
    path = tool_input.get("scriptPath")
    if path and Path(str(path)).is_file():
        script += "\n" + Path(str(path)).read_text(encoding="utf-8", errors="replace")
    return script


def _written_text(tool_input: dict) -> str:
    parts = [str(tool_input.get("content") or ""), str(tool_input.get("new_string") or "")]
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict):
            parts.append(str(edit.get("new_string") or ""))
    return "\n".join(parts)


def _is_config_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return any(p.search(normalized) for p in _CONFIG_PATHS)


def is_forbidden(tool: str, tool_input: dict) -> bool:
    if tool in ("Agent", "Task"):
        return "fable" in str(tool_input.get("model") or "").lower()
    if tool == "Workflow":
        return _sets_fable(_workflow_text(tool_input))
    if tool in ("Write", "Edit", "MultiEdit"):
        return _is_config_file(str(tool_input.get("file_path") or "")) and _sets_fable(
            _written_text(tool_input))
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        return bool(_FLAG.search(command)) or _sets_fable(command)
    return False


def main() -> None:
    _, data = read_hook_input()
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        pass_through()
    if is_forbidden(str(data.get("tool_name") or ""), tool_input):
        block(MESSAGE)
    pass_through()


if __name__ == "__main__":
    main()
