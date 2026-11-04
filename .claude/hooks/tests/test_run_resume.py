"""lib/run_resume.py + lib/run_journal.py — la reprise « sur ton ordre » d'un run autonome arrêté (Jay, 2026-10-17 / 2026-11-04).

Un run s'arrête (limite de jetons, coupure, point de contrôle). Jay dit « reprends » : le brief est CALCULÉ depuis le
contrat et le journal du run, jamais écrit de mémoire. Une brique n'est « prouvée » que si sa dernière tentative porte
une commande, sa sortie et un SHA que git connaît.

LECTURE FERMÉE par construction (trois relectures FAIL sur la lecture de Markdown libre) : le journal est un fichier de
lignes JSON strictes, l'ordre des briques vient d'une liste fermée du contrat. Une ligne illisible, un coût qui n'est pas
un nombre, un jalon sans brique ARRÊTENT la reprise ; rien n'est ignoré, rien n'est compté à zéro.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))
_spec = importlib.util.spec_from_file_location("run_resume", LIB / "run_resume.py")
rr = importlib.util.module_from_spec(_spec)
sys.modules["run_resume"] = rr
_spec.loader.exec_module(rr)
import run_journal as rj  # noqa: E402

CONTRACT = {
    "mode": "lot", "scope": ["B07", "B08", "B09"], "deploy": "jamais",
    "cdc_version": "0.6.0", "pet_version": "0.9.0",
    "budget": {"cout_max_usd": 20, "tokens_max": 5_000_000, "duree_max_h": 6, "alerte_pct": 80, "arret_pct": 100},
    "livrable": [{"id": "L1", "preuve": "parcours", "verification": "script_navigateur"}],
    "checkpoints": [{"id": "C1", "apres": "B08", "jay_verifie": "le premier écran", "bloquant": True}],
}
VERS = {"cdc_version": "0.6.0", "pet_version": "0.9.0"}


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    if not (repo / ".git").exists():
        for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"]):
            subprocess.run(["git", *args], cwd=repo, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    return repo, sha


def row(brick, sha, *, livre=True, cmd="mix test", out="5424 tests, 0 failures (exit 0)", cost=1.5, **extra):
    event = {"type": "brique", "brique": brick, "livre": livre, "commande": cmd, "sortie": out, "sha": sha, "cout_usd": cost}
    return json.dumps({**event, **extra}, ensure_ascii=False) + "\n"


def journal(rows="", raison="limite de jetons", valid=()):
    text = rows + "".join(json.dumps({"type": "point_valide", "id": c}) + "\n" for c in valid)
    return text + json.dumps({"type": "arret", "raison": raison}, ensure_ascii=False) + "\n"


def plan(tmp_path, text, contract=None, **kw):
    repo = kw.pop("repo", None) or _repo(tmp_path)[0]
    ctx = rr.Context(repo=repo, **{**VERS, **kw})
    return rr.plan_resume(contract or CONTRACT, rr.parse_journal(text), ctx)


# --- le journal est strict ------------------------------------------------------------------------------------------


def test_the_journal_events_are_read_with_their_fields():
    j = rj.parse_journal(row("b07", "abc1234") + journal(valid=["C1"]))
    assert j.rows[0]["brique"] == "B07" and j.rows[0]["cout"] == 1.5
    assert j.front["raison"] == "limite de jetons" and j.front["points_valides"] == ["C1"]


def test_an_empty_journal_is_a_first_run_not_an_error():
    assert rj.parse_journal("").rows == []


def test_every_unreadable_line_is_reported_with_its_number():
    text = row("B07", "abc1234") + "pas du json\n" + '{"type": "inconnu"}\n' + '{"type": "brique", "brique": "B08"}\n'
    assert rj.parse_journal(text).orphans == [2, 3, 4]


def test_field_types_are_strict():
    good = {"type": "brique", "brique": "B07", "livre": True, "commande": "c", "sortie": "s", "sha": "abc1234", "cout_usd": 1}
    for field, bad in (("livre", "oui"), ("brique", ""), ("commande", None), ("sha", 12), ("brique", 7)):
        assert rj.parse_journal(json.dumps({**good, field: bad}) + "\n").orphans == [1], field


def test_a_utf8_bom_at_the_start_is_tolerated_by_the_command_line(tmp_path):
    repo, sha = _repo(tmp_path)
    contract = tmp_path / "c.md"
    contract.write_text("---\n" + __import__("yaml").safe_dump(CONTRACT, allow_unicode=True) + "---\nbody\n", encoding="utf-8")
    run = tmp_path / "run.jsonl"
    run.write_bytes(b"\xef\xbb\xbf" + (row("B07", sha) + journal()).encode("utf-8"))
    out = subprocess.run([sys.executable, str(LIB / "run_resume.py"), str(contract), str(run), "--repo", str(repo),
                          "--cdc-version", "0.6.0", "--pet-version", "0.9.0"], capture_output=True, text=True)
    assert out.returncode == 0 and "B08" in out.stdout


# --- ce qui est prouvé ---------------------------------------------------------------------------------------------


def test_a_brick_with_command_output_and_a_real_sha_is_proven(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("B07", sha)), repo=repo)
    assert p.proven == ["B07"] and p.next_brick == "B08" and p.status == "reprendre"


def test_a_sha_that_git_does_not_know_is_not_a_proof(tmp_path):
    p = plan(tmp_path, journal(row("B07", "deadbeef")))
    assert p.proven == [] and p.redo == ["B07"] and p.next_brick == "B07"


def test_a_row_without_command_or_output_or_delivery_is_not_a_proof(tmp_path):
    repo, sha = _repo(tmp_path)
    for rows in (row("B07", sha, cmd=""), row("B07", sha, out=""), row("B07", sha, livre=False)):
        p = plan(tmp_path, journal(rows), repo=repo)
        assert p.proven == [] and p.redo == ["B07"], rows


def test_a_dash_is_not_a_command_or_an_output(tmp_path):
    repo, sha = _repo(tmp_path)
    for cmd, out in (("-", "5424 tests"), ("mix test", "-"), (" ", "ok"), ("mix test", "…")):
        assert plan(tmp_path, journal(row("B07", sha, cmd=cmd, out=out)), repo=repo).proven == [], (cmd, out)


def test_the_last_row_of_a_brick_wins(tmp_path):
    repo, sha = _repo(tmp_path)
    assert plan(tmp_path, journal(row("B07", sha) + row("B07", "deadbeef")), repo=repo).proven == []


def test_brick_ids_are_compared_without_case(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("b07", sha)), repo=repo)
    assert p.proven == ["B07"] and p.next_brick == "B08"


def test_only_a_real_hexadecimal_sha_is_a_proof_not_a_git_revision_name(tmp_path):
    repo, sha = _repo(tmp_path)
    for fake in ("HEAD", "main", "--all", "abc", sha[:5]):
        assert plan(tmp_path, journal(row("B07", fake)), repo=repo).proven == [], fake


def test_a_first_run_starts_at_the_first_brick(tmp_path):
    p = plan(tmp_path, "")
    assert p.status == "reprendre" and p.next_brick == "B07" and p.proven == []


def test_everything_proven_means_nothing_to_resume(tmp_path):
    repo, sha = _repo(tmp_path)
    rows = "".join(row(b, sha) for b in ("B07", "B08", "B09"))
    p = plan(tmp_path, journal(rows, valid=["C1"]), repo=repo)
    assert p.status == "terminé" and p.next_brick is None


# --- ce qui arrête la reprise --------------------------------------------------------------------------------------


def test_a_blocking_checkpoint_waits_for_jay_until_he_validates_it(tmp_path):
    repo, sha = _repo(tmp_path)
    rows = row("B07", sha) + row("B08", sha)
    waiting = plan(tmp_path, journal(rows), repo=repo)
    assert waiting.status == "attendre" and waiting.checkpoints[0]["id"] == "C1"
    ok = plan(tmp_path, journal(rows, valid=["C1"]), repo=repo)
    assert ok.status == "reprendre" and ok.next_brick == "B09"


def test_a_non_blocking_checkpoint_does_not_stop_the_resume(tmp_path):
    repo, sha = _repo(tmp_path)
    contract = copy.deepcopy(CONTRACT)
    contract["checkpoints"][0]["bloquant"] = False
    p = plan(tmp_path, journal(row("B07", sha) + row("B08", sha)), contract=contract, repo=repo)
    assert p.status == "reprendre" and p.digest and p.digest[0]["id"] == "C1"


def test_a_milestone_checkpoint_waits_for_jay_even_when_every_brick_is_proven(tmp_path):
    repo, sha = _repo(tmp_path)
    contract = copy.deepcopy(CONTRACT)
    contract["checkpoints"] = [{"id": "C9", "apres": "fin du lot", "jay_verifie": "le tout", "bloquant": True}]
    rows = "".join(row(b, sha) for b in ("B07", "B08", "B09"))
    assert plan(tmp_path, journal(rows), contract=contract, repo=repo).status == "attendre"
    assert plan(tmp_path, journal(rows, valid=["C9"]), contract=contract, repo=repo).status == "terminé"


def test_an_exhausted_budget_refuses_the_resume(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("B07", sha, cost=12) + row("B08", sha, cost=9)), repo=repo)
    assert p.status == "refuser" and any("budget" in r for r in p.reasons)


def test_the_alert_threshold_is_a_warning_not_a_refusal(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("B07", sha, cost=17)), repo=repo)
    assert p.status == "reprendre" and any("alerte" in w for w in p.warnings)


def test_a_changed_version_voids_the_contract(tmp_path):
    p = plan(tmp_path, "", cdc_version="0.7.0")
    assert p.status == "refuser" and any("contract_void" in r for r in p.reasons)


def test_a_malformed_contract_is_a_clean_refusal(tmp_path):
    repo, _ = _repo(tmp_path)
    for bad in ({**CONTRACT, "checkpoints": ["C1"]}, {**CONTRACT, "checkpoints": {"id": "C1"}},
                {**CONTRACT, "budget": {**CONTRACT["budget"], "arret_pct": "100"}}, {**CONTRACT, "budget": None}):
        p = plan(tmp_path, "", contract=bad, repo=repo)
        assert p.status == "refuser" and p.next_brick is None


# --- une dépense inconnue arrête : jamais comptée à zéro -------------------------------------------------------------


def test_an_unknown_cost_stops_the_resume_until_jay_writes_it(tmp_path):
    repo, sha = _repo(tmp_path)
    for bad in (None, "12", "$15", "15 USD", -3, float("nan"), float("inf"), True, [1]):
        p = plan(tmp_path, journal(row("B07", sha, cost=bad)), repo=repo)
        assert p.status == "attendre" and any("coût" in r or "illisible" in r for r in p.reasons), bad
        assert p.next_brick is None


def test_a_cost_of_zero_is_a_number_and_is_accepted(tmp_path):
    repo, sha = _repo(tmp_path)
    assert plan(tmp_path, journal(row("B07", sha, cost=0)), repo=repo).status == "reprendre"


def test_costs_of_every_attempt_are_added(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("B07", sha, livre=False, cost=25) + row("B07", sha, cost=1)), repo=repo)
    assert p.spent == 26.0 and p.status == "refuser" and p.proven == ["B07"]


# --- lecture fermée : tout ce qui est illisible ARRÊTE (test de famille) ------------------------------------------------


def test_every_unreadable_journal_line_stops_the_resume(tmp_path):
    repo, sha = _repo(tmp_path)
    good = row("B07", sha, cost=1)
    variants = {
        "ligne JSON invalide": good + "{pas du json\n",
        "ligne de tableau markdown": good + f"| B07 | non | pytest | 2 failed | {sha} | 12 | revert |\n",
        "ligne sans pipe initial": good + f"B07 | non | pytest | 2 failed | {sha} | 12 | revert\n",
        "type inconnu": good + '{"type": "annule", "brique": "B07"}\n',
        "champ manquant": good + '{"type": "brique", "brique": "B07", "livre": false}\n',
        "valeur d'un autre type": good + row("B08", sha).replace('"livre": true', '"livre": "oui"'),
        "tableau JSON au lieu d'un objet": good + "[1, 2]\n",
    }
    for name, text in variants.items():
        p = plan(tmp_path, journal(text), repo=repo)
        assert p.status in ("attendre", "refuser") and p.next_brick is None, (name, p.status)
        assert any("ligne" in r for r in p.reasons), name


# --- la liste des briques est fermée -------------------------------------------------------------------------------------


def test_project_mode_takes_its_closed_list_from_the_contract(tmp_path):
    repo, sha = _repo(tmp_path)
    contract = {**copy.deepcopy(CONTRACT), "mode": "projet", "scope": "all", "briques": ["B-001", "B-002", "B-003"]}
    contract["checkpoints"] = [{"id": "C1", "apres": "B-002", "jay_verifie": "x", "bloquant": True}]
    p = plan(tmp_path, journal(row("B-001", sha)), contract=contract, repo=repo)
    assert p.next_brick == "B-002" and p.status == "reprendre"
    done = "".join(row(b, sha) for b in ("B-001", "B-002", "B-003"))
    assert plan(tmp_path, journal(done), contract=contract, repo=repo).status == "attendre"
    assert plan(tmp_path, journal(done, valid=["C1"]), contract=contract, repo=repo).status == "terminé"


def test_project_mode_without_a_closed_list_is_refused_by_the_contract(tmp_path):
    for bad in ({}, {"briques": []}, {"briques": ["B1", "B1"]}, {"briques": ["", "B2"]}, {"briques": "B1"}):
        contract = {**copy.deepcopy(CONTRACT), "mode": "projet", "scope": "all", **bad}
        codes = [v.code for v in rr.cl.lint(contract) if v.severity == "error"]
        assert "briques_invalid" in codes, bad


def test_a_proven_brick_outside_the_contract_scope_is_flagged(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("B42", sha)), repo=repo)
    assert any("B42" in w and "périmètre" in w for w in p.warnings)


def test_one_sha_shared_by_several_proven_bricks_is_flagged(tmp_path):
    repo, sha = _repo(tmp_path)
    p = plan(tmp_path, journal(row("B07", sha) + row("B08", sha)), repo=repo)
    assert any("même SHA" in w for w in p.warnings)


# --- l'écrivain du journal : un outil, pas de la prose ------------------------------------------------------------------


def test_the_writer_appends_valid_lines_and_refuses_invalid_ones(tmp_path):
    path = tmp_path / "run.jsonl"
    rj.append_event(path, {"type": "brique", "brique": "B07", "livre": True, "commande": "mix test",
                           "sortie": "ok", "sha": "abc1234", "cout_usd": 1.0})
    rj.append_event(path, {"type": "arret", "raison": "limite de jetons"})
    assert rj.parse_journal(path.read_text(encoding="utf-8")).orphans == []
    for bad in ({"type": "brique", "brique": "B08"}, {"type": "x"}, {"type": "brique", "brique": "B08", "livre": True,
                "commande": "c", "sortie": "s", "sha": "abc1234", "cout_usd": "12"}):
        try:
            rj.append_event(path, bad)
        except rj.JournalError:
            continue
        raise AssertionError(bad)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_the_writer_command_line_round_trips(tmp_path):
    path = tmp_path / "run.jsonl"
    base = [sys.executable, str(LIB / "run_journal.py")]
    ok = subprocess.run(base + ["brique", str(path), "--brique", "B07", "--livre", "oui", "--commande", "mix test",
                                "--sortie", "5424 tests", "--sha", "abc1234", "--cout", "1.25"], capture_output=True, text=True)
    assert ok.returncode == 0
    assert subprocess.run(base + ["arret", str(path), "--raison", "coupure"], capture_output=True).returncode == 0
    assert subprocess.run(base + ["point-valide", str(path), "--id", "C1"], capture_output=True).returncode == 0
    parsed = rj.parse_journal(path.read_text(encoding="utf-8"))
    assert parsed.orphans == [] and parsed.rows[0]["cout"] == 1.25 and parsed.front["points_valides"] == ["C1"]
    bad = subprocess.run(base + ["brique", str(path), "--brique", "B08", "--livre", "oui", "--commande", "c",
                                 "--sortie", "s", "--sha", "abc1234", "--cout", "douze"], capture_output=True, text=True)
    assert bad.returncode == 2 and "Traceback" not in bad.stderr


# --- le brief et la ligne de commande -------------------------------------------------------------------------------


def test_the_brief_names_the_next_brick_the_proofs_and_the_reason(tmp_path):
    repo, sha = _repo(tmp_path)
    text = journal(row("B07", sha))
    out = rr.render_brief(plan(tmp_path, text, repo=repo), rr.parse_journal(text))
    assert "B08" in out and sha[:7] in out and "limite de jetons" in out


def _cli(tmp_path, repo, run_text, *extra):
    contract = tmp_path / "Contrat.md"
    contract.write_text("---\n" + __import__("yaml").safe_dump(CONTRACT, allow_unicode=True) + "---\nbody\n", encoding="utf-8")
    run = tmp_path / "run.jsonl"
    run.write_text(run_text, encoding="utf-8")
    cmd = [sys.executable, str(LIB / "run_resume.py"), str(contract), str(run), "--repo", str(repo), *extra]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_cli_exit_codes(tmp_path):
    repo, sha = _repo(tmp_path)
    ok = _cli(tmp_path, repo, journal(row("B07", sha)), "--cdc-version", "0.6.0", "--pet-version", "0.9.0")
    assert ok.returncode == 0 and "B08" in ok.stdout
    void = _cli(tmp_path, repo, journal(row("B07", sha)), "--cdc-version", "9", "--pet-version", "0.9.0")
    assert void.returncode == 1
    waiting = _cli(tmp_path, repo, journal(row("B07", sha, cost=None)), "--cdc-version", "0.6.0", "--pet-version", "0.9.0")
    assert waiting.returncode == 1
    gone = subprocess.run([sys.executable, str(LIB / "run_resume.py"), str(tmp_path / "absent.md"), str(tmp_path / "x")],
                          capture_output=True, text=True)
    assert gone.returncode == 2 and "Traceback" not in gone.stderr


def test_a_repo_that_is_not_a_git_repository_is_a_clean_exit_2(tmp_path):
    for repo in (tmp_path / "absent", tmp_path):
        out = _cli(tmp_path, repo, journal())
        assert out.returncode == 2 and "Traceback" not in out.stderr, repo


def test_the_writer_refuses_a_negative_or_non_finite_cost(tmp_path):
    path = tmp_path / "run.jsonl"
    base = {"type": "brique", "brique": "B07", "livre": True, "commande": "c", "sortie": "s", "sha": "abc1234"}
    for bad in (-1, float("nan"), float("inf")):
        try:
            rj.append_event(path, {**base, "cout_usd": bad})
        except rj.JournalError:
            continue
        raise AssertionError(bad)
    assert not path.exists()


def test_the_last_stop_reason_is_the_one_reported():
    text = journal(raison="première coupure") + journal(raison="limite de jetons")
    assert rj.parse_journal(text).front["raison"] == "limite de jetons"


# --- remarques de la 4e relecture (PASS) -----------------------------------------------------------------------------


def test_the_writer_and_the_reader_agree_on_unicode_line_separators(tmp_path):
    path = tmp_path / "run.jsonl"
    for sep in (" ", " ", "\x85", "\x0b", "\x0c"):
        rj.append_event(path, {"type": "brique", "brique": "B07", "livre": True, "commande": "c",
                               "sortie": f"ok{sep}suite", "sha": "abc1234", "cout_usd": 1.0})
    parsed = rj.parse_journal(path.read_text(encoding="utf-8"))
    assert parsed.orphans == [] and len(parsed.rows) == 5


def test_a_duplicate_key_in_an_event_makes_the_line_unreadable():
    line = ('{"type": "brique", "brique": "B01", "livre": false, "commande": "c", "sortie": "FAILED", "sha": "abc1234", '
            '"cout_usd": 1, "livre": true}\n')
    assert rj.parse_journal(line).orphans == [1]


def test_a_huge_integer_cost_is_unknown_not_a_crash():
    line = '{"type": "brique", "brique": "B01", "livre": true, "commande": "c", "sortie": "s", "sha": "abc1234", "cout_usd": 1' + "0" * 400 + "}\n"
    parsed = rj.parse_journal(line)
    assert parsed.rows[0]["cout"] is None


def test_scope_ids_that_differ_only_by_case_are_duplicates():
    contract = {**copy.deepcopy(CONTRACT), "scope": ["B01", "b01"]}
    assert "scope_mismatch" in [v.code for v in rr.cl.lint(contract) if v.severity == "error"]


def test_a_huge_budget_number_is_refused_not_a_crash():
    contract = copy.deepcopy(CONTRACT)
    contract["budget"]["cout_max_usd"] = int("1" + "0" * 400)
    assert "budget_invalid" in [v.code for v in rr.cl.lint(contract) if v.severity == "error"]


def test_a_contract_with_a_utf8_bom_is_read_by_the_command_line(tmp_path):
    repo, sha = _repo(tmp_path)
    contract = tmp_path / "Contrat.md"
    contract.write_bytes(b"\xef\xbb\xbf" + ("---\n" + __import__("yaml").safe_dump(CONTRACT, allow_unicode=True) + "---\nbody\n").encode("utf-8"))
    run = tmp_path / "run.jsonl"
    run.write_text(row("B07", sha) + journal(), encoding="utf-8")
    out = subprocess.run([sys.executable, str(LIB / "run_resume.py"), str(contract), str(run), "--repo", str(repo),
                          "--cdc-version", "0.6.0", "--pet-version", "0.9.0"], capture_output=True, text=True)
    assert out.returncode == 0 and "B08" in out.stdout


# --- défauts d'affichage révélés par l'essai à blanc sur le vrai plan de Dogu (ids mixtes B09b) ---------------------


def test_the_brief_shows_brick_ids_as_the_contract_writes_them(tmp_path):
    repo, sha = _repo(tmp_path)
    contract = {**copy.deepcopy(CONTRACT), "scope": ["B09b", "B14b"], "checkpoints": []}
    text = journal(row("b09B", sha))
    p = plan(tmp_path, text, contract=contract, repo=repo)
    out = rr.render_brief(p, rr.parse_journal(text))
    assert "B09b" in out and "B09B" not in out and "Prochaine brique : B14b" in out


def test_a_failed_attempt_is_not_reported_as_an_unknown_sha(tmp_path):
    repo, sha = _repo(tmp_path)
    text = journal(row("B07", sha, livre=False))
    out = rr.render_brief(plan(tmp_path, text, repo=repo), rr.parse_journal(text))
    assert "non livrée" in out and "SHA inconnu" not in out
    text = journal(row("B07", "deadbeef"))
    out = rr.render_brief(plan(tmp_path, text, repo=repo), rr.parse_journal(text))
    assert "SHA" in out and "non livrée" not in out
