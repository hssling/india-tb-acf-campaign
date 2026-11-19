"""Task 5: Q1 consistency checks (§6) and Q2 discrepancy classes (§7), with the
quality-study reconciliation (§7.5). Synthetic rows test the rules; a few real-data
tests pin results the report relies on."""
from __future__ import annotations

import math
from fractions import Fraction

import pytest

from src import q1_consistency as q1
from src import q2_reconcile as q2


def fig(fid="f", quantity="screened", value="100", printed=None, qualifier="exact",
        unit="persons", definition_class="unspecified", scope="unspecified",
        window_label="", window_start="", window_end="", as_on="", geography="India",
        source_file="doc_a", table_id="", context="", definition="", series_type="period"):
    return {
        "fig_id": fid, "quantity": quantity, "value": value,
        "value_printed": printed if printed is not None else value,
        "qualifier": qualifier, "unit": unit, "definition_class": definition_class,
        "scope": scope, "window_label": window_label, "window_start": window_start,
        "window_end": window_end, "as_on": as_on, "geography": geography,
        "source_file": source_file, "table_id": table_id,
        "context_verbatim": context or f"context of {fid}",
        "definition_verbatim": definition or quantity, "series_type": series_type,
        "as_on_basis": "stated" if as_on else "bounded", "note": "",
    }


# ------------------------------------------------------------- the brief's five tests

def test_cascade_monotonicity_flag():
    rows = [fig("s", "screened", "1000"), fig("p", "presumptive", "50"),
            fig("t", "tested", "60", definition_class="people tested"),
            fig("d", "tb_cases", "5", definition_class="diagnosed")]
    res = q1.cascade_checks(rows)
    by = {(r["_figs"][0], r["_figs"][1]): r["pass"] for r in res}
    assert by[("s", "p")] == "yes"
    assert by[("p", "t")] == "no"          # 60 tested out of 50 presumptive: grows
    assert by[("s", "d")] == "yes"         # non-adjacent steps are compared too
    assert by[("t", "d")] == "yes"
    # tests done never enter (one person may have several tests)
    rows2 = [fig("p", "presumptive", "50"),
             fig("t", "tested", "500", definition_class="tests done")]
    assert [r for r in q1.cascade_checks(rows2) if r["pass"] in ("yes", "no")] == []
    # different window: different cell, nothing compared
    rows3 = [fig("p", "presumptive", "50", window_label="2023"),
             fig("t", "tested", "60", definition_class="people tested")]
    assert [r for r in q1.cascade_checks(rows3) if r["pass"] in ("yes", "no")] == []
    # an unspecified tb_cases figure is not compared with notified/diagnosed steps
    rows4 = [fig("d", "tb_cases", "5", definition_class="diagnosed"),
             fig("u", "tb_cases", "9", definition_class="unspecified")]
    assert [r for r in q1.cascade_checks(rows4) if r["pass"] in ("yes", "no")] == []


def test_percentage_recompute_flag():
    n, d = (Fraction(37), Fraction(37)), (Fraction(1000), Fraction(1000))
    p_ok = q1.interval(fig(value="3.7", printed="3.7%", unit="percent"))
    p_bad = q1.interval(fig(value="4.0", printed="4.0%", unit="percent"))
    assert q1.percentage_ok(p_ok, n, d)
    assert not q1.percentage_ok(p_bad, n, d)
    rows = [fig("pct", "other:pct_diagnosed_among_tested", "3.7", "3.7%", unit="percent",
                context="s1"),
            fig("n", "tb_cases", "37", definition_class="diagnosed", context="s1"),
            fig("d", "tested", "1000", definition_class="people tested", context="s1")]
    assert [r["pass"] for r in q1.percentage_checks(rows)] == ["yes"]
    rows[0] = fig("pct", "other:pct_diagnosed_among_tested", "4.0", "4.0%", unit="percent",
                  context="s1")
    assert [r["pass"] for r in q1.percentage_checks(rows)] == ["no"]


def test_sum_of_parts_tolerance():
    parts = [(Fraction(10),) * 2, (Fraction(20),) * 2, (Fraction(30),) * 2]
    assert q1.sum_of_parts_ok(parts, (Fraction(60),) * 2)
    assert q1.sum_of_parts_ok(parts, (Fraction(61),) * 2)       # |difference| <= 1
    assert q1.sum_of_parts_ok(parts, (Fraction(59),) * 2)
    assert not q1.sum_of_parts_ok(parts, (Fraction(62),) * 2)
    # rounded parts widen the tolerance by their half-units: 1.2 + 3.4 lakh vs 4.7 lakh
    lk = [q1.interval(fig(value="120000", printed="1.2 lakh")),
          q1.interval(fig(value="340000", printed="3.4 lakh"))]
    assert q1.sum_of_parts_ok(lk, q1.interval(fig(value="470000", printed="4.7 lakh")))
    assert not q1.sum_of_parts_ok(lk, q1.interval(fig(value="490000", printed="4.9 lakh")))
    # the column rule on table rows: State rows against the INDIA row
    rows = [fig("a", value="10", geography="Bihar", table_id="T", context="T | col | Bihar"),
            fig("b", value="20", geography="Assam", table_id="T", context="T | col | Assam"),
            fig("t", value="32", geography="India", table_id="T", context="T | col | INDIA")]
    res = q1.sum_checks(rows)
    assert len(res) == 1 and res[0]["pass"] == "no" and "t" in res[0]["_figs"]


def test_decision_order():
    yr = dict(window_start="2023-01-01", window_end="2023-12-31")
    later = dict(window_start="2023-01-01", window_end="2023-12-31", as_on="2026-02-06")
    a = fig("a", "tb_cases", "100", definition_class="notified", source_file="A", **yr)
    b = fig("b", "tb_cases", "200", definition_class="diagnosed", source_file="B", **later)
    # all three of 1, 2, 3 apply: arithmetic first, the others noted
    c = q2.classify(a, b, failed={"a": ["check 3 failed"]})
    assert c["cls"] == "1" and c["others"] == ["2", "3a"]
    # without a failed check: definition before window
    c = q2.classify(a, b, failed={})
    assert c["cls"] == "2" and c["others"] == ["3a"]
    # same definition class: window
    b2 = dict(b, definition_class="notified")
    assert q2.classify(a, b2, failed={})["cls"] == "3a"
    # later cut-off giving the smaller value: 3b
    b3 = dict(b2, value="50", value_printed="50")
    assert q2.classify(a, b3, failed={})["cls"] == "3b"
    # an unspecified class never makes class 2; an unstated window never makes class 3
    a4 = dict(a, definition_class="unspecified", window_start="", window_end="")
    c = q2.classify(a4, b, failed={})
    assert c["cls"] == "4" and c["others"] == []
    # windows not nested and not from the same start: 3a (no direction implied)
    p = fig("p", "screened", "10", source_file="A", window_start="2024-01-01",
            window_end="2024-06-30")
    r = fig("r", "screened", "500", source_file="B", window_start="2024-03-01",
            window_end="2024-12-31")
    assert q2.classify(r, p, failed={})["cls"] == "3a"
    # equal spans with differing fields: 3a
    e1 = fig("e1", "screened", "10", source_file="A", window_start="2024-01-01",
             window_end="2024-10-31", as_on="2024-12-31")
    e2 = fig("e2", "screened", "5", source_file="B", window_start="2024-01-01",
             window_end="2024-12-31")
    assert q2.classify(e1, e2, failed={})["cls"] == "3a"


def test_unexplained_is_a_class_not_an_error():
    a = fig("a", "districts_selected", "347", unit="districts", scope="phase 1",
            window_label="100-day campaign", source_file="A")
    b = fig("b", "districts_selected", "455", unit="districts", scope="phase 1",
            window_label="100-day campaign", source_file="B")
    c = q2.classify(a, b, failed={})
    assert c["cls"] == "4"
    assert q2.CLASS_LABEL["4"] == "unexplained"
    assert "4" in q2.CLASSES                      # a valid result, listed with the others
    assert "error" not in c["rule"].lower() and "error" not in c["evidence"].lower()
    rows, _ = q2.compare([a, b], failed={})
    assert len(rows) == 1 and rows[0]["agree"] == "no" and rows[0]["class"] == "4"
    assert rows[0]["class_label"] == "unexplained"


# ----------------------------------------------------------------- further rules

def test_a21_cascade_one_definition_class_per_step():
    """PGPH: 'screened by chest X-ray' 9,321 is never compared with presumptive 11,357."""
    w = dict(window_start="2023-01-01", window_end="2023-09-30")
    rows = [fig("xray", "screened", "9321", definition_class="screened by chest X-ray", **w),
            fig("all", "screened", "581633", **w),
            fig("p", "presumptive", "11357", **w),
            fig("t", "tested", "7527", **w),
            fig("d", "tb_cases", "117", definition_class="diagnosed", **w)]
    res = q1.cascade_checks(rows)
    run = [r for r in res if r["pass"] in ("yes", "no")]
    assert all("xray" not in r["_figs"] for r in run)
    assert all(r["pass"] == "yes" for r in run)
    assert {tuple(r["_figs"]) for r in run} == {("p", "t"), ("p", "d"), ("t", "d")}
    noted = [r for r in res if r["pass"] == "n/a"]
    assert len(noted) == 1 and "A21" in noted[0]["note"]
    # a step with a single class (even a sub-type) is compared as usual
    rows2 = [fig("xray", "screened", "9321", definition_class="screened by chest X-ray", **w),
             fig("p", "presumptive", "11357", **w)]
    assert [r["pass"] for r in q1.cascade_checks(rows2)] == ["no"]


def test_interval_of_a_figure_rounding_and_qualifiers():
    inf = math.inf
    T = q1.interval_from_text
    assert T("9.02 crore people were screened", "9.02 crore") == (
        Fraction(90150000), Fraction(90250000))
    assert T("of which 1,802 TB cases", "1,802") == (1802, 1802)        # integer count: h = 0
    assert T("stated as 3.7% of tested", "3.7%", "percent") == (
        Fraction("3.65"), Fraction("3.75"))
    assert T("nearly 9 crore were screened", "9 crore") == (85000000, 95000000)
    assert T("about 4.14 lakh inmates", "4.14 lakh") == (413500, 414500)
    assert T("~3 lakh TB cases", "3 lakh") == (250000, 350000)          # "~" = about
    assert T("over 3.5 lakh patients", "3.5 lakh") == (350000, inf)     # at_least: [v, inf)
    assert T("25 crore+ screened", "25 crore") == (250000000, inf)      # "+" = at_least
    assert T("up to 25 crore people", "25 crore") == (0, 250000000)     # at_most: [0, v]
    assert T("3+2 rule", "3") == (3, 3)                                 # "+" before a digit
    # value_printed with symbols and spaces as thousands separators
    assert q1.interval(fig(value="162000", printed="1.62+ Lakh", qualifier="at_least")) == (
        162000, inf)
    assert q1.interval(fig(value="581633", printed="581 633")) == (581633, 581633)
    assert q1.interval(fig(value="2824", printed="2,824", unit="ratio")) == (
        Fraction("2823.5"), Fraction("2824.5"))
    assert q1.interval(fig(value="", printed="12-16%", unit="percent")) is None


def test_wilson_hand_value():
    # 37 of 1000, z = 1.959964: the roots of (1 + z²/n)p² − (2p̂ + z²/n)p + p̂² = 0,
    # solved by hand (an independent route to the §8.2 formula)
    lo, hi = q2.wilson(37, 1000)
    assert lo == pytest.approx(0.026961, abs=2e-6)
    assert hi == pytest.approx(0.050582, abs=2e-6)
    # 0 of 50: lower bound 0, upper 2(z²/2n)/(1 + z²/n)
    lo0, hi0 = q2.wilson(0, 50)
    assert lo0 == 0 and hi0 == pytest.approx(0.071348, abs=2e-6)


def test_exploratory_labelling():
    pq = "data_raw/pq/"
    q1216 = fig("a", "tb_cases", "10", source_file=pq + "AU1216_WFw8li.pdf",
                window_start="2025-01-01", window_end="2025-12-31", as_on="2026-02-06")
    q420 = fig("b", "tb_cases", "11", source_file=pq + "AU420_ulGhhr.pdf",
               window_start="2025-01-01", window_end="2025-12-31", as_on="2026-01-21")
    assert q2.analysis_status(q1216, q420)[0] == "exploratory"
    q1900_24 = fig("c", "tb_cases", "9", source_file=pq + "AU1900_PxKD5V.pdf",
                   window_start="2024-01-01", window_end="2024-12-31")
    q1216_24 = dict(q1216, window_start="2024-01-01", window_end="2024-12-31")
    assert q2.analysis_status(q1216_24, q1900_24)[0] == "exploratory"
    q1900_25 = fig("d", "tb_cases", "9", source_file=pq + "AU1900_PxKD5V.pdf",
                   window_start="2025-01-01", window_end="2025-10-31")
    q1093 = fig("e", "tb_cases", "8", source_file=pq + "AU1093_dH065I.pdf",
                window_start="2025-01-01", window_end="2025-10-31")
    status, reason = q2.analysis_status(q1900_25, q1093)
    assert status == "pre-specified" and "9.5.5" in reason
    assert q2.analysis_status(q1216, q1093)[0] == "pre-specified"
    rows, _ = q2.compare([q1216, q420], failed={})
    assert rows[0]["analysis"] == "exploratory"


# ------------------------------------------------------------- real data, pinned

@pytest.fixture(scope="module")
def real():
    inv = q1.load_inventory()
    checks = q1.run_checks(inv, q1.load_quality())
    rows, info = q2.compare(inv, failed=q1.failures(checks))
    return inv, checks, rows, info


def test_real_q1_known_sum_failures(real):
    _, checks, _, _ = real
    fails = [c for c in checks if c["check"].startswith("3") and c["pass"] == "no"]
    obs = " ".join(c["inputs"] + " " + c["observed"] for c in fails)
    assert "Annexure IV" in obs and "-21" in obs              # v6 Annexure IV, other: quantity
    assert "-6174" in obs and "-1214" in obs and "-51" in obs  # ITR2023 ACF annexure
    assert "gap -9" in obs or "-9" in obs                      # PGPH Elderly presumptive


def test_real_q2_455_vs_347_is_unexplained(real):
    _, _, rows, _ = real
    hit = [r for r in rows if r["quantity"] == "districts_selected"
           and {r["a_value"], r["b_value"]} == {"347", "455"} and r["scope"] == "phase 1"]
    assert hit and all(r["class"] == "4" for r in hit)


def test_real_quality_studies():
    out = {(r["study"], r["indicator"]): r for r in q2.quality_reconciliation(q2.load_quality())}
    assert out[("GHA2023", "C3")]["recomputable"] == "no"
    assert out[("PGPH2025", "C1")]["numerator_n"] == "117"
    assert out[("PGPH2025", "C1")]["denominator_n"] == "7527"
    assert float(out[("PGPH2025", "C4")]["recomputed"]) == pytest.approx(581633 / 117, abs=0.05)


# ------------------------------------- corrected set (§13, 19 November 2026; post hoc)

def test_d1_span_ends_at_window_end_where_printed():
    y23 = fig("a", "tb_cases", "100", source_file="A", window_start="2023-01-01",
              window_end="2023-12-31", as_on="2026-02-06")
    y25 = fig("b", "tb_cases", "90", source_file="B", window_start="2025-01-01",
              window_end="2025-10-31")
    assert q2.related(y23, y25) == ["windows overlap"]            # registered rule
    assert q2.related(y23, y25, corrected=True) == []             # D1: different years
    rows, _ = q2.compare([y23, y25], failed={}, corrected=True)
    assert rows == []
    # as_on still extends a span whose end is blank (a cumulative "since" figure)
    since = fig("c", "screened", "10", source_file="A", window_start="2024-12-07",
                as_on="2025-03-24", series_type="cumulative")
    mid = fig("d", "screened", "20", source_file="B", window_start="2025-02-01",
              window_end="2025-02-28")
    assert q2.related(since, mid, corrected=True) == ["windows overlap"]
    # same window, both cut-offs stated: the later cut-off giving the smaller value is 3b
    q1216 = fig("e", "tb_cases", "100", source_file="A", window_start="2025-01-01",
                window_end="2025-12-31", as_on="2026-02-06")
    q420 = fig("f", "tb_cases", "110", source_file="B", window_start="2025-01-01",
               window_end="2025-12-31", as_on="2026-01-21")
    assert q2.classify(q1216, q420, failed={}, corrected=True)["cls"] == "3b"


def _itr_rows():
    t = "1.2. TB case notification"
    col = "TB patients notified, n(% of achievement against target)"
    common = dict(quantity="tb_cases", definition_class="notified", source_file="ITR",
                  table_id="Annexure 1.2", window_start="2023-01-01", window_end="2023-12-31",
                  geography="Bihar")
    return [fig("pub", value="84049", context=f"{t} | {col}: Public | Bihar", **common),
            fig("pri", value="102925", context=f"{t} | {col}: Private | Bihar", **common),
            fig("tot", value="186974", context=f"{t} | {col}: Total | Bihar", **common)]


def test_d2_sector_parts_not_grouped_but_summed():
    itr = _itr_rows()
    assert q1.sector_keyword(itr[0]) == "public"
    assert q1.sector_keyword(itr[1]) == "private"
    assert q1.sector_keyword(itr[2]) == ""
    # a title naming one sector only is not a split
    gha = fig("g", "tb_cases", "41659", table_id="S2 Annex", definition_class="diagnosed",
              context="S2 Annex: total public notified TB cases and the ACF cases | "
                      "TB ACF cases diagnosed | INDIA")
    assert q1.sector_keyword(gha) == ""
    other = fig("q", "tb_cases", "184706", source_file="Q", definition_class="notified",
                window_start="2023-01-01", window_end="2023-12-31", geography="Bihar")
    reg, _ = q2.compare(itr + [other], failed={})
    assert any("pub" in r["a_fig_ids"] + r["b_fig_ids"] for r in reg)
    cor, info = q2.compare(itr + [other], failed={}, corrected=True)
    assert all("pub" not in r["a_fig_ids"] + r["b_fig_ids"] for r in cor)
    assert all("pri" not in r["a_fig_ids"] + r["b_fig_ids"] for r in cor)
    assert len(cor) == 1                                          # total vs Q only
    assert {s["fig_id"]: s["keyword"] for s in info["sector_excluded"]} == {
        "pub": "public", "pri": "private"}
    c3 = [r for r in q1.run_checks(itr, corrected=True) if r["check"] == q1.CHECK3]
    assert len(c3) == 1 and c3[0]["pass"] == "yes" and {"pub", "pri"} <= set(c3[0]["_figs"])


def test_d3_cascade_within_one_printed_table_or_paragraph():
    w = dict(window_start="2023-01-01", window_end="2023-12-31", source_file="ITR")
    prose = fig("d", "tb_cases", "35438", definition_class="diagnosed", **w)
    prose["page_or_para"] = "PDF page 54; para 2"
    table = fig("n", "tb_cases", "2552257", definition_class="notified", table_id="Annexure 1.2",
                **w)
    table["page_or_para"] = "PDF page 188; Annexure 1.2"
    reg = [r for r in q1.run_checks([prose, table]) if r["check"] == q1.CHECK1]
    assert [r["pass"] for r in reg] == ["no"]                     # registered: one cell
    cor = [r for r in q1.run_checks([prose, table], corrected=True) if r["check"] == q1.CHECK1]
    assert cor == []                                              # D3: two printed cascades
    same = dict(table, fig_id="d2", value="35438", value_printed="35438",
                definition_class="diagnosed")
    cor2 = [r for r in q1.run_checks([same, table], corrected=True) if r["check"] == q1.CHECK1]
    assert [r["pass"] for r in cor2] == ["no"]                    # one table: compared
    # Q2 class 1 follows the corrected check 1
    other = fig("x", "tb_cases", "117", definition_class="diagnosed", source_file="P",
                window_start="2023-01-01", window_end="2023-09-30")
    rows = [prose, table, other]
    f_reg = q1.failures(q1.run_checks(rows))
    f_cor = q1.failures(q1.run_checks(rows, corrected=True))
    c_reg = q2.classify(prose, other, failed=f_reg)["cls"]
    c_cor = q2.classify(prose, other, failed=f_cor, corrected=True)["cls"]
    assert c_reg == "1" and c_cor != "1"


def test_no_other_quantity_in_q1_checks():
    inv = q1.load_inventory()
    other_ids = {r["fig_id"] for r in inv if r["quantity"].startswith("other:")}
    for corrected in (False, True):
        main, desc = q1.split_other(q1.run_checks(inv, q1.load_quality(), corrected=corrected))
        assert desc and all(r.get("_other") for r in desc)
        for r in main:
            assert not other_ids & set(r["_figs"]), r["inputs"][:120]
            assert not r.get("_other")
    import csv as _csv
    for name in ("q1_checks.csv", "q1_checks_corrected.csv"):
        path = q1.ROOT / "outputs" / name
        if path.exists():
            with open(path, encoding="utf-8", newline="") as f:
                for row in _csv.DictReader(f):
                    toks = set(row["inputs"].replace(",", " ").replace(";", " ").split())
                    assert not toks & other_ids, (name, row["inputs"][:120])
