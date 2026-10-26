#!/usr/bin/env python3
"""Le conseil arrive AVANT l'ecriture — et il laisse une trace.

Trigger
-------
PreToolUse Write/Edit sur un rapport de session (`docs/Sessions/Session-*.md`).

Regle
-----
Le rapport porte soit une contradiction emise (`[CHALLENGE] ...`), soit la
raison ecrite de n'en avoir emis aucune (`[NO-CHALLENGE] motif: <liste
fermee>`). Sans l'un des deux, l'ecriture est refusee.

Pourquoi
--------
Mesure du 2026-09-06 sur tout l'atelier : le gabarit de contradiction technique
a ete emis pour de vrai **1 fois sur 1269 rapports**. Sur les 20 dernieres
sessions : 43 decisions structurantes, 3 contradictions (dont une fausse), et
~43 defauts rattrapes APRES ecriture — un par decision prise. La regle existait
depuis des mois ; elle n'a jamais mordu, parce que rien ne la tenait.

La raison ecrite n'est pas une sortie de secours : c'est le signal. « Jay a
apporte le meilleur chemin lui-meme » est exactement ce qu'on veut voir compte,
pas efface — c'est arrive le jour meme ou cette porte a ete posee.

Le lecteur est tolerant a la mise en forme (gras, accents graves, cellule de
tableau) : une porte doit refuser un defaut de fond, jamais un defaut de
presentation. Un marqueur en gras a deja bloque silencieusement toute une serie
de tentatives.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    find_repo_root,
    format_block,
    get_file_path,
    get_tool_input,
    pass_through,
    read_hook_input,
    warn,
)

# Liste FERMEE. Une liste qu'on rallonge n'est plus une garde — chaque motif
# doit rester un signal qu'on peut compter, pas une case a cocher.
MOTIFS = (
    "aucune-decision-structurante",
    "chemin-unique-impose",
    "contradiction-portee-par-jay",
    "session-de-correction-dirigee",
)

# Le chemin arrive tantot absolu, tantot relatif au depot : les deux comptent.
_RAPPORT_RE = re.compile(r"(?:^|\\)docs\\Sessions\\Session-[^\\]*\.md$", re.I)
_CHALLENGE_RE = re.compile(r"\[CHALLENGE\]", re.I)
_NO_CHALLENGE_RE = re.compile(
    r"\[NO-CHALLENGE\][\s`*_|]*motif\s*:\s*([a-z0-9-]+)", re.I
)


def is_session_report(chemin: str) -> bool:
    """Vrai pour un rapport de session, faux pour tout le reste du depot."""
    if not chemin:
        return False
    return bool(_RAPPORT_RE.search(chemin.replace("/", "\\")))


def trace(contenu: str) -> str | None:
    """La trace portee par le texte, ou None s'il n'y en a pas de valable."""
    if not contenu:
        return None
    if _CHALLENGE_RE.search(contenu):
        return "challenge"
    m = _NO_CHALLENGE_RE.search(contenu)
    if m and m.group(1).lower() in MOTIFS:
        return m.group(1).lower()
    return None


_REPROCHES_RE = re.compile(r"reproches?\s+de\s+livraison", re.I)
# Une reponse, pas un titre : soit « aucun », soit une parole rapportee.
_REPONSE_RE = re.compile(r"\baucun\b|[«\"']", re.I)


def complaints_section(contenu: str) -> bool:
    """La section « Reproches de livraison » existe ET dit quelque chose.

    Un titre vide serait une case a cocher. On exige donc une reponse dans les
    lignes qui suivent : « aucun », ou la parole de Jay rapportee.

    Pourquoi : 5 reproches en 20 sessions, 3 d'entre eux APRES le correctif
    cense les fermer. Le signal etait documente a chaque fois et n'entrait dans
    aucun score, donc rien ne changeait.
    """
    if not contenu:
        return False
    m = _REPROCHES_RE.search(contenu)
    if not m:
        return False
    suite = contenu[m.end():m.end() + 400]
    # On s'arrete au titre suivant : ce qui appartient a une autre section ne
    # repond pas pour celle-ci.
    coupe = re.split(r"\n\s*#{1,6}\s", suite)[0]
    return bool(_REPONSE_RE.search(coupe))


# « Toute règle créée est annoncée » (Jay, 2026-10-13): « ce n'est pas la première fois que tu crées des
# règles sans réellement me consulter, sans réellement me notifier ». Le rapport nomme chaque règle,
# annexe, garde-fou ou compétence posé dans la séance.
CHEMINS_DE_REGLES = (
    ".claude/rules/", ".claude/rules-ondemand/", ".claude/hooks/guards/", ".claude/hooks/quality/",
    ".claude/hooks/lifecycle/", ".claude/skills/", ".claude/settings.json",
)
_TITRE_REGLES_RE = re.compile(r"^[ \t]*#{1,6}[ \t]*[*_ ]*r[eè]gles?[ \t]+pos[eé]es?\b.*$", re.I | re.M)
_AUCUNE_RE = re.compile(r"^\W*aucune?\b", re.I)


def _corps_regles(contenu: str) -> str:
    """Le texte de la section « Règles posées » (jusqu'au titre suivant), vide s'il n'y en a pas."""
    m = _TITRE_REGLES_RE.search(contenu or "")
    if not m:
        return ""
    return re.split(r"\n[ \t]*#{1,6}[ \t]", contenu[m.end():m.end() + 1500])[0].strip()


def rules_section(contenu: str) -> bool:
    """La section existe ET répond: « aucune », ou la liste de ce qui a été posé."""
    return bool(_corps_regles(contenu))


def dit_aucune(contenu: str) -> bool:
    return bool(_AUCUNE_RE.match(_corps_regles(contenu)))


def _git(racine: Path, *args: str) -> list[str]:
    try:
        sortie = subprocess.run(["git", "-C", str(racine), *args], capture_output=True, text=True,
                                encoding="utf-8", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    return [ligne.strip() for ligne in sortie.stdout.splitlines() if ligne.strip()] if sortie.returncode == 0 else []


def regles_touchees(racine: Path | None = None) -> list[str]:
    """Les fichiers de règles changés depuis le dernier rapport de séance (validés ou non)."""
    racine = Path(racine) if racine else find_repo_root()
    dernier = _git(racine, "log", "-1", "--format=%H", "--", "docs/Sessions")
    if not dernier:
        return []
    chemins = list(CHEMINS_DE_REGLES)
    fichiers = (_git(racine, "diff", "--name-only", f"{dernier[0]}..HEAD", "--", *chemins)
                + _git(racine, "diff", "--name-only", "HEAD", "--", *chemins)
                + _git(racine, "ls-files", "--others", "--exclude-standard", "--", *chemins))
    return sorted(set(fichiers))


def verdict(chemin: str, contenu: str) -> str | None:
    """Le message de refus, ou None quand la porte laisse passer. `contenu` est le rapport COMPLET."""
    if not is_session_report(chemin):
        return None
    if not contenu.strip():
        # Squelette vide : la porte se pose au contenu, pas au geste.
        return None
    if not trace(contenu):
        return _refus_trace()
    if not complaints_section(contenu):
        return _refus_reproches()
    if not rules_section(contenu):
        return _refus_regles()
    return None


def avertissement(chemin: str, contenu: str, touchees: list[str] | None = None) -> str | None:
    """« aucune » règle posée alors que le dépôt montre des règles changées: un avis, jamais un refus.

    Constat de relecture (2026-10-26): `git diff` voit aussi le travail d'une AUTRE séance menée en parallèle,
    donc le dépôt ne prouve pas que CETTE séance a posé ces règles. Le doute se signale; il ne bloque pas.
    """
    if not is_session_report(chemin) or not dit_aucune(contenu):
        return None
    touchees = regles_touchees() if touchees is None else touchees
    if not touchees:
        return None
    liste = "\n".join(f"  - {f}" for f in touchees[:10]) + ("\n  - …" if len(touchees) > 10 else "")
    return ("Le rapport dit « aucune » règle posée, mais le dépôt montre des fichiers de règles changés depuis "
            "le dernier rapport (peut-être par une autre séance menée en parallèle) :\n" + liste +
            "\nSi l'un d'eux vient de cette séance, le nommer dans « Règles posées » "
            "(ce qu'il fait, pourquoi, décision de Jay).")


def _appliquer(texte: str, edits: list[dict]) -> str | None:
    for e in edits:
        ancien, nouveau = e.get("old_string", ""), e.get("new_string", "")
        if not ancien or ancien not in texte:
            return None
        texte = texte.replace(ancien, nouveau) if e.get("replace_all") else texte.replace(ancien, nouveau, 1)
    return texte


def contenu_complet(data: dict) -> str | None:
    """Le rapport tel qu'il sera sur le disque après l'appel; None si on ne peut pas le savoir.

    Un `Edit` ne porte que le morceau changé: le juger sur ce morceau refuse une faute de frappe corrigée dans un
    rapport complet (constat de relecture, 2026-10-26). Si l'édition ne s'applique pas, la porte ne juge pas:
    l'outil lui-même échouera.
    """
    entree = get_tool_input(data)
    if data.get("tool_name") == "Write" or "content" in entree:
        return entree.get("content") or ""
    try:
        actuel = Path(get_file_path(data)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):   # un rapport illisible n'est pas jugé: la porte ne plante pas
        return None
    return _appliquer(actuel, entree.get("edits") or [entree])


def _refus_regles() -> str:
    return format_block(
        reason=(
            "rapport de session sans section « Règles posées ». Reproche de Jay (2026-10-13) : des règles "
            "créées « sans réellement me consulter, sans réellement me notifier »."
        ),
        recovery=(
            "Ajouter la section au rapport :\n"
            "  ## Règles posées\n"
            "  aucune\n"
            "OU la liste de chaque règle, annexe, garde-fou ou compétence créé ou modifié dans la séance : "
            "ce qu'il fait, pourquoi, et ce que Jay a décidé (ou « à valider »)."
        ),
        reference=".claude/rules/01-Lecture.md § 5 (ce qui se transmet avec chaque réponse)",
    )


def _refus_trace() -> str:
    return format_block(
        reason=(
            "rapport de session sans trace de conseil. Mesure : le gabarit de "
            "contradiction technique a ete emis 1 fois sur 1269 rapports, "
            "pendant que ~43 defauts etaient rattrapes APRES ecriture."
        ),
        recovery=(
            "Ajouter au rapport SOIT la contradiction emise :\n"
            "  [CHALLENGE] <ce qui a ete contredit, et ce qui en est sorti>\n"
            "SOIT la raison de n'en avoir emis aucune, motif dans la liste "
            "fermee :\n"
            f"  [NO-CHALLENGE] motif: <{' | '.join(MOTIFS)}>\n"
            "La raison n'est pas une sortie de secours : c'est le signal."
        ),
        reference="rules/Honesty.md — Active Technical Challenge",
    )


def _refus_reproches() -> str:
    return format_block(
        reason=(
            "rapport de session sans section « Reproches de livraison » remplie. "
            "Mesure : 5 reproches en 20 sessions, dont 3 APRES le correctif cense "
            "les fermer — le signal n'entrait dans aucun score."
        ),
        recovery=(
            "Ajouter la section au rapport :\n"
            "  ## Reproches de livraison\n"
            "  aucun\n"
            "OU, s'il y en a eu, la parole de Jay mot pour mot, la cause trouvee, "
            "et ce qui a change. -10 Valeur par occurrence."
        ),
        reference="rules/Workflows.md — Scoring V2",
    )


def main() -> None:
    _, data = read_hook_input()
    chemin, contenu = get_file_path(data), contenu_complet(data)
    if contenu is None:
        pass_through()
    message = verdict(chemin, contenu)
    if message:
        block(message)
    avis = avertissement(chemin, contenu)
    if avis:
        warn(avis)
    pass_through()


if __name__ == "__main__":
    main()
