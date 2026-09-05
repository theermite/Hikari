#!/usr/bin/env python3
"""Sonde de sante des garde-fous — SessionStart. Annonce, ne bloque jamais.

POURQUOI ELLE EXISTE. Le 2026-09-05, deux sessions ont affiche
`Hook error: SessionStart (exit 126)` sans que personne ne s'en apercoive avant
qu'un test de cablage n'echoue. **Un garde-fou qui meurt en silence ressemble
exactement a un garde-fou vert.** Toute la methodologie repose sur « ce qui est
tenu par du code tient » — cette phrase devient fausse des qu'un controle ne
tourne pas, et rien ne le disait.

Meme famille que « une integration continue silencieuse ressemble a une
integration verte » (Manabi, 2026-09-01) : la panne et le succes rendent le meme
signal, c'est-a-dire aucun.

CE QU'ELLE FAIT. Au demarrage de chaque session, elle repond a trois questions
et affiche la reponse :
1. Quel interprete Python s'execute VRAIMENT ? (pas lequel le PATH nomme —
   `command -v` trouve le raccourci Microsoft Store, qui refuse de tourner)
2. Combien de garde-fous sont configures ?
3. Combien pointent vers un fichier absent ?

CE QU'ELLE NE FAIT PAS. Elle ne bloque rien. Une session doit pouvoir demarrer
meme sans garde-fou — mais alors on le SAIT, et on decide en connaissance.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root  # type: ignore

# L'ordre compte : le premier qui S'EXECUTE gagne, pas le premier nomme.
CANDIDATS = ("python3", "python", "py", "python3.13", "python3.12")

# `bash "<...>/_run.sh" <cible>` ou l'ancienne forme `"$HOOK"` avec HOOK=...
# Le guillemet fermant colle au nom : sans le `"?`, la sonde comptait ZERO
# garde-fou tout en affichant « operationnels ». Elle produisait exactement le
# faux zero qu'elle existe pour detecter (trouve a sa premiere execution reelle).
CIBLE_LANCEUR = re.compile(r'_run\.sh"?\s+(\S+)')
CIBLE_ANCIENNE = re.compile(r"/\.claude/hooks/(\S+?\.py)")


def _interprete_qui_tourne() -> tuple[str | None, str]:
    """Rend le premier interprete qui s'execute reellement, et sa version.

    On le FAIT TOURNER : c'est la seule preuve. Le raccourci Microsoft Store
    existe sur le PATH et repond « permission refusee » a l'execution — un test
    de presence le declarerait bon.
    """
    for nom in CANDIDATS:
        try:
            proc = subprocess.run([nom, "-c", "import sys;print(sys.version.split()[0])"],
                                  capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return nom, proc.stdout.strip()
    return None, ""


def _commandes(config: dict):
    """Aplatit la configuration en une suite de commandes."""
    for entrees in (config.get("hooks") or {}).values():
        for entree in entrees or []:
            for hook in entree.get("hooks") or []:
                yield str(hook.get("command") or "")


def _cibles(reglages: Path) -> list[str]:
    try:
        config = json.loads(reglages.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    cibles = []
    for commande in _commandes(config):
        trouve = CIBLE_LANCEUR.search(commande) or CIBLE_ANCIENNE.search(commande)
        if trouve:
            cibles.append(trouve.group(1))
    return cibles


def diagnostiquer(reglages: Path | None = None, racine: Path | None = None) -> dict:
    """Etat des garde-fous. Ne leve jamais."""
    racine = Path(racine) if racine else find_repo_root()
    reglages = Path(reglages) if reglages else racine / ".claude" / "settings.json"
    nom, version = _interprete_qui_tourne()
    cibles = _cibles(reglages)
    absents = [c for c in cibles if not (racine / ".claude" / "hooks" / c).is_file()]
    # Defaut D2, relecture independante du 2026-09-06 : la sonde verifiait les
    # cibles `.py` et sondait `python3` en direct — deux choses que les garde-fous
    # n'empruntent PAS. Ils passent tous par `_run.sh`. Un depot qui recoit le
    # cablage sans le lanceur affichait « 60 operationnels » avec 60 controles
    # morts. C'est exactement le faux vert que cette sonde existe pour tuer.
    lanceur = racine / ".claude" / "hooks" / "_run.sh"
    return {
        "interprete": nom,
        "version": version,
        "hooks_configures": len(cibles),
        "fichiers_absents": sorted(set(absents)),
        "lanceur_present": lanceur.is_file(),
    }


def message(etat: dict) -> str:
    """Le texte affiche. Il nomme toujours la CONSEQUENCE, jamais juste l'etat —
    un diagnostic qui dit « KO » sans dire ce que ca coute ne declenche rien."""
    if not etat.get("lanceur_present", True):
        return ("[GARDE-FOUS] Le lanceur `.claude/hooks/_run.sh` est ABSENT. "
                f"{etat['hooks_configures']} garde-fous sont cables et AUCUN ne peut "
                "demarrer : chaque appel echouera. Conséquence : rien n'est tenu par du "
                "code cette session. Recuperer le fichier depuis Kata avant de coder.")
    if etat["interprete"] is None:
        return ("[GARDE-FOUS] AUCUN interprete Python executable. "
                f"{etat['hooks_configures']} garde-fous configures, ZERO ne peut tourner. "
                "Conséquence : rien n'est tenu par du code cette session — ni le masquage "
                "des secrets, ni les limites de taille, ni la porte de reformulation. "
                "Traiter avant de coder.")
    lignes = [f"[GARDE-FOUS] {etat['hooks_configures']} configures · interprete "
              f"{etat['interprete']} {etat['version']} · operationnels."]
    if etat["fichiers_absents"]:
        lignes.append(f"[GARDE-FOUS] {len(etat['fichiers_absents'])} pointent vers un fichier "
                      f"ABSENT, donc ne gardent rien : {', '.join(etat['fichiers_absents'])}")
    return "\n".join(lignes)


def build_decision(etat: dict | None = None) -> dict:
    """Toujours une annonce, jamais un blocage."""
    etat = etat if etat is not None else diagnostiquer()
    return {
        "systemMessage": message(etat),
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message(etat),
        },
    }


def main() -> None:
    try:
        print(json.dumps(build_decision(), ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 — une sonde ne casse jamais un demarrage
        print(f"[DEBUG][hook-health-check] {type(error).__name__}: {error}", file=sys.stderr)
        print("{}")


if __name__ == "__main__":
    main()
