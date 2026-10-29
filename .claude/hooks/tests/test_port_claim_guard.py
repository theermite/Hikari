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


# --- une machine, un registre : le meme numero peut servir deux services sur deux machines (2026-10-29) ---

REGISTRE_DEUX_MACHINES = (
    "## VPS OVH (217.182.206.127)\n\n| Port | Bind | Service |\n|---|---|---|\n| 3004 | 127.0.0.1 | Michi-Niwa web |\n\n"
    "## Ermite-Game (Jay's local machine)\n\n| Port | Service | VPS access via |\n|---|---|---|\n"
    "| 8007 | SearXNG de secours | Tailscale |\n\n"
    "## Local Dev (ermite-game, Jay's Windows machine)\n\n| Port | Service | Project |\n|---|---|---|\n"
    "| 3004 | dev server ad hoc | Hoso |\n"
)


def _infra_deux_machines(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "Port-Registry.md").write_text(REGISTRE_DEUX_MACHINES, encoding="utf-8")
    return tmp_path


def test_owners_are_read_per_machine(tmp_path):
    infra = _infra_deux_machines(tmp_path)
    vps = ports_registry.read_owners(infra, machine="vps")
    local = ports_registry.read_owners(infra, machine="local")
    assert "Michi-Niwa" in vps[3004] and "Hoso" not in vps[3004] and 8007 not in vps
    assert "Hoso" in local[3004] and local[8007].startswith("SearXNG") and "Michi-Niwa" not in local[3004]


def test_default_machine_is_the_vps_because_compose_files_are_deployed_there(tmp_path):
    infra = _infra_deux_machines(tmp_path)
    assert ports_registry.read_owners(infra) == ports_registry.read_owners(infra, machine="vps")


def test_a_port_declared_for_the_local_machine_is_known_not_unknown(tmp_path):
    repo = _atelier(tmp_path, "Tour")
    md = repo.parent / "Shinkofa-Infra" / "docs" / "Port-Registry.md"
    md.write_text(MD + "\n## Ermite-Game (Jay's local machine)\n\n| Port | Service | VPS access via |\n"
                  "|---|---|---|\n| 8555 | outil de la tour | Tailscale |\n", encoding="utf-8")
    r = _ecrire(repo, _compose("8555"))
    assert r.returncode == 0 and r.stderr == b""


def test_a_port_in_no_registry_still_warns(tmp_path):
    r = _ecrire(_atelier(tmp_path, "Tour"), _compose("8777"))
    assert r.returncode == 0 and b"8777" in r.stderr


# --- une plage du yaml (9001-9024) est lue comme les ports qu'elle couvre ; l'ecart entre listes se mesure ---

def _infra_ecart(tmp_path):
    (tmp_path / "registry").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "registry" / "infra.yaml").write_text(
        "meta:\n  v: 1\nports:\n  22: ssh\n  3020: shizen\n  9001-9003: mcp-fleet\ndatabases:\n  x: y\n", encoding="utf-8")
    (tmp_path / "docs" / "Port-Registry.md").write_text(
        "## VPS\n\n| Port | Service |\n|---|---|\n| 22 | ssh |\n| 9002 | mcp |\n| 8040 | mcp-web |\n\n"
        "## Ermite-Game (local)\n\n| Port | Service |\n|---|---|\n| 11434 | Ollama |\n", encoding="utf-8")
    return tmp_path


def test_a_yaml_range_covers_every_port_it_names(tmp_path):
    owners = ports_registry.read_owners(_infra_ecart(tmp_path))
    assert {9001, 9002, 9003} <= set(owners) and "mcp-fleet" in owners[9001]


def test_the_gap_between_the_two_lists_is_measured_per_port(tmp_path):
    seulement_yaml, seulement_md = ports_registry.divergence(_infra_ecart(tmp_path))
    assert seulement_yaml == [3020, 9001, 9003]     # 9002 est dans les deux
    assert seulement_md == [8040]
    assert ports_registry.divergence(tmp_path / "absent") == ([], [])
