"""Tests for `sync_engine_sidecar` — run with `python -m unittest scripts.test_sync_engine_sidecar`
from the repo root (or `python scripts/test_sync_engine_sidecar.py`).

The guard these protect: the engine embedded in the app must never be older than its source.
Measured 2026-10-13 — the sidecar sat frozen at its 2026-09-14 build for a month, in dev AND
in the published 0.6.1 installer, because `tauri-build` overwrites the freshly compiled
engine with the sidecar copy on every app build.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_engine_sidecar as sidecar  # noqa: E402


def touch(path: Path, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))
    return path


class IsStale(unittest.TestCase):
    def test_should_be_stale_when_a_source_is_newer_than_the_engine(self):
        self.assertTrue(sidecar.is_stale(engine_mtime=100.0, newest_source_mtime=200.0))

    def test_should_be_fresh_when_the_engine_is_newer_than_every_source(self):
        self.assertFalse(sidecar.is_stale(engine_mtime=300.0, newest_source_mtime=200.0))

    def test_should_be_fresh_when_the_engine_was_built_in_the_same_second(self):
        self.assertFalse(sidecar.is_stale(engine_mtime=200.0, newest_source_mtime=200.0))


class NewestSourceMtime(unittest.TestCase):
    def test_should_read_the_newest_rust_file_of_the_engine_and_protocol_crates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root / "crates/engine/src/main.rs", 100.0)
            touch(root / "crates/protocol/src/wire.rs", 500.0)
            touch(root / "crates/protocol/Cargo.toml", 300.0)

            self.assertEqual(sidecar.newest_source_mtime(root), 500.0)

    def test_should_ignore_files_that_are_not_engine_inputs(self):
        # A newer README or a newer app source must not make a fresh engine look stale.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root / "crates/engine/src/main.rs", 100.0)
            touch(root / "crates/engine/README.md", 900.0)
            touch(root / "src/lib.rs", 900.0)

            self.assertEqual(sidecar.newest_source_mtime(root), 100.0)


class InstallSidecar(unittest.TestCase):
    def test_should_replace_a_stale_sidecar_with_the_built_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            built = touch(root / "target/debug/hikari-engine.exe", 1000.0)
            built.write_bytes(b"new engine")
            old = touch(root / "binaries/hikari-engine-x86_64-pc-windows-msvc.exe", 10.0)
            old.write_bytes(b"old engine")

            sidecar.install_sidecar(built, old)

            self.assertEqual(old.read_bytes(), b"new engine")

    def test_should_refuse_a_copy_that_does_not_match_the_built_engine(self):
        # A locked or half-written destination must stop the build, never ship silently.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            built = touch(root / "target/debug/hikari-engine.exe", 1000.0)
            built.write_bytes(b"new engine")
            destination = root / "binaries/hikari-engine-x86_64-pc-windows-msvc.exe"

            real_copy = sidecar.shutil.copy2

            def truncated_copy(src, dst):
                real_copy(src, dst)
                Path(dst).write_bytes(b"new")

            sidecar.shutil.copy2 = truncated_copy
            try:
                with self.assertRaises(SystemExit):
                    sidecar.install_sidecar(built, destination)
            finally:
                sidecar.shutil.copy2 = real_copy


if __name__ == "__main__":
    unittest.main()
