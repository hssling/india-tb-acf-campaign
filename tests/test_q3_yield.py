"""Task 6: Q3 yield, NNS and ACF share with Wilson intervals (analysis plan §8)."""
from __future__ import annotations

import math

import pytest

from src import q3_yield as q3


def test_wilson_interval_known_values():
    # hand-computed with z = 1.959964: 1 of 10
    lo, hi = q3.wilson(1, 10)
    assert lo == pytest.approx(0.017876, abs=1e-5)
    assert hi == pytest.approx(0.404150, abs=1e-5)
    # 0 of 100: the closed form is [0, z^2 / (n + z^2)]
    lo, hi = q3.wilson(0, 100)
    assert lo == 0.0
    assert hi == pytest.approx(0.036993, abs=1e-5)
    # symmetric at x = n
    lo, hi = q3.wilson(100, 100)
    assert hi == 1.0 and lo == pytest.approx(1 - 0.036993, abs=1e-5)
    # yield: Wilson of diagnosed/screened times 100,000
    y = q3.yield_indicator(1, 10)
    assert y["value"] == pytest.approx(10000.0)
    assert y["lower"] == pytest.approx(1787.6, abs=0.1)
    assert y["upper"] == pytest.approx(40415.0, abs=0.5)


def test_nns_reciprocal_bounds():
    n = q3.nns_indicator(5, 200)
    lo, hi = q3.wilson(5, 200)
    assert n["value"] == pytest.approx(40.0)
    assert n["lower"] == pytest.approx(1 / hi)
    assert n["upper"] == pytest.approx(1 / lo)
    assert n["lower"] < n["value"] < n["upper"]


def test_zero_diagnosed_behaviour():
    y = q3.yield_indicator(0, 500)
    assert y["value"] == 0.0 and y["lower"] == 0.0 and y["upper"] > 0
    n = q3.nns_indicator(0, 500)
    assert n["value"] is None and n["upper"] == math.inf
    assert n["lower"] == pytest.approx(1 / q3.wilson(0, 500)[1])
    rows = q3.indicator_rows(_tab(), {"state": "Goa", "screened": 500, "diagnosed": 0})
    nns = [r for r in rows if r["indicator"] == "nns"][0]
    assert nns["status"] == "not_computable" and nns["value"] == ""
    assert nns["upper"] == "unbounded" and "zero diagnosed" in nns["reason"]
    yld = [r for r in rows if r["indicator"] == q3.YIELD][0]
    assert yld["status"] == "computed" and yld["value"] == "0.0"


def _tab(source_id="T1", year=2022, level=1, pub="2023-03-20", units=("Goa", "Manipur")):
    return {"source_id": source_id, "year": year, "level": level, "pub_date": pub,
            "table": "Annexure 6", "pdf_page": "1", "printed_page": "1",
            "units": tuple(units), "note": ""}


def test_missing_state_listed_not_imputed():
    tab = _tab()
    recs = [{"state": "Goa", "screened": 1000, "diagnosed": 10}]  # Manipur has no row
    rows = q3.table_rows(tab, recs)
    man = [r for r in rows if r["state"] == "Manipur"]
    assert {r["indicator"] for r in man} == {q3.YIELD, "nns"}
    for r in man:
        assert r["status"] == "not_available" and r["value"] == ""
        assert r["lower"] == "" and r["upper"] == ""
        assert "no row" in r["reason"]
    # a printed blank is listed with its own reason, not filled
    rows = q3.table_rows(tab, [{"state": "Goa", "screened": 1000, "diagnosed": None,
                                "reason": "diagnosed printed 'NA'"},
                               {"state": "Manipur", "screened": 5, "diagnosed": 1}])
    goa = [r for r in rows if r["state"] == "Goa"]
    assert all(r["status"] == "not_available" and "NA" in r["reason"] for r in goa)


def test_precedence_picks_level_then_later_publication():
    t_itr = _tab("ITR", level=1, pub="2022-03-24")
    t_gha = _tab("GHA", level=99, pub="2023-09-01")
    rec = {"state": "Goa", "screened": 1000, "diagnosed": 10}
    rows = q3.indicator_rows(t_gha, rec) + q3.indicator_rows(t_itr, rec)
    summ = q3.summarise(rows)
    y = [s for s in summ if s["indicator"] == q3.YIELD][0]
    assert y["chosen_source"] == "ITR" and y["sources_computed"] == "GHA; ITR"
    # tie within a level goes to the later publication
    t_b = _tab("B", level=1, pub="2024-03-19")
    summ = q3.summarise(q3.indicator_rows(t_itr, rec) + q3.indicator_rows(t_b, rec))
    assert [s for s in summ if s["indicator"] == "nns"][0]["chosen_source"] == "B"
    # a chosen table without the figure falls to the next table that gives it
    miss = q3.indicator_rows(t_itr, {"state": "Goa", "screened": 1000, "diagnosed": None,
                                     "reason": "blank"})
    summ = q3.summarise(miss + q3.indicator_rows(t_gha, rec))
    assert [s for s in summ if s["indicator"] == "nns"][0]["chosen_source"] == "GHA"


def test_real_data_national_rows():
    res = q3.run()
    yrs = {(r["year"], r["source_id"]): r for r in res["rows"]
           if r["state"] == "India" and r["indicator"] == q3.YIELD}
    r23 = yrs[("2023", "ITR2024-A6")]
    assert (r23["numerator"], r23["denominator"]) == ("35438", "205331541")
    # every State row of the printed tables is either computed or listed with a reason
    for r in res["rows"]:
        assert r["status"] == "computed" or r["reason"]
