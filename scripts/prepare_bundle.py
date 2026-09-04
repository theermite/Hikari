#!/usr/bin/env python3
"""Prepare everything `tauri build` needs that cargo alone does not produce.

Two artefacts are missing from a plain `cargo build --release`, and the Tauri bundler
reads both BEFORE it runs — so they have to exist first:

1. `src-tauri/binaries/hikari-engine-<target-triple><ext>` — the engine binary under the
   name the Tauri `externalBin` mechanism expects. Tauri strips the triple at install
   time, so it lands as `hikari-engine.exe` right next to the app. That is exactly where
   `engine_bridge::engine_path()` looks for it (ADR-013: launched by path, never linked).

2. `src-tauri/obs-runtime/` — the OBS runtime (obs.dll, `data/`, `obs-plugins/`). Fetched
   by `cargo obs-build`, which resolves the release matching the `libobs` crate and
   verifies its checksums. Never vendored into git: it weighs tens of megabytes and has
   its own distribution (CDC §8 FMEA — a downloaded binary is checksum-verified before
   it is ever executed, and `cargo obs-build` is what does that verification here).

Run it directly, or through `pnpm bundle`, which chains it with `tauri build`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_TAURI = REPO_ROOT / "src-tauri"
RUNTIME_DIR = SRC_TAURI / "obs-runtime"
BINARIES_DIR = SRC_TAURI / "binaries"
ENGINE_STEM = "hikari-engine"


def run(command: list[str], cwd: Path) -> None:
    """Run a build command, letting its output through and stopping on failure.

    Output is NOT captured: a cargo build can sit for minutes on a Windows file lock, and
    swallowing its stream hides the one line that explains the wait (cross-project lesson
    2026-07-31 — a pipe hid a build-lock message for two hours).
    """
    print(f"\n$ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def host_triple() -> str:
    """The current platform's Rust target triple, e.g. `x86_64-pc-windows-msvc`."""
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


def sidecar_name(triple: str, executable_suffix: str) -> str:
    """The filename Tauri's `externalBin` expects for the engine on this platform."""
    return f"{ENGINE_STEM}-{triple}{executable_suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-runtime",
        action="store_true",
        help="re-download the OBS runtime even when src-tauri/obs-runtime already exists",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="reuse the existing release binaries instead of rebuilding the workspace",
    )
    args = parser.parse_args()

    suffix = ".exe" if sys.platform == "win32" else ""

    if not args.skip_build:
        run(["cargo", "build", "--workspace", "--release"], cwd=SRC_TAURI)

    if args.refresh_runtime and RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)

    if not RUNTIME_DIR.exists():
        run(
            ["cargo", "obs-build", "build", "--out-dir", "obs-runtime", "--remove-pdbs"],
            cwd=SRC_TAURI,
        )
    else:
        print(f"OBS runtime already present: {RUNTIME_DIR}", flush=True)

    engine = SRC_TAURI / "target" / "release" / f"{ENGINE_STEM}{suffix}"
    if not engine.is_file():
        raise SystemExit(
            f"engine binary missing: {engine}\n"
            "Run without --skip-build, or build the workspace first."
        )

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    destination = BINARIES_DIR / sidecar_name(host_triple(), suffix)
    shutil.copy2(engine, destination)
    print(f"\nengine sidecar ready: {destination}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
