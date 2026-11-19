"""Task 2 (extension): the State x year panel (extension plan section 3)."""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"
pytestmark = pytest.mark.skipif(not EXTRACTED.is_dir(), reason="data/extracted absent")

if EXTRACTED.is_dir():
    from src.ext import panel as P


def _src(name):
    with open(EXTRACTED / f"{name}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sum(name, column, members):
    vals = [r["value"] for r in _src(name)
            if r["is_total"] == "no" and r["column"] == column
            and r["label_printed"] in members]
    assert len(vals) == len(members), (name, column, members, vals)
    return sum(int(v) for v in vals)


def _row(rows, unit, year):
    (r,) = [r for r in rows if r["unit"] == unit and r["year"] == year]
    return r


def test_units_coarsened():
    rows = P.load_panel()
    names = {r["unit"] for r in rows}
    for bad in ("Ladakh", "Daman and Diu", "Dadra and Nagar Haveli", "Jammu and Kashmir"):
        assert bad not in names
    assert "Jammu and Kashmir (incl. Ladakh)" in names
    # merged values equal the sums of the parts in the source CSVs
    r = _row(rows, "Dadra and Nagar Haveli and Daman and Diu", 2018)
    assert r["diagnosed"] == _sum("itr2019_a1_7_acf", "diagnosed",
                                  {"Dadra & Nagar Haveli", "Daman & Diu"})
    r = _row(rows, "Jammu and Kashmir (incl. Ladakh)", 2021)
    assert r["screened"] == _sum("itr2022_a6_acf", "screened", {"Jammu & Kashmir", "Ladakh"})
    r = _row(rows, "Jammu and Kashmir (incl. Ladakh)", 2023)
    assert r["notified_total"] == _sum("itr2024_a1_2", "notified_total",
                                       {"Jammu and Kashmir", "Ladakh"})
    per_year = {y: len({r["unit"] for r in rows if r["year"] == y}) for y in (2018, 2019, 2021, 2022, 2023)}
    assert per_year == {2018: 32, 2019: 32, 2021: 35, 2022: 35, 2023: 35}
    assert {r["year"] for r in rows} == {2018, 2019, 2021, 2022, 2023}


def test_year_sources():
    rows = P.load_panel()
    chk = [(2018, "itr2019_a1_7_acf", "tested"), (2019, "itr2020_a6_acf", "tested"),
           (2021, "itr2022_a6_acf", "tested"), (2022, "itr2023_a6_acf", "symptomatic_examined"),
           (2023, "itr2024_a6_acf", "tested")]
    for year, name, tcol in chk:
        src = {}
        for s in _src(name):
            if s["is_total"] == "no" and s["column"] == "diagnosed" and s["value"] != "":
                src[s["coarse_unit"]] = src.get(s["coarse_unit"], 0) + int(s["value"])
        for u, d in src.items():
            r = _row(rows, u, year)
            if r["diagnosed"] is not None:
                assert r["diagnosed"] == d, (year, u)
        assert {r["tested_definition"] for r in rows if r["year"] == year} == {
            "examined" if year == 2022 else "tested"}
    a = _row(rows, "Andhra Pradesh", 2022)
    (ex,) = [s for s in _src("itr2023_a6_acf") if s["label_printed"] == "Andhra Pradesh"
             and s["column"] == "symptomatic_examined"]
    assert a["tested"] == int(ex["value"])
    # notifications: 2019, 2022, 2023 only; population: 2019 and 2021 only
    assert all((r["notified_total"] is not None) == (r["year"] in (2019, 2022, 2023)) for r in rows)
    assert all((r["est_population"] is not None) == (r["year"] in (2019, 2021)) for r in rows)
    (n,) = [s for s in _src("itr2023_a1_2") if s["label_printed"] == "Bihar"
            and s["column"] == "notified_total"]
    assert _row(rows, "Bihar", 2022)["notified_total"] == int(n["value"])


def test_unbalanced_panel_kept():
    rows = P.load_panel()
    # Ladakh/DNHDD/Telangana-type units absent in 2018-2019 keep their later years
    by_unit = {}
    for r in rows:
        by_unit.setdefault(r["unit"], set()).add(r["year"])
    assert any(len(ys) < 5 for ys in by_unit.values())
    assert all(ys for ys in by_unit.values())
    # a unit with a missing cell in one year keeps its other years
    assert by_unit["Lakshadweep"] == {2018, 2019, 2021, 2022, 2023}
    assert by_unit["Puducherry"] == {2018, 2019, 2021, 2022, 2023}


def test_zero_and_na_listed():
    ex = P.exclusions()
    rows = P.load_panel()
    keyed = {(e["unit"], e["year"], e["field"]): e["reason"] for e in ex}
    for u in ("Andaman and Nicobar Islands", "Goa", "Lakshadweep"):
        assert keyed[(u, 2023, "diagnosed")]
        assert _row(rows, u, 2023)["diagnosed"] == 0
    assert keyed[("Manipur", 2023, "diagnosed")]
    assert _row(rows, "Manipur", 2023)["diagnosed"] is None
    assert _row(rows, "Manipur", 2023)["tested"] == 0
    assert all(e["reason"] for e in ex)
    assert keyed[("Lakshadweep", 2019, "screened")]
    assert keyed[("Puducherry", 2022, "screened")]
    assert keyed[("Puducherry", 2018, "diagnosed")]
    assert _row(rows, "Lakshadweep", 2019)["screened"] == 0


def test_national_totals():
    rows = P.load_panel()
    with open(ROOT / "outputs" / "q3_yield_summary.csv", encoding="utf-8", newline="") as f:
        nat = {int(r["year"]): r for r in csv.DictReader(f)
               if r["state"] == "India" and r["indicator"] == "nns"}
    for year in (2018, 2019, 2021, 2022, 2023):
        yr = [r for r in rows if r["year"] == year]
        S = sum(r["screened"] for r in yr if r["screened"] is not None)
        D = sum(r["diagnosed"] for r in yr if r["diagnosed"] is not None)
        nS, nD = int(nat[year]["denominator"]), int(nat[year]["numerator"])
        if year == 2022:
            assert any("itr2023_states_not_india" in r["flags"] for r in yr)
            assert abs(S - nS) / nS < 0.05 and abs(D - nD) / nD < 0.05
        else:
            assert (S, D) == (nS, nD), (year, S, nS, D, nD)
