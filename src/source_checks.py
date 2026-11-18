"""Extraction checks of the Q4 source tables and their mechanical consequences
(analysis plan §9.6, "Extraction checks for every Q4 source"; §9.5.2; §10.7).

- A Q4 source table fails extraction if its State rows do not sum to its printed total
  within ±1, or if a needed column cannot be read.
- If no total is printed, the sum check is not applied, and this is reported.
- A trend source in use (primary or fallback) that fails leaves that year missing for
  every State, with no further substitution.
- An outcome table that fails makes its contrast not computable.
- A failure of Question 1216's own extraction checks counts as a failed guard (§9.5.2):
  the January-October contrast becomes primary and the fallback trend sources replace
  2023 and 2024 together (§9.6).

Nothing here computes a guard ratio, a comparison between sources or any Q result.
Pure standard library: analysis modules import it without the PDF libraries.
"""
from __future__ import annotations

NO_TOTAL = "no total printed: sum check not applied"

# The Q4 source tables (§9.6) and their roles.
Q1216, Q3467, ITR2020, ITR2023, ITR2024, LS261, Q1093 = (
    "RS Q1216", "RS Q3467", "ITR 2020", "ITR 2023", "ITR 2024", "LS Q261", "RS Q1093")

# Trend points: year -> (primary source, fallback source) (§9.6 table).
TREND = {2019: (ITR2020, ITR2020), 2022: (ITR2023, ITR2023),
         2023: (Q1216, ITR2024), 2024: (Q1216, Q3467)}
# Contrasts: name -> outcome tables (§9.5.1, §9.5.3).
CONTRASTS = {"full-year 2025 vs 2024": (Q1216,),
             "January-October 2025 vs 2024 (S8)": (LS261, Q1093)}


def total_check(values: list[int], printed_total: int | None) -> dict:
    """Rows sum to the printed total within ±1 (§6.2 check 3; §9.6). With no printed
    total the check is not applied, and the record says so."""
    s = sum(values)
    if printed_total is None:
        return {"sum_of_rows": s, "printed_total": "", "difference": "", "pass": "n/a",
                "note": NO_TOTAL}
    d = s - printed_total
    return {"sum_of_rows": s, "printed_total": printed_total, "difference": d,
            "pass": "yes" if abs(d) <= 1 else "no", "note": ""}


def q4_extraction_check(source: str, columns: dict[str, list[int | None] | None],
                        printed_totals: dict[str, int | None],
                        needed: tuple[str, ...]) -> dict:
    """The §9.6 extraction check of one Q4 source table.

    `columns` maps a column name to its State values (None for an unreadable column;
    a None value inside the list is a blank cell). `printed_totals` gives the printed
    total of each column (None when no total is printed). A needed column that is
    absent, unreadable or has a blank cell cannot be read. The sum check is applied to
    every needed column that has a printed total."""
    unreadable, sums, notes = [], [], []
    for c in needed:
        vals = columns.get(c)
        if vals is None or not vals or any(v is None for v in vals):
            unreadable.append(c)
            continue
        t = total_check([v for v in vals], printed_totals.get(c))
        sums.append((c, t))
    sum_fail = [c for c, t in sums if t["pass"] == "no"]
    no_total = [c for c, t in sums if t["pass"] == "n/a"]
    if unreadable:
        notes.append("needed column not readable: " + ", ".join(unreadable))
    for c, t in sums:
        if t["pass"] == "n/a":
            notes.append(f"{c}: {NO_TOTAL}")
        else:
            notes.append(f"{c}: rows sum to {t['sum_of_rows']}, printed total "
                         f"{t['printed_total']}, difference {t['difference']}")
    if not sums:
        sum_check = "not applied"
    elif sum_fail:
        sum_check = "fail"
    elif len(no_total) == len(sums):
        sum_check = "not applied (no total printed)"
    else:
        sum_check = "pass" + (" (some columns have no printed total)" if no_total else "")
    return {"source": source, "needed_columns": "; ".join(needed),
            "column_check": "fail" if unreadable else "pass",
            "sum_check": sum_check,
            "result": "fail" if (unreadable or sum_fail) else "pass",
            "note": "; ".join(notes)}


def guard_failed_by_extraction(results: dict[str, str]) -> bool:
    """§9.5.2: a failure of Question 1216's own extraction checks counts as a failed
    guard for every purpose."""
    return results.get(Q1216) == "fail"


def trend_points(results: dict[str, str], fallback: bool) -> dict[int, dict]:
    """Each trend year's source in use and its status. The fallback column replaces
    2023 and 2024 together, never one year alone. A source in use that failed leaves
    the year missing for every State, with no substitute."""
    out = {}
    for year, (primary, fb) in TREND.items():
        src = fb if fallback else primary
        ok = results.get(src) == "pass"
        out[year] = {"source": src,
                     "status": "in use" if ok else
                     "missing for every State (source failed its extraction checks; "
                     "no substitute)"}
    return out


def contrast_status(results: dict[str, str]) -> dict[str, str]:
    """A contrast whose outcome table failed extraction is not computable."""
    return {name: ("computable" if all(results.get(t) == "pass" for t in tables)
                   else "not computable (outcome table failed its extraction checks)")
            for name, tables in CONTRASTS.items()}


def consequences(results: dict[str, str]) -> list[dict]:
    """The mechanical consequences of the extraction checks (no guard ratio is
    computed: the guard of §9.5.2 itself is applied later, before any Q4 computation).
    """
    guard_fail = guard_failed_by_extraction(results)
    contrasts = contrast_status(results)
    trend = trend_points(results, fallback=guard_fail)
    out = []
    if guard_fail:
        primary = "January-October 2025 vs 2024 (S8)"
        out.append({"item": "guard (§9.5.2)",
                    "outcome": "failed: Question 1216 failed its own extraction checks",
                    "rule": "§9.5.2, last bullets; §9.6 Fallback"})
    else:
        primary = "full-year 2025 vs 2024"
        if results.get(Q3467) == "fail":
            out.append({"item": "guard (§9.5.2)",
                        "outcome": "cannot be applied: Question 3467 failed its "
                                   "extraction checks; the full-year contrast remains "
                                   "primary and the paper states the guard was not run",
                        "rule": "§9.5.2, 'If the guard cannot be applied'"})
        else:
            out.append({"item": "guard (§9.5.2)",
                        "outcome": "not triggered by extraction; the guard is applied "
                                   "to the extracted values before any Q4 computation",
                        "rule": "§9.5.2"})
    for name, status in contrasts.items():
        role = "primary" if name == primary else "sensitivity (S8)" if "S8" in name \
            else "descriptive (§10.7)"
        out.append({"item": f"contrast: {name}", "outcome": f"{status}; role {role}",
                    "rule": "§9.6 extraction checks; §9.5; §10.7"})
    if contrasts[primary] != "computable":
        other = [n for n in contrasts if n != primary][0]
        out.append({"item": "Q4 reporting",
                    "outcome": ("descriptive from the other contrast (§10.7)"
                                if contrasts[other] == "computable"
                                else "not run: no contrast is computable"),
                    "rule": "§9.6, outcome table that fails"})
    for year, t in sorted(trend.items()):
        out.append({"item": f"trend point {year}",
                    "outcome": f"{t['source']}: {t['status']}",
                    "rule": "§9.6 table and extraction checks"
                            + ("; fallback column in use (guard failed)" if guard_fail
                               else "")})
    return out
