#!/usr/bin/env python3
"""La fiche du projet suit le code — PreToolUse(Write|Edit) sur un rapport de séance. AVERTIT, ne bloque pas.

Quand on écrit le rapport de fin de séance, la fiche du projet (`Shinzo/02-Projets/<projet>.md`) doit porter une
date au moins égale à celle du dernier commit de code. Sinon : rappel, une fois par séance, avec les deux dates.

Pourquoi (Jay, 2026-11-01) : mesure du jour sur 32 projets — 21 fiches à jour, 8 en retard, 3 absentes. Le code
forçait la lecture de la fiche, rien ne forçait sa mise à jour. Jay ne doit pas être la mémoire de secours.

Limite écrite : la date lue est celle de l'étiquette « Dernière MAJ » de l'en-tête de la fiche ; une fiche qui
change sans toucher cette date reste vue en retard. Ne bloque pas : un correctif sans effet sur la fiche existe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    canonical_project_name,
    format_warn,
    get_file_path,
    pass_through,
    read_hook_input,
    warn,
)
from fiche_fraicheur import PROJETS_DIR, SHINZO_DIR, chemin_fiche, etat_fiche  # noqa: E402
from session_state import mark_once  # noqa: E402

_RAPPORT_RE = re.compile(r"(?:^|\\)docs\\Sessions\\Session-[^\\]*\.md$", re.I)


def est_rapport(chemin: str) -> bool:
    return bool(chemin) and bool(_RAPPORT_RE.search(chemin.replace("/", "\\")))


def message(projet: str, projets: Path = PROJETS_DIR, shinzo: Path = SHINZO_DIR) -> str | None:
    """Le rappel à donner, ou None quand la fiche est à jour ou le projet inconnu."""
    e = etat_fiche(projet, projets, shinzo, seuil=0)
    fiche = chemin_fiche(projet, shinzo)
    if e.etat == "absente":
        return f"la fiche du projet {projet} n'existe pas ({fiche}) alors que le code a un historique : à créer avant la fin de séance"
    if e.etat == "sans_date":
        return f"la fiche {fiche} ne porte pas d'étiquette « Dernière MAJ : AAAA-MM-JJ » : on ne peut pas dire si elle suit le code"
    if e.etat == "en_retard":
        return (f"le code de {projet} a bougé le {e.date_code} et la fiche {fiche} date du {e.date_fiche} "
                f"({e.retard} jour(s) de retard) : mets-la à jour (état, décisions, prochaines étapes, date)")
    return None


def main() -> None:
    _, data = read_hook_input()
    if not est_rapport(get_file_path(data)):
        pass_through()
    rappel = message(canonical_project_name())
    if rappel and mark_once("fiche-fraicheur", "rappel", session_id=data.get("session_id", "") or "no-session"):
        warn(format_warn(
            "Fiche de projet en retard sur le code",
            rappel,
            reference="Shinzo/02-Projets/_Index.md (la fiche suit le code, Jay 2026-11-01)",
        ))
    pass_through()


if __name__ == "__main__":
    main()
