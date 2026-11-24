"""eichi_ajout — la marque d'un ajout dans Eichi, lue de la même façon par le garde-fou et par l'échantillon.

Décision du 2026-11-19 (Jay : le quoi ; Takumi : le comment) : Eichi s'écrit directement, mais chaque ajout porte
une date, une source, un EXTRAIT de cette source et le nom de qui l'a rédigé. Forme d'une marque, seule sur sa ligne :

    [AJOUT 2026-11-23 | source: https://exemple.org/page | extrait: "quelques mots pris dans la page" | rédigé par: modèle local]

Pourquoi un extrait : la lecture d'une page ne se déduit pas de la forme de la sortie d'un outil (formats d'erreur sans fin ;
quatre relectures indépendantes FAIL le 2026-11-23). Un extrait retrouvé dans le corps de la lecture appelée sur cette
adresse attrape l'invention de mémoire et la page jamais ouverte, et il relie l'ajout à ce que dit la source :
l'échantillon de l'inventaire compare les deux.

Limites écrites : c'est un filet, pas une preuve. Le rédacteur choisit l'extrait : un 403 ou un captcha lus sans erreur
déclarée peuvent lui en fournir un (seul un témoin indépendant, l'outil de lecture qui écrirait son état, le ferme).
L'extrait ne prouve pas que la phrase résume fidèlement la page (relu par un humain). Un ISBN n'a ni lecture ni extrait.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

MARQUE = re.compile(
    r"\[AJOUT\s+(?P<date>[^|\]]*?)\s*\|\s*source:\s*(?P<source>[^|\]]*?)\s*"
    r"(?:\|\s*extrait:\s*(?P<extrait>\"[^\"]*\"|«[^»]*»)\s*)?"
    r"\|\s*rédigé par:\s*(?P<auteur>[^\]]*?)\s*\]")
_URL = re.compile(r"^https?://[^\s/]+\.[^\s/]+\S*$", re.I)
_AUTRE = re.compile(r"^(?:doi:\s*10\.\d{4,9}/\S+|arxiv:\s*\d{4}\.\d{4,5}|isbn[\s:-]*[\d-]{10,17})$", re.I)
GABARIT = ('[AJOUT AAAA-MM-JJ | source: <https://… ou doi:10… ou arXiv:… ou ISBN …> | extrait: "<6 mots ou plus copiés de la page lue>" '
           '| rédigé par: <modèle local | Takumi>]')
MOTS_EXTRAIT_MINI = 6


def marques(texte: str) -> list[dict]:
    """Les marques du texte ; adresse entre chevrons et guillemets de l'extrait sont retirés."""
    trouvees = [m.groupdict() for m in MARQUE.finditer(texte)]
    for m in trouvees:
        m["source"] = m["source"].strip("<> ")
        m["extrait"] = (m["extrait"] or "")[1:-1].strip()
    return trouvees


def adresse_a_lire(source: str) -> str | None:
    """L'adresse web qu'il a fallu lire : l'adresse même, ou celle du DOI / de l'arXiv. Un ISBN n'en a pas."""
    if est_url(source):
        return source
    doi = re.match(r"doi:\s*(10\.\S+)$", source, re.I)
    if doi:
        return f"https://doi.org/{doi.group(1)}"
    arxiv = re.match(r"arxiv:\s*(\d{4}\.\d{4,5})$", source, re.I)
    return f"https://arxiv.org/abs/{arxiv.group(1)}" if arxiv else None


def est_url(source: str) -> bool:
    return bool(_URL.match(source))


def cle_url(url: str) -> str:
    """Ce qui identifie une page : ni le schéma, ni « www. », ni la casse de l'hôte, ni le « / » final, ni l'ancre."""
    sans = url.strip().strip("<>").split("#")[0].rstrip("/.,;)")
    sans = re.sub(r"^https?://", "", sans, flags=re.I)
    hote, _, reste = sans.partition("/")
    hote = re.sub(r"^www\.", "", hote.lower())
    return f"{hote}/{reste}" if reste else hote


def mots(texte: str) -> list[str]:
    """Les mots d'un texte tel qu'on le LIT : sans casse, ponctuation ni mise en forme ; un lien markdown se réduit à son
    libellé, une ligature se défait (NFKC), un mot coupé en fin de ligne se recolle."""
    texte = unicodedata.normalize("NFKC", texte).lower()
    texte = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", texte)
    texte = re.sub(r"-[ \t]*\n\s*", "", texte)
    return re.findall(r"\w+", texte)


def extrait_dans(extrait: str, page: str) -> bool:
    """Les mots de l'extrait se suivent, dans le même ordre, dans la page."""
    voulus = mots(extrait)
    lus = mots(page)
    n = len(voulus)
    return n > 0 and any(lus[i:i + n] == voulus for i in range(len(lus) - n + 1))


def probleme(marque: dict, aujourdhui: date) -> str | None:
    """Ce qui ne va pas dans une marque, ou None."""
    try:
        jour = date.fromisoformat(marque["date"])
    except ValueError:
        return f"date illisible « {marque['date']} » (attendu AAAA-MM-JJ)"
    if (aujourdhui - jour).days not in range(0, 3):
        return f"date {jour} : doit être celle d'aujourd'hui ({aujourdhui}), à deux jours près, jamais dans le futur"
    source = marque["source"]
    if not (_URL.match(source) or _AUTRE.match(source)):
        return f"source « {source} » inatteignable : il faut une adresse, un DOI, un arXiv ou un ISBN"
    if not marque["auteur"]:
        return "« rédigé par » est vide"
    if adresse_a_lire(source) and len(mots(marque["extrait"])) < MOTS_EXTRAIT_MINI:
        return f"« extrait » manquant ou trop court (au moins {MOTS_EXTRAIT_MINI} mots copiés de la page lue)"
    return None
