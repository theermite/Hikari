"""Tests for guards/pre-deploy-audit-check.py — dependency audit output before a deploy.

Security.md said « zero critical/high CVEs at deploy time » and, in the same breath,
« no guard runs this check » (measured 2026-09-05). A claim of « zero CVE » was a claim, not a
gate. The gate asks for an artefact: the audit tool really ran in this session, and its result
is quoted with the commit it covered.

The hook is loaded by file path (hyphen in name -> not importable as a module).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-deploy-audit-check.py"
_spec = importlib.util.spec_from_file_location("pre_deploy_audit_check", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

HEAD = "abc1234def5678"
DEPLOY = "docker compose up -d"
RAN = ["pnpm audit --prod"]
GOOD = "[AUDIT] outil: pnpm-audit sur abc1234 — critiques: 0, hautes: 0"


def _verdict(texts, command=DEPLOY, ran=RAN, head=HEAD, changed=lambda a, b: [], dirty=lambda: []):
    return gate.verdict(command, texts, ran=ran, head=head, changed=changed, dirty_files=dirty)


# --- the marker --------------------------------------------------------------


def test_a_complete_marker_is_read():
    audits = gate.find_audits(GOOD)
    assert len(audits) == 1 and audits[0]["tool"] == "pnpm-audit"


def test_a_marker_without_counts_is_not_a_marker():
    assert gate.find_audits("[AUDIT] outil: pnpm-audit sur abc1234") == []


def test_a_marker_for_an_unknown_tool_is_not_a_marker():
    assert gate.find_audits("[AUDIT] outil: tout-va-bien sur abc1234 — critiques: 0, hautes: 0") == []


def test_a_marker_quoted_in_code_is_not_a_marker():
    assert gate.find_audits("le format :\n```\n" + GOOD + "\n```") == []
    assert gate.find_audits("le format `" + GOOD + "`") == []


def test_a_marker_that_does_not_open_its_line_is_not_a_marker():
    """Documentation reproduces the real form faithfully: only a line that OPENS with it counts."""
    assert gate.find_audits("exemple de marqueur : " + GOOD) == []


def test_a_plain_claim_is_not_evidence():
    assert gate.find_audits("j'ai lance l'audit, zero faille") == []


# --- the gate ----------------------------------------------------------------


def test_deploy_without_audit_is_blocked():
    message = _verdict(["on a bien avance"])
    assert message is not None and "[AUDIT]" in message


def test_deploy_with_a_real_clean_audit_passes():
    assert _verdict([GOOD]) is None


def test_a_marker_without_the_tool_having_run_is_refused():
    """Nothing in the session ran the audit: the marker is a sentence, not a measure."""
    message = _verdict([GOOD], ran=["git status", "ls"])
    assert message is not None and "pnpm" in message


def test_each_tool_is_recognised_by_its_real_command():
    cases = {
        "npm-audit": "npm audit --omit=dev",
        "pnpm-audit": "pnpm audit",
        "pip-audit": "python -m pip_audit -r requirements.txt",
        "mix-deps-audit": "mix deps.audit",
        "cargo-audit": "cargo audit",
        "osv-scanner": "osv-scanner scan --lockfile=mix.lock",
    }
    for tool, command in cases.items():
        text = f"[AUDIT] outil: {tool} sur abc1234 — critiques: 0, hautes: 0"
        assert _verdict([text], ran=[command]) is None, tool


def test_findings_block_the_deploy():
    text = "[AUDIT] outil: pnpm-audit sur abc1234 — critiques: 1, hautes: 2"
    message = _verdict([text])
    assert message is not None and "1" in message


def test_findings_accepted_by_identifier_may_ship():
    text = "[AUDIT] outil: pnpm-audit sur abc1234 — critiques: 0, hautes: 1, acceptees: GHSA-xxxx-yyyy-zzzz"
    assert _verdict([text]) is None


def test_fewer_accepted_identifiers_than_findings_is_refused():
    text = "[AUDIT] outil: pnpm-audit sur abc1234 — critiques: 1, hautes: 1, acceptees: GHSA-xxxx-yyyy-zzzz"
    assert _verdict([text]) is not None


def test_the_latest_audit_wins_over_an_older_clean_one():
    newer = "[AUDIT] outil: pnpm-audit sur abc1234 — critiques: 2, hautes: 0"
    assert _verdict([newer, GOOD]) is not None


# --- what the audit covered ---------------------------------------------------


def test_an_audit_of_an_older_commit_is_refused_when_a_lockfile_changed_since():
    older = "[AUDIT] outil: pnpm-audit sur 1111111 — critiques: 0, hautes: 0"
    message = _verdict([older], changed=lambda a, b: ["docs/x.md", "pnpm-lock.yaml"])
    assert message is not None and "pnpm-lock.yaml" in message


def test_an_audit_of_an_older_commit_holds_when_no_dependency_file_changed():
    older = "[AUDIT] outil: pnpm-audit sur 1111111 — critiques: 0, hautes: 0"
    assert _verdict([older], changed=lambda a, b: ["docs/x.md", "src/app.ts"]) is None


def test_an_unreadable_comparison_is_refused_not_ignored():
    older = "[AUDIT] outil: pnpm-audit sur 1111111 — critiques: 0, hautes: 0"
    assert _verdict([older], changed=lambda a, b: None) is not None


def test_an_unknown_head_does_not_turn_ignorance_into_a_refusal():
    assert _verdict([GOOD], head=None) is None


# --- the dispense is a closed list, with a commit -----------------------------


def test_every_documented_motif_is_accepted():
    for motif in gate.SKIP_MOTIFS:
        assert _verdict([f"[AUDIT-SKIP] motif: {motif} sur abc1234"], ran=[]) is None, motif


def test_an_invented_motif_is_refused():
    assert _verdict(["[AUDIT-SKIP] motif: pas le temps sur abc1234"], ran=[]) is not None


def test_a_dispense_without_a_commit_is_refused():
    assert _verdict(["[AUDIT-SKIP] motif: rollback"], ran=[]) is not None


def test_a_dispense_for_another_commit_is_refused():
    assert _verdict(["[AUDIT-SKIP] motif: rollback sur 1111111"], ran=[]) is not None


# --- what counts as shipping --------------------------------------------------


def test_a_command_that_ships_nothing_passes():
    assert _verdict([], command="git status") is None


def test_reading_a_deploy_script_is_not_shipping():
    assert _verdict([], command="cat deploy.sh") is None
    assert _verdict([], command="echo 'docker compose up -d'") is None


def test_a_package_publication_ships():
    assert _verdict([], command="npm publish") is not None


def test_a_plain_push_is_not_gated():
    """Same line as the review gate: a branch push is reversible and gating it kills the rule."""
    assert _verdict([], command="git push origin main") is None


def test_an_unparseable_line_is_inspected_raw():
    assert _verdict([], command="docker compose up -d 'oops") is not None


# --- the registry knows the guard ----------------------------------------------


def test_the_guard_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "guards/pre-deploy-audit-check.py" in settings


# --- review 2026-10-31 (independent reviewer, PASS with remarks) -----------------


def test_naming_the_tool_in_another_command_is_not_running_it():
    for command in ("pip install pip-audit", "grep -r 'pnpm audit' docs", "pnpm audit --help", "echo pnpm audit"):
        assert _verdict([GOOD], ran=[command]) is not None, command


def test_a_runner_in_front_of_the_tool_still_counts():
    text = "[AUDIT] outil: osv-scanner sur abc1234 — critiques: 0, hautes: 0"
    assert _verdict([text], ran=["npx osv-scanner scan"]) is None


def test_uncommitted_dependency_files_are_refused():
    message = _verdict([GOOD], dirty=lambda: ["package-lock.json"])
    assert message is not None and "package-lock.json" in message


def test_nested_requirements_and_bun_locks_count_as_dependency_files():
    older = "[AUDIT] outil: pip-audit sur 1111111 — critiques: 0, hautes: 0"
    for path in ("requirements/prod.txt", "constraints.txt", "bun.lock", "apps/web/bun.lockb"):
        assert _verdict([older], ran=["pip-audit"], changed=lambda a, b, p=path: [p]) is not None, path


def test_a_marker_whose_counts_are_out_of_order_is_not_a_marker():
    assert gate.find_audits("[AUDIT] outil: pnpm-audit sur abc1234 — hautes: 3, critiques: 0, hautes: 0") == []


def test_prose_beside_an_identifier_is_not_an_acceptance():
    text = "[AUDIT] outil: pnpm-audit sur abc1234 — critiques: 0, hautes: 1, acceptees: aucune (voir GHSA-xxxx plus tard)"
    assert _verdict([text]) is not None


def test_monorepo_and_other_publications_ship():
    for command in ("pnpm -r publish", "pnpm --recursive publish", "uv publish", "poetry publish", "hatch publish"):
        assert _verdict([], command=command) is not None, command


def test_a_commit_message_or_a_log_search_naming_a_publication_ships_nothing():
    for command in ('git commit -m "feat: npm publish flow"', 'git log --grep "npm publish"',
                    'gh pr create --title "npm publish workflow"'):
        assert _verdict([], command=command) is None, command


def test_compose_with_options_before_the_verb_ships():
    for command in ("docker compose -f prod.yml up -d", "docker compose --profile prod up -d",
                    "ssh vps docker compose -f x.yml up -d"):
        assert _verdict([], command=command) is not None, command


# --- relecture finale 2026-11-01: a local `docker compose up` is not a deploy to audit ---------------------------


def test_local_dev_dispense_lets_a_local_compose_up_through():
    assert _verdict([f"[AUDIT-SKIP] motif: local-dev sur {HEAD[:7]}"], command="docker compose up -d", ran=[]) is None


def test_local_dev_dispense_is_refused_for_anything_that_leaves_the_machine():
    for command in ("ssh vps docker compose up -d", "ssh vps 'cd apps/x && docker compose up -d'", "npm publish",
                    "pnpm -r publish", "vercel --prod", "fly deploy", "kubectl apply -f x.yml", "twine upload dist/*",
                    "gh workflow run deploy.yml", "docker compose up -d && rsync -a build/ vps:/srv/x"):
        message = _verdict([f"[AUDIT-SKIP] motif: local-dev sur {HEAD[:7]}"], command=command, ran=[])
        assert message is not None and "local-dev" in message, command


def test_the_refusal_names_the_way_out():
    message = _verdict([f"[AUDIT-SKIP] motif: local-dev sur {HEAD[:7]}"], command="ssh vps docker compose up -d", ran=[])
    assert "[AUDIT]" in message


# --- 2026-11-01: a note that QUOTES a deploy is not a deploy; an audit run through a wrapper is an audit -------


def test_a_multiline_commit_message_that_quotes_a_deploy_ships_nothing():
    command = ("python - <<'EOF'\nprint('x')\nEOF\n"
               "git add docs/x.md && git commit -q -m 'docs: rapport\n\nle garde lit `docker compose up -d` comme un deploiement\n\nCo-Authored-By: A'")
    assert _verdict([], command=command) is None


def test_a_heredoc_note_that_quotes_a_deploy_ships_nothing():
    assert _verdict([], command="cat > note.md <<'EOF'\ndocker compose up -d puis npm publish\nEOF") is None


def test_a_quote_that_never_closes_is_still_read_raw_and_refused():
    assert _verdict([], command="echo 'oops docker compose up -d\nsuite") is not None


def test_an_audit_run_through_a_wrapper_or_an_option_is_recognised():
    cases = {
        "pip-audit": ["uv run pip-audit", "poetry run pip-audit -r req.txt"],
        "npm-audit": ["npm --prefix web audit --omit=dev", "npm exec -- npm audit"],
        "pnpm-audit": ["pnpm -r audit --prod", "pnpm --filter web audit"],
    }
    for tool, commands in cases.items():
        text = f"[AUDIT] outil: {tool} sur abc1234 — critiques: 0, hautes: 0"
        for command in commands:
            assert _verdict([text], ran=[command]) is None, command
