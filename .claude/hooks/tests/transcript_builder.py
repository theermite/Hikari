"""Aides de test : fabrique un journal de séance (JSON lines) avec appels d'outil, résultats et messages de Jay."""

from __future__ import annotations

import json
from pathlib import Path


class Journal:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._n = 0

    def user(self, text: str) -> "Journal":
        self.entries.append({"type": "user", "message": {"role": "user", "content": text}})
        return self

    def tool(self, name: str, tool_input: dict, output: str = "", is_error: bool = False) -> "Journal":
        self._n += 1
        ident = f"toolu_{self._n}"
        self.entries.append({"type": "assistant", "message": {"role": "assistant",
                             "content": [{"type": "tool_use", "id": ident, "name": name, "input": tool_input}]}})
        self.entries.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": ident, "content": output, "is_error": is_error}]}})
        return self

    def bash(self, command: str, output: str = "", is_error: bool = False) -> "Journal":
        return self.tool("Bash", {"command": command}, output, is_error)

    def say(self, text: str) -> "Journal":
        self.entries.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
        return self

    def write_to(self, path: Path) -> str:
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in self.entries), encoding="utf-8")
        return str(path)
