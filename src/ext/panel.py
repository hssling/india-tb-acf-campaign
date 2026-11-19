"""State x year panel of published ACF figures, notifications and campaign exposure
(extension plan section 3). Panel construction only: no estimate is computed here.

Run as `python -I src/ext/panel.py` to write data/ext/panel.csv and
data/ext/panel_exclusions.csv (UTF-8, LF, sorted by unit then year).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python -I src/ext/panel.py`
    sys.path.insert(0, str(ROOT))

EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "data" / "ext"

# year -> (ACF file, screened col, tested col, diagnosed col, population col or None,
#          tested definition, notification file or None)
SOURCES = {
    2018: ("itr2019_a1_7_acf", "screened", "tested", "diagnosed", None, "tested", None),
    2019: ("itr2020_a6_acf", "screened", "tested", "diagnosed",
           "estimated_population_lakhs", "tested", "itr2020_a1_2"),
    2021: ("itr2022_a6_acf", "screened", "tested", "diagnosed",
           "estimated_population_lakhs", "tested", None),
    2022: ("itr2023_a6_acf", "screened", "symptomatic_examined", "diagnosed",
           None, "examined", "itr2023_a1_2"),
    2023: ("itr2024_a6_acf", "screened", "tested", "diagnosed",
           None, "tested", "itr2024_a1_2"),
}
SMALL_UT = frozenset({
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Lakshadweep", "Puducherry"})
FIELDS = ("unit", "year", "screened", "tested", "tested_definition", "diagnosed",
          "notified_public", "notified_private", "notified_total", "est_population",
          "exposure_reconstructed", "exposure_registered", "small_ut", "flags")


def _read(name: str) -> list[dict]:
    with open(EXTRACTED / f"{name}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _column(name: str, column: str) -> dict:
    """coarse unit -> summed value (None if any member is blank); State rows only."""
    vals: dict = {}
    na: set = set()
    for r in _read(name):
        if r["column"] != column or r["is_total"] == "yes":
            continue
        u = r["coarse_unit"]
        if not u:
            raise ValueError(f"{name}: unmapped label {r['label_printed']!r}")
        v = r["value"].strip()
        if v == "":
            na.add(u)
        else:
            vals[u] = vals.get(u, 0) + int(float(v))
    for u in na:  # any NA member makes the merged unit NA
        vals[u] = None
    return vals


def _zero_members(name: str, column: str) -> dict:
    """Merged units with a member printed 0 but a positive sum: unit -> labels."""
    parts: dict = {}
    for r in _read(name):
        if r["column"] == column and r["is_total"] == "no" and r["value"].strip() != "":
            parts.setdefault(r["coarse_unit"], []).append(
                (r["label_printed"], int(float(r["value"]))))
    return {u: [lab for lab, v in p if v == 0] for u, p in parts.items()
            if len(p) > 1 and any(v == 0 for _, v in p) and sum(v for _, v in p) > 0}


def _exposure() -> tuple:
    def load(fname: str) -> dict:
        out = {}
        with open(EXTRACTED / fname, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                # E = min(1, c/L), exactly from the counts (not the rounded share)
                out[r["unit"]] = (min(1.0, int(r["campaign_count"]) / int(r["lgd_count"]))
                                  if r["computable"] == "yes" else None)
        return out
    return load("exposure_share_reconstructed.csv"), load("exposure_share.csv")


def _expected(year: int, field: str) -> bool:
    src = SOURCES[year]
    if field.startswith("notified_"):
        return src[6] is not None
    if field == "est_population":
        return src[4] is not None
    return True


def _list_exclusions(r: dict, out: list) -> None:
    def add(field: str, reason: str) -> None:
        out.append({"unit": r["unit"], "year": r["year"], "field": field, "reason": reason})
    for f in ("screened", "tested", "diagnosed", "notified_public", "notified_private",
              "notified_total", "est_population"):
        if r[f] is None and _expected(r["year"], f):
            add(f, "NA in the source (printed NA or blank, or a member of a merged unit "
                   "is NA); not imputed; left out of models that need it")
    S, T, D, N = r["screened"], r["tested"], r["diagnosed"], r["notified_total"]
    if D == 0:
        add("diagnosed", "zero diagnoses as printed; excluded from log-scale analyses, "
                         "kept on the count and rank scale")
    if S == 0:
        add("screened", "zero screened as printed; inconsistent row (S = 0), excluded "
                        "from log-scale analyses")
    if T == 0 and D is None:
        add("tested", "zero tested as printed with diagnosed NA; value kept as printed")
    if S is not None and D is not None and S > 0 and D >= S:
        add("diagnosed", "inconsistent row (D >= S): log-yield variance undefined or <= 0")
    if N == 0:
        add("notified_total", "zero notifications; excluded from 1/N-weighted and "
                              "log-scale D3 entries")


def _build() -> tuple:
    expo_rec, expo_reg = _exposure()
    rows: list = []
    excl: list = []
    for year, (acf, cs, ct, cd, cp_, tdef, nfile) in SOURCES.items():
        S, T, D = _column(acf, cs), _column(acf, ct), _column(acf, cd)
        Pop = _column(acf, cp_) if cp_ else {}
        N = ({k: _column(nfile, f"notified_{k}") for k in ("public", "private", "total")}
             if nfile else {})
        zero_members = _zero_members(acf, cd)
        # rows follow the ACF table's units; a notification-only unit gets no row
        # (ITR 2020 A1.2 lists Chandigarh, Madhya Pradesh and Manipur, absent from its A6)
        units = set(S) | set(T) | set(D) | set(Pop)
        for u in sorted(units):
            flags = []
            if year == 2022:
                flags.append("itr2023_states_not_india")
            if year == 2019 and Pop.get(u) is not None:
                # ITR 2020 A6 population column misaligned with its State rows as printed
                # (extension plan section 10, 19 November 2026): kept as printed, not used
                flags.append("est_population_misaligned_itr2020")
            if u in zero_members:
                flags.append("member_zero_diagnosed:" + "/".join(sorted(zero_members[u])))
            if expo_reg.get(u) is None:
                flags.append("exposure_registered_na")
            row = {
                "unit": u, "year": year, "screened": S.get(u), "tested": T.get(u),
                "tested_definition": tdef, "diagnosed": D.get(u),
                "notified_public": N.get("public", {}).get(u),
                "notified_private": N.get("private", {}).get(u),
                "notified_total": N.get("total", {}).get(u),
                "est_population": Pop.get(u),
                "exposure_reconstructed": expo_rec.get(u),
                "exposure_registered": expo_reg.get(u),
                "small_ut": u in SMALL_UT, "flags": ";".join(flags),
            }
            rows.append(row)
            _list_exclusions(row, excl)
    rows.sort(key=lambda r: (r["unit"], r["year"]))
    excl.sort(key=lambda r: (r["unit"], r["year"], r["field"], r["reason"]))
    return rows, excl


_CACHE: list = []


def _cached() -> tuple:
    if not _CACHE:
        _CACHE.append(_build())
    return _CACHE[0]


def load_panel() -> list:
    return [dict(r) for r in _cached()[0]]


def exclusions() -> list:
    return [dict(r) for r in _cached()[1]]


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _write(path: Path, fields: tuple, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for r in rows:
            w.writerow([_fmt(r[k]) for k in fields])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, excl = _cached()
    _write(OUT / "panel.csv", FIELDS, rows)
    _write(OUT / "panel_exclusions.csv", ("unit", "year", "field", "reason"), excl)
    print(f"panel rows {len(rows)}, exclusions {len(excl)}")


if __name__ == "__main__":
    main()
