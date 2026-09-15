"""iter_entries — le lecteur canonique, teste directement.

10e relecture independante (2026-09-15) : en corrigeant context-gauge.py pour
deleguer sa lecture a iter_entries, la relecture a trouve 2 vrais defauts DANS
le lecteur canonique lui-meme -- affectant les 8 autres appelants du repo, pas
seulement context-gauge.py :

1. `p.exists()` est HORS du try/except OSError : un `stat()` qui echoue sur
   permission refusee (ACL Windows, dossier verrouille par un antivirus ou
   OneDrive) fait planter l'appelant au lieu de rendre [].
2. `read_text().splitlines()` coupe sur les separateurs de ligne Unicode
   (U+2028, U+2029, \\x85) -- legaux A L'INTERIEUR d'une chaine JSON (un
   prompt colle depuis Word/PDF, un fichier lu par l'outil Read). Une entree
   valide se retrouve coupee en deux lignes JSON invalides, silencieusement
   perdue.

Mesure sur le plus gros transcript reel de la machine (63,7 Mo) : le meme
defaut faisait passer le pic memoire de ~1 Mo (streaming ligne a ligne) a
~573 Mo (fichier entier + liste de lignes en memoire).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import transcript_reader  # noqa: E402


def _write_bytes(tmp_path: Path, data: bytes) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_bytes(data)
    return p


def test_should_survive_a_permission_failure_instead_of_raising(tmp_path, monkeypatch):
    # Protege l'ouverture du fichier, le point d'entree I/O direct.
    p = tmp_path / "t.jsonl"
    p.write_text('{"a": 1}\n', encoding="utf-8")

    def _open_refuse(self, *a, **k):
        raise PermissionError(13, "Access is denied", str(self))

    monkeypatch.setattr(Path, "open", _open_refuse)
    assert list(transcript_reader.iter_entries(p)) == []


def test_should_read_the_file_even_when_exists_reports_eacces(tmp_path, monkeypatch):
    # 12e relecture independante (2026-09-15) : le tour precedent affirmait
    # ce garde a l'envers impossible ("le chemin de code a disparu"). Faux --
    # pathlib._abc's PathBase.exists() n'ignore que
    # (ENOENT, ENOTDIR, EBADF, 10062) et RELANCE tout le reste, EACCES (13)
    # compris. Meme si iter_entries n'appelle plus exists() lui-meme, ce test
    # verrouille que personne ne le reintroduise hors du bloc protege : le
    # patcher sur exists() ET stat() (l'un ou l'autre selon l'implementation
    # pathlib) suffit a reproduire fidelement un vrai fichier en acces refuse.
    p = tmp_path / "t.jsonl"
    p.write_text('{"a": 1}\n', encoding="utf-8")

    def _eacces(self, *a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "exists", _eacces)
    monkeypatch.setattr(Path, "stat", _eacces)
    assert list(transcript_reader.iter_entries(p)) == [{"a": 1}]


def test_should_survive_a_value_error_from_an_unencodable_path(tmp_path):
    # 11e relecture independante (2026-09-15) : Path.exists() absorbe
    # explicitement ValueError ("Non-encodable path", ex. un octet nul dans
    # le chemin). En le retirant, le seul `except OSError` du correctif
    # precedent laissait fuir cette classe d'erreur -- ValueError n'est pas
    # une OSError. Un chemin porteur d'un octet nul la reproduit.
    chemin_invalide = str(tmp_path / "t.jsonl") + "\x00suffixe"
    assert list(transcript_reader.iter_entries(chemin_invalide)) == []


def test_should_keep_an_entry_containing_a_unicode_line_separator(tmp_path):
    # U+2028 (LINE SEPARATOR) a l'interieur de la valeur JSON, pas comme
    # separateur de ligne du fichier.
    ligne = '{"message": {"usage": {"input_tokens": 650000}}, "note": "a b"}\n'
    p = _write_bytes(tmp_path, ligne.encode("utf-8"))
    entrees = list(transcript_reader.iter_entries(p))
    assert len(entrees) == 1
    assert entrees[0]["note"] == "a b"


def test_should_keep_an_entry_containing_a_nel_separator(tmp_path):
    ligne = '{"a": "x\x85y"}\n'
    p = _write_bytes(tmp_path, ligne.encode("utf-8"))
    entrees = list(transcript_reader.iter_entries(p))
    assert len(entrees) == 1
    assert entrees[0]["a"] == "x\x85y"


def test_should_keep_an_entry_containing_a_paragraph_separator(tmp_path):
    ligne = '{"a": "x y"}\n'
    p = _write_bytes(tmp_path, ligne.encode("utf-8"))
    entrees = list(transcript_reader.iter_entries(p))
    assert len(entrees) == 1
    assert entrees[0]["a"] == "x y"


# --- non-regression : comportement deja tenu, a garder -----------------------


def test_default_order_is_latest_first(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"n": 1}\n{"n": 2}\n', encoding="utf-8")
    assert [e["n"] for e in transcript_reader.iter_entries(p)] == [2, 1]


def test_reverse_false_is_chronological(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"n": 1}\n{"n": 2}\n', encoding="utf-8")
    assert [e["n"] for e in transcript_reader.iter_entries(p, reverse=False)] == [1, 2]


def test_a_malformed_line_is_skipped_silently(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"n": 1}\nnot json\n{"n": 2}\n', encoding="utf-8")
    assert [e["n"] for e in transcript_reader.iter_entries(p, reverse=False)] == [1, 2]


def test_a_missing_transcript_yields_nothing(tmp_path):
    assert list(transcript_reader.iter_entries(tmp_path / "absent.jsonl")) == []


def test_an_empty_path_yields_nothing():
    assert list(transcript_reader.iter_entries("")) == []
