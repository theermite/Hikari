"""Un projet qui a des comptes a des tests qui prouvent que A ne lit rien de B (lacune du 2026-10-30).

Le code COMPTE (garde hebdomadaire `scripts/garde-methode.py`) et ne bloque rien : refuser une mise en ligne sur une recherche de
mots dans des fichiers de test serait un faux refus assuré. Un compte annonce « tel projet a des comptes et aucun test dont
les mots parlent d'isolation » ; Jay et Takumi regardent ensuite le projet.

Limites écrites :
- « a des comptes » se lit à une bibliothèque d'authentification dans `package.json`, `mix.exs`, `pyproject.toml` ou
  `requirements*.txt` (racine, un niveau plus bas, `apps/*` et `packages/*`) ; une authentification faite à la main n'est pas vue.
- « a des tests d'isolation » se lit à des MOTS dans un fichier de test (isolation, cross-user, other user, tenant, IDOR…) : un
  test nommé autrement échappe, un test qui cite ces mots sans rien prouver passe. C'est un comptage, pas une preuve.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from cdc_modele_interaction import _dossiers_a_lire

_JS_AUTH = {"next-auth", "@auth/core", "passport", "jsonwebtoken", "jose", "lucia", "bcrypt", "bcryptjs", "argon2",
            "@node-rs/argon2", "better-auth", "iron-session"}
_JS_AUTH_PREFIXES = ("@clerk/", "@supabase/auth", "@auth0/")
_CLES_JS = ("dependencies", "devDependencies", "peerDependencies")
_TEXT_AUTH = re.compile(
    r"(?<![\w-])(fastapi-users|python-jose|pyjwt|authlib|passlib|flask-login|django-allauth|argon2-cffi|"
    r"argon2_elixir|bcrypt_elixir|comeonin|guardian|ueberauth|joken|assent|pow)(?![\w-])", re.IGNORECASE)
_TEST_FILE = re.compile(r"(\.(test|spec)\.[cm]?[jt]sx?$)|(^|/)test_[^/]*\.py$|_test\.exs?$|_test\.py$")
# Le mot nu « isolation » ne compte plus : « transaction isolation » dans un test de base de données n'est pas l'isolation entre
# utilisateurs (relecture indépendante du 2026-11-02).
_ISOLATION = re.compile(
    r"(?:user|tenant|account|data)[-_ ]?isolation|isolation[-_ ]?(?:between|entre|of)[-_ ]?(?:user|tenant|account|utilisateur)"
    r"|cross[-_ ]?(?:user|tenant|account)|(?:other|another)[-_ ]?(?:user|account|tenant)"
    r"|tenant[-_ ]?leak|\bidor\b|user[ _]a\b[^\n]{0,60}user[ _]b\b", re.IGNORECASE)
_IGNORED = {"node_modules", ".git", "deps", "_build", ".venv", "venv", "env", "dist", "build", "target", "coverage", ".next",
            ".turbo", ".svelte-kit", "__pycache__"}
_MAX_FILES = 3000


def _package_json_auth(fichier: Path) -> bool:
    try:
        donnees = json.loads(fichier.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return False
    noms = {n for cle in _CLES_JS if isinstance(donnees, dict) and isinstance(donnees.get(cle), dict) for n in donnees[cle]}
    return bool(noms & _JS_AUTH) or any(n.startswith(_JS_AUTH_PREFIXES) for n in noms)


def _text_auth(fichier: Path) -> bool:
    try:
        return bool(_TEXT_AUTH.search(fichier.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def a_des_comptes(racine: Path) -> bool:
    for dossier in _dossiers_a_lire(Path(racine)):
        if (dossier / "package.json").is_file() and _package_json_auth(dossier / "package.json"):
            return True
        candidats = [dossier / "mix.exs", dossier / "pyproject.toml", *dossier.glob("requirements*.txt")]
        if any(f.is_file() and _text_auth(f) for f in candidats):
            return True
    return False


def _fichiers_de_test(racine: Path):
    parcourus = 0   # les fichiers PARCOURUS, pas seulement les tests : un gros dépôt avec peu de tests reste borné
    pile = [Path(racine)]
    while pile and parcourus < _MAX_FILES:
        dossier = pile.pop()
        try:
            entrees = sorted(dossier.iterdir())
        except OSError:
            continue
        for entree in entrees:
            parcourus += 1
            if entree.is_symlink() or getattr(entree, "is_junction", lambda: False)():
                continue   # une jonction ou un lien peut boucler
            if entree.is_dir():
                if entree.name not in _IGNORED:
                    pile.append(entree)
            elif _TEST_FILE.search(entree.as_posix()):
                yield entree


def a_des_tests_d_isolation(racine: Path) -> bool:
    for fichier in _fichiers_de_test(racine):
        try:
            if _ISOLATION.search(fichier.read_text(encoding="utf-8", errors="replace")):
                return True
        except OSError:
            continue
    return False


def manquants(projets: list[str], dossier: Path) -> list[str]:
    """Projets qui ont des comptes et aucun test dont les mots parlent d'isolation entre utilisateurs."""
    manquants_: list[str] = []
    for nom in projets:
        racine = Path(dossier) / nom
        try:   # un projet illisible n'efface pas le compte des autres
            if racine.is_dir() and a_des_comptes(racine) and not a_des_tests_d_isolation(racine):
                manquants_.append(nom)
        except (OSError, ValueError):
            continue
    return manquants_
