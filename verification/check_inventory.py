"""Check that the inventory and the analysis inputs trace to recorded sources.

Run as: python -I verification/check_inventory.py

1. Every row of data/figures_inventory.csv has a source_file that is a row of
   data/source_manifest.csv, or is an online page (a URL) recorded with that URL in
   data/transcribed/online_pages.csv or data/transcribed/quality_studies_tables.csv.
2. Every computed row of outputs/q3_yield.csv: its numerator and denominator equal the
   value of the source column its source_id names (diagnosed and screened of the India TB
   Report annexure, or the GHA supplement S1/S2 inventory rows) for the same State and
   year.
3. Every row of outputs/q4_states.csv: a, b and the trend values equal the coarsened-unit
   sum of the column they come from, keyed by unit, year and column: a (2024) and b (2025)
   from Q1216's full-year notified columns, or Q261 and Q1093 January-October for S8;
   n2019 from ITR2020 A1.2, n2022 from ITR2023 A1.2, n2023 and n2024 from Q1216;
   q261_2023 from Q261 and itr2024_2023 from ITR2024 A1.2; the placebo's a and b are the
   2022 and 2023 counts. A value that belongs to another figure of the same unit fails.
Nothing is written.
"""
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FULL, JANOCT, PLACEBO = ("full-year 2025 vs 2024", "January-October 2025 vs 2024",
                         "placebo 2023 vs 2022")
# The extracted column behind each Q4 quantity (plan 9.5, 9.6, 10.1): a is the first
# window (2024), b the second (2025); the trend points come from their own year tables
# (2023 and 2024 from Q1216, the primary trend source: the guard passed).
N_COLS = {"n2019": ("itr2020_a1_2.csv", "notified_total"),
          "n2022": ("itr2023_a1_2.csv", "notified_total"),
          "n2023": ("pq_q1216.csv", "2023_notified"),
          "n2024": ("pq_q1216.csv", "2024_notified")}
Q4_COLS = {
    FULL: {"a": ("pq_q1216.csv", "2024_notified"), "b": ("pq_q1216.csv", "2025_notified"),
           **N_COLS},
    JANOCT: {"a": ("pq_q261.csv", "2024_jan_oct_reported"),
             "b": ("pq_q1093.csv", "2025_jan_oct_reported"),
             "q261_2023": ("pq_q261.csv", "2023_reported"),
             "itr2024_2023": ("itr2024_a1_2.csv", "notified_total"), **N_COLS},
    PLACEBO: {"a": N_COLS["n2022"], "b": N_COLS["n2023"], "n2019": N_COLS["n2019"],
              "n2022": N_COLS["n2022"], "n2023": N_COLS["n2023"]},
}
# Q3: source_id -> (year, kind, numerator, denominator, table or inventory prefix)
Q3_SOURCES = {
    "ITR2019-A1.7": (2018, "csv", "diagnosed", "screened", "itr2019_a1_7_acf.csv"),
    "ITR2020-A6": (2019, "csv", "diagnosed", "screened", "itr2020_a6_acf.csv"),
    "ITR2022-A6": (2021, "csv", "diagnosed", "screened", "itr2022_a6_acf.csv"),
    "ITR2023-A6": (2022, "csv", "diagnosed", "screened", "itr2023_a6_acf.csv"),
    "ITR2024-A6": (2023, "csv", "diagnosed", "screened", "itr2024_a6_acf.csv"),
    "GHA2023-S1": (2021, "inv", ".number-diagnosed-among-tested.", ".number-screened.",
                   "GHA2023SM.s1."),
    "GHA2023-S2": (2021, "inv",
                   ".tb-acf-cases-diagnosed-among-tested-reported-as-acf-detected.",
                   ".public-notified-tb-from-2022-india-tb-report.", "GHA2023SM.s2."),
}


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dec(s) -> Decimal | None:
    try:
        return Decimal(str(s).replace(",", "").strip()) if str(s).strip() != "" else None
    except InvalidOperation:
        return None


def _urls(root: Path) -> set[str]:
    out: set[str] = set()
    for name, col in (("online_pages.csv", "url"), ("quality_studies_tables.csv", "url")):
        p = root / "data" / "transcribed" / name
        if p.exists():
            out |= {r[col].strip() for r in read(p) if r.get(col, "").strip()}
    return out


def source_problems(root: Path) -> tuple[list[str], int]:
    manifest = {r["file"] for r in read(root / "data" / "source_manifest.csv")}
    urls = _urls(root)
    bad: list[str] = []
    rows = read(root / "data" / "figures_inventory.csv")
    for r in rows:
        src = r["source_file"]
        if src in manifest or src in urls:
            continue
        kind = "online page" if src.startswith("http") else "file"
        bad.append(f"inventory {r['fig_id']}: source_file {src!r} is not in the source "
                   f"manifest and is not a {kind} recorded in data/transcribed/*.csv")
    return bad, len(rows)


def unit_sums(root: Path, name: str, column: str) -> dict[str, Decimal]:
    """Coarsened-unit sums of one extracted column (State rows, members summed)."""
    out: dict[str, Decimal] = defaultdict(Decimal)
    for r in read(root / "data" / "extracted" / name):
        v = dec(r["value"])
        if (r["column"] == column and r.get("is_total", "no") != "yes" and v is not None
                and r["coarse_unit"]):
            out[r["coarse_unit"]] += v
    return dict(out)


def state_values(root: Path, name: str, column: str) -> dict[str, set[Decimal]]:
    """canonical label -> values of one extracted column (the India total included)."""
    out: dict[str, set[Decimal]] = defaultdict(set)
    for r in read(root / "data" / "extracted" / name):
        v = dec(r["value"])
        if r["column"] == column and v is not None and r["canonical"]:
            out[r["canonical"]].add(v)
    return dict(out)


def inventory_values(root: Path, prefix: str, mid: str) -> dict[str, set[Decimal]]:
    out: dict[str, set[Decimal]] = defaultdict(set)
    for r in read(root / "data" / "figures_inventory.csv"):
        v = dec(r["value"])
        if r["fig_id"].startswith(prefix) and mid in r["fig_id"] + "." and v is not None:
            out[r["geography"]].add(v)
    return dict(out)


def q3_expected(root: Path, source_id: str) -> tuple[int, dict, dict]:
    year, kind, num, den, table = Q3_SOURCES[source_id]
    if kind == "csv":
        return year, state_values(root, table, num), state_values(root, table, den)
    return year, inventory_values(root, table, num), inventory_values(root, table, den)


def q3_problems(root: Path) -> tuple[list[str], int]:
    bad, n = [], 0
    cache: dict[str, tuple] = {}
    for r in read(root / "outputs" / "q3_yield.csv"):
        if r["status"] != "computed":
            continue
        sid = r["source_id"]
        if sid not in Q3_SOURCES:
            bad.append(f"q3_yield {r['state']} {r['year']} {r['indicator']}: source_id "
                       f"{sid!r} has no known source column")
            continue
        year, numv, denv = cache.setdefault(sid, q3_expected(root, sid))
        label = f"q3_yield {r['state']} {r['year']} {r['indicator']} ({sid})"
        if int(r["year"]) != year:
            bad.append(f"{label}: year {r['year']} but {sid} reports {year}")
        for col, pool in (("numerator", numv), ("denominator", denv)):
            v = dec(r[col])
            if v is None or v not in pool.get(r["state"], set()):
                bad.append(f"{label}: {col} {r[col]!r} is not the {sid} source value for "
                           f"this State ({sorted(pool.get(r['state'], set()))})")
            else:
                n += 1
    return bad, n


def q4_problems(root: Path) -> tuple[list[str], int]:
    bad, n = [], 0
    sums: dict[tuple, dict] = {}
    for r in read(root / "outputs" / "q4_states.csv"):
        cols = Q4_COLS.get(r["contrast"])
        if cols is None:
            bad.append(f"q4_states {r['unit']}: unknown contrast {r['contrast']!r}")
            continue
        for col, src in cols.items():
            exp = sums.setdefault(src, unit_sums(root, *src)).get(r["unit"])
            v = dec(r.get(col, ""))
            label = f"q4_states {r['unit']} ({r['contrast']}, {r['denominator_set']}) {col}"
            if v is None:
                if exp is not None and r["computable"] == "yes":
                    bad.append(f"{label}: blank but {src[0]}:{src[1]} holds {exp}")
            elif exp != v:
                bad.append(f"{label}: {v} but {src[0]}:{src[1]} gives "
                           f"{'no value' if exp is None else exp} for this unit")
            else:
                n += 1
    return bad, n


def problems(root: Path = ROOT) -> tuple[list[str], dict]:
    b1, n1 = source_problems(root)
    b2, n2 = q3_problems(root)
    b3, n3 = q4_problems(root)
    return b1 + b2 + b3, {"inventory": n1, "q3": n2, "q4": n3}


def main(root: Path = ROOT) -> int:
    bad, n = problems(root)
    if bad:
        for b in bad[:60]:
            print(f"FAIL: {b}")
        if len(bad) > 60:
            print(f"FAIL: ... and {len(bad) - 60} more")
        return 1
    print(f"OK: {n['inventory']} inventory rows resolve to the source manifest or a recorded "
          f"online page; {n['q3']} Q3 inputs and {n['q4']} Q4 inputs match their source "
          f"column by unit, year and column")
    return 0


if __name__ == "__main__":
    sys.exit(main())
