# Copied from hssling/india-state-tb-score (MIT), verification/check_extraction_totals.py, commit 05bcaa7; modified: no PDFs or extractors needed; recomputes every recorded sum from the extracted CSVs (and, for the three campaign tables, from the inventory) and compares data/extracted/table_total_checks.csv and q4_source_checks.csv with the recomputation
"""Re-verify the recorded table-total checks against the extracted data, writing nothing.

Run as: python -I verification/check_extraction_totals.py

1. Every column of every extracted CSV (data/extracted/itr*.csv, pq_*.csv) and the
   three campaign tables read into the inventory (CTD State | Total District, Guidance
   Document State | Total District, Campaign 2026 Annexure IV) is summed again. Each
   recomputed group must match exactly one row of data/extracted/table_total_checks.csv
   (same file, row count, sum, printed total) and each recorded row must match one group.
   Percentage columns (*_pct) are not additive and are not checked.
   For each row the difference is recomputed and the recorded pass/fail must agree: the
   rows sum to the printed total within +-1; a figure table printed in lakhs with one
   decimal follows the interval rule of plan 6.2 check 3; no printed total is 'n/a'.
2. Every row of data/extracted/q4_source_checks.csv is recomputed: its needed columns
   exist and hold values, its sum check agrees with the recomputed sums, and its result
   is pass only if both pass.
"""
import csv
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_TABLES = (  # fig_id prefixes of the three printed State tables with a total row
    "CTD100.p007.total-district.", "GUIDE.p008.total-district.", "TMBA26.p059.")


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _dec(s: str) -> Decimal | None:
    s = (s or "").replace(",", "").strip()
    return Decimal(s) if s else None


def _h(printed: str) -> Decimal:
    d = len(printed.split(".")[1]) if "." in printed else 0
    return Decimal(100000) * Decimal(5) / (Decimal(10) ** (d + 1))


def extracted_groups(root: Path) -> list[dict]:
    """One group per (source file, table, column): rows, sum and printed total."""
    groups = []
    ex = root / "data" / "extracted"
    for f in sorted(list(ex.glob("itr*.csv")) + list(ex.glob("pq_*.csv"))):
        rows = read(f)
        if not rows or not {"column", "value", "is_total", "source_file"} <= set(rows[0]):
            continue
        keyed: dict[tuple, list[dict]] = {}
        for r in rows:
            keyed.setdefault((r["source_file"], r.get("table_key") or r.get("table_id", ""),
                              r["column"]), []).append(r)
        for (src, table, col), rs in keyed.items():
            if col.endswith("_pct"):  # percentages are not additive; no total check exists
                continue
            parts = [r for r in rs if r["is_total"] == "no"]
            tots = [r for r in rs if r["is_total"] == "yes"]
            vals = [r for r in parts if r["value"] != ""]
            groups.append({
                "csv": f.name, "source_file": src, "table": table, "column": col,
                "rows_all": len(parts), "rows_nonblank": len(vals),
                "sum": sum(_dec(r["value"]) for r in vals),
                "printed": _dec(tots[0]["value"]) if tots else None,
                "printed_text": [r["value_printed"] for r in vals],
                "printed_total_text": tots[0]["value_printed"] if tots else ""})
    inv = read(root / "data" / "figures_inventory.csv")
    for prefix in CAMPAIGN_TABLES:
        rs = [r for r in inv if r["fig_id"].startswith(prefix)]
        parts = [r for r in rs if r["fig_id"].split(".")[-2] != "total"
                 and re.match(r"^[0-9,]+$", r["value"])]
        tot = [r for r in rs if r["fig_id"].split(".")[-2] == "total"]
        if parts and tot:
            groups.append({"csv": "figures_inventory.csv", "source_file": parts[0]["source_file"],
                           "table": prefix, "column": "", "rows_all": len(parts),
                           "rows_nonblank": len(parts),
                           "sum": sum(_dec(r["value"]) for r in parts),
                           "printed": _dec(tot[0]["value"]), "printed_text": [],
                           "printed_total_text": ""})
    return groups


def _num(s: str) -> Decimal | None:
    return _dec(s)


def expected_pass(rec: dict, group: dict | None) -> str:
    """The pass value the recorded numbers imply."""
    s, t = _num(rec["sum_of_rows"]), _num(rec["printed_total"])
    if t is None:
        return "n/a"
    if "lakhs with one decimal" in rec["note"] and group:
        pr = group["printed_text"]
        vals_lo = vals_hi = Decimal(0)
        for p in pr:
            vals_lo += _dec(p) * 100000 - _h(p)
            vals_hi += _dec(p) * 100000 + _h(p)
        lo, hi = vals_lo - 1, vals_hi + 1
        hT = _h(group["printed_total_text"])
        return "no" if (hi < t - hT or lo > t + hT) else "yes"
    return "yes" if abs(s - t) <= 1 else "no"


def totals_problems(root: Path) -> tuple[list[str], int, list[tuple[dict, dict]]]:
    bad: list[str] = []
    groups = extracted_groups(root)
    checks = read(root / "data" / "extracted" / "table_total_checks.csv")
    pairs: list[tuple[dict, dict]] = []
    used: set[int] = set()
    n_ok = 0
    for i, c in enumerate(checks):
        label = f"{c['source_file']} p{c['page']} {c['table'][:60]!r}"
        s, t = _num(c["sum_of_rows"]), _num(c["printed_total"])
        diff_rec = _num(c["difference"])
        if s is None:
            if c["pass"] != "n/a" or t is not None:
                bad.append(f"{label}: no sum recorded but pass={c['pass']!r}")
            else:
                n_ok += 1
            continue
        g = None
        for j, cand in enumerate(groups):
            if j in used or cand["source_file"] != c["source_file"]:
                continue
            if (cand["sum"] == s and cand["printed"] == t
                    and int(c["rows"]) in (cand["rows_all"], cand["rows_nonblank"])):
                g = j
                break
        if g is None:
            bad.append(f"{label}: recorded {c['rows']} rows, sum {c['sum_of_rows']}, printed "
                       f"total {c['printed_total'] or 'none'} is not reproduced by any "
                       f"extracted column")
            continue
        used.add(g)
        pairs.append((c, groups[g]))
        if t is not None and diff_rec != s - t:
            bad.append(f"{label}: recorded difference {c['difference']} != {s} - {t}")
        exp = expected_pass(c, groups[g])
        if c["pass"] != exp:
            bad.append(f"{label}: recorded pass={c['pass']!r} but the recomputed sums give "
                       f"{exp!r}")
        else:
            n_ok += 1
    for j, g in enumerate(groups):
        if j not in used:
            bad.append(f"{g['csv']} {g['table']} {g['column']}: {g['rows_all']} rows sum to "
                       f"{g['sum']} (printed total {g['printed']}) but no recorded check "
                       f"matches")
    return bad, n_ok, pairs


def q4_problems(root: Path) -> tuple[list[str], int]:
    bad: list[str] = []
    groups = extracted_groups(root)
    n = 0
    for r in read(root / "data" / "extracted" / "q4_source_checks.csv"):
        needed = [c.strip() for c in r["needed_columns"].split(";") if c.strip()]
        found, sums, notes = [], [], []
        for col in needed:
            gs = [g for g in groups if g["source_file"] == r["source_file"]
                  and g["column"] == col and g["rows_nonblank"] > 0]
            found.append(bool(gs))
            if gs:
                g = gs[0]
                if g["printed"] is None:
                    sums.append(None)
                else:
                    d = g["sum"] - g["printed"]
                    sums.append(abs(d) <= 1)
                    notes.append(f"{col}: rows sum to {g['sum']}, printed total "
                                 f"{g['printed']}, difference {d}")
        col_ok = "pass" if found and all(found) else "fail"
        applied = [s for s in sums if s is not None]
        sum_ok = ("not applied (no total printed)" if not applied
                  else "pass" if all(applied) else "fail")
        result = "pass" if col_ok == "pass" and sum_ok != "fail" else "fail"
        label = f"q4_source_checks {r['source']}"
        for name, rec, exp in (("column_check", r["column_check"], col_ok),
                               ("sum_check", r["sum_check"], sum_ok),
                               ("result", r["result"], result)):
            if rec != exp:
                bad.append(f"{label}: recorded {name}={rec!r} but the recomputation gives "
                           f"{exp!r}")
        for ln in notes:
            if ln not in r["note"]:
                bad.append(f"{label}: note does not contain the recomputed '{ln}'")
        if not any(b.startswith(label) for b in bad):
            n += 1
    return bad, n


def problems(root: Path = ROOT) -> tuple[list[str], dict]:
    b1, n1, _ = totals_problems(root)
    b2, n2 = q4_problems(root)
    return b1 + b2, {"totals": n1, "q4": n2}


def main(root: Path = ROOT) -> int:
    bad, n = problems(root)
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    print(f"OK: {n['totals']} recorded table-total checks reproduced from the extracted "
          f"data (sums, differences and pass/fail); {n['q4']} Q4 source checks reproduced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
