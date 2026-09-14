"""Le controle des CLAUDE.md, branche avant chaque `git push` (2026-09-14).

Jay 2026-09-13 : `check-claude-md.py` n'etait lance par rien — un CLAUDE.md
pouvait perimer sans que personne ne le voie. Le brancher sur `git push`
reprend le meme trigger, le meme WARN-jamais-BLOCK, que le controle de derive
methodologique deja present dans ce fichier (pre-push-drift-check.py).

Meme fixture que test_pre_push_drift_check.py : `Kata` cote a cote du projet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-push-drift-check.py"


def _locate_kata_root() -> Path:
    """The real Kata repo, wherever this test happens to run from.

    `parents[3]` broke the instant this file traveled to a propagated repo
    (2026-09-14, first propagation attempt): there, parents[3] is the
    RECEIVING repo itself, which has no scripts/check-claude-md.py -- that
    script stays canonical-only in Kata, never propagated. Same sibling
    lookup as the hook under test (_find_source): walk up to the repo this
    file lives in, then look for a sibling literally named "Kata".
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            sibling = parent.parent / "Kata"
            if (sibling / "scripts" / "check-claude-md.py").is_file():
                return sibling
            return parent  # we ARE Kata: no sibling needed, we are the source
    raise RuntimeError(f"no repository found above {here}")


KATA_ROOT = _locate_kata_root()


def _make_repo(base: Path) -> Path:
    (base / ".git").mkdir(parents=True, exist_ok=True)
    return base


def _run(cwd: Path, command: str) -> subprocess.CompletedProcess:
    payload = {"tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(cwd),
    )


def _copy_checker(src: Path) -> None:
    """Le vrai script, pas une doublure — c'est lui que le hook doit lancer."""
    checker = KATA_ROOT / "scripts" / "check-claude-md.py"
    dest = src / "scripts" / "check-claude-md.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(checker.read_text(encoding="utf-8"), encoding="utf-8")


def _src_and_project(tmp_path: Path):
    src = _make_repo(tmp_path / "Kata")
    (src / ".claude").mkdir(parents=True, exist_ok=True)  # _find_source requires it
    proj = _make_repo(tmp_path / "Kobo")
    _copy_checker(src)
    return src, proj


def _write_claude_md(base: Path, contenu: str, sous_dossier: bool = True) -> None:
    p = base / (".claude/CLAUDE.md" if sous_dossier else "CLAUDE.md")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenu, encoding="utf-8")


def test_warns_on_a_stale_claude_md_before_push(tmp_path):
    src, proj = _src_and_project(tmp_path)
    _write_claude_md(proj, "# Demo\n\nSource : MNK-GoRin/mnk/\n")
    res = _run(proj, "git push origin main")
    assert res.returncode == 0  # WARN, never block
    assert b"WARNING" in res.stderr
    assert b"CLAUDE.md" in res.stderr


def test_silent_when_claude_md_is_clean(tmp_path):
    src, proj = _src_and_project(tmp_path)
    _write_claude_md(proj, "# Demo\n\nProjet propre, aucun chemin mort.\n")
    res = _run(proj, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_silent_when_no_claude_md_at_all(tmp_path):
    src, proj = _src_and_project(tmp_path)
    res = _run(proj, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_silent_on_non_push_command(tmp_path):
    src, proj = _src_and_project(tmp_path)
    _write_claude_md(proj, "# Demo\n\nSource : MNK-GoRin/mnk/\n")
    res = _run(proj, "git status")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_silent_when_checker_script_is_absent(tmp_path):
    # Source trouvee (.claude present), mais scripts/check-claude-md.py n'y
    # vit pas (ancienne version de Kata) : degrade en silence, jamais un crash.
    src = _make_repo(tmp_path / "Kata")
    (src / ".claude").mkdir(parents=True, exist_ok=True)
    proj = _make_repo(tmp_path / "Kobo")
    _write_claude_md(proj, "# Demo\n\nSource : MNK-GoRin/mnk/\n")
    res = _run(proj, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_a_real_defect_survives_when_the_checker_crashes_on_a_second_file(tmp_path):
    # F2, relecture independante 2026-09-14 : `lines[:-1]` supposait que la
    # DERNIERE ligne de stdout est toujours le resume. Si le checker plante
    # sur un second fichier (encodage invalide) avant d'imprimer ce resume,
    # la derniere ligne restante est le VRAI defaut du premier fichier -- et
    # l'ancien code l'avalait. Root = defaut reel ; .claude/ = octets invalides.
    src, proj = _src_and_project(tmp_path)
    (proj / "CLAUDE.md").write_text("# Demo\n\nSource : MNK-GoRin/mnk/\n", encoding="utf-8")
    claude_dir = proj / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "CLAUDE.md").write_bytes(b"# Demo\n\n\xe9crit en latin-1\n")
    res = _run(proj, "git push origin main")
    assert res.returncode == 0  # WARN, never block, even on a checker crash
    assert b"WARNING" in res.stderr
    assert b"MNK-GoRin" in res.stderr, (
        f"le vrai defaut a disparu, stderr={res.stderr!r}"
    )


def test_the_canonical_source_itself_is_checked_too(tmp_path):
    # Contrairement a la derive methodologique, Kata verifie SON PROPRE
    # CLAUDE.md — rien ne l'exempte, lui aussi peut perimer.
    src, _proj = _src_and_project(tmp_path)
    _write_claude_md(src, "# Demo\n\nSource : MNK-GoRin/mnk/\n")
    res = _run(src, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" in res.stderr
    assert b"CLAUDE.md" in res.stderr
