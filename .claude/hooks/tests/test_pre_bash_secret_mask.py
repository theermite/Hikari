"""Tests for guards/pre-bash-secret-mask.py — rewrite suspicious commands to
pipe their output through the secret masker BEFORE it reaches the model.

Origin: docs/Briefs/Hook-Masquage-Secrets-Sorties-Bash-2026-08-30.md. A
PostToolUse hook cannot rewrite a tool's output on this Claude Code version
(verified live, 2026-08-30: `updatedToolOutput` is ignored) — only a
PreToolUse rewrite of the command itself (`updatedInput`) is honored. So the
masking has to happen by rewriting the COMMAND, not by filtering the result
after the fact.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-bash-secret-mask.py"
_spec = importlib.util.spec_from_file_location("pre_bash_secret_mask", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# --- Trigger detection --------------------------------------------------------


def test_docker_exec_is_suspicious():
    assert mod.is_suspicious("docker exec mycontainer sh -c 'echo hi'")


def test_docker_compose_config_is_suspicious():
    assert mod.is_suspicious("docker compose -f prod.yml config")


def test_ssh_with_docker_is_suspicious():
    assert mod.is_suspicious('ssh vps "docker exec db env"')


def test_cat_env_file_is_suspicious():
    assert mod.is_suspicious("cat .env")
    assert mod.is_suspicious("cat backend/.env.production")


def test_printenv_is_suspicious():
    assert mod.is_suspicious("printenv")


def test_plain_ls_is_not_suspicious():
    assert not mod.is_suspicious("ls -la /srv")


def test_git_status_is_not_suspicious():
    assert not mod.is_suspicious("git status")


# --- Independent review 2026-08-31 round 5, famille chemin-fragile-git-rev-parse --


def test_wrap_command_does_not_depend_on_git(tmp_path):
    # cross-model-sonnet, 5th review, proven by real execution: outside a
    # git repo, `$(git rev-parse --show-toplevel)` fails, the filter path
    # resolves to garbage, and the original command's output disappears
    # silently (exit code still 0 — looks like success with no output).
    # The absolute path is already known via `__file__`; no need for git.
    wrapped = mod.wrap_command("printenv")
    assert "git rev-parse" not in wrapped
    assert "secret_mask.py" in wrapped


def test_wrap_command_runs_correctly_outside_a_git_repo(tmp_path):
    import subprocess

    git_bash = r"C:\Program Files\Git\usr\bin\bash.exe"
    wrapped = mod.wrap_command("echo PASSWORD=abcdefghijklmnopqrst1234")
    proc = subprocess.run([git_bash, "-c", wrapped], capture_output=True, text=True, cwd=str(tmp_path))
    assert "abcdefghijklmnopqrst1234" not in proc.stdout
    assert "<masque:" in proc.stdout


# --- Command rewrite -----------------------------------------------------------


def test_wrap_pipes_through_filter_and_preserves_exit_code():
    wrapped = mod.wrap_command("docker compose -f prod.yml config")
    assert "secret_mask.py" in wrapped
    assert "--filter" in wrapped
    assert "PIPESTATUS" in wrapped
    assert "docker compose -f prod.yml config" in wrapped


def test_wrap_does_not_double_wrap_already_wrapped_command():
    once = mod.wrap_command("cat .env")
    twice = mod.wrap_command(once)
    assert once == twice


# --- Independent review 2026-08-31, famille masquage-secret-incomplet-et-sur-masquage --


def test_command_merely_mentioning_the_filter_path_still_gets_wrapped():
    # CRITICAL found by cross-model-sonnet: the anti-double-wrap guard used
    # to match the bare substring "secret_mask.py" ANYWHERE in the command,
    # so a suspicious command that happened to mention that path (e.g. it
    # reads the hook's own file alongside a real .env) skipped wrapping
    # entirely and its .env leaked unmasked.
    cmd = "docker exec prod-db cat /app/.claude/hooks/lib/secret_mask.py /app/.env"
    assert mod.is_suspicious(cmd)
    wrapped = mod.wrap_command(cmd)
    assert wrapped != cmd
    assert "PIPESTATUS" in wrapped


def test_docker_compose_with_hyphen_is_suspicious():
    # MAJOR found by cross-model-sonnet: `docker-compose` (legacy binary,
    # still aliased in real shells) escaped `\bdocker\s+compose\b` entirely —
    # incident B reproduced with a hyphen instead of a space.
    assert mod.is_suspicious("docker-compose -f prod.yml config")


def test_docker_compose_logs_is_suspicious():
    assert mod.is_suspicious("docker compose logs db")


def test_bare_env_is_suspicious():
    assert mod.is_suspicious("env")


def test_environment_word_is_not_falsely_suspicious():
    assert not mod.is_suspicious("echo environment ready")


def test_kubectl_exec_is_suspicious():
    assert mod.is_suspicious("kubectl exec -it pod -- env")


def test_cat_private_key_file_is_suspicious():
    assert mod.is_suspicious("cat ~/.ssh/id_rsa")
    assert mod.is_suspicious("cat server.pem")
    assert mod.is_suspicious("cat prod.key")


def test_curl_verbose_is_suspicious():
    # cross-model-sonnet, 8th review: `curl -v`/`-i`/`--include`/`--verbose`
    # prints request/response headers, the most common real-world way an
    # `Authorization: Bearer <token>` header ends up in a command's output
    # — and curl was entirely absent from the suspicious list.
    assert mod.is_suspicious("curl -v https://api.example.com/account")
    assert mod.is_suspicious("curl -i https://api.example.com/account")
    assert mod.is_suspicious("curl --verbose https://api.example.com")
    assert mod.is_suspicious("curl --include https://api.example.com")
    assert not mod.is_suspicious("curl https://api.example.com")  # no header flag, quiet body only


def test_secretsmanager_and_vault_are_suspicious():
    assert mod.is_suspicious("aws secretsmanager get-secret-value --secret-id x")
    assert mod.is_suspicious("vault kv get secret/prod/db")
    assert mod.is_suspicious("heroku config -a myapp")


# --- Real end-to-end preservation of the exit code (not just a substring) --


# --- Independent review 2026-08-31 round 2, famille detection-regex-non-robuste-casse-separateurs --


def test_uppercase_docker_exec_is_suspicious():
    # cross-model-sonnet, 2nd review: proven exploitable on THIS Windows box
    # — NTFS resolves executable case-insensitively, so `DOCKER exec ...`
    # actually runs while escaping every un-anchored lowercase pattern.
    assert mod.is_suspicious("DOCKER EXEC mycontainer")


def test_mixed_case_docker_compose_config_is_suspicious():
    assert mod.is_suspicious("Docker Compose -f prod.yml Config")


def test_docker_compose_with_double_space_is_suspicious():
    assert mod.is_suspicious("docker  compose config")


def test_docker_compose_with_tab_is_suspicious():
    assert mod.is_suspicious("docker\tcompose\tconfig")


def test_pipestatus_preserves_real_exit_code_through_real_bash():
    # Windows has 3 binaries named "bash" on PATH (Git Bash, WSL launcher,
    # WindowsApps) that resolve differently depending on invocation context
    # — `subprocess.run(["bash", ...])` picked the WSL one in this sandbox
    # and silently lost the exit code (reviewer's MINOR finding, reproduced
    # for real). Pin to Git Bash explicitly: it is what the actual Bash tool
    # this hook runs under uses (confirmed live, same session).
    import shutil
    import subprocess

    git_bash = shutil.which("bash", path=r"C:\Program Files\Git\usr\bin") or r"C:\Program Files\Git\usr\bin\bash.exe"
    wrapped = mod.wrap_command("bash -c 'echo leaking; exit 42'")
    proc = subprocess.run([git_bash, "-c", wrapped], capture_output=True, text=True)
    assert proc.returncode == 42


# --- Independent review 2026-08-31 round 3, famille wrap-defeated-par-redirection --


def test_own_file_redirect_is_detected():
    # cross-model-sonnet, 3rd review, proven by real execution: a command
    # that already redirects its OWN output to a file consumes it before
    # the outer masking pipe ever sees it. The secret lands on disk in
    # clear, and neither this hook nor the PostToolUse alert net (which
    # only sees tool_response.stdout/stderr, itself empty in this case) can
    # observe it — a pre-existing architectural blind spot (verified:
    # identical with or without wrapping), not something a regex fix
    # closes. The only honest move is to say so.
    assert mod.has_own_redirection("docker compose config > backup.yml")
    assert mod.has_own_redirection("docker compose config >> backup.yml")
    assert mod.has_own_redirection("docker exec db env 2> /tmp/err.log")
    assert mod.has_own_redirection("docker exec db env &> combined.log")


def test_fd_duplication_is_not_a_file_redirect():
    # `2>&1` merges stderr into stdout — no file involved, no blind spot.
    assert not mod.has_own_redirection("docker exec db env 2>&1")
    assert not mod.has_own_redirection("docker compose config >&2")


def test_internal_pipe_without_file_redirect_is_not_flagged():
    # a pipe to another process (grep, etc.) still flows through the outer
    # wrap normally — only a FILE redirect bypasses it (confirmed by the
    # 2nd review: `docker compose config | grep PASSWORD` stayed wrapped).
    assert not mod.has_own_redirection("docker compose config | grep PASSWORD")


def test_build_decision_warns_without_pretending_to_mask_on_file_redirect():
    decision = mod.build_decision({"tool_input": {"command": "docker compose config > backup.yml"}})
    assert decision is not None
    ctx = decision["hookSpecificOutput"].get("additionalContext", "")
    assert "redirect" in ctx.lower() and "file" in ctx.lower()


# --- Full hook decision (stdin -> stdout JSON) ----------------------------------


def test_build_decision_returns_updated_input_for_suspicious_command():
    decision = mod.build_decision({"tool_input": {"command": "cat .env"}})
    assert decision is not None
    updated = decision["hookSpecificOutput"]["updatedInput"]["command"]
    assert "secret_mask.py" in updated


def test_build_decision_returns_none_for_ordinary_command():
    decision = mod.build_decision({"tool_input": {"command": "ls -la"}})
    assert decision is None
