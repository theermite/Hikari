#!/usr/bin/env bash
# Lanceur unique de tous les garde-fous.
#
# POURQUOI IL EXISTE. Le 2026-09-05, deux sessions ont affiche
# `Hook error: SessionStart (exit 126)` — « commande trouvee, mais pas
# executable ». Cause : `python3` pointe en premier vers le raccourci Microsoft
# Store, qui fonctionne ou refuse selon le contexte, sans rien dire. Les 55
# garde-fous l'appelaient tous. Un garde-fou qui meurt en silence ressemble
# exactement a un garde-fou vert — et c'est la promesse « tenu par du code » qui
# s'effondre, pas un detail d'outillage.
#
# CE QU'IL FAIT. Il prend le premier interprete qui S'EXECUTE VRAIMENT, pas le
# premier que le PATH nomme. `command -v` ne suffit pas : le raccourci Store
# EXISTE, il refuse seulement de tourner. La seule preuve qu'un interprete
# marche est de le faire tourner.
#
# S'IL N'EN TROUVE AUCUN. Il le DIT, fort, sur stderr, puis rend la main sans
# bloquer. Se taire serait reproduire le defaut qu'il repare.
#
# USAGE  bash .claude/hooks/_run.sh <chemin/relatif/au/hook.py> [args...]

set -u

# D6 (relecture independante 2026-09-06) : la racine se deduit de la POSITION du
# script, plus de `git`. Le script sait ou il est ; dependre de git ajoutait une
# panne dans le seul cas ou elle compte — un dossier pas encore sous git.
ICI="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Le nom est retenu AVANT le shift : sans ca, le message d erreur final ne
# pouvait plus nommer le garde-fou non execute (defaut trouve par son test).
NOM="${1:-}"
[ -n "$NOM" ] || exit 0
CIBLE="$ICI/$NOM"
shift || true

# Un garde-fou absent n'est pas une erreur : un projet peut n'avoir qu'une partie
# de la methodologie synchronisee.
[ -f "$CIBLE" ] || exit 0

# La liste est surchargeable pour qu'un test puisse EPROUVER le cas « aucun
# interprete ». Une garde qu'on ne peut pas voir rouge n'est pas une garde
# (lecon Kanee 2026-08-31).
CANDIDATS="${HOOK_PY_CANDIDATES:-python3 python py python3.13 python3.12}"

# D7 (relecture independante 2026-09-06) : sonder l'interprete coutait un
# demarrage Python complet a CHAQUE appel de garde-fou — mesure 152 ms sans
# lanceur contre 608 ms avec, sur le meme hook. Le resultat est retenu pour la
# session. Limite assumee : si l'interprete cesse de marcher en cours de route,
# la sonde de sante le dira au demarrage suivant, pas ici.
CACHE="$ICI/../state/hook-interpreter"
if [ -z "${HOOK_PY_CANDIDATES:-}" ] && [ -r "$CACHE" ]; then
  PY_CACHE="$(cat "$CACHE" 2>/dev/null || true)"
  if [ -n "$PY_CACHE" ]; then
    exec "$PY_CACHE" "$CIBLE" "$@"
  fi
fi

# Le raccourci Microsoft Store demarre 3x plus lentement qu'un vrai Python
# (mesure 2026-09-06 : 558 ms contre 169 ms, meme machine, meme commande vide).
# Il n'est donc pris qu'en DERNIER RECOURS — il reste un interprete valable
# quand c'est le seul, mais il ne doit pas coiffer les autres par sa seule
# position dans le PATH.
DERNIER_RECOURS=""
CHOISI=""
for PY in $CANDIDATS; do
  "$PY" -c "" >/dev/null 2>&1 || continue
  CHEMIN="$(command -v "$PY" 2>/dev/null || echo "$PY")"
  case "$CHEMIN" in
    *WindowsApps*) [ -n "$DERNIER_RECOURS" ] || DERNIER_RECOURS="$PY" ;;
    *) CHOISI="$PY"; break ;;
  esac
done
[ -n "$CHOISI" ] || CHOISI="$DERNIER_RECOURS"

if [ -n "$CHOISI" ]; then
  if [ -z "${HOOK_PY_CANDIDATES:-}" ]; then
    mkdir -p "$(dirname "$CACHE")" 2>/dev/null || true
    printf '%s' "$CHOISI" > "$CACHE" 2>/dev/null || true
  fi
  exec "$CHOISI" "$CIBLE" "$@"
fi

echo "[HOOK-INTERPRETEUR] Aucun interprete Python executable trouve (essayes : $CANDIDATS)." >&2
echo "[HOOK-INTERPRETEUR] Garde-fou NON EXECUTE : $NOM" >&2
echo "[HOOK-INTERPRETEUR] Consequence : ce controle ne garde rien pour cette session." >&2
exit 0
