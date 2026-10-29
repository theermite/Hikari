#!/usr/bin/env python3
"""PreToolUse Write|Edit|MultiEdit — un fichier compose ne prend pas un port déjà pris.

Pourquoi
--------
Reproche de Jay (2026-07-29, répété) : une séance tente d'utiliser un port qui sert déjà à autre chose,
parce qu'elle n'a pas consulté le registre. Le garde de dérive (`pre-infra-drift-check.py`) ne regarde
qu'au moment de la mise en ligne, trop tard. Ici on regarde quand le port s'écrit.

Quoi
----
Sur l'écriture d'un fichier `docker-compose*.yml` / `compose*.yml`, chaque port publié sur l'hôte est
cherché dans le registre (`Shinkofa-Infra/registry/infra.yaml` + `docs/Port-Registry.md`, frère du dépôt
courant, ou `~/apps/Shinkofa-Infra`) :

- pris par un AUTRE service  -> BLOQUE, avec le propriétaire déclaré et la sortie.
- absent du registre         -> PRÉVIENT (le registre s'inscrit AVANT la mise en ligne), ne bloque pas.
- registre introuvable       -> laisse passer (dépôt hors atelier ou machine sans le registre).

Sortie légitime d'un faux positif : `# PORT-OK: <raison>` dans le contenu écrit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    canonical_project_name,
    find_repo_root,
    format_block,
    format_warn,
    get_file_path,
    get_tool_input,
    pass_through,
    read_hook_input,
    warn,
)
import ports_registry  # noqa: E402


def _infra_root(repo_root: Path) -> Path | None:
    for candidat in (repo_root.parent / "Shinkofa-Infra", Path.home() / "apps" / "Shinkofa-Infra"):
        if (candidat / "registry").is_dir() or (candidat / "docs" / "Port-Registry.md").is_file():
            return candidat
    return None


def _written_content(data: dict) -> str:
    ti = get_tool_input(data)
    morceaux = [ti.get("content") or "", ti.get("new_string") or ""]
    morceaux += [e.get("new_string") or "" for e in ti.get("edits") or [] if isinstance(e, dict)]
    return "\n".join(m for m in morceaux if m)


def _signaler(conflits: list[tuple[int, str]], inconnus: list[int]) -> None:
    if conflits:
        lignes = "; ".join(f"{port} -> {owner[:80]}" for port, owner in conflits)
        block(format_block(
            reason=f"port déjà pris par un autre service d'après le registre ({lignes})",
            recovery="choisis un port libre dans `Shinkofa-Infra/docs/Port-Registry.md`, inscris-le au "
                     "registre dans le même commit, puis réécris. Si c'est bien le même service, ajoute "
                     "`# PORT-OK: <raison>` dans le fichier.",
            reference="registre des ports (Shinkofa-Infra)",
        ))
    if inconnus:
        warn(format_warn(
            reason=f"port(s) {', '.join(map(str, inconnus))} absent(s) du registre des ports",
            action="inscris-les dans `Shinkofa-Infra/registry/infra.yaml` et `docs/Port-Registry.md` "
                   "AVANT la mise en ligne, dans le même commit.",
            reference="registre des ports (Shinkofa-Infra)",
        ))


def main() -> None:
    _, data = read_hook_input()
    path = get_file_path(data)
    content = _written_content(data)
    if not ports_registry.is_compose_file(path) or not ports_registry.host_ports(content):
        pass_through()
    repo = find_repo_root(Path(path).parent if Path(path).is_absolute() else None)
    infra = _infra_root(repo)
    owners = ports_registry.read_owners(infra) if infra else {}
    if not owners:
        pass_through()
    _signaler(*ports_registry.check(content, canonical_project_name(repo), owners))
    pass_through()


if __name__ == "__main__":
    main()
