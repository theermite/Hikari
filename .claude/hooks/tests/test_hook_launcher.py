"""Tests du lanceur `_run.sh` et de la sonde de sante des garde-fous.

Origine mesuree le 2026-09-05 : deux sessions ont affiche
`Hook error: SessionStart (exit 126)`. 126 = commande trouvee, mais pas
executable. `python3` pointe en premier vers le raccourci Microsoft Store, qui
fonctionne ou refuse selon le contexte, sans rien dire. Les 55 garde-fous
l'appelaient tous.

Un garde-fou qui meurt en silence ressemble exactement a un garde-fou vert.
Meme famille que « une integration continue silencieuse ressemble a une
integration verte » (Manabi, 2026-09-01) — sauf qu'ici elle attaque le socle
entier de la methodologie, pas un projet.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
DEPOT = HOOKS.parents[1]
LANCEUR = HOOKS / "_run.sh"
SONDE = HOOKS / "lifecycle" / "hook-health-check.py"

_spec = importlib.util.spec_from_file_location("hook_health_check", SONDE)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

BASH = r"C:\Program Files\Git\usr\bin\bash.exe"


def _lance(args, entree=""):
    return subprocess.run([BASH, str(LANCEUR), *args], input=entree,
                          capture_output=True, text=True, cwd=str(DEPOT), timeout=60)


# --- les fins de ligne du lanceur --------------------------------------------
#
# Mesure du 2026-09-07 : `_run.sh` voyageait avec des CRLF. Un bash strict rend
# alors `$'\r': command not found` puis le code 2 — qui vaut REFUS pour l'outil.
# Un lanceur casse ne desarme pas UN garde-fou, il les bloque TOUS, sur chaque
# depot receveur. Le correctif existait sans un seul test capable de rougir : on
# pouvait l'annuler et la suite entiere restait verte.


def test_le_lanceur_n_a_aucun_retour_chariot():
    """Les octets du fichier, pas la promesse d'un `.gitattributes`.

    C'est le FICHIER DE TRAVAIL que la propagation copie, jamais la version du
    depot : seuls ses octets reels disent la verite.
    """
    assert b"\r" not in LANCEUR.read_bytes()


def test_une_regle_de_fin_de_ligne_voyage_avec_les_garde_fous():
    """La regle doit ARRIVER chez le receveur, pas seulement proteger la source.

    Le `.gitattributes` racine de Kata ne voyage pas : la propagation ne copie
    que `.claude/{rules,rules-ondemand,agents,hooks,skills}`. Sans regle DANS le
    dossier propage, un receveur Windows (`core.autocrlf=true`, defaut systeme)
    reintroduit les CRLF au premier clone ou `reset --hard`, et le defaut
    revient a l'identique.
    """
    regle = HOOKS / ".gitattributes"
    assert regle.is_file(), "aucune regle de fin de ligne dans le dossier propage"
    texte = regle.read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in texte


# --- le lanceur --------------------------------------------------------------


def test_launcher_runs_the_target_hook():
    proc = _lance(["tests/_fixtures/echo_ok.py"])
    assert proc.returncode == 0
    assert "GARDE-FOU-EXECUTE" in proc.stdout


def test_launcher_passes_stdin_through():
    proc = _lance(["tests/_fixtures/echo_stdin.py"], entree='{"cle": "valeur"}')
    assert "valeur" in proc.stdout


def test_a_missing_hook_is_not_an_error():
    # Un projet peut n'avoir qu'une partie de la methodologie synchronisee.
    proc = _lance(["quality/nexiste-pas.py"])
    assert proc.returncode == 0
    assert proc.stderr.strip() == ""


def test_launcher_is_loud_when_no_interpreter_runs():
    """Le cas reel du 2026-09-05, reproduit : aucun interprete ne s'execute.

    On ne vide pas le PATH — ca emporterait le shell lui-meme, et le test
    prouverait autre chose. On remplace la liste des candidats par des noms qui
    n'existent pas : c'est exactement la condition qu'on veut eprouver.
    """
    import os
    env = dict(os.environ, HOOK_PY_CANDIDATES="python-qui-nexiste-pas python-non-plus")
    proc = subprocess.run([BASH, str(LANCEUR), "tests/_fixtures/echo_ok.py"],
                          capture_output=True, text=True, cwd=str(DEPOT), timeout=60, env=env)
    assert proc.returncode == 0                      # il ne bloque jamais...
    assert "HOOK-INTERPRETEUR" in proc.stderr        # ...mais il le DIT.
    assert "NON EXECUTE" in proc.stderr              # ...et il nomme la consequence.
    assert "GARDE-FOU-EXECUTE" not in proc.stdout    # ...et le hook n'a pas tourne.


# --- la sonde de sante -------------------------------------------------------


def test_probe_finds_a_working_interpreter():
    etat = mod.diagnostiquer()
    assert etat["interprete"] is not None
    assert etat["version"]


def test_probe_counts_the_configured_hooks():
    """Le seuil est haut EXPRES.

    A sa premiere execution reelle, la sonde a affiche « 0 configures ·
    operationnels » : son motif ne reconnaissait pas la forme citee du lanceur.
    Un `> 0` aurait laisse passer un compte de 1. Le depot en a des dizaines —
    si ce chiffre s'effondre, c'est que la sonde ne lit plus la configuration.
    """
    etat = mod.diagnostiquer()
    assert etat["hooks_configures"] > 20, etat


def test_probe_reads_the_quoted_launcher_form(tmp_path):
    # La forme reelle ecrite dans settings.json : le guillemet colle au nom.
    reglages = tmp_path / "settings.json"
    reglages.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command",
         "command": 'bash "$(git rev-parse --show-toplevel)/.claude/hooks/_run.sh" guards/x.py'}]}]}}),
        encoding="utf-8")
    etat = mod.diagnostiquer(reglages=reglages, racine=tmp_path)
    assert etat["hooks_configures"] == 1, etat


def test_probe_reports_hooks_whose_file_is_missing(tmp_path):
    reglages = tmp_path / "settings.json"
    reglages.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": 'bash .claude/hooks/_run.sh guards/fantome.py'}]}]}}),
        encoding="utf-8")
    etat = mod.diagnostiquer(reglages=reglages, racine=tmp_path)
    assert "guards/fantome.py" in etat["fichiers_absents"]


def test_probe_message_names_the_consequence():
    # Un diagnostic qui dit « KO » sans dire ce que ca coute ne declenche rien.
    message = mod.message(mod.diagnostiquer())
    assert "garde" in message.lower()


def test_probe_never_blocks_the_session():
    decision = mod.build_decision()
    texte = json.dumps(decision) if decision else ""
    assert '"continue": false' not in texte
    assert "deny" not in texte
