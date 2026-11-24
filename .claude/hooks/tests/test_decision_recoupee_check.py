"""quality/decision-recoupee-check.py — Stop: ne pas présenter à Jay comme « ouverte » une décision sans l'avoir recoupée.

Reproche de Jay (2026-11-24, deux fois dans la journée): « La plupart de ces questions, j'y ai déjà répondu. » J'avais repris la
liste « décisions à trancher » de la carte (un instantané du 19/11) sans la comparer à la reprise du 20/11, à la doctrine ni
à la mémoire. Famille: affirmer depuis UNE source, sans la recouper avec celles qui disent la suite. Le garde ne juge pas le
contenu : il constate qu'aucune lecture d'une source de décisions n'a eu lieu dans le tour qui présente des décisions ouvertes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "decision-recoupee-check.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
_spec = importlib.util.spec_from_file_location("decision_recoupee_check", HOOK)
drc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drc)

LISTE = "Voici tes décisions en attente : Q1, le mot pour Takumi ; Q4, les garde-fous qui refusent."


def test_une_liste_de_decisions_ouvertes_sans_recoupement_est_signalee():
    assert drc.presente_des_decisions_ouvertes(LISTE)
    assert drc.presente_des_decisions_ouvertes("Il reste deux points à trancher par toi.")
    assert drc.presente_des_decisions_ouvertes("Question Q3 : où écrire le libre arbitre ?")


def test_une_reponse_sans_decision_ouverte_n_est_pas_signalee():
    assert not drc.presente_des_decisions_ouvertes("Fait et vérifié : 12 tests verts.")
    assert not drc.presente_des_decisions_ouvertes("Tu as tranché le 20/11 : maître expert.")


def test_une_citation_ou_un_bloc_de_code_ne_compte_pas():
    assert not drc.presente_des_decisions_ouvertes("Le mot « à trancher » figure dans la carte.")
    assert not drc.presente_des_decisions_ouvertes("```\nQ1 à trancher\n```\nFait.")


class _Run:
    def __init__(self, name="Read", path="", command=""):
        self.name, self.path, self.command = name, path, command


def test_lire_la_reprise_la_doctrine_ou_la_memoire_vaut_recoupement():
    assert drc.a_recoupe([_Run(path="D:/Shinzo/02-Projets/Kata/Reprises/Kata-Reprise-Methodologie.md")])
    assert drc.a_recoupe([_Run(path="D:/Kata/docs/Doctrine-2026-10-25.md")])
    assert drc.a_recoupe([_Run(name="Bash", command="grep -rn Décisions D:/Shinzo/02-Projets/Kata.md")])
    assert drc.a_recoupe([_Run(path="D:/Shinzo/05-Memoire/feedback-ne-pas-reposer-une-question-deja-renvoyee.md")])


def test_lire_un_fichier_sans_rapport_n_est_pas_un_recoupement():
    assert not drc.a_recoupe([_Run(path="D:/Kata/.claude/hooks/lib/common.py")])
    assert not drc.a_recoupe([])


def _depot(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _stop(depot: Path, reply: str, session: str = "s1"):
    return subprocess.run([sys.executable, str(HOOK)], capture_output=True, timeout=20, cwd=depot,
                          input=json.dumps({"hook_event_name": "Stop", "session_id": session, "last_assistant_message": reply,
                                            "transcript_path": ""}).encode("utf-8"))


def test_le_garde_laisse_un_rappel_il_ne_refuse_pas(tmp_path):
    from session_state import read_state
    depot = _depot(tmp_path)
    r = _stop(depot, LISTE)
    assert r.returncode == 0 and b"RAPPEL (tour suivant" in r.stderr
    assert read_state("rappel-decisions", session_id="s1", repo_root=depot).get("pending") is True


def test_le_garde_se_tait_sur_une_reponse_ordinaire(tmp_path):
    r = _stop(_depot(tmp_path), "Fait et vérifié.")
    assert r.returncode == 0 and b"RAPPEL" not in r.stderr


def test_une_entree_illisible_ne_casse_rien(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK)], input=b"pas du json", capture_output=True, timeout=20, cwd=_depot(tmp_path))
    assert r.returncode == 0


def test_le_message_dit_quoi_faire_sans_demander_de_reecrire():
    assert "recoupe" in drc.MESSAGE.lower() and "réécris" not in drc.MESSAGE.lower()


def test_des_identifiants_du_registre_se_jugent_par_le_registre(tmp_path):
    from session_state import read_state
    import os
    depot = _depot(tmp_path)
    shinzo = tmp_path / "Shinzo"
    (shinzo / "02-Projets").mkdir(parents=True)
    (shinzo / "02-Projets" / "_Decisions.json").write_text(json.dumps({"decisions": [
        {"id": "D-2026-11-20-close", "sujet": "x", "qui": "jay", "statut": "tranchee", "reponse": "Oui.", "date": "2026-11-20", "source": "a"},
        {"id": "D-2026-11-24-ouverte", "sujet": "y", "qui": "jay", "statut": "ouverte", "reponse": "", "date": "2026-11-24", "source": "a"}]}), encoding="utf-8")
    env = {**os.environ, "SHINZO_DIR": str(shinzo)}

    def lancer(reply, session):
        return subprocess.run([sys.executable, str(HOOK)], capture_output=True, timeout=20, cwd=depot, env=env,
                              input=json.dumps({"hook_event_name": "Stop", "session_id": session, "last_assistant_message": reply, "transcript_path": ""}).encode())

    assert lancer("Tes décisions à trancher : D-2026-11-20-close.", "sa").returncode == 0
    etat = read_state("rappel-decisions", session_id="sa", repo_root=depot)
    assert etat.get("pending") is True and "D-2026-11-20-close" in etat.get("message", "")
    lancer("Tes décisions à trancher : D-2026-11-24-ouverte.", "sb")
    assert not read_state("rappel-decisions", session_id="sb", repo_root=depot).get("pending"), "une décision ouverte du registre est une vraie question"


def test_un_trimestre_n_est_pas_une_question_ouverte():
    """Relecture indépendante du 2026-11-24 : « prévu au Q1 2027 » était lu comme la question Q1."""
    assert not drc.presente_des_decisions_ouvertes("La sortie est prévue au Q1 2027.")
