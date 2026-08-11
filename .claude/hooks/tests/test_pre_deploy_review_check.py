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


def test_deploy_with_review_passes():
    marker = "[REVIEW] par contexte-neuf le 2026-08-10 — verdict: PASS, 0 defaut"
    assert gate.verdict("docker compose up -d", [marker]) is None


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
    assert gate.verdict(command, [marker]) is None


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
