"""quality/clear-recap-check.py — Stop hook : ce que Takumi dit à Jay se comprend sans avoir vu le code.

Reproche de Jay (2026-11-01) : « les récapitulatifs et les rapports sont encore bien trop techniques, ça
m'embrouille. Quand il a des questions à me poser, il me parle comme si j'avais le contexte de ce qu'il vient de
coder, alors que c'est noyé dans toutes les commandes. Je veux des récaps et des questions claires, avec le
contexte en langage simple, l'impact, et ce que ça apporte ou non. »

Mesure de départ (3 jours, 682 messages de plus de 40 mots) : 53 des 98 questions à Jay sont techniques,
73 messages citent un numéro de commit, 31 % contiennent 4 termes internes ou plus.
Le garde ne juge pas la justesse du texte : il exige la FORME qui oblige à écrire le contexte, et refuse le
vocabulaire que Jay n'a pas.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "clear-recap-check.py"
_spec = importlib.util.spec_from_file_location("clear_recap_check", HOOK)
crc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crc)

PLAIN_QUESTION = (
    "## 🟦 L'essentiel :\non a corrigé la page de connexion, qui refusait certains comptes.\n\n"
    "## 🟧 Pour toi :\nles personnes bloquées pourront se reconnecter dès demain.\n\n"
    "## 🟩 Gains et limites :\nça règle le blocage ; ça ne touche pas à la vitesse de la page.\n\n"
    "## 🟪 Ta question :\nVeux-tu que je prévienne les personnes concernées ?"
)


PAD = ("Voici le point du travail de la journée, avec toutes les vérifications faites étape par étape sur la partie "
       "concernée du projet. ")


def _problems(text: str) -> list[str]:
    return [p for p, _ in crc.problems(text)]


# --- une question à Jay ouvre sur son contexte ------------------------------------------------------------------


def test_a_question_without_context_is_flagged():
    assert "question" in _problems(PAD + "J'ai mis à jour le garde et tout est vert. Veux-tu que je continue avec la suite ?")


def test_a_question_with_the_three_blocks_passes():
    assert _problems(PLAIN_QUESTION + " " + "Merci de ta réponse, je continue ensuite avec le reste du travail prévu.") == []


def test_the_blocks_may_be_written_with_a_few_variants():
    text = ("## 🟦 L'essentiel :\nla page de connexion refusait certains comptes, c'est corrigé et vérifié par un essai.\n\n"
            "## 🟧 Pour toi :\nles personnes bloquées se reconnectent dès demain matin.\n\n"
            "## 🟩 Gains et limites :\nrègle le blocage, pas la vitesse de la page.\n\n"
            "Veux-tu que je prévienne les personnes concernées ?")
    assert _problems(text) == []


def test_two_blocks_out_of_three_is_not_enough():
    text = ("**L'essentiel** : la page de connexion refusait certains comptes, c'est corrigé et vérifié par un essai.\n"
            "**Pour toi** : les personnes bloquées se reconnectent dès demain matin, sans rien avoir à faire.\n\n"
            "Veux-tu que je prévienne les personnes concernées, et par quel moyen le faire dès aujourd'hui ?")
    assert "question" in _problems(text)


def test_a_short_message_without_question_is_left_alone():
    assert _problems("Fait, c'est en ligne.") == []
    assert _problems("Oui, la propagation est terminée sur 31 projets.") == []


def test_a_very_short_question_is_left_alone():
    assert _problems("Lequel des deux ?") == []


def test_a_question_quoted_from_jay_is_not_asked():
    text = ("Tu m'avais demandé « veux-tu que je commite ? » : c'est fait. Le travail est terminé, vérifié, et rangé "
            "avec ses explications dans le rapport de la séance, rien d'autre n'est en attente pour le moment.")
    assert _problems(text) == []


# --- un long compte rendu ouvre sur « en clair » ------------------------------------------------------------------


def test_a_long_report_without_a_plain_opening_is_flagged():
    text = "Voici où on en est. " + "Le travail avance sur plusieurs points, avec des vérifications à chaque étape. " * 14
    assert "rapport" in _problems(text)


def test_a_long_report_with_the_plain_blocks_passes():
    text = ("## 🟦 L'essentiel :\nle travail est terminé.\n\n## 🟧 Pour toi :\nrien pour toi aujourd'hui.\n\n"
            + "Le travail avance sur plusieurs points, avec des vérifications à chaque étape. " * 12)
    assert _problems(text) == []


# --- le vocabulaire que Jay n'a pas -------------------------------------------------------------------------------


def test_internal_vocabulary_is_flagged_from_three_distinct_terms():
    text = PAD + ("**L'essentiel** : j'ai relancé le receveur simulé avec le marqueur et la dispense, puis comparé l'empreinte.\n"
            "**Ce que ça change** : rien.\n**Ce que ça apporte** : une preuve.\n")
    found = dict(crc.problems(text))
    assert "vocabulaire" in found and "receveur" in found["vocabulaire"].lower()


def test_two_internal_terms_are_tolerated_and_code_is_ignored():
    text = ("**L'essentiel** : j'ai relancé le receveur avec le marqueur, tout va bien pour la suite du travail.\n"
            "**Ce que ça change** : rien pour toi.\n**Ce que ça apporte** : une preuve.\n"
            "```\nhook dispense empreinte mutation worktree\n```\n`yaml json regex`")
    assert "vocabulaire" not in _problems(text)


def test_a_commit_number_in_the_chat_counts_as_a_term():
    text = PAD + ("**L'essentiel** : le correctif est dans le commit 9a2885a1 avec la mutation et la dispense.\n"
            "**Ce que ça change** : rien.\n**Ce que ça apporte** : rien.\n")
    assert "vocabulaire" in _problems(text)


def test_the_message_gives_a_plain_word_for_each_term_found():
    text = PAD + ("**L'essentiel** : receveur, marqueur, dispense et empreinte dans la même phrase, c'est trop pour toi.\n"
            "**Ce que ça change** : rien.\n**Ce que ça apporte** : rien.\n")
    suggestion = dict(crc.problems(text))["vocabulaire"]
    assert "projet qui reçoit" in suggestion and "numéro de version" in suggestion


# --- le garde tel que l'application le lance -----------------------------------------------------------------------


def _run(payload: dict):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20)


def test_the_hook_blocks_once_then_lets_the_second_stop_through():
    reply = PAD + "J'ai mis à jour le garde et tout est vert. Veux-tu que je continue avec la suite du travail prévu ?"
    first = _run({"hook_event_name": "Stop", "last_assistant_message": reply})
    assert first.returncode == 2 and b"L'essentiel" in first.stderr
    assert _run({"hook_event_name": "Stop", "stop_hook_active": True, "last_assistant_message": reply}).returncode == 0


def test_the_hook_lets_a_plain_message_through():
    reply = PLAIN_QUESTION + " Le reste du travail continue ensuite comme prévu, sans rien d'autre à décider."
    assert _run({"hook_event_name": "Stop", "last_assistant_message": reply}).returncode == 0


def test_the_hook_fails_open_on_garbage():
    assert _run({"hook_event_name": "Stop", "last_assistant_message": 12}).returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True).returncode == 0


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/clear-recap-check.py" in settings


def test_a_long_number_is_not_a_commit_number_and_a_real_one_is_enough_alone():
    assert "vocabulaire" not in _problems(PAD + "Le suivi a consommé 1500000 jetons ce mois-ci, ce qui reste normal et attendu pour ce type de travail suivi.")
    assert "vocabulaire" in _problems(PAD + "Le correctif est dans le commit 9a2885a1, rien d'autre à signaler ici, tout le reste du travail est en ordre et vérifié.")


# --- le format des intitulés (Jay 2026-11-01) : titre de niveau 2, saut de ligne, texte en dessous -----------------


def test_titles_in_bold_on_the_same_line_are_flagged():
    text = ("**L'essentiel** : la page de connexion refusait certains comptes, c'est corrigé et vérifié par un essai.\n"
            "**Pour toi** : les personnes bloquées se reconnectent dès demain matin.\n"
            "**Gains et limites** : règle le blocage, pas la vitesse de la page.\n\n"
            "Veux-tu que je prévienne les personnes concernées ?")
    found = dict(crc.problems(text))
    assert "format" in found and "niveau 2" in found["format"]


def test_a_title_with_its_text_on_the_same_line_is_flagged_even_as_a_heading():
    text = ("## 🟦 L'essentiel : la page de connexion refusait certains comptes, c'est corrigé et vérifié par un essai.\n\n"
            "## 🟧 Pour toi :\nles personnes bloquées se reconnectent dès demain matin.\n\n"
            "## 🟩 Gains et limites :\nrègle le blocage, pas la vitesse de la page.\n\n"
            "Veux-tu que je prévienne les personnes concernées ?")
    assert "format" in _problems(text)


def test_the_template_given_to_takumi_uses_the_new_format():
    template = crc.TEMPLATE
    assert "## 🟦 L'essentiel :\n" in template and "## 🟪 Ta question :\n" in template


# --- la pastille devant le titre (Jay 2026-11-01) : un rôle, une couleur, toujours la même ------------------------


def test_a_title_without_its_colour_dot_is_flagged():
    text = PLAIN_QUESTION.replace("## 🟦 L'essentiel", "## L'essentiel")
    found = dict(crc.problems(text))
    assert "format" in found and "pastille" in found["format"]


def test_a_title_with_the_wrong_colour_dot_is_flagged():
    text = PLAIN_QUESTION.replace("## 🟧 Pour toi", "## 🟩 Pour toi")
    assert "format" in _problems(text)


def test_titles_with_their_dots_are_recognised_as_the_plain_blocks():
    assert _problems(PLAIN_QUESTION + " Merci, je continue ensuite avec le reste du travail prévu pour la suite.") == []


def test_the_template_tells_which_dot_goes_with_which_title():
    for dot, title in (("🟦", "L'essentiel"), ("🟧", "Pour toi"), ("🟩", "Gains et limites"),
                       ("🟪", "Ta question")):
        assert f"## {dot} {title} :" in crc.TEMPLATE


# --- relecture 7.8.0 : seul le premier titre de chaque rôle est jugé -------------------------------------------


def _conforming_body(extra: str) -> str:
    filler = "Le travail avance sur plusieurs points, avec des vérifications à chaque étape. " * 12
    return PLAIN_QUESTION + "\n\n" + filler + "\n" + extra


def test_a_later_impact_line_does_not_make_a_well_formed_reply_wrong():
    for extra in ("Impact : aucun utilisateur touché.", "- Impact sur les tests : aucun.", "L'essentiel, c'est qu'il ne reste rien."):
        assert "format" not in _problems(_conforming_body(extra)), extra


def test_the_former_titles_are_no_longer_accepted():
    """Essai de trois jours (Jay 2026-11-01) : L'essentiel, Pour toi, Gains et limites remplacent les anciens titres."""
    old = (PLAIN_QUESTION.replace("L'essentiel", "En clair").replace("Pour toi", "Ce que ça change pour toi")
           .replace("Gains et limites", "Ce que ça apporte, ou non"))
    assert "question" in _problems(old)
