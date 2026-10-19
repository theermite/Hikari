"""frozen_copies — a frozen copy of a Kata file kept by a project falls behind.

Dogu keeps Kata's shell guard and secret masker, frozen, as the oracle its own
Elixir reader is compared to (Dogu `test-fixtures/oracle/`). When Kata changes
one of them, nothing told anyone the copy was behind (Jay, 2026-10-18).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))
import frozen_copies as fc  # noqa: E402

HOOK = HOOKS / "guards" / "frozen-copy-alert.py"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _world(tmp_path: Path, kata_text: str, copy_text: str) -> tuple[Path, tuple]:
    """A Kata repo and a consumer copy side by side, as on every machine."""
    kata = tmp_path / "Kata"
    (kata / ".claude/hooks/guards").mkdir(parents=True)
    (kata / ".claude/hooks/guards/bash-guard.py").write_text(kata_text)
    copy = tmp_path / "Proj/oracle"
    copy.mkdir(parents=True)
    (copy / "SHA256SUMS").write_text(f"{_sha(copy_text)}  hooks/guards/bash-guard.py\n")
    copies = (
        fc.Copy(
            consumer="Proj",
            directory="Proj/oracle",
            readme="oracle/README.md",
            files={".claude/hooks/guards/bash-guard.py": "hooks/guards/bash-guard.py"},
        ),
    )
    return kata, copies


def test_a_copy_that_matches_kata_is_not_behind(tmp_path):
    kata, copies = _world(tmp_path, "v1", "v1")
    assert fc.behind(kata, copies) == []


def test_a_kata_file_that_moved_puts_the_copy_behind(tmp_path):
    kata, copies = _world(tmp_path, "v2", "v1")
    [late] = fc.behind(kata, copies)
    assert (late.consumer, late.source) == ("Proj", ".claude/hooks/guards/bash-guard.py")


def test_a_copy_missing_from_this_machine_is_skipped(tmp_path):
    kata, copies = _world(tmp_path, "v2", "v1")
    (tmp_path / "Proj/oracle/SHA256SUMS").unlink()
    (tmp_path / "Proj/oracle").rmdir()
    assert fc.behind(kata, copies) == []


def test_a_file_the_copy_never_recorded_counts_as_behind(tmp_path):
    kata, copies = _world(tmp_path, "v1", "v1")
    (tmp_path / "Proj/oracle/SHA256SUMS").write_text("")
    assert len(fc.behind(kata, copies)) == 1


def test_the_registry_names_dogu_and_the_files_its_oracle_holds():
    [dogu] = [c for c in fc.COPIES if c.consumer == "Dogu"]
    assert dogu.directory == "Dogu/test-fixtures/oracle"
    assert set(dogu.files.values()) == {
        "hooks/lib/common.py",
        "hooks/lib/shell_parse.py",
        "hooks/lib/secret_mask.py",
        "hooks/guards/bash-guard.py",
        "hooks/guards/git_push_guard.py",
    }


def test_the_message_says_what_to_copy_and_where(tmp_path):
    kata, copies = _world(tmp_path, "v2", "v1")
    text = fc.message(fc.behind(kata, copies))
    assert "Proj" in text and "bash-guard.py" in text and "oracle/README.md" in text


# --- the hook, after a real commit in a real (temporary) Kata repo ----------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _run_hook(cwd: Path, command: str) -> subprocess.CompletedProcess:
    # Launched from elsewhere on purpose: the repo is the one the command ran in (payload cwd).
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})
    return subprocess.run(
        [sys.executable, str(HOOK)], input=payload, text=True, capture_output=True, cwd=cwd.parent
    )


def _kata_repo(tmp_path: Path, guard_text: str) -> Path:
    kata = tmp_path / "Kata"
    (kata / "scripts").mkdir(parents=True)
    (kata / "scripts/propagate-methodology.py").write_text("")
    (kata / ".claude/hooks/guards").mkdir(parents=True)
    (kata / ".claude/hooks/guards/bash-guard.py").write_text(guard_text)
    (kata / "README.md").write_text("x")
    _git(kata, "init", "-q")
    _git(kata, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(kata, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    copy = tmp_path / "Dogu/test-fixtures/oracle"
    copy.mkdir(parents=True)
    (copy / "SHA256SUMS").write_text(f"{_sha(guard_text)}  hooks/guards/bash-guard.py\n")
    return kata


def _commit(kata: Path, path: str, text: str) -> None:
    (kata / path).write_text(text)
    _git(kata, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "change")


def test_the_hook_alerts_after_a_kata_commit_that_moves_a_copied_file(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    out = _run_hook(kata, 'git commit -m "guard"')
    assert out.returncode == 0
    context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Dogu" in context and "bash-guard.py" in context


def test_the_hook_is_silent_when_the_commit_touched_no_copied_file(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    _commit(kata, "README.md", "y")
    out = _run_hook(kata, 'git commit -m "doc"')
    assert out.returncode == 0 and out.stdout == ""


def test_the_hook_is_silent_outside_kata(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    (kata / "scripts/propagate-methodology.py").unlink()
    _git(kata, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "not kata")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    out = _run_hook(kata, 'git commit -m "guard"')
    assert out.returncode == 0 and out.stdout == ""


def test_the_hook_ignores_a_command_that_is_not_git(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    out = _run_hook(kata, "ls -la")
    assert out.returncode == 0 and out.stdout == ""
    # The first git command after Kata moved, whatever it is (a pull, a status), says it.
    assert _alerts(_run_hook(kata, "git status"))


def _alerts(out: subprocess.CompletedProcess) -> bool:
    return out.returncode == 0 and "Dogu" in out.stdout


def test_the_hook_says_it_once_per_new_state_of_kata(tmp_path):
    # Review 2026-10-18: any later command mentioning "git commit" repeated the alert.
    kata = _kata_repo(tmp_path, "v1")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    assert _alerts(_run_hook(kata, 'git commit -m "guard"'))
    for command in ('git commit -m "rien"', "git log --grep='git commit'", 'echo "git commit"'):
        assert _run_hook(kata, command).stdout == ""


def test_the_hook_hears_a_commit_made_from_another_project(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    assert _alerts(_run_hook(kata, f'git -C {kata} commit -m "guard"'))


def test_the_hook_hears_a_merge_that_brings_a_changed_guard(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    _run_hook(kata, "git status")  # the hook has seen main as it was
    _git(kata, "switch", "-qc", "side")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    _git(kata, "switch", "-q", "-")
    _commit(kata, "README.md", "y")
    _git(kata, "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-edit", "side")
    assert _alerts(_run_hook(kata, "git merge side"))


def test_the_committed_content_counts_not_the_file_on_disk(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    guard = kata / ".claude/hooks/guards/bash-guard.py"
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    _run_hook(kata, 'git commit -m "v2"')
    # Back to the copied version in the commit, with other work left on disk only.
    guard.write_text("v1")
    _git(kata, "add", "--", ".claude/hooks/guards/bash-guard.py")
    guard.write_text("v3 en cours")
    _git(kata, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "back to v1")
    assert _run_hook(kata, 'git commit -m "back"').stdout == ""


def test_the_binary_and_bom_forms_of_sha256sums_are_read(tmp_path):
    kata, copies = _world(tmp_path, "v1", "v1")
    sums = tmp_path / "Proj/oracle/SHA256SUMS"
    sums.write_text("\ufeff" + f"{_sha('v1')} *hooks/guards/bash-guard.py\r\n", encoding="utf-8")
    assert fc.behind(kata, copies) == []


def test_a_damaged_state_never_breaks_a_git_command(tmp_path):
    # 2nd review: `[]` in the state raised on every git command, forever.
    kata = _kata_repo(tmp_path, "v1")
    state = kata / ".claude/state/frozen-copy-alert.json"
    state.parent.mkdir(parents=True)
    for damaged in ("[]", "null", '"x"', "{"):
        state.write_text(damaged)
        _commit(kata, ".claude/hooks/guards/bash-guard.py", f"v-{len(damaged)}-{damaged!r}")
        out = _run_hook(kata, 'git commit -m "guard"')
        assert out.returncode == 0 and out.stderr.count("Traceback") == 0


def test_an_unwritable_state_never_breaks_a_git_command(tmp_path):
    kata = _kata_repo(tmp_path, "v1")
    (kata / ".claude/state").mkdir(parents=True)
    (kata / ".claude/state/frozen-copy-alert.json").mkdir()  # a directory: write fails
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    out = _run_hook(kata, 'git commit -m "guard"')
    assert out.returncode == 0 and "Traceback" not in out.stderr


def test_going_back_in_history_says_nothing(tmp_path):
    # 2nd review: a checkout back and forth repeated an alert already given.
    kata = _kata_repo(tmp_path, "v1")
    _commit(kata, ".claude/hooks/guards/bash-guard.py", "v2")
    assert _alerts(_run_hook(kata, 'git commit -m "guard"'))
    _git(kata, "checkout", "-q", "HEAD~1")
    assert _run_hook(kata, "git checkout HEAD~1").stdout == ""
    _git(kata, "checkout", "-q", "-")
    assert _run_hook(kata, "git checkout -").stdout == ""
