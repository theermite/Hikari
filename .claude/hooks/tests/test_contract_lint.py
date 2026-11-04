"""The autonomy contract is checked by code, not by whoever reads it.

Born 2026-10-17 from Jay's rule: "if it can be code, make it code". The contract
(`docs/Contrat-Autonomie.md`) authorises a long autonomous run. A contract nobody
validates mechanically is an instruction an agent can bend, so the pre-flight
runs this linter and the run does not start on any error.

This file is also the conformance suite for the Elixir port in Dogu: the same
cases, the same expected codes (Python is the arbiter, see Dogu.md 2026-10-10).

What is proved here, one test per rule: each error fires on the mutation that
should trigger it, and the valid contract raises nothing.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "lib" / "contract_lint.py"
_spec = importlib.util.spec_from_file_location("contract_lint", TOOL)
tool = importlib.util.module_from_spec(_spec)
# Registered BEFORE exec: dataclass resolves its annotations through sys.modules.
sys.modules["contract_lint"] = tool
_spec.loader.exec_module(tool)

VALID = {
    "mode": "lot",
    "scope": ["B07", "B08"],
    "deploy": "jamais",
    "cdc_version": "0.6.0",
    "pet_version": "0.9.0",
    "budget": {"cout_max_usd": 20, "tokens_max": 5_000_000, "duree_max_h": 6,
               "alerte_pct": 80, "arret_pct": 100},
    "livrable": [
        {"id": "L1", "preuve": "parcours maquette", "verification": "script_navigateur"},
        {"id": "L2", "preuve": "tests verts", "verification": "commande", "commande": "mix test"},
    ],
    "checkpoints": [
        {"id": "C1", "apres": "B08", "jay_verifie": "premier ecran utilisable", "bloquant": True},
    ],
}
CTX = {"cdc_version": "0.6.0", "pet_version": "0.9.0", "cost_history": [2.0, 3.0, 2.5]}


def codes(data, **ctx):
    merged = {**CTX, **ctx}
    return sorted(v.code for v in tool.lint(data, **merged) if v.severity == "error")


def mutated(**changes):
    data = copy.deepcopy(VALID)
    for key, value in changes.items():
        if value is tool.DELETE:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def test_a_valid_contract_raises_nothing():
    assert codes(VALID) == []


def test_unknown_mode_is_refused():
    assert codes(mutated(mode="tout")) == ["mode_invalid"]


def test_brique_needs_exactly_one_brick():
    assert codes(mutated(mode="brique", scope=["B07", "B08"])) == ["scope_mismatch"]
    assert codes(mutated(mode="brique", scope=["B07"])) == []


def test_lot_needs_at_least_two_named_bricks():
    assert codes(mutated(mode="lot", scope=["B07"])) == ["scope_mismatch"]


def test_projet_scope_must_be_all():
    assert codes(mutated(mode="projet", scope=["B07"], briques=["B07"])) == ["scope_mismatch"]
    assert codes(mutated(mode="projet", scope="all", briques=["B07", "B08"])) == []


def test_missing_budget_is_refused():
    assert "budget_missing" in codes(mutated(budget=tool.DELETE))


def test_budget_ceilings_must_be_positive():
    budget = {**VALID["budget"], "cout_max_usd": 0}
    assert codes(mutated(budget=budget)) == ["budget_invalid"]


def test_alert_must_come_before_stop_and_stop_cannot_exceed_100():
    assert codes(mutated(budget={**VALID["budget"], "alerte_pct": 100, "arret_pct": 100})) == ["budget_invalid"]
    assert codes(mutated(budget={**VALID["budget"], "arret_pct": 120})) == ["budget_invalid"]


def test_projet_without_a_blocking_checkpoint_is_refused():
    soft = [{"id": "C1", "apres": "B08", "jay_verifie": "x", "bloquant": False}]
    assert codes(mutated(mode="projet", scope="all", briques=["B07", "B08"], checkpoints=soft)) == ["checkpoint_blocking_missing"]


def test_checkpoint_needs_something_jay_can_check():
    bad = [{"id": "C1", "apres": "B08", "jay_verifie": "  ", "bloquant": True}]
    assert codes(mutated(checkpoints=bad)) == ["checkpoint_invalid"]


def test_checkpoint_ids_must_be_unique():
    dup = VALID["checkpoints"] * 2
    assert codes(mutated(checkpoints=dup)) == ["checkpoint_invalid"]


def test_unknown_deploy_policy_is_refused():
    assert codes(mutated(deploy="oui")) == ["deploy_invalid"]


def test_deploy_needs_a_blocking_checkpoint_before_going_live():
    live = mutated(deploy="staging")
    assert codes(live) == ["deploy_checkpoint_missing"]
    live["checkpoints"] = VALID["checkpoints"] + [
        {"id": "C2", "apres": "B08", "jay_verifie": "version en ligne", "bloquant": True,
         "avant_mise_en_ligne": True}]
    assert codes(live) == []


def test_deliverable_must_be_verifiable_in_a_closed_way():
    assert codes(mutated(livrable=[])) == ["livrable_missing"]
    bad = [{"id": "L1", "preuve": "ca marche", "verification": "a_l_oeil"}]
    assert codes(mutated(livrable=bad)) == ["livrable_invalid"]


def test_a_command_deliverable_names_its_command():
    bad = [{"id": "L1", "preuve": "tests", "verification": "commande"}]
    assert codes(mutated(livrable=bad)) == ["livrable_invalid"]


def test_changed_versions_void_the_contract():
    assert codes(VALID, cdc_version="0.7.0") == ["contract_void"]
    assert codes(VALID, pet_version="1.0.0") == ["contract_void"]


def test_estimate_above_the_ceiling_is_refused():
    # median 2.5 x 2 bricks x 1.5 = 7.5 USD
    cheap = {**VALID["budget"], "cout_max_usd": 5}
    assert codes(mutated(budget=cheap)) == ["estimate_above_ceiling"]
    assert codes(mutated(budget={**VALID["budget"], "cout_max_usd": 7.5})) == []


def test_projet_estimate_uses_the_remaining_brick_count():
    big = mutated(mode="projet", scope="all", briques=[f"B{i:02d}" for i in range(1, 11)])
    assert codes(big, remaining_bricks=10) == ["estimate_above_ceiling"]  # 37.5 > 20
    assert codes(big, remaining_bricks=4) == []                            # 15 <= 20
    assert codes(big) == ["estimate_above_ceiling"]                        # no override: the closed list counts


def test_no_history_is_a_warning_never_a_made_up_number():
    found = tool.lint(VALID, cdc_version="0.6.0", pet_version="0.9.0", cost_history=[])
    assert [v.code for v in found if v.severity == "error"] == []
    assert "estimate_unavailable" in [v.code for v in found if v.severity == "warning"]


def test_every_error_is_reported_not_only_the_first():
    data = mutated(mode="tout", deploy="oui", budget=tool.DELETE)
    assert set(codes(data)) >= {"mode_invalid", "deploy_invalid", "budget_missing"}


def test_frontmatter_is_read_with_safe_load(tmp_path):
    path = tmp_path / "c.md"
    path.write_text("---\nmode: !!python/object/apply:os.system ['echo no']\n---\nbody\n", encoding="utf-8")
    try:
        tool.load_frontmatter(path.read_text(encoding="utf-8"))
    except tool.ContractFormatError:
        return
    raise AssertionError("an unsafe tag must be refused, not executed")


def test_the_unfilled_template_is_refused():
    template = Path(__file__).resolve().parents[2] / "skills/concevoir/contrat-autonomie-template.md"
    data = tool.load_frontmatter(template.read_text(encoding="utf-8"))
    found = codes(data)
    assert {"budget_invalid", "livrable_invalid"} & set(found) and "contract_void" in found  # never starts a run


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.md"
    good.write_text("---\n" + tool.dump_yaml(VALID) + "---\nbody\n", encoding="utf-8")
    hist = tmp_path / "hist.json"
    hist.write_text(json.dumps([2.0, 3.0, 2.5]), encoding="utf-8")
    args = [str(good), "--cdc-version", "0.6.0", "--pet-version", "0.9.0", "--history", str(hist)]
    assert tool.main(args) == 0
    assert tool.main(args[:-2] + ["--history", str(hist), "--cdc-version", "9"]) == 1
    assert tool.main([str(tmp_path / "absent.md")]) == 2


def test_missing_pyyaml_is_a_clear_exit_2_not_a_traceback(tmp_path):
    """Le linter sert avant un long travail seul : sans PyYAML il le dit et donne la commande, il ne plante pas."""
    import subprocess
    good = tmp_path / "c.md"
    good.write_text("---\nmode: brique\n---\nbody\n", encoding="utf-8")
    code = ("import sys; sys.modules['yaml'] = None; import runpy; sys.argv = ['contract_lint', %r]; "
            "runpy.run_path(%r, run_name='__main__')" % (str(good), str(TOOL)))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 2 and "pip install pyyaml" in out.stderr and "Traceback" not in out.stderr


def test_a_boolean_is_not_a_budget_number():
    budget = {**VALID["budget"], "cout_max_usd": True}
    assert "budget_invalid" in codes(mutated(budget=budget))


def test_an_infinite_or_nan_ceiling_is_refused():
    for bad in (float("inf"), float("nan")):
        for key in ("cout_max_usd", "tokens_max", "duree_max_h"):
            assert "budget_invalid" in codes(mutated(budget={**VALID["budget"], key: bad})), (key, bad)


def test_scope_must_name_real_distinct_bricks():
    for scope in ([None, None], ["", ""], ["B1", "B1"], [{}, {}]):
        assert "scope_mismatch" in codes(mutated(mode="lot", scope=scope)), scope
    assert "scope_mismatch" in codes(mutated(mode="brique", scope=[{}]))


def test_a_duplicate_key_in_the_header_is_refused():
    text = "---\nmode: projet\nmode: lot\n---\nbody\n"
    try:
        tool.load_frontmatter(text)
    except tool.ContractFormatError as exc:
        assert "mode" in str(exc)
        return
    raise AssertionError("the last duplicate key must not win silently")


def test_an_invalid_cost_history_is_a_clean_exit_2(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text("---\n" + tool.dump_yaml(VALID) + "---\nbody\n", encoding="utf-8")
    for bad in ('{"B07": 3.1}', '["a", "b"]', "[-1, 2]", "[NaN, 2]"):
        hist = tmp_path / "h.json"
        hist.write_text(bad, encoding="utf-8")
        assert tool.main([str(good), "--history", str(hist)]) == 2, bad
    assert "Traceback" not in capsys.readouterr().err


def test_project_mode_needs_a_closed_list_of_distinct_bricks():
    for bad in (tool.DELETE, [], ["B1", "B1"], ["", "B2"], "B1", ["b1", "B1"]):
        assert "briques_invalid" in codes(mutated(mode="projet", scope="all", briques=bad)), bad
