"""Registre des ports : qui possède quel port, et quels ports un fichier compose demande.

Deux listes existent dans Shinkofa-Infra : `registry/infra.yaml` (lue par le comparateur de dérive) et
`docs/Port-Registry.md` (écrite à la main, avec les ports de la tour). Un port est connu s'il figure dans
l'une OU l'autre : le garde-fou qui s'en sert ne doit pas rater un port à cause de la liste qu'il lit.
Aucune dépendance (pas de PyYAML) : les garde-fous tournent avec le Python nu.
"""

from __future__ import annotations

import re
from pathlib import Path

ESCAPE = re.compile(r"#\s*PORT-OK:\s*\S")

_COMPOSE_FILE = re.compile(r"(^|[\\/])(docker-)?compose[^\\/]*\.ya?ml$", re.IGNORECASE)
_YAML_PORT = re.compile(r"^[ ]{2}(\d{2,5}):[ ]*(.*)$", re.MULTILINE)
_MD_ROW = re.compile(r"^\|[ ]*(\d{2,5})[ ]*\|(.*)$", re.MULTILINE)
_PORT_MAPPING = re.compile(
    r"^[ \t]*-[ \t]*[\"']?(?:(?:\d{1,3}(?:\.\d{1,3}){3}|\[[0-9a-fA-F:]*\]):)?(\d{2,5}):\d{1,5}"
    r"(?:/(?:tcp|udp))?[\"']?[ \t]*(?:#.*)?$",
    re.MULTILINE,
)
_CONTAINER_NAME = re.compile(r"^[ \t]*container_name:[ \t]*[\"']?([\w.-]+)", re.MULTILINE)


def is_compose_file(path: str) -> bool:
    return bool(path) and bool(_COMPOSE_FILE.search(path))


def host_ports(content: str) -> list[int]:
    """Ports publiés sur l'hôte par un fichier compose (forme courte `[ip:]hote:conteneur`)."""
    return sorted({int(m.group(1)) for m in _PORT_MAPPING.finditer(content)})


def container_names(content: str) -> list[str]:
    return _CONTAINER_NAME.findall(content)


def _yaml_ports_section(text: str) -> str:
    debut = text.find("\nports:\n")
    if debut < 0:
        return ""
    reste = text[debut + len("\nports:\n"):]
    fin = re.search(r"^\S", reste, re.MULTILINE)
    return reste[: fin.start()] if fin else reste


def read_owners(infra_root: Path) -> dict[int, str]:
    """Port -> texte du ou des propriétaires déclarés, les deux listes réunies. {} si aucune lisible."""
    owners: dict[int, list[str]] = {}
    sources = (
        (infra_root / "registry" / "infra.yaml", lambda t: _YAML_PORT.finditer(_yaml_ports_section(t))),
        (infra_root / "docs" / "Port-Registry.md", lambda t: _MD_ROW.finditer(t)),
    )
    for path, finder in sources:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in finder(text):
            owners.setdefault(int(m.group(1)), []).append(m.group(2).strip())
    return {port: " | ".join(parts) for port, parts in owners.items()}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def same_service(owner_text: str, names: list[str]) -> bool:
    """Le propriétaire déclaré et l'un de nos noms (projet, conteneur) se contiennent l'un l'autre."""
    owner = _norm(owner_text)
    for name in names:
        n = _norm(name)
        if len(n) >= 4 and (n in owner or any(len(w) >= 4 and w in n for w in _owner_words(owner_text))):
            return True
    return False


# Mots qui décrivent un service sans le nommer : « server » ou « prod » dans le texte du registre ne
# prouvent pas que deux services sont le même.
_MOTS_VIDES = frozenset({
    "server", "prod", "production", "docker", "container", "service", "staging", "internal", "reserve",
    "reserved", "bind", "only", "with", "from", "http", "https", "none", "port", "tour", "local",
})


def _owner_words(owner_text: str) -> list[str]:
    mots = (_norm(w) for w in re.split(r"[^A-Za-z0-9]+", owner_text))
    return [m for m in mots if len(m) >= 4 and m not in _MOTS_VIDES]


def check(content: str, project: str, owners: dict[int, str]) -> tuple[list[tuple[int, str]], list[int]]:
    """(conflits, inconnus). Conflit = port pris par un autre service ; inconnu = absent du registre."""
    if ESCAPE.search(content):
        return [], []
    names = [project, *container_names(content)]
    conflicts: list[tuple[int, str]] = []
    unknown: list[int] = []
    for port in host_ports(content):
        owner = owners.get(port)
        if owner is None:
            unknown.append(port)
        elif not same_service(owner, names):
            conflicts.append((port, owner))
    return conflicts, unknown
