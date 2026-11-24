#!/usr/bin/env python3
"""PreToolUse Write|Edit|MultiEdit — tout ajout dans Eichi porte une date, une source, un extrait lu et un auteur.

Décision de Jay du 2026-11-19 (« le quoi est à moi, le comment est à Takumi ») : Eichi s'écrit directement,
sans passer par lui, mais avec des garde-fous. Ce garde-fou en tient trois ; les deux autres sont ailleurs :
le retrait se fait par l'historique git, l'échantillon relu à l'inventaire est `scripts/eichi_echantillon.py`.

Ce qui est contrôlé : une page de contenu (`Eichi/NN-domaine/…/*.md` à n'importe quelle profondeur, hors INDEX et
dossiers `_…`) qui reçoit du texte NEUF (au moins 8 mots neufs, hors lignes d'en-tête `clé: valeur` à clé connue)
doit aussi recevoir une marque `[AJOUT AAAA-MM-JJ | source: … | extrait: "…" | rédigé par: …]`, SEULE sur sa ligne
(voir lib/eichi_ajout.py).

Ce que ce garde-fou EST : un filet, pas une preuve. Les mots de l'EXTRAIT doivent se retrouver, dans l'ordre, dans le CORPS
d'une lecture web (web_read ou WebFetch, sans erreur déclarée) APPELÉE sur l'adresse de la source (DOI et arXiv : leur
adresse officielle). Cela attrape l'oubli, l'invention de mémoire, la page jamais ouverte, et oblige à un texte relu
(l'échantillon compare extrait et phrase). Quatre relectures indépendantes FAIL le 2026-11-23 sur la même famille ont
établi ce qu'il NE PEUT PAS faire : le rédacteur choisit lui-même l'extrait dans la sortie de l'outil ; une page
d'erreur ou un captcha lus sans erreur déclarée (403 de WebFetch, « Un instant… ») lui fournissent donc des mots à
citer. Aucun filtre de format ne ferme cela. Seul un TÉMOIN INDÉPENDANT le ferme : l'outil de lecture (web_read, sur le
serveur de Jay) écrivant lui-même une ligne d'état stable (code HTTP, adresse finale) que ce garde lirait. Suite à
faire dans Shinkofa-MCP ; d'ici là, la vérification réelle est l'échantillon relu par un humain.

Le volume de texte neuf se compte en mots neufs (multiensemble, hors en-tête et marques) : une coquille ou un
déplacement n'est pas un ajout, une phrase collée au bout d'une ligne en est un.

Sortie : `EICHI-OK: <raison>` dans le texte ajouté (coquilles en série, déplacement de contenu).

LIMITES ÉCRITES : un extrait cité dans une page d'erreur lue sans erreur déclarée passe (voir plus haut) ; l'extrait ne prouve
pas non plus que la phrase ajoutée résume fidèlement la page (échantillon). Une marque couvre tout l'ajout du même appel,
et le volume se juge appel par appel (une suite d'Edit de 7 mots passe ; une écriture par Bash aussi). Un ISBN n'est pas vérifiable (pas d'extrait exigé). Un résultat de WebFetch est un résumé de modèle : il
doit citer l'extrait pour compter. Un sous-agent lit le journal du PARENT : une lecture faite seulement par lui ne
compte pas. Le navigateur Chrome n'est pas reconnu comme lecteur. Sans journal de séance lisible, seule la forme de la
marque est contrôlée. `EICHI-OK` écrit dans la page elle-même (même en commentaire) dispense : relu à l'échantillon.
"""

from __future__ import annotations

import posixpath
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402
from eichi_ajout import GABARIT, MARQUE, adresse_a_lire, cle_url, extrait_dans, marques, probleme  # noqa: E402
from transcript_reader import entry_message, iter_entries  # noqa: E402

_CHEMIN = re.compile(r"(?:^|/)eichi/\d\d-[^/]+/.+\.md$")
_CLES = ("aliases|tags|created|modified|updated|status|domain|language|languages_researched|reviewed|"
         "confidence|sources|type|priority|date|author")
_CLE = re.compile(rf"^\s*(?:{_CLES}):(\s|$)", re.I)
_DISPENSE = re.compile(r"EICHI-OK:\s*\S")
_OUTILS_LECTURE = ("web_read", "webfetch")  # lire une page ; web_search et web_check prouvent qu'elle existe, pas qu'elle a été lue
MOTS_MINI = 8
_ENVELOPPE = re.compile(r'<external-content[^>]*>(.*?)</external-content>', re.S)


def _est_du_contenu(chemin: str) -> bool:
    p = posixpath.normpath(chemin.replace("\\", "/")).lower()
    if not _CHEMIN.search(p) or p.endswith("/index.md"):
        return False
    return not any(part.startswith("_") for part in p.split("eichi/", 1)[1].split("/"))


def _lignes_neuves(neuf: str, ancien: str) -> list[str]:
    """Les lignes neuves. Une ligne identique à une ancienne n'est pas un ajout ; une ligne qui prolonge une ancienne
    ne compte que par son prolongement (jamais de retrait d'un morceau au milieu : « x » est dans « hexdocs »)."""
    anciennes = [ligne.strip() for ligne in ancien.splitlines() if ligne.strip()]
    neuves = []
    for ligne in (n.strip() for n in neuf.splitlines()):
        reste = next((ligne[len(a):].strip() for a in anciennes if len(a) >= 8 and ligne.startswith(a)), ligne)
        if reste and ligne not in anciennes:
            neuves.append(reste)
    return neuves


def _ancien_fichier(entree: dict) -> str:
    chemin = Path(str(entree.get("file_path") or ""))
    try:
        return chemin.read_text(encoding="utf-8", errors="replace") if chemin.is_file() else ""
    except OSError:
        return ""


def _paire(modif: dict) -> tuple[str, str]:
    return str(modif.get("new_string") or ""), str(modif.get("old_string") or "")


def _paires(tool: str, entree: dict) -> list[tuple[str, str]]:
    if tool == "Write":
        return [(str(entree.get("content") or ""), _ancien_fichier(entree))]
    modifs = entree.get("edits") if tool == "MultiEdit" else [entree]
    return [_paire(m) for m in modifs or [] if isinstance(m, dict)]


def texte_ajoute(tool: str, entree: dict) -> str:
    return "\n".join("\n".join(_lignes_neuves(neuf, ancien)) for neuf, ancien in _paires(tool, entree))


def _mots(texte: str) -> list[str]:
    return [m for ligne in texte.splitlines() if not _CLE.match(ligne) for m in MARQUE.sub("", ligne).split()]


def _mots_neufs(tool: str, entree: dict) -> int:
    """Mots présents après et absents avant, en comptant les répétitions : une coquille ou un déplacement en ont
    presque aucun, une phrase ajoutée au bout d'une ligne en a autant qu'elle en contient."""
    return sum(sum((Counter(_mots(neuf)) - Counter(_mots(ancien))).values()) for neuf, ancien in _paires(tool, entree))


def _marque_hors_de_sa_ligne(texte: str) -> bool:
    return any(MARQUE.search(ligne) and MARQUE.sub("", ligne).strip() for ligne in texte.splitlines())


def _texte(contenu) -> str:
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in contenu)
    return ""


def _blocs(entree) -> list[dict]:
    msg = entry_message(entree)
    contenu = msg.get("content") if msg else None
    return [b for b in contenu if isinstance(b, dict)] if isinstance(contenu, list) else []


def lectures(transcript_path: str) -> list[tuple[str, str]] | None:
    """(adresse d'APPEL, résultat) de chaque lecture web sans erreur déclarée ; None si le journal est vide."""
    entrees = list(iter_entries(transcript_path, reverse=False)) if transcript_path else []
    if not entrees:
        return None
    appels: dict[str, str] = {}
    lues: list[tuple[str, str]] = []
    for entree in entrees:
        for bloc in _blocs(entree):
            _noter(bloc, appels, lues)
    return lues


def _corps(resultat: str) -> str:
    """Le corps de la page : sans l'enveloppe de l'outil, son préfixe d'état ni l'adresse (des mots que l'outil écrit, pas la page)."""
    enveloppe = _ENVELOPPE.search(resultat)
    return enveloppe.group(1) if enveloppe else resultat


def _est_lecteur(nom: str) -> bool:
    return any(o in nom.lower() for o in _OUTILS_LECTURE)


def _noter(bloc: dict, appels: dict[str, str], lues: list[tuple[str, str]]) -> None:
    if bloc.get("type") == "tool_use":
        if _est_lecteur(str(bloc.get("name") or "")):
            appels[str(bloc.get("id"))] = str((bloc.get("input") or {}).get("url") or "")
        return
    url = appels.get(str(bloc.get("tool_use_id")))
    if url and bloc.get("type") == "tool_result" and not bloc.get("is_error"):
        lues.append((cle_url(url), _corps(_texte(bloc.get("content")))))


def _refus(chemin: str, raison: str) -> None:
    block(f"Eichi : {raison}\nFichier : {chemin}\nChaque ajout porte une marque seule sur sa ligne :\n  {GABARIT}\n"
          "L'extrait doit être copié de la page LUE dans cette séance (web_read ou WebFetch appelé sur la même adresse). "
          "Décision de Jay du 2026-11-19 ; retrait possible par l'historique. Correction de masse sans nouvelle "
          "information : écris `EICHI-OK: <raison>` dans le texte ajouté.")


def _extrait_lu(marque: dict, lues: list[tuple[str, str]]) -> bool:
    cible = cle_url(adresse_a_lire(marque["source"]) or "")
    return any(url == cible and extrait_dans(marque["extrait"], texte) for url, texte in lues)


def _juger(ajoute: str, transcript: str) -> str | None:
    """La raison du refus, ou None."""
    trouvees = marques(ajoute)
    if not trouvees:
        return "du texte neuf est ajouté sans marque d'ajout (date, source, extrait, auteur)."
    if _marque_hors_de_sa_ligne(ajoute):
        return "la marque doit être SEULE sur sa ligne (du texte la suit ou la précède sur la même ligne)."
    lues = lectures(transcript)
    for m in trouvees:
        if (pb := probleme(m, date.today())):
            return f"marque refusée : {pb}."
        if lues is not None and adresse_a_lire(m["source"]) and not _extrait_lu(m, lues):
            return (f"l'extrait « {m['extrait']} » ne se retrouve dans aucune lecture de {m['source']} faite dans cette séance "
                    "(page jamais lue, lecture en échec, ou extrait qui n'est pas dans la page).")
    return None


def main() -> None:
    _, data = read_hook_input()
    tool = str(data.get("tool_name") or "")
    entree = data.get("tool_input") or {}
    chemin = str(entree.get("file_path") or "")
    if tool not in ("Write", "Edit", "MultiEdit") or not _est_du_contenu(chemin):
        return pass_through()
    if _mots_neufs(tool, entree) < MOTS_MINI or _DISPENSE.search(texte_ajoute(tool, entree)):
        return pass_through()
    raison = _juger(texte_ajoute(tool, entree), str(data.get("transcript_path") or ""))
    return _refus(chemin, raison) if raison else pass_through()


if __name__ == "__main__":
    main()
