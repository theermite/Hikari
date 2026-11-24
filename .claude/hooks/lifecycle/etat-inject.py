#!/usr/bin/env python3
"""État inject — UserPromptSubmit. Les faits arrivent dans le contexte AVANT que Takumi parle.

Jay 2026-11-24: la méthode doit anticiper les erreurs, pas les corriger après coup. Trois fois dans la journée j'ai affirmé un état de
mémoire (fusionné ou non, nombre de gardes, décisions à trancher). Ici le code calcule et dépose les faits :
- toujours, quand le registre existe : les décisions ouvertes (pour Jay seulement) et les dernières tranchées (`lib/decisions.py`) ;
- là où `scripts/etat.py` existe (Kata) : l'état du chantier (branches, propagation par contenu).
Quand : au premier message de la séance, puis chaque fois que Jay demande un point, un état, un reste à faire, une propagation, une
fusion ou une décision. Sinon rien (le contexte coûte à chaque réponse). Toute erreur: sortie 0 muette.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import decisions as dec  # noqa: E402
from common import find_repo_root, read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402

STATE_NAME = "etat-injecte"
MAX_LIGNES_ETAT = 40
_DEMANDE = re.compile(
    r"(?i)\b(?:point|[ée]tat|avancement|reste|restent|propag\w*|fusion\w*|fusionn\w*|d[ée]cision\w*|o[ùu] on en est|o[ùu] en est|"
    r"branche\w*|d[ée]j[àa] (?:fait|tranch\w*|d[ée]cid\w*))\b"
)


def declencheur(prompt: str, premiere: bool) -> bool:
    return premiere or bool(_DEMANDE.search(prompt or ""))


def resume_decisions(registre: list[dict]) -> str:
    """Les décisions pour Jay (ouvertes, à recouper) d'abord, puis les cinq dernières tranchées. Bornée (≤ 14 lignes)."""
    if not registre:
        return "Registre des décisions : introuvable ou vide (rien n'est dit de ce qui est tranché ; ne le devine pas)."
    pour_jay = sorted((x for x in dec.ouvertes(registre) if x.get("qui") == "jay"), key=lambda x: str(x["id"]))
    tranchees = sorted((x for x in registre if x.get("statut") == "tranchee"), key=lambda x: (str(x.get("date")), str(x["id"])), reverse=True)[:5]
    lignes = ["À trancher par Jay (seules questions légitimes pour lui) :"]
    lignes += [f"- {x['id']} [{x['statut']}] {x['sujet']}" for x in pour_jay[:6]] or ["- rien d'ouvert"]
    lignes.append("Tranchées récemment (ne les repose pas) :")
    lignes += [f"- {x['id']} : {str(x.get('reponse') or '')[:100]}" for x in tranchees]
    return "\n".join(lignes)


def _etat_du_depot(racine: Path) -> str:
    script = racine / "scripts" / "etat.py"
    if not script.is_file():
        return ""
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=25,
                           stdin=subprocess.DEVNULL, cwd=racine)
    except (OSError, subprocess.SubprocessError):
        return ""
    return "\n".join(r.stdout.splitlines()[:MAX_LIGNES_ETAT]) if r.returncode == 0 else ""


def main() -> None:
    try:
        _, data = read_hook_input()
        session = str(data.get("session_id") or "") or None
        premiere = not read_state(STATE_NAME, session_id=session).get("fait")
        if not declencheur(str(data.get("prompt") or ""), premiere):
            sys.exit(0)
        write_state(STATE_NAME, {"fait": True}, session_id=session)
        morceaux = ["[ÉTAT CALCULÉ PAR LE CODE — à citer tel quel, jamais à refaire de mémoire]", resume_decisions(dec.charger())]
        etat = _etat_du_depot(find_repo_root())
        if etat:
            morceaux.append(etat)
        sys.stdout.write("\n".join(morceaux) + "\n")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 — never break Jay's prompt
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
