"""Les avertissements qui n'ont pas de refus derrière arrivent AU MODÈLE, pas seulement dans la console de Jay.

Constat du 2026-10-30 (lego, traductions) étendu aux garde-fous restants : un avertissement écrit sur stderr avec une sortie 0
n'est vu que dans un journal. Sondé le 2026-11-02 : bash-guard (version précise dans un install, message de commit hors
convention, trailer de commit absent) et post-write-guard (console.log, fichier trop long, test vide…) parlaient dans le vide :
le trailer exigé par le dépôt est resté inconnu du modèle pendant toute une séance.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]


def _run(script: str, payload: dict, cwd: Path):
    return subprocess.run([sys.executable, str(HOOKS / script)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, cwd=str(cwd))


def _context(done) -> str:
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"] if done.stdout.strip() else ""


def _bash(command: str, cwd: Path):
    return _run("guards/bash-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "t",
                                         "cwd": str(cwd), "tool_input": {"command": command}}, cwd)


def test_bash_guard_hands_the_commit_message_warning_to_the_model(tmp_path):
    done = _bash('git commit -m "update stuff"', tmp_path)
    assert done.returncode == 0 and "Conventional Commits" in _context(done)
    assert b"Conventional Commits" in done.stderr   # la console de Jay le voit toujours


def test_bash_guard_hands_the_trailer_warning_to_the_model(tmp_path):
    assert "trailer" in _context(_bash('git commit -m "feat: x"', tmp_path)).lower()


def test_bash_guard_hands_the_pinned_version_warning_to_the_model(tmp_path):
    assert "Specific version" in _context(_bash("npm install left-pad@1.3.0", tmp_path))


def test_bash_guard_stays_silent_when_nothing_is_wrong(tmp_path):
    assert _bash("ls -la", tmp_path).stdout.strip() == b""


def test_a_blocking_message_is_not_turned_into_context(tmp_path):
    done = _bash("git add -A", tmp_path)
    assert done.returncode == 2 and done.stdout.strip() == b""


def test_post_write_guard_hands_a_console_log_warning_to_the_model(tmp_path):
    fichier = tmp_path / "a.ts"
    fichier.write_text("console.log('x')\n", encoding="utf-8")
    done = _run("guards/post-write-guard.py", {"hook_event_name": "PostToolUse", "tool_name": "Write", "session_id": "t",
                                               "tool_input": {"file_path": str(fichier)}, "tool_response": {}}, tmp_path)
    assert done.returncode == 0 and "console.log" in _context(done)


def test_a_crashed_end_user_guard_says_so_to_the_model(monkeypatch, capsys):
    """« Rien n'a été vérifié » (sortie 0) est la phrase la plus importante à faire lire au modèle."""
    import importlib.util
    import io

    spec = importlib.util.spec_from_file_location("eug", HOOKS / "guards" / "end-user-data-guard.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    monkeypatch.setattr(guard, "store_present", lambda: True)
    monkeypatch.setattr(guard, "_check", lambda payload: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write"})))
    assert guard.main() == 0
    sortie = capsys.readouterr()
    assert "rien n'a été vérifié" in sortie.err
    assert "rien n'a été vérifié" in json.loads(sortie.out)["hookSpecificOutput"]["additionalContext"]


# --- relecture indépendante du 2026-11-02 (R3) : maintenant que les avertissements arrivent au modèle, les fausses alertes comptent ---


def test_a_script_that_only_quotes_a_commit_does_not_trigger_the_trailer_warning(tmp_path):
    commande = "python - <<'EOF'\nprint('git commit -m \"feat: x\"')\nEOF"
    assert "trailer" not in _context(_bash(commande, tmp_path)).lower()


def test_a_script_that_only_quotes_a_deploy_does_not_trigger_the_vps_warning(tmp_path):
    commande = "cat > notes.txt <<'EOF'\nssh vps systemctl restart nginx\nEOF"
    assert "VPS deploy" not in _context(_bash(commande, tmp_path))


def test_a_real_remote_restart_still_warns(tmp_path):
    assert "VPS deploy" in _context(_bash('ssh vps "systemctl restart nginx"', tmp_path))


def test_a_real_commit_without_the_trailer_still_warns(tmp_path):
    assert "trailer" in _context(_bash('git commit -m "feat: x"', tmp_path)).lower()


def test_scp_rsync_and_remote_restarts_still_warn(tmp_path):
    for commande in ("scp dist.tgz vps:/srv/app", "rsync -az dist/ vps:/srv/app",
                     "ssh vps 'systemctl --user restart kobo'", "ssh vps pm2 restart all"):
        assert "VPS deploy" in _context(_bash(commande, tmp_path)), commande
