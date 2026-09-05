"""Le corps d'un heredoc est une DONNEE, pas une commande.

Friction notee par Jay le 2026-08-16 (« un heredoc contenant un exemple de
commande declenche le garde-fou »), rencontree TROIS fois le 2026-09-05 :

1. une commande de demonstration citant une commande dangereuse ;
2. un message de commit qui EXPLIQUE pourquoi on ne la lance jamais ;
3. l'ecriture de ce fichier de test lui-meme.

Le garde-fou lisait le texte brut de l'entree — donc la charge utile autant que
la commande. Citer n'est pas executer. Un texte passe en donnee a `git commit -F`
n'atteint jamais un shell.

**La limite gardee volontairement** : un heredoc qui alimente un interprete
(`bash <<EOF`) reste analyse, parce que la son corps EST du code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "bash-guard.py"
_spec = importlib.util.spec_from_file_location("bash_guard_heredoc", HOOK)
bg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bg)

DANGER = "rm" + " -rf dist/"


def test_a_dangerous_command_quoted_in_a_commit_message_is_not_blocked():
    commande = (
        "git commit -F - <<'EOF'\n"
        f"fix(x): explique pourquoi on n'ecrit jamais {DANGER} sur du travail\n"
        "EOF"
    )
    assert bg.check_destructive(commande) is None


def test_a_real_deletion_is_still_blocked():
    assert bg.check_destructive(DANGER) is not None


def test_a_heredoc_that_feeds_a_shell_is_still_analysed():
    # Ici le corps est execute : il doit rester sous surveillance.
    assert bg.check_destructive(f"bash <<'EOF'\n{DANGER}\nEOF") is not None


def test_the_command_before_a_heredoc_is_still_analysed():
    # Le danger peut vivre AVANT le heredoc, sur la meme ligne.
    commande = f"{DANGER} && git commit -F - <<'EOF'\nmessage anodin\nEOF"
    assert bg.check_destructive(commande) is not None


def test_a_command_without_heredoc_is_unchanged():
    assert bg.check_destructive("ls -la") is None
    assert bg.check_destructive("git status") is None
