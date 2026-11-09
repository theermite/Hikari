"""Journal de frictions — une ligne par refus de garde-fou, et les notes que Takumi y ajoute à la main.

Pourquoi (Jay, 2026-11-09): « il faudrait une note globale où Takumi ajoute une ligne quand un garde-fou
bloque à tort, pour que je puisse le traiter en revenant dans Kata ». Le journal par séance ne compte que
des totaux: ni la cible, ni le garde-fou, ni le motif.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import friction_log  # noqa: E402

DIGEST = RACINE / ".claude/hooks/lifecycle/frictions-digest.py"
_spec = importlib.util.spec_from_file_location("frictions_digest", DIGEST)
digest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(digest)


def test_append_ecrit_une_ligne_json_par_refus(tmp_path):
    journal = tmp_path / "f.jsonl"
    friction_log.append({"garde": "annexes-gate.py", "outil": "Edit", "cible": "a.py", "motif": "BLOCKED: x"}, chemin=journal)
    friction_log.append({"garde": "bash-guard.py", "outil": "Bash", "cible": "git", "motif": "BLOCKED: y"}, chemin=journal)
    lignes = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines()]
    assert [l["garde"] for l in lignes] == ["annexes-gate.py", "bash-guard.py"]
    assert all("ts" in l for l in lignes)


def test_append_coupe_le_motif_et_ne_casse_jamais(tmp_path):
    journal = tmp_path / "f.jsonl"
    friction_log.append({"motif": "x" * 5000}, chemin=journal)
    assert len(json.loads(journal.read_text(encoding="utf-8"))["motif"]) <= friction_log.MAX_MOTIF
    friction_log.append({"garde": "g"}, chemin=tmp_path / "dossier" / "absent" / "f.jsonl")  # crée le dossier
    friction_log.append({"garde": "g"}, chemin=tmp_path)  # un dossier n'est pas un fichier: pas d'exception


def test_arret_par_variable_d_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("FRICTION_LOG", str(tmp_path / "f.jsonl"))
    monkeypatch.setenv("FRICTION_LOG_OFF", "1")
    friction_log.append({"garde": "g"})
    assert not (tmp_path / "f.jsonl").exists()


def test_un_refus_reel_est_journalise_sans_le_texte_de_la_commande(tmp_path):
    """Bout en bout: un garde qui refuse écrit sa ligne; le secret de la commande n'y figure jamais."""
    journal = tmp_path / "f.jsonl"
    code = ("import sys, json; sys.path.insert(0, r'%s'); import common\n"
            "common.read_hook_input(); common.block('BLOCKED: essai. RECOVERY: rien')\n"
            % (RACINE / ".claude/hooks/lib"))
    entree = {"tool_name": "Bash", "tool_input": {"command": "curl -H 'Authorization: SECRET123' x"}, "session_id": "s1"}
    env = {**os.environ, "FRICTION_LOG": str(journal)}
    env.pop("FRICTION_LOG_OFF", None)
    res = subprocess.run([sys.executable, "-c", code], input=json.dumps(entree).encode(), env=env, capture_output=True)
    assert res.returncode == 2
    ligne = journal.read_text(encoding="utf-8")
    assert "SECRET123" not in ligne
    assert json.loads(ligne)["outil"] == "Bash" and json.loads(ligne)["cible"] == "curl"


def test_un_secret_en_premier_mot_n_entre_jamais_dans_le_journal(tmp_path, monkeypatch):
    """Relecture 2026-11-09: `GITHUB_TOKEN=ghp_x git push` ou une adresse avec mot de passe sont des « premiers mots »."""
    journal = tmp_path / "f.jsonl"
    monkeypatch.setenv("FRICTION_LOG", str(journal))
    monkeypatch.delenv("FRICTION_LOG_OFF", raising=False)
    for commande in ("GITHUB_TOKEN=ghp_SECRETVALUE git push", "https://user:pass@host/x", "TOKEN=abc curl x", "git push"):
        friction_log.refus("BLOCKED: x", {"tool_name": "Bash", "tool_input": {"command": commande}}, "g.py")
    texte = journal.read_text(encoding="utf-8")
    assert "SECRETVALUE" not in texte and "pass@" not in texte and "abc" not in texte
    assert json.loads(texte.splitlines()[-1])["cible"] == "git"  # un mot sûr reste utile


def test_le_refus_tient_meme_si_le_journal_plante():
    code = "\n".join([f"import sys; sys.path.insert(0, r'{RACINE / '.claude/hooks/lib'}'); import common, friction_log",
                     "friction_log.refus = lambda *a, **k: 1 / 0",
                     "common.read_hook_input(); common.block('BLOCKED: essai')"])
    res = subprocess.run([sys.executable, "-c", code], input=b"{}", capture_output=True)
    assert res.returncode == 2 and b"BLOCKED: essai" in res.stderr


def test_les_garde_fous_qui_sortent_sans_block_laissent_aussi_leur_trace(tmp_path):
    """Relecture 2026-11-09: bash-guard et write-guard font `exit(2)` eux-mêmes: leurs refus étaient invisibles."""
    journal = tmp_path / "f.jsonl"
    env = {**os.environ, "FRICTION_LOG": str(journal), "PYTHONIOENCODING": "utf-8"}
    env.pop("FRICTION_LOG_OFF", None)
    entree = {"tool_name": "Bash", "tool_input": {"command": "git add -A"}, "session_id": "s", "cwd": str(tmp_path)}
    res = subprocess.run([sys.executable, str(RACINE / ".claude/hooks/guards/bash-guard.py")],
                         input=json.dumps(entree).encode(), env=env, capture_output=True, cwd=tmp_path)
    assert res.returncode == 2
    assert json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])["garde"] == "bash-guard.py"


def test_la_note_a_la_main_est_marquee_manuelle(tmp_path):
    journal = tmp_path / "f.jsonl"
    friction_log.note("le garde X refuse une lecture légitime", projet="Kata", chemin=journal)
    ligne = json.loads(journal.read_text(encoding="utf-8"))
    assert ligne["manuel"] is True and "refuse une lecture" in ligne["motif"] and ligne["projet"] == "Kata"


def test_resume_compte_par_garde_et_distingue_les_notes(tmp_path):
    ev = [{"garde": "a.py", "motif": "BLOCKED: m1", "cible": "x"}] * 3 + [{"garde": "b.py", "motif": "BLOCKED: m2"}] + \
         [{"manuel": True, "motif": "faux positif sur Z"}]
    texte = friction_log.resume(ev)
    assert "5" in texte and "a.py" in texte and "faux positif sur Z" in texte
    assert texte.index("a.py") < texte.index("b.py")  # le plus fréquent d'abord


def test_le_demarrage_ne_parle_que_des_nouvelles_lignes(tmp_path):
    journal = tmp_path / "f.jsonl"
    vu = tmp_path / "vu"
    friction_log.append({"garde": "a.py", "motif": "BLOCKED: m"}, chemin=journal)
    d1 = digest.build_decision(journal, vu)
    assert "a.py" in d1["hookSpecificOutput"]["additionalContext"]
    assert digest.build_decision(journal, vu) == {}  # rien de neuf: silence
    friction_log.append({"garde": "c.py", "motif": "BLOCKED: n"}, chemin=journal)
    assert "c.py" in digest.build_decision(journal, vu)["hookSpecificOutput"]["additionalContext"]


def test_journal_absent_ou_vide_donne_le_silence(tmp_path):
    assert digest.build_decision(tmp_path / "absent.jsonl", tmp_path / "vu") == {}


def test_un_secret_seul_en_premier_mot_n_entre_pas_non_plus(tmp_path, monkeypatch):
    """Seconde relecture 2026-11-09: `sk-…` ou `ghp_…` n'utilisent que des caractères sûrs. Liste fermée de commandes connues."""
    journal = tmp_path / "f.jsonl"
    monkeypatch.setenv("FRICTION_LOG", str(journal))
    monkeypatch.delenv("FRICTION_LOG_OFF", raising=False)
    jeton = "sk-" + "a1b2" * 8
    for commande in (jeton + " x", "ghp_" + "Z9" * 18 + " push", "git push"):
        friction_log.refus("BLOCKED: x", {"tool_name": "Bash", "tool_input": {"command": commande}}, "g.py")
    lignes = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines()]
    assert jeton not in journal.read_text(encoding="utf-8") and "ghp_" not in journal.read_text(encoding="utf-8")
    assert [l["cible"] for l in lignes] == ["autre", "autre", "git"]


def _lancer_garde(nom: str, entree: bytes, journal: Path):
    env = {**os.environ, "FRICTION_LOG": str(journal)}
    env.pop("FRICTION_LOG_OFF", None)
    return subprocess.run([sys.executable, str(RACINE / ".claude/hooks/guards" / nom)], input=entree, env=env, capture_output=True)


def test_bash_guard_refuse_en_code_2_meme_sur_une_entree_mal_formee(tmp_path):
    """Seconde relecture 2026-11-09: la trace ajoutée relisait le texte brut et faisait sortir le garde en code 1 (= laisse passer)."""
    jeton = "sk-" + "a1b2" * 8
    for brut in (f'{{"tool_input": {{"command": "echo {jeton}', f"echo {jeton}", json.dumps([jeton]), json.dumps(jeton)):
        res = _lancer_garde("bash-guard.py", brut.encode(), tmp_path / "f.jsonl")
        assert res.returncode == 2, (brut[:20], res.returncode, res.stderr[-200:])


def test_veille_check_laisse_outil_et_cible_dans_la_trace(tmp_path):
    source = (RACINE / ".claude/hooks/guards/pre-code-veille-check.py").read_text(encoding="utf-8")
    assert "remember_input" in source
