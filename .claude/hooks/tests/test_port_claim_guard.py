"""port-claim-guard.py — un fichier compose ne prend pas un port déjà pris par un autre service.

Le registre est un faux atelier : `<ws>/Shinkofa-Infra/registry/infra.yaml` et `docs/Port-Registry.md`.
Le dépôt courant est `<ws>/<projet>` ; le HOME est détourné pour ne pas lire le vrai serveur.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "port-claim-guard.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import ports_registry  # noqa: E402

YAML = """meta:
  version: 1
ports:
  22: ssh
  8009: auth-phoenix            # SSO
  8017: dogu-server
  3010: michi-shinkofa
databases:
  x: y
"""
MD = """| Port | Bind | Service |
|------|------|---------|
| 8007 | 127.0.0.1 | SearXNG de secours (tour) |
| 8009 | 127.0.0.1 | auth-phoenix |
"""


def _atelier(tmp_path: Path, projet: str, *, avec_registre: bool = True) -> Path:
    ws = tmp_path / "ws"
    repo = ws / projet
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    if avec_registre:
        (ws / "Shinkofa-Infra" / "registry").mkdir(parents=True)
        (ws / "Shinkofa-Infra" / "docs").mkdir(parents=True)
        (ws / "Shinkofa-Infra" / "registry" / "infra.yaml").write_text(YAML, encoding="utf-8")
        (ws / "Shinkofa-Infra" / "docs" / "Port-Registry.md").write_text(MD, encoding="utf-8")
    return repo


def _ecrire(repo: Path, contenu: str, nom: str = "docker-compose.yml", outil: str = "Write"):
    cle = "content" if outil == "Write" else "new_string"
    payload = {"tool_name": outil, "tool_input": {"file_path": str(repo / nom), cle: contenu}}
    env = {**os.environ, "HOME": str(repo.parent), "USERPROFILE": str(repo.parent)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20, cwd=str(repo), env=env)


def _compose(port: str, nom: str = "") -> str:
    ligne = f"    container_name: {nom}\n" if nom else ""
    return f"services:\n  web:\n{ligne}    ports:\n      - \"127.0.0.1:{port}:80\"\n"


def test_blocks_a_port_owned_by_another_service(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Manabi"), _compose("8017"))
    assert r.returncode == 2
    assert b"8017" in r.stderr and b"dogu-server" in r.stderr


def test_allows_the_port_of_the_same_service(tmp_path):
    assert _ecrire(_atelier(tmp_path, "Dogu"), _compose("8017")).returncode == 0


def test_container_name_proves_it_is_the_same_service(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Shinkofa-Backend"), _compose("8009", "shinkofa_auth_phoenix_prod"))
    assert r.returncode == 0


def test_a_filler_word_does_not_prove_ownership(tmp_path):
    """« server » / « prod » ne nomment aucun service : ils ne doivent pas ouvrir la porte."""
    r = _ecrire(_atelier(tmp_path, "Manabi"), _compose("8017", "manabi_server_prod"))
    assert r.returncode == 2


def test_port_only_in_the_hand_written_list_is_still_known(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Manabi"), _compose("8007"))
    assert r.returncode == 2 and b"SearXNG" in r.stderr


def test_unknown_port_warns_without_blocking(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Manabi"), _compose("8099"))
    assert r.returncode == 0 and b"8099" in r.stderr


def test_port_ok_marker_lets_a_false_positive_through(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Manabi"), "# PORT-OK: même service renommé\n" + _compose("8017"))
    assert r.returncode == 0 and r.stderr == b""


def test_edit_new_string_is_checked_too(tmp_path):
    assert _ecrire(_atelier(tmp_path, "Manabi"), _compose("8017"), outil="Edit").returncode == 2


def test_non_compose_file_is_ignored(tmp_path):
    assert _ecrire(_atelier(tmp_path, "Manabi"), _compose("8017"), nom="notes.yml").returncode == 0


def test_no_registry_lets_everything_through(tmp_path):
    repo = _atelier(tmp_path, "Manabi", avec_registre=False)
    assert _ecrire(repo, _compose("8017")).returncode == 0


def test_compose_without_published_port_is_ignored(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Manabi"), "services:\n  web:\n    image: x\n")
    assert r.returncode == 0 and r.stderr == b""


def test_host_ports_reads_short_forms_only_on_the_host_side():
    texte = 'ports:\n  - "8080:80"\n  - 9000:9000/tcp\n  - "[::1]:3000:3000"\n  - "127.0.0.1:4000:4000"\n'
    assert ports_registry.host_ports(texte) == [3000, 4000, 8080, 9000]


def test_real_registry_is_readable_when_present():
    """Garde-fou de la lecture : le vrai registre, s'il est là, donne des propriétaires non vides."""
    infra = Path(__file__).resolve().parents[4] / "Shinkofa-Infra"
    if not infra.is_dir():
        return
    owners = ports_registry.read_owners(infra)
    assert owners.get(22) and len(owners) >= 40
