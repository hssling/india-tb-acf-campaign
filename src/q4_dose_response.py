"""Q4: dose-response (analysis plan §9-§10). This module holds, for now, only the guard
of §9.5.2, the first step of the order of analyses; no other Q4 quantity is computed
here yet.

Guard (§9.5.2): each State's 2023 and 2024 counts in Rajya Sabha Question 1216 are
divided by its "notified" counts in Question 3467, after unit coarsening (§9.4). States
lacking either value are left out of that year and listed.

- The guard fails if the median 2023 ratio lies outside [0.95, 1.05] or the median
  2024 ratio is below 0.95. A 2024 median above 1.05 does not fail it (late reports);
  it is reported descriptively.
- A failure of Question 1216's own extraction checks counts as a failed guard,
  whatever the medians.
- The guard is not run (the full-year contrast stays primary) if Question 1216 passes
  its extraction checks but Question 3467 fails its own, or fewer than 10 States have
  both values for either year.
- Every State whose ratio lies outside [0.95, 1.05] in either year is a Q2 discrepancy;
  2024 ratios above 1.05 are labelled late-report-consistent.
- If the guard fails, the January-October contrast (S8) becomes primary with the
  fallback trend sources for 2023 and 2024 together (§9.6).

Pure standard library (§11).

Run: python -I src/q4_dose_response.py --guard
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import statistics

from src import source_checks as sc

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "data/extracted"
YEARS = (2023, 2024)
LO, HI = 0.95, 1.05
MIN_STATES = 10
LATE = "late-report-consistent"

Counts = dict[int, dict[str, int]]   # year -> coarsened unit -> count


def ratios(q1216: Counts, q3467: Counts) -> dict[int, dict[str, float]]:
    """Per-year State ratios Q1216 / Q3467 over the units with both values (a zero
    denominator leaves the unit out)."""
    out = {}
    for y in YEARS:
        a, b = q1216.get(y, {}), q3467.get(y, {})
        out[y] = {u: a[u] / b[u] for u in sorted(a.keys() & b.keys()) if b[u]}
    return out


def guard(q1216: Counts, q3467: Counts, q1216_extraction_ok: bool,
          q3467_extraction_ok: bool) -> tuple[str, dict[int, float | None], list[dict]]:
    """(status, medians, flagged_states); status is pass, fail or not_run."""
    r = ratios(q1216, q3467)
    medians = {y: (statistics.median(r[y].values()) if r[y] else None) for y in YEARS}
    flagged = []
    for y in YEARS:
        for u, x in r[y].items():
            if x < LO or x > HI:
                flagged.append({"state": u, "year": y, "ratio": x,
                                "label": LATE if (y == 2024 and x > HI) else ""})
    if not q1216_extraction_ok:
        return "fail", medians, flagged
    if not q3467_extraction_ok or any(len(r[y]) < MIN_STATES for y in YEARS):
        return "not_run", medians, flagged
    m23, m24 = medians[2023], medians[2024]
    status = "fail" if (m23 < LO or m23 > HI or m24 < LO) else "pass"
    return status, medians, flagged


def guard_consequences(status: str, extraction: dict[str, str] | None = None) -> dict:
    """Primary contrast and trend sources implied by the guard (§9.5.2, §9.6)."""
    ext = extraction or {s: "pass" for s in (sc.Q1216, sc.Q3467, sc.ITR2020,
                                               sc.ITR2023, sc.ITR2024, sc.LS261,
                                               sc.Q1093)}
    failed = status == "fail"
    return {
        "primary": ("January-October 2025 vs 2024 (S8)" if failed
                    else "full-year 2025 vs 2024"),
        "full_year_role": "descriptive (§10.7)" if failed else "primary",
        "trend": sc.trend_points(ext, fallback=failed),
        "note": ("the guard was not run; the full-year contrast stays primary and the "
                 "paper states that the guard could not be run" if status == "not_run"
                 else ""),
    }


# ================================================================== run on the extracted tables

def _read(name: str) -> list[dict]:
    with open(EX / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _counts(name: str, columns: dict[str, int]) -> tuple[Counts, list[str]]:
    """Coarsened counts per year from an extracted parliamentary table; rows whose label
    is not computable are listed."""
    out: Counts = {y: {} for y in YEARS}
    unmapped = []
    for r in _read(name):
        if r["column"] not in columns or r["value"] == "":
            continue
        if not r["coarse_unit"]:
            unmapped.append(r["label_printed"])
            continue
        y = columns[r["column"]]
        out[y][r["coarse_unit"]] = out[y].get(r["coarse_unit"], 0) + int(r["value"])
    return out, unmapped


def run_guard() -> dict:
    q1216, u1 = _counts("pq_q1216.csv", {"2023_notified": 2023, "2024_notified": 2024})
    q3467, u2 = _counts("pq_q3467.csv", {"2023_notified": 2023, "2024_notified": 2024})
    ext = {r["source"]: r["result"] for r in _read("q4_source_checks.csv")}
    status, medians, flagged = guard(q1216, q3467, ext.get(sc.Q1216) == "pass",
                                     ext.get(sc.Q3467) == "pass")
    r = ratios(q1216, q3467)
    rows = []
    for y in YEARS:
        units = sorted(q1216[y].keys() | q3467[y].keys())
        for u in units:
            x = r[y].get(u)
            out = x is not None and (x < LO or x > HI)
            rows.append({"year": y, "unit": u, "q1216_notified": q1216[y].get(u, ""),
                         "q3467_notified": q3467[y].get(u, ""),
                         "ratio": "" if x is None else f"{x:.6f}",
                         "in_guard": "yes" if x is not None else "no",
                         "outside_0_95_1_05": "yes" if out else "no",
                         "q2_discrepancy": "yes" if out else "no",
                         "label": LATE if (out and y == 2024 and x > HI) else "",
                         "note": "" if x is not None else
                                 "missing in one table: left out and listed"})
    cons = guard_consequences(status, ext)
    result = {"status": status, "medians": medians,
              "n": {y: len(r[y]) for y in YEARS}, "flagged": flagged,
              "consequences": cons, "unmapped": u1 + u2, "rows": rows,
              "extraction": {sc.Q1216: ext.get(sc.Q1216), sc.Q3467: ext.get(sc.Q3467)}}
    return result


def write_guard(result: dict) -> None:
    fields = ["year", "unit", "q1216_notified", "q3467_notified", "ratio", "in_guard",
              "outside_0_95_1_05", "q2_discrepancy", "label", "note"]
    with open(EX / "guard_ratios.csv", "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(result["rows"])
    cons = result["consequences"]
    summary = [
        {"item": "status", "value": result["status"]},
        {"item": "median ratio 2023", "value": f"{result['medians'][2023]:.6f}"},
        {"item": "median ratio 2024", "value": f"{result['medians'][2024]:.6f}"},
        {"item": "n States 2023", "value": result["n"][2023]},
        {"item": "n States 2024", "value": result["n"][2024]},
        {"item": "States outside [0.95, 1.05] in 2023",
         "value": sum(1 for x in result["flagged"] if x["year"] == 2023)},
        {"item": "States outside [0.95, 1.05] in 2024",
         "value": sum(1 for x in result["flagged"] if x["year"] == 2024)},
        {"item": "2024 rows labelled late-report-consistent",
         "value": sum(1 for x in result["flagged"] if x["label"] == LATE)},
        {"item": "extraction checks", "value": "; ".join(
            f"{k}: {v}" for k, v in result["extraction"].items())},
        {"item": "primary contrast", "value": cons["primary"]},
        {"item": "full-year contrast role", "value": cons["full_year_role"]},
        {"item": "trend sources", "value": "; ".join(
            f"{y}: {t['source']} ({t['status']})"
            for y, t in sorted(cons["trend"].items()))},
        {"item": "labels not computable", "value": "; ".join(result["unmapped"])
         or "none"},
    ]
    with open(EX / "guard_result.csv", "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["item", "value"], lineterminator="\n")
        w.writeheader()
        w.writerows(summary)


def main(argv: list[str]) -> int:
    if "--guard" not in argv:
        print("usage: python -I src/q4_dose_response.py --guard")
        return 2
    res = run_guard()
    write_guard(res)
    print(f"guard: {res['status']}; median 2023 {res['medians'][2023]:.4f} "
          f"(n={res['n'][2023]}); median 2024 {res['medians'][2024]:.4f} "
          f"(n={res['n'][2024]}); primary: {res['consequences']['primary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
