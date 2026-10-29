"""reformulate-gate.py — les deux accords qui levent CE garde-fou (Jay, 2026-10-18).

1. Un document de conception (PET, CDC, brief) montre puis un mot d'approbation.
2. Une consigne de Jay qui nomme une brique du PET du projet.

Les aides (constructeurs de journal, _run) viennent de test_reformulate_gate.
"""

from __future__ import annotations

from pathlib import Path

from test_reformulate_gate import (
    _assistant_text,
    _assistant_tool,
    _run,
    _tool_result,
    _user,
    _write_subagent_transcript,
    _write_transcript,
)

def fired(r) -> bool:
    """Le garde-fou s'est déclenché: il AVERTIT (annonce attendue) depuis le mandat du 2026-10-24."""
    return r.returncode == 0 and b"ANNONCE ATTENDUE" in r.stderr



# --- Un accord de conception vaut autorisation (Jay, 2026-10-18) -------------
# Un document de conception (docs/PET.md, docs/CDC.md, docs/Briefs/*.md) lu,
# ecrit ou cite par Takumi, PUIS un mot d'approbation exact de Jay, leve ce
# garde-fou pour la session. Veille, tests, lint, secrets continuent de tirer.


def _design_read(path: str = "/repo/docs/PET.md", tid: str = "d1", is_error: bool = False) -> list[dict]:
    return [
        _assistant_tool("Read", tid, {"file_path": path}),
        _tool_result(tid, is_error=is_error),
    ]


def _prior_write() -> list[dict]:
    return [
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w1", is_error=False),
    ]


def _new_instruction_and_prior_write() -> list[dict]:
    """A real instruction closes the reformulation window; one write is done."""
    return [
        _user("fais la brique 3 maintenant"),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w1", is_error=False),
    ]


def test_design_doc_then_approval_word_lifts_the_gate(tmp_path):
    entries = [_user("on conçoit"), *_design_read(), _assistant_text("Voici le PET."),
               _user("valide"), *_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert not fired(r), f"design agreement should pass: {r.stderr!r}"


def test_design_doc_only_cited_in_his_text_does_not_count(tmp_path):
    entries = [_user("on conçoit"), _assistant_text("Le CDC est dans docs/CDC.md, tout y est."),
               _user("go"), *_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "only an opened/written document counts, never a mention"


def test_brief_under_docs_briefs_counts(tmp_path):
    entries = [_user("on conçoit"), *_design_read("/repo/docs/Briefs/Mon-Brief.md"),
               _user("ok"), *_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert not fired(r), f"brief + ok should pass: {r.stderr!r}"


def test_design_doc_then_a_new_instruction_does_not_count(tmp_path):
    entries = [_user("on conçoit"), *_design_read(),
               _user("ajoute aussi une page de connexion"),
               *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "a new instruction is not an approval"


def test_go_without_any_design_doc_does_not_count(tmp_path):
    entries = [_user("on discute"), _assistant_text("Je propose ceci."),
               _user("go"), *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "an approval of nothing documented is not a design agreement"


def test_a_relance_nudge_is_not_an_approval(tmp_path):
    entries = [_user("on conçoit"), *_design_read(), _user("reprends"),
               *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "'reprends' keeps the window open but never approves a design"


def test_approval_before_the_doc_is_cited_does_not_count(tmp_path):
    entries = [_user("ok"), *_design_read(), *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "the approval must come AFTER the document is shown"


def test_failed_read_of_the_doc_does_not_count(tmp_path):
    entries = [_user("on conçoit"), *_design_read(is_error=True), _user("go"),
               *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "a Read that failed shows nothing to approve"


def test_doc_path_only_inside_written_code_does_not_count(tmp_path):
    # The word is present, the fact is not: it sits in a comment inside file
    # content, never as a file path he opened or a sentence he said.
    entries = [_user("on conçoit"),
               _assistant_tool("Write", "w0", {"file_path": "/repo/src/x.py",
                                               "content": "# voir docs/PET.md"}),
               _tool_result("w0"), _user("go"), *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "a path inside file content is not a document shown to Jay"


def test_a_file_named_pet_outside_docs_does_not_count(tmp_path):
    entries = [_user("on conçoit"), *_design_read("/repo/notes/PET.md"), _user("go"),
               *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "only docs/PET.md, docs/CDC.md and docs/Briefs/*.md are design documents"


# --- Une consigne qui nomme une brique du PET vaut accord (Jay, 2026-10-18) --
# La derniere consigne de Jay (les "go" de relance ne la remplacent pas) leve CE
# garde-fou si elle nomme une brique presente dans le docs/PET.md du projet
# ecrit, et n'est pas une question. Jamais pour un sous-agent.


def _project_with_pet(tmp_path: Path, pet_text: str = "| B8 | Page connexion |\n| B-PREP | Prepa |\n") -> str:
    docs = tmp_path / "proj" / "docs"
    docs.mkdir(parents=True)
    (docs / "PET.md").write_text(pet_text, encoding="utf-8")
    src = tmp_path / "proj" / "src"
    src.mkdir()
    return str(src / "foo.py")


def _instruction_then_write(text: str) -> list[dict]:
    return [
        _user(text),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w1", is_error=False),
    ]


def test_instruction_naming_a_pet_brick_lifts_the_gate(tmp_path):
    target = _project_with_pet(tmp_path)
    entries = _instruction_then_write("go, lance-toi sur la brique 8")
    r = _run(_write_transcript(tmp_path / "t", *entries), file_path=target)
    assert not fired(r), f"named PET brick should pass: {r.stderr!r}"


def test_bare_b_form_and_lettered_id_count(tmp_path):
    target = _project_with_pet(tmp_path)
    for text in ("fais la B8", "go sur B-PREP", "attaque la brique 8."):
        entries = _instruction_then_write(text)
        r = _run(_write_transcript(tmp_path / "t", *entries), file_path=target)
        assert not fired(r), f"{text!r} should pass: {r.stderr!r}"


def test_brick_absent_from_the_pet_does_not_count(tmp_path):
    target = _project_with_pet(tmp_path)
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write("fais la brique 12")), file_path=target)
    assert fired(r), "a brick the PET does not list is not a PET brick"


def test_a_question_naming_a_brick_does_not_count(tmp_path):
    target = _project_with_pet(tmp_path)
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write("pourquoi la brique 8 échoue ?")), file_path=target)
    assert fired(r), "a question authorizes nothing"


def test_instruction_without_a_brick_does_not_count(tmp_path):
    target = _project_with_pet(tmp_path)
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write("ajoute une page de connexion")), file_path=target)
    assert fired(r)


def test_no_pet_found_does_not_count(tmp_path):
    (tmp_path / "bare").mkdir()
    target = str(tmp_path / "bare" / "foo.py")
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write("go, lance-toi sur la brique 8")), file_path=target)
    assert fired(r), "no docs/PET.md above the target -> nothing to name"


def test_old_instruction_naming_a_brick_is_replaced_by_the_new_one(tmp_path):
    target = _project_with_pet(tmp_path)
    entries = [_user("go, lance-toi sur la brique 8"), _user("ajoute une page de connexion"),
               *_instruction_then_write("ajoute une page de connexion")[1:]]
    r = _run(_write_transcript(tmp_path / "t", *entries), file_path=target)
    assert fired(r), "the LAST instruction decides"


def test_a_relance_nudge_keeps_the_named_brick_instruction(tmp_path):
    target = _project_with_pet(tmp_path)
    entries = [*_instruction_then_write("lance-toi sur la brique 8"), _user("go")]
    r = _run(_write_transcript(tmp_path / "t", *entries), file_path=target)
    assert not fired(r), f"'go' must not replace the instruction: {r.stderr!r}"


def test_a_subagent_never_inherits_the_brick_instruction(tmp_path):
    target = _project_with_pet(tmp_path)
    parent = _write_transcript(tmp_path / "t", _user("go, lance-toi sur la brique 8"))
    _write_subagent_transcript(parent, "ag1", *_instruction_then_write("Implémente la brique 8"))
    r = _run(parent, file_path=target, agent_id="ag1")
    assert fired(r), "a sub-agent brief is written by Takumi, never by Jay"


def test_harness_injected_message_is_not_jays_instruction(tmp_path):
    # Measured on a real journal: "<task-notification> ... b3wf2e265" read as a brick.
    target = _project_with_pet(tmp_path, "| B3 | x |\n")
    text = "<task-notification><task-id>b3</task-id> brique 3 terminee</task-notification>"
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write(text)), file_path=target)
    assert fired(r), "only Jay's own words authorize"


def test_a_random_identifier_is_not_a_brick(tmp_path):
    # The PET carries the same junk id, so only a strict id shape can refuse it.
    target = _project_with_pet(tmp_path, "| B3 | x |\nref b3wf2e265\n")
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write("regarde la tache b3wf2e265")), file_path=target)
    assert fired(r), "'b3wf2e265' is a task id, not B3"


# --- relecture independante 2026-10-18 ---------------------------------------


def test_a_mere_mention_of_the_pet_in_his_text_is_not_a_shown_document(tmp_path):
    entries = [_user("on démarre"), _assistant_text("Je ne touche pas docs/PET.md."),
               _user("ok"), *_new_instruction_and_prior_write()]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r)


def test_design_agreement_ends_at_the_next_real_instruction(tmp_path):
    entries = [_user("on conçoit"), *_design_read(), _user("valide"),
               _user("refais entièrement le module de paiement"),
               *_new_instruction_and_prior_write()[1:]]
    r = _run(_write_transcript(tmp_path, *entries))
    assert fired(r), "an approval covers the instruction that follows it, not the whole session"


def test_design_agreement_is_never_inherited_by_a_subagent(tmp_path):
    # the sub-agent journal ends on "ok" + a write, with NO newer instruction: only the
    # agent_id guard can refuse (a journal ending on an instruction would refuse by itself)
    parent = _write_transcript(tmp_path / "t", _user("on conçoit"))
    _write_subagent_transcript(parent, "ag1", _user("brief"), *_design_read(), _user("ok"), *_prior_write())
    r = _run(parent, agent_id="ag1")
    assert fired(r)


def test_lowercase_named_brick_matches(tmp_path):
    target = _project_with_pet(tmp_path, "| B-CHAT | x |\n")
    r = _run(_write_transcript(tmp_path / "t", *_instruction_then_write("fais la b-chat")), file_path=target)
    assert not fired(r)


# --- Une copie du journal n'est pas Jay (audit 2026-10-29) -------------------
# Le journal recopie chaque message dans une entrée `api-request-blob`. Cette
# copie n'est pas une parole : elle ne doit jamais valoir accord.


def _copy_of(entry: dict) -> dict:
    return {"type": "api-request-blob", "message": entry}


def test_a_journal_copy_naming_a_brick_is_not_the_agreement(tmp_path):
    target = _project_with_pet(tmp_path)
    entries = [*_instruction_then_write("fais autre chose"),
               _copy_of(_user("go, lance-toi sur la brique 8"))]
    r = _run(_write_transcript(tmp_path / "t", *entries), file_path=target)
    assert fired(r), f"a copy must not name the brick: {r.stderr!r}"


def test_a_journal_copy_of_an_approval_word_is_not_an_approval(tmp_path):
    entries = [_user("on conçoit"), *_design_read(), _assistant_text("Voici le PET."),
               _copy_of(_user("valide")), *_prior_write()]
    r = _run(_write_transcript(tmp_path / "t", *entries))
    assert fired(r), f"a copied approval word must not lift the gate: {r.stderr!r}"
