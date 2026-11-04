"""lib/plan_bricks.py — la liste fermée des briques du contrat : lecture de la feuille de route, statuts, options, ligne de commande."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_bricks_helpers as _h  # noqa: E402

globals().update({k: v for k, v in vars(_h).items() if not k.startswith("__")})  # shared plans and readers, underscore names included


# --- ce qui est lu -------------------------------------------------------------------------------------------------


def test_the_roadmap_of_the_template_is_read_with_its_statuses():
    r = read(TEMPLATE_PET)
    assert r.problems == [] and [(b.id, b.state) for b in r.bricks] == [("B-001", "fait"), ("B-002", "en cours"), ("B-003", "à faire")]


def test_a_real_plan_with_other_tables_and_long_status_cells_is_read():
    r = read(DOGU_LIKE)
    assert r.problems == []
    assert [b.id for b in r.bricks] == ["B00", "B02b", "B03", "B09a", "B09b", "B10", "B11"]  # the "Ordre" table is not the roadmap
    assert [b.state for b in r.bricks] == ["fait", "fait", "fait", "fait", "à faire", "fait", "en cours"]


def test_remaining_bricks_are_the_ones_not_done_in_file_order():
    assert pb.remaining(read(DOGU_LIKE)) == ["B09b", "B11"]
    assert pb.remaining(read(DOGU_LIKE), include_done=True) == ["B00", "B02b", "B03", "B09a", "B09b", "B10", "B11"]


# --- ce qui est un problème (jamais ignoré) ---------------------------------------------------------------------------


def test_a_detailed_brick_missing_from_the_roadmap_is_a_problem():
    text = DOGU_LIKE + "#### B38 — Appliquer\n#### B39 — Modèle local\n"
    r = read(text)
    assert any("B38" in p and "B39" in p and "absentes de la feuille de route" in p for p in r.problems)


def test_an_unknown_status_is_a_problem():
    r = read(DOGU_LIKE.replace("| ⬜ |", "| bientôt |"))
    assert any("B09b" in p and "statut" in p for p in r.problems)


def test_a_duplicate_id_is_a_problem():
    r = read(DOGU_LIKE.replace("| B11 | Jauges", "| B09b | Jauges"))
    assert any("B09b" in p and "deux fois" in p for p in r.problems)


def test_a_roadmap_row_without_a_brick_id_is_a_problem():
    r = read(DOGU_LIKE.replace("| B11 | Jauges", "| ??? | Jauges"))
    assert any("identifiant" in p for p in r.problems)


def test_a_table_row_outside_any_table_is_a_problem():
    r = read(DOGU_LIKE + "\n| B50 | Orpheline | F-1 | Standard | — | ⬜ |\n")
    assert any("hors de tout tableau" in p for p in r.problems)


def test_no_roadmap_table_at_all_is_a_problem():
    assert read("# PET\n\n## 6. Roadmap\n\nrien\n").problems


def test_a_brick_without_a_detail_heading_is_only_a_warning():
    r = read(TEMPLATE_PET.replace("### B-003 — Auth\n", ""))
    assert r.problems == [] and any("B-003" in w for w in r.warnings)


def test_brick_ids_are_case_preserved_and_compared_without_case():
    assert read(DOGU_LIKE.replace("#### B09b — Palette", "#### b09B — Palette")).problems == []


# --- le contrôle d'un contrat -----------------------------------------------------------------------------------------


def test_a_contract_list_missing_a_remaining_brick_is_reported():
    gaps = pb.check_contract(contract(mode="projet", scope="all", briques=["B09b"]), read(DOGU_LIKE))
    assert any("B11" in g and "manque" in g for g in gaps)


def test_a_contract_list_with_a_done_or_unknown_brick_is_reported():
    gaps = pb.check_contract(contract(mode="projet", scope="all", briques=["B09b", "B11", "B00", "B77"]), read(DOGU_LIKE))
    assert any("B00" in g and "déjà faite" in g for g in gaps) and any("B77" in g and "inconnue" in g for g in gaps)


def test_a_matching_contract_list_has_no_gap():
    assert pb.check_contract(contract(mode="projet", scope="all", briques=["b09B", "B11"]), read(DOGU_LIKE)) == []


def test_a_lot_scope_is_checked_for_unknown_bricks_only():
    r = read(DOGU_LIKE)
    assert pb.check_contract(contract(scope=["B09b", "B11"]), r) == []
    assert any("B77" in g for g in pb.check_contract(contract(scope=["B09b", "B77"]), r))


# --- la ligne de commande ---------------------------------------------------------------------------------------------


def test_cli_prints_the_yaml_list_and_exits_0(tmp_path):
    out = _cli(tmp_path, DOGU_LIKE)
    assert out.returncode == 0 and "briques:" in out.stdout and "- B09b" in out.stdout and "- B11" in out.stdout
    assert "B00" not in out.stdout


def test_cli_prints_no_list_when_there_are_problems(tmp_path):
    out = _cli(tmp_path, DOGU_LIKE + "#### B38 — Appliquer\n")
    assert out.returncode == 1 and "briques:" not in out.stdout and "B38" in out.stderr


def test_cli_checks_a_contract_and_exits_1_on_a_gap(tmp_path):
    import yaml
    path = tmp_path / "Contrat.md"
    def write(briques):
        path.write_text("---\n" + yaml.safe_dump(contract(mode="projet", scope="all", briques=briques), allow_unicode=True) + "---\nbody\n", encoding="utf-8")
    write(["B09b"])
    out = _cli(tmp_path, DOGU_LIKE, "--check", str(path))
    assert out.returncode == 1 and "B11" in out.stderr + out.stdout
    write(["B09b", "B11"])
    assert _cli(tmp_path, DOGU_LIKE, "--check", str(path)).returncode == 0


def test_cli_unreadable_input_is_exit_2(tmp_path):
    out = subprocess.run([sys.executable, str(LIB / "plan_bricks.py"), str(tmp_path / "absent.md")], capture_output=True, text=True)
    assert out.returncode == 2 and "Traceback" not in out.stderr


def test_examples_inside_a_code_block_are_not_the_plan_but_their_ids_are_still_flagged():
    example = "\n```\n| B99 | Exemple | ⬜ |\n### B98 — exemple\n| ID | Brique | Statut |\n|---|---|---|\n| B97 | x | ⬜ |\n```\n"
    r = read(DOGU_LIKE + example)
    assert [b.id for b in r.bricks] == ["B00", "B02b", "B03", "B09a", "B09b", "B10", "B11"]  # never read as roadmap rows
    assert any("B97" in p and "B98" in p and "B99" in p for p in r.problems)          # but never silently dropped
    ok = _rr(DOGU_LIKE + example, known=["B97", "B98", "B99"])
    assert ok.problems == [] and any("B99" in w for w in ok.warnings)


# --- trancher explicitement les briques détaillées mais absentes de la feuille de route ---------------------------------


def test_an_absent_brick_can_be_included_on_purpose_and_is_marked_as_such():
    r = _rr(ABSENT, include=["B38", "b39"])
    assert r.problems == []
    assert pb.remaining(r) == ["B09b", "B11", "B38", "B39"]
    assert [b.state for b in r.bricks if b.id in ("B38", "B39")] == ["à faire", "à faire"]
    assert any("B38" in w and "ajoutée" in w for w in r.warnings)


def test_including_only_some_absent_bricks_leaves_the_others_a_problem():
    r = _rr(ABSENT, include=["B38"])
    assert any("B39" in p for p in r.problems) and not any("B38" in p for p in r.problems)


def test_including_an_id_that_is_not_an_absent_detailed_brick_is_a_problem():
    for bad in ("B11", "B77", "pas-un-id"):
        r = _rr(ABSENT, include=["B38", "B39", bad])
        assert any(bad in p and "inclure" in p for p in r.problems), bad


def test_warnings_about_missing_detail_sheets_are_one_line_not_one_per_brick():
    text = TEMPLATE_PET.replace("### B-002 — Schéma DB\n### B-003 — Auth\n", "")
    r = read(text)
    assert len([w for w in r.warnings if "fiche" in w]) == 1 and "B-002" in r.warnings[0] and "B-003" in r.warnings[0]


def test_cli_include_flag(tmp_path):
    pet = tmp_path / "PET.md"
    pet.write_text(ABSENT, encoding="utf-8")
    base = [sys.executable, str(LIB / "plan_bricks.py"), str(pet), "--numerotation-libre"]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 1
    out = subprocess.run(base + ["--inclure", "B38,B39"], capture_output=True, text=True)
    assert out.returncode == 0 and "- B38" in out.stdout and "- B39" in out.stdout


