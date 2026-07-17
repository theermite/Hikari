#!/usr/bin/env python3
"""D2 — PreToolUse Bash guard: block deploys with a missing Vault secret.

Targets the real Shinkofa-Vault (SOPS/age), not HashiCorp Vault.

Model
-----
The vault declares, per project/service, which env vars a deploy needs:
    ~/Shinkofa-Vault/mappings/<stem>.yaml   ->  `ENV_VAR_NAME: secret_key`
    ~/Shinkofa-Vault/envs/<stem>.env        ->  generated `ENV_VAR_NAME=value`
`inject.sh` copies the env into the service. If a mapped ENV_VAR_NAME never
made it into the generated env, the deploy would start with a missing secret.

Trigger
-------
PreToolUse on a Bash command matching a deploy verb (docker compose up,
systemctl restart, deploy.sh, vercel --prod, ssh host ... systemctl, etc.).

Action
------
1. Locate the vault: $SHINKOFA_VAULT_DIR or ~/Shinkofa-Vault. Absent -> pass
   (host not vault-enabled / project not opted in).
2. Resolve project P: $SHINKOFA_PROJECT or the repo-root dir name, lowercased.
3. Match mappings whose stem == P or starts with `P-` (multi-service repos like
   michi-niwa-bot / michi-niwa-web). None -> pass.
4. For each matched mapping that HAS a sibling envs/<stem>.env:
       required = the ENV_VAR_NAME keys declared in the mapping
       present  = the KEY names in the env file (names only — never values)
       missing += required - present
   A mapping with no generated env is skipped (covered-via-Infra / not built
   on this host) — we cannot conclude, so we do not block.
5. Any missing -> exit 2 (BLOCK) with recovery. Else pass.

Confidentiality: only env var NAMES are read from the env file; secret VALUES
are never parsed, logged, or surfaced (Confidentiality.md).

Reference: VAULT.md workflow (generate-envs.sh -> inject.sh). Plan Phase D2.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    canonical_project_name,
    find_repo_root,
    format_block,
    get_command,
    looks_like_deploy,
    pass_through,
    read_hook_input,
)


# --- Vault location & project resolution ------------------------------------


def _vault_dir() -> Path | None:
    override = os.environ.get("SHINKOFA_VAULT_DIR")
    root = Path(override) if override else Path.home() / "Shinkofa-Vault"
    return root if (root / "mappings").is_dir() else None


def _project_name() -> str:
    override = os.environ.get("SHINKOFA_PROJECT")
    if override:
        return override.strip().lower()
    return canonical_project_name().lower()


def _matched_stems(vault: Path, project: str) -> list[str]:
    """Mapping stems that belong to this project (exact or `project-<svc>`)."""
    stems = []
    for path in sorted((vault / "mappings").glob("*.yaml")):
        stem = path.stem
        if stem == project or stem.startswith(project + "-"):
            stems.append(stem)
    return stems


# --- Parsing (names only — never values) ------------------------------------

_MAPPING_VAR_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]{2,})\s*:", re.MULTILINE)
_ENV_KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=", re.MULTILINE)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _required_vars(mapping: Path) -> list[str]:
    return _MAPPING_VAR_RE.findall(_read(mapping))


def _present_keys(env_file: Path) -> set[str]:
    return set(_ENV_KEY_RE.findall(_read(env_file)))


# --- Main -------------------------------------------------------------------


def _collect_missing(vault: "Path", stems: list[str]) -> list[str]:
    missing: list[str] = []
    for stem in stems:
        env_file = vault / "envs" / f"{stem}.env"
        if not env_file.is_file():
            continue  # covered-via-Infra / not generated here → cannot conclude
        present = _present_keys(env_file)
        for var in _required_vars(vault / "mappings" / f"{stem}.yaml"):
            if var not in present:
                missing.append(var)
    return missing


def _emit_block(project: str, missing: list[str]) -> None:
    var_list = ", ".join(dict.fromkeys(missing))  # dedup, keep order
    block(format_block(
        reason=f"deploy aborted — Vault-mapped secret(s) missing from the "
               f"generated env: {var_list}",
        recovery=(
            f"regenerate and inject for '{project}': "
            f"`cd ~/Shinkofa-Vault && ./scripts/generate-envs.sh <stem> && "
            f"./scripts/inject.sh <stem>`, then re-run the deploy. If the var is "
            f"obsolete, remove it from mappings/<stem>.yaml."
        ),
        reference="VAULT.md (generate-envs.sh -> inject.sh)",
    ))


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd or not looks_like_deploy(cmd):
        pass_through()

    vault = _vault_dir()
    if vault is None:
        pass_through()

    project = _project_name()
    stems = _matched_stems(vault, project)
    if not stems:
        pass_through()

    missing = _collect_missing(vault, stems)
    if not missing:
        pass_through()

    _emit_block(project, missing)


if __name__ == "__main__":
    main()
