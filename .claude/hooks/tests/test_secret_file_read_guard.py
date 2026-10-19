"""guards/secret-file-read-guard.py — PreToolUse Read|Grep: no direct read of a
file whose whole content is a secret (.env, SSH/TLS key files, the vault's
decrypted env files and age key). Encrypted sops files and *.example templates
stay readable. The output filter (post-tool-secret-redact) remains the backstop
for everything else.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "secret-file-read-guard.py"


def _run(tool: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10)


def _read(path: str):
    return _run("Read", {"file_path": path})


def test_dotenv_files_are_refused_with_a_french_recovery():
    for p in ("/repo/.env", "D:\\proj\\.env", "/repo/.env.local", "/repo/.env.production", "/repo/api/.env.staging"):
        r = _read(p)
        assert r.returncode == 2, p
        assert "coffre" in r.stderr.decode("utf-8").lower()


def test_templates_are_readable():
    for p in ("/repo/.env.example", "/repo/.env.sample", "/repo/.env.template", "/repo/.env.dist",
              "/repo/.env.local.example"):
        assert _read(p).returncode == 0, p


def test_key_files_and_credential_stores_are_refused():
    for p in ("/home/u/.ssh/id_rsa", "/home/u/.ssh/id_ed25519", "C:\\Users\\u\\.ssh\\id_ecdsa",
              "/x/server.pem", "/x/tls.key", "/x/cert.p12", "/x/cert.pfx", "/home/u/.netrc",
              "/home/u/.aws/credentials", "/home/u/.config/sops/age/keys.txt", "/v/age-key.txt",
              "/x/tokens.env", "/x/prod.tokens.env", "/home/u/.npmrc", "/home/u/.pgpass"):
        assert _read(p).returncode == 2, p


def test_public_keys_and_encrypted_vault_files_are_readable():
    for p in ("/home/u/.ssh/id_rsa.pub", "/home/u/.ssh/known_hosts", "/home/u/.ssh/config",
              "/v/secrets/api-keys.sops.yaml", "/v/.sops.yaml", "/v/mappings/kobo.yaml"):
        assert _read(p).returncode == 0, p


def test_vault_generated_envs_directory_is_refused():
    assert _read("/d/Shinkofa-Vault/envs/kobo.env").returncode == 2
    assert _read("D:\\30-Dev-Projects\\Shinkofa-Vault\\envs\\kobo.env").returncode == 2


def test_a_path_that_only_contains_the_word_env_is_readable():
    for p in ("/repo/src/environment.py", "/repo/docs/env-guide.md", "/repo/envelope.txt", "/repo/.envrc.md"):
        assert _read(p).returncode == 0, p


def test_dotdot_does_not_hide_a_secret_file():
    assert _read("/repo/src/../.env").returncode == 2


def test_grep_on_a_secret_file_or_glob_is_refused():
    assert _run("Grep", {"pattern": "KEY", "path": "/repo/.env"}).returncode == 2
    assert _run("Grep", {"pattern": "KEY", "path": "/repo", "glob": ".env*"}).returncode == 2
    assert _run("Grep", {"pattern": "KEY", "path": "/repo", "glob": "*.pem"}).returncode == 2


def test_ordinary_grep_and_read_pass():
    assert _run("Grep", {"pattern": "def main", "path": "/repo/src"}).returncode == 0
    assert _read("/repo/src/app.py").returncode == 0


def test_unreadable_input_fails_open():
    for raw in (b"", b"not json", b'{"tool_input": 5}', b'{"tool_name":"Read","tool_input":{"file_path":7}}'):
        r = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, timeout=10)
        assert r.returncode == 0


# --- Bash: a command that DISPLAYS a secret file (Jay 2026-10-18) ---------------


def _bash(cmd: str):
    return _run("Bash", {"command": cmd})


def test_bash_readers_of_a_secret_file_are_refused():
    for cmd in ("cat .env", "cat ./api/.env.production", "type C:/p/.env", "head -5 .env", "tail -f .env",
                "less /home/u/.ssh/id_rsa", "grep KEY .env", "rg TOKEN .env", "sed -n 1p .env",
                "awk '{print}' .env", "cat < .env", "cd /app && cat .env", "cat a.txt .env | head",
                "Get-Content .env", "base64 /x/server.pem", "python3 -c \"print(open('.env').read())\"",
                "node -e \"console.log(require('fs').readFileSync('.env','utf8'))\"",
                "sh -c 'cat .env'", "cat ~/.aws/credentials"):
        r = _bash(cmd)
        assert r.returncode == 2, cmd
        assert "coffre" in r.stderr.decode("utf-8").lower()


def test_bash_commands_that_use_a_secret_file_without_displaying_it_pass():
    for cmd in ("docker compose --env-file .env up -d", "source .env && npm test", "ls -la .env",
                "chmod 600 .env", "test -f .env && echo yes", "git check-ignore .env", "cp .env.example .env",
                "cat .env.example", "grep -q KEY .env", "grep -c KEY .env", "wc -c .env",
                "echo hello", "cat README.md", "rm -f /tmp/x/.env"):
        assert _bash(cmd).returncode == 0, cmd


def test_bash_unparsable_command_fails_open():
    assert _bash("cat 'unclosed").returncode == 0


# --- second independent review (2026-10-18) ---------------------------------------


def test_grep_on_the_vault_envs_folder_itself_is_refused():
    assert _run("Grep", {"pattern": "x", "path": "D:\\30-Dev-Projects\\Shinkofa-Vault\\envs"}).returncode == 2
    assert _run("Grep", {"pattern": "x", "path": "/d/Shinkofa-Vault/envs/"}).returncode == 2


def test_braced_glob_naming_secret_files_is_refused():
    assert _run("Grep", {"pattern": "x", "path": "/repo", "glob": "*.{env,pem}"}).returncode == 2
    assert _run("Grep", {"pattern": "x", "path": "/repo", "glob": "*.{md,py}"}).returncode == 0


def test_more_secret_stores_are_refused():
    for p in ("/repo/secrets.env", "/repo/prod.env", "/home/u/.git-credentials", "/home/u/.pypirc",
              "/home/u/.htpasswd", "/x/credentials.json", "/home/u/.kube/kubeconfig", "/x/key.ppk",
              "/x/terraform.tfvars", "/home/u/.ssh/id_rsa.bak", "/home/u/.ssh/id_ed25519_sk",
              "/home/u/.ssh/id_rsa_github", "/home/u/.docker/config.json"):
        assert _read(p).returncode == 2, p


def test_public_certificates_and_encrypted_envs_are_readable():
    for p in ("/etc/ssl/fullchain.pem", "/etc/ssl/cacert.pem", "/x/chain.pem", "/x/.env.sops",
              "/x/.env.age", "/x/.env.vault", "/home/u/.ssh/id_rsa_github.pub"):
        assert _read(p).returncode == 0, p


def test_dotdot_is_resolved_before_judging():
    # the vault folder is escaped by `..`: only a normalised path says it is readable
    assert _read("/x/shinkofa-vault/envs/../secrets/api-keys.sops.yaml").returncode == 0
