#!/usr/bin/env python3
"""End-user identifiers, kept as salted fingerprints — never in clear.

Why (2026-10-10, Shizen): the pseudo of a real end user, given by Jay for a
yes/no check, was copied into a published document. Confidentiality Gate C
forbade it; the writing did not hold. This module is the single place that
knows how an identifier becomes a fingerprint, so the guard that BLOCKS and the
tool that FILLS the list can never disagree (one normalisation, one hash).

Store (outside every repository, mode 600), default `~/.config/shinkofa/
end-user-identifiers/`, overridable with `EUI_STORE_DIR` (tests):

    salt            random, created once — fingerprints are useless elsewhere
    db.sha256       rebuilt from the account databases (`rebuild`)
    manual.sha256   names known only from conversation (`add`), kept on rebuild
    allow.sha256    words Jay declared harmless (`allow`), never block

CLI — values always arrive on STDIN, one per line, never as arguments (a
process listing would show them) and nothing is ever printed back:

    python3 end_user_identifiers.py rebuild   # replace db.sha256 (refused if it shrinks by half; --force)
    python3 end_user_identifiers.py add       # append to manual.sha256
    python3 end_user_identifiers.py allow     # append to allow.sha256
    python3 end_user_identifiers.py check     # exit 1 if any line matches
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import sys
import unicodedata
from pathlib import Path

MIN_LENGTH = 3
# Plancher d'une reconstruction : une liste qui fond de plus de moitie d'un coup
# vient d'une requete cassee, pas d'utilisateurs partis (relecture 2026-10-10).
REBUILD_FLOOR = 0.5
REBUILD_FLOOR_MIN_PREVIOUS = 10

_WORD = re.compile(r"[\w][\w.\-'/]*")
_SEGMENT_SPLIT = re.compile(r"[._\-/']+")
# Balisage qui coupe un mot sans le changer pour un lecteur : `Zor**vexa**`.
_MARKUP = str.maketrans("", "", "*`~")


def store_dir() -> Path:
    override = os.environ.get("EUI_STORE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".config" / "shinkofa" / "end-user-identifiers"


def normalize(value: str) -> str:
    """Lowercase, accents and invisible format characters (zero-width...) removed, whitespace collapsed."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(
        c for c in decomposed if not unicodedata.combining(c) and unicodedata.category(c) != "Cf"
    )
    return " ".join(stripped.lower().split())


def _salt(create: bool) -> bytes | None:
    path = store_dir() / "salt"
    if path.exists():
        return path.read_bytes()
    if not create:
        return None
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # O_EXCL : deux ecritures simultanees (reconstruction nocturne + ajout a la
    # main) ne peuvent pas poser deux sels differents.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes()
    with os.fdopen(fd, "wb") as handle:
        handle.write(secrets.token_hex(32).encode())
    return path.read_bytes()


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.chmod(path, 0o600)


def fingerprint(normalized: str, salt: bytes) -> str:
    return hashlib.sha256(salt + b"\0" + normalized.encode("utf-8")).hexdigest()


def candidates_from_value(value: str) -> set[str]:
    """What a stored value protects: the value itself, or the local part of an e-mail."""
    value = value.strip()
    if "@" in value:
        value = value.split("@", 1)[0]
    norm = normalize(value)
    return {norm} if len(norm.replace(" ", "")) >= MIN_LENGTH else set()


def candidates_from_text(text: str) -> set[str]:
    """Every word, every segment of a word (split on . _ - / '), and every pair of
    adjacent segments in both orders (`Dupont Jean`, `Jean-Dupont`)."""
    norm = normalize(text).translate(_MARKUP)
    found: set[str] = set()
    segments: list[str] = []
    for raw in _WORD.findall(norm):
        word = raw.rstrip(".-'/")
        if not word:
            continue
        found.add(word)
        parts = [part for part in _SEGMENT_SPLIT.split(word) if part]
        found.update(parts)
        segments.extend(parts)
    for first, second in zip(segments, segments[1:]):
        found.add(f"{first} {second}")
        found.add(f"{second} {first}")
    return found


def _read_set(name: str) -> set[str]:
    path = store_dir() / name
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def store_present() -> bool:
    return (store_dir() / "salt").exists()


def contains_identifier(text: str) -> bool:
    """True if the text carries at least one stored identifier. Never says which."""
    salt = _salt(create=False)
    if salt is None or not text:
        return False
    protected = (_read_set("db.sha256") | _read_set("manual.sha256")) - _read_set("allow.sha256")
    if not protected:
        return False
    return any(fingerprint(c, salt) in protected for c in candidates_from_text(text))


def _fingerprints_from_stdin(salt: bytes) -> set[str]:
    out: set[str] = set()
    for line in sys.stdin.read().splitlines():
        for candidate in candidates_from_value(line):
            out.add(fingerprint(candidate, salt))
    return out


def _save(name: str, fingerprints: set[str], append: bool) -> int:
    path = store_dir() / name
    current = _read_set(name) if append else set()
    merged = current | fingerprints
    _write_private(path, ("\n".join(sorted(merged)) + "\n").encode() if merged else b"")
    return len(merged)


def _rebuild_would_disarm(new_count: int) -> bool:
    previous = len(_read_set("db.sha256"))
    return previous >= REBUILD_FLOOR_MIN_PREVIOUS and new_count < previous * REBUILD_FLOOR


def main(argv: list[str]) -> int:
    force = "--force" in argv[2:]
    args = [a for a in argv if a != "--force"]
    if len(args) != 2 or args[1] not in {"rebuild", "add", "allow", "check"}:
        print(__doc__, file=sys.stderr)
        return 2
    command = args[1]

    if command == "check":
        if _salt(create=False) is None:
            print("aucune liste d'identifiants sur cette machine", file=sys.stderr)
            return 2
        lines = sys.stdin.read().splitlines()
        matches = sum(1 for line in lines if line.strip() and contains_identifier(line))
        print(f"{matches} correspondance(s) sur {len(lines)} ligne(s)")
        return 1 if matches else 0

    salt = _salt(create=True)
    fingerprints = _fingerprints_from_stdin(salt)
    if command == "rebuild" and not force and _rebuild_would_disarm(len(fingerprints)):
        print(
            f"refus : la nouvelle liste ({len(fingerprints)}) fait moins de la moitie de "
            "l'ancienne — requete cassee ? Liste gardee. Relancer avec --force si c'est voulu.",
            file=sys.stderr,
        )
        return 3
    target = {"rebuild": "db.sha256", "add": "manual.sha256", "allow": "allow.sha256"}[command]
    total = _save(target, fingerprints, append=command != "rebuild")
    print(f"{target} : {total} empreinte(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
