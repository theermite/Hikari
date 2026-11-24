"""Les tests de garde-fous provoquent des refus à la chaîne: aucun ne doit écrire dans le vrai journal de frictions.

Deuxième rôle (relecture indépendante du 2026-11-24, quatrième retour de la même famille) : `.claude/hooks/tests/` voyage dans
chaque dépôt receveur, `scripts/` non. Un test qui lit `scripts/…` casse la collecte chez le receveur, et la propagation
refuse le dépôt. Un test de ce genre porte la marque `# KATA-ONLY` dans ses 30 premières lignes : il n'est PAS collecté là où
`scripts/propagate-methodology.py` n'existe pas. `test_kata_only_marque.py` échoue dans Kata si un test lit `scripts/` sans la marque.
"""

import os
from pathlib import Path

os.environ.setdefault("FRICTION_LOG_OFF", "1")

MARQUE = "# KATA-ONLY"
DANS_KATA = (Path(__file__).resolve().parents[3] / "scripts" / "propagate-methodology.py").is_file()


def est_kata_seulement(chemin: Path) -> bool:
    try:
        tete = chemin.read_text(encoding="utf-8", errors="replace").splitlines()[:30]
    except OSError:
        return False
    return any(ligne.strip() == MARQUE for ligne in tete)


def pytest_ignore_collect(collection_path, config):
    if not DANS_KATA and collection_path.suffix == ".py" and est_kata_seulement(collection_path):
        return True
    return None
