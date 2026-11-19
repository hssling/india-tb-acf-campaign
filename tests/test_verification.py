"""Unit tests of the verification checks, on temporary fixtures (never the real repository)."""
import csv
import json
import subprocess
from pathlib import Path

import pytest

from verification import (check_all, check_deviations, check_extraction_totals,
                          check_inventory, check_plan_order)

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
    _tree(tmp_path, LOGGED, {"q2_discrepancies.csv": "RSQ420.p003.x,exploratory\n"})
    assert check_deviations.problems(tmp_path)[0] == []


def test_exploratory_line_naming_an_unlogged_question_is_flagged(tmp_path):
    _tree(tmp_path, LOGGED, {"q2_discrepancies.csv": "RSQ1093.p002.x,exploratory\n"})
    assert len(check_deviations.problems(tmp_path)[0]) == 1


def test_exploratory_without_any_entry_is_flagged_even_for_a_logged_question(tmp_path):
    _tree(tmp_path, PLAN, {"q2_discrepancies.csv": "RSQ420.p003.x,exploratory\n"})
    assert len(check_deviations.problems(tmp_path)[0]) == 1


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


# ------------------------------------------------------------------ inventory

Q3_HEAD = ["state", "year", "indicator", "source_id", "numerator", "denominator", "status"]
Q4_HEAD = ["denominator_set", "contrast", "unit", "a", "b", "n2019", "n2022", "n2023",
           "n2024", "q261_2023", "itr2024_2023"]
MAN_HEAD = ["file", "url", "bytes", "sha256", "retrieved_utc", "note"]


def _inv_tree(root, inv_rows, q3_rows, q4_rows, online=("https://x.org/p",)):
    d = root / "data"
    _csv(d / "source_manifest.csv", MAN_HEAD, [{"file": "data_raw/x.pdf"}])
    _csv(d / "figures_inventory.csv", INV_HEAD, inv_rows)
    _csv(d / "transcribed" / "online_pages.csv", ["page_key", "url"],
         [{"page_key": "1", "url": u} for u in online])
    _csv(d / "transcribed" / "quality_studies_tables.csv", ["study", "url"], [])
    _csv(d / "extracted" / "pq_q1.csv", EXTRACT_HEAD,
         _extracted_rows(["10", "20"], "30", col="2024_notified"))
    _csv(root / "outputs" / "q3_yield.csv", Q3_HEAD, q3_rows)
    _csv(root / "outputs" / "q4_states.csv", Q4_HEAD, q4_rows)


def _good():
    inv = [{"fig_id": "A", "value": "5", "geography": "S0", "source_file": "data_raw/x.pdf"},
           {"fig_id": "B", "value": "6", "geography": "S0", "source_file": "https://x.org/p"}]
    q3 = [{"state": "S0", "year": 2024, "indicator": "nns", "source_id": "X",
           "numerator": "10", "denominator": "5", "status": "computed"},
          {"state": "S1", "year": 2024, "indicator": "nns", "source_id": "X",
           "numerator": "", "denominator": "", "status": "not_available"}]
    q4 = [{"denominator_set": "R", "contrast": "c", "unit": "S1", "a": "20", "b": "20",
           "n2024": "20"}]
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


def test_q3_input_without_a_source_value_is_flagged(tmp_path):
    inv, q3, q4 = _good()
    q3[0]["denominator"] = "99"
    _inv_tree(tmp_path, inv, q3, q4)
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and "denominator" in bad[0]


def test_q4_value_without_a_source_value_is_flagged(tmp_path):
    inv, q3, q4 = _good()
    q4[0]["b"] = "21"
    _inv_tree(tmp_path, inv, q3, q4)
    bad = check_inventory.problems(tmp_path)[0]
    assert len(bad) == 1 and "b=21" in bad[0]


# ------------------------------------------------------------------ check_all

def test_check_all_runs_every_check_and_pytest():
    names = [n for n, _ in check_all.STEPS]
    assert names == ["pytest -q", "check_plan_order", "check_deviations",
                     "check_extraction_totals", "check_inventory"]


def test_every_check_script_runs_in_isolated_mode():
    """Each script has a main(root) entry and the repository root as its default."""
    for mod in (check_plan_order, check_deviations, check_extraction_totals, check_inventory):
        assert mod.ROOT == Path(__file__).resolve().parents[1]
        assert callable(mod.main)
