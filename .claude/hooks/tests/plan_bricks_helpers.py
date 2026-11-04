"""Aides communes des tests de plan_bricks (chargement du module, plans d'essai, lecture).

lib/plan_bricks.py — la liste fermée des briques du contrat, calculée depuis la feuille de route du PET.

Besoin (essai à blanc sur le plan réel de Dogu, 2026-11-04) : la liste `briques` d'un contrat en mode projet était
recopiée à la main ; une brique oubliée n'était vue par personne. Cet outil la CALCULE et signale les écarts.

Lecture FERMÉE (même méthode que run_journal.py, après trois relectures en échec sur de la lecture ouverte) : tout
ce qui ressemble à une brique et n'est pas lu proprement est un PROBLÈME rapporté, jamais ignoré ; en cas de problème
aucune liste n'est produite (sortie 1). La feuille de route = les tableaux dont l'en-tête a une colonne `ID` et une
colonne `Statut` ; les autres tableaux du PET (ordre, séances, priorités) ne sont pas la feuille de route.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))
_spec = importlib.util.spec_from_file_location("plan_bricks", LIB / "plan_bricks.py")
pb = importlib.util.module_from_spec(_spec)
sys.modules["plan_bricks"] = pb
_spec.loader.exec_module(pb)

BASE_CONTRACT = {
    "scope": ["B09b", "B11"], "deploy": "jamais", "cdc_version": "0.6.0", "pet_version": "0.12.0",
    "budget": {"cout_max_usd": 40, "tokens_max": 8000000, "duree_max_h": 10, "alerte_pct": 80, "arret_pct": 100},
    "livrable": [{"id": "L1", "preuve": "parcours", "verification": "script_navigateur"}],
    "checkpoints": [{"id": "C1", "apres": "B09b", "jay_verifie": "x", "bloquant": True}],
}


def contract(**kw):
    return {**BASE_CONTRACT, "mode": "lot", **kw}


TEMPLATE_PET = """# PET

## 6. Roadmap — Bricks

| ID | Brick | CDC ref | Briques réutilisées | Statut | Coverage | Veille requise | Commit | Date |
|----|-------|---------|---------------------|--------|----------|----------------|--------|------|
| B-001 | Bootstrap | F-000 | `Skeleton` | 🟢 Done | — | Stack | abc | 2026-11-01 |
| B-002 | Schéma DB | F-001 | — | 🟡 In progress | 80% | PG | — | — |
| B-003 | Auth | F-002 | `Input` | ⬜ Pending | 95% | Argon2 | — | — |

## 7. Détail par brick

### B-001 — Bootstrap
### B-002 — Schéma DB
### B-003 — Auth
"""

DOGU_LIKE = """# PET

## 6. Roadmap

| Ordre | Brique | Ce qu'elle apporte |
|---|---|---|
| 1 | B02b | Le disjoncteur |
| 2 | B03 | Pi parle à DeepSeek |

### Phase 0
| ID | Brique | CDC | Niveau | Dépend de | Statut |
|---|---|---|---|---|---|
| B00 | Dépôt | — | Tooling | — | 🟢 |
| B02b | Disjoncteur | F-002 | Critical | B00 | 🟢 en service (statut remis le 2026-10-21) |
| B03 | Pi | F-001 | Sensitive | B00 | 🟢 |

### Phase 2
| ID | Brique | CDC | Niveau | Dépend de | Statut |
|---|---|---|---|---|---|
| B09a | Coquille | F-007 | Standard | B00 | 🟢 2026-10-31 — voie crochet |
| B09b | Palette | F-034 | Standard | B09a | ⬜ |
| B10 | Conversation | F-001 | Standard | B09a | 🟢 |
| B11 | Jauges | F-004 | Standard | B10 | 🟡 |

## 7. Détail par brique

#### B00 — Dépôt
#### B02b — Disjoncteur
#### B09a — Coquille
#### B09b — Palette
#### B10 — Conversation
#### B11 — Jauges
"""


def _rr(text, **kw):
    return pb.read_roadmap(text, **{"libre": True, **kw})


def read(text):
    return _rr(text)



def _cli(tmp_path, text, *extra):
    pet = tmp_path / "PET.md"
    pet.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, str(LIB / "plan_bricks.py"), str(pet), "--numerotation-libre", *extra], capture_output=True, text=True)


ABSENT = DOGU_LIKE + "#### B38 — Appliquer\n#### B39 — Modèle local\n"



def _problems(text, **kw):
    return _rr(text, **kw).problems


def _remaining(text):
    r = _rr(text)
    return r.problems, pb.remaining(r)


def _hidden(block: str) -> list:
    return read(DOGU_LIKE + block).problems


def _stray(block):
    return " ".join(read(DOGU_LIKE + block).problems)


GAP_PET = """# PET

## 6. Roadmap

| ID | Brique | Statut |
|---|---|---|
| B11 | a | 🟢 |
| B12 | b | ⬜ |
| B13 | c | ⬜ |
| B15 | d | ⬜ |

#### B11 — a
#### B12 — b
#### B13 — c
#### B15 — d
"""


def _gap(text="", **kw):
    return pb.read_roadmap(GAP_PET + text, **kw)




def in_roadmap(plan: str, block: str) -> str:
    """Put a block inside the roadmap section of a plan (before the detail section), where tables count."""
    return plan.replace("## 7.", block + "\n## 7.", 1)
