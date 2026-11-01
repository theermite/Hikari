#!/usr/bin/env python3
"""Permission-ask check — Stop hook. Jay n'est pas le tampon qui autorise ce que le mandat laisse à Takumi.

Reproche de Jay (2026-11-01): des séances attendent qu'on leur dise qu'elles ont le droit de commiter, de mettre
en ligne ou de passer à l'étape suivante, alors qu'un développement demandé l'est jusqu'au bout ; et une séance de
paiement qui détient l'API Stripe lui demande d'ouvrir Stripe pour y faire des gestes. Mesure : 60 demandes
d'autorisation sur 2104 fins de tour des trois derniers jours.

Le mandat (règle 01 § 2) ne laisse que cinq arrêts : choix de goût, acte irréversible ou sortant, blocage, secret
manquant, tiers engagé.

Méthode (changée le 2026-11-01 après deux relectures FAIL de la même famille). La première version devinait les
arrêts légitimes à partir de mots (« refusé », « piste », « supprimé »…) : un mot loin de la question l'excusait,
et 5 vraies demandes sur 10 « excusées » l'étaient à tort. Un mot ne dit pas si un arrêt est vrai. Donc la séance
le DÉCLARE, sur une ligne qui ouvre sa ligne, motif fermé et raison dite :

    [ARRET] sortant|secret|blocage|tiers|gout|quoi|plan|perimetre : <la raison, en trois mots ou plus>

Les cinq premiers sont les arrêts du mandat (règle 01 § 2) ; les trois autres sont ce que les règles laissent en
plus à Jay : le quoi (règle 01 § 3), le plan (règle 02 § 1), un travail non demandé (annexe Conduite). Troisième
relecture FAIL : sans eux, 57 % des blocages visaient une question légitime.

Le garde ne bloque que ce qui ressemble à une demande d'autorisation (ou à « ouvre le tableau de bord du
fournisseur ») et ne porte pas cette déclaration. Une fois par tour (stop_hook_active). Une déclaration fausse se voit
dans la réponse que Jay lit ; le garde ne la juge pas. Limites écrites : la détection de la demande est lexicale (une
question déguisée passe) ; un vrai arrêt non déclaré est arrêté une fois et passe au second essai.
Contrat du hook Stop vérifié le 2026-11-01 (code.claude.com/docs/en/hooks) : exit 2 + stderr fait continuer le tour.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402

MESSAGES = {
    "permission": (
        "Tu demandes à Jay la permission de faire quelque chose. Si la question est de celles que les règles lui "
        "laissent, déclare-la sur une ligne qui ouvre sa ligne : "
        "[ARRET] sortant|secret|blocage|tiers|gout|quoi|plan|perimetre : <l'acte, la cause exacte, ce qui manque, qui "
        "est engagé, ou ce qui est ambigu>. Les cinq arrêts du mandat (règle 01 § 2) : sortant (irréversible ou qui "
        "part), secret (une valeur qui te manque), blocage (cause exacte), tiers (autrui engagé), gout (vraie "
        "alternative, toutes les options). Et ce que les règles lui laissent en plus : quoi (l'ambiguïté porte sur "
        "ce qu'il faut obtenir, règle 01 § 3), plan (il juge le plan des briques, règle 02 § 1), perimetre (le "
        "travail n'est pas dans ce qui a été demandé). Puis arrête-toi. Sinon, fais-le : un commit, une mise en "
        "ligne sur son serveur avec test de fumée, une doc à jour, un choix d'implémentation, l'étape suivante "
        "d'un travail demandé ne s'autorisent pas. Si la question porte sur le comment et que tu as une "
        "recommandation, applique-la. Rends compte ensuite (fait, vérifié avec la commande et sa sortie, fils "
        "ouverts). Réécris ta réponse."
    ),
    "handoff": (
        "Tu dis à Jay d'aller faire un geste chez un fournisseur. L'as-tu fait toi-même (API, ligne de commande, "
        "navigateur intégré, outil connecté) ? Si oui et que ça échoue, déclare-le : "
        "[ARRET] blocage|secret|tiers : <ce que tu as essayé et la cause exacte>, avec les autres issues. "
        "Si tu ne l'as pas essayé, fais-le. Il ne reste à Jay que le consentement d'un tiers, une double "
        "authentification, la valeur d'un secret ou un geste physique. Réécris ta réponse."
    ),
}

_TAIL = 700
_MOTIFS = ("sortant", "secret", "blocage", "tiers", "gout", "goût", "quoi", "plan", "perimetre", "périmètre")
# La déclaration ouvre sa ligne (hors code), à la mise en forme près (gras, puce, citation, emoji), motif fermé, raison
# d'au moins trois mots qui n'est pas le gabarit recopié (« <…> »).
_DECLARATION = re.compile(
    r"(?im)^[ \t>*\-•\W]{0,12}\[ARR[EÊ]T\]\W{0,3}[ \t]*(?:" + "|".join(_MOTIFS) + r")[ \t  ]*:[ \t]*"
    r"(?![^\n]*<[^>\n]*>)\S+(?:[ \t]+\S+){2,}"
)

_WISH = (r"veux-tu|souhaites-tu|voulez-vous|souhaitez-vous|tu veux que|dois-je|puis-je|peux-je|ok pour|d'accord pour|"
         r"do you want|want me to|should i|shall i|ready to|go ahead")
_ACT = (r"lance|continue|commite|commit|pousse|push|merge|déploie|deploie|passe|poursuis|démarre|commence|enchaîne|"
        r"mets|fais|termine|finalise|prépare|corrige|relis|teste|range|ajoute|écris|attaque|procède|vais|occupe|aller")
_SHORT = (r"on (?:y va|lance|continue|commite|enchaîne|passe|déploie|pousse|merge)|ça te va|ça te convient|"
          r"ça marche pour toi|tu valides|tu confirmes|tu es d'accord|feu vert")
_ASK = re.compile(
    r"(?i)\b(?:" + _WISH + "|" + _SHORT + r")\b|(?<![\w'])(?:je|j')\s?(?:peux\s)?(?:(?:le|la|les|l'|y|m'en|m'y|en)\s?)?"
    r"(?:" + _ACT + r")\w*\b|\b(?:ton|ta) (?:accord|go|validation|feu vert)\b|^\W*go\W*$"
)
_WAIT = re.compile(
    r"(?i)\b(?:dis-moi (?:quand tu veux que|si tu veux)|j'attends (?:ton|ta) (?:go|accord|feu vert|validation|retour)|"
    r"tu me dis quand (?:je|on) peux)\b"
)
_QUOTED = re.compile("«[^»]*»|“[^”]*”|\"[^\"\\n]{0,200}\"")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")

_UI_ASK = re.compile(
    r"(?i)(?<![\w'])(ouvre|ouvrez|va (?:sur|dans)|allez (?:sur|dans)|clique|cliquez|connecte-toi|connectez-vous|"
    r"rends-toi (?:sur|dans))\b"
)
# Un fournisseur (qui a une API) nommé, ou son adresse, dans la même phrase qu'un geste à faire dans son interface.
_PROVIDER = re.compile(
    r"(?i)\b(?:stripe|github|ovh(?:cloud)?|google|cloudflare|brevo|vercel|notion|slack|sentry|glitchtip|postiz|linear|"
    r"figma|o2switch|twitch|telegram|paypal|umami|hetzner|aws|azure)\b|\bdashboard\.\w+\.\w+"
)
_UI_GESTURE = re.compile(r"(?i)\b(?:clique|cliquez|tableau de bord|dashboard|interface|console|paramètres|settings)\b")


def declared(reply: str) -> bool:
    """Une déclaration `[ARRET]` valide ouvre une ligne de la réponse, hors bloc de code."""
    return bool(_DECLARATION.search(_FENCE.sub(" ", reply).split("```")[0]))


def _clean(sentence: str) -> str:
    """La phrase sans mise en forme (gras, emoji, parenthèse finale) pour savoir si elle se termine par « ? »."""
    plain = re.sub(r"[*_`❓]", "", sentence).strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", plain).strip()


def _sentences(text: str) -> list[str]:
    body = _QUOTED.sub(" ", _FENCE.sub(" ", text))[-_TAIL:]
    return [x.strip() for x in _SENTENCE.split(body) if x.strip()]


_ANSWER = re.compile(r"(?i)^(?:oui|non|pas|rien|aucun|aucune|bien sûr|d'accord|[abc])\b")


def _is_an_answer(following: str) -> bool:
    """Une phrase courte qui commence comme une réponse (« Non. », « Pas encore. ») suit la question et la clôt."""
    if not following or following.endswith("?") or _WAIT.search(following):
        return False
    return len(following.split()) <= 3 and bool(_ANSWER.match(following))


def _questions(text: str) -> list[str]:
    """Les phrases interrogatives de la fin du message, hors citations et hors question qui se répond elle-même."""
    sentences = _sentences(text)[-6:]
    following = sentences[1:] + [""]
    return [s for s, nxt in zip(sentences, following) if _clean(s).endswith("?") and not _is_an_answer(nxt)]


def _asks_permission(text: str) -> bool:
    return any(_ASK.search(_clean(q)) for q in _questions(text)) or bool(_WAIT.search(_QUOTED.sub(" ", text)[-_TAIL:]))


def _is_handoff(text: str) -> bool:
    """Le verbe d'action et le lieu chez un fournisseur dans la MÊME phrase."""
    return any(_UI_ASK.search(s) and _PROVIDER.search(s) and _UI_GESTURE.search(s) for s in _sentences(text))


def classify(reply: str) -> str | None:
    """"permission", "handoff" ou None."""
    text = reply.replace("\u2019", "'")
    if declared(text):
        return None
    if _is_handoff(text):
        return "handoff"
    return "permission" if _asks_permission(text) else None


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    kind = classify(reply) if isinstance(reply, str) else None
    if kind:
        block(MESSAGES[kind])
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[permission-ask-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
