"""quality/plan-incomplet-check.py — « j'annonce sans faire » lu sur un FAIT: la liste de tâches du tour.

Jay 2026-11-24: la méthode doit anticiper, pas deviner. Le garde lexical (`announce-without-doing-check`) cherche des mots du futur.
Ici, le fait est dans le journal: la liste de tâches tenue pendant le tour a encore des étapes non terminées et le tour finit sans
`wrap_up`. Mêmes appels d'outil, même verdict. Le garde ne refuse pas (rappel au tour suivant): la réponse est déjà lue.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_tour  # noqa: E402
from transcript_builder import Journal  # noqa: E402

HOOK = Path(__file__).resolve().parents[1] / "quality" / "plan-incomplet-check.py"
PLAN = "mcp__ccd_turn__update_plan"
FIN = "mcp__ccd_turn__wrap_up"


def _items(*statuts: str) -> dict:
    return {"items": [{"content": f"étape {i + 1}", "status": s} for i, s in enumerate(statuts)], "scope": "continuation"}


def _plan(journal: Journal, tmp_path: Path) -> str:
    return journal.write_to(tmp_path / "t.jsonl")


def test_une_liste_posee_avec_des_etapes_ouvertes_est_incomplete(tmp_path):
    j = Journal().user("Fais X").tool(PLAN, _items("in_progress", "pending", "pending"))
    etat = plan_tour.plan_du_tour(_plan(j, tmp_path))
    assert etat.a_une_liste and etat.restantes == ["étape 1", "étape 2", "étape 3"] and not etat.cloture


def test_advance_termine_l_etape_en_cours_et_ouvre_la_suivante(tmp_path):
    j = Journal().user("Fais X").tool(PLAN, _items("in_progress", "pending", "pending")).tool(PLAN, {"advance": True})
    assert plan_tour.plan_du_tour(_plan(j, tmp_path)).restantes == ["étape 2", "étape 3"]


def test_done_et_start_sont_comptes_en_numeros_a_partir_de_un(tmp_path):
    j = Journal().user("Fais X").tool(PLAN, _items("in_progress", "pending", "pending")).tool(PLAN, {"done": [1, 3], "start": 2})
    assert plan_tour.plan_du_tour(_plan(j, tmp_path)).restantes == ["étape 2"]


def test_toutes_les_etapes_terminees_ne_laissent_rien(tmp_path):
    j = Journal().user("Fais X").tool(PLAN, _items("completed", "completed"))
    assert plan_tour.plan_du_tour(_plan(j, tmp_path)).restantes == []


def test_wrap_up_cloture_le_tour(tmp_path):
    j = Journal().user("Fais X").tool(PLAN, _items("in_progress", "pending")).tool(FIN, {"recap": "Fait."})
    assert plan_tour.plan_du_tour(_plan(j, tmp_path)).cloture


def test_une_liste_d_un_tour_precedent_n_est_pas_celle_de_ce_tour(tmp_path):
    j = Journal().user("Premier").tool(PLAN, _items("in_progress", "pending")).user("Deuxième").say("Réponse courte.")
    assert not plan_tour.plan_du_tour(_plan(j, tmp_path)).a_une_liste


def test_un_journal_absent_ou_illisible_ne_dit_rien(tmp_path):
    assert not plan_tour.plan_du_tour("").a_une_liste
    assert not plan_tour.plan_du_tour(str(tmp_path / "nope.jsonl")).a_une_liste


def test_le_verdict_se_tait_si_la_liste_est_finie_cloturee_ou_si_le_tour_demande_a_jay():
    fini = plan_tour.PlanTour(True, [], False)
    ouvert = plan_tour.PlanTour(True, ["étape 2"], False)
    ferme = plan_tour.PlanTour(True, ["étape 2"], True)
    sans = plan_tour.PlanTour(False, [], False)
    assert not plan_tour.tour_incomplet(fini, "Fait.")
    assert not plan_tour.tour_incomplet(ferme, "Fait.")
    assert not plan_tour.tour_incomplet(sans, "Fait.")
    assert plan_tour.tour_incomplet(ouvert, "Fait. Je continue après.")
    assert not plan_tour.tour_incomplet(ouvert, "Tu choisis laquelle ?"), "une question à Jay est un arrêt légitime"
    assert not plan_tour.tour_incomplet(ouvert, "[ARRET] plan : deux voies possibles ici\nLaquelle ?")


def _stop(depot: Path, journal_path: str, reply: str, session: str):
    return subprocess.run([sys.executable, str(HOOK)], capture_output=True, timeout=30, cwd=depot,
                          input=json.dumps({"hook_event_name": "Stop", "session_id": session, "last_assistant_message": reply,
                                            "transcript_path": journal_path}).encode())


def test_le_hook_laisse_un_rappel_avec_les_etapes_restantes(tmp_path):
    from session_state import read_state
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    chemin = _plan(Journal().user("Fais X").tool(PLAN, _items("in_progress", "pending")), tmp_path)
    r = _stop(tmp_path, chemin, "Première étape faite. Je passe à la suite.", "sp")
    assert r.returncode == 0 and b"RAPPEL (tour suivant" in r.stderr
    message = read_state("rappel-plan", session_id="sp", repo_root=tmp_path).get("message", "")
    assert "étape 1" in message and "étape 2" in message and "réécris" not in message.lower()


def test_le_hook_se_tait_sans_liste_de_taches(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    chemin = _plan(Journal().user("Bonjour").say("Bonjour."), tmp_path)
    r = _stop(tmp_path, chemin, "Bonjour.", "sq")
    assert r.returncode == 0 and b"RAPPEL" not in r.stderr


def test_une_entree_illisible_ne_casse_rien(tmp_path):
    assert subprocess.run([sys.executable, str(HOOK)], input=b"pas du json", capture_output=True, timeout=30, cwd=tmp_path).returncode == 0
