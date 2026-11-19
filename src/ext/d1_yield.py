"""D1 part 1: pooled State yield of active case finding per data year, empirical-Bayes
shrinkage, rank intervals and tiers (extension plan sections 3.3, 4.1, 4.2 and 9).

Run as `python -I src/ext/d1_yield.py` to write, under outputs/ext/ (UTF-8, LF):
  d1_pooled.csv    one row per analysis (each data year, and the pooled 2021-2023 yield);
  d1_states.csv    one row per unit in each analysis (posterior, rank interval, tier);
  d1_excluded.csv  unit-years left out of each analysis, with the reason (section 3.3).
Columns are documented in outputs/ext/README.md.

The intensity-stratum repeat of the 2021-2023 tiers (section 4.2, last bullet) needs the
strata of section 4.5, which Task 4 builds (`d1_saturation.intensity_strata`); it is run
there or later through `analyse_pooled(units=...)`, not here.
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python -I src/ext/d1_yield.py`
    sys.path.insert(0, str(ROOT))

from src.ext import panel  # noqa: E402

OUT = ROOT / "outputs" / "ext"
SEED = 20261119
DRAWS = 10000
YEARS = (2018, 2019, 2021, 2022, 2023)
POOLED_YEARS = (2021, 2022, 2023)
Z = float(stats.norm.ppf(0.975))
PER = 100000.0  # yield scale: 100,000 x exp(log-yield)


# ---------------------------------------------------------------- estimators (4.1, 4.2)

def dl_pool(y: np.ndarray, v: np.ndarray) -> dict:
    """DerSimonian-Laird random-effects pooling (section 4.1).

    Returns mu, se, ci, tau2, i2, pi (None if k < 3), k, q and mu_fixed, all on the
    scale of y."""
    y = np.asarray(y, dtype=float)
    v = np.asarray(v, dtype=float)
    k = int(y.size)
    if k == 0 or np.any(v <= 0):
        raise ValueError("dl_pool needs k >= 1 and every variance > 0")
    w = 1.0 / v
    sw = float(np.sum(w))
    mu_f = float(np.sum(w * y)) / sw
    q = float(np.sum(w * (y - mu_f) ** 2))
    c = sw - float(np.sum(w * w)) / sw
    tau2 = max(0.0, (q - (k - 1)) / c) if c > 0 else 0.0
    i2 = max(0.0, (q - (k - 1)) / q) * 100.0 if q > 0 else 0.0
    ws = 1.0 / (v + tau2)
    sws = float(np.sum(ws))
    mu = float(np.sum(ws * y)) / sws
    se = math.sqrt(1.0 / sws)
    ci = (mu - Z * se, mu + Z * se)
    if k >= 3:
        half = float(stats.t.ppf(0.975, k - 2)) * math.sqrt(tau2 + se * se)
        pi = (mu - half, mu + half)
    else:
        pi = None
    return {"mu": mu, "se": se, "ci": ci, "tau2": tau2, "i2": i2, "pi": pi, "k": k,
            "q": q, "mu_fixed": mu_f}


def eb_shrink(y, v, mu: float, tau2: float) -> tuple:
    """Plug-in empirical-Bayes posterior (section 4.2): mean B*mu + (1-B)*y with
    B = v/(v + tau2), and SD sqrt(v*tau2/(v + tau2)). tau2 = 0 gives mu and SD 0."""
    y = np.asarray(y, dtype=float)
    v = np.asarray(v, dtype=float)
    if tau2 == 0:
        return np.full(y.shape, mu, dtype=float), np.zeros(y.shape, dtype=float)
    b = v / (v + tau2)
    return b * mu + (1.0 - b) * y, np.sqrt(v * tau2 / (v + tau2))


def rank_intervals(post_mean, post_sd, rng, draws: int = DRAWS) -> tuple:
    """Parametric rank intervals (section 4.2). Rank 1 is the highest yield; the rank in a
    draw is 1 + the number of units with a strictly greater draw. Returns (lo, hi) as
    integer arrays (2.5th and 97.5th percentiles, method "inverted_cdf")."""
    m = np.asarray(post_mean, dtype=float)
    sd = np.asarray(post_sd, dtype=float)
    n = m.size
    zd = rng.standard_normal((draws, n))  # one call, as section 4.2 states
    theta = m + sd * zd
    ranks = 1 + np.sum(theta[:, None, :] > theta[:, :, None], axis=2)
    lo, hi = np.quantile(ranks, [0.025, 0.975], axis=0, method="inverted_cdf")
    return lo.astype(int), hi.astype(int)


def tier(lo_ci: float, hi_ci: float, mu: float) -> str:
    """Tier from the State's own posterior interval against the pooled mean (section 4.2)."""
    if lo_ci > mu:
        return "above"
    if hi_ci < mu:
        return "below"
    return "overlaps"


def classify(y, v, mu: float, tau2: float) -> tuple:
    """Posterior, its 95% interval m +/- z*sd, and the tier of each unit."""
    m, sd = eb_shrink(y, v, mu, tau2)
    lo, hi = m - Z * sd, m + Z * sd
    return m, sd, lo, hi, [tier(a, b, mu) for a, b in zip(lo, hi)]


# ---------------------------------------------------------------- samples (3.3)

def _reason(r: dict) -> str | None:
    """Why a unit-year cannot enter a log-scale analysis (section 3.3), or None."""
    S, D = r["screened"], r["diagnosed"]
    out = []
    if S is None:
        out.append("screened NA in the source; not imputed")
    if D is None:
        out.append("diagnosed NA in the source; not imputed")
    if S == 0:
        out.append("zero screened as printed (inconsistent row, S = 0)")
    if D == 0:
        out.append("zero diagnoses as printed; excluded from log-scale analyses (section 3.3)")
    if S is not None and D is not None and S > 0 and D >= S:
        out.append("inconsistent row (D >= S): log-yield variance undefined or <= 0")
    return "; ".join(out) if out else None


def _rows(rows, units):
    rows = panel.load_panel() if rows is None else rows
    if units is not None:
        keep = set(units)
        rows = [r for r in rows if r["unit"] in keep]
    return rows


def year_sample(year: int, rows=None, units=None) -> tuple:
    """(units, D, S, excluded) for one data year: units sorted by name; excluded is a list
    of {unit, year, reason} for unit-years left out, including units with no row."""
    rows = _rows(rows, units)
    all_units = sorted({r["unit"] for r in rows})
    by_unit = {r["unit"]: r for r in rows if r["year"] == year}
    keep, D, S, excl = [], [], [], []
    for u in all_units:
        r = by_unit.get(u)
        if r is None:
            excl.append({"unit": u, "year": year,
                         "reason": "no row in this year's ACF table (unbalanced panel)"})
            continue
        why = _reason(r)
        if why:
            excl.append({"unit": u, "year": year, "reason": why})
            continue
        keep.append(u)
        D.append(r["diagnosed"])
        S.append(r["screened"])
    return keep, np.array(D, dtype=float), np.array(S, dtype=float), excl


def pooled_sample(years=POOLED_YEARS, rows=None, units=None) -> tuple:
    """(units, sum D, sum S, years per unit, excluded) for the pooled yield
    ln(sum D / sum S) over the unit-years of `years` that pass section 3.3."""
    rows = _rows(rows, units)
    years = tuple(sorted(years))
    sums: dict = {}
    excl = []
    for u in sorted({r["unit"] for r in rows}):
        got = {r["year"]: r for r in rows if r["unit"] == u and r["year"] in years}
        for y in years:
            r = got.get(y)
            if r is None:
                excl.append({"unit": u, "year": y,
                             "reason": "no row in this year's ACF table (unbalanced panel)"})
                continue
            why = _reason(r)
            if why:
                excl.append({"unit": u, "year": y, "reason": why})
                continue
            d, s, ys = sums.get(u, (0, 0, []))
            sums[u] = (d + r["diagnosed"], s + r["screened"], ys + [y])
        if u not in sums:
            excl.append({"unit": u, "year": "",
                         "reason": "no unit-year in " + ";".join(map(str, years))
                                   + " passes section 3.3; unit has no pooled value"})
    keep = sorted(sums)
    D = np.array([sums[u][0] for u in keep], dtype=float)
    S = np.array([sums[u][1] for u in keep], dtype=float)
    yrs = [sums[u][2] for u in keep]
    for u, d, s in zip(keep, D, S):
        if d >= s:  # cannot happen when every unit-year passes, kept as a guard
            raise ValueError(f"{u}: pooled D >= S")
    return keep, D, S, yrs, excl


# ---------------------------------------------------------------- analysis

def _analyse(units, D, S) -> tuple:
    """Pooling, posterior, ranks and tiers for one analysis. The generator is reset
    here (section 9: one rank-draw set is one analysis)."""
    y = np.log(D / S)
    v = 1.0 / D - 1.0 / S
    pool = dl_pool(y, v)
    m, sd, lo, hi, tiers = classify(y, v, pool["mu"], pool["tau2"])
    rng = np.random.default_rng(SEED)
    rlo, rhi = rank_intervals(m, sd, rng, DRAWS)
    states = []
    for i, u in enumerate(units):
        states.append({"unit": u, "diagnosed": int(D[i]), "screened": int(S[i]),
                       "y_log": float(y[i]), "v_log": float(v[i]),
                       "post_mean_log": float(m[i]), "post_sd_log": float(sd[i]),
                       "post_lo_log": float(lo[i]), "post_hi_log": float(hi[i]),
                       "rank_lo": int(rlo[i]), "rank_hi": int(rhi[i]), "tier": tiers[i]})
    return pool, states


def analyse_year(year: int, rows=None, units=None) -> tuple:
    """(pool, states, excluded) for one data year."""
    keep, D, S, excl = year_sample(year, rows, units)
    pool, states = _analyse(keep, D, S)
    return pool, states, excl


def analyse_pooled(years=POOLED_YEARS, rows=None, units=None) -> tuple:
    """(pool, states, excluded) for the pooled yield over `years` (main: 2021-2023).
    `units` restricts the sample (e.g. one intensity stratum, section 4.2)."""
    keep, D, S, yrs, excl = pooled_sample(years, rows, units)
    pool, states = _analyse(keep, D, S)
    for st, ys in zip(states, yrs):
        st["years"] = ";".join(map(str, ys))
        st["n_years"] = len(ys)
    return pool, states, excl


_POOLED: dict = {}


def pooled_posterior(years=POOLED_YEARS) -> dict:
    """unit -> (posterior mean, plug-in posterior SD) of the pooled log-yield."""
    key = tuple(sorted(years))
    if key not in _POOLED:
        _, states, _ = analyse_pooled(key)
        _POOLED[key] = {s["unit"]: (s["post_mean_log"], s["post_sd_log"]) for s in states}
    return _POOLED[key]


def pooled_state_yield(unit: str) -> tuple:
    """(posterior mean, plug-in posterior SD) of the unit's pooled 2021-2023 log-yield
    ln(sum D / sum S), shrunk as in section 4.2 (the D2 measure, section 5.1).
    (None, None) if the unit has no unit-year that passes section 3.3."""
    return pooled_posterior(POOLED_YEARS).get(unit, (None, None))


# ---------------------------------------------------------------- outputs

POOLED_FIELDS = ("analysis", "k", "n_units_without_value", "n_listed", "mu_log", "se_log", "ci_lo_log", "ci_hi_log",
                 "pi_lo_log", "pi_hi_log", "yield_per_100k", "ci_lo_per_100k",
                 "ci_hi_per_100k", "pi_lo_per_100k", "pi_hi_per_100k", "tau2", "i2", "q",
                 "n_above", "n_overlaps", "n_below")
STATE_FIELDS = ("analysis", "unit", "small_ut", "years", "n_years", "diagnosed", "screened",
                "y_log", "v_log", "post_mean_log", "post_sd_log", "post_lo_log",
                "post_hi_log", "post_per_100k", "post_lo_per_100k", "post_hi_per_100k",
                "rank_lo", "rank_hi", "n_ranked", "tier")
EXCL_FIELDS = ("analysis", "unit", "year", "reason")


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
            w.writerow([_fmt(r.get(k)) for k in fields])


def _ex(x: float) -> float:
    return PER * math.exp(x)


def build() -> tuple:
    rows = panel.load_panel()
    small = {r["unit"]: r["small_ut"] for r in rows}
    pooled_out, states_out, excl_out = [], [], []
    runs = [(str(y), *analyse_year(y, rows)) for y in YEARS]
    runs.append(("2021-2023", *analyse_pooled(POOLED_YEARS, rows)))
    for label, pool, states, excl in runs:
        mu = pool["mu"]
        counts = {t: sum(s["tier"] == t for s in states) for t in ("above", "overlaps", "below")}
        pooled_out.append({
            "analysis": label, "k": pool["k"],
            "n_units_without_value": len({r["unit"] for r in rows}) - pool["k"],
            "n_listed": len(excl),
            "mu_log": mu, "se_log": pool["se"], "ci_lo_log": pool["ci"][0],
            "ci_hi_log": pool["ci"][1], "pi_lo_log": pool["pi"][0],
            "pi_hi_log": pool["pi"][1], "yield_per_100k": _ex(mu),
            "ci_lo_per_100k": _ex(pool["ci"][0]), "ci_hi_per_100k": _ex(pool["ci"][1]),
            "pi_lo_per_100k": _ex(pool["pi"][0]), "pi_hi_per_100k": _ex(pool["pi"][1]),
            "tau2": pool["tau2"], "i2": pool["i2"], "q": pool["q"],
            "n_above": counts["above"], "n_overlaps": counts["overlaps"],
            "n_below": counts["below"]})
        for s in states:
            row = dict(s)
            row.update({"analysis": label, "small_ut": small[s["unit"]],
                        "post_per_100k": _ex(s["post_mean_log"]),
                        "post_lo_per_100k": _ex(s["post_lo_log"]),
                        "post_hi_per_100k": _ex(s["post_hi_log"]),
                        "n_ranked": len(states)})
            if label != "2021-2023":
                row["years"], row["n_years"] = label, 1
            states_out.append(row)
        for e in excl:
            excl_out.append({"analysis": label, **e})
    return pooled_out, states_out, excl_out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pooled_out, states_out, excl_out = build()
    _write(OUT / "d1_pooled.csv", POOLED_FIELDS, pooled_out)
    _write(OUT / "d1_states.csv", STATE_FIELDS, states_out)
    _write(OUT / "d1_excluded.csv", EXCL_FIELDS, excl_out)
    for p in pooled_out:
        print(f"{p['analysis']:>9}  k={p['k']:2d}  yield/100k={p['yield_per_100k']:.1f} "
              f"[{p['ci_lo_per_100k']:.1f}, {p['ci_hi_per_100k']:.1f}]  "
              f"tau2={p['tau2']:.3f}  I2={p['i2']:.1f}  "
              f"above/overlaps/below={p['n_above']}/{p['n_overlaps']}/{p['n_below']}")


if __name__ == "__main__":
    main()
