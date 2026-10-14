#!/usr/bin/env python3
"""Build the engine ALONE and put it where the app embeds it: `src-tauri/binaries/`.

Why this script exists (measured 2026-10-13): `tauri-build` copies
`binaries/hikari-engine-<triple>.exe` over `target/<profile>/hikari-engine.exe` every time
the app crate is built, deleting the engine cargo had just compiled. Nothing ever refreshed
`binaries/`, so the engine embedded in the app stayed frozen at its 2026-09-14 build — in
dev, and in the published 0.6.1 installer. Every engine change since (overlay, media, the
audio-channel fix) silently never shipped.

The cure is the ORDER: build the engine alone (the app crate is not built, so `tauri-build`
cannot clobber it), copy cargo's own reported artifact into `binaries/`, then let the app
build pick that copy up. The copy is checked byte for byte; the date guard
(`is_stale`) only protects the one path where no build happens (`prepare_bundle --skip-build`).

Usage: `python scripts/sync_engine_sidecar.py [--profile debug|release]`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_TAURI = REPO_ROOT / "src-tauri"
BINARIES_DIR = SRC_TAURI / "binaries"
ENGINE_BIN = "hikari-engine"

# What a rebuilt engine depends on. The app crate and the interface are NOT inputs: a newer
# app source must never make a fresh engine look stale.
SOURCE_GLOBS = (
    "crates/engine/**/*.rs",
    "crates/engine/Cargo.toml",
    "crates/protocol/**/*.rs",
    "crates/protocol/Cargo.toml",
    "Cargo.toml",
    "Cargo.lock",
)


def is_stale(engine_mtime: float, newest_source_mtime: float) -> bool:
    """True when some source was edited after the engine was built."""
    return engine_mtime < newest_source_mtime


def newest_source_mtime(src_tauri: Path) -> float:
    """The latest modification time among the files the engine is built from."""
    times = [
        path.stat().st_mtime
        for pattern in SOURCE_GLOBS
        for path in src_tauri.glob(pattern)
        if path.is_file()
    ]
    return max(times) if times else 0.0


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_sidecar(built: Path, destination: Path) -> None:
    """Copy `built` to `destination` and prove the copy is byte-identical.

    A locked or half-written destination stops the build here: shipping an engine other than
    the one just compiled is exactly the defect this script removes.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, destination)
    if _digest(built) != _digest(destination):
        raise SystemExit(
            f"engine sidecar differs from the built engine after copy: {destination}"
        )


def host_triple() -> str:
    result = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    triple = result.stdout.strip()
    if not triple:
        raise SystemExit("rustc reported no host triple — cannot name the engine sidecar")
    return triple


def build_engine(profile: str) -> Path:
    """Compile the engine alone and return the executable cargo itself reports.

    Reading the path from cargo's JSON output means no guess about the layout of `target/`.
    """
    command = ["cargo", "build", "-p", "engine", "--message-format=json"]
    if profile == "release":
        command.append("--release")
    # stdout carries the JSON stream, stderr carries cargo's human text: only stderr may go
    # straight through to the console.
    process = subprocess.run(
        command, cwd=SRC_TAURI, stdout=subprocess.PIPE, text=True, check=False
    )
    if process.returncode != 0:
        raise SystemExit(
            "engine build failed — if the message above says 'Access is denied', close "
            "Hikari first: Windows locks the running engine and cargo cannot replace it."
        )
    executable = None
    for line in process.stdout.splitlines():
        if not line.startswith("{"):
            continue
        message = json.loads(line)
        target = message.get("target", {})
        if (
            message.get("reason") == "compiler-artifact"
            and target.get("name") == ENGINE_BIN
            and "bin" in target.get("kind", [])
            and message.get("executable")
        ):
            executable = Path(message["executable"])
    if executable is None or not executable.is_file():
        raise SystemExit("cargo did not report the engine executable")
    return executable


def sync(profile: str) -> Path:
    # No "older than its sources" check here: cargo itself decides whether the engine is
    # up to date, and it relinks the executable even when the file was overwritten (measured
    # 2026-10-14: a stale engine put over `target/debug/hikari-engine.exe` was replaced by a
    # fresh build). A date comparison on top of that only raised false alarms — bumping the
    # app version in `Cargo.toml` made a perfectly fresh engine look "stale" and blocked the
    # dev launch. The date guard stays for ONE case, in `prepare_bundle --skip-build`: an
    # engine reused without any build, where nothing else vouches for it.
    built = build_engine(profile)
    suffix = ".exe" if sys.platform == "win32" else ""
    destination = BINARIES_DIR / f"{ENGINE_BIN}-{host_triple()}{suffix}"
    install_sidecar(built, destination)
    print(f"engine sidecar ready: {destination}", flush=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("debug", "release"), default="debug")
    args = parser.parse_args()
    sync(args.profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
