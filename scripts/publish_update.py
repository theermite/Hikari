#!/usr/bin/env python3
"""Build a signed release and publish it to the private update channel.

Why the channel address lives OUTSIDE this repository: `theermite/Hikari` is public. A
private path written into a public repo stops being private the moment it is pushed. So
the address, the SSH host and the remote directory sit in `scripts/publish.local.json`,
which is gitignored, and this script feeds them to the Tauri bundler as a config overlay
at build time. A build made from a public clone simply has no channel, and says so
cleanly instead of failing (see `UpdateBanner`).

Expected `scripts/publish.local.json`:

    {
      "endpoint": "https://<host>/<private-path>/latest.json",
      "ssh_host": "vps",
      "remote_dir": "/home/ubuntu/apps/hikari-updates"
    }

The signing key is read from `TAURI_SIGNING_PRIVATE_KEY` (a path or the key itself). It is
never read, printed or stored by this script — it is handed to the bundler through the
environment and nothing else.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_TAURI = REPO_ROOT / "src-tauri"
CONFIG_PATH = REPO_ROOT / "scripts" / "publish.local.json"
OVERLAY_PATH = SRC_TAURI / "tauri.private.conf.json"
BUNDLE_DIR = SRC_TAURI / "target" / "release" / "bundle" / "nsis"
# The updater matches this key against the running platform; `windows-x86_64` is the only
# target we ship today (macOS is blocked upstream — libobs-rs has no working macOS build).
PLATFORM_KEY = "windows-x86_64"


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    """Run a build/upload step, stopping on failure.

    The executable is resolved through PATH first: on Windows `pnpm` is `pnpm.cmd`, and
    handing the bare name to the process API raises "cannot find the file specified" — an
    error that names neither the tool nor the reason.

    `env` replaces the child's environment when given — used to build WITHOUT the signing
    key, so the bundler never reaches for a console password prompt.
    """
    resolved = shutil.which(command[0])
    if resolved is None:
        raise SystemExit(f"{command[0]!r} not found in PATH — cannot continue")
    print(f"\n$ {' '.join(command)}", flush=True)
    subprocess.run([resolved, *command[1:]], cwd=cwd, check=True, env=env)


def load_channel() -> dict[str, str]:
    if not CONFIG_PATH.is_file():
        raise SystemExit(
            f"missing {CONFIG_PATH}\n"
            "Create it with the private channel address — see this script's docstring."
        )
    channel = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key in ("endpoint", "ssh_host", "remote_dir"):
        if not channel.get(key):
            raise SystemExit(f"{CONFIG_PATH}: missing key {key!r}")
    if not channel["endpoint"].startswith("https://"):
        # The updater enforces TLS in production; a plain-http address would be rejected
        # at runtime, long after the release was published. Fail here instead.
        raise SystemExit("endpoint must be an https:// URL")
    return channel


def app_version() -> str:
    config = json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
    return config["version"]


def write_overlay(endpoint: str) -> None:
    """The build-time config overlay carrying the private endpoint (never committed).

    It also turns OFF `createUpdaterArtifacts` for this build. That flag is what makes the
    bundler sign the installer itself — and to do that it asks for the key's password on
    the CONSOLE, not on standard input. An unattended run then stops dead at a prompt
    nobody can see, after building everything (three failed releases on 2026-09-06, the
    first waiting ten hours). Signing moves to its own step in `build_signed`, where the
    password is an argument and nothing can be asked.

    The public key stays in the app: it is what the installed cockpit uses to verify the
    NEXT update, and removing it would silently disarm that check.
    """
    OVERLAY_PATH.write_text(
        json.dumps(
            {
                "bundle": {"createUpdaterArtifacts": False},
                "plugins": {"updater": {"endpoints": [endpoint]}},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def build_signed(version: str) -> tuple[Path, Path]:
    if not os.environ.get("TAURI_SIGNING_PRIVATE_KEY"):
        raise SystemExit(
            "TAURI_SIGNING_PRIVATE_KEY is not set — the bundler cannot sign the update.\n"
            "Point it at the private key file, e.g. ~/.tauri/hikari-updater.key"
        )
    run([sys.executable, str(REPO_ROOT / "scripts" / "prepare_bundle.py")], cwd=REPO_ROOT)
    # `--config` is resolved against the CURRENT directory, not against `src-tauri/`
    # (unlike `resources` and `externalBin` inside the config itself). Passing the path
    # relative to the repo root is what the CLI actually reads.
    overlay = OVERLAY_PATH.relative_to(REPO_ROOT).as_posix()
    # The overlay disables the bundler's own signing (see `write_overlay`); the signature
    # is produced below, by a command that takes the password as an argument.
    run(["pnpm", "tauri", "build", "--config", overlay], cwd=REPO_ROOT)

    # Matched on the VERSION being published, never "the only file present": the bundle
    # directory keeps every past build, so a glob that demands a single match turns an
    # ordinary leftover into a failed release — and, worse, a glob that takes the first
    # match would happily publish yesterday's installer under today's version number.
    installers = sorted(BUNDLE_DIR.glob(f"*_{version}_*-setup.exe"))
    if len(installers) != 1:
        raise SystemExit(
            f"expected exactly one installer for {version} in {BUNDLE_DIR}, "
            f"found {len(installers)}: {[p.name for p in installers]}"
        )
    installer = installers[0]
    signature = installer.with_suffix(installer.suffix + ".sig")
    # A signature left over from a previous run must never pass for this one: it would
    # publish a manifest whose signature belongs to another file, and every client would
    # reject the update with nothing explaining why.
    signature.unlink(missing_ok=True)
    key_path = os.environ["TAURI_SIGNING_PRIVATE_KEY"]
    password = os.environ.get("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", "")
    # The signer reads the SAME variable as an inline key, and refuses a run that names the
    # key twice ("--private-key-path cannot be used with --private-key"). So it gets the
    # path as an argument and an environment without that variable — one source, not two.
    signer_env = {k: v for k, v in os.environ.items() if k != "TAURI_SIGNING_PRIVATE_KEY"}
    run(
        ["pnpm", "tauri", "signer", "sign", "-f", key_path, "-p", password, str(installer)],
        cwd=REPO_ROOT,
        env=signer_env,
    )
    if not signature.is_file():
        raise SystemExit(f"no signature next to {installer.name} — signing produced nothing")
    return installer, signature


def build_manifest(version: str, endpoint: str, installer: Path, signature: Path) -> str:
    """The static manifest the updater reads. `url` sits beside `latest.json`, so the
    installer is served from the same private directory — one place to secure, not two."""
    base = endpoint.rsplit("/", 1)[0]
    return json.dumps(
        {
            "version": version,
            "notes": f"Hikari {version}",
            "pub_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "platforms": {
                PLATFORM_KEY: {
                    "signature": signature.read_text(encoding="utf-8").strip(),
                    "url": f"{base}/{installer.name}",
                }
            },
        },
        indent=2,
    )


def main() -> int:
    channel = load_channel()
    version = app_version()
    write_overlay(channel["endpoint"])

    installer, signature = build_signed(version)
    manifest_path = BUNDLE_DIR / "latest.json"
    manifest_path.write_text(
        build_manifest(version, channel["endpoint"], installer, signature) + "\n",
        encoding="utf-8",
    )

    host, remote = channel["ssh_host"], channel["remote_dir"]
    run(["ssh", host, f"mkdir -p {remote}"], cwd=REPO_ROOT)
    # The installer goes up FIRST: a manifest that announces a file nobody can download
    # yet would send every running app straight into a failed download.
    run(["scp", str(installer), f"{host}:{remote}/"], cwd=REPO_ROOT)
    run(["scp", str(manifest_path), f"{host}:{remote}/"], cwd=REPO_ROOT)

    print(f"\npublished Hikari {version} to the private channel", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
