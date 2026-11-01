"""Couverture linguistique d'une recherche de fond — le marqueur contre les requêtes réellement lancées.

Décision de Jay (2026-10-31) : la recherche en sept langues est une règle ciblée (recherche de fond),
avec un rapport de couverture. Origine : feedback de Jay du 2026-05-26, « les agents prétendent avoir
cherché en 7 langues sans le faire ».

Le marqueur : `[LANGUES] EN=ok FR=ok ZH=rien JA=rien KO=rien DE=ok RU=ok`. `ok` = au moins une requête
dans cette langue a été lancée ; `rien` = cherché sans résultat, ou non cherché (dit sans honte).
Une langue annoncée `ok` sans requête dans son écriture est un mensonge, et c'est ce que ce module refuse.

LIMITES ÉCRITES : la langue d'une requête se lit à son écriture (idéogrammes, kana, hangul, cyrillique) ou à
des mots-outils (allemand, français). Un exemple cité SEUL sur sa ligne reste lu comme émis : poser le marqueur
uniquement à la fin d'une recherche, et citer la règle dans une phrase ou entre accents graves. Un texte latin sans mot-outil ni accent est indécidable : il couvre EN,
FR et DE à la fois (échec ouvert). Le contrôle est donc strict pour ZH, JA, KO et RU, là où le mensonge est
le plus probable, et indulgent pour les trois langues latines. Des idéogrammes sans kana comptent pour ZH.
"""

from __future__ import annotations

import re

LANGUES = ("EN", "FR", "ZH", "JA", "KO", "DE", "RU")
VALEURS = ("ok", "rien")

_MARQUEUR_EMIS = re.compile(r"^ {0,3}[*_]*\[LANGUES\]([^\n]*)$", re.I | re.M)
_BLOC_DE_CODE = re.compile(r"(```|~~~).*?(?:\1|\Z)", re.S)
_PAIRE = re.compile(r"\b(EN|FR|ZH|JA|KO|DE|RU)\b[\s`*_]*[=:][\s`*_]*([A-Za-zéèÉÈ-]+)")

_KANA = re.compile(r"[぀-ヿ]")
_HAN = re.compile(r"[㐀-䶿一-鿿]")
_HANGUL = re.compile(r"[가-힯ᄀ-ᇿ]")
_CYRILLIQUE = re.compile(r"[Ѐ-ӿ]")

_MOTS_DE = {"und", "der", "die", "das", "mit", "für", "fur", "nicht", "ist", "wie", "von", "zu", "den",
            "dem", "ein", "eine", "auf", "bei", "oder", "im", "über", "ueber"}
_MOTS_FR = {"le", "la", "les", "des", "du", "pour", "avec", "une", "un", "est", "dans", "sur", "et",
            "par", "qui", "que", "aux", "ou", "de", "en", "sans", "entre", "chez", "comme", "nos", "ses"}
_TREMAS_DE = re.compile(r"[äöüßÄÖÜ]")
_ACCENTS_FR = re.compile(r"[éèêàâçùûîôëïÉÈÊÀÂÇ]")
_MOTS = re.compile(r"[a-zA-ZäöüßÄÖÜéèêàâçùûîôëïÉÈÊÀÂÇ]+")


def parse_marker(texte: str) -> dict[str, str] | None:
    """Le marqueur EMIS dans le texte : `{langue: valeur}`, None s'il n'y en a pas.

    Emis = une ligne qui commence par `[LANGUES]` (gras admis, au plus 3 espaces de retrait), hors clôture de code, et qui porte
    au moins une paire `LANGUE=valeur`. Cité en exemple (au milieu d'une phrase, entre accents graves, dans
    une liste ou un bloc de code), il n'est pas lu : une réponse qui explique la règle n'est pas refusée.
    """
    sans_code = _BLOC_DE_CODE.sub("", texte or "")
    emis = [{lang: valeur.lower() for lang, valeur in _PAIRE.findall(m.group(1))}
            for m in _MARQUEUR_EMIS.finditer(sans_code)]
    emis = [paires for paires in emis if paires]
    return emis[-1] if emis else None   # le dernier : un exemple cité plus haut ne l'emporte pas


def _ecritures(requete: str) -> set[str]:
    """Les langues qui se lisent à l'écriture seule (kana avant idéogrammes : le japonais en porte les deux)."""
    trouvees: set[str] = set()
    if _KANA.search(requete):
        trouvees.add("JA")
    elif _HAN.search(requete):
        trouvees.add("ZH")
    if _HANGUL.search(requete):
        trouvees.add("KO")
    if _CYRILLIQUE.search(requete):
        trouvees.add("RU")
    return trouvees


def _langue_latine(requete: str) -> set[str]:
    """DE, FR ou EN pour un texte latin (les trois si rien ne tranche) ; rien sans mot de trois lettres."""
    mots = _MOTS.findall(requete.lower())
    if not any(len(m) >= 3 for m in mots):
        return set()
    de = sum(m in _MOTS_DE for m in mots) + 2 * bool(_TREMAS_DE.search(requete))
    fr = sum(m in _MOTS_FR for m in mots) + 2 * bool(_ACCENTS_FR.search(requete))
    if de >= 2 and de >= fr:
        return {"DE"}
    if fr >= 2:
        return {"FR"}
    # Indécidable (aucun mot-outil, aucun accent) : la langue peut être l'une des trois. On échoue ouvert :
    # refuser un `ok` honnête est pire que laisser passer un `ok` douteux sur une langue latine.
    return {"EN", "FR", "DE"}


def langues_de(requete: str) -> set[str]:
    """Les langues dont l'écriture ou les mots-outils se lisent dans la requête."""
    return _ecritures(requete) or _langue_latine(requete)


def _erreurs_de_forme(marqueur: dict[str, str]) -> list[str]:
    erreurs: list[str] = []
    for lang in LANGUES:
        if lang not in marqueur:
            erreurs.append(f"{lang} : langue absente du marqueur (les sept doivent y figurer, `ok` ou `rien`).")
        elif marqueur[lang] not in VALEURS:
            erreurs.append(f"{lang} : valeur '{marqueur[lang]}' inconnue (seulement `ok` ou `rien`).")
    return erreurs


def _erreurs_de_couverture(marqueur: dict[str, str], queries: list[str]) -> list[str]:
    couvertes: set[str] = set()
    for q in queries:
        couvertes |= langues_de(q)
    return [f"{lang} : annoncée `ok`, mais aucune requête lancée dans cette langue."
            for lang in LANGUES if marqueur[lang] == "ok" and lang not in couvertes]


def problemes(marqueur: dict[str, str] | None, queries: list[str], delegue: bool = False) -> list[str]:
    """Ce qui cloche entre le marqueur et les requêtes. `delegue` : les recherches ont pu être faites par
    un sous-agent, que ce journal ne voit pas ; on ne juge alors que la forme du marqueur."""
    if marqueur is None:
        return []
    erreurs = _erreurs_de_forme(marqueur)
    if delegue or erreurs:
        return erreurs
    return _erreurs_de_couverture(marqueur, queries)
