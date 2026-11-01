"""Un avertissement de garde-fou doit ATTEINDRE le modele (2026-10-30).

Constat : un garde qui ecrit son avertissement sur stderr et sort 0 n'est vu que dans un journal ; le modele n'en
lit rien. Les avertissements Lego et traductions etaient donc muets : 367 fichiers sur 3 695 importent la
bibliotheque, 362 portent du texte en dur sans traduction. Le canal qui atteint le modele est le JSON
`hookSpecificOutput.additionalContext` (celui du masque de secrets), lu seulement quand la sortie est 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
LIB = HOOKS / "lib"


def _courir(script: Path, entree: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script)], input=json.dumps(entree), capture_output=True, text=True,
                          timeout=30, cwd=str(cwd) if cwd else None)


def _mini_hook(tmp_path: Path, corps: str) -> Path:
    chemin = tmp_path / "mini.py"
    chemin.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(LIB)!r})\n"
        "from common import read_hook_input, warn\n"
        "read_hook_input()\n" + textwrap.dedent(corps), encoding="utf-8")
    return chemin


def _contexte(sortie: subprocess.CompletedProcess) -> dict:
    return json.loads(sortie.stdout)["hookSpecificOutput"]


def test_a_warning_reaches_the_model_in_the_events_that_accept_context(tmp_path):
    hook = _mini_hook(tmp_path, 'warn("WARNING: un"); warn("WARNING: deux"); sys.exit(0)\n')
    for evenement in ("PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart"):
        sortie = _courir(hook, {"hook_event_name": evenement})
        sortant = _contexte(sortie)
        assert sortant["hookEventName"] == evenement and sortie.returncode == 0, evenement
        assert "un" in sortant["additionalContext"] and "deux" in sortant["additionalContext"], evenement


def test_two_warnings_are_one_json_document(tmp_path):
    hook = _mini_hook(tmp_path, 'warn("a"); warn("b"); sys.exit(0)\n')
    sortie = _courir(hook, {"hook_event_name": "PreToolUse"})
    assert len(sortie.stdout.strip().splitlines()) == 1


def test_the_warning_stays_on_stderr_for_the_human(tmp_path):
    hook = _mini_hook(tmp_path, 'warn("WARNING: visible"); sys.exit(0)\n')
    assert "WARNING: visible" in _courir(hook, {"hook_event_name": "PreToolUse"}).stderr


def test_an_event_that_takes_no_context_gets_no_json(tmp_path):
    hook = _mini_hook(tmp_path, 'warn("x"); sys.exit(0)\n')
    for evenement in ("Stop", "SessionEnd", "PreCompact", ""):
        assert _courir(hook, {"hook_event_name": evenement} if evenement else {}).stdout.strip() == "", evenement


def test_no_warning_means_no_output(tmp_path):
    hook = _mini_hook(tmp_path, "sys.exit(0)\n")
    assert _courir(hook, {"hook_event_name": "PreToolUse"}).stdout == ""


def test_the_exit_code_the_hook_chose_is_kept(tmp_path):
    for code in (0, 1, 2):
        hook = _mini_hook(tmp_path, f'warn("x"); sys.exit({code})\n')
        assert _courir(hook, {"hook_event_name": "PreToolUse"}).returncode == code


# --- les gardes reels : Lego et traductions -----------------------------------------------------------------

_DEMO = "export function MaCarteUnique() {\n  return <p>%s</p>;\n}\n"


def _ecriture(texte: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Write",
            "tool_input": {"file_path": "C:/projet/src/Carte.tsx", "content": _DEMO % texte}}


def test_the_i18n_guard_reaches_the_model():
    sortie = _courir(HOOKS / "lego" / "i18n-no-hardcode.py", _ecriture("Bonjour tout le monde ici present"))
    assert "hardcoded UI text" in _contexte(sortie)["additionalContext"] and sortie.returncode == 0


def test_a_write_guard_warning_reaches_the_model():
    entree = {"hook_event_name": "PreToolUse", "tool_name": "Write",
              "tool_input": {"file_path": "C:/projet/Dockerfile", "content": "FROM node:20\n"}}
    sortie = _courir(HOOKS / "guards" / "write-guard.py", entree)
    assert "Docker image version" in _contexte(sortie)["additionalContext"] and sortie.returncode == 0


def test_french_text_with_accents_is_caught_by_the_i18n_guard():
    sortie = _courir(HOOKS / "lego" / "i18n-no-hardcode.py", _ecriture("Bienvenue, ton espace est prêt à l'emploi !"))
    assert "hardcoded" in _contexte(sortie)["additionalContext"].lower()


def test_a_translated_component_gets_no_warning():
    entree = _ecriture("{t('carte:titre')}")
    assert _courir(HOOKS / "lego" / "i18n-no-hardcode.py", entree).stdout.strip() == ""


def test_a_blocking_message_still_blocks_without_json():
    entree = {"hook_event_name": "PreToolUse", "tool_name": "Write",
              "tool_input": {"file_path": "C:/projet/src/Button.tsx",
                             "content": "export function Button() { return <button>x</button>; }\n"}}
    sortie = _courir(HOOKS / "guards" / "write-guard.py", entree)
    assert sortie.returncode == 2 and "already exists in @shinkofa/ui" in sortie.stderr and sortie.stdout.strip() == ""


def test_the_frozen_copy_alert_does_not_print_two_documents():
    source = (HOOKS / "guards" / "frozen-copy-alert.py").read_text(encoding="utf-8")
    assert "additionalContext" not in source, "common.warn s'en charge : un second JSON ferait refuser la sortie"
