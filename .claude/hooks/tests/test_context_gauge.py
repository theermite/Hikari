"""La taille du contexte se LIT, elle ne s'estime plus.

Demande de Jay, 2026-09-06 : « la methodologie a une mauvaise lecture du
contexte, alors que je sais que c'est possible d'avoir une conscience reelle du
contexte en temps reel ».

CE QUI EXISTAIT : « alerte a ~40 echanges ou ~15 lectures de fichiers (~60 %) ·
arret a ~60 echanges ». Trois defauts mesures le meme jour :

1. Ce sont des RACCOURCIS. Un echange peut couter 200 jetons ou 40 000 ; une
   lecture, 3 lignes ou 3 000. Le compte d'echanges ne mesure rien.
2. Ils sont calibres sur une fenetre de 200 000 jetons. La session travaille sur
   1 000 000 — les seuils sont donc faux d'un facteur 5.
3. Mesure prise pendant cette session : ~479 000 jetons reellement occupes, soit
   moins de la moitie de la fenetre, alors que la regle aurait ordonne l'arret
   depuis longtemps. Un garde-fou qui se declenche a tort finit debranche.

CE QUI LE REMPLACE : le transcript porte, a chaque tour, la taille reelle
occupee. On lit un nombre au lieu d'en deviner un.

Le hook est charge par chemin (le tiret dans le nom empeche l'import direct).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "context-gauge.py"
_spec = importlib.util.spec_from_file_location("context_gauge", HOOK)
jauge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jauge)


def _transcript(tmp_path: Path, usages) -> Path:
    p = tmp_path / "t.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for u in usages:
            f.write(json.dumps({"type": "assistant", "message": {"usage": u}}) + "\n")
    return p


# --- lire la taille reelle ---------------------------------------------------


def test_the_size_is_the_sum_of_what_the_model_actually_read(tmp_path):
    # Le cache lu compte : il occupe la fenetre, meme s'il coute moins cher.
    t = _transcript(tmp_path, [{
        "input_tokens": 2,
        "cache_creation_input_tokens": 1866,
        "cache_read_input_tokens": 476795,
    }])
    assert jauge.context_size(t) == 478_663


def test_the_latest_measure_wins(tmp_path):
    t = _transcript(tmp_path, [
        {"input_tokens": 1000},
        {"input_tokens": 5000},
    ])
    assert jauge.context_size(t) == 5000


def test_a_transcript_without_usage_says_it_does_not_know(tmp_path):
    p = tmp_path / "vide.jsonl"
    p.write_text("", encoding="utf-8")
    assert jauge.context_size(p) is None


def test_a_missing_transcript_says_it_does_not_know(tmp_path):
    # Ne pas savoir n'est pas zero : un faux zero se lit comme « tout va bien ».
    assert jauge.context_size(tmp_path / "absent.jsonl") is None


# --- les paliers, calibres sur la vraie fenetre -----------------------------


def test_a_quiet_session_says_nothing():
    assert jauge.level(200_000) == "ok"
    assert jauge.level(599_999) == "ok"


def test_the_degradation_zone_raises_an_alert():
    # Jay : « il y a une degradation possible a partir de 600 a 700 000 jetons ».
    assert jauge.level(600_000) == "alerte"
    assert jauge.level(699_999) == "alerte"


def test_beyond_the_zone_a_warm_resume_is_recommended():
    assert jauge.level(700_000) == "reprise"
    assert jauge.level(950_000) == "reprise"


def test_an_unknown_size_never_invents_a_level():
    assert jauge.level(None) == "inconnu"


# --- la jauge parle une fois par palier, jamais en boucle -------------------


def test_it_speaks_when_a_threshold_is_crossed():
    assert jauge.should_speak("alerte", "ok") is True
    assert jauge.should_speak("reprise", "alerte") is True


def test_it_stays_quiet_on_the_same_level():
    # Repeter a chaque tour, c'est se faire ignorer.
    assert jauge.should_speak("alerte", "alerte") is False
    assert jauge.should_speak("ok", "ok") is False


def test_it_stays_quiet_when_the_pressure_drops():
    # Apres une reprise a chaud, la jauge redescend : ce n'est pas un evenement.
    assert jauge.should_speak("ok", "reprise") is False


def test_it_never_speaks_on_an_unknown_size():
    assert jauge.should_speak("inconnu", "ok") is False


# --- ce que la jauge dit ----------------------------------------------------


def test_the_alert_names_the_real_number():
    texte = jauge.message(612_345, "alerte")
    assert "612" in texte.replace(" ", "").replace(" ", "")


def test_the_resume_message_names_the_way_out():
    texte = jauge.message(720_000, "reprise")
    assert "clear" in texte.lower()
    assert "suspens" in texte.lower()
