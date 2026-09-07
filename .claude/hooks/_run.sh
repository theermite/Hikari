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
#
# ✋ CE FICHIER N'EST TENU PAR AUCUN TEST, ET C'EST DIT (2026-09-07).
# J'ai essaye d'en ecrire un ; il n'est pas fiable sur ce poste. Depuis pytest,
# Python lance un bash dont l'environnement MSYS n'est pas celui que l'outil
# emploie : le meme chemin « D:/... » s'ouvre dans l'un et pas dans l'autre, et
# `git rev-parse` y rend « /mnt/d/... » au lieu de « D:/... ». Le test echouait
# donc sur sa mise en scene, jamais sur ce script. Un test rouge pour une raison
# etrangere apprend a ignorer le rouge ; un test vert par accident est pire.
#
# CE QUI TIENT A LA PLACE — quatre scenarios rejoues A LA MAIN le 2026-09-07,
# chacun reproduisant un defaut trouve par une relecture independante :
#   1. Raccourci Store seul interprete   -> il tourne, le cache reste VIDE.
#   2. Ce raccourci se met a refuser     -> message explicite, sortie 0.
#   3. Cache pointant vers un disparu    -> se repare, reecrit le bon.
#   4. Aucun interprete                  -> trois lignes sur stderr, sortie 0.
# Refaire ces quatre-la avant toute modification de ce fichier.

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
  # Un `exec` direct sur une valeur perimee (Python desinstalle, poste change)
  # faisait sortir TOUS les garde-fous en 127 — et la sonde de sante, qui aurait
  # du le dire, passe elle-meme par ce lanceur. Trouve par la relecture
  # independante du 2026-09-06.
  #
  # ON VERIFIE LA PRESENCE, PAS L'EXECUTION. Le faire TOURNER coutait un
  # demarrage Python complet par garde-fou : 316 ms mesures, soit ~7 s par
  # commande Bash sur 22 hooks — la contre-relecture du meme jour l'a chiffre,
  # et ca annulait exactement le cache que ces lignes existent pour tenir.
  #
  # Garantie assumee, plus faible et dite : `command -v` attrape l'interprete
  # DISPARU, pas l'interprete present qui refuse. Ce second cas est celui du
  # raccourci Microsoft Store — il n'entre jamais dans ce cache parce qu'on
  # refuse de l'y ecrire (voir « RETENIR » plus bas). J'avais d'abord ecrit
  # qu'il « ne peut pas s'y trouver, deja ecarte au choix » : c'etait faux, il
  # DEVIENT le choix des qu'il est seul.
  if [ -n "$PY_CACHE" ] && command -v "$PY_CACHE" >/dev/null 2>&1; then
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
# Le dernier recours ne se MET PAS EN CACHE. Troisieme relecture independante
# du 2026-09-07 : mon propre commentaire, plus haut, affirmait que le raccourci
# Microsoft Store « ne peut pas se trouver dans ce cache ». Faux — il y entre
# des qu'il est le SEUL interprete, c'est-a-dire exactement sur le poste que ce
# fichier existe pour reparer. Fige la, il rendait 126 a chaque garde-fou sans
# jamais se reparer : le symptome d'origine, a demeure.
#
# On s'en sert pour ce tour, on ne l'ecrit pas. Le tour suivant resondera, et
# prendra un vrai interprete des qu'il y en aura un.
RETENIR="$CHOISI"
CHEMIN_RETENU="$(command -v "$CHOISI" 2>/dev/null || echo "$CHOISI")"
[ -n "$CHOISI" ] || CHOISI="$DERNIER_RECOURS"

if [ -n "$CHOISI" ]; then
  # On met en cache le CHEMIN, jamais le nom. 4e relecture independante,
  # 2026-09-07 : un cache contenant « python » se reresout par le PATH au tour
  # suivant. Si le vrai Python disparait du PATH, ce meme nom retombe sur le
  # raccourci Microsoft Store, `command -v` le trouve, et on rend 126 en
  # silence — le symptome d'origine, revenu par une autre porte. Un chemin
  # absolu disparu echoue a `command -v`, donc il se repare.
  if [ -n "$RETENIR" ]; then
    mkdir -p "$(dirname "$CACHE")" 2>/dev/null || true
    printf '%s' "$CHEMIN_RETENU" > "$CACHE" 2>/dev/null || true
  fi
  exec "$CHOISI" "$CIBLE" "$@"
fi

echo "[HOOK-INTERPRETEUR] Aucun interprete Python executable trouve (essayes : $CANDIDATS)." >&2
echo "[HOOK-INTERPRETEUR] Garde-fou NON EXECUTE : $NOM" >&2
echo "[HOOK-INTERPRETEUR] Consequence : ce controle ne garde rien pour cette session." >&2
exit 0
