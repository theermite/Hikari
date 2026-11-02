#!/usr/bin/env python3
"""PreToolUse Bash — `docker run -p` et les serveurs de développement n'ouvrent pas un port inscrit sans le dire.

Pourquoi
--------
`port-claim-guard.py` ne regarde que l'écriture d'un fichier compose. Une commande `docker run -p 8017:80`,
`vite --port 8009` ou `python -m http.server 8017` ouvre un port sans passer par lui (brief du 2026-10-31,
reste « docker run -p et serveurs de développement hors du garde »).

Quoi
----
Les commandes sont lues par `shell_parse` : un texte qui CITE une commande (message de commit, echo) n'en est pas
une. Chaque port publié sur l'hôte est cherché dans le registre (Shinkofa-Infra, voir `ports_registry`) :

- inscrit pour un service du serveur -> PRÉVIENT, avec le propriétaire déclaré ;
- absent du registre                 -> PRÉVIENT (le registre s'inscrit AVANT la mise en ligne) ;
- registre introuvable ou commande illisible -> laisse passer.

Ne bloque JAMAIS : la commande peut tourner sur la machine de Jay (tunnel, autre machine) et le garde ne sait pas
où elle s'exécute. Le blocage reste réservé au fichier compose, qui se met en ligne sur le serveur.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import ports_registry  # noqa: E402
import shell_parse  # noqa: E402
from common import (  # noqa: E402
    find_repo_root,
    format_warn,
    get_tool_input,
    pass_through,
    read_hook_input,
    warn,
)

_MAPPING = re.compile(r"^(?:(?:\d{1,3}(?:\.\d{1,3}){3}|\[[0-9a-fA-F:]*\]):)?(\d{2,5})(?:-\d{2,5})?:\d{1,5}(?:/\w+)?$")
_BIND = re.compile(r"(?:^|:)(\d{2,5})$")
_DEV_SERVERS = {"vite", "next", "uvicorn", "flask", "gunicorn", "serve", "http-server", "astro", "nuxt", "webpack"}
_PORT_FLAGS = {"--port", "-p"}
_BIND_FLAGS = {"--bind", "-b"}


def _program(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _published(rest: list[str]) -> list[str]:
    """Valeurs de `-p X:Y`, `-pX:Y`, `--publish X:Y`, `--publish=X:Y` dans les arguments de `docker run`."""
    values: list[str] = []
    for i, token in enumerate(rest):
        if token in ("-p", "--publish") and i + 1 < len(rest):
            values.append(rest[i + 1])
        elif token.startswith("--publish="):
            values.append(token.split("=", 1)[1])
        elif token.startswith("-p") and token[2:3].isdigit():
            values.append(token[2:])
    return values


def _docker_ports(tokens: list[str]) -> list[int]:
    """Ports hôte de `docker [container] run|create`."""
    rest = tokens[1:]
    if rest[:1] == ["container"]:
        rest = rest[1:]
    if rest[:1] not in (["run"], ["create"]):
        return []
    return [int(m.group(1)) for v in _published(rest) if (m := _MAPPING.match(v))]


def _flag_value(tokens: list[str], i: int) -> str | None:
    token = tokens[i]
    if token in _PORT_FLAGS | _BIND_FLAGS:
        return tokens[i + 1] if i + 1 < len(tokens) else None
    return token.split("=", 1)[1] if token.startswith(("--port=", "--bind=")) else None


def _http_server_port(tokens: list[str]) -> list[int]:
    """`python -m http.server N` : le port est l'argument qui suit."""
    if "http.server" not in tokens:
        return []
    following = tokens[tokens.index("http.server") + 1 :][:1]
    return [int(t) for t in following if t.isdigit()]


def _dev_server_ports(tokens: list[str]) -> list[int]:
    """Port explicite d'un serveur de développement : `--port N`, `--port=N`, `-p N`, `--bind h:N`, `http.server N`."""
    ports = _http_server_port(tokens)
    if not {_program(t) for t in tokens[:4]} & _DEV_SERVERS:
        return ports
    values = (_flag_value(tokens, i) for i in range(len(tokens)))
    return ports + [int(m.group(1)) for v in values if v and (m := _BIND.search(v))]


def requested_ports(command: str) -> list[int]:
    try:
        segments = shell_parse.simple_commands(command)
    except ValueError:
        return []
    found: set[int] = set()
    for tokens in segments:
        if tokens and _program(tokens[0]) == "docker":
            found.update(_docker_ports(tokens))
        elif tokens:
            found.update(_dev_server_ports(tokens))
    return sorted(found)


def _announce(ports: list[int], owners: dict[int, str], local: dict[int, str]) -> None:
    taken = [f"{p} -> {owners[p][:80]}" for p in ports if p in owners]
    unknown = [p for p in ports if p not in owners and p not in local]
    if taken:
        warn(format_warn(
            reason=f"port(s) déjà inscrit(s) au registre du serveur ({'; '.join(taken)})",
            action="si la commande tourne sur le serveur, choisis un port libre; sur ta machine (tunnel, essai), "
                   "ignore cet avertissement.",
            reference="registre des ports (Shinkofa-Infra)",
        ))
    if unknown:
        warn(format_warn(
            reason=f"port(s) {', '.join(map(str, unknown))} absent(s) du registre des ports",
            action="inscris-les dans `Shinkofa-Infra/registry/infra.yaml` AVANT la mise en ligne.",
            reference="registre des ports (Shinkofa-Infra)",
        ))


def main() -> None:
    _, data = read_hook_input()
    command = get_tool_input(data).get("command") or ""
    ports = requested_ports(command) if isinstance(command, str) else []
    infra = ports_registry.find_infra_root(find_repo_root(None)) if ports else None
    owners = ports_registry.read_owners(infra) if infra else {}
    if owners:
        _announce(ports, owners, ports_registry.read_owners(infra, machine="local"))
    pass_through()


if __name__ == "__main__":
    main()
