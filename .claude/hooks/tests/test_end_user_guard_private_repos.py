"""end-user-data-guard : dans un dépôt PRIVÉ connu, les notes et les messages de commit sont libres (2026-10-30).

Décision de Jay : la conversation et ses notes privées sont libres ; un dépôt public ou une publication ne porte
jamais d'information d'utilisateur ; le code, les tests, les exemples et les jeux de données restent filtrés où qu'ils
soient. Règle de départ la plus prudente : un dépôt n'est « privé » que si GitHub (ou le cache de sa réponse) le dit.
Sans réponse, sans remote GitHub, ou avec un cache illisible ou trop vieux : le garde reste strict, comme avant.

Ces tests lancent le garde comme le harnais (sous-processus, vraie entrée) dans de vrais dépôts git temporaires.
Tous les identifiants sont inventés.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
GUARD = HOOKS / "guards" / "end-user-data-guard.py"
LIB = HOOKS / "lib" / "end_user_identifiers.py"
SLUG = "acme/depot-prive"
NOM = "Zorvexa"
FRAIS = {"private": True, "at": None}


def _env(store: Path) -> dict:
    env = dict(os.environ)
    env["EUI_STORE_DIR"] = str(store)
    env["EUI_GH_CMD"] = "commande-gh-introuvable"      # jamais d'appel reseau reel dans un test
    return env


def _store(tmp_path: Path) -> Path:
    store = tmp_path / "store"
    store.mkdir()
    subprocess.run([sys.executable, str(LIB), "rebuild"], input=f"{NOM}\n", capture_output=True, text=True,
                   env=_env(store), check=True)
    return store


def _cache(store: Path, slug: str = SLUG, private: bool = True, age: float = 0.0, brut: str | None = None) -> None:
    contenu = brut if brut is not None else json.dumps({slug: {"private": private, "at": time.time() - age}})
    (store / "repo-visibility.json").write_text(contenu, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _depot(tmp_path: Path, remote: str | None = f"https://github.com/{SLUG}.git") -> Path:
    repo = tmp_path / "depot"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    if remote:
        _git(repo, "remote", "add", "origin", remote)
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _garde(store: Path, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload), capture_output=True, text=True,
                          env=_env(store), cwd=str(cwd))


def _ecrire(repo: Path, store: Path, nom: str, contenu: str) -> int:
    chemin = str(repo / nom).replace("\\", "/")
    return _garde(store, {"tool_name": "Write", "tool_input": {"file_path": chemin, "content": contenu}}, repo).returncode


def _commit(repo: Path, store: Path, message: str, **fichiers: str) -> int:
    for nom, contenu in fichiers.items():
        chemin = repo / nom.replace("__", "/")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")
    _git(repo, "add", "-A")
    commande = f'git commit -m "{message}"'
    return _garde(store, {"tool_name": "Bash", "tool_input": {"command": commande}, "cwd": str(repo)}, repo).returncode


# --- écrire un fichier ------------------------------------------------------------------------------------------

def test_notes_are_free_in_a_known_private_repo(tmp_path):
    store, repo = _store(tmp_path), None
    repo = _depot(tmp_path)
    _cache(store)
    for nom in ("notes.md", "docs/Sessions/rapport.mdx", "docs/plan.rst", "Zorvexa-notes.md"):
        assert _ecrire(repo, store, nom, f"Ma fille {NOM} utilise la plateforme.") == 0, nom


def test_code_tests_and_examples_stay_filtered_even_in_a_private_repo(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    for nom in ("src/app.py", "src/App.tsx", "config/users.json", "data/seed.yaml",
                "tests/notes.md", "fixtures/profil.md", "docs/examples/demo.md", "src/__snapshots__/a.md"):
        assert _ecrire(repo, store, nom, f"user = '{NOM}'") == 2, nom


def test_a_public_repo_is_as_strict_as_before(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store, private=False)
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2


def test_an_unknown_visibility_stays_strict(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)                                    # aucun cache, commande gh introuvable
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2


def test_no_github_remote_stays_strict(tmp_path):
    store = _store(tmp_path)
    _cache(store)
    for remote in (None, "https://gitlab.com/acme/depot-prive.git", "ssh://git@vps/srv/git/depot-prive.git"):
        dossier = tmp_path / f"r{abs(hash(remote)) % 1000}"
        dossier.mkdir()
        repo = _depot(dossier, remote)
        assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2, remote


def test_a_corrupt_or_ancient_cache_stays_strict(tmp_path):
    for i, (cache_kwargs) in enumerate(({"brut": "pas du json"}, {"brut": "[]"}, {"brut": '{"acme/depot-prive": 3}'},
                                        {"age": 40 * 86400.0})):
        dossier = tmp_path / f"c{i}"
        dossier.mkdir()
        store = _store(dossier)
        repo = _depot(dossier)
        _cache(store, **cache_kwargs)
        assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2, cache_kwargs


def test_a_stale_cache_is_trusted_when_github_does_not_answer(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store, age=3 * 86400.0)                             # plus vieux qu'une heure, moins que 30 jours
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 0


def test_the_cache_is_per_repository(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store, slug="acme/un-autre-depot")
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2


# --- commiter ---------------------------------------------------------------------------------------------------

def test_a_commit_message_is_free_in_a_private_repo(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    assert _commit(repo, store, f"notes sur {NOM}", **{"notes.md": "rien\n"}) == 0


def test_a_commit_message_is_filtered_in_a_public_or_unknown_repo(tmp_path):
    for i, privee in enumerate((False, None)):
        dossier = tmp_path / f"p{i}"
        dossier.mkdir()
        store = _store(dossier)
        repo = _depot(dossier)
        if privee is not None:
            _cache(store, private=privee)
        assert _commit(repo, store, f"notes sur {NOM}", **{"notes.md": "rien\n"}) == 2, privee


def test_added_lines_are_free_in_notes_and_filtered_in_code_of_a_private_repo(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    assert _commit(repo, store, "notes", **{"docs__plan.md": f"Ma fille {NOM}\n"}) == 0
    assert _commit(repo, store, "code", **{"src__app.py": f"user = '{NOM}'\n"}) == 2


def test_notes_under_tests_or_examples_are_filtered_at_commit_too(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    assert _commit(repo, store, "n", **{"tests__notes.md": f"Ma fille {NOM}\n"}) == 2


def test_a_file_name_with_a_person_is_free_for_a_private_note_only(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    assert _commit(repo, store, "n", **{"notes-sur-Zorvexa.md": "rien\n"}) == 0
    assert _commit(repo, store, "n", **{"src__zorvexa_config.py": "x = 1\n"}) == 2


def test_the_staged_but_not_listed_content_cannot_slip_through_a_private_message(tmp_path):
    """Un message libre ne doit pas rendre libre le code indexe dans le meme commit."""
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    assert _commit(repo, store, "notes", **{"docs__plan.md": "ok\n", "src__app.py": f"user = '{NOM}'\n"}) == 2


# --- relecture finale (PASS, 5 remarques) ----------------------------------------------------------------------

def test_a_note_whose_name_has_an_accent_is_a_note(tmp_path):
    """git ecrit `+++ "b/S\\303\\251ance.md"` entre guillemets : le chemin n'etait pas lu, la note etait filtree."""
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    assert _commit(repo, store, "n", **{"notes__Séance.md": f"Ma fille {NOM}\n"}) == 0


def test_an_accented_file_name_is_still_read_as_a_name(tmp_path):
    """Sans `core.quotepath=off`, un nom accentue arrive en octal et ne peut plus correspondre a un identifiant."""
    for i, privee in enumerate((True, False)):
        dossier = tmp_path / f"a{i}"
        dossier.mkdir()
        store = _store(dossier)
        repo = _depot(dossier)
        _cache(store, private=privee)
        assert _commit(repo, store, "c", **{"src__zorvexâ_config.py": "x = 1\n"}) == 2, privee


def test_a_forged_diff_header_in_added_text_does_not_hide_code(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    piege = f"++ b/fake.md\nuser = '{NOM}'\n"        # git l'affiche `+++ b/fake.md` dans le diff
    assert _commit(repo, store, "c", **{"src__code.py": piege}) == 2


def test_a_deleted_file_is_read_without_error(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    _commit(repo, store, "ajout", **{"src__a.py": "x = 1\n"})
    (repo / "src" / "a.py").unlink()
    _git(repo, "add", "-A")
    assert _garde(store, {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "retire"'}, "cwd": str(repo)},
                  repo).returncode == 0


def test_every_remote_must_be_known_private(tmp_path):
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _git(repo, "remote", "add", "miroir", "https://github.com/acme/miroir-public.git")
    _cache(store, brut=json.dumps({SLUG: {"private": True, "at": time.time()},
                                   "acme/miroir-public": {"private": False, "at": time.time()}}))
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2                  # un second remote public
    _git(repo, "remote", "set-url", "miroir", "https://gitlab.com/acme/miroir.git")
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2                  # un hebergeur inconnu
    _git(repo, "remote", "set-url", "miroir", "https://github.com/acme/miroir-prive.git")
    _cache(store, brut=json.dumps({SLUG: {"private": True, "at": time.time()},
                                   "acme/miroir-prive": {"private": True, "at": time.time()}}))
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 0                  # tous prives et connus
    _git(repo, "remote", "set-url", "--push", "miroir", "https://github.com/acme/miroir-public.git")
    _cache(store, brut=json.dumps({SLUG: {"private": True, "at": time.time()},
                                   "acme/miroir-prive": {"private": True, "at": time.time()},
                                   "acme/miroir-public": {"private": False, "at": time.time()}}))
    assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == 2                  # l'adresse de poussee compte


def test_a_cache_older_than_a_week_is_not_trusted_when_github_is_silent(tmp_path):
    for i, (age, attendu) in enumerate(((3 * 86400.0, 0), (6 * 86400.0, 0), (10 * 86400.0, 2))):
        dossier = tmp_path / f"v{i}"
        dossier.mkdir()
        store = _store(dossier)
        repo = _depot(dossier)
        _cache(store, age=age)
        assert _ecrire(repo, store, "notes.md", f"Ma fille {NOM}") == attendu, age


def test_text_lists_and_data_folders_are_not_notes(tmp_path):
    """La regle promet : jeux de donnees et exports toujours filtres ; un .txt est souvent une liste."""
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    _cache(store)
    for nom in ("notes.txt", "requirements.txt", "data/users.md", "datasets/export.md", "exports/liste.md",
                "dumps/base.md", "db/notes.md", "backups/a.md"):
        assert _ecrire(repo, store, nom, f"Ma fille {NOM}") == 2, nom


# --- le résolveur lui-même --------------------------------------------------------------------------------------

def _resolveur():
    import importlib
    sys.path.insert(0, str(HOOKS / "lib"))
    return importlib.import_module("repo_visibility")


def test_the_github_slug_is_read_from_every_usual_remote_form(tmp_path):
    rv = _resolveur()
    assert rv.slug_from_url("https://github.com/acme/depot-prive.git") == "acme/depot-prive"
    assert rv.slug_from_url("https://github.com/acme/depot-prive") == "acme/depot-prive"
    assert rv.slug_from_url("https://github.com/acme/depot-prive/") == "acme/depot-prive"
    assert rv.slug_from_url("git@github.com:acme/depot-prive.git") == "acme/depot-prive"
    assert rv.slug_from_url("ssh://git@github.com/acme/depot-prive.git") == "acme/depot-prive"
    assert rv.slug_from_url("https://user:token@github.com/acme/depot.prive.git") == "acme/depot.prive"
    for autre in ("https://gitlab.com/acme/x.git", "git@vps:acme/x.git", "", "https://github.com/seulement", "not a url"):
        assert rv.slug_from_url(autre) is None, autre


def test_github_is_asked_when_the_cache_is_missing_or_stale_and_its_answer_is_cached(tmp_path, monkeypatch):
    rv = _resolveur()
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    monkeypatch.setenv("EUI_STORE_DIR", str(store))
    appels = []
    monkeypatch.setattr(rv, "_ask_github", lambda slug: appels.append(slug) or True)
    assert rv.is_private(str(repo)) is True and appels == [SLUG]
    assert rv.is_private(str(repo)) is True and appels == [SLUG]            # 2e fois : le cache suffit
    _cache(store, age=2 * 3600.0)                                           # vieux d'une heure et plus : on redemande
    assert rv.is_private(str(repo)) is True and appels == [SLUG, SLUG]


def test_a_repo_that_became_public_is_seen_within_an_hour(tmp_path, monkeypatch):
    rv = _resolveur()
    store = _store(tmp_path)
    repo = _depot(tmp_path)
    monkeypatch.setenv("EUI_STORE_DIR", str(store))
    _cache(store, age=2 * 3600.0)                                           # le cache dit « prive », a refaire
    monkeypatch.setattr(rv, "_ask_github", lambda slug: False)
    assert rv.is_private(str(repo)) is False


def test_an_answer_that_is_not_true_or_false_is_not_an_answer(tmp_path, monkeypatch):
    rv = _resolveur()
    monkeypatch.setenv("EUI_GH_CMD", sys.executable)
    assert rv._ask_github("acme/depot-prive") is None                       # `python api repos/... --jq .private` échoue
