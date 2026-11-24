"""Les gardes de fin de message ne font plus réécrire la réponse: ils laissent un rappel pour le tour suivant.

Jay 2026-11-24 (capture): le refus d'un Stop arrive APRÈS l'affichage de la réponse, donc toute réécriture la lui montre
deux fois. Garde à l'envers: avant ce changement, sept gardes de Stop appelaient `block` (code 2).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

from session_state import read_state  # noqa: E402

REGLAGES = HOOKS.parent / "settings.json"
INJECT = HOOKS / "lifecycle" / "rappel-inject.py"


def _gardes_de_stop() -> list[Path]:
    reglages = json.loads(REGLAGES.read_text(encoding="utf-8"))
    sortie = []
    # SubagentStop est hors champ: Jay ne lit pas la fin de message d'un sous-agent, aucune double lecture à éviter
    # (relecture du 2026-11-24): `langues-check` y garde son refus, voir le test dédié plus bas.
    for evenement in ("Stop",):
        for bloc in reglages["hooks"].get(evenement, []):
            for h in bloc["hooks"]:
                nom = re.search(r'_run\.sh"\s+(\S+)', h["command"]).group(1)
                sortie.append(HOOKS / nom)
    return sortie


def test_aucun_garde_de_stop_ne_refuse_la_fin_du_message():
    # `langues-check` garde un refus, mais seulement dans sa branche SubagentStop (test dédié plus bas)
    refusent = [p.name for p in _gardes_de_stop() if p.name != "langues-check.py"
                and re.search(r"(?<![\w])block\(|(?<![\w])(?:sys\.)?exit\(\s*2\s*\)|SystemExit\(\s*2\s*\)", p.read_text(encoding="utf-8"))]
    assert refusent == [], f"ces gardes de Stop refusent encore (la réponse serait montrée deux fois): {refusent}"


def _depot(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_rappel_garde_puis_efface_une_seule_fois(tmp_path):
    from rappels import NOMS, garder
    depot = _depot(tmp_path)
    garder("recap", "Trop de jargon.", session_id="s1", repo_root=depot)
    premier = subprocess.run([sys.executable, str(INJECT)], input=json.dumps({"session_id": "s1"}).encode(),
                             capture_output=True, timeout=20, cwd=depot)
    texte = premier.stdout.decode("utf-8", "replace")
    assert premier.returncode == 0 and "Trop de jargon." in texte and "Ne réécris pas" in texte
    assert read_state("rappel-recap", session_id="s1", repo_root=depot).get("pending") is False
    second = subprocess.run([sys.executable, str(INJECT)], input=json.dumps({"session_id": "s1"}).encode(),
                            capture_output=True, timeout=20, cwd=depot)
    assert second.stdout == b""
    assert "recap" in NOMS


def test_plusieurs_rappels_se_disent_ensemble(tmp_path):
    from rappels import garder
    depot = _depot(tmp_path)
    garder("recap", "Premier rappel.", session_id="s2", repo_root=depot)
    garder("francais", "Second rappel.", session_id="s2", repo_root=depot)
    r = subprocess.run([sys.executable, str(INJECT)], input=json.dumps({"session_id": "s2"}).encode(),
                       capture_output=True, timeout=20, cwd=depot)
    texte = r.stdout.decode("utf-8", "replace")
    assert "Premier rappel." in texte and "Second rappel." in texte


def test_un_nom_inconnu_est_refuse(tmp_path):
    from rappels import garder
    import pytest
    with pytest.raises(ValueError):
        garder("inconnu", "x", session_id="s3", repo_root=_depot(tmp_path))


def test_rien_en_attente_ne_dit_rien_et_une_entree_illisible_ne_casse_rien(tmp_path):
    depot = _depot(tmp_path)
    assert subprocess.run([sys.executable, str(INJECT)], input=json.dumps({"session_id": "s4"}).encode(),
                          capture_output=True, timeout=20, cwd=depot).stdout == b""
    assert subprocess.run([sys.executable, str(INJECT)], input=b"pas du json", capture_output=True, timeout=20, cwd=depot).returncode == 0


def _appeler_rappel(depot: Path, nom: str, session: str | None):
    code = ("import sys; sys.path.insert(0, %r); import common; common._INPUT = {%s}; common.rappel(%r, 'BLOCKED: un message')"
            % (str(LIB), f"'session_id': {session!r}" if session else "", nom))
    return subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=20, cwd=depot)


def test_rappel_range_le_message_sous_la_seance_et_sort_zero(tmp_path):
    depot = _depot(tmp_path)
    r = _appeler_rappel(depot, "recap", "sA")
    assert r.returncode == 0 and "RAPPEL (tour suivant" in r.stderr.decode("utf-8", "replace")
    etat = read_state("rappel-recap", session_id="sA", repo_root=depot)
    assert etat.get("pending") is True and etat.get("message") == "un message", "le préfixe BLOCKED: ne se rend plus"


def test_rappel_sans_seance_ne_range_rien_qui_serait_dit_a_une_autre(tmp_path):
    depot = _depot(tmp_path)
    r = _appeler_rappel(depot, "recap", None)
    assert r.returncode == 0 and "RAPPEL (tour suivant" in r.stderr.decode("utf-8", "replace")
    assert not (depot / ".claude" / "state").exists() or not list((depot / ".claude" / "state").glob("rappel-*"))


def test_un_nom_de_rappel_inconnu_est_une_erreur_visible_pas_un_rappel_perdu(tmp_path):
    r = _appeler_rappel(_depot(tmp_path), "recapp", "sB")
    assert r.returncode != 0 and b"rappel inconnu" in r.stderr


def test_le_garde_des_langues_garde_son_refus_sur_un_sous_agent():
    """Jay ne lit pas un sous-agent: le refus le fait corriger son marqueur avant de rendre la main (relecture 2026-11-24)."""
    source = (HOOKS / "quality" / "langues-check.py").read_text(encoding="utf-8")
    assert len(re.findall(r"(?<![\w])block\(", source)) == 1, "un seul refus dans ce garde"
    branche = source.split('data.get("hook_event_name") == "SubagentStop"')[1].split("rappel(")[0]
    assert "block(message_de_refus(erreurs))" in branche, "le refus est dans la branche SubagentStop, avant le rappel"
