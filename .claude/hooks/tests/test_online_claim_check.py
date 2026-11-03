"""quality/online-claim-check.py (Stop) + deploy/smoke-test-required.py — « en ligne » veut dire joignable ET fonctionnel.

Décision de Jay (2026-10-30) : après une mise en ligne, avant de dire qu'un site est en ligne, un contrôle réel (web_check ou
curl) est lancé et sa sortie citée. Le garde de fumée ne regardait que `curl` (jamais un appel MCP) et ne prévenait qu'une
fois. Ici : l'appel `web_check` compte comme contrôle, et l'affirmation « c'est en ligne » est refusée tant qu'une mise en
ligne de la séance n'a eu aucun contrôle depuis.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
SMOKE = HOOKS / "deploy" / "smoke-test-required.py"
CLAIM = HOOKS / "quality" / "online-claim-check.py"


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _run(script: Path, repo: Path, payload: dict):
    return subprocess.run([sys.executable, str(script)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=30, cwd=str(repo))


def _bash(repo: Path, command: str, session: str = "s1"):
    return _run(SMOKE, repo, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": session,
                              "tool_input": {"command": command}})


def _mcp(repo: Path, tool: str = "mcp__shinkofa-web__web_check", session: str = "s1"):
    return _run(SMOKE, repo, {"hook_event_name": "PreToolUse", "tool_name": tool, "session_id": session,
                              "tool_input": {"url": "https://exemple.shinkofa.com"}})


def _stop(repo: Path, message: str, session: str = "s1", active: bool = False):
    return _run(CLAIM, repo, {"hook_event_name": "Stop", "session_id": session, "stop_hook_active": active,
                              "last_assistant_message": message})


CLAIMS = ("C'est en ligne, tout est bon.", "Le site est déployé et fonctionne.", "La mise en ligne est terminée.",
          "The site is now live.", "Le correctif est en production.")


def test_a_claim_after_a_deploy_without_check_is_refused(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    for claim in CLAIMS:
        fait = _stop(repo, claim)
        assert fait.returncode == 2 and b"web_check" in fait.stderr, claim


def test_a_web_check_call_clears_the_debt(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    _mcp(repo)
    assert _stop(repo, "C'est en ligne, tout est bon.").returncode == 0


def test_a_browser_call_also_counts_as_a_check(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    _mcp(repo, "mcp__shinkofa-web__browser_open")
    assert _stop(repo, "C'est en ligne.").returncode == 0


def test_a_curl_health_still_counts(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    _bash(repo, "curl -fsS https://exemple.shinkofa.com/health")
    assert _stop(repo, "C'est en ligne.").returncode == 0


def test_no_deploy_means_no_refusal(tmp_path):
    assert _stop(_repo(tmp_path), "C'est en ligne.").returncode == 0


def test_a_message_that_is_not_a_claim_passes(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    for message in ("Je lance le contrôle maintenant.", "Ce n'est pas encore en ligne : le contrôle reste à faire.",
                    "Le site n'est pas déployé.", "Voici le rapport de la séance.",
                    "Je ne dis pas que c'est en ligne tant que le contrôle n'a pas répondu.",
                    "Si c'est en ligne, je lance le contrôle.",
                    "Avant de dire que c'est en ligne, je contrôle le parcours critique.",
                    "Est-ce que c'est en ligne ?"):
        assert _stop(repo, message).returncode == 0, message


def test_it_speaks_once_per_turn(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    assert _stop(repo, "C'est en ligne.", active=True).returncode == 0


def test_another_session_is_not_blamed(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d", session="s1")
    assert _stop(repo, "C'est en ligne.", session="s2").returncode == 0


def test_broken_input_fails_open(tmp_path):
    fait = subprocess.run([sys.executable, str(CLAIM)], input=b"not json", capture_output=True, cwd=str(_repo(tmp_path)))
    assert fait.returncode == 0


# --- relecture indépendante du 2026-11-02 (FAIL, D1) : le repli prescrit doit lever la dette -----------------------------


def test_the_curl_the_guard_itself_prescribes_clears_the_debt(tmp_path):
    """Le RECOVERY dit : curl -fsS -o /dev/null -w \"%{http_code}\" <url>. Sans le serveur web c'est le seul contrôle possible."""
    repo = _repo(tmp_path)
    _bash(repo, "ssh vps 'cd /srv/kobo && docker compose up -d'")
    assert _stop(repo, "Kobo est en ligne : curl rend 200.").returncode == 2
    _bash(repo, 'curl -fsS -o /dev/null -w "%{http_code}" https://kobo.shinkofa.com')
    assert _stop(repo, "Kobo est en ligne : curl rend 200.").returncode == 0


def test_a_curl_to_a_critical_path_also_clears_the_debt(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    _bash(repo, 'curl -fsS -o /dev/null -w "%{http_code}" https://kobo.shinkofa.com/login')
    assert _stop(repo, "C'est en ligne.").returncode == 0


def test_a_curl_to_localhost_before_nothing_else_still_counts_only_after_a_deploy(tmp_path):
    repo = _repo(tmp_path)
    assert _stop(repo, "C'est en ligne.").returncode == 0   # aucune mise en ligne : rien à lever


# --- citations et oublis (R2) --------------------------------------------------------------------------------------------


def test_a_quoted_phrase_is_not_a_claim(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    for message in ("Le garde refuse une réponse qui dit « c'est en ligne » sans contrôle.",
                    'La phrase "c\'est en ligne" est refusée sans contrôle.',
                    "Les tests sont en ligne avec la spec.",
                    "Le paquet est déployé localement dans node_modules.",
                    "La branche est déployée en prévisualisation."):
        assert _stop(repo, message).returncode == 0, message


def test_common_english_claims_are_seen(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    for message in ("It's live!", "Deployed and verified.", "Everything is up and running."):
        assert _stop(repo, message).returncode == 2, message


# --- relecture ciblée du 2026-11-02 (PASS, remarques 1 et 2) ---------------------------------------------------------------


def test_real_claims_with_an_exempt_looking_phrase_are_still_refused(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    for message in ("C'est en ligne avec le nouveau formulaire.",
                    "La version 2 est en ligne avec le correctif de connexion.",
                    "J'ai testé déployé localement, et maintenant c'est en ligne.",
                    'Écran de 27" : c\'est en ligne.\nLe "mode sombre" marche.'):
        assert _stop(repo, message).returncode == 2, message


def test_aligned_with_something_is_still_not_a_claim(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    for message in ("Les tests sont en ligne avec la spec.", "Le choix est en ligne avec la charte.",
                    "Le paquet est déployé localement dans node_modules."):
        assert _stop(repo, message).returncode == 0, message


def test_a_dev_server_or_a_local_address_is_not_a_check(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    _bash(repo, "curl -s http://localhost:5173/")
    _bash(repo, "curl -s http://127.0.0.1:3000/login")
    assert _stop(repo, "C'est en ligne.").returncode == 2


def test_a_commit_message_quoting_curl_is_not_a_check(tmp_path):
    repo = _repo(tmp_path)
    _bash(repo, "docker compose up -d")
    _bash(repo, 'git commit -m "docs: tester avec curl https://exemple.com"')
    assert _stop(repo, "C'est en ligne.").returncode == 2
