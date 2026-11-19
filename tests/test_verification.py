"""Unit tests of the verification checks, on temporary fixtures (never the real repository)."""
import csv
import json
import shutil
import statistics
import subprocess
from pathlib import Path

import pytest

from verification import (check_all, check_deviations, check_ext_outputs,
                          check_extraction_totals, check_inventory, check_outputs,
                          check_plan_order)

PLAN = "# Plan\n\nBefore.\n\n## 13. Deviations\n\n**18 November 2026.** None.\n"


# ------------------------------------------------------------------ git fixtures

def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                   check=True, capture_output=True)


def commit(repo, files, msg):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        git(repo, "add", rel)
    git(repo, "commit", "-m", msg)
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    return tmp_path


def test_clean_history_passes_and_section13_edit_is_allowed(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    lgd = commit(repo, {"docs/analysis_plan.md": PLAN + "\n**19 November 2026.** LGD.\n"},
                 "lgd deviation")
    commit(repo, {"data/extracted/pq_q1.csv": "a\n1\n", "src/q3_yield.py": "x = 1\n",
                  "outputs/q3_yield.csv": "a\n"}, "work")
    assert check_plan_order.problems(repo, reg, lgd=lgd) == []


def test_edit_above_section13_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Changed.")}, "edit")
    bad = check_plan_order.problems(repo, reg, lgd=None)
    assert len(bad) == 1 and "above section 13" in bad[0]


def test_line_ending_change_above_section13_is_flagged(repo):
    """Byte identity, not line identity: a CRLF conversion of the frozen text fails."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.\n", "Before.\r\n")}, "crlf")
    assert len(check_plan_order.problems(repo, reg, lgd=None)) == 1


def test_output_committed_before_registration_is_flagged(repo):
    commit(repo, {"outputs/q1.csv": "a\n"}, "output first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg, lgd=None)
    assert len(bad) == 1 and "not a descendant" in bad[0]


def test_q_module_in_registration_commit_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN, "src/q4_dose_response.py": "x\n"},
                 "plan+code")
    assert len(check_plan_order.problems(repo, reg, lgd=None)) == 1


def test_outcome_data_before_lgd_commit_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"data/extracted/itr2020_a1_2.csv": "a\n"}, "data first")
    lgd = commit(repo, {"docs/lgd.txt": "lgd\n"}, "lgd deviation")
    bad = check_plan_order.problems(repo, reg, lgd=lgd)
    assert len(bad) == 1 and "outcome data" in bad[0]


def test_outcome_file_in_a_subfolder_before_the_lgd_commit_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"data/extracted/sub/dir/pq_q9.csv": "a\n"}, "nested outcome data first")
    lgd = commit(repo, {"docs/lgd.txt": "lgd\n"}, "lgd deviation")
    bad = check_plan_order.problems(repo, reg, lgd=lgd)
    assert len(bad) == 1 and "outcome data" in bad[0]


def test_outcome_data_on_a_merged_side_branch_is_found_over_the_full_history(repo):
    """History simplification would hide a side-branch commit whose change a merge drops."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, {"data/extracted/itr2023_a1_2.csv": "a\n"}, "outcome data on a side branch")
    git(repo, "checkout", "-q", "-")
    lgd = commit(repo, {"docs/lgd.txt": "lgd\n"}, "lgd deviation")
    git(repo, "merge", "-q", "-s", "ours", "side", "-m", "merge, keeping our tree")
    bad = check_plan_order.problems(repo, reg, lgd=lgd)
    assert len(bad) == 1 and "outcome data" in bad[0]


def test_registration_not_ancestor_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    git(repo, "checkout", "-q", "--orphan", "other")
    commit(repo, {"docs/analysis_plan.md": PLAN}, "unrelated history")
    bad = check_plan_order.problems(repo, reg, lgd=None)
    assert len(bad) == 1 and "not an ancestor" in bad[0]


def test_plan_order_skips_without_git(tmp_path, capsys):
    """A release archive has no .git: the history check is skipped, not failed."""
    assert check_plan_order.main(tmp_path) == 0
    assert capsys.readouterr().out.startswith("SKIPPED: not a git checkout")


def test_plan_order_reads_registration_from_json(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": json.dumps({"registered_commit": reg})},
           "event")
    assert check_plan_order.registered_commit(repo) == reg


# ------------------------------------------------------------------ deviations

LOGGED = (PLAN + "\n**18 November 2026 (after registration).** Question 420 is used only as an"
          " exploratory Q2 cross-check, and Question 1900 likewise (exploratory).\n"
          "\n**19 November 2026 (after registration).** Q1/Q2 corrections (deviation): a "
          "second, corrected set.\n"
          "\n**19 November 2026 (after registration).** District denominator reconstructed "
          "from official notices (deviation); both Q4 analyses are reported.\n")


def _tree(root, plan, outputs, extracted=None):
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "analysis_plan.md").write_text(plan, encoding="utf-8")
    (root / "outputs").mkdir(exist_ok=True)
    for name, text in outputs.items():
        (root / "outputs" / name).write_text(text, encoding="utf-8")
    (root / "data" / "extracted").mkdir(parents=True, exist_ok=True)
    for name, text in (extracted or {}).items():
        (root / "data" / "extracted" / name).write_text(text, encoding="utf-8")


def test_deviations_pass_when_nothing_is_labelled(tmp_path):
    _tree(tmp_path, PLAN, {"q3_yield.csv": "a,b\n1,2\n"})
    assert check_deviations.problems(tmp_path) == ([], [])


def test_unlogged_exploratory_label_is_flagged_any_case(tmp_path):
    _tree(tmp_path, LOGGED, {"q3_yield.csv": "a,b\n1,Exploratory\n"})
    bad, _ = check_deviations.problems(tmp_path)
    assert len(bad) == 1 and "q3_yield.csv" in bad[0]


def test_exploratory_line_naming_a_logged_question_is_accepted(tmp_path):
    _tree(tmp_path, LOGGED, {"q2_discrepancies.csv": "h,analysis\nRSQ420.p003.x,exploratory\n"})
    assert check_deviations.problems(tmp_path)[0] == []


def test_exploratory_line_naming_an_unlogged_question_is_flagged(tmp_path):
    _tree(tmp_path, LOGGED, {"q2_discrepancies.csv": "RSQ1093.p002.x,exploratory\n"})
    assert len(check_deviations.problems(tmp_path)[0]) == 1


def test_exploratory_without_any_entry_is_flagged_even_for_a_logged_question(tmp_path):
    _tree(tmp_path, PLAN, {"q2_discrepancies.csv": "h,analysis\nRSQ420.p003.x,exploratory\n"})
    assert len(check_deviations.problems(tmp_path)[0]) == 1


def test_new_unlogged_q2_exploratory_line_is_flagged(tmp_path):
    """A Q2 file is not blanket-covered by the Q420/Q1900 entry: a line naming no logged
    question, or a logged question in an entry that does not name the analysis, fails."""
    _tree(tmp_path / "a", LOGGED, {"q2_discrepancies.csv": "h,analysis\ng01,new check,exploratory\n"})
    assert len(check_deviations.problems(tmp_path / "a")[0]) == 1
    other = LOGGED.replace("exploratory Q2 cross-check", "exploratory cross-check")
    _tree(tmp_path / "b", other, {"q2_discrepancies.csv": "h,analysis\nRSQ420.p003.x,exploratory\n"})
    assert len(check_deviations.problems(tmp_path / "b")[0]) == 1
    _tree(tmp_path / "c", LOGGED, {"q2_discrepancies.csv": "h,analysis\nRSQ420.p003.x,exploratory\n"})
    assert check_deviations.problems(tmp_path / "c")[0] == []


def test_summary_readme_and_header_lines_keep_the_fallback(tmp_path):
    _tree(tmp_path, LOGGED, {"q2_summary.csv": "Q2 exploratory: agree,36\n",
                             "q2_groups.csv": "key,n_entry_pairs_exploratory\n1,2\n",
                             "README.md": "exploratory entry pairs.\n"})
    assert check_deviations.problems(tmp_path)[0] == []
    _tree(tmp_path / "x", LOGGED, {"q3_summary.csv": "Q3 exploratory: agree,36\n"})
    assert len(check_deviations.problems(tmp_path / "x")[0]) == 1


def test_corrected_set_needs_a_dated_entry(tmp_path):
    named = {"q1_checks_corrected.csv": "a\n1\n"}
    labelled = {"q1_checks.csv": "set,n\ncorrected,1\n"}
    for sub, plan, out, n in (("a", PLAN, named, 1), ("b", LOGGED, named, 0),
                              ("c", PLAN, labelled, 1), ("d", LOGGED, labelled, 0)):
        root = tmp_path / sub
        _tree(root, plan, out)
        assert len(check_deviations.problems(root)[0]) == n, sub


def test_reconstructed_exposure_file_needs_a_dated_entry(tmp_path):
    ex = {"exposure_share_reconstructed.csv": "unit,share\nA,0.5\n"}
    _tree(tmp_path, PLAN, {}, ex)
    assert len(check_deviations.problems(tmp_path)[0]) == 1
    _tree(tmp_path, LOGGED, {}, ex)
    assert check_deviations.problems(tmp_path)[0] == []


def test_q4_reconstructed_label_needs_a_dated_entry(tmp_path):
    _tree(tmp_path, PLAN, {"q4_summary.csv": "set\nreconstructed\n"})
    assert len(check_deviations.problems(tmp_path)[0]) >= 1


# ------------------------------------------------------------------ extraction totals

EXTRACT_HEAD = ["table_key", "source_file", "pdf_page", "column", "canonical", "coarse_unit",
                "is_total", "value", "value_printed"]
CHECK_HEAD = ["table", "source_file", "page", "rows", "sum_of_rows", "printed_total",
              "difference", "pass", "note"]
INV_HEAD = ["fig_id", "quantity", "value", "unit", "geography", "source_file"]


def _csv(path, head, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=head, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in head})


def _extracted_rows(values, total, src="data_raw/x.pdf", col="notified_total"):
    rows = [{"table_key": "T", "source_file": src, "pdf_page": 1, "column": col,
             "canonical": f"S{i}", "coarse_unit": f"S{i}", "is_total": "no", "value": v,
             "value_printed": v} for i, v in enumerate(values)]
    rows.append({"table_key": "T", "source_file": src, "pdf_page": 1, "column": col,
                 "canonical": "India", "coarse_unit": "", "is_total": "yes", "value": total,
                 "value_printed": total})
    return rows


def _totals_tree(root, values, total, rec_sum, rec_total, rec_pass, q4=None):
    ex = root / "data" / "extracted"
    _csv(ex / "itr2020_a1_2.csv", EXTRACT_HEAD, _extracted_rows(values, total))
    _csv(root / "data" / "figures_inventory.csv", INV_HEAD, [])
    diff = "" if rec_total == "" else int(rec_sum) - int(rec_total)
    _csv(ex / "table_total_checks.csv", CHECK_HEAD, [{
        "table": "T", "source_file": "data_raw/x.pdf", "page": 1, "rows": len(values),
        "sum_of_rows": rec_sum, "printed_total": rec_total, "difference": diff,
        "pass": rec_pass, "note": "values kept exactly as printed"}])
    q4 = q4 or {"source": "X", "source_file": "data_raw/x.pdf", "needed_columns":
                "notified_total", "column_check": "pass", "sum_check": "pass",
                "result": "pass", "note": f"notified_total: rows sum to {rec_sum}, printed "
                f"total {rec_total}, difference {diff}"}
    _csv(ex / "q4_source_checks.csv", ["source", "source_file", "needed_columns",
                                       "column_check", "sum_check", "result", "note"], [q4])


def test_totals_clean_fixture_passes(tmp_path):
    _totals_tree(tmp_path, ["3", "4"], "7", "7", "7", "yes")
    assert check_extraction_totals.problems(tmp_path)[0] == []


def test_edited_extracted_value_is_caught(tmp_path):
    _totals_tree(tmp_path, ["3", "4"], "7", "7", "7", "yes")
    p = tmp_path / "data" / "extracted" / "itr2020_a1_2.csv"
    p.write_text(p.read_text(encoding="utf-8").replace(",3,3\n", ",30,30\n", 1),
                 encoding="utf-8")
    bad, _ = check_extraction_totals.problems(tmp_path)
    assert any("not reproduced" in b for b in bad)


def test_wrong_recorded_pass_is_caught(tmp_path):
    _totals_tree(tmp_path, ["3", "6"], "7", "9", "7", "yes")
    bad, _ = check_extraction_totals.problems(tmp_path)
    assert any("recorded pass='yes'" in b for b in bad)


def test_failed_total_recorded_as_failed_is_accepted(tmp_path):
    _totals_tree(tmp_path, ["3", "5"], "7", "8", "7", "no",
                 q4={"source": "X", "source_file": "data_raw/x.pdf",
                     "needed_columns": "notified_total", "column_check": "pass",
                     "sum_check": "fail", "result": "fail",
                     "note": "notified_total: rows sum to 8, printed total 7, difference 1"})
    # difference 1 is within +-1, so the recorded 'no' is wrong
    assert any("recorded pass='no'" in b for b in check_extraction_totals.problems(tmp_path)[0])
    _totals_tree(tmp_path, ["3", "6"], "7", "9", "7", "no",
                 q4={"source": "X", "source_file": "data_raw/x.pdf",
                     "needed_columns": "notified_total", "column_check": "pass",
                     "sum_check": "fail", "result": "fail",
                     "note": "notified_total: rows sum to 9, printed total 7, difference 2"})
    assert check_extraction_totals.problems(tmp_path)[0] == []


def test_extracted_column_without_a_recorded_check_is_caught(tmp_path):
    _totals_tree(tmp_path, ["3", "4"], "7", "7", "7", "yes")
    _csv(tmp_path / "data" / "extracted" / "table_total_checks.csv", CHECK_HEAD, [])
    bad, _ = check_extraction_totals.problems(tmp_path)
    assert any("no recorded check matches" in b for b in bad)


def test_q4_source_check_recorded_result_must_match(tmp_path):
    _totals_tree(tmp_path, ["3", "4"], "7", "7", "7", "yes",
                 q4={"source": "X", "source_file": "data_raw/x.pdf",
                     "needed_columns": "missing_column", "column_check": "pass",
                     "sum_check": "pass", "result": "pass", "note": ""})
    bad, _ = check_extraction_totals.problems(tmp_path)
    assert any("column_check" in b for b in bad)


# ------------------------------------------------------------------ inventory (keyed)

Q3_HEAD = ["state", "year", "indicator", "source_id", "numerator", "denominator", "status"]
Q4_HEAD = ["denominator_set", "contrast", "unit", "a", "b", "n2019", "n2022", "n2023",
           "n2024", "q261_2023", "itr2024_2023", "computable"]
MAN_HEAD = ["file", "url", "bytes", "sha256", "retrieved_utc", "note"]
COL_HEAD = ["column", "canonical", "coarse_unit", "is_total", "value"]
FULL, JANOCT, PLACEBO = (check_inventory.FULL, check_inventory.JANOCT,
                         check_inventory.PLACEBO)


def _col(path, column, values):
    """An extracted table with one column: unit -> value (units 'U1', 'U2' ...)."""
    rows = [{"column": column, "canonical": u, "coarse_unit": u, "is_total": "no",
             "value": v} for u, v in values.items()]
    if path.exists():  # several columns of one table
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f)) + rows
    _csv(path, COL_HEAD, rows)


def _inv_tree(root, inv_rows, q3_rows, q4_rows, online=("https://x.org/p",)):
    d = root / "data"
    _csv(d / "source_manifest.csv", MAN_HEAD, [{"file": "data_raw/x.pdf"}])
    _csv(d / "figures_inventory.csv", INV_HEAD, inv_rows)
    _csv(d / "transcribed" / "online_pages.csv", ["page_key", "url"],
         [{"page_key": "1", "url": u} for u in online])
    _csv(d / "transcribed" / "quality_studies_tables.csv", ["study", "url"], [])
    ex = d / "extracted"
    # two figures of the same unit in the same table family: the trap of value-only matching
    _col(ex / "pq_q1216.csv", "2024_notified", {"U1": "534", "U2": "20"})
    _col(ex / "itr2020_a6_acf.csv", "diagnosed", {"U1": "10", "U2": "561"})
    _col(ex / "itr2020_a6_acf.csv", "screened", {"U1": "5", "U2": "7"})
    # the other Q4 source columns, with the same values as the first
    for name, column in (("pq_q1216.csv", "2025_notified"), ("pq_q1216.csv", "2023_notified"),
                         ("pq_q261.csv", "2024_jan_oct_reported"),
                         ("pq_q261.csv", "2023_reported"),
                         ("pq_q1093.csv", "2025_jan_oct_reported"),
                         ("itr2020_a1_2.csv", "notified_total"),
                         ("itr2023_a1_2.csv", "notified_total"),
                         ("itr2024_a1_2.csv", "notified_total")):
        _col(ex / name, column, {"U1": "534", "U2": "20"})
    _csv(root / "outputs" / "q3_yield.csv", Q3_HEAD, q3_rows)
    _csv(root / "outputs" / "q4_states.csv", Q4_HEAD, q4_rows)


def _good():
    inv = [{"fig_id": "A", "value": "5", "geography": "U1", "source_file": "data_raw/x.pdf"},
           {"fig_id": "B", "value": "6", "geography": "U1", "source_file": "https://x.org/p"}]
    q3 = [{"state": "U1", "year": 2019, "indicator": "nns", "source_id": "ITR2020-A6",
           "numerator": "10", "denominator": "5", "status": "computed"},
          {"state": "U2", "year": 2019, "indicator": "nns", "source_id": "ITR2020-A6",
           "numerator": "", "denominator": "", "status": "not_available"}]
    q4 = [{"denominator_set": "R", "contrast": FULL, "unit": "U1", "a": "534", "b": "534",
           "n2019": "534", "n2022": "534", "n2023": "534", "n2024": "534",
           "computable": "yes"}]
    return inv, q3, q4


def test_inventory_clean_fixture_passes(tmp_path):
    _inv_tree(tmp_path, *_good())
    assert check_inventory.problems(tmp_path)[0] == []


def test_inventory_source_not_in_manifest_is_flagged(tmp_path):
    inv, q3, q4 = _good()
    inv.append({"fig_id": "C", "value": "1", "source_file": "data_raw/other.pdf"})
    _inv_tree(tmp_path, inv, q3, q4)
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and "C" in bad[0] and "manifest" in bad[0]


def test_inventory_online_page_must_be_transcribed(tmp_path):
    inv, q3, q4 = _good()
    inv.append({"fig_id": "D", "value": "1", "source_file": "https://x.org/unrecorded"})
    _inv_tree(tmp_path, inv, q3, q4)
    assert len(check_inventory.problems(tmp_path)[0]) == 1


def test_q3_input_with_no_source_value_is_flagged(tmp_path):
    inv, q3, q4 = _good()
    q3[0]["denominator"] = "99"
    _inv_tree(tmp_path, inv, q3, q4)
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and "denominator" in bad[0]


def test_q3_value_of_another_figure_of_the_state_is_flagged(tmp_path):
    """U2's diagnosed count (561) exists in the table, but U1's numerator is 10."""
    inv, q3, q4 = _good()
    q3[0]["numerator"] = "561"
    _inv_tree(tmp_path, inv, q3, q4)
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and "numerator" in bad[0]


def test_q3_value_from_the_wrong_column_is_flagged(tmp_path):
    """The numerator must be the diagnosed column, not the screened one."""
    inv, q3, q4 = _good()
    q3[0]["numerator"] = "5"
    _inv_tree(tmp_path, inv, q3, q4)
    assert len(check_inventory.problems(tmp_path)[0]) == 1


def test_q4_value_with_no_source_value_is_flagged(tmp_path):
    inv, q3, q4 = _good()
    q4[0]["b"] = "21"
    _inv_tree(tmp_path, inv, q3, q4)
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and " b:" in bad[0]


def test_q4_a_taken_from_another_figure_of_the_same_unit_is_flagged(tmp_path):
    """The 534 -> 561 mutation: 561 is a real figure of the unit (U2's value in another
    table), but a must be the unit's 2024 notified count."""
    inv, q3, q4 = _good()
    q4[0]["a"] = "561"
    _inv_tree(tmp_path, inv, q3, q4)
    _col(tmp_path / "data" / "extracted" / "pq_q1093.csv", "2025_jan_oct_reported",
         {"U1": "561"})  # 561 exists for U1 elsewhere
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and " a:" in bad[0]


def test_q4_trend_value_must_come_from_its_own_year_table(tmp_path):
    inv, q3, q4 = _good()
    q4[0]["n2019"] = "534"      # ITR2020 A1.2 holds 400 for U1 below
    _inv_tree(tmp_path, inv, q3, q4)
    _col(tmp_path / "data" / "extracted" / "itr2020_a1_2.csv", "notified_total", {"U1": "400"})
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and "n2019" in bad[0]


def test_q4_jan_oct_a_comes_from_q261_not_q1216(tmp_path):
    inv, q3, q4 = _good()
    q4[0].update(contrast=JANOCT, a="534", b="534")
    _inv_tree(tmp_path, inv, q3, q4)
    _col(tmp_path / "data" / "extracted" / "pq_q261.csv", "2024_jan_oct_reported",
         {"U1": "445"})
    bad = check_inventory.problems(tmp_path)[0]
    assert any(" a:" in b and "pq_q261.csv" in b for b in bad)


# ------------------------------------------------------------------ derived outputs

Z975 = statistics.NormalDist().inv_cdf(0.975)
Q4_FULL_HEAD = ["denominator_set", "contrast", "unit", "a", "b", "y", "y_poisson_lo",
                "y_poisson_hi", "trend_points_used", "n2019", "n2022", "n2023", "n2024",
                "beta", "x", "E", "w", "computable"]
SUMMARY_HEAD = ["analysis", "denominator_set", "contrast", "n", "t_df", "gamma0",
                "gamma0_model_lo", "gamma0_model_hi", "gamma1", "se_gamma1", "t_0975",
                "gamma1_model_lo", "gamma1_model_hi", "exp_gamma1"]
UNITS = {"U1": (2, 10, 1000, 990, 1010, 1040, 1100, 1120),
         "U2": (3, 10, 500, 520, 530, 550, 640, 600),
         "U3": (5, 10, 800, 805, 790, 810, 860, 880),
         "U4": (7, 10, 300, 330, 345, 360, 380, 420),
         "U5": (10, 10, 2000, 2100, 2150, 2300, 2400, 2350)}  # c, L, n19, n22, n23, n24, a, b


def _f6(v):
    return "" if v is None else f"{v:.6f}"


def _outputs_tree(root):
    ex = root / "data" / "extracted"
    for dset, name in check_outputs.EXPOSURE.items():
        _csv(ex / name, ["unit", "campaign_count", "lgd_count", "computable"],
             [{"unit": u, "campaign_count": v[0], "lgd_count": v[1], "computable": "yes"}
              for u, v in UNITS.items()])
    _csv(ex / "guard_result.csv", ["item", "value"],
         [{"item": "primary contrast", "value": FULL}])
    expo = check_outputs.exposure(root, "R")
    rows, recs = [], {}
    for dset in ("R", "D"):
        for contrast in (FULL, JANOCT, PLACEBO):
            for u, (c, L, n19, n22, n23, n24, a, b) in UNITS.items():
                if contrast == PLACEBO:
                    a, b, n24 = n22, n23, None
                if contrast == JANOCT:
                    a, b = a - 40, b - 30
                r = {"denominator_set": dset, "contrast": contrast, "unit": u, "a": a,
                     "b": b, "n2019": n19, "n2022": n22, "n2023": n23, "n2024": n24 or ""}
                e = check_outputs.recompute_row({k: str(v) for k, v in r.items()}, expo)
                r.update(y=_f6(e["y"]), y_poisson_lo=_f6(e["lo"]), y_poisson_hi=_f6(e["hi"]),
                         trend_points_used=e["used"], beta=_f6(e["beta"]), x=_f6(e["x"]),
                         E=_f6(e["E"]), w=_f6(e["w"]), computable=e["computable"])
                rows.append(r)
                recs.setdefault((dset, contrast), []).append(
                    {"x": e["x"], "E": e["E"], "w": e["w"]})
    _csv(root / "outputs" / "q4_states.csv", Q4_FULL_HEAD, rows)
    summ = []
    for analysis, contrast in check_outputs.MODELS.items():
        for dset in ("R", "D"):
            rs = recs[(dset, contrast)]
            fit = check_outputs.wls([r["E"] for r in rs], [r["x"] for r in rs],
                                    [r["w"] for r in rs])
            row = {"analysis": analysis, "denominator_set": dset, "contrast": contrast,
                   "n": fit["n"], "t_df": fit["df"]}
            row.update({k: _f6(fit[k]) for k in SUMMARY_HEAD[5:]})
            summ.append(row)
    _csv(root / "outputs" / "q4_summary.csv", SUMMARY_HEAD, summ)
    q3 = []
    for ind, x, d in (("yield_diagnosed_per_100000", 47, 1200), ("nns", 47, 1200),
                      ("nns", 0, 953), ("acf_share_of_public_sector_notifications_pct",
                                         20, 400)):
        lo, hi = check_outputs.wilson(x, d)
        if ind == "yield_diagnosed_per_100000":
            v = (1e5 * x / d, 1e5 * lo, 1e5 * hi)
        elif ind == "nns":
            v = (d / x if x else None, 1 / hi, 1 / lo if lo else "unbounded")
        else:
            v = (100 * x / d, 100 * lo, 100 * hi)
        q3.append({"state": "U1", "year": 2019, "indicator": ind, "source_id": "S",
                   "numerator": x, "denominator": d,
                   "value": _f6(v[0]), "lower": _f6(v[1]),
                   "upper": v[2] if v[2] == "unbounded" else _f6(v[2]),
                   "status": "computed" if x else "not_computable"})
    _csv(root / "outputs" / "q3_yield.csv", ["state", "year", "indicator", "source_id",
                                              "numerator", "denominator", "value", "lower",
                                              "upper", "status"], q3)


def _edit(path, fn):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    head = list(rows[0])
    fn(rows)
    _csv(Path(path), head, rows)


def test_outputs_clean_fixture_passes(tmp_path):
    _outputs_tree(tmp_path)
    assert check_outputs.problems(tmp_path)[0] == []


def test_beta_edit_in_q4_states_is_caught(tmp_path):
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q4_states.csv",
          lambda rows: rows[0].update(beta=f"{float(rows[0]['beta']) + 0.01:.6f}"))
    bad = check_outputs.problems(tmp_path)[0]
    assert any("beta is" in b and "U1" in b for b in bad)


def test_gamma1_edit_in_q4_summary_is_caught(tmp_path):
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q4_summary.csv",
          lambda rows: rows[0].update(gamma1=f"{float(rows[0]['gamma1']) + 0.01:.6f}"))
    bad = check_outputs.problems(tmp_path)[0]
    assert len(bad) == 1 and "gamma1 is" in bad[0] and "primary (R)" in bad[0]


def test_placebo_summary_edit_is_caught_under_the_d_denominator(tmp_path):
    _outputs_tree(tmp_path)

    def edit(rows):
        for r in rows:
            if r["analysis"] == "placebo" and r["denominator_set"] == "D":
                r["se_gamma1"] = f"{float(r['se_gamma1']) * 2:.6f}"
    _edit(tmp_path / "outputs" / "q4_summary.csv", edit)
    assert any("placebo (D)" in b for b in check_outputs.problems(tmp_path)[0])


def test_edited_exposure_or_weight_is_caught(tmp_path):
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q4_states.csv",
          lambda rows: rows[1].update(w=f"{float(rows[1]['w']) + 1:.6f}"))
    assert any("w is" in b for b in check_outputs.problems(tmp_path)[0])
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q4_states.csv", lambda rows: rows[1].update(E="0.900000"))
    assert any("E is" in b for b in check_outputs.problems(tmp_path)[0])


def test_q3_value_and_wilson_bound_edits_are_caught(tmp_path):
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q3_yield.csv",
          lambda rows: rows[0].update(value=f"{float(rows[0]['value']) + 1:.6f}"))
    assert any("value is" in b for b in check_outputs.problems(tmp_path)[0])
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q3_yield.csv",
          lambda rows: rows[3].update(upper=f"{float(rows[3]['upper']) + 0.01:.6f}"))
    assert any("upper is" in b for b in check_outputs.problems(tmp_path)[0])
    _outputs_tree(tmp_path)
    _edit(tmp_path / "outputs" / "q3_yield.csv", lambda rows: rows[2].update(upper="5.0"))
    assert any("unbounded" in b for b in check_outputs.problems(tmp_path)[0])


def test_independent_wls_and_t_quantile_agree_with_the_analysis_code():
    """The check's own WLS and t quantile against src/q4_dose_response.py."""
    import random

    from src import q4_dose_response as q4
    rng = random.Random(7)
    E = [rng.random() for _ in range(12)]
    x = [0.3 * e + rng.gauss(0, 0.05) for e in E]
    w = [rng.uniform(1e3, 5e4) for _ in E]
    mine, theirs = check_outputs.wls(E, x, w), q4.wls_fit(E, x, w)
    for a, b in (("gamma0", "gamma0"), ("gamma1", "gamma1"), ("se_gamma1", "se"),
                 ("t_0975", "t"), ("gamma1_model_lo", "lo"), ("gamma1_model_hi", "hi"),
                 ("gamma0_model_lo", "lo0"), ("gamma0_model_hi", "hi0")):
        assert mine[a] == pytest.approx(theirs[b], abs=1e-9)
    assert check_outputs.t_quantile(0.975, 14) == pytest.approx(2.144787, abs=1e-6)
    assert check_outputs.wilson(47, 1200) == pytest.approx(q3_wilson(47, 1200), abs=1e-12)


def q3_wilson(x, n):
    from src import q3_yield
    return q3_yield.wilson(x, n)


# ------------------------------------------------------------------ check_all

def test_check_all_runs_every_check_and_pytest():
    names = [n for n, _ in check_all.STEPS]
    assert names == ["pytest -q", "check_plan_order", "check_deviations",
                     "check_extraction_totals", "check_inventory", "check_outputs",
                     "check_ext_outputs", "check_manuscript_numbers", "check_docx_tie"]


def test_every_check_script_has_main_and_the_repository_root():
    for mod in (check_plan_order, check_deviations, check_extraction_totals,
                check_inventory, check_outputs, check_ext_outputs):
        assert mod.ROOT == Path(__file__).resolve().parents[1]
        assert callable(mod.main)


def test_edit_above_section13_reverted_later_is_still_flagged(repo):
    """Every commit after registration is compared, not only HEAD."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    mid = commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Changed.")}, "edit")
    commit(repo, {"docs/analysis_plan.md": PLAN}, "revert")
    bad = check_plan_order.problems(repo, reg, lgd=None)
    assert len(bad) == 1 and bad[0].startswith(f"commit {mid[:7]}") and "above section 13" in bad[0]


def test_renamed_outcome_file_is_matched_under_both_names(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN, "data/extracted/notes.csv": "a\n1\n"}, "plan")
    git(repo, "mv", "data/extracted/notes.csv", "data/extracted/pq_q9.csv")
    git(repo, "commit", "-m", "rename")
    lgd = commit(repo, {"docs/analysis_plan.md": PLAN + "\n**19 November 2026.** LGD.\n"}, "lgd")
    bad = check_plan_order.problems(repo, reg, lgd=lgd)
    assert len(bad) == 1 and "outcome data" in bad[0]


# ------------------------------------------------------------------ extension outputs

REAL = Path(__file__).resolve().parents[1]
EXT_FILES = ("data/ext/panel.csv", "outputs/q3_yield_summary.csv",
             "outputs/ext/d1_pooled.csv", "outputs/ext/d1_elasticity.csv",
             "outputs/ext/d2_alignment.csv", "outputs/ext/d3.csv",
             "outputs/ext/headline.csv", "outputs/ext/spec_curve.csv")


@pytest.fixture
def ext_tree(tmp_path):
    """A copy of the (small) files the extension check reads, in a temporary tree."""
    for rel in EXT_FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL / rel, dst)
    return tmp_path


def _ext_edit(root, rel, fn):
    p = root / rel
    with open(p, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    head = list(rows[0])
    fn(rows)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, head, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_ext_clean_fixture_passes(ext_tree):
    bad, n = check_ext_outputs.problems(ext_tree)
    assert bad == [] and n["labels"] == 3 and n["pooled"] == 6


def test_mutated_headline_label_fails(ext_tree):
    def flip(rows):
        for r in rows:
            if r["estimate"] == "rho":
                r["label"] = "supported"
    _ext_edit(ext_tree, "outputs/ext/headline.csv", flip)
    bad = check_ext_outputs.problems(ext_tree)[0]
    assert len(bad) == 1 and "headline rho: label printed 'supported'" in bad[0]


def test_headline_labels_follow_the_section8_rule_on_the_grid(ext_tree):
    labels = {r["estimate"]: r["label"] for r in check_ext_outputs.read(
        ext_tree / "outputs" / "ext" / "headline.csv")}
    assert labels == {"epsilon": "supported", "rho": "not established",
                      "theta": "not established"}

    def disagree(rows):  # six non-main epsilon entries move to the other side of the null
        k = 0
        for r in rows:
            if r["estimate"] == "epsilon" and r["main"] == "no" and k < 6:
                r["value"] = "1.5"
                k += 1
    _ext_edit(ext_tree, "outputs/ext/spec_curve.csv", disagree)
    bad = check_ext_outputs.problems(ext_tree)[0]
    assert any("headline epsilon: label printed 'supported'" in b for b in bad)


def test_section8_rule_exact_null_and_noncomputable_do_not_agree():
    f = check_ext_outputs.label_of
    assert f(0.5, 0.1, 0.9, 1.0, [0.5] * 8 + [None] * 2) == ("supported", 8)   # 8/10
    assert f(0.5, 0.1, 0.9, 1.0, [0.5] * 7 + [1.0, None, None]) == ("not established", 7)
    assert f(0.5, 0.1, 1.2, 1.0, [0.5] * 10) == ("not established", 10)        # CI spans


def test_mutated_theta_fails(ext_tree):
    def edit(rows):
        for r in rows:
            if r["analysis"] == "main":
                r["estimate"] = repr(float(r["estimate"]) + 1e-4)
    _ext_edit(ext_tree, "outputs/ext/d3.csv", edit)
    bad = check_ext_outputs.problems(ext_tree)[0]
    assert len(bad) == 1 and "d3 main theta" in bad[0]


def test_mutated_elasticity_rho_and_pooling_fail(ext_tree):
    for rel, key, name, what in (
            ("outputs/ext/d1_elasticity.csv", "estimate", "main", "d1_elasticity main"),
            ("outputs/ext/d2_alignment.csv", "estimate", "main", "d2_alignment main"),
            ("outputs/ext/d1_pooled.csv", "tau2", "2021", "d1_pooled 2021 tau2")):
        def edit(rows, key=key, name=name):
            for r in rows:
                if r["analysis"] == name:
                    r[key] = repr(float(r[key]) + 1e-4)
        _ext_edit(ext_tree, rel, edit)
        assert any(what in b for b in check_ext_outputs.problems(ext_tree)[0]), rel
        shutil.copyfile(REAL / rel, ext_tree / rel)
    assert check_ext_outputs.problems(ext_tree)[0] == []


def test_panel_total_gap_is_tolerated_only_when_flagged_in_2022(ext_tree):
    def edit(rows):
        for r in rows:
            if r["unit"] == "Bihar" and r["year"] == "2023":
                r["diagnosed"] = str(int(r["diagnosed"]) + 1)
    _ext_edit(ext_tree, "data/ext/panel.csv", edit)
    assert any(b.startswith("2023: panel totals")
               for b in check_ext_outputs.problems(ext_tree)[0])
    shutil.copyfile(REAL / "data/ext/panel.csv", ext_tree / "data/ext/panel.csv")

    def unflag(rows):
        for r in rows:
            if r["year"] == "2022":
                r["flags"] = ""
    _ext_edit(ext_tree, "data/ext/panel.csv", unflag)
    assert any(b.startswith("2022: panel totals")
               for b in check_ext_outputs.problems(ext_tree)[0])


# ------------------------------------------------------------------ extension registration order

EXT_PLAN_TEXT = ("# Extension\n\nBefore.\n\n## 10. Deviations\n\n"
                 "**19 November 2026.** None.\n")


def test_ext_clean_history_passes(repo):
    ereg = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT}, "ext plan")
    commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT + "\nA later entry.\n"}, "dev")
    commit(repo, {"src/ext/panel.py": "x = 1\n"}, "panel after registration is allowed")
    commit(repo, {"src/ext/d1_yield.py": "x\n", "src/ext/robustness.py": "x\n",
                  "outputs/ext/headline.csv": "a\n"}, "work")
    assert check_plan_order.ext_problems(repo, ereg) == []


def test_ext_output_before_ext_registration_fails(repo):
    commit(repo, {"outputs/ext/d3.csv": "a\n"}, "ext output first")
    ereg = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT}, "ext plan")
    bad = check_plan_order.ext_problems(repo, ereg)
    assert len(bad) == 1 and "not a descendant" in bad[0]


def test_ext_analysis_modules_before_registration_fail_but_panel_does_not(repo):
    commit(repo, {"src/ext/panel.py": "x\n"}, "panel first is fine")
    for name in ("d1_yield.py", "d2_targeting.py", "d3_additionality.py", "robustness.py"):
        commit(repo, {f"src/ext/{name}": "x\n"}, f"early {name}")
    ereg = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT}, "ext plan")
    assert len(check_plan_order.ext_problems(repo, ereg)) == 4


def test_ext_module_in_the_registration_commit_fails(repo):
    ereg = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT, "src/ext/d2_x.py": "x\n"},
                  "plan + code")
    assert len(check_plan_order.ext_problems(repo, ereg)) == 1


def test_edit_above_section10_of_extension_plan_fails(repo):
    ereg = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT}, "ext plan")
    mid = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT.replace("Before.", "Changed.")},
                 "edit")
    commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT}, "revert")  # reverted: still caught
    bad = check_plan_order.ext_problems(repo, ereg)
    assert len(bad) == 1 and bad[0].startswith(f"commit {mid[:7]}")
    assert "above section 10" in bad[0]


def test_ext_registration_is_read_from_its_json_and_wired_into_problems(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"outputs/ext/d3.csv": "a\n"}, "ext output before its registration")
    ereg = commit(repo, {"docs/extension_plan.md": EXT_PLAN_TEXT}, "ext plan")
    commit(repo, {"docs/registration_event_ext.json": json.dumps({"registered_commit": ereg})},
           "event")
    assert check_plan_order.ext_registered_commit(repo) == ereg
    bad = check_plan_order.problems(repo, reg, lgd=None)
    assert len(bad) == 1 and "extension registration commit" in bad[0]
