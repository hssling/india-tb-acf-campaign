"""Q3: ACF yield, number needed to screen and ACF share, with Wilson intervals
(analysis plan §8).

Indicators (§8.1), computed only where one published table gives the numerator and the
denominator:

- yield = 100,000 x diagnosed / screened (the table's 'diagnosed' column);
- NNS = screened / diagnosed;
- ACF share of public-sector notifications = TB patients found through ACF / public-sector
  TB notifications, from one table (GHA S2 only).

Intervals (§8.2): Wilson score interval with z = NormalDist().inv_cdf(0.975). Yield: the
Wilson interval of diagnosed/screened x 100,000. NNS: (1/upper, 1/lower) of the same
bounds. Zero diagnosed: yield 0 with its Wilson interval; NNS not computable, upper
bound 'unbounded'. No imputation (§8.3): a State without a printed numerator and
denominator is listed as not available, with the reason. Every table is computed and
reported (§8.4); the summary file takes one table per State, year and indicator by the
precedence of §8.4.

Writes outputs/q3_yield.csv and outputs/q3_yield_summary.csv. Standard library only.
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import math
from statistics import NormalDist

from src import states

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data/extracted"
OUT = ROOT / "outputs/q3_yield.csv"
OUT_SUMMARY = ROOT / "outputs/q3_yield_summary.csv"

Z = NormalDist().inv_cdf(0.975)
YIELD = "yield_diagnosed_per_100000"
NNS = "nns"
SHARE = "acf_share_of_public_sector_notifications_pct"

COLUMNS = ["state", "year", "indicator", "source_id", "source_table", "pdf_page",
           "printed_page", "numerator", "denominator", "value", "lower", "upper", "unit",
           "status", "reason", "note"]
SUMMARY_COLUMNS = ["state", "year", "indicator", "chosen_source", "precedence_level",
                   "sources_computed", "numerator", "denominator", "value", "lower",
                   "upper", "unit", "status", "reason"]

UNITS = {YIELD: "per 100,000 screened", NNS: "persons screened per person diagnosed",
         SHARE: "percent"}


# ------------------------------------------------------------------ the arithmetic

def wilson(x: int, n: int) -> tuple[float, float]:
    """Wilson score interval of x of n, as proportions (§8.2)."""
    if n <= 0 or x < 0 or x > n:
        raise ValueError(f"Wilson interval needs 0 <= x <= n, n > 0 (got {x} of {n})")
    p = x / n
    d = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / d
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    lo, hi = centre - half, centre + half
    # the bounds at the ends are exact: x = 0 gives 0, x = n gives 1
    return (0.0 if x == 0 else max(0.0, lo)), (1.0 if x == n else min(1.0, hi))


def yield_indicator(diagnosed: int, screened: int) -> dict:
    lo, hi = wilson(diagnosed, screened)
    return {"value": 100000 * diagnosed / screened, "lower": 100000 * lo,
            "upper": 100000 * hi}


def nns_indicator(diagnosed: int, screened: int) -> dict:
    """Reciprocal bounds (1/upper, 1/lower); zero diagnosed gives no value and an
    unbounded upper bound."""
    lo, hi = wilson(diagnosed, screened)
    return {"value": None if diagnosed == 0 else screened / diagnosed,
            "lower": 1 / hi, "upper": math.inf if lo == 0 else 1 / lo}


def share_indicator(acf: int, notified: int) -> dict:
    lo, hi = wilson(acf, notified)
    return {"value": 100 * acf / notified, "lower": 100 * lo, "upper": 100 * hi}


# ------------------------------------------------------------------ result rows

def _f(v) -> str:
    return "" if v is None else repr(round(float(v), 6))


def _i(v) -> str:
    return "" if v is None else str(int(v))


def _row(tab, state, indicator, rec, num, den, res=None, status="computed", reason=""):
    res = res or {}
    upper = res.get("upper")
    return {
        "state": state, "year": str(tab["year"]), "indicator": indicator,
        "source_id": tab["source_id"], "source_table": tab["table"],
        "pdf_page": rec.get("pdf_page", tab["pdf_page"]),
        "printed_page": rec.get("printed_page", tab["printed_page"]),
        "numerator": _i(num), "denominator": _i(den), "value": _f(res.get("value")),
        "lower": _f(res.get("lower")),
        "upper": "unbounded" if upper == math.inf else _f(upper),
        "unit": UNITS[indicator], "status": status, "reason": reason,
        "note": "; ".join(x for x in (tab.get("note", ""), rec.get("note", "")) if x),
        "_level": str(tab["level"]), "_pub": tab["pub_date"],
    }


def _na(tab, state, indicators, rec, num, den, reason):
    return [_row(tab, state, i, rec, num, den, status="not_available", reason=reason)
            for i in indicators]


def _unavailable_reason(rec, num, den, num_name, den_name):
    """None when both figures are usable, else why not (§8.3)."""
    if num is None or den is None:
        return rec.get("reason") or f"{num_name} or {den_name} not printed"
    if den == 0:
        return f"{den_name} is zero"
    if num > den:
        return f"{num_name} ({num}) exceeds {den_name} ({den})"
    return None


def indicator_rows(tab, rec) -> list[dict]:
    """Yield and NNS for one State record {state, screened, diagnosed, ...}."""
    s, d, state = rec.get("screened"), rec.get("diagnosed"), rec["state"]
    why = _unavailable_reason(rec, d, s, "diagnosed", "screened")
    if why:
        return _na(tab, state, (YIELD, NNS), rec, d, s, why)
    out = [_row(tab, state, YIELD, rec, d, s, yield_indicator(d, s))]
    if d == 0:
        out.append(_row(tab, state, NNS, rec, d, s, nns_indicator(d, s),
                        status="not_computable",
                        reason="zero diagnosed: NNS not computable, upper bound unbounded"))
    else:
        out.append(_row(tab, state, NNS, rec, d, s, nns_indicator(d, s)))
    return out


def share_rows(tab, rec) -> list[dict]:
    """ACF share of public-sector notifications for a record {state, acf, notified, ...}."""
    a, n, state = rec.get("acf"), rec.get("notified"), rec["state"]
    why = _unavailable_reason(rec, a, n, "ACF diagnosed", "notified")
    if why:
        return _na(tab, state, (SHARE,), rec, a, n, why)
    return [_row(tab, state, SHARE, rec, a, n, share_indicator(a, n))]


def table_rows(tab, recs, kind="yield") -> list[dict]:
    """All rows of a table: its records, and every expected State/UT it has no row for."""
    make = indicator_rows if kind == "yield" else share_rows
    inds = (YIELD, NNS) if kind == "yield" else (SHARE,)
    rows, seen = [], set()
    for rec in recs:
        seen.add(rec["state"])
        rows += make(tab, rec)
    for u in tab["units"]:
        if u not in seen:
            rows += _na(tab, u, inds, {}, None, None,
                        "no row for this State in the published table")
    return rows


# ------------------------------------------------------------------ summary (§8.4)

def _rank(r):
    # lower is better: the table's precedence level, then the later publication
    return (int(r["_level"]), tuple(-ord(c) for c in r["_pub"]))


def summarise(rows) -> list[dict]:
    """One row per State, year and indicator: the table by the §8.4 precedence among the
    tables that give the numerator and the denominator."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["state"], r["year"], r["indicator"]), []).append(r)
    out = []
    for (state, year, ind), rs in groups.items():
        gives = [r for r in rs if r["status"] != "not_available"]
        best = min(gives or rs, key=_rank)
        reason = best["reason"] if gives else "; ".join(
            sorted({f"{r['source_id']}: {r['reason']}" for r in rs if r["reason"]}))
        out.append({
            "state": state, "year": year, "indicator": ind,
            "chosen_source": best["source_id"], "precedence_level": best["_level"],
            "sources_computed": "; ".join(sorted(r["source_id"] for r in gives)),
            "numerator": best["numerator"], "denominator": best["denominator"],
            "value": best["value"], "lower": best["lower"], "upper": best["upper"],
            "unit": best["unit"], "status": best["status"], "reason": reason})
    return out


# ------------------------------------------------------------------ tables and loading

ITR_NOTE_2022 = ("the State rows do not sum to the printed India row in any column "
                 "(printed-total checks TOT-012, TOT-013, TOT-014; differences of 6,174 "
                 "screened, 1,214 examined, 51 diagnosed); each State computed per row "
                 "as printed")

# (source_id, file, data year, note). Every India TB Report edition is §8.4 level 1 for
# the year it reports; the quality study is none of the five levels (Q3T-2021-GHA).
ITR_TABLES = [
    ("ITR2019-A1.7", "itr2019_a1_7_acf.csv", 2018, ""),
    ("ITR2020-A6", "itr2020_a6_acf.csv", 2019, ""),
    ("ITR2022-A6", "itr2022_a6_acf.csv", 2021, ""),
    ("ITR2023-A6", "itr2023_a6_acf.csv", 2022, ITR_NOTE_2022),
    ("ITR2024-A6", "itr2024_a6_acf.csv", 2023, ""),
]
LEVEL_ITR, LEVEL_OTHER = 1, 99
NO_TABLE_YEARS = {
    2020: "no published State ACF table for data year 2020 among the Q3 tables read",
    2024: "no published State ACF table for data year 2024 among the Q3 tables read",
}


def _int(s):
    return int(s) if s not in ("", None) else None


def _read(name):
    with open(EXTRACTED / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_itr(source_id, file, year, note):
    raw = _read(file)
    first = raw[0]
    tab = {"source_id": source_id, "year": year, "level": LEVEL_ITR,
           "pub_date": first["pub_date"],
           "table": f"{first['edition']} {first['table_id']} ({first['table_title']})",
           "pdf_page": first["pdf_page"], "printed_page": first["printed_page"],
           "units": states.units(year), "note": note}
    by: dict[str, dict] = {}
    for r in raw:
        if r["column"] not in ("screened", "diagnosed"):
            continue
        rec = by.setdefault(r["canonical"], {"state": r["canonical"]})
        rec[r["column"]] = _int(r["value"])
        rec.setdefault("pdf_page", r["pdf_page"])
        rec.setdefault("printed_page", r["printed_page"])
        if r["value"] == "":
            rec["reason"] = (f"{r['column']} not printed ({r['note']})" if r["note"]
                             else f"{r['column']} not printed")
        if r["is_total"] == "yes":
            rec["note"] = "India row as printed"
    return tab, list(by.values())


def load_gha():
    raw = _read("quality_studies.csv")

    def pick(table, q):
        return {r["geography"]: r for r in raw if r["study"] == "GHA2023SM"
                and r["table_id"] == table and r["quantity"] == q}

    def records(a, b, names):
        out = []
        for g in sorted(set(a) | set(b)):
            rec = {"state": g, names[0]: _int(a[g]["value"]) if g in a else None,
                   names[1]: _int(b[g]["value"]) if g in b else None}
            if g == "India":
                rec["note"] = "India row as printed"
            out.append(rec)
        return out

    base = {"year": 2021, "level": LEVEL_OTHER, "pub_date": "2023-09-01",
            "pdf_page": "n/a (supplementary annex)", "printed_page": "n/a",
            "units": states.units(2021)}
    s1 = dict(base, source_id="GHA2023-S1", note="", table="GHA 2023 supplement, S1 Annex "
              "(State screened, tested, diagnosed; first ACF cycle 2021)")
    s2 = dict(base, source_id="GHA2023-S2", table="GHA 2023 supplement, S2 Annex "
              "(ACF-detected and public notified TB, 2021)",
              note="denominator is public-sector notifications only (printed column "
                   "'Public notified TB (from 2022 India TB report)')")
    return ((s1, records(pick("S1 Annex", "screened"), pick("S1 Annex", "diagnosed"),
                         ("screened", "diagnosed"))),
            (s2, records(pick("S2 Annex", "diagnosed"), pick("S2 Annex", "public_notified"),
                         ("acf", "notified"))))


def run() -> dict:
    rows = []
    for spec in ITR_TABLES:
        tab, recs = load_itr(*spec)
        rows += table_rows(tab, recs)
    (s1, r1), (s2, r2) = load_gha()
    rows += table_rows(s1, r1)
    rows += table_rows(s2, r2, kind="share")
    summary = summarise(rows)
    for year, why in NO_TABLE_YEARS.items():
        for ind in (YIELD, NNS, SHARE):
            rows.append({c: "" for c in COLUMNS} | {
                "state": "(all States)", "year": str(year), "indicator": ind,
                "unit": UNITS[ind], "status": "not_available", "reason": why})
    return {"rows": rows, "summary": summary}


def _write(path, rows, cols):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = run()
    rows = sorted(res["rows"], key=lambda r: (r["year"], r["source_id"], r["indicator"],
                                              r["state"] != "India", r["state"]))
    _write(OUT, rows, COLUMNS)
    summ = sorted(res["summary"], key=lambda r: (r["year"], r["indicator"],
                                                 r["state"] != "India", r["state"]))
    _write(OUT_SUMMARY, summ, SUMMARY_COLUMNS)
    print(f"q3_yield.csv: {len(rows)} rows; q3_yield_summary.csv: {len(summ)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
