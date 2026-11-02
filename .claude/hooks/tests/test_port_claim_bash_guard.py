"""port-claim-bash-guard.py — `docker run -p` et les serveurs de développement ne prennent pas un port inscrit.

Le garde pour fichiers compose (port-claim-guard) ne voyait que l'écriture d'un fichier. Une commande
`docker run -p 8017:80` ou `vite --port 8009` ouvrait un port sans passer par lui (brief du 2026-10-31).
Ce garde AVERTIT seulement : une commande locale peut légitimement reprendre un numéro du serveur
(tunnel, autre machine), il ne peut pas savoir où elle tourne.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "port-claim-bash-guard.py"

YAML = """meta:
  version: 1
ports:
  22: ssh
  8009: auth-phoenix
  8017: dogu-server
databases:
  x: y
"""


def _atelier(tmp_path: Path, *, avec_registre: bool = True) -> Path:
    ws = tmp_path / "ws"
    repo = ws / "projet"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    if avec_registre:
        (ws / "Shinkofa-Infra" / "registry").mkdir(parents=True)
        (ws / "Shinkofa-Infra" / "docs").mkdir(parents=True)
        (ws / "Shinkofa-Infra" / "registry" / "infra.yaml").write_text(YAML, encoding="utf-8")
        (ws / "Shinkofa-Infra" / "docs" / "Port-Registry.md").write_text("| Port | Service |\n", encoding="utf-8")
    return repo


def _run(repo: Path, command: str):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {**os.environ, "HOME": str(repo.parent), "USERPROFILE": str(repo.parent)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20, cwd=str(repo), env=env)


def _warns(result, port: int) -> bool:
    out = (result.stdout + result.stderr).decode("utf-8", "replace")
    return result.returncode == 0 and str(port) in out


def test_docker_run_publishing_a_registered_port_warns(tmp_path):
    repo = _atelier(tmp_path)
    assert _warns(_run(repo, "docker run -d -p 127.0.0.1:8017:80 nginx"), 8017)
    assert _warns(_run(repo, "docker run --publish 8009:80 nginx"), 8009)
    assert _warns(_run(repo, "docker container run -p8009:80 nginx"), 8009)


def test_a_dev_server_on_a_registered_port_warns(tmp_path):
    repo = _atelier(tmp_path)
    assert _warns(_run(repo, "npx vite --port 8017"), 8017)
    assert _warns(_run(repo, "uvicorn app:app --port=8009"), 8009)
    assert _warns(_run(repo, "python -m http.server 8017"), 8017)
    assert _warns(_run(repo, "next dev -p 8009"), 8009)


def test_a_port_absent_from_the_registry_warns_to_register_it(tmp_path):
    repo = _atelier(tmp_path)
    assert _warns(_run(repo, "docker run -p 8123:80 nginx"), 8123)


def test_a_command_that_only_quotes_the_text_is_left_alone(tmp_path):
    repo = _atelier(tmp_path)
    result = _run(repo, "git commit -m 'note: docker run -p 8017:80 reste à documenter'")
    assert result.returncode == 0 and not (result.stdout + result.stderr).strip()
    assert not (_run(repo, "echo \"vite --port 8017\"").stdout + _run(repo, "echo \"vite --port 8017\"").stderr).strip()


def test_other_docker_commands_and_random_host_ports_are_ignored(tmp_path):
    repo = _atelier(tmp_path)
    for command in ("docker ps -a", "docker run -p 80 nginx", "docker exec web ls", "ls -la"):
        result = _run(repo, command)
        assert result.returncode == 0 and not (result.stdout + result.stderr).strip(), command


def test_the_guard_never_blocks_and_passes_without_a_registry(tmp_path):
    repo = _atelier(tmp_path, avec_registre=False)
    result = _run(repo, "docker run -p 8017:80 nginx")
    assert result.returncode == 0 and not (result.stdout + result.stderr).strip()


def test_a_command_that_cannot_be_read_passes_through(tmp_path):
    repo = _atelier(tmp_path)
    assert _run(repo, "docker run -p 8017:80 'nginx").returncode == 0


def test_the_guard_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "guards/port-claim-bash-guard.py" in settings
