"""lib/plan_bricks.py — lecture fermée : invariant, plages, numérotation (relectures successives)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_bricks_helpers as _h  # noqa: E402

globals().update({k: v for k, v in vars(_h).items() if not k.startswith("__")})  # shared plans and readers, underscore names included


# --- lecture fermée par le contenu : 3e relecture ratée sur la lecture par noms de colonnes (Jay 2026-11-04) -------------


def test_a_status_cell_with_two_different_states_is_a_problem():
    base = DOGU_LIKE.replace("| B09b | Palette | F-034 | Standard | B09a | ⬜ |", "| B09b | Palette | F-034 | Standard | B09a | {} |")
    for cell in ("🟢 → 🟡 rouvert", "⬜ puis 🟢", "🟡 mais 🔴", "🔴 bloqué (B00 🟢)", "🟡 (attend B00 🟢)"):
        assert any("B09b" in p and "plusieurs statuts" in p for p in _problems(base.format(cell))), cell


def test_the_same_state_written_twice_in_a_cell_is_not_a_problem():
    base = DOGU_LIKE.replace("| B09b | Palette | F-034 | Standard | B09a | ⬜ |", "| B09b | Palette | F-034 | Standard | B09a | 🟢 fait, 🟢 vérifié |")
    assert _problems(base) == []


def test_a_status_table_without_a_column_of_brick_ids_is_a_problem():
    koshin = in_roadmap(DOGU_LIKE, "\n### Phase X\n| # | Brique | Statut |\n|---|---|---|\n| 1 | Démarrer | ⬜ |\n| 2 | Finir | ⬜ |\n")
    assert any("colonne d'identifiants" in p for p in _problems(koshin))


def test_a_second_roadmap_table_with_another_header_name_is_read_not_ignored():
    koshin_like = in_roadmap(DOGU_LIKE, "\n| # | Brique | Statut |\n|---|---|---|\n| K-B1 | Démarrer | ⬜ |\n| A-B0 | Socle | 🟢 |\n")
    problems, left = _remaining(koshin_like)
    assert problems == [] and "K-B1" in left and "A-B0" not in left and "B09b" in left


def test_the_id_column_is_found_by_its_content_not_by_its_position():
    text = in_roadmap(DOGU_LIKE, "\n| Phase | ID | Statut |\n|---|---|---|\n| P1 | B50 | ⬜ |\n")
    r = _rr(text + "#### B50 — x\n")
    assert "B50" in pb.remaining(r) and r.problems == []


def test_a_brick_mentioned_in_another_table_but_missing_from_the_roadmap_is_a_problem():
    text = DOGU_LIKE + "\n| Ordre | Brique |\n|---|---|\n| 1 | B77 |\n"
    assert any("B77" in p and "ligne" in p for p in _problems(text))


def test_a_row_with_pipes_but_no_leading_pipe_in_the_roadmap_is_still_a_row():
    last_row = "| B11 | Jauges | F-004 | Standard | B10 | 🟡 |\n"
    text = DOGU_LIKE.replace(last_row, last_row + "B88 | Dernière | F-1 | Standard | — | ⬜ |\n") + "#### B88 — x\n"
    r = read(text)
    assert r.problems == [] and "B88" in pb.remaining(r)


def test_a_pipe_line_outside_a_table_starting_with_a_brick_id_is_a_problem():
    text = DOGU_LIKE + "\nB99 | Orpheline | ⬜\n"
    assert any("B99" in p for p in _problems(text))


def test_prose_with_a_shell_pipe_is_not_a_problem():
    assert _problems(DOGU_LIKE + "\nOn lance `ls | grep x` puis ls | wc.\n") == []


def test_detail_headings_are_found_with_bold_emoji_depth_and_case():
    for heading in ("### **B50** — x", "### 🔴 B50 — x", "###### B50 — x", "### b50 — x"):
        assert any("b50" in p.lower() and "absentes" in p for p in _problems(DOGU_LIKE + heading + "\n")), heading


def test_hyphen_and_case_differences_do_not_hide_a_duplicate_or_a_gap():
    assert any("deux fois" in p for p in _problems(DOGU_LIKE.replace("| B11 | Jauges", "| B-09b | Jauges")))
    assert pb.check_contract(contract(mode="projet", scope="all", briques=["B-09b", "b11"]), read(DOGU_LIKE)) == []


def test_a_contract_list_with_a_repeated_brick_is_reported():
    gaps = pb.check_contract(contract(mode="projet", scope="all", briques=["b11", " B11 ", "B09b"]), read(DOGU_LIKE))
    assert any("contrat invalide" in g and "briques_invalid" in g for g in gaps)  # the contract lint already refuses duplicates


def test_an_included_id_close_to_a_roadmap_id_is_flagged_as_a_possible_typo():
    text = DOGU_LIKE + "#### B1 — faute de frappe\n"
    r = _rr(text, include=["B1"])
    assert any("B1" in w and "proche de" in w and "B11" in w for w in r.warnings)


def test_the_refusal_without_a_roadmap_names_the_tables_it_saw():
    r = read("# PET\n\n| # | Brique | Avancement |\n|---|---|---|\n| 1 | x | ok |\n")
    assert any("aucune feuille de route" in p and "Avancement" in p for p in r.problems)


# --- un tableau Statut qui ne parle pas de briques : avertissement nommé, pas blocage -------------------------------------


def test_a_status_table_that_is_not_about_bricks_is_a_named_warning():
    text = in_roadmap(DOGU_LIKE, "\n| Fonction | Fichier | Statut |\n|---|---|---|\n| f1 | a.py | ⬜ |\n")
    r = read(text)
    assert r.problems == [] and any("Fonction" in w and "Statut" in w for w in r.warnings)


def test_a_status_table_whose_header_speaks_of_bricks_but_has_no_ids_is_a_problem():
    for head in ("Brique", "Brick", "Briques réutilisées"):
        text = in_roadmap(DOGU_LIKE, f"\n| N | {head} | Statut |\n|---|---|---|\n| 1 | x | ⬜ |\n")
        assert any("colonne d'identifiants" in p for p in _problems(text)), head


def test_a_sub_brick_of_a_known_brick_is_not_flagged_as_a_typo():
    text = DOGU_LIKE + "#### B11a — sous-brique\n"
    r = _rr(text, include=["B11a"])
    assert r.problems == [] and not any("proche de" in w for w in r.warnings)


# --- l'invariant de fermeture : tout identifiant écrit dans le PET est dans la feuille de route (2e relecture FAIL) --------


def test_a_roadmap_in_a_quote_or_callout_is_not_lost():
    quote = "\n> | ID | Brique | Statut |\n> |---|---|---|\n> | B53 | c | ⬜ |\n"
    assert any("B53" in p for p in _hidden(quote))


def test_a_roadmap_after_a_nested_code_fence_is_read_not_lost():
    for opener in ("````", "~~~"):
        block = f"\n{opener}md\n```\nx\n{opener}\n| ID | Brique | Statut |\n|---|---|---|\n| B54 | c | ⬜ |\n#### B54 — c\n"
        r = read(in_roadmap(DOGU_LIKE, block))
        assert r.problems == [] and "B54" in pb.remaining(r), opener  # the fence is followed like CommonMark: B54 is real


def test_ignoring_a_table_cannot_erase_its_bricks():
    text = DOGU_LIKE + "\n| # | Brique | Statut |\n|---|---|---|\n| K-B7 | Démarrer | ⬜ |\n"
    r = _rr(text, ignore=["#"])
    assert any("K-B7" in p for p in r.problems)


def test_ids_in_any_cell_or_prose_must_exist_in_the_roadmap():
    for block in ("\n| x | B40, B41 | y |\n", "\nVoir **B42** (reportée).\n", "\n- [ ] B43 à relire\n"):
        assert any(ident in " ".join(_hidden(block)) for ident in ("B40", "B42", "B43")), block
    dep = DOGU_LIKE.replace("| B11 | Jauges | F-004 | Standard | B10 | 🟡 |", "| B11 | Jauges | F-004 | Standard | B99 | 🟡 |")
    assert any("B99" in p for p in read(dep).problems)


def test_the_problem_names_the_line_of_each_stray_id():
    problems = _hidden("\nVoir B42.\n")
    assert any("B42 (ligne" in p for p in problems)


def test_known_ids_are_acknowledged_with_a_warning_and_must_really_appear():
    text = DOGU_LIKE + "\nLe modèle B52 est cité.\n"
    assert _rr(text, known=["B52"]).problems == []
    assert any("B52" in w for w in _rr(text, known=["B52"]).warnings)
    assert any("B77" in p and "--connu" in p for p in _rr(text, known=["B52", "B77"]).problems)


def test_words_that_only_look_like_ids_are_not_flagged():
    prose = "\nLe B2B marche, le tab1 aussi, les hash b0c12f4, b3261e et b11829, et RFC-9110 ; voir B09b et B-9b.\n"
    problems = _hidden(prose)
    assert not any(w in p for p in problems for w in ("B2B", "tab1", "b0c12f4", "b3261e", "b11829"))


def test_check_reports_an_invalid_contract_instead_of_saying_no_gap():
    gaps = pb.check_contract(contract(mode="Projet", briques=["B09b", "B11"]), read(DOGU_LIKE))
    assert any("contrat invalide" in g for g in gaps)
    gaps = pb.check_contract(contract(mode="brique", scope="all"), read(DOGU_LIKE))
    assert any("contrat invalide" in g for g in gaps)


def test_cli_known_flag(tmp_path):
    pet = tmp_path / "PET.md"
    pet.write_text(DOGU_LIKE + "\nLe modèle B52 est cité.\n", encoding="utf-8")
    base = [sys.executable, str(LIB / "plan_bricks.py"), str(pet), "--numerotation-libre"]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 1
    assert subprocess.run(base + ["--connu", "B52"], capture_output=True, text=True).returncode == 0


def test_an_ignored_table_is_always_announced():
    text = in_roadmap(DOGU_LIKE, "\n| Réf. | Contenu | Statut |\n|---|---|---|\n| P1a | x | ⬜ |\n")
    r = _rr(text, ignore=["Réf."])
    assert r.problems == [] and any("Réf." in w and "ignoré à la demande" in w for w in r.warnings)


# --- 3e relecture FAIL : « B40-B41 » cachait B41 ; les plages cachent leur milieu ------------------------------------------


def test_both_ends_of_a_hyphenated_pair_are_checked():
    for block in ("\nRestent B40-B41.\n", "\n### B40-B41 — ajout découpé\n", "\n(B40–B41)\n", "\nB40—B41\n"):
        found = _stray(block)
        assert "B40" in found and "B41" in found, block


def test_including_one_end_of_a_pair_does_not_hide_the_other():
    r = _rr(DOGU_LIKE + "\nRestent B40-B41.\n", include=["B40"])
    assert any("B41" in p for p in r.problems)


def test_the_bricks_in_the_middle_of_a_range_must_exist_in_the_roadmap():
    found = _stray("\nVoir B40-B43.\n")
    assert all(b in found for b in ("B40", "B41", "B42", "B43"))
    assert "B09b" not in found


def test_a_range_over_known_bricks_is_fine():
    text = DOGU_LIKE.replace("| B10 | Conversation", "| B10 | Conversation") + "\nVoir B09a–B11 (dont B10).\n"
    problems = read(text).problems
    assert not any("B10" in p for p in problems)  # B10 is in the roadmap; B09b too


def test_a_range_keeps_the_zero_padding_and_the_letter_form():
    assert all(b in _stray("\nVoir B008-B010.\n") for b in ("B008", "B009", "B010"))
    found = _stray("\nVoir B50a-c.\n")
    assert "B50a" in found and "B50b" in found and "B50c" in found


def test_a_huge_or_cross_family_range_is_a_problem_not_a_flood():
    assert any("plage" in p for p in _hidden("\nVoir B1-B900.\n"))
    assert any("plage" in p for p in _hidden("\nVoir K-B1–A-B9.\n"))


def test_the_prefixed_ids_are_still_read_whole():
    assert "K-B7" in _stray("\nVoir K-B7.\n") and "K-B7-" not in _stray("\nVoir K-B7.\n")


def test_tilde_fences_and_html_comments_never_feed_the_roadmap():
    for block in ("\n~~~\n| ID | Brique | Statut |\n|---|---|---|\n| B09 | x | ⬜ |\n~~~\n",
                  "\n<!--\n| ID | Brique | Statut |\n|---|---|---|\n| B09 | x | ⬜ |\n-->\n"):
        r = read(DOGU_LIKE + block)
        assert "B09" not in [b.id for b in r.bricks]
        assert any("B09" in p for p in r.problems)  # but the id is not silently dropped either


def test_a_longer_fence_is_not_closed_by_a_shorter_one():
    block = "\n````md\n```\nexemple\n```\n| ID | Brique | Statut |\n|---|---|---|\n| B09 | x | ⬜ |\n````\n"
    assert "B09" not in [b.id for b in read(DOGU_LIKE + block).bricks]


def test_the_id_column_is_the_one_made_of_ids_not_a_prerequisite_column():
    text = ("# PET\n\n## 6. Roadmap\n\n| Prérequis | Brique | Statut |\n|---|---|---|\n| — | B01 | 🟢 |\n| B01 | B02 | ⬜ |\n"
            "#### B01 — a\n#### B02 — b\n")
    r = read(text)
    assert r.problems == [] and [(b.id, b.state) for b in r.bricks] == [("B01", "fait"), ("B02", "à faire")]


def test_two_columns_of_ids_with_no_way_to_tell_them_apart_is_a_problem():
    text = "# PET\n\n## 6. Roadmap\n\n| Prérequis | Suivant | Statut |\n|---|---|---|\n| B02 | B01 | 🟢 |\n| B01 | B02 | ⬜ |\n"
    assert any("plusieurs colonnes" in p for p in read(text).problems)


def test_a_pair_is_checked_even_when_only_the_hyphen_scan_could_see_it():
    assert "B77" in _stray("\nvoir ref-B77 ici\n")  # an id glued to a word by a hyphen is still an id


def test_a_reversed_or_suffixed_range_is_a_problem():
    for block in ("\nVoir B43-B40.\n", "\nVoir B50a–B52c.\n", "\nVoir B52c-a.\n"):
        assert any("plage" in p for p in _hidden(block)), block


# --- 4e relecture FAIL : les écritures de plage en français sont un ensemble ouvert -> contrôle de numérotation ---------------


def test_a_hole_in_the_numbering_is_a_problem_whatever_the_prose_says():
    for prose in ("", "\nReste B11 à B15.\n", "\nReste B11-15.\n", "\nB11 → B15\n", "\nB11..B15\n", "\nB12, B13, ..., B15\n"):
        r = _gap(prose)
        assert any("B14" in p and "numérotation" in p for p in r.problems), prose


def test_a_numbering_without_a_hole_is_fine():
    assert _gap().problems != [] and pb.read_roadmap(GAP_PET.replace("| B15 | d | ⬜ |", "| B14 | d | ⬜ |\n| B15 | e | ⬜ |").replace("#### B15 — d", "#### B14 — d\n#### B15 — e")).problems == []


def test_a_hole_can_be_acknowledged_on_purpose_and_stays_visible():
    r = _gap(trou=["B14"])
    assert r.problems == [] and any("B14" in w and "trou" in w for w in r.warnings)


def test_acknowledging_something_that_is_not_a_hole_is_a_problem():
    r = _gap(trou=["B14", "B12", "B99"])
    assert any("B12" in p and "--trou" in p for p in r.problems) and any("B99" in p and "--trou" in p for p in r.problems)


def test_free_numbering_switches_the_check_off_visibly():
    r = _gap(libre=True)
    assert r.problems == [] and any("numérotation libre" in w for w in r.warnings)


def test_families_are_checked_apart():
    text = GAP_PET.replace("| B15 | d | ⬜ |", "| B14 | d | ⬜ |\n| K-B1 | e | ⬜ |\n| K-B2 | f | ⬜ |\n| A-B0 | g | ⬜ |\n| A-B2 | h | ⬜ |")
    text = text.replace("#### B15 — d", "#### B14 — d\n#### K-B1 — e\n#### K-B2 — f\n#### A-B0 — g\n#### A-B2 — h")
    problems = " ".join(pb.read_roadmap(text).problems)
    assert "A-B1" in problems and "K-B" not in problems.replace("A-B1", "") and "B14" not in problems


def test_sub_bricks_cover_their_parent_number():
    text = GAP_PET.replace("| B15 | d | ⬜ |", "| B14a | d | ⬜ |\n| B14b | e | ⬜ |\n| B15 | f | ⬜ |")
    text = text.replace("#### B15 — d", "#### B14a — d\n#### B14b — e\n#### B15 — f")
    assert pb.read_roadmap(text).problems == []


def test_the_hole_keeps_the_zero_padding_of_its_family():
    text = GAP_PET.replace("B11", "B-001").replace("B12", "B-002").replace("B13", "B-003").replace("B15", "B-005")
    assert any("B-004" in p for p in pb.read_roadmap(text).problems)


def test_a_hole_is_listed_once_with_its_neighbours():
    problems = [p for p in _gap().problems if "numérotation" in p]
    assert len(problems) == 1 and "B13" in problems[0] and "B15" in problems[0]


def test_an_acknowledged_unknown_id_with_a_detail_sheet_is_refused():
    text = GAP_PET.replace("| B15 | d | ⬜ |", "| B14 | d | ⬜ |").replace("#### B15 — d", "#### B14 — d")
    r = pb.read_roadmap(text + "\n### B2 — Paiement\n", known=["B2"])
    assert any("B2" in p and "fiche" in p for p in r.problems)


def test_the_real_templates_have_no_hole():
    template = Path(__file__).resolve().parents[3] / "templates/docs-structure/PET.md"
    if not template.is_file():  # les dépôts receveurs n'ont pas le gabarit : ce test ne vaut que dans Kata
        pytest.skip("gabarit PET absent (dépôt receveur)")
    assert pb.read_roadmap(template.read_text(encoding="utf-8")).problems == []


def test_cli_trou_and_libre_flags(tmp_path):
    pet = tmp_path / "PET.md"
    pet.write_text(GAP_PET, encoding="utf-8")
    base = [sys.executable, str(LIB / "plan_bricks.py"), str(pet)]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 1
    assert subprocess.run(base + ["--trou", "B14"], capture_output=True, text=True).returncode == 0
    assert subprocess.run(base + ["--numerotation-libre"], capture_output=True, text=True).returncode == 0


def test_a_title_starting_with_a_single_letter_is_not_a_letter_range():
    text = GAP_PET.replace("#### B15 — d", "#### B15 — a faire\n#### B13 — c bis\n")
    assert not any("plage" in p or "B13b" in p for p in pb.read_roadmap(text, trou=["B14"]).problems)


# --- 5e relecture FAIL : l'outil devinait quel tableau est la feuille de route -> on l'ancre sur sa section -------------------


RISK_PET = """# PET

## 6. Roadmap

| ID | Brique | Statut |
|---|---|---|
| B1 | a | ⬜ |
| B2 | b | ⬜ |

## 7. Détail par brique

#### B1 — a
#### B2 — b

## 9. Risques

| Risque | Brique | Statut |
|---|---|---|
| perte de données | B3 | 🟢 |
"""


def test_a_status_table_outside_the_roadmap_section_is_not_the_roadmap():
    r = pb.read_roadmap(RISK_PET)
    assert [b.id for b in r.bricks] == ["B1", "B2"]
    assert any("B3" in p and "absentes de la feuille de route" in p for p in r.problems)  # not absorbed as « fait »


def test_a_brick_cited_in_a_risk_table_that_exists_in_the_roadmap_is_fine_once_the_table_is_set_aside():
    text = RISK_PET.replace("| perte de données | B3 | 🟢 |", "| perte de données | B2 | 🟢 |")
    assert any("HORS de la section" in p for p in pb.read_roadmap(text).problems)  # never silently dropped
    r = pb.read_roadmap(text, ignore=["Risque"])
    assert r.problems == [] and [b.state for b in r.bricks] == ["à faire", "à faire"]


def test_tables_in_sub_sections_of_the_roadmap_count_and_tables_after_it_do_not():
    text = RISK_PET.replace("| B2 | b | ⬜ |", "| B2 | b | ⬜ |\n\n### Phase 2\n\n| ID | Brique | Statut |\n|---|---|---|\n| B3 | c | ⬜ |").replace("#### B2 — b", "#### B2 — b\n#### B3 — c")
    r = pb.read_roadmap(text, ignore=["Risque"])
    assert [b.id for b in r.bricks] == ["B1", "B2", "B3"] and r.problems == []


def test_no_roadmap_section_is_a_problem_that_names_the_way_out():
    text = RISK_PET.replace("## 6. Roadmap", "## 6. Plan")
    problems = " ".join(pb.read_roadmap(text).problems)
    assert "section" in problems and "--section" in problems


def test_the_section_can_be_named_on_purpose():
    text = RISK_PET.replace("## 6. Roadmap", "## 6. Plan des briques")
    r = pb.read_roadmap(text, section="Plan des briques")
    assert [b.id for b in r.bricks] == ["B1", "B2"]


def test_the_roadmap_section_title_is_found_whatever_its_wording():
    for title in ("## 6. Roadmap — Briques", "## 6. Roadmap (Bricks) — LIVE", "## Feuille de route"):
        text = RISK_PET.replace("## 6. Roadmap", title)
        assert [b.id for b in pb.read_roadmap(text).bricks] == ["B1", "B2"], title


def test_a_missing_sub_brick_letter_is_a_hole():
    text = GAP_PET.replace("| B15 | d | ⬜ |", "| B14a | d | ⬜ |\n| B14c | e | ⬜ |\n| B15 | f | ⬜ |")
    text = text.replace("#### B15 — d", "#### B14a — d\n#### B14c — e\n#### B15 — f")
    assert any("B14b" in p and "numérotation" in p for p in pb.read_roadmap(text).problems)
    text2 = text.replace("| B14a | d | ⬜ |\n", "")
    assert any("B14a" in p for p in pb.read_roadmap(text2.replace("#### B14a — d\n", "")).problems)


def test_a_family_written_with_and_without_a_hyphen_is_one_family():
    text = "# PET\n\n## 6. Roadmap\n\n| ID | Brique | Statut |\n|---|---|---|\n| B11 | a | 🟢 |\n| B-14 | d | ⬜ |\n\n#### B11 — a\n#### B-14 — d\n"
    problems = " ".join(pb.read_roadmap(text).problems)
    assert "B12" in problems and "B13" in problems  # B11 and B-14 are one family: the hole is seen


def test_two_status_columns_are_a_problem():
    text = RISK_PET.replace("| ID | Brique | Statut |\n|---|---|---|\n| B1 | a | ⬜ |", "| ID | Statut | Brique | Statut |\n|---|---|---|---|\n| B1 | ⬜ | a | 🟢 |", 1).replace("| B2 | b | ⬜ |", "| B2 | ⬜ | b | ⬜ |")
    assert any("plusieurs colonnes Statut" in p for p in pb.read_roadmap(text).problems)


def test_bold_headers_and_linked_ids_are_read():
    text = RISK_PET.replace("| ID | Brique | Statut |\n|---|---|---|\n| B1 | a | ⬜ |", "| ID | Brique | **Statut** |\n|---|---|---|\n| [B1](#b1) | a | ⬜ |", 1).replace("| B2 | b | ⬜ |", "| **B2** | b | ⬜ |")
    assert [b.id for b in pb.read_roadmap(text).bricks] == ["B1", "B2"]


def test_many_holes_suggest_free_numbering():
    rows = "\n".join(f"| B{n} | x | ⬜ |" for n in (10, 20, 30, 40, 50, 60, 70))
    text = f"# PET\n\n## 6. Roadmap\n\n| ID | Brique | Statut |\n|---|---|---|\n{rows}\n"
    assert any("par pas" in p and "--numerotation-libre" in p for p in pb.read_roadmap(text).problems)


def test_a_heading_ends_the_table_before_it():
    text = in_roadmap(DOGU_LIKE, "### Phase 9\n| B77 | x | F | S | — | ⬜ |\n")
    assert any("B77" in p for p in pb.read_roadmap(text, libre=True).problems)
    glued = DOGU_LIKE.replace("| B11 | Jauges | F-004 | Standard | B10 | 🟡 |\n", "| B11 | Jauges | F-004 | Standard | B10 | 🟡 |\n### Phase 9\n| B77 | x | F | S | — | ⬜ |\n", 1)
    assert any("hors de tout tableau" in p for p in pb.read_roadmap(glued, libre=True).problems)


# --- 6e relecture FAIL : un tableau Statut + ids hors de la section ancrée ne doit jamais être écarté en silence -----------


WRONG_ANCHOR = """# PET

## Roadmap des risques

| Brique | Risque | Statut |
|---|---|---|
| B01 | a | 🟢 |
| B02 | b | 🟢 |
| B03 | c | 🟢 |

## Plan d'exécution

| Brique | Nom | Statut |
|---|---|---|
| B01 | a | 🟢 |
| B02 | b | ⬜ |
| B03 | c | ⬜ |
"""


def test_a_status_and_ids_table_outside_the_anchored_section_is_a_problem_not_silence():
    problems = " ".join(pb.read_roadmap(WRONG_ANCHOR).problems)
    assert "Plan d'exécution" in problems or "Nom" in problems
    assert "--section" in problems and "--ignorer-tableau" in problems


def test_naming_the_real_section_and_ignoring_the_risk_table_gives_the_real_list():
    text = WRONG_ANCHOR.replace("| Brique | Risque | Statut |", "| Registre | Risque | Statut |\n|---|---|---|\n| B01 | a | 🟢 |\n| B02 | b | 🟢 |\n| B03 | c | 🟢 |\n\n| Brique | Risque | Statut |", 1)
    r = pb.read_roadmap(text, section="Plan d'exécution", ignore=["Registre"], libre=True)
    assert "B02" in pb.remaining(r) and "B03" in pb.remaining(r)


def test_a_table_with_an_id_header_and_unreadable_ids_in_the_roadmap_is_a_problem():
    text = ("# PET\n\n## Roadmap\n\n| Brique | Statut |\n|---|---|\n| B01 | 🟢 |\n| B02 | ⬜ |\n\n### Suite\n\n"
            "| ID | Statut |\n|---|---|\n| B03A | ⬜ |\n| B03B | ⬜ |\n")
    assert any("colonne d'identifiants" in p for p in pb.read_roadmap(text, libre=True).problems)


def test_a_setext_title_anchors_its_section():
    text = RISK_PET.replace("## 6. Roadmap", "Roadmap\n-------").replace("| perte de données | B3 | 🟢 |", "| perte de données | B2 | 🟢 |")
    assert [b.id for b in pb.read_roadmap(text).bricks] == ["B1", "B2"]


def test_a_title_followed_by_an_html_comment_still_closes_the_previous_section():
    text = "# PET\n\n## 6. Roadmap\n\n| ID | Brique | Statut |\n|---|---|---|\n| B1 | a | ⬜ |\n\n## 9. Risques <!-- ancien -->\n\n| Risque | Brique | Statut |\n|---|---|---|\n| x | B3 | 🟢 |\n"
    problems = " ".join(pb.read_roadmap(text).problems)
    assert "HORS de la section" in problems or "B3" in problems  # the risk table is not swallowed by the roadmap section


def test_the_section_chosen_on_purpose_is_announced():
    text = RISK_PET.replace("## 6. Roadmap", "## 6. Plan des briques")
    r = pb.read_roadmap(text, section="Plan des briques")
    assert any("Plan des briques" in w and "--section" in w for w in r.warnings)


def test_the_letter_gap_message_names_the_missing_letter_first():
    text = GAP_PET.replace("| B15 | d | ⬜ |", "| B14b | d | ⬜ |\n| B14c | e | ⬜ |\n| B15 | f | ⬜ |")
    text = text.replace("#### B15 — d", "#### B14b — d\n#### B14c — e\n#### B15 — f")
    assert any("B14a (entre" in p for p in pb.read_roadmap(text).problems)
