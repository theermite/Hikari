"""Les notes globales de Jay remontent — sinon elles dorment.

Ne le 2026-09-07. En rangeant les reserves de propagation j'ai ouvert
`Shinzo/08-Notes/inbox.md` et y ai trouve des idees ecrites par Jay, jamais
traitees : l'ecosysteme deja construit qu'il n'utilise pas, la visibilite des
outils, les outils qui disparaissent dans des tiroirs. `/session-start` lit
quatre fichiers de Shinzo, tous lies a UN projet. Celui-la n'en fait pas partie.

CHOIX DE JAY (2026-09-07) : ces notes remontent dans le depot **Takumi**, « c'est
avec lui que je brainstorm ou fais tout ce qui n'est pas forcement specifique a
un projet, ou qui en touche plusieurs ». Ailleurs, elles seraient du bruit.

MEME FAMILLE QUE LA VEILLE, une fois de plus : le canal existait, son lecteur
manquait. On ne se contente donc pas d'ajouter une ligne a une consigne — une
regle ecrite sans executant reste inerte, c'est la mesure du 2026-09-06.

Ce qui est eprouve ici : ca parle dans Takumi, ca se tait ailleurs, ca ne parle
qu'une fois par changement, et une note absente n'arrete jamais une session.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]

HOOK = RACINE / ".claude/hooks/lifecycle/notes-globales.py"
_spec = importlib.util.spec_from_file_location("notes_globales", HOOK)
notes = importlib.util.module_from_spec(_spec)
sys.modules["notes_globales"] = notes
_spec.loader.exec_module(notes)


def _atelier(tmp_path, contenu="", depot="Takumi"):
    """Un atelier jetable : un depot, et Shinzo en frere."""
    racine = tmp_path / depot
    (racine / ".claude" / "state").mkdir(parents=True)
    inbox = tmp_path / "Shinzo" / "08-Notes" / "inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(contenu, encoding="utf-8")
    return racine


def test_les_notes_remontent_dans_takumi(tmp_path):
    racine = _atelier(tmp_path, "## Concernant l'ecosysteme\nune idee qui traine\n")
    texte = notes.rapport(racine)
    assert "08-Notes/inbox.md" in texte
    assert "Takumi" not in texte or texte  # le chemin suffit, pas de sermon


def test_ailleurs_le_hook_se_tait(tmp_path):
    """Une note globale dans chaque depot serait du bruit — Jay a nomme Takumi."""
    racine = _atelier(tmp_path, "une idee qui traine\n", depot="Kobo")
    assert notes.rapport(racine) == ""


def test_il_ne_parle_qu_une_fois_par_changement(tmp_path):
    racine = _atelier(tmp_path, "une idee qui traine\n")
    assert notes.rapport(racine) != ""
    assert notes.rapport(racine) == "", "repeter a chaque demarrage apprend a ne plus lire"


def test_un_signal_manque_revient_le_lendemain(tmp_path, monkeypatch):
    """Defaut mesure par relecture croisee le 2026-09-07 — l'hypothese de Jay etait juste.

    Le hook ne parlait qu'une fois par CHANGEMENT du texte. Si Jay ferme la
    fenetre sans avoir lu, le signal ne revient JAMAIS tant qu'il n'ecrit pas
    autre chose. Ses notes attendaient deja depuis des semaines : les taire
    definitivement apres une seule ligne serait le meme defaut, en pire.

    Un jour est la bonne maille : assez rare pour ne pas lasser, assez frequent
    pour qu'un oubli ne devienne pas une perte.
    """
    racine = _atelier(tmp_path, "une idee qui traine\n")
    assert notes.rapport(racine) != ""
    assert notes.rapport(racine) == "", "deux fois le meme jour, non"
    monkeypatch.setattr(notes, "aujourdhui", lambda: "2099-01-01")
    assert notes.rapport(racine) != "", "le lendemain, la note non traitee reparle"


def test_le_depot_se_reconnait_malgre_la_casse(tmp_path):
    """Mesure du 2026-09-07 : deux noms reels rendaient le hook muet en silence.

    Windows ne distingue pas la casse. Une comparaison stricte desactivait le
    hook sans le dire — un garde-fou muet ressemble a un garde-fou vert.

    Le cas du worktree a quitte ce test : il reposait sur une hypothese fausse
    (un nom impose par git). Il vit desormais dans
    `test_un_worktree_parle_quel_que_soit_son_nom`, qui en cree un VRAI.
    """
    # Un espace par nom : Windows ne distingue pas `takumi` de `TAKUMI`, et deux
    # ateliers au meme endroit se marcheraient dessus.
    for i, nom in enumerate(("takumi", "TAKUMI")):
        racine = _atelier(tmp_path / f"essai{i}", "une idee qui traine\n", depot=nom)
        assert notes.rapport(racine) != "", nom


def test_un_worktree_parle_quel_que_soit_son_nom(tmp_path):
    """Mon hypothese sur le nommage des worktrees etait fausse — mesuree, 5e tour.

    J'avais ecrit que git nomme ses copies de travail `<depot>-worktree-...`.
    Faux : `git worktree add` prend le nom que l'humain lui donne et n'impose
    RIEN. `Takumi-review-pr42` serait donc reste muet, sans le dire.

    On demande desormais a git, qui sait relier un worktree a son depot
    principal. Ce test cree un vrai worktree, il ne simule pas.
    """
    import subprocess

    principal = tmp_path / "Takumi"
    (principal / ".claude" / "state").mkdir(parents=True)
    inbox = tmp_path / "Shinzo" / "08-Notes" / "inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("une idee qui traine\n", encoding="utf-8")
    lancer = lambda *a: subprocess.run(a, cwd=principal, check=True, capture_output=True)
    lancer("git", "init", "-q", ".")
    (principal / "x.txt").write_text("x", encoding="utf-8")
    lancer("git", "add", "x.txt")
    lancer("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")

    annexe = tmp_path / "NomQueGitNImposePas"
    lancer("git", "worktree", "add", "-q", str(annexe), "-b", "essai")
    (annexe / ".claude" / "state").mkdir(parents=True, exist_ok=True)
    assert notes.rapport(annexe) != "", "un worktree de Takumi doit parler, quel que soit son nom"


def test_un_depot_homonyme_ne_voit_pas_les_notes_privees(tmp_path):
    """Defaut cree par MON correctif precedent, trouve au tour suivant.

    Remplacer la comparaison stricte par un prefixe ouvert faisait parler
    `TakumiTools` ou `Takumi-Docs-Sans-Rapport` — donc AFFICHAIT les notes
    privees de Jay dans un depot sans rapport. Le defaut d'hier taisait un
    signal ; celui-la le divulgue. La liste fermee tranche les deux.
    """
    for i, nom in enumerate(("TakumiTools", "Takumi-Docs-Sans-Rapport", "Kobo")):
        racine = _atelier(tmp_path / f"autre{i}", "une idee privee\n", depot=nom)
        assert notes.rapport(racine) == "", nom


def test_une_note_modifiee_reparle(tmp_path):
    racine = _atelier(tmp_path, "une idee qui traine\n")
    notes.rapport(racine)
    (tmp_path / "Shinzo" / "08-Notes" / "inbox.md").write_text(
        "une idee qui traine\net une deuxieme\n", encoding="utf-8")
    assert notes.rapport(racine) != ""


def test_une_note_vide_ne_dit_rien(tmp_path):
    racine = _atelier(tmp_path, "*(Inbox vide — rien a trier.)*\n")
    assert notes.rapport(racine) == ""


def test_shinzo_absent_n_arrete_jamais_une_session(tmp_path):
    racine = tmp_path / "Takumi"
    (racine / ".claude" / "state").mkdir(parents=True)
    assert notes.rapport(racine) == ""


def test_le_hook_est_cable_a_un_evenement():
    """Un controle que rien n'execute ne garde rien (2026-09-06, trois orphelins)."""
    import json
    reglages = json.loads((RACINE / ".claude/settings.json").read_text(encoding="utf-8"))
    commandes = [
        h.get("command", "")
        for evenement in reglages["hooks"].values()
        for entree in evenement
        for h in entree.get("hooks", [])
    ]
    assert any("notes-globales" in c for c in commandes)
