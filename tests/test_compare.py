"""Comparability layer (analysis plan §9.5). Checks the rules, not the analysis results."""
from datetime import date, timedelta

import pytest

from src import compare as cp


def row(unit="X", col="c", start="2024-01-01", end="2024-12-31", as_on="2025-02-01",
        basis="stated", heading="Number of TB cases notified", title="T", source="Ni-kshay",
        doc="a.pdf", answer="2026-02-10", value="10"):
    return dict(coarse_unit=unit, column=col, window_start=start, window_end=end, as_on=as_on,
                as_on_basis=basis, column_heading=heading, table_title=title,
                data_source=source, source_file=doc, answer_date=answer, value=value,
                is_total="no")


def test_window_mismatch_refused():
    ok, why = cp.comparable(row(), row(end="2025-10-31", start="2025-01-01"))
    assert not ok and "window" in why
    # same calendar span in a leap and a non-leap year is the same window
    assert cp.comparable(row(as_on="2025-01-15"),
                         row(start="2025-01-01", end="2025-12-31", as_on="2026-01-15"))[0]


def test_asof_beyond_60_days_refused():
    a = row(doc="a.pdf", as_on="2025-02-01")
    b = row(doc="b.pdf", start="2025-01-01", end="2025-12-31", as_on="2026-03-02")  # 61 days
    ok, why = cp.comparable(a, b)
    assert not ok and "60" in why
    b = row(doc="b.pdf", start="2025-01-01", end="2025-12-31", as_on="2026-03-01")  # 60 days
    assert cp.comparable(a, b)[0]


def test_different_wording_or_source_refused():
    kw = dict(start="2025-01-01", end="2025-12-31", as_on="2026-01-15")
    assert not cp.comparable(row(as_on="2025-01-15"), row(heading="Number of TB cases reported", **kw))[0]
    assert not cp.comparable(row(as_on="2025-01-15"), row(source="HMIS", **kw))[0]
    assert not cp.comparable(row(as_on="2025-01-15"), row(source="", **kw))[0]
    # case, whitespace and "portal" do not matter
    assert cp.comparable(row(as_on="2025-01-15"),
                         row(heading="NUMBER of  TB Cases  notified ", source="Ni-kshay portal", **kw))[0]


def test_single_document_shared_cutoff_accepted():
    end25 = date(2025, 12, 31)
    for days, expect in ((40, True), (70, False)):
        as_on = (end25 + timedelta(days=days)).isoformat()
        a = row(as_on=as_on)
        b = row(start="2025-01-01", end="2025-12-31", as_on=as_on)
        assert cp.comparable(a, b)[0] is expect
    # different documents do not get the shared-cut-off rule
    as_on = (end25 + timedelta(days=40)).isoformat()
    assert not cp.comparable(row(as_on=as_on), row(start="2025-01-01", end="2025-12-31",
                                                   as_on=as_on, doc="b.pdf"))[0]


def test_bounded_cutoff_uses_answer_date():
    a = row(end="2024-10-31", as_on="", basis="bounded", answer="2024-12-13")      # 43 days
    b = row(start="2025-01-01", end="2025-10-31", as_on="", basis="bounded",
            answer="2025-12-09", doc="b.pdf")                                         # 39 days
    assert cp.comparable(a, b)[0]
    b["answer_date"] = "2026-01-05"                                                   # 66 days
    assert not cp.comparable(a, b)[0]


def test_pairs_drop_missing_units_with_reason():
    rows = [row("A", "2024_notified", as_on="2026-01-15", value="5"),
            row("A", "2025_notified", start="2025-01-01", end="2025-12-31",
                as_on="2026-01-15", value="7"),
            row("A", "2024_notified", as_on="2026-01-15", value="1"),  # combined member: summed
            row("B", "2024_notified", as_on="2026-01-15", value="3")]
    pairs, dropped = cp.full_year_pairs(rows)
    assert pairs == {"A": (6, 7)}
    assert dropped == [("B", "missing in 2025_notified")]


def test_full_year_pairs_real_q1216():
    if not (cp.EX / "pq_q1216.csv").exists():
        pytest.skip("pq_q1216.csv absent")
    rows = cp.load_pq("pq_q1216")
    pairs, dropped = cp.full_year_pairs(rows)
    assert len(pairs) == 35 and dropped == []
    assert {r["source_file"] for r in rows} == {"data_raw/pq/AU1216_WFw8li.pdf"}
    assert {r["as_on"] for r in rows} == {"2026-02-06"}
    assert (date(2026, 2, 6) - date(2025, 12, 31)).days == 37
    a = next(r for r in rows if r["column"] == "2024_notified")
    b = next(r for r in rows if r["column"] == "2025_notified")
    assert cp.comparable(a, b) == (True, "")
    # the each-own rule alone would fail for 2024 (13 months): the shared rule applies
    assert not cp._lag_ok(cp.effective_as_on(a), date(2024, 12, 31))


def test_jan_oct_pairs_real_s8_files():
    if not (cp.EX / "pq_q261.csv").exists() or not (cp.EX / "pq_q1093.csv").exists():
        pytest.skip("S8 files absent")
    rows = cp.load_pq("pq_q261") + cp.load_pq("pq_q1093")
    pairs, dropped = cp.jan_oct_pairs(rows)
    assert len(pairs) == 35 and dropped == []
    a = next(r for r in rows if r["column"] == "2024_jan_oct_reported")
    b = next(r for r in rows if r["column"] == "2025_jan_oct_reported")
    # plan 9.5.3: same words, Ni-kshay, same window, bounded cut-offs 43 and 39 days: accepted
    assert cp.comparable(a, b) == (True, "")
    assert (cp.effective_as_on(a) - date(2024, 10, 31)).days == 43
    assert (cp.effective_as_on(b) - date(2025, 10, 31)).days == 39


PAID = "2024 (Jan-Dec): Number of Beneficiaries paid at least once"


def test_title_does_not_spill_into_other_columns():
    t = "State/UT wise Number of TB Case notified and Number of patients paid"
    kw = dict(start="2025-01-01", end="2025-12-31", as_on="2026-01-15", title=t)
    assert not cp.comparable(row(as_on="2025-01-15", heading=PAID, title=t), row(**kw))[0]
    assert cp.quantity_wording(row(heading=PAID, title=t)) != "tb case notified"


def test_case_cases_same_quantity_and_period_only_heading_uses_title():
    kw = dict(start="2025-01-01", end="2025-12-31", as_on="2026-01-15")
    assert cp.comparable(row(as_on="2025-01-15", heading="TB case notified"),
                         row(heading="TB cases notified", **kw))[0]
    a = row(heading="2024 (Jan- Oct)", title="TB cases reported since 2022 to 2024*")
    assert cp.quantity_wording(a) == "tb case reported"


def test_stated_asof_missing_raises_and_asof_before_window_end_refused():
    with pytest.raises(ValueError, match="stated as_on missing"):
        cp.effective_as_on(row(as_on=""))
    a = row(as_on="2024-12-01")  # before the 31 Dec window end
    b = row(start="2025-01-01", end="2025-12-31", as_on="2026-01-15", doc="b.pdf")
    assert not cp.comparable(a, b)[0]


def test_non_integer_value_raises_and_every_member_is_checked():
    rows = [row("A", "2024_notified", as_on="2026-01-15", value="5.5"),
            row("A", "2025_notified", start="2025-01-01", end="2025-12-31",
                as_on="2026-01-15")]
    with pytest.raises(ValueError):
        cp.full_year_pairs(rows)
    good = row("A", "2024_notified", as_on="2026-01-15")
    bad = row("A", "2024_notified", as_on="2026-01-15", source="HMIS")
    y25 = row("A", "2025_notified", start="2025-01-01", end="2025-12-31", as_on="2026-01-15")
    pairs, dropped = cp.full_year_pairs([good, bad, y25])
    assert pairs == {} and dropped[0][0] == "A"


def test_every_q4_pq_source_has_a_data_source():
    expect_stated = {"pq_q1216": True, "pq_q261": True, "pq_q1093": True, "pq_q3467": False}
    for name, stated in expect_stated.items():
        if not (cp.EX / f"{name}.csv").exists():
            pytest.skip("pq file absent")
        rows = cp.load_pq(name)
        assert rows
        assert all(bool(r["data_source"]) is stated for r in rows), name


def test_q3467_refused_as_unstated_source():
    if not (cp.EX / "pq_q3467.csv").exists():
        pytest.skip("pq_q3467.csv absent")
    rows = cp.load_pq("pq_q3467")
    a = next(r for r in rows if r["column"] == "2023_notified")
    b = next(r for r in rows if r["column"] == "2024_notified")
    # the printed headings carry the year ("2023:" / "2024*:"), which would be refused as
    # different wording first; give both the same heading so the source check is reached
    b = dict(b, column_heading=a["column_heading"])
    ok, why = cp.comparable(a, b)
    assert not ok and "unstated source" in why


def test_blank_heading_is_not_period_only():
    assert not cp._period_only("") and not cp._period_only(None or "")
    assert cp._period_only("2024 (Jan- Oct)")
