"""D1 part 1: pooled State yield of active case finding per data year, empirical-Bayes
shrinkage, rank intervals and tiers (extension plan sections 3.3, 4.1, 4.2 and 9).

Run as `python -I src/ext/d1_yield.py` to write, under outputs/ext/ (UTF-8, LF):
  d1_pooled.csv    one row per analysis (each data year, and the pooled 2021-2023 yield);
  d1_states.csv    one row per unit in each analysis (posterior, rank interval, tier);
  d1_excluded.csv  unit-years left out of each analysis, with the reason (section 3.3);
  d1_states_betweenyear.csv, d1_pooled_betweenyear.csv
                   POST HOC sensitivity (plan section 10, 19 November 2026): tiers and
                   ranks with a within-State random-effects mean over 2021-2023 that
                   includes between-year variation, beside the registered tiers.
Columns are documented in outputs/ext/README.md.

The intensity-stratum repeat of the 2021-2023 tiers (section 4.2, last bullet) needs the
strata of section 4.5, which Task 4 builds (`d1_saturation.intensity_strata`); it is run
there or later through `analyse_pooled(units=...)`, not here.
"""
from __future__ import annotations

import csv
import io
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

def _analyse(units, D, S, y=None, v=None) -> tuple:
    """Pooling, posterior, ranks and tiers for one analysis. The generator is reset
    here (section 9: one rank-draw set is one analysis). y and v default to ln(D/S) and
    1/D - 1/S; the post hoc between-year sensitivity passes its own."""
    if y is None:
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


# ------------------------------------- POST HOC: between-year sensitivity (plan section 10)
# Added 19 November 2026, after registration and after the registered tiers were seen.
# The registered pooled yield ln(sum D / sum S) has binomial variance only. Here each
# unit's usable 2021-2023 yearly log-yields are combined by a within-State
# DerSimonian-Laird random-effects mean, whose SE includes between-year variation; the
# section 4.2 cross-State procedure is then applied unchanged.

BETWEEN_LABEL = "2021-2023 between-year (post hoc)"


def within_state_yield(D, S) -> tuple:
    """(log-yield, SE, within-State tau2) from one unit's yearly counts: a DL
    random-effects mean of ln(D_t/S_t) with variances 1/D_t - 1/S_t. A single year
    keeps its own value and binomial SE, and tau2 is None."""
    D = np.asarray(D, dtype=float)
    S = np.asarray(S, dtype=float)
    y = np.log(D / S)
    v = 1.0 / D - 1.0 / S
    if y.size == 1:
        return float(y[0]), math.sqrt(float(v[0])), None
    r = dl_pool(y, v)
    return r["mu"], r["se"], r["tau2"]


def analyse_betweenyear(years=POOLED_YEARS, rows=None, units=None) -> tuple:
    """(pool, states, excluded) for the post hoc sensitivity. The units, contributing
    unit-years and exclusions are those of `pooled_sample`. Each state row also has
    `single_year` (flag) and `within_tau2`."""
    rows = _rows(rows, units)
    keep, D, S, yrs, excl = pooled_sample(years, rows)
    by = {(r["unit"], r["year"]): r for r in rows}
    ys, vs, t2s = [], [], []
    for u, yl in zip(keep, yrs):
        y, se, t2 = within_state_yield([by[(u, t)]["diagnosed"] for t in yl],
                                       [by[(u, t)]["screened"] for t in yl])
        ys.append(y)
        vs.append(se * se)
        t2s.append(t2)
    pool, states = _analyse(keep, D, S, np.array(ys), np.array(vs))
    for st, yl, t2 in zip(states, yrs, t2s):
        st["years"] = ";".join(map(str, yl))
        st["n_years"] = len(yl)
        st["single_year"] = len(yl) == 1
        st["within_tau2"] = t2
    return pool, states, excl


# ---------------------------------------------------------------- outputs

POOLED_FIELDS = ("analysis", "k", "n_units_without_value", "n_listed", "mu_log", "se_log",
                 "ci_lo_log", "ci_hi_log",
                 "pi_lo_log", "pi_hi_log", "yield_per_100k", "ci_lo_per_100k",
                 "ci_hi_per_100k", "pi_lo_per_100k", "pi_hi_per_100k", "tau2", "i2", "q",
                 "n_above", "n_overlaps", "n_below")
STATE_FIELDS = ("analysis", "unit", "small_ut", "years", "n_years", "diagnosed", "screened",
                "y_log", "v_log", "post_mean_log", "post_sd_log", "post_lo_log",
                "post_hi_log", "post_per_100k", "post_lo_per_100k", "post_hi_per_100k",
                "rank_lo", "rank_hi", "n_ranked", "tier")
EXCL_FIELDS = ("analysis", "unit", "year", "reason")
BETWEEN_FIELDS = STATE_FIELDS + ("tier_registered", "tier_agrees", "single_year",
                                 "within_tau2")
BETWEEN_POOLED_FIELDS = POOLED_FIELDS + ("n_single_year", "n_tier_agrees", "robust_above",
                                         "robust_overlaps", "robust_below")
TIERS = ("above", "overlaps", "below")


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def render(fields: tuple, rows: list) -> str:
    """CSV text (LF line endings) exactly as written to disk."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        w.writerow([_fmt(r.get(k)) for k in fields])
    return buf.getvalue()


def _ex(x: float) -> float:
    return PER * math.exp(x)


def _pooled_row(label, pool, states, excl, n_units) -> dict:
    mu = pool["mu"]
    counts = {t: sum(s["tier"] == t for s in states) for t in TIERS}
    return {
        "analysis": label, "k": pool["k"],
        "n_units_without_value": n_units - pool["k"],
        "n_listed": len(excl),
        "mu_log": mu, "se_log": pool["se"], "ci_lo_log": pool["ci"][0],
        "ci_hi_log": pool["ci"][1], "pi_lo_log": pool["pi"][0],
        "pi_hi_log": pool["pi"][1], "yield_per_100k": _ex(mu),
        "ci_lo_per_100k": _ex(pool["ci"][0]), "ci_hi_per_100k": _ex(pool["ci"][1]),
        "pi_lo_per_100k": _ex(pool["pi"][0]), "pi_hi_per_100k": _ex(pool["pi"][1]),
        "tau2": pool["tau2"], "i2": pool["i2"], "q": pool["q"],
        "n_above": counts["above"], "n_overlaps": counts["overlaps"],
        "n_below": counts["below"]}


def _state_row(s, label, small, n) -> dict:
    row = dict(s)
    row.update({"analysis": label, "small_ut": small[s["unit"]],
                "post_per_100k": _ex(s["post_mean_log"]),
                "post_lo_per_100k": _ex(s["post_lo_log"]),
                "post_hi_per_100k": _ex(s["post_hi_log"]),
                "n_ranked": n})
    return row


def build() -> dict:
    """file name -> CSV text for every file under outputs/ext written by this module."""
    rows = panel.load_panel()
    small = {r["unit"]: r["small_ut"] for r in rows}
    n_units = len({r["unit"] for r in rows})
    pooled_out, states_out, excl_out = [], [], []
    runs = [(str(y), *analyse_year(y, rows)) for y in YEARS]
    runs.append(("2021-2023", *analyse_pooled(POOLED_YEARS, rows)))
    registered_tier = {}
    for label, pool, states, excl in runs:
        pooled_out.append(_pooled_row(label, pool, states, excl, n_units))
        for s in states:
            row = _state_row(s, label, small, len(states))
            if label != "2021-2023":
                row["years"], row["n_years"] = label, 1
            else:
                registered_tier[s["unit"]] = s["tier"]
            states_out.append(row)
        for e in excl:
            excl_out.append({"analysis": label, **e})

    # post hoc between-year sensitivity, beside the registered pooled tiers
    pool, states, excl = analyse_betweenyear(POOLED_YEARS, rows)
    between_out = []
    for s in states:
        row = _state_row(s, BETWEEN_LABEL, small, len(states))
        row["tier_registered"] = registered_tier[s["unit"]]
        row["tier_agrees"] = row["tier"] == row["tier_registered"]
        between_out.append(row)
    summary = _pooled_row(BETWEEN_LABEL, pool, states, excl, n_units)
    summary["n_single_year"] = sum(r["single_year"] for r in between_out)
    summary["n_tier_agrees"] = sum(r["tier_agrees"] for r in between_out)
    for t in TIERS:
        summary["robust_" + t] = sum(r["tier_agrees"] and r["tier"] == t for r in between_out)

    return {"d1_pooled.csv": render(POOLED_FIELDS, pooled_out),
            "d1_states.csv": render(STATE_FIELDS, states_out),
            "d1_excluded.csv": render(EXCL_FIELDS, excl_out),
            "d1_states_betweenyear.csv": render(BETWEEN_FIELDS, between_out),
            "d1_pooled_betweenyear.csv": render(BETWEEN_POOLED_FIELDS, [summary])}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in build().items():
        with open(OUT / name, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    for name in ("d1_pooled.csv", "d1_pooled_betweenyear.csv"):
        with open(OUT / name, encoding="utf-8", newline="") as f:
            for p in csv.DictReader(f):
                print(f"{p['analysis']:>9}  k={p['k']}  "
                      f"yield/100k={float(p['yield_per_100k']):.1f} "
                      f"[{float(p['ci_lo_per_100k']):.1f}, {float(p['ci_hi_per_100k']):.1f}]  "
                      f"tau2={float(p['tau2']):.3f}  I2={float(p['i2']):.1f}  "
                      f"above/overlaps/below={p['n_above']}/{p['n_overlaps']}/{p['n_below']}"
                      + (f"  agree={p['n_tier_agrees']} robust="
                         f"{p['robust_above']}/{p['robust_overlaps']}/{p['robust_below']}"
                         if "n_tier_agrees" in p else ""))


if __name__ == "__main__":
    main()
