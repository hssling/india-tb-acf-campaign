"""Exposure table (analysis plan §9.2, checks E1-E7) and the label rule (E3)."""
from pathlib import Path

import pytest

from src import states
from src.extract import labels

ROOT = Path(__file__).resolve().parents[1]
CTD = ROOT / "data_raw/official/100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf"

campaign = pytest.importorskip("src.extract.campaign")

DNHDD = "Dadra and Nagar Haveli and Daman and Diu"
JKL = "Jammu and Kashmir (incl. Ladakh)"


# ---------------------------------------------------------------- label rule (E3)

def test_label_step1_ignores_case_punctuation_and_ampersand():
    r = labels.resolve("Jammu & Kashmir")
    assert (r.canonical, r.step) == ("Jammu and Kashmir", 1)
    r = labels.resolve("  andaman and nicobar islands. ")
    assert (r.canonical, r.step) == ("Andaman and Nicobar Islands", 1)


def test_label_step2_is_logged_with_evidence():
    r = labels.resolve("DNH & DND")
    assert r.canonical == DNHDD and r.step == 2 and r.evidence
    r = labels.resolve("The Dadra And Nagar Haveli And Daman And Diu")
    assert r.canonical == DNHDD and r.step == 2 and r.evidence


def test_label_unmappable_halts():
    with pytest.raises(labels.UnmappedLabel):
        labels.resolve("Atlantis")
    with pytest.raises(labels.UnmappedLabel):
        labels.resolve("TOTAL")


# ---------------------------------------------------------------- table parsing

LINES = [
    "Following this process, 4 districts have been selected across 3 State/UTs.",
    "State Total District State Total District",
    "Karnataka 2 Goa 1",
    "DNH & DND 1 TOTAL 4",
    "Key strategies",
]


def test_parse_two_blocks_and_total():
    rows, total = campaign.parse_exposure_lines(LINES)
    assert rows == [("Karnataka", 2), ("DNH & DND", 1), ("Goa", 1)]
    assert total == 4


def test_parse_without_total_reports_none():
    rows, total = campaign.parse_exposure_lines(LINES[:3])
    assert total is None and len(rows) == 2


def test_e3_halts_on_unmappable_name():
    with pytest.raises(labels.UnmappedLabel):
        campaign.map_rows([("Karnataka", 2), ("Atlantis", 1)])


# ---------------------------------------------------------------- checks E1-E5

def _table(n_rows=33, total=347):
    """Synthetic table: 33 distinct States with counts summing to `total`."""
    names = [s for s in states.ALL if s not in ("Ladakh",)][:n_rows]
    counts = [10] * n_rows
    counts[0] += total - sum(counts)
    return [(n, n, c) for n, c in zip(names, counts)]


def _lgd(rows, bump=5):
    """LGD counts above every campaign count (so E4 passes, E5 flags none)."""
    lgd = {states.coarsen(s): 50 for s in states.ALL}
    for _, canon, c in rows:
        lgd[states.coarsen(canon)] = c + bump
    return lgd


def _check(res, name):
    return next(c for c in res.checks if c["check"] == name)


def test_printed_total_e1_e2_pass():
    rows = _table()
    res = campaign.check_exposure(rows, 347, _lgd(rows))
    assert _check(res, "E1")["pass"] == "yes"
    assert _check(res, "E2")["pass"] == "yes"
    assert _check(res, "E3")["pass"] == "yes"
    assert not res.rejected


def test_e1_total_not_347_rejects():
    rows = _table(total=346)
    res = campaign.check_exposure(rows, 346, _lgd(rows))
    assert _check(res, "E1")["pass"] == "no"
    assert res.rejected


def test_e2_rows_not_summing_to_total_rejects():
    rows = _table()
    rows[0] = (rows[0][0], rows[0][1], rows[0][2] + 1)
    res = campaign.check_exposure(rows, 347, _lgd(rows))
    assert _check(res, "E2")["pass"] == "no"
    assert res.rejected


def test_e3_row_count_other_than_33_is_reported_not_rejected():
    rows = _table(n_rows=32)
    res = campaign.check_exposure(rows, 347, _lgd(rows))
    assert _check(res, "E3")["pass"] == "no"
    assert not res.rejected


def test_e4_fewer_than_5_below_lgd_rejects():
    rows = _table()
    lgd = _lgd(rows, bump=0)            # every campaign count equals LGD
    for _, canon, c in rows[:4]:
        lgd[states.coarsen(canon)] = c + 1
    res = campaign.check_exposure(rows, 347, lgd)
    assert _check(res, "E4")["pass"] == "no"
    assert res.rejected
    for _, canon, c in rows[4:5]:
        lgd[states.coarsen(canon)] = c + 1
    res = campaign.check_exposure(rows, 347, lgd)
    assert _check(res, "E4")["pass"] == "yes"


def test_e5_flags_and_caps_up_to_3_then_rejects():
    rows = _table()
    lgd = _lgd(rows)
    for _, canon, c in rows[:3]:
        lgd[states.coarsen(canon)] = c - 1
    res = campaign.check_exposure(rows, 347, lgd)
    assert not res.rejected
    flagged = [u for u in res.units if u["flagged_e5"] == "yes"]
    assert len(flagged) == 3
    assert all(u["share"] == "1" and u["capped"] == "yes" for u in flagged)
    _, canon, c = rows[3]
    lgd[states.coarsen(canon)] = c - 1
    res = campaign.check_exposure(rows, 347, lgd)
    assert _check(res, "E5")["pass"] == "no"
    assert res.rejected


def test_equal_counts_are_capped_not_flagged():
    rows = _table()
    lgd = _lgd(rows)
    _, canon, c = rows[0]
    lgd[states.coarsen(canon)] = c
    res = campaign.check_exposure(rows, 347, lgd)
    unit = next(u for u in res.units if u["unit"] == states.coarsen(canon))
    assert (unit["share"], unit["capped"], unit["flagged_e5"]) == ("1", "yes", "no")


def test_units_coarsened_and_absent_states_zero():
    rows = [("Jammu & Kashmir", "Jammu and Kashmir", 3), ("Ladakh", "Ladakh", 1),
            ("Goa", "Goa", 2)]
    lgd = {states.coarsen(s): 10 for s in states.ALL}
    res = campaign.check_exposure(rows, 6, lgd)
    jkl = next(u for u in res.units if u["unit"] == JKL)
    assert jkl["campaign_count"] == 4
    kerala = next(u for u in res.units if u["unit"] == "Kerala")
    assert kerala["campaign_count"] == 0 and kerala["in_table"] == "no"


def test_unit_without_lgd_count_is_not_computable():
    rows = _table()
    lgd = _lgd(rows)
    lgd[states.coarsen(rows[1][1])] = None
    res = campaign.check_exposure(rows, 347, lgd)
    unit = next(u for u in res.units if u["unit"] == states.coarsen(rows[1][1]))
    assert unit["computable"] == "no" and unit["share"] == "" and unit["reason"]


def test_e6_e7_report_only():
    rows = _table()
    res = campaign.check_exposure(rows, 347, _lgd(rows), e6_number=346,
                                  e7=(347, 32))
    assert _check(res, "E6")["pass"] == "no"
    assert _check(res, "E7")["pass"] == "no"
    assert not res.rejected


# ---------------------------------------------------------------- real document

needs_ctd = pytest.mark.skipif(not CTD.exists(), reason="data_raw absent")


@needs_ctd
def test_ctd_table_printed_total():
    rows, total = campaign.read_exposure_table(CTD)
    assert total == 347
    assert sum(c for _, c in rows) == total
    assert len(rows) == 33
