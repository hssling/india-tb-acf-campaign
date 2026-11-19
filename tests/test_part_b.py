"""Part B of Task 3: parliamentary answers and India TB Reports (analysis plan §3, §5,
§8.4, §9.4-§9.6). Printed-total checks per extractor, the §9.6 extraction checks of the
Q4 source tables, inventory provenance and window fields, and the source-choice record.
Nothing here compares sources or computes a Q result."""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"
RAW_PQ = ROOT / "data_raw/pq"

from src import source_checks as sc  # noqa: E402


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------- §9.6 extraction checks (unit level)

def test_q4_source_extraction_checks():
    # rows that differ from the printed total by 2 fail; by 1 pass
    two = sc.q4_extraction_check("T", {"n": [10, 20, 32]}, {"n": 60}, ("n",))
    one = sc.q4_extraction_check("T", {"n": [10, 20, 31]}, {"n": 60}, ("n",))
    assert two["result"] == "fail" and two["sum_check"] == "fail"
    assert one["result"] == "pass" and one["sum_check"] == "pass"
    # a missing or unreadable needed column fails
    for cols in ({}, {"n": None}, {"n": []}):
        r = sc.q4_extraction_check("T", cols, {"n": None}, ("n",))
        assert r["result"] == "fail" and r["column_check"] == "fail"
        assert "not readable" in r["note"]
    # no printed total: the sum check is skipped, and the record says so
    r = sc.q4_extraction_check("T", {"n": [1, 2, 3]}, {"n": None}, ("n",))
    assert r["result"] == "pass"
    assert r["sum_check"].startswith("not applied")
    assert sc.NO_TOTAL in r["note"]
    # a failed trend source leaves its year missing for every State, no substitute
    ok = {s: "pass" for s in (sc.Q1216, sc.Q3467, sc.ITR2020, sc.ITR2023, sc.ITR2024,
                              sc.LS261, sc.Q1093)}
    t = sc.trend_points(ok | {sc.ITR2020: "fail"}, fallback=False)
    assert t[2019]["source"] == sc.ITR2020
    assert t[2019]["status"].startswith("missing for every State")
    assert "no substitute" in t[2019]["status"]
    assert all(t[y]["status"] == "in use" for y in (2022, 2023, 2024))
    t = sc.trend_points(ok | {sc.Q3467: "fail"}, fallback=True)
    assert t[2024]["source"] == sc.Q3467 and t[2024]["status"].startswith("missing")
    assert t[2023]["source"] == sc.ITR2024 and t[2023]["status"] == "in use"
    # a failed outcome table makes its contrast not computable
    c = sc.contrast_status(ok | {sc.Q1093: "fail"})
    assert c["January-October 2025 vs 2024 (S8)"].startswith("not computable")
    assert c["full-year 2025 vs 2024"] == "computable"
    c = sc.contrast_status(ok | {sc.Q1216: "fail"})
    assert c["full-year 2025 vs 2024"].startswith("not computable")


def test_blank_state_cell_is_missing_not_failure():
    """A blank State cell: that State is missing and listed; the table does not fail
    (§9.6; §10.4). The sum check runs over the printed values."""
    r = sc.q4_extraction_check("T", {"n": {"Goa": 10, "Delhi": None, "Assam": 20}},
                               {"n": 30}, ("n",))
    assert r["result"] == "pass" and r["column_check"] == "pass"
    assert r["sum_check"] == "pass"
    assert "Delhi" in r["note"] and "missing" in r["note"]
    r = sc.q4_extraction_check("T", {"n": [10, None, 20]}, {"n": None}, ("n",))
    assert r["result"] == "pass" and "missing" in r["note"]


@pytest.mark.skipif(not RAW_PQ.exists(), reason="data_raw absent")
def test_campaign_main_keeps_other_extractors_total_checks(tmp_path, monkeypatch):
    """A non-campaign row of table_total_checks.csv survives a campaign main() run."""
    from src.extract import campaign
    monkeypatch.setattr(campaign, "EXTRACTED", tmp_path)
    monkeypatch.setattr(campaign, "INVENTORY", tmp_path / "figures_inventory.csv")
    monkeypatch.setattr(campaign, "SCOPE_DECISIONS",
                        tmp_path / "inventory_scope_decisions.csv")
    fields = ["table", "source_file", "page", "rows", "sum_of_rows", "printed_total",
              "difference", "pass", "note"]
    other = {"table": "RS Unstarred Q. 1216, Annexure: test row",
             "source_file": "data_raw/pq/AU1216_WFw8li.pdf", "page": "2", "rows": "36",
             "sum_of_rows": "1", "printed_total": "", "difference": "", "pass": "n/a",
             "note": "kept"}
    with open(tmp_path / "table_total_checks.csv", "w", newline="\n",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerow(other)
    campaign.main()
    rows = _read(tmp_path / "table_total_checks.csv")
    assert other in rows
    assert any(r["source_file"] == campaign.CTD_FILE for r in rows)


def test_q1216_failure_counts_as_failed_guard():
    ok = {s: "pass" for s in (sc.Q1216, sc.Q3467, sc.ITR2020, sc.ITR2023, sc.ITR2024,
                              sc.LS261, sc.Q1093)}
    cons = {c["item"]: c["outcome"] for c in sc.consequences(ok | {sc.Q1216: "fail"})}
    assert cons["guard (§9.5.2)"].startswith("failed")
    assert "role primary" in cons["contrast: January-October 2025 vs 2024 (S8)"]
    assert cons["trend point 2023"].startswith(sc.ITR2024)
    assert cons["trend point 2024"].startswith(sc.Q3467)
    cons = {c["item"]: c["outcome"] for c in sc.consequences(ok | {sc.Q3467: "fail"})}
    assert cons["guard (§9.5.2)"].startswith("cannot be applied")
    assert "role primary" in cons["contrast: full-year 2025 vs 2024"]


def test_source_checks_import_without_pdf_libraries():
    import subprocess
    import sys
    code = ("import sys; sys.path.insert(0, '.'); sys.modules['pdfplumber'] = None; "
            "import src.source_checks, src.inventory_rules, src.states")
    r = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ------------------------------------------------- extracted tables and their checks

def _checks():
    return _read(EXTRACTED / "table_total_checks.csv")


def test_pq_printed_total_checks():
    from src.extract import pq
    checks = {c["table"]: c for c in _checks()}
    for spec in pq.TABLES:
        rows = _read(EXTRACTED / spec.csv_name)
        for col in spec.columns:
            name = spec.check_name(col)
            assert name in checks, name
            c = checks[name]
            vals = [int(r["value"]) for r in rows
                    if r["column"] == col.key and r["is_total"] == "no"]
            assert len(vals) == spec.n_rows, (name, len(vals))
            assert int(c["sum_of_rows"]) == sum(vals)
            # no parliamentary table prints a total row
            assert c["printed_total"] == "" and c["pass"] == "n/a"
            assert c["note"].startswith(sc.NO_TOTAL)


def test_itr_printed_total_checks():
    from src.extract import itr
    checks = {c["table"]: c for c in _checks()}
    for spec in itr.TABLES:
        rows = _read(EXTRACTED / spec.csv_name)
        for col in spec.count_columns():
            name = spec.check_name(col)
            assert name in checks, name
            c = checks[name]
            vals = [int(r["value"]) for r in rows if r["column"] == col.key
                    and r["is_total"] == "no" and r["value"] != ""]
            tot = [r["value"] for r in rows if r["column"] == col.key
                   and r["is_total"] == "yes"]
            assert int(c["sum_of_rows"]) == sum(vals), name
            assert c["printed_total"] == tot[0], name
            d = sum(vals) - int(tot[0])
            assert int(c["difference"]) == d
            assert c["pass"] == ("yes" if abs(d) <= 1 else "no"), name


def test_extracted_rows_carry_provenance_and_windows():
    from src.extract import itr, pq
    from src import states
    for spec in list(pq.TABLES) + list(itr.TABLES):
        for r in _read(EXTRACTED / spec.csv_name):
            for k in ("source_file", "pdf_page", "table_id", "window_start",
                      "window_end", "as_on", "as_on_basis", "label_printed"):
                assert k in r
            assert r["source_file"] and r["pdf_page"] and r["table_id"]
            assert r["as_on_basis"] in ("stated", "bounded", "window_end")
            if r["is_total"] == "no" and r["canonical"]:
                assert states.canonical(r["canonical"]) == r["canonical"]
                assert r["coarse_unit"] == states.coarsen(r["canonical"])


def test_q4_sources_have_their_extraction_check():
    rows = _read(EXTRACTED / "q4_source_checks.csv")
    got = {r["source"] for r in rows}
    assert got == {sc.Q1216, sc.Q3467, sc.ITR2020, sc.ITR2023, sc.ITR2024, sc.LS261,
                   sc.Q1093}
    for r in rows:
        assert r["result"] in ("pass", "fail")
        assert r["recheck_954"], r["source"]


# ------------------------------------------------- inventory rows of Part B

def _own_rows():
    from src.extract import itr, pq
    own = pq.OWN_FILES | itr.OWN_FILES
    return [r for r in _read(INVENTORY) if r["source_file"] in own]


def test_inventory_rows_sourced():
    rows = _own_rows()
    assert rows
    for r in rows:
        assert r["source_file"].strip() and r["page_or_para"].strip(), r["fig_id"]
        assert r["source_url"].strip() and r["value_printed"].strip(), r["fig_id"]
        assert r["context_verbatim"].strip(), r["fig_id"]


def test_window_fields_present():
    for r in _own_rows():
        for k in ("window_label", "window_start", "window_end", "as_on", "as_on_basis",
                  "series_type"):
            assert k in r
        assert r["as_on_basis"] in ("stated", "bounded", "window_end"), r["fig_id"]
        if r["as_on_basis"] == "stated":
            assert r["as_on"]
        if r["as_on_basis"] == "window_end":
            assert r["window_end"] and not r["as_on"]
    # every parliamentary State count states its window (column heading) and basis
    from src.extract import pq
    for r in _own_rows():
        if r["source_file"] in pq.OWN_FILES and r["quantity"] == "tb_cases":
            assert r["window_start"] and r["window_end"], r["fig_id"]


def test_part_b_inventory_context_and_classes():
    from src import inventory_rules as R
    for r in _own_rows():
        ctx = r["context_verbatim"]
        if "table cell" not in r["note"]:
            R.find_figure(ctx, r["value_printed"])
        assert R.scope(ctx)[0] == r["scope"], r["fig_id"]
        if r["quantity"] in ("screened", "tested", "tb_cases"):
            assert R.definition_class(r["quantity"], r["definition_verbatim"])[0] \
                == r["definition_class"], r["fig_id"]


@pytest.mark.skipif(not RAW_PQ.exists(), reason="data_raw absent")
def test_part_b_inventory_rebuilds_identically_from_sources():
    from src.extract import itr, pq
    for mod in (pq, itr):
        rows, prov = mod.build_inventory()
        assert all(p["method"] in ("text", "text (loose)", "page image") for p in prov)
        on_disk = [r for r in _read(INVENTORY) if r["source_file"] in mod.OWN_FILES]
        assert [{k: str(v) for k, v in r.items()} for r in rows] == on_disk


# ------------------------------------------------- source choices (§5.4)

def test_source_choices_record():
    from src.extract import source_choices as S
    rows = S.build()
    cols = set(rows[0])
    for c in ("decision_id", "topic", "source_file", "locator", "decision", "rule",
              "evidence", "date"):
        assert c in cols
    ids = [r["decision_id"] for r in rows]
    assert len(ids) == len(set(ids))
    topics = {r["topic"] for r in rows}
    for t in ("exposure table", "LGD denominator", "label rule", "printed totals",
              "named list", "inventory scope", "quality studies",
              "Q4 extraction checks", "re-check at extraction (§9.5.4)",
              "Q4 consequences", "unit coarsening (§9.4)", "Q3 tables (§8.4)",
              "outcome tables (§9.5)", "trend sources (§9.6)"):
        assert t in topics, t
    for r in rows:
        assert r["decision"].strip() and r["rule"].strip(), r["decision_id"]
    path = ROOT / "data/source_choices.csv"
    if path.exists():
        assert _read(path) == [{k: str(v) for k, v in r.items()} for r in rows]
