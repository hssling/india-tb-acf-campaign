"""Recompute the headline values of the extension (outputs/ext/) from the panel, with code
of this file only (numpy and scipy; nothing of src/ext/ is imported).

Run as: python -I verification/check_ext_outputs.py

Tolerance 1e-6. What is recomputed, from data/ext/panel.csv:

(a) the national totals of the panel (sum of screened and of diagnosed over its units) per
    year against the India rows of outputs/q3_yield_summary.csv. The 2022 gap (ITR 2023
    State rows do not sum to that table's India row) is tolerated only when every 2022
    panel row carries the flag itr2023_states_not_india; any other gap fails.
(b) outputs/ext/d1_pooled.csv: the DerSimonian-Laird pooled mean, tau^2 and I^2 of each
    year (2018, 2019, 2021, 2022, 2023) and of the 2021-2023 pooling (plan section 4.1).
(c) outputs/ext/d1_elasticity.csv, row "main": the within-State elasticity (weighted least
    squares of ln D on ln S with unit and year effects, weights D, zeros excluded, units
    with one row dropped; plan section 4.3).
(d) outputs/ext/d2_alignment.csv, row "main": the weighted Spearman correlation of
    campaign exposure with the pooled 2021-2023 empirical-Bayes yield (plan section 5.1).
(e) outputs/ext/d3.csv, row "main": theta, the within-State association of public
    notifications with ACF diagnoses (plan section 6).
(f) outputs/ext/headline.csv: the three labels (plan section 8), recomputed from the
    main value and interval of headline.csv and the values of outputs/ext/spec_curve.csv:
    "supported" only if the main interval excludes the null and at least 80% of the
    whole grid lies strictly on the main estimate's side of the null (an entry exactly at
    the null does not agree; one that cannot be computed counts as not agreeing). The
    agreement counts and the headline main values are also compared with the grid.
(g) outputs/ext/headline.csv against its source rows: the main value and interval of each
    headline equal the estimate and bootstrap interval of the main row of
    d1_elasticity.csv (epsilon), d2_alignment.csv (rho) and d3.csv (theta), so an interval
    and its label cannot be edited together in headline.csv alone.
(h) outputs/ext/d1_elasticity_samedef.csv (post hoc, plan section 10, 20 November 2026): the
    model of (c) on the data years 2019 and 2021 only (the same printed screened heading).

NOT re-derived here: every bootstrap and permutation interval and band. They are
reproduced by the seeded build (src/ext/d1_saturation.py, d2_targeting.py,
d3_additionality.py, robustness.py); this check reads the intervals as printed.
"""
import csv
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-6
YEARS = (2018, 2019, 2021, 2022, 2023)
POOLED = (2021, 2022, 2023)
Z = float(stats.norm.ppf(0.975))
NULLS = {"epsilon": 1.0, "rho": 0.0, "theta": 0.0}
GRID = {"epsilon": 24, "rho": 24, "theta": 16}
THRESHOLD = 0.8
GAP_FLAG = "itr2023_states_not_india"
SAME_DEFINITION_YEARS = (2019, 2021)  # post hoc (plan section 10, 20 November 2026)


# ------------------------------------------------------------------ input

def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _int(s: str):
    s = s.strip()
    return int(float(s)) if s else None


def _flt(s: str):
    s = s.strip()
    return float(s) if s else None


def load_panel(root: Path) -> list[dict]:
    out = []
    for r in read(root / "data" / "ext" / "panel.csv"):
        out.append({"unit": r["unit"], "year": int(r["year"]), "S": _int(r["screened"]),
                    "D": _int(r["diagnosed"]), "Npub": _int(r["notified_public"]),
                    "E": _flt(r["exposure_reconstructed"]), "flags": r["flags"]})
    return out


def _close(got, want, what: str, bad: list) -> None:
    if got is None or want is None or not (abs(got - want) <= TOL):
        bad.append(f"{what}: printed {got} but recomputed {want}")


# ------------------------------------------------------------------ (a) national totals

def total_problems(root: Path, panel: list) -> list[str]:
    bad: list[str] = []
    india = {}
    for r in read(root / "outputs" / "q3_yield_summary.csv"):
        if r["state"] == "India" and r["indicator"] == "yield_diagnosed_per_100000":
            india[int(r["year"])] = (int(r["numerator"]), int(r["denominator"]))
    for year in YEARS:
        rows = [r for r in panel if r["year"] == year]
        D = sum(r["D"] for r in rows if r["D"] is not None)
        S = sum(r["S"] for r in rows if r["S"] is not None)
        if year not in india:
            bad.append(f"{year}: no India row in outputs/q3_yield_summary.csv")
            continue
        d_in, s_in = india[year]
        if (D, S) == (d_in, s_in):
            continue
        flagged = bool(rows) and all(GAP_FLAG in r["flags"].split(";") for r in rows)
        if year == 2022 and flagged:
            continue  # the ITR 2023 sum gap, flagged on every row of that year
        bad.append(f"{year}: panel totals D={D}, S={S} differ from the India row "
                   f"D={d_in}, S={s_in} and the gap is not the flagged ITR 2023 gap")
    return bad


# ------------------------------------------------------------------ (b) DL pooling

def _passes(r: dict) -> bool:
    S, D = r["S"], r["D"]
    return S is not None and D is not None and S > 0 and D > 0 and D < S


def dl(y: np.ndarray, v: np.ndarray) -> dict:
    w = 1.0 / v
    k = len(y)
    muf = np.sum(w * y) / np.sum(w)
    q = float(np.sum(w * (y - muf) ** 2))
    c = float(np.sum(w) - np.sum(w * w) / np.sum(w))
    tau2 = max(0.0, (q - (k - 1)) / c)
    i2 = 100.0 * max(0.0, (q - (k - 1)) / q) if q > 0 else 0.0
    ws = 1.0 / (v + tau2)
    return {"mu": float(np.sum(ws * y) / np.sum(ws)), "tau2": tau2, "i2": i2, "k": k}


def year_sample(panel: list, year: int):
    rs = sorted((r for r in panel if r["year"] == year and _passes(r)),
                key=lambda r: r["unit"])
    D = np.array([r["D"] for r in rs], dtype=float)
    S = np.array([r["S"] for r in rs], dtype=float)
    return [r["unit"] for r in rs], D, S


def pooled_sample(panel: list):
    sums: dict = {}
    for r in panel:
        if r["year"] in POOLED and _passes(r):
            d, s = sums.get(r["unit"], (0, 0))
            sums[r["unit"]] = (d + r["D"], s + r["S"])
    units = sorted(sums)
    return (units, np.array([sums[u][0] for u in units], dtype=float),
            np.array([sums[u][1] for u in units], dtype=float))


def pooled_problems(root: Path, panel: list) -> tuple[list[str], int]:
    bad: list[str] = []
    printed = {r["analysis"]: r for r in read(root / "outputs" / "ext" / "d1_pooled.csv")}
    n = 0
    for label in [str(y) for y in YEARS] + ["2021-2023"]:
        row = printed.get(label)
        if row is None:
            bad.append(f"d1_pooled {label}: row missing")
            continue
        _, D, S = pooled_sample(panel) if label == "2021-2023" else \
            year_sample(panel, int(label))
        fit = dl(np.log(D / S), 1.0 / D - 1.0 / S)
        if int(row["k"]) != fit["k"]:
            bad.append(f"d1_pooled {label}: k printed {row['k']} but recomputed {fit['k']}")
        for col, key in (("mu_log", "mu"), ("tau2", "tau2"), ("i2", "i2")):
            _close(float(row[col]), fit[key], f"d1_pooled {label} {col}", bad)
        n += 1
    return bad, n


def pooled_eb(panel: list) -> dict:
    """Plug-in empirical-Bayes posterior mean of the pooled 2021-2023 log-yield, by unit."""
    units, D, S = pooled_sample(panel)
    y, v = np.log(D / S), 1.0 / D - 1.0 / S
    fit = dl(y, v)
    B = v / (v + fit["tau2"])
    return dict(zip(units, B * fit["mu"] + (1.0 - B) * y))


# ------------------------------------------------------------------ (c), (e) fixed-effects WLS

def fe_slope(units, years, x, y, w) -> tuple[float, int]:
    """Slope of x in y ~ x + unit effects + year effects (the earliest year is the
    reference), by weighted least squares; units with one row are dropped first."""
    units, years = np.asarray(units), np.asarray(years)
    x, y, w = (np.asarray(a, dtype=float) for a in (x, y, w))
    names, counts = np.unique(units, return_counts=True)
    keep = np.isin(units, names[counts > 1])
    units, years, x, y, w = units[keep], years[keep], x[keep], y[keep], w[keep]
    names = np.unique(units)
    yrs = np.unique(years)
    cols = [x] + [(units == u).astype(float) for u in names] \
        + [(years == t).astype(float) for t in yrs[1:]]
    X = np.column_stack(cols)
    sw = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return float(coef[0]), int(len(names))


def elasticity_main(panel: list, years: tuple | None = None) -> tuple[float, int]:
    use = [r for r in panel if _passes(r) and (years is None or r["year"] in years)]
    return fe_slope([r["unit"] for r in use], [r["year"] for r in use],
                    [math.log(r["S"]) for r in use], [math.log(r["D"]) for r in use],
                    [r["D"] for r in use])


def theta_main(panel: list) -> tuple[float, int]:
    use = [r for r in panel if r["year"] in (2019, 2022, 2023) and r["D"] is not None
           and r["Npub"] is not None and r["Npub"] > 0]
    return fe_slope([r["unit"] for r in use], [r["year"] for r in use],
                    [r["D"] for r in use], [r["Npub"] for r in use],
                    [1.0 / r["Npub"] for r in use])


# ------------------------------------------------------------------ (d) weighted Spearman

def weighted_spearman(x, y, w) -> float:
    rx = stats.rankdata(x, method="average")
    ry = stats.rankdata(y, method="average")
    w = np.asarray(w, dtype=float)
    dx = rx - np.sum(w * rx) / np.sum(w)
    dy = ry - np.sum(w * ry) / np.sum(w)
    return float(np.sum(w * dx * dy) / math.sqrt(np.sum(w * dx * dx) * np.sum(w * dy * dy)))


def rho_main(panel: list) -> tuple[float, int]:
    eb = pooled_eb(panel)
    s23 = {r["unit"]: r["S"] for r in panel if r["year"] == 2023}
    e = {}
    for r in panel:
        e.setdefault(r["unit"], r["E"])
    use = [u for u in sorted(eb) if e.get(u) is not None and s23.get(u) is not None]
    return (weighted_spearman([e[u] for u in use], [eb[u] for u in use],
                              [s23[u] for u in use]), len(use))


# ------------------------------------------------------------------ (f) labels

def label_of(main: float, lo: float, hi: float, null: float, values: list) -> tuple:
    """(label, n_agree): section 8. values: grid entries, None when not computable."""
    def agree(v):
        return v is not None and ((v > null and main > null) or (v < null and main < null))
    n_agree = sum(agree(v) for v in values)
    excludes = lo > null or hi < null
    share = n_agree / len(values)
    return ("supported" if excludes and share >= THRESHOLD else "not established"), n_agree


def label_problems(root: Path) -> tuple[list[str], int]:
    bad: list[str] = []
    head = {r["estimate"]: r for r in read(root / "outputs" / "ext" / "headline.csv")}
    curve = read(root / "outputs" / "ext" / "spec_curve.csv")
    n = 0
    for est, null in NULLS.items():
        row = head.get(est)
        ent = [c for c in curve if c["estimate"] == est]
        if row is None:
            bad.append(f"headline {est}: row missing")
            continue
        if len(ent) != GRID[est]:
            bad.append(f"spec_curve {est}: {len(ent)} entries, the registered grid has "
                       f"{GRID[est]}")
            continue
        main_rows = [c for c in ent if c["main"] == "yes"]
        values = [_flt(c["value"]) if c["computable"] == "yes" else None for c in ent]
        if len(main_rows) != 1:
            bad.append(f"spec_curve {est}: {len(main_rows)} main entries, expected 1")
            continue
        main, lo, hi = (float(row[k]) for k in ("main_value", "ci_lo", "ci_hi"))
        _close(_flt(main_rows[0]["value"]), main, f"spec_curve {est} main entry vs headline",
               bad)
        if float(row["null"]) != null:
            bad.append(f"headline {est}: null printed {row['null']}, registered {null}")
        label, k = label_of(main, lo, hi, null, values)
        if row["label"] != label:
            bad.append(f"headline {est}: label printed {row['label']!r} but section 8 gives "
                       f"{label!r} ({k}/{len(ent)} entries agree; interval "
                       f"[{lo:.6f}, {hi:.6f}], null {null})")
        if int(row["n_agree"]) != k or int(row["n_entries"]) != len(ent):
            bad.append(f"headline {est}: n_agree/n_entries printed {row['n_agree']}/"
                       f"{row['n_entries']} but the grid gives {k}/{len(ent)}")
        n += 1
    return bad, n


# ------------------------------------------------------------------ (g) headline sources

HEADLINE_SOURCES = {"epsilon": "d1_elasticity.csv", "rho": "d2_alignment.csv",
                    "theta": "d3.csv"}


def headline_source_problems(root: Path) -> list[str]:
    bad: list[str] = []
    out = root / "outputs" / "ext"
    head = {r["estimate"]: r for r in read(out / "headline.csv")}
    for est, name in HEADLINE_SOURCES.items():
        if est not in head:
            continue  # reported by label_problems
        src = next(r for r in read(out / name) if r["analysis"] == "main")
        for hcol, scol in (("main_value", "estimate"), ("ci_lo", "boot_lo"),
                           ("ci_hi", "boot_hi")):
            _close(_flt(head[est][hcol]), _flt(src[scol]),
                   f"headline {est} {hcol} vs {name} main {scol}", bad)
    return bad


# ------------------------------------------------------------------ driver

def problems(root: Path = ROOT) -> tuple[list[str], dict]:
    panel = load_panel(root)
    bad = total_problems(root, panel)
    b, n_pool = pooled_problems(root, panel)
    bad += b
    out = root / "outputs" / "ext"
    eps, g = elasticity_main(panel)
    row = next(r for r in read(out / "d1_elasticity.csv") if r["analysis"] == "main")
    _close(float(row["estimate"]), eps, "d1_elasticity main estimate", bad)
    if int(row["n_units"]) != g:
        bad.append(f"d1_elasticity main: n_units {row['n_units']} but recomputed {g}")
    eps2, g2 = elasticity_main(panel, SAME_DEFINITION_YEARS)
    row = next(r for r in read(out / "d1_elasticity_samedef.csv")
               if r["analysis"] == "same screened definition (post hoc)")
    _close(float(row["estimate"]), eps2, "d1_elasticity_samedef estimate", bad)
    if int(row["n_units"]) != g2 or row["years"] != ";".join(map(str, SAME_DEFINITION_YEARS)):
        bad.append(f"d1_elasticity_samedef: n_units {row['n_units']}, years {row['years']} but "
                   f"recomputed {g2} units over {SAME_DEFINITION_YEARS}")
    rho, n_rho = rho_main(panel)
    row = next(r for r in read(out / "d2_alignment.csv") if r["analysis"] == "main")
    _close(float(row["estimate"]), rho, "d2_alignment main rho", bad)
    if int(row["n"]) != n_rho:
        bad.append(f"d2_alignment main: n {row['n']} but recomputed {n_rho}")
    theta, g3 = theta_main(panel)
    row = next(r for r in read(out / "d3.csv") if r["analysis"] == "main")
    _close(float(row["estimate"]), theta, "d3 main theta", bad)
    if int(row["n_units"]) != g3:
        bad.append(f"d3 main: n_units {row['n_units']} but recomputed {g3}")
    b, n_lab = label_problems(root)
    b += headline_source_problems(root)
    return bad + b, {"pooled": n_pool, "labels": n_lab, "epsilon": eps, "rho": rho,
                     "theta": theta, "epsilon_samedef": eps2}


def main(root: Path = ROOT) -> int:
    bad, n = problems(root)
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    print(f"OK: panel totals match the India rows (2022 ITR 2023 gap flagged); "
          f"{n['pooled']} DL poolings (mu, tau2, I2), epsilon {n['epsilon']:.6f} "
          f"(post hoc same heading {n['epsilon_samedef']:.6f}), rho {n['rho']:.6f}, theta {n['theta']:.6f} reproduced; {n['labels']} headline "
          f"labels recomputed from the grid by section 8; headline values and intervals "
          f"equal their source rows (bootstrap and permutation intervals not re-derived: "
          f"reproduced by the seeded build)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
