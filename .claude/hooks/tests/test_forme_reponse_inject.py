"""lifecycle/forme-reponse-inject.py — la taille de la réponse se règle AVANT qu'elle soit écrite, selon la FORME de la question.

Jay 2026-11-24: « Je t'ai posé une question simple et on regarde la taille de ta réponse. » Un oui ou un non reçoit une phrase, pas un
tableau. Le garde de forme existant ne mesure que la longueur des phrases. Ici, c'est la forme du message de Jay qui décide, par un
test déterministe (mêmes mots, même verdict), et le code dépose la consigne dans le contexte avant que Takumi réponde.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "forme-reponse-inject.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
_spec = importlib.util.spec_from_file_location("forme_reponse_inject", HOOK)
fr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr)

FERMEES = [
    "Ok, donc concrètement, la différence qui est là, c'est la différence de tout ce que nous n'avons pas encore propagé, c'est bien ça ?",
    "Est-ce que c'est normal que la session de Shinzo me dise qu'elle a du retard sur la méthodologie ?",
    "As-tu relancé la suite de tests ?",
    "Tu peux confirmer que c'est fusionné ?",
    "C'est fusionné ?",
    "Peux-tu me dire si la branche est poussée ?",
    "Est-ce que ça peut se reproduire ?",
]
OUVERTES = [
    "Fais-moi un point sur l'état d'avancement de l'alignement de la méthodologie.",
    "Pourquoi la suite de tests a échoué ?",
    "Construis la deuxième brique.",
    "Dis-moi ce qu'il reste à faire.",
    "Explique-moi comment fonctionne le registre des décisions ?",
    "Montre-moi la liste des dépôts en retard ?",
    "Quels sont les dépôts en retard ?",
    "Oui, fusionne et pousse",
    "Bonjour",
]


def test_une_question_fermee_courte_est_reconnue():
    for q in FERMEES:
        assert fr.est_question_fermee(q), q


def test_une_demande_ouverte_ou_un_ordre_ne_l_est_pas():
    for q in OUVERTES:
        assert not fr.est_question_fermee(q), q


def test_un_long_message_n_est_jamais_une_question_fermee():
    assert not fr.est_question_fermee("C'est bien ça ? " + "Voici le contexte détaillé de ma demande. " * 12)


def test_un_bloc_de_code_ou_plusieurs_questions_ne_sont_pas_une_question_fermee():
    assert not fr.est_question_fermee("C'est bien ça ?\n```\ncode\n```")
    assert not fr.est_question_fermee("C'est fusionné ? Et la suite ? Et le serveur ? Et les dépôts ?")


def test_le_verdict_est_deterministe():
    assert [fr.est_question_fermee(q) for q in FERMEES + OUVERTES] == [fr.est_question_fermee(q) for q in FERMEES + OUVERTES]


def _lancer(prompt: str, tmp_path: Path):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"session_id": "s", "prompt": prompt}).encode(),
                          capture_output=True, timeout=30, cwd=tmp_path)


def test_le_hook_depose_la_consigne_sur_une_question_fermee_et_se_tait_sinon(tmp_path):
    r = _lancer("C'est fusionné ?", tmp_path)
    assert r.returncode == 0 and b"FORME" in r.stdout and "une ou deux phrases".encode() in r.stdout
    assert _lancer("Fais-moi un point sur l'état d'avancement.", tmp_path).stdout == b""


def test_une_entree_illisible_ne_casse_rien(tmp_path):
    assert subprocess.run([sys.executable, str(HOOK)], input=b"pas du json", capture_output=True, timeout=30, cwd=tmp_path).returncode == 0


def test_une_question_ouverte_en_c_est_ou_une_demande_d_action_n_est_pas_fermee():
    """Relecture indépendante du 2026-11-24 : ces trois messages recevaient la consigne « réponds oui ou non »."""
    for msg in ("C'est quoi le problème avec Boken ?", "C'est où le fichier de config ?", "Tu peux m'aider à refaire le menu ?"):
        assert not fr.est_question_fermee(msg), msg
