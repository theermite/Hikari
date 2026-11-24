# KATA-ONLY
"""scripts/etat.py — l'état du chantier est CALCULÉ par le code, jamais écrit de mémoire.

Jay 2026-11-24: trois fois dans la journée j'ai affirmé un état sans le mesurer (« non fusionné » alors que c'était fusionné, un
nombre de gardes de tête, une liste de décisions périmée). Ici: mêmes entrées, même sortie; la propagation se juge sur le
CONTENU des fichiers (pas sur le compte rendu d'un script), les branches sur git, les décisions sur le registre.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "etat.py"
_spec = importlib.util.spec_from_file_location("etat", SCRIPT)
etat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(etat)

SONDE = ".claude/hooks/lib/common.py"


def _ecrire(racine: Path, nom: str, contenu: bytes) -> None:
    f = racine / nom
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(contenu)


def test_la_fin_de_ligne_ne_change_pas_l_empreinte(tmp_path):
    _ecrire(tmp_path, "a.py", b"x = 1\r\ny = 2\r\n")
    _ecrire(tmp_path, "b.py", b"x = 1\ny = 2\n")
    assert etat.empreinte(tmp_path / "a.py") == etat.empreinte(tmp_path / "b.py") is not None


def test_un_fichier_absent_n_a_pas_d_empreinte(tmp_path):
    assert etat.empreinte(tmp_path / "rien.py") is None


def test_propagation_dit_a_jour_en_retard_ou_absent(tmp_path):
    source, projets = tmp_path / "Kata", tmp_path
    _ecrire(source, SONDE, b"v2\n")
    _ecrire(projets / "Bon", SONDE, b"v2\r\n")
    _ecrire(projets / "Vieux", SONDE, b"v1\n")
    (projets / "Vide" / ".claude").mkdir(parents=True)
    r = etat.propagation(source, projets, ["Bon", "Vieux", "Vide", "Introuvable"], sondes=(SONDE,))
    assert r["Bon"]["statut"] == "a_jour"
    assert r["Vieux"] == {"statut": "en_retard", "ecarts": [SONDE]}
    assert r["Vide"]["statut"] == "en_retard" and r["Vide"]["ecarts"] == [SONDE]
    assert r["Introuvable"]["statut"] == "absent"


def test_une_sonde_absente_de_la_source_est_ignoree(tmp_path):
    source, projets = tmp_path / "Kata", tmp_path
    _ecrire(source, SONDE, b"v2\n")
    _ecrire(projets / "Bon", SONDE, b"v2\n")
    assert etat.propagation(source, projets, ["Bon"], sondes=(SONDE, ".claude/hooks/lib/n_existe_pas.py"))["Bon"]["statut"] == "a_jour"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True, capture_output=True)


def _depot(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _ecrire(tmp_path, "f.txt", b"1")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-q", "-m", "un")
    return tmp_path


def test_branches_dit_fusionnee_ou_non_et_ignore_main(tmp_path):
    depot = _depot(tmp_path)
    _git(depot, "branch", "fusionnee")
    _git(depot, "checkout", "-q", "-b", "travail")
    _ecrire(depot, "g.txt", b"2")
    _git(depot, "add", "g.txt")
    _git(depot, "commit", "-q", "-m", "deux")
    _git(depot, "checkout", "-q", "main")
    r = etat.branches(depot)
    assert r == [{"nom": "fusionnee", "fusionnee": True}, {"nom": "travail", "fusionnee": False}]


def test_branches_d_un_dossier_sans_git_est_vide(tmp_path):
    assert etat.branches(tmp_path) == []


def _decision(ident: str, statut: str, qui: str = "jay") -> dict:
    return {"id": ident, "sujet": f"Sujet {ident}", "qui": qui, "statut": statut}


def test_le_rendu_est_deterministe_et_dit_chaque_fait(tmp_path):
    prop = {"B": {"statut": "en_retard", "ecarts": [SONDE]}, "A": {"statut": "a_jour", "ecarts": []}}
    br = [{"nom": "x", "fusionnee": False}]
    dec = [_decision("D-2026-11-24-b", "ouverte"), _decision("D-2026-11-24-a", "a_recouper")]
    texte = etat.rendu(prop, br, dec)
    assert texte == etat.rendu(prop, br, dec)
    assert "à jour : A" in texte and "EN RETARD (1) : B" in texte and "x : NON fusionnée" in texte
    assert texte.index("D-2026-11-24-a") < texte.index("D-2026-11-24-b"), "tri par identifiant"
    assert "1 sur 2" in texte or "à jour : 1" in texte


def test_une_decision_de_takumi_n_est_jamais_une_question_pour_jay(tmp_path):
    texte = etat.rendu({}, [], [_decision("D-2026-11-24-c", "ouverte", qui="takumi")])
    pour_jay = texte.split("À trancher par Jay")[1].split("À vérifier par Takumi")[0]
    assert "D-2026-11-24-c" not in pour_jay and "D-2026-11-24-c" in texte


def test_serveur_compare_le_contenu_lu_par_ssh(tmp_path):
    source = tmp_path / "Kata"
    sonde = ".claude/rules/07-Securite.md"
    _ecrire(source, sonde, b"regle\n")
    bon = etat.empreinte(source / sonde)
    lu = f"Boken {sonde} {bon}\nKobo {sonde} {'0' * 64}\n"
    r = etat.serveur(source, {"Boken": "/x/Boken", "Kobo": "/x/Kobo", "Muet": "/x/Muet"}, executer=lambda c: lu, sondes=(sonde,))
    assert r["Boken"]["statut"] == "a_jour"
    assert r["Kobo"] == {"statut": "en_retard", "ecarts": [sonde]}
    assert r["Muet"]["statut"] == "en_retard", "un dépôt que le serveur ne rend pas n'est jamais déclaré à jour"


def test_une_connexion_qui_echoue_dit_inconnu_et_ne_declare_personne_a_jour(tmp_path):
    source = tmp_path / "Kata"
    sonde = ".claude/rules/07-Securite.md"
    _ecrire(source, sonde, b"regle\n")
    assert etat.serveur(source, {"Boken": "/x/Boken"}, executer=lambda c: "", sondes=(sonde,))["Boken"]["statut"] == "inconnu"


def test_les_depots_qui_ont_les_memes_ecarts_sont_regroupes(tmp_path):
    prop = {f"P{i}": {"statut": "en_retard", "ecarts": [SONDE]} for i in range(5)}
    texte = etat.rendu(prop, [], [])
    assert texte.count("EN RETARD") == 1 and "(5)" in texte


def test_une_source_absente_dit_inconnu_jamais_a_jour(tmp_path):
    r = etat.propagation(tmp_path / "Kata", tmp_path, ["Shizen"], sondes=(SONDE,))
    assert r["Shizen"]["statut"] == "inconnu"
    assert "INCONNU" in etat.rendu(r, [], [])


def test_main_non_pousse_est_signale(tmp_path):
    depot = _depot(tmp_path)
    assert etat.non_pousses(depot) is None, "sans origin, rien a dire"
    assert "non envoy" in etat.rendu({}, [{"nom": "x", "fusionnee": True}], [], en_avance=2)
    assert "non envoy" not in etat.rendu({}, [], [], en_avance=0)
