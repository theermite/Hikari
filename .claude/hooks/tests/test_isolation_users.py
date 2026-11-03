"""lib/isolation_users.py — un projet qui a des comptes a des tests qui prouvent que A ne lit rien de B.

Lacune du 2026-10-30 : « aucune porte n'impose des tests d'isolation entre utilisateurs pour les plateformes à comptes ». Le code
COMPTE les projets concernés (garde hebdomadaire) et ne bloque rien : bloquer une mise en ligne sur la foi d'une recherche de mots
dans des fichiers de test serait un faux refus assuré.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import isolation_users as iso  # noqa: E402


def _projet(dossier: Path, nom: str, *, deps: dict | None = None, mix: str | None = None, tests: dict | None = None) -> Path:
    racine = dossier / nom
    racine.mkdir(parents=True)
    if deps is not None:
        (racine / "package.json").write_text(json.dumps({"dependencies": deps}), encoding="utf-8")
    if mix is not None:
        (racine / "mix.exs").write_text(mix, encoding="utf-8")
    for chemin, texte in (tests or {}).items():
        (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
        (racine / chemin).write_text(texte, encoding="utf-8")
    return racine


def test_a_js_project_with_an_auth_library_has_accounts(tmp_path):
    assert iso.a_des_comptes(_projet(tmp_path, "a", deps={"next-auth": "5.0.0"}))
    assert iso.a_des_comptes(_projet(tmp_path, "b", deps={"@clerk/nextjs": "1"}))


def test_a_project_without_auth_has_no_accounts(tmp_path):
    assert not iso.a_des_comptes(_projet(tmp_path, "c", deps={"react": "19.0.0"}))


def test_an_elixir_project_with_an_auth_dependency_has_accounts(tmp_path):
    assert iso.a_des_comptes(_projet(tmp_path, "d", mix='defp deps do\n [{:argon2_elixir, "~> 4.0"}]\nend'))


def test_a_python_project_with_an_auth_requirement_has_accounts(tmp_path):
    racine = _projet(tmp_path, "e")
    (racine / "requirements.txt").write_text("fastapi==0.115\npython-jose==3.3\n", encoding="utf-8")
    assert iso.a_des_comptes(racine)


def test_a_monorepo_app_is_seen(tmp_path):
    racine = _projet(tmp_path, "f")
    (racine / "apps" / "web").mkdir(parents=True)
    (racine / "apps" / "web" / "package.json").write_text(json.dumps({"dependencies": {"jsonwebtoken": "9"}}), encoding="utf-8")
    assert iso.a_des_comptes(racine)


def test_an_isolation_test_is_found_by_its_words(tmp_path):
    racine = _projet(tmp_path, "g", deps={"jose": "5"},
                     tests={"tests/accounts.test.ts": "it('user A cannot read other user data', () => {})"})
    assert iso.a_des_tests_d_isolation(racine)
    racine = _projet(tmp_path, "h", deps={"jose": "5"}, tests={"test/a_test.exs": 'test "tenant isolation" do end'})
    assert iso.a_des_tests_d_isolation(racine)


def test_ordinary_tests_do_not_count(tmp_path):
    racine = _projet(tmp_path, "i", deps={"jose": "5"}, tests={"tests/login.test.ts": "it('logs in', () => {})"})
    assert not iso.a_des_tests_d_isolation(racine)


def test_tests_inside_dependencies_do_not_count(tmp_path):
    racine = _projet(tmp_path, "j", deps={"jose": "5"},
                     tests={"node_modules/lib/x.test.js": "it('cross-user isolation', () => {})"})
    assert not iso.a_des_tests_d_isolation(racine)


def test_missing_lists_only_projects_with_accounts_and_no_isolation_test(tmp_path):
    _projet(tmp_path, "sans-compte", deps={"react": "19"})
    _projet(tmp_path, "protege", deps={"jose": "5"}, tests={"tests/a.test.ts": "it('forbids cross-user access', () => {})"})
    _projet(tmp_path, "expose", deps={"jose": "5"}, tests={"tests/b.test.ts": "it('logs in', () => {})"})
    assert iso.manquants(["sans-compte", "protege", "expose", "absent"], tmp_path) == ["expose"]


# --- relecture indépendante du 2026-11-02 (R4) -------------------------------------------------------------------------


def test_the_bare_word_isolation_in_a_database_test_does_not_count(tmp_path):
    racine = _projet(tmp_path, "k", deps={"jose": "5"},
                     tests={"tests/db.test.ts": "it('uses transaction isolation level serializable', () => {})"})
    assert not iso.a_des_tests_d_isolation(racine)
    racine = _projet(tmp_path, "l", deps={"jose": "5"}, tests={"tests/u.test.ts": "it('user isolation holds', () => {})"})
    assert iso.a_des_tests_d_isolation(racine)


def test_more_vendor_folders_are_ignored(tmp_path):
    for dossier in ("env", "target", "coverage", ".turbo", ".svelte-kit"):
        racine = _projet(tmp_path / dossier, "p", deps={"jose": "5"},
                         tests={f"{dossier}/lib/x.test.js": "it('cross-user isolation', () => {})"})
        assert not iso.a_des_tests_d_isolation(racine), dossier


def test_the_cap_counts_files_walked_not_only_tests(tmp_path, monkeypatch):
    racine = _projet(tmp_path, "m", deps={"jose": "5"})
    for i in range(30):
        (racine / f"f{i}.txt").write_text("x", encoding="utf-8")
    (racine / "tests").mkdir()
    (racine / "tests" / "z.test.ts").write_text("it('cross-user isolation', () => {})", encoding="utf-8")
    monkeypatch.setattr(iso, "_MAX_FILES", 10)
    assert not iso.a_des_tests_d_isolation(racine)   # the walk stopped before reaching the test: bounded, not exhaustive


def test_a_symlink_is_not_followed(tmp_path):
    racine = _projet(tmp_path, "n", deps={"jose": "5"})
    try:
        (racine / "boucle").symlink_to(racine, target_is_directory=True)
    except (OSError, NotImplementedError):
        return   # no symlink right on this machine: nothing to prove
    assert iso.a_des_tests_d_isolation(racine) is False


def test_one_unreadable_project_does_not_erase_the_others(tmp_path, monkeypatch):
    _projet(tmp_path, "a-casse", deps={"jose": "5"})
    _projet(tmp_path, "b-expose", deps={"jose": "5"})
    appels = []
    reel = iso.a_des_comptes

    def parfois_casse(racine):
        appels.append(Path(racine).name)
        if Path(racine).name == "a-casse":
            raise OSError("illisible")
        return reel(racine)
    monkeypatch.setattr(iso, "a_des_comptes", parfois_casse)
    assert iso.manquants(["a-casse", "b-expose"], tmp_path) == ["b-expose"]
