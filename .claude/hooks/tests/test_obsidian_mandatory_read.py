"""lifecycle/obsidian-mandatory-read.py — la lecture obligatoire des fiches Shinzo, en séance locale ou dans le nuage.

Blocage de la séance du 2026-11-03 (nuage) : Shinzo n'est pas sur le disque, la commande qui le clone était bloquée
par ce même garde, et lire les fiches par GitHub ne comptait pas (seul l'outil Read comptait). Décision de Jay
(2026-11-04) : dans le nuage, soit les fiches sont lues sur le dépôt GitHub de Shinzo, soit l'absence du dépôt
local ne bloque pas. En local, le garde reste tel quel.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "obsidian-mandatory-read.py"
FICHES = ("_Cross-Project.md", "_Index.md", "Kata.md")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "work" / "Kata"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def _transcript(tmp_path: Path, calls: list[dict], failed: tuple[int, ...] = (), succeeded: bool = False) -> str:
    path = tmp_path / "transcript.jsonl"
    entries = [{"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "tool_use", "id": f"t{i}", **c}]}} for i, c in enumerate(calls)]
    entries += [{"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": f"t{i}", "is_error": True, "content": "File does not exist."}]}}
        for i in failed]
    if succeeded:  # in production every successful Read has its own tool_result, is_error false
        entries += [{"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}", "is_error": False, "content": "..."}]}}
            for i in range(len(calls)) if i not in failed]
    path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    return str(path)


def _github_reads(repo_name: str = "Shinzo") -> list[dict]:
    return [{"name": "mcp__github__get_file_contents",
             "input": {"owner": "theermite", "repo": repo_name, "path": f"02-Projets/{f}"}} for f in FICHES]


def _run(tmp_path: Path, *, cloud: bool, shinzo_on_disk: bool, calls: list[dict] | None = None,
         remote_value: str | None = None, shinzo_dir: Path | None = None, home_clone: bool = False,
         worktree: bool = False, failed: tuple[int, ...] = (), succeeded: bool = False):
    repo = _repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    if home_clone:
        (home / "Shinzo" / "02-Projets").mkdir(parents=True)
    if worktree:
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
                       cwd=repo, check=True)
        wt = tmp_path / "wt" / "branch-x"
        subprocess.run(["git", "worktree", "add", "-q", "-b", "x", str(wt)], cwd=repo, check=True)
        repo = wt
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_REMOTE", "SHINZO_DIR")}
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Path.home() lit USERPROFILE sous Windows, HOME ailleurs
    if cloud:
        env["CLAUDE_CODE_REMOTE"] = "true"
    if remote_value is not None:
        env["CLAUDE_CODE_REMOTE"] = remote_value
    if shinzo_dir is not None:
        env["SHINZO_DIR"] = str(shinzo_dir)
    if shinzo_on_disk:
        (tmp_path / "work" / "Shinzo" / "02-Projets").mkdir(parents=True)
    payload = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "mkdir build"},
               "transcript_path": _transcript(tmp_path, calls or [], failed, succeeded)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, cwd=repo, env=env, timeout=30)


def test_local_session_with_shinzo_on_disk_still_blocks_without_reads(tmp_path):
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True).returncode == 2


def test_local_session_without_shinzo_clone_still_blocks(tmp_path):
    """Hors nuage, un clone manquant est un défaut de la machine de Jay : le garde ne s'assouplit pas."""
    assert _run(tmp_path, cloud=False, shinzo_on_disk=False).returncode == 2


def test_cloud_session_with_shinzo_on_disk_still_blocks_without_reads(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True).returncode == 2


def test_cloud_session_without_shinzo_on_disk_is_not_blocked(tmp_path):
    out = _run(tmp_path, cloud=True, shinzo_on_disk=False)
    assert out.returncode == 0


def test_the_three_fiches_read_on_github_count_as_read_in_the_cloud(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True, calls=_github_reads()).returncode == 0


def test_github_reads_do_not_count_in_a_local_session(tmp_path):
    """Séance locale inchangée (Jay) : seul Read compte, une fiche locale peut être en avance sur GitHub."""
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_github_reads()).returncode == 2


def test_two_fiches_read_on_github_are_not_enough(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True, calls=_github_reads()[:2]).returncode == 2


def test_fiches_read_on_another_github_repo_do_not_count(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True, calls=_github_reads("Kata")).returncode == 2


def test_fiches_read_on_another_owner_do_not_count(tmp_path):
    calls = _github_reads()
    for c in calls:
        c["input"]["owner"] = "someone-else"
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True, calls=calls).returncode == 2


def test_remote_flag_other_than_true_is_not_the_cloud(tmp_path):
    assert _run(tmp_path, cloud=False, shinzo_on_disk=False, remote_value="1").returncode == 2


def test_shinzo_dir_variable_counts_as_a_clone_on_disk(tmp_path):
    clone = tmp_path / "elsewhere" / "02-Projets"
    clone.mkdir(parents=True)
    assert _run(tmp_path, cloud=True, shinzo_on_disk=False, shinzo_dir=clone.parent).returncode == 2


def test_home_shinzo_counts_as_a_clone_on_disk(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=False, home_clone=True).returncode == 2


def test_clone_next_to_the_main_repo_is_found_from_a_worktree(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True, worktree=True).returncode == 2


# --- une lecture compte si elle a réussi et si c'est la vraie fiche (Jay 2026-11-04) ------------------------------


def _local_reads(folder: str = "/x/Shinzo/02-Projets", names=FICHES) -> list[dict]:
    return [{"name": "Read", "input": {"file_path": f"{folder}/{n}"}} for n in names]


def test_the_three_real_fiches_read_with_read_pass(tmp_path):
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_local_reads()).returncode == 0


def test_a_failed_read_does_not_count(tmp_path):
    out = _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_local_reads(), failed=(0,))
    assert out.returncode == 2 and b"_Cross-Project" in out.stderr


def test_a_failed_github_read_does_not_count_in_the_cloud(tmp_path):
    assert _run(tmp_path, cloud=True, shinzo_on_disk=True, calls=_github_reads(), failed=(2,)).returncode == 2


def test_a_file_that_only_contains_the_name_does_not_count(tmp_path):
    calls = _local_reads(names=("_Cross-Project.md", "_Index.md.bak", "Kata.md"))
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=calls).returncode == 2


def test_the_notes_of_jay_are_not_the_project_fiche(tmp_path):
    calls = _local_reads(names=("_Cross-Project.md", "_Index.md", "Kata-Notes-Jay.md"))
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=calls).returncode == 2


def test_a_fiche_outside_a_projets_folder_does_not_count(tmp_path):
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_local_reads("/tmp/notes")).returncode == 2


def test_windows_paths_count(tmp_path):
    folder = "D:\\30-Dev-Projects\\Shinzo\\02-Projets\\"
    calls = [{"name": "Read", "input": {"file_path": folder + n}} for n in FICHES]
    assert all("/" not in c["input"]["file_path"] for c in calls)
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=calls).returncode == 0


def test_successful_reads_with_their_results_in_the_journal_still_count(tmp_path):
    """Chaque Read réussi a son tool_result (is_error faux) : une erreur qui les traiterait en échec bloquerait toute séance."""
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_local_reads(), succeeded=True).returncode == 0


def test_a_failed_read_among_successful_ones_still_blocks(tmp_path):
    out = _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_local_reads(), failed=(1,), succeeded=True)
    assert out.returncode == 2


def test_a_fiche_without_extension_counts(tmp_path):
    calls = _local_reads(names=("_Cross-Project", "_Index", "Kata"))
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=calls).returncode == 0


def test_the_former_projets_folder_and_other_case_count(tmp_path):
    calls = _local_reads("/x/Shinzo/01-Projets", names=("_CROSS-PROJECT.MD", "_index.md", "KATA.md"))
    assert _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=calls).returncode == 0


def test_the_block_message_says_what_to_do_when_the_project_fiche_does_not_exist(tmp_path):
    out = _run(tmp_path, cloud=False, shinzo_on_disk=True, calls=_local_reads(names=FICHES[:2]))
    assert out.returncode == 2 and b"does not exist" in out.stderr
