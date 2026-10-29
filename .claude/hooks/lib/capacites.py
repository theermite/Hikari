"""Les capacités que les règles supposent, et ce qu'un garde-fou peut en dire.

Une règle qui exige un outil absent produit une déclaration fausse (`[VEILLE] … via <source>` sans
accès web). Au démarrage, l'état des capacités est donc dit — jamais silencieusement dégradé.

Limite assumée: un garde-fou ne voit pas les outils réellement chargés par le harnais. Il lit ce qui est
DÉCLARÉ (serveurs MCP dans la configuration), ce qui est REFUSÉ (règle de refus dans les réglages) et ce
qui est PRÉSENT (commande sur la machine). « Déclarée » n'est pas « connectée »: seul le harnais sait si un
serveur répond, et c'est au modèle de le confirmer d'après sa propre liste d'outils.
"""

from __future__ import annotations

import json
from pathlib import Path

LIBELLES = {
    "declaree": "déclarée",
    "non-declaree": "non déclarée",
    "refusee": "refusée par les réglages",
    "non-verifiable": "non vérifiable",
    "integree": "intégrée à l'application, présumée présente",
}


def _lire(chemin: Path) -> dict | None:
    """Le contenu d'un fichier JSON; {} s'il est absent; None s'il existe mais ne se lit pas."""
    if not chemin.is_file():
        return {}
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return donnees if isinstance(donnees, dict) else None


def _json(chemin: Path) -> dict:
    return _lire(chemin) or {}


def configurations_illisibles(home: Path, projet: Path) -> set[str]:
    """Les fichiers de configuration MCP qui existent mais ne se lisent pas: leurs serveurs sont inconnus, pas absents."""
    return {c.name for c in (Path(home) / ".claude.json", Path(projet) / ".mcp.json") if _lire(c) is None}


def serveurs_mcp(home: Path, projet: Path) -> set[str]:
    """Les serveurs MCP déclarés pour ce projet (configuration utilisateur, du projet, `.mcp.json`)."""
    utilisateur = _json(Path(home) / ".claude.json")
    du_projet = (utilisateur.get("projects") or {}).get(str(projet), {}) or {}
    sources = (utilisateur, du_projet, _json(Path(projet) / ".mcp.json"))
    return {nom for s in sources for nom in (s.get("mcpServers") or {})}


def outils_refuses(home: Path, projet: Path) -> set[str]:
    """Les outils interdits en bloc par une règle de refus (`WebSearch`), pas les motifs (`Bash(rm:*)`)."""
    refus: set[str] = set()
    for chemin in (Path(home) / ".claude/settings.json", Path(projet) / ".claude/settings.json",
                   Path(projet) / ".claude/settings.local.json"):
        regles = (_json(chemin).get("permissions") or {}).get("deny") or []
        refus |= {r for r in regles if isinstance(r, str) and "(" not in r}
    return refus


def _etat(preuve: dict, mcp: set[str], refuses: set[str], commandes: set[str], illisibles: set[str]) -> str:
    if not preuve:
        return "non-verifiable"
    if set(preuve.get("outils", [])) & refuses:
        return "refusee"
    if "outils" in preuve:
        return "non-verifiable"   # un outil intégré: l'absence d'un refus ne prouve pas sa présence
    attendus, present = (preuve.get("mcp"), mcp) if "mcp" in preuve else (preuve.get("commandes"), commandes)
    if set(attendus or []) & present:
        return "declaree"
    return "non-verifiable" if illisibles and "mcp" in preuve else "non-declaree"


def diagnostiquer(registre: list[dict], serveurs_mcp: set[str], outils_refuses: set[str],
                  commandes: set[str], illisibles: set[str] = frozenset()) -> list[dict]:
    return [{**c, "etat": _etat_complet(c, serveurs_mcp, outils_refuses, commandes, illisibles)} for c in registre]


def _etat_complet(c: dict, mcp: set[str], refuses: set[str], commandes: set[str], illisibles: set[str]) -> str:
    """Une capacité fournie par l'application (outil intégré) est présumée présente, sauf refus lisible.

    2026-10-28 : « non vérifiable → [VEILLE-IMPOSSIBLE] » a fait déclarer l'absence de la recherche web par deux
    séances, alors que WebSearch et WebFetch existent (outils différés, à charger par ToolSearch).
    """
    etat = _etat(c.get("preuve", {}), mcp, refuses, commandes, illisibles)
    return "integree" if c.get("integree") and etat != "refusee" else etat


def resume(diagnostic: list[dict], illisibles: set[str] = frozenset()) -> str:
    """Quelques lignes pour le démarrage: ce qui manque ou est incertain, avec sa dégradation."""
    bien = [c["nom"] for c in diagnostic if c["etat"] == "declaree"]
    lignes = ["Capacités (déclarée ≠ connectée) : confirme-les d'après les outils réellement chargés, "
              "et écris l'état en première ligne du rapport."]
    if illisibles:
        lignes.append(f"Configuration illisible ({', '.join(sorted(illisibles))}) : les serveurs MCP ne peuvent pas "
                      "être lus — ils sont non vérifiables, pas absents.")
    if bien:
        lignes.append("Déclarées : " + ", ".join(bien) + ".")
    for c in diagnostic:
        if c["etat"] == "integree":
            lignes.append(f"- {c['nom']} — {LIBELLES['integree']} : {c['confirmation']} ; {c['degradation']}.")
        elif c["etat"] != "declaree":
            note = f" ({c['note']})" if c.get("note") else ""
            conduite = c.get("degradation_refusee") if c["etat"] == "refusee" else None
            lignes.append(f"- {c['nom']} — {LIBELLES[c['etat']]}{note} → {conduite or c['degradation']}.")
    return "\n".join(lignes)
