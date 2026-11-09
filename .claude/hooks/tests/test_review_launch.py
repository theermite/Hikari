"""What a reviewer was given is read from the tool call: the journal can lose a message's text,
never a call's input. Dogu, 2026-11-08: five real passes, deployment refused all the same, because
the brief sat in lost text, or in a resumed reviewer's SendMessage."""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from review_launch import brief_from_blocks  # noqa: E402

BRIEF = """Consigne : refuter ce travail.
Objectif : reprendre une conversation sans perdre le fil
Périmètre : le commit ac89c6a
Zones suspectes : la reprise
"""


def _guard():
    path = os.path.join(os.path.dirname(__file__), "..", "guards", "pre-deploy-review-check.py")
    spec = importlib.util.spec_from_file_location("review_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(name, **fields):
    return [{"type": "tool_use", "name": name, "input": fields}]


def test_should_read_the_brief_when_a_reviewer_is_launched():
    blocks = _call("Agent", subagent_type="Cross Model Reviewer Master", prompt=BRIEF)
    assert "- objectif: reprendre" in brief_from_blocks(blocks)


def test_should_ignore_a_launch_that_is_not_a_review():
    assert brief_from_blocks(_call("Agent", subagent_type="Explore", prompt=BRIEF)) == ""


def test_should_read_the_brief_when_a_reviewer_is_resumed():
    assert "- zones suspectes: la reprise" in brief_from_blocks(_call("SendMessage", to="a1", message=BRIEF))


def test_should_not_take_a_plain_message_for_a_brief():
    assert brief_from_blocks(_call("SendMessage", to="a1", message="Peux-tu regarder ce fichier ?")) == ""


def test_should_not_take_a_message_that_does_not_ask_to_refute():
    sans_refus = BRIEF.replace("refuter", "valider")
    assert brief_from_blocks(_call("SendMessage", to="a1", message=sans_refus)) == ""


def test_should_tell_where_a_brief_is_never_lost_when_it_is_missing():
    message = _guard()._missing_brief_message()
    assert "reviewer's own prompt" in message
    assert "SendMessage" in message
