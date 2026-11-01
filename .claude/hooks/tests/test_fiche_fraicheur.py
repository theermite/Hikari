"""lib/fiche_fraicheur.py et quality/fiche-fraicheur-check.py — la fiche de projet suit le code.

Origine : Jay, 2026-11-01. « Sans fiches à jour, l'autonomie fera des bêtises, et je ne dois jamais être la
mémoire de secours. » Mesure du jour : 21 fiches à jour, 8 en retard, 3 absentes. Le code forçait la
LECTURE de la fiche ; rien ne forçait sa mise à jour.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fiche_fraicheur as ff  # noqa: E402

HOOK = Path(__file__).resolve().parents[1] / "quality" / "fiche-fraicheur-check.py"
_spec = importlib.util.spec_from_file_location("fiche_fraicheur_check", HOOK)
garde = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(garde)


def _depot(dossier: Path, commits: list[tuple[str, str]]) -> None:
    """Un dépôt dont chaque commit porte la date (AAAA-MM-JJ) et le sujet donnés."""
    dossier.mkdir(parents=True)
    base = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=dossier, check=True, env=base)
    for i, (jour, sujet) in enumerate(commits):
        (dossier / f"f{i}.txt").write_text(str(i), encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=dossier, check=True, env=base)
        quand = f"{jour}T12:00:00+00:00"
        subprocess.run(["git", "commit", "-q", "-m", sujet], cwd=dossier, check=True,
                       env={**base, "GIT_AUTHOR_DATE": quand, "GIT_COMMITTER_DATE": quand})


def _fiche(shinzo: Path, nom: str, texte: str) -> None:
    (shinzo / "02-Projets").mkdir(parents=True, exist_ok=True)
    (shinzo / "02-Projets" / f"{nom}.md").write_text(texte, encoding="utf-8")


# --- lire la date de la fiche -------------------------------------------------


def test_reads_the_date_after_the_label_in_every_spelling_used():
    assert ff.date_fiche("# P\n**Derniere MAJ** : 2026-10-30 (suite)") == date(2026, 10, 30)
    assert ff.date_fiche("**Dernière mise à jour** : 2026-10-28") == date(2026, 10, 28)
    assert ff.date_fiche("**Mise à jour** : 2026-08-23 (focus)") == date(2026, 8, 23)
    assert ff.date_fiche("> **Dernière MAJ** : 2026-09-02") == date(2026, 9, 2)


def test_takes_the_first_date_when_the_line_lists_several():
    assert ff.date_fiche("**Derniere MAJ** : 2026-11-01 Dogu · 2026-10-29 Dogu") == date(2026, 11, 1)


def test_a_date_that_is_not_the_update_date_is_ignored():
    # « Créé 2026-01-01 » n'est pas une mise à jour; sans étiquette de mise à jour, pas de date.
    assert ff.date_fiche("**Créé** : 2026-01-01\n**Statut** : actif") is None


def test_a_label_quoted_in_prose_is_not_the_label():
    # La structure qui porte le fait est une ligne qui OUVRE sur l'étiquette, pas le mot dans une phrase.
    assert ff.date_fiche("Voir la Derniere MAJ : 2026-10-30 du dépôt voisin.") is None


def test_an_impossible_date_is_not_a_date():
    assert ff.date_fiche("**Derniere MAJ** : 2026-13-45") is None


# --- la date du code ----------------------------------------------------------


def test_code_date_ignores_methodology_sync_and_session_reports(tmp_path):
    depot = tmp_path / "P"
    _depot(depot, [("2026-10-01", "feat: x"), ("2026-10-20", "chore(methodo): sync MNK-GoRin"),
                   ("2026-10-25", "docs(session): rapport")])
    assert ff.date_code(depot) == date(2026, 10, 1)


def test_code_date_is_none_without_repo(tmp_path):
    assert ff.date_code(tmp_path / "absent") is None


# --- l'état ---------------------------------------------------------------------


def test_states(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-10-30", "feat: a")])
    _fiche(shinzo, "A", "**Derniere MAJ** : 2026-10-30")
    _depot(projets / "B", [("2026-10-30", "feat: b")])
    _fiche(shinzo, "B", "**Derniere MAJ** : 2026-10-01")
    _depot(projets / "C", [("2026-10-30", "feat: c")])
    _depot(projets / "D", [("2026-10-30", "feat: d")])
    _fiche(shinzo, "D", "# D\npas de date")
    etats = {n: ff.etat_fiche(n, projets, shinzo) for n in "ABCD"}
    assert etats["A"].etat == "a_jour" and etats["A"].retard == 0
    assert etats["B"].etat == "en_retard" and etats["B"].retard == 29
    assert etats["C"].etat == "absente"
    assert etats["D"].etat == "sans_date"
    assert ff.etat_fiche("Z", projets, shinzo).etat == "sans_depot"


def test_threshold_is_a_strict_greater_than(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-10-15", "feat: a")])
    _fiche(shinzo, "A", "**Derniere MAJ** : 2026-10-01")  # 14 jours exactement
    assert ff.etat_fiche("A", projets, shinzo, seuil=14).etat == "a_jour"
    assert ff.etat_fiche("A", projets, shinzo, seuil=13).etat == "en_retard"


def test_code_older_than_the_fiche_is_up_to_date(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-09-01", "feat: a")])
    _fiche(shinzo, "A", "**Derniere MAJ** : 2026-10-01")
    e = ff.etat_fiche("A", projets, shinzo)
    assert e.etat == "a_jour" and e.retard == 0


def test_summary_counts_by_state(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-10-30", "feat: a")])
    _fiche(shinzo, "A", "**Derniere MAJ** : 2026-10-30")
    _depot(projets / "B", [("2026-10-30", "feat: b")])
    _fiche(shinzo, "B", "**Derniere MAJ** : 2026-09-01")
    _depot(projets / "C", [("2026-10-30", "feat: c")])
    comptes = ff.bilan(["A", "B", "C", "Z"], projets, shinzo)
    assert (comptes["a_jour"], comptes["en_retard"], comptes["absente"], comptes["sans_depot"]) == (1, 1, 1, 1)


# --- le garde de fin de séance -----------------------------------------------


def test_guard_targets_only_session_reports():
    assert garde.est_rapport("docs/Sessions/Session-2026-11-01-001.md")
    assert garde.est_rapport(r"D:\x\docs\Sessions\Session-2026-11-01-001.md")
    assert not garde.est_rapport("docs/Briefs/Brief-X.md")


def test_guard_message_when_code_moved_and_fiche_did_not(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-10-30", "feat: a")])
    _fiche(shinzo, "A", "**Derniere MAJ** : 2026-10-01")
    msg = garde.message("A", projets, shinzo)
    assert msg and "A" in msg and "2026-10-01" in msg and "2026-10-30" in msg


def test_guard_is_silent_when_fiche_is_current_or_unknown(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-10-30", "feat: a")])
    _fiche(shinzo, "A", "**Derniere MAJ** : 2026-10-30")
    assert garde.message("A", projets, shinzo) is None
    assert garde.message("Inconnu", projets, shinzo) is None


def test_guard_says_so_when_the_fiche_is_missing(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "A", [("2026-10-30", "feat: a")])
    (shinzo / "02-Projets").mkdir(parents=True)
    msg = garde.message("A", projets, shinzo)
    assert msg and "n'existe pas" in msg


def test_a_repo_whose_fiche_has_another_name_is_found(tmp_path):
    projets, shinzo = tmp_path / "p", tmp_path / "Shinzo"
    _depot(projets / "Hikari", [("2026-10-30", "feat: a")])
    _fiche(shinzo, "Hikari-Stream", "**Derniere MAJ** : 2026-10-30")
    assert ff.etat_fiche("Hikari", projets, shinzo).etat == "a_jour"


def test_a_label_in_bold_in_the_middle_of_a_header_line_is_read():
    # Shinzo/02-Projets/Shinkofa-MCP.md : « **Rôle** : … **Dernière MAJ** : 2026-10-31. » (relecture 2026-11-01)
    assert ff.date_fiche("**Rôle** : passerelle. **Dernière MAJ** : 2026-10-31.") == date(2026, 10, 31)


def test_a_yaml_updated_key_is_read():
    assert ff.date_fiche("---\ntitre: X\nupdated: 2026-07-11\n---") == date(2026, 7, 11)


def test_documentation_and_dependency_commits_are_not_code(tmp_path):
    depot = tmp_path / "P"
    _depot(depot, [("2026-10-01", "fix(niwa): x"), ("2026-10-05", "docs(sessions): rapport"),
                   ("2026-10-06", "docs: rapport de seance"), ("2026-10-07", "docs(readme): README"),
                   ("2026-10-08", "chore(deps): morphic"), ("2026-10-09", "fix(rules): sync Interpretation-Protocol"),
                   ("2026-10-10", "chore(hooks): sync")])
    assert ff.date_code(depot) == date(2026, 10, 1)
