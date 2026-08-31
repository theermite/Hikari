"""Tests for guards/pre-deploy-review-check.py — independent review before deploy.

Jay 2026-08-10: "j'aimerais que l'on integre un systeme qui force une relecture
independante des codes ou des briques qui sont faits." Decision: the gate sits at
DEPLOY time, not at every commit — reviewing each commit would cost more than it
saves, while shipping unreviewed code is what actually hurts.

Evidence that day: three independent reviews caught eight real defects across
three versions of the same fix, each one before it shipped.

The hook is loaded by file path (hyphen in name -> not importable as a module).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-deploy-review-check.py"
_spec = importlib.util.spec_from_file_location("pre_deploy_review_check", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# --- what counts as a valid review marker ------------------------------------


def test_full_marker_is_accepted():
    text = "[REVIEW] par contexte-neuf le 2026-08-10 — verdict: PASS, 0 defaut retenu"
    assert gate.find_marker(text) is not None


def test_marker_with_defects_found_is_accepted():
    text = "[REVIEW] par cross-model le 2026-08-10 — verdict: FAIL, 3 defauts corriges"
    assert gate.find_marker(text) is not None


def test_marker_missing_verdict_is_refused():
    assert gate.find_marker("[REVIEW] par contexte-neuf le 2026-08-10") is None


def test_marker_missing_reviewer_is_refused():
    assert gate.find_marker("[REVIEW] le 2026-08-10 — verdict: PASS") is None


def test_plain_claim_of_review_is_not_a_marker():
    assert gate.find_marker("j'ai fait relire le code, tout est bon") is None


# --- the skip motif is a closed list -----------------------------------------


def test_known_skip_motif_is_accepted():
    assert gate.find_skip("[REVIEW-SKIP] motif: rollback") is not None


def test_every_documented_motif_is_accepted():
    for motif in gate.SKIP_MOTIFS:
        assert gate.find_skip(f"[REVIEW-SKIP] motif: {motif}") is not None, motif


def test_invented_motif_is_refused():
    assert gate.find_skip("[REVIEW-SKIP] motif: c'est bon je suis sur de moi") is None


def test_empty_motif_is_refused():
    assert gate.find_skip("[REVIEW-SKIP] motif:") is None


# --- the gate itself ---------------------------------------------------------


def test_deploy_without_review_is_blocked():
    assert gate.verdict("docker compose up -d", ["on a bien avance"]) is not None


_BRIEF = "\n".join([
    "[REVIEW-BRIEF]",
    "- objectif: aider une personne a suivre son energie sans se sentir jugee",
    "- perimetre: le diff de la brique, 3 fichiers",
    "- zones suspectes: la bascule de theme et la persistance du choix",
    "- consigne: refuter",
])


def test_deploy_with_review_passes():
    """A PASS also needs its launch traced (contract widened 2026-08-30)."""
    marker = "[REVIEW] par contexte-neuf le 2026-08-10 — verdict: PASS, 0 defaut"
    assert gate.verdict("docker compose up -d", [marker, _BRIEF]) is None


def test_deploy_with_a_review_but_no_launch_brief_is_refused():
    """The counterpart of the test above: the same PASS, without the brief."""
    marker = "[REVIEW] par contexte-neuf le 2026-08-10 — verdict: PASS, 0 defaut"
    assert gate.verdict("docker compose up -d", [marker]) is not None


def test_deploy_with_valid_skip_passes():
    assert gate.verdict("./deploy.sh", ["[REVIEW-SKIP] motif: rollback"]) is None


def test_deploy_with_invented_skip_is_blocked():
    assert gate.verdict("./deploy.sh", ["[REVIEW-SKIP] motif: pas le temps"]) is not None


def test_a_command_that_is_not_a_deploy_passes():
    assert gate.verdict("git status", []) is None


def test_methodology_propagation_counts_as_a_deploy():
    """Sending to 30 repos is a deploy — that is where a defect multiplies."""
    command = "python scripts/propagate-methodology.py --all"
    assert gate.verdict(command, ["on y va"]) is not None


def test_methodology_propagation_with_review_passes():
    marker = "[REVIEW] par cross-model le 2026-08-10 — verdict: PASS, 2 defauts corriges"
    command = "python scripts/propagate-methodology.py --all"
    assert gate.verdict(command, [marker, _BRIEF]) is None


def test_sync_repo_propagation_counts_as_a_deploy():
    assert gate.verdict("bash scripts/sync-repo.sh --vps", []) is not None


# --- the block message must be usable ----------------------------------------


def test_block_message_names_the_marker_to_emit():
    message = gate.verdict("docker compose up -d", [])
    assert "[REVIEW]" in message
    assert "REVIEW-SKIP" in message


# --- independent review, 2026-08-10: the form was checked, the substance was not


def test_a_failed_review_blocks_the_deploy():
    """A marker proved a review happened, never that it went well."""
    marker = "[REVIEW] par cross-model le 2026-08-10 — verdict: FAIL, 5 defauts bloquants"
    assert gate.verdict("docker compose up -d", [marker]) is not None


def test_a_failed_review_followed_by_a_passing_one_unblocks():
    texts = [
        "[REVIEW] par cross-model le 2026-08-10 — verdict: PASS, defauts corriges",
        "[REVIEW] par cross-model le 2026-08-10 — verdict: FAIL, 5 defauts",
        _BRIEF,
    ]  # most recent first, as the transcript reader yields them
    assert gate.verdict("docker compose up -d", texts) is None


def test_an_ordinary_push_is_free():
    """A push on a branch is reversible, and gating it every time exhausts Jay.

    Decision 2026-08-11: the gate protects what cannot be taken back.
    """
    assert gate.verdict("git push", []) is None


def test_a_push_to_a_branch_is_free():
    assert gate.verdict("git push -u origin feature/x", []) is None


def test_force_push_is_a_shipping_action():
    assert gate.verdict("git push --force origin main", []) is not None


def test_a_forced_push_on_another_repo_is_caught():
    """`git -C <path> push --force` is how another repo gets pushed from here."""
    assert gate.verdict("git -C ~/Shinzo push --force", []) is not None


def test_a_forced_push_with_lease_is_caught():
    assert gate.verdict("git -C ~/Shinzo push --force-with-lease", []) is not None


def test_a_short_flag_forced_push_is_caught():
    assert gate.verdict("git -C ~/Shinzo push -f origin main", []) is not None


def test_the_word_dash_f_inside_a_message_is_not_a_forced_push():
    assert gate.verdict("git push origin main -m 'parle de -f ici'", []) is None


def test_an_uppercase_program_name_is_still_git():
    """Windows resolves `GIT` to git.exe, so the program name is case-blind."""
    assert gate.verdict("GIT push --force origin main", []) is not None


def test_an_uppercase_subcommand_is_not_a_command_at_all():
    """`git PUSH` pushes nothing — git rejects it: 'PUSH' is not a git command.

    A review flagged this as a bypass on 2026-08-11. Verified against real git:
    the subcommand is case-sensitive, so there is nothing to catch.
    """
    assert gate.verdict("git PUSH --FORCE", []) is None


def test_publishing_a_package_is_a_shipping_action():
    assert gate.verdict("npm publish", []) is not None


def test_building_is_not_shipping():
    assert gate.verdict("pnpm build", []) is None


def test_a_deploy_verb_quoted_inside_a_heredoc_is_not_a_deploy():
    """A script that merely MENTIONS a deploy must not trip the gate.

    Found live on 2026-08-10: the gate blocked its own diagnostic probe.
    """
    command = "python - <<'PY'\nprint('docker compose up -d')\nPY"
    assert gate.verdict(command, []) is None


def test_a_real_remote_deploy_in_quotes_still_counts():
    assert gate.verdict('ssh vps "systemctl restart app"', []) is not None


def test_quoting_the_marker_format_is_not_evidence():
    """Explaining the format to Jay must not unlock a deploy."""
    text = "Le format attendu est `[REVIEW] par X le 2026-01-01 — verdict: PASS, ok`."
    assert gate.verdict("docker compose up -d", [text]) is not None


def test_marker_shown_in_a_fenced_block_is_not_evidence():
    text = "Voici le format:\n\n```\n[REVIEW] par X le 2026-01-01 — verdict: PASS, ok\n```\n"
    assert gate.verdict("docker compose up -d", [text]) is not None


# --- 2nd review (2026-08-10): dropping everything after `<<` opened a bypass --


def test_a_real_deploy_after_a_heredoc_is_still_caught():
    """Writing a script via heredoc then deploying must not slip through."""
    command = "cat > s.sh <<EOF\necho hello\nEOF\ndocker compose up -d"
    assert gate.verdict(command, []) is not None


def test_a_real_deploy_after_a_remote_heredoc_is_still_caught():
    command = 'ssh host bash <<EOF\necho hi\nEOF\nsystemctl restart nginx'
    assert gate.verdict(command, []) is not None


def test_an_arithmetic_shift_does_not_disable_the_gate():
    command = "R=$((5 << 2))\ndocker compose up -d"
    assert gate.verdict(command, []) is not None


def test_quoting_a_push_in_a_message_is_not_a_push():
    command = "echo 'rappel: ne jamais faire git push --force sur main'"
    assert gate.verdict(command, []) is None


# --- 3rd review (2026-08-10): hand-rolled parsing kept reopening holes --------
#
# Four bypasses of the same family, in four versions of the same function. Fixed
# at the root: the command is now read as shell tokens (lib/shell_parse.py), so a
# `<<` inside quotes is text, and a command inside quotes after `bash -c` is a
# command.


def test_a_fake_heredoc_in_a_quoted_string_does_not_hide_a_deploy():
    command = 'echo "note <<EOF" ; docker compose up -d'
    assert gate.verdict(command, []) is not None


def test_a_fake_heredoc_in_a_comment_does_not_hide_a_deploy():
    command = "echo hi # <<EOF\ndocker compose up -d"
    assert gate.verdict(command, []) is not None


def test_a_forced_push_wrapped_in_bash_c_is_still_caught():
    assert gate.verdict("bash -c 'git push --force'", []) is not None


def test_a_publish_wrapped_in_sh_c_is_still_a_publish():
    assert gate.verdict("sh -c 'npm publish'", []) is not None


def test_a_remote_push_over_ssh_is_still_a_push():
    assert gate.verdict("ssh vps 'git push --force origin main'", []) is not None


def test_an_unparseable_command_fails_closed():
    """An unbalanced quote must not switch the gate off."""
    assert gate.verdict("docker compose up -d \"", []) is not None


# --- 4th review (2026-08-10) --------------------------------------------------


def test_a_substitution_inside_echo_still_runs_the_command():
    """`echo $(deploy)` prints the OUTPUT — the deploy really happens."""
    assert gate.verdict("echo $(docker compose up -d)", []) is not None


def test_a_deploy_inside_a_heredoc_fed_to_bash_is_caught():
    assert gate.verdict("bash <<EOF\ndocker compose up -d\nEOF", []) is not None


def test_a_forced_push_split_by_a_line_continuation_is_caught():
    assert gate.verdict("git \\\npush --force", []) is not None


def test_printing_a_file_is_not_shipping():
    assert gate.verdict("cat notes.txt", []) is None


# --- reading a script is not running it (2026-08-11) -------------------------
#
# The gate blocked a plain `grep` over the propagation script, because the
# command merely NAMED it. Reading a file never ships anything.


def test_grepping_the_propagation_script_is_not_a_propagation():
    command = "grep -n 'rsync' scripts/propagate-methodology.py"
    assert gate.verdict(command, []) is None


def test_reading_the_propagation_script_is_not_a_propagation():
    assert gate.verdict("cat scripts/propagate-methodology.py", []) is None


def test_listing_a_deploy_script_is_not_a_deploy():
    assert gate.verdict("ls -la deploy.sh", []) is None


def test_reading_a_slice_of_the_propagation_script_is_not_a_propagation():
    command = 'sed -n "1330,1340p" scripts/propagate-methodology.py'
    assert gate.verdict(command, []) is None


def test_a_pipeline_of_readers_over_a_deploy_script_is_free():
    command = "grep -n run scripts/propagate-methodology.py | head -6"
    assert gate.verdict(command, []) is None


def test_actually_running_the_propagation_is_still_gated():
    assert gate.verdict("python scripts/propagate-methodology.py --apply", []) is not None


def test_a_reader_does_not_excuse_a_real_deploy_later_on_the_line():
    command = "cat notes.txt && docker compose up -d"
    assert gate.verdict(command, []) is not None


def test_python_reading_the_propagation_script_is_not_a_propagation():
    """`python -c` inspecting the file is reading, not running it."""
    command = "python -c \"import ast; ast.parse(open('scripts/propagate-methodology.py').read())\""
    assert gate.verdict(command, []) is None


def test_running_the_propagation_script_by_path_is_gated():
    assert gate.verdict("python scripts/propagate-methodology.py Kobo", []) is not None


def test_linting_the_propagation_script_is_not_running_it():
    assert gate.verdict("ruff check scripts/propagate-methodology.py", []) is None


def test_linting_it_through_python_module_is_not_running_it():
    command = "python -m ruff check scripts/propagate-methodology.py"
    assert gate.verdict(command, []) is None


def test_find_with_exec_is_not_a_reader():
    """`find -exec` runs whatever follows — it only reads without that flag."""
    command = "find . -name propagate-methodology.py -exec python {} --apply \\;"
    assert gate.verdict(command, []) is not None


def test_find_exec_of_a_deploy_is_caught():
    assert gate.verdict("find . -exec docker compose up -d \\;", []) is not None


def test_plain_find_is_still_a_reader():
    assert gate.verdict("find . -name scripts/propagate-methodology.py", []) is None


def test_find_exec_of_a_reader_on_a_deploy_script_is_free():
    """Reading a file named deploy.sh is not running it."""
    assert gate.verdict("find . -name deploy.sh -exec cat {} \\;", []) is None


def test_find_exec_grep_on_a_deploy_script_is_free():
    assert gate.verdict("find . -name deploy.sh -exec grep foo {} \\;", []) is None


def test_find_exec_running_a_deploy_script_is_caught():
    assert gate.verdict("find . -name deploy.sh -exec bash {} \\;", []) is not None


def test_testing_the_propagation_script_is_not_running_it():
    command = "python -m pytest tests/test_propagate.py"
    assert gate.verdict(command, []) is None


# --- what the reviewer was GIVEN, not only what it returned --------------------
#
# Jay 2026-08-30: "j'ai l'impression que lorsque l'on lance un agent pour faire
# les relectures, par moment soit il omet certaines erreurs soit il ne prend pas
# en compte l'objectif et/ou la vision du projet, ce qui lui donne un point de
# vue biaise."
#
# Audit that day: nothing governed the LAUNCH. The gate checked that a verdict
# appeared afterwards; the prompt handed to the reviewer was improvised each
# time. A reviewer with no objective can only check that the code agrees with
# itself -- which is exactly the bias Jay felt.
#
# So a PASS is only evidence when the launch was traced:
#
#   [REVIEW-BRIEF]
#   - objectif: <what the project is FOR, one sentence, in user terms>
#   - perimetre: <the diff / files handed over>
#   - zones suspectes: <where to look first>
#   - consigne: refuter

PASS_MARKER = "[REVIEW] par contexte-neuf le 2026-08-30 — verdict: PASS, 0 defaut retenu"

FULL_BRIEF = (
    "[REVIEW-BRIEF]\n"
    "- objectif: aider une personne a suivre son energie sans se sentir jugee\n"
    "- perimetre: le diff de la brique B-004, 3 fichiers\n"
    "- zones suspectes: la bascule de theme et la persistance du choix\n"
    "- consigne: refuter\n"
)

DEPLOY = "docker compose up -d"


def test_should_find_a_complete_launch_brief():
    assert gate.find_brief(FULL_BRIEF) is not None


def test_should_refuse_a_brief_missing_the_objective():
    partial = FULL_BRIEF.replace(
        "- objectif: aider une personne a suivre son energie sans se sentir jugee\n", ""
    )
    assert gate.find_brief(partial) is None


def test_should_refuse_a_brief_whose_objective_is_empty():
    """An empty field must not borrow the next line as its answer."""
    empty = FULL_BRIEF.replace(
        "- objectif: aider une personne a suivre son energie sans se sentir jugee",
        "- objectif:",
    )
    assert gate.find_brief(empty) is None


def test_should_refuse_a_brief_that_asks_for_validation():
    """A reviewer told to check confirms; a reviewer told to refute finds."""
    soft = FULL_BRIEF.replace("- consigne: refuter", "- consigne: valider le code")
    assert gate.find_brief(soft) is None


def test_should_ignore_a_brief_quoted_as_an_example():
    quoted = "le gabarit est : ```\n" + FULL_BRIEF + "```"
    assert gate.find_brief(quoted) is None


def test_should_block_a_passing_review_with_no_launch_brief():
    blocked = gate.verdict(DEPLOY, [PASS_MARKER])
    assert blocked is not None
    assert "REVIEW-BRIEF" in blocked


def test_should_name_the_missing_fields_in_the_block_message():
    blocked = gate.verdict(DEPLOY, [PASS_MARKER])
    for field in ("objectif", "perimetre", "zones suspectes", "consigne"):
        assert field in blocked, field


def test_should_accept_a_passing_review_launched_from_a_brief():
    assert gate.verdict(DEPLOY, [PASS_MARKER, FULL_BRIEF]) is None


def test_should_accept_a_brief_and_a_verdict_in_the_same_message():
    together = FULL_BRIEF + "\n" + PASS_MARKER
    assert gate.verdict(DEPLOY, [together]) is None


def test_should_still_block_a_failing_review_even_with_a_brief():
    """A brief does not turn a FAIL into a PASS."""
    failed = "[REVIEW] par x le 2026-08-30 — verdict: FAIL, famille: bouton decoratif, 1 defaut"
    blocked = gate.verdict(DEPLOY, [failed, FULL_BRIEF])
    assert blocked is not None
    assert "FAIL" in blocked


def test_should_not_ask_for_a_brief_when_the_review_is_legitimately_skipped():
    skipped = "[REVIEW-SKIP] motif: rollback"
    assert gate.verdict(DEPLOY, [skipped]) is None


def test_should_not_ask_for_a_brief_on_a_command_that_ships_nothing():
    assert gate.verdict("pnpm build", [PASS_MARKER]) is None


# --- the brief must belong to THIS review, not to an older one -----------------
#
# Found while writing the launch gate: accepting any brief anywhere in the window
# lets a brief written for review #1 excuse an un-briefed review #2. Texts arrive
# most recent first, so a brief that came BEFORE the verdict sits AFTER it in the
# list. Anything earlier in the list happened after the verdict — it cannot have
# briefed it.


def test_should_refuse_a_brief_that_came_after_the_verdict():
    """A brief written after the fact briefed nothing."""
    texts = [_BRIEF, PASS_MARKER]  # brief is the MOST recent, verdict is older
    assert gate.verdict(DEPLOY, texts) is not None


def test_should_accept_a_brief_that_came_before_the_verdict():
    texts = [PASS_MARKER, _BRIEF]  # verdict most recent, brief older = before it
    assert gate.verdict(DEPLOY, texts) is None


def test_should_refuse_when_an_older_review_was_briefed_and_this_one_was_not():
    """Two reviews: the first briefed, the second improvised. The second is the
    one that gates this deploy, and it has no brief of its own."""
    first_pass = "[REVIEW] par x le 2026-08-29 — verdict: PASS, rien"
    second_pass = "[REVIEW] par y le 2026-08-30 — verdict: PASS, rien"
    texts = [second_pass, first_pass, _BRIEF]  # most recent first
    assert gate.verdict(DEPLOY, texts) is not None


def test_should_carry_the_brief_across_a_corrective_round():
    """review -> FAIL -> fix -> re-review -> PASS: one launch, one brief.

    Re-emitting four lines on every corrective round is friction with no added
    truth: the objective did not change between the two passes.
    """
    texts = [
        "[REVIEW] par x le 2026-08-30 — verdict: PASS, corrige",
        "[REVIEW] par x le 2026-08-30 — verdict: FAIL, famille: bouton decoratif, 1 defaut",
        _BRIEF,
    ]
    assert gate.verdict(DEPLOY, texts) is None


# --- the template the agents are told to emit must be readable by this gate ----
#
# Independent review 2026-08-30, family: a template that contradicts its own
# parser. The agent files were told to answer `VERDICT: PASS` as their first
# line, while this hook reads `[REVIEW] par <x> le <date> — verdict: PASS`. A
# reviewer obeying the instruction to the letter produced output INVISIBLE to
# both gates -- so a real FAIL never opened its [CAUSE] obligation.
#
# Same family as 2026-07-30 ("when a written rule does not bite, look for the
# TEMPLATE that contradicts it"). The test below reads the agent files on disk,
# so the two can never drift apart again in silence.

AGENTS = (
    Path(__file__).resolve().parents[2] / "agents" / "code-review-master.md",
    Path(__file__).resolve().parents[2] / "agents" / "cross-model-reviewer-master.md",
)


def _prescribed_lines(agent_file):
    """Every `[REVIEW] ...` line the agent file tells the reviewer to emit."""
    text = agent_file.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip().startswith("[REVIEW]")]


def test_should_prescribe_a_marker_in_every_review_agent():
    for agent in AGENTS:
        assert _prescribed_lines(agent), f"{agent.name} prescribes no [REVIEW] marker"


def test_should_parse_every_marker_the_review_agents_prescribe():
    """What the agent is told to write is what this gate must be able to read."""
    for agent in AGENTS:
        for line in _prescribed_lines(agent):
            concrete = (
                line.replace("<relecteur>", "cross-model-sonnet")
                .replace("<YYYY-MM-DD>", "2026-08-30")
                .replace("<slug>", "bouton-decoratif")
                .replace("<ce qui en est sorti>", "1 defaut reel")
            )
            assert gate.find_marker(concrete) is not None, f"{agent.name}: {line}"
