"""Check that the inventory and the analysis inputs trace to recorded sources.

Run as: python -I verification/check_inventory.py

1. Every row of data/figures_inventory.csv has a source_file that is a row of
   data/source_manifest.csv, or is an online page (a URL) recorded with that URL in
   data/transcribed/online_pages.csv or data/transcribed/quality_studies_tables.csv.
2. Every computed row of outputs/q3_yield.csv: its numerator and denominator are values
   of an extracted row (data/extracted/itr*.csv, pq_*.csv) or an inventory row for the
   same State (or India), with the same value.
3. Every row of outputs/q4_states.csv: the a, b and trend values (n2019, n2022, n2023,
   n2024, q261_2023, itr2024_2023) equal the sum, over the States of the unit, of one
   column of one extracted table (units that are single States equal that State's value).
Nothing is written.
"""
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREND_COLUMNS = ("a", "b", "n2019", "n2022", "n2023", "n2024", "q261_2023", "itr2024_2023")


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


def value_index(root: Path) -> tuple[dict, dict]:
    """(state, value) pairs from extracted CSVs and the inventory; and, per unit, the sums
    of each extracted (file, column) over the States of the unit."""
    pairs: set[tuple[str, Decimal]] = set()
    unit_sums: dict[str, set[Decimal]] = defaultdict(set)
    ex = root / "data" / "extracted"
    for f in sorted(list(ex.glob("itr*.csv")) + list(ex.glob("pq_*.csv"))):
        rows = read(f)
        if not rows or not {"column", "value", "coarse_unit", "canonical"} <= set(rows[0]):
            continue
        acc: dict[tuple, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for r in rows:
            v = dec(r["value"])
            if v is None:
                continue
            for k in (r["canonical"], r["coarse_unit"]):
                if k:
                    pairs.add((k, v))
            if r["is_total"] == "no" and r["coarse_unit"]:
                acc[(f.name, r["column"])][r["coarse_unit"]] += v
        for (_, _), per in acc.items():
            for unit, s in per.items():
                unit_sums[unit].add(s)
    for r in read(root / "data" / "figures_inventory.csv"):
        v = dec(r["value"])
        if v is not None and r["geography"]:
            pairs.add((r["geography"], v))
    return pairs, unit_sums


def q3_problems(root: Path, pairs) -> tuple[list[str], int]:
    bad, n = [], 0
    for r in read(root / "outputs" / "q3_yield.csv"):
        if r["status"] != "computed":
            continue
        for col in ("numerator", "denominator"):
            v = dec(r[col])
            if v is None or (r["state"], v) not in pairs:
                bad.append(f"q3_yield {r['state']} {r['year']} {r['indicator']} "
                           f"({r['source_id']}): {col} {r[col]!r} matches no inventory or "
                           f"extracted row for this State")
            else:
                n += 1
    return bad, n


def q4_problems(root: Path, pairs, unit_sums) -> tuple[list[str], int]:
    bad, n = [], 0
    seen: set[tuple] = set()
    for r in read(root / "outputs" / "q4_states.csv"):
        for col in TREND_COLUMNS:
            v = dec(r.get(col, ""))
            if v is None or (r["unit"], col, v) in seen:
                continue
            seen.add((r["unit"], col, v))
            if v in unit_sums.get(r["unit"], set()) or (r["unit"], v) in pairs:
                n += 1
            else:
                bad.append(f"q4_states {r['unit']} ({r['contrast']}, {r['denominator_set']}): "
                           f"{col}={r[col]} matches no extracted column sum or inventory "
                           f"value for this unit")
    return bad, n


def problems(root: Path = ROOT) -> tuple[list[str], dict]:
    b1, n1 = source_problems(root)
    pairs, unit_sums = value_index(root)
    b2, n2 = q3_problems(root, pairs)
    b3, n3 = q4_problems(root, pairs, unit_sums)
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
          f"online page; {n['q3']} Q3 inputs and {n['q4']} distinct Q4 inputs trace to "
          f"extracted or inventory values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
