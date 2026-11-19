"""D2: was phase-1 campaign screening aimed where prior ACF yield was highest? Alignment of
each State's campaign district share with its prior yield, descriptive tier shares, and an
illustrative marginal-shift scenario (extension plan sections 3.3, 5.1, 5.2 and 9).

Run as `python -I src/ext/d2_targeting.py` to write, under outputs/ext/ (UTF-8, LF):
  d2_alignment.csv       the main weighted Spearman correlation and its one-axis variants
                         (measure, denominator, weights), each with its bootstrap interval
                         and permutation band; the full 24-entry grid is written later
                         (robustness module);
  d2_tier_shares.csv     units and phase-1 campaign districts per pooled 2021-2023 tier
                         (registered), and per post hoc "robust" tier;
  d2_scenario.csv        the marginal-shift scenario: main (registered tiers, main
                         elasticity), the registered stratum-elasticity sensitivity, and a
                         POST HOC sensitivity on the "robust" tiers (plan section 10,
                         19 November 2026);
  d2_scenario_units.csv  the gaining and losing units of each scenario row.
Columns are documented in outputs/ext/README.md.

These are observational State-level associations. Low alignment means that campaign
districts were not concentrated in States of higher prior yield; it is not read as a
targeting failure (section 5.1). The scenario is an illustration, not a forecast: it
assumes the within-State association epsilon would hold under reallocation (section 5.2).

Random numbers: `numpy.random.default_rng(20261119)` is reset before each bootstrap and
before each permutation (section 9). The scenario reuses the elasticity bootstrap draws of
`d1_saturation.elasticity` (which resets the generator itself).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python -I src/ext/d2_targeting.py`
    sys.path.insert(0, str(ROOT))

from src.ext import d1_saturation as D1  # noqa: E402
from src.ext import d1_yield as Y  # noqa: E402
from src.ext import panel  # noqa: E402

OUT = ROOT / "outputs" / "ext"
EXTRACTED = ROOT / "data" / "extracted"
SEED = Y.SEED
DRAWS = Y.DRAWS
MEASURES = ("pooled_eb", "yield_2023", "eb_2023")
DENOMINATORS = ("reconstructed", "registered")
WEIGHTS = ("screened_2023", "none")
TIERS = ("above", "overlaps", "below")
SHARE = 0.10


# ---------------------------------------------------------------- Spearman (5.1)

def _wpearson(rx: np.ndarray, ry: np.ndarray, w: np.ndarray) -> float | None:
    """r_w = sum w(x - xw)(y - yw) / sqrt(sum w(x - xw)^2 sum w(y - yw)^2), with weighted
    means xw = sum wx / sum w (section 5.1). None if a weighted variance is zero."""
    sw = float(np.sum(w))
    dx = rx - float(np.sum(w * rx)) / sw
    dy = ry - float(np.sum(w * ry)) / sw
    sxx = float(np.sum(w * dx * dx))
    syy = float(np.sum(w * dy * dy))
    if sxx <= 0 or syy <= 0:
        return None
    return float(np.sum(w * dx * dy)) / float(np.sqrt(sxx * syy))


def _constant(a: np.ndarray) -> bool:
    return bool(np.all(a == a[0]))


def weighted_spearman(x, y, w=None) -> float | None:
    """Section 5.1: average ranks (`scipy.stats.rankdata`, method "average"), taken
    unweighted, then the weighted Pearson correlation of the ranks. w=None gives w_s = 1
    (the ordinary Spearman correlation). None if either variable is constant."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    if x.size < 2 or _constant(x) or _constant(y):
        return None
    return _wpearson(stats.rankdata(x, method="average"),
                     stats.rankdata(y, method="average"), w)


def bootstrap_rho(x, y, w=None, draws: int = DRAWS) -> np.ndarray:
    """Section 5.1 bootstrap of units: the generator is reset; draw b is
    `rng.integers(0, n, size=n)`; each unit brings its x, y and weight; ranks are
    recomputed in the draw. A draw in which either variable is constant is degenerate
    (NaN). Returns all draws in order."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    n = x.size
    rng = np.random.default_rng(SEED)
    out = np.full(draws, np.nan)
    for b in range(draws):
        idx = rng.integers(0, n, size=n)
        xb, yb = x[idx], y[idx]
        if _constant(xb) or _constant(yb):
            continue
        r = _wpearson(stats.rankdata(xb, method="average"),
                      stats.rankdata(yb, method="average"), w[idx])
        if r is not None:
            out[b] = r
    return out


def permutation_rho(x, y, w=None, draws: int = DRAWS) -> np.ndarray:
    """Section 5.1 permutation: the generator is reset; in each of `draws` permutations
    (`rng.permutation(n)`) the exposure ranks are permuted over units, while the yield
    ranks and the weights stay with their units, and rho is recomputed."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(x) if w is None else np.asarray(w, dtype=float)
    rx = stats.rankdata(x, method="average")
    ry = stats.rankdata(y, method="average")
    rng = np.random.default_rng(SEED)
    out = np.full(draws, np.nan)
    for b in range(draws):
        r = _wpearson(rx[rng.permutation(x.size)], ry, w)
        if r is not None:
            out[b] = r
    return out


def band(a: np.ndarray) -> tuple:
    """2.5th and 97.5th percentiles (`numpy.quantile`, linear) of the non-NaN values."""
    a = np.asarray(a, dtype=float)
    v = a[~np.isnan(a)]
    if v.size == 0:
        return (None, None)
    lo, hi = np.quantile(v, [0.025, 0.975])
    return (float(lo), float(hi))


# ---------------------------------------------------------------- alignment sample

def _load(rows):
    return panel.load_panel() if rows is None else rows


def _units(rows) -> list:
    return sorted({r["unit"] for r in rows})


def _year(rows, year: int) -> dict:
    return {r["unit"]: r for r in rows if r["year"] == year}


def measure_values(measure: str, rows=None) -> tuple:
    """({unit: value}, {unit: reason}) for the D2 yield measure (sections 5.1, 7.1):
    'pooled_eb' the pooled 2021-2023 posterior mean (section 4.2; main);
    'yield_2023' D/S in 2023, a zero yield kept (it takes the lowest rank);
    'eb_2023' the single-year 2023 posterior mean (section 4.2), zero-diagnosed units
    excluded (section 3.3)."""
    real = rows is None  # the registered panel: use d1_yield.pooled_state_yield
    rows = _load(rows)
    units = _units(rows)
    vals, why = {}, {}
    if measure == "pooled_eb":
        if real:
            got = {u: Y.pooled_state_yield(u)[0] for u in units}
        else:
            got = {s["unit"]: s["post_mean_log"]
                   for s in Y.analyse_pooled(rows=rows)[1]}
        for u in units:
            if got.get(u) is None:
                why[u] = ("no pooled 2021-2023 yield: no unit-year passes section 3.3")
            else:
                vals[u] = got[u]
    elif measure == "yield_2023":
        p23 = _year(rows, 2023)
        for u in units:
            r = p23.get(u)
            if r is None:
                why[u] = "no 2023 row"
            elif r["screened"] is None:
                why[u] = "2023 screened NA"
            elif r["screened"] == 0:
                why[u] = "2023 screened zero"
            elif r["diagnosed"] is None:
                why[u] = "2023 diagnosed NA"
            else:
                vals[u] = r["diagnosed"] / r["screened"]
    elif measure == "eb_2023":
        _, states, excl = Y.analyse_year(2023, rows)
        vals = {s["unit"]: s["post_mean_log"] for s in states}
        for e in excl:
            why[e["unit"]] = "2023 empirical Bayes: " + e["reason"]
    else:
        raise ValueError(measure)
    return vals, why


def exposure_values(denominator: str, rows=None) -> tuple:
    """({unit: E_s}, {unit: reason}): E = min(1, c/L) from the panel (section 3.1)."""
    if denominator not in DENOMINATORS:
        raise ValueError(denominator)
    rows = _load(rows)
    key = "exposure_" + denominator
    vals, why = {}, {}
    for u in _units(rows):
        v = next(r[key] for r in rows if r["unit"] == u)
        if v is None:
            why[u] = f"exposure ({denominator} denominator) not computable"
        else:
            vals[u] = v
    return vals, why


def weight_values(weights: str, rows=None) -> tuple:
    """({unit: w_s}, {unit: reason}): 2023 screened (main) or 1 ('none')."""
    rows = _load(rows)
    units = _units(rows)
    if weights == "none":
        return {u: 1.0 for u in units}, {}
    if weights != "screened_2023":
        raise ValueError(f"weights must be 'screened_2023' (main) or 'none', not {weights!r}")
    p23 = _year(rows, 2023)
    vals, why = {}, {}
    for u in units:
        r = p23.get(u)
        if r is None or r["screened"] is None:
            why[u] = "weight: 2023 screened NA"
        else:
            vals[u] = float(r["screened"])
    return vals, why


def alignment_sample(measure="pooled_eb", denominator="reconstructed",
                     weights="screened_2023", units=None, rows=None) -> tuple:
    """(units, x = exposure, y = measure, w, listed). `units` restricts the correlation
    sample only; the measure is not recomputed (section 7.1). Units lacking a value or a
    weight are listed ({unit, reason})."""
    given = rows
    rows = _load(rows)
    xv, xw = exposure_values(denominator, rows)
    yv, yw = measure_values(measure, given)
    wv, ww = weight_values(weights, rows)
    keep = _units(rows) if units is None else [u for u in _units(rows) if u in set(units)]
    use, listed = [], []
    for u in keep:
        reasons = [d[u] for d in (xw, yw, ww) if u in d]
        if reasons:
            listed.append({"unit": u, "reason": "; ".join(reasons)})
        else:
            use.append(u)
    return (use, np.array([xv[u] for u in use]), np.array([yv[u] for u in use]),
            np.array([wv[u] for u in use]), listed)


def alignment(measure: str = "pooled_eb", denominator: str = "reconstructed",
              weights: str = "screened_2023", units=None, rows=None,
              draws: int = DRAWS) -> dict:
    """Section 5.1 alignment: rho, the Spearman correlation of exposure E_s with the
    yield measure, weighted by 2023 screened (main) or unweighted ('none'). weights=None
    is rejected, to avoid confusing "default" with "unweighted".

    Returns rho, boot_ci (bootstrap of units, percentile, linear), n_draws, n_valid,
    degenerate, perm_band (2.5th and 97.5th percentiles of 10,000 permutations, linear),
    n_perm, outside_band, n, units, listed, and the specification."""
    if measure not in MEASURES:
        raise ValueError(measure)
    if weights is None:
        raise ValueError("weights must be named: 'screened_2023' (main) or 'none'")
    use, x, y, w, listed = alignment_sample(measure, denominator, weights, units, rows)
    rho = weighted_spearman(x, y, w) if len(use) >= 3 else None
    out = {"measure": measure, "denominator": denominator, "weights": weights,
           "units_spec": "all" if units is None else "restricted", "rho": rho,
           "n": len(use), "units": use, "listed": listed, "n_draws": draws,
           "n_perm": draws, "boot_ci": (None, None), "perm_band": (None, None),
           "n_valid": 0, "degenerate": draws, "outside_band": None}
    if rho is None:
        return out
    boot = bootstrap_rho(x, y, w, draws)
    perm = permutation_rho(x, y, w, draws)
    lo, hi = band(perm)
    out.update({"boot_ci": band(boot), "n_valid": int(np.sum(~np.isnan(boot))),
                "degenerate": int(np.sum(np.isnan(boot))), "perm_band": (lo, hi),
                "outside_band": bool(rho < lo or rho > hi)})
    return out


# ---------------------------------------------------------------- tiers

def registered_tiers(rows=None) -> dict:
    """unit -> registered pooled 2021-2023 tier (section 4.2; d1_states.csv)."""
    return {s["unit"]: s["tier"] for s in Y.analyse_pooled(rows=rows)[1]}


def robust_tiers(rows=None) -> dict:
    """POST HOC (plan section 10, 19 November 2026): unit -> tier where the registered
    and the between-year tiers agree, else 'not robust' (d1_states_betweenyear.csv)."""
    reg = registered_tiers(rows)
    _, states, _ = Y.analyse_betweenyear(rows=rows)
    return {s["unit"]: (s["tier"] if s["tier"] == reg[s["unit"]] else "not robust")
            for s in states}


def campaign_counts() -> dict:
    """unit -> phase-1 campaign districts (`campaign_count`). The count is the same in
    both exposure files; a difference raises."""
    def load(name):
        with open(EXTRACTED / name, encoding="utf-8", newline="") as f:
            return {r["unit"]: int(r["campaign_count"]) for r in csv.DictReader(f)}
    rec = load("exposure_share_reconstructed.csv")
    if rec != load("exposure_share.csv"):
        raise ValueError("campaign_count differs between the exposure files")
    return rec


def tier_shares(tiers=None, rows=None) -> list:
    """Section 5.1 descriptive tier shares: for each tier and for 'no tier', the number
    of units, the phase-1 campaign districts and their share of all campaign districts.
    `tiers` defaults to the registered pooled 2021-2023 tiers."""
    tiers = registered_tiers(rows) if tiers is None else tiers
    counts = campaign_counts()
    total = sum(counts.values())
    order = list(TIERS) + sorted(set(tiers.values()) - set(TIERS)) + ["no tier"]
    out = []
    for t in order:
        us = sorted(u for u in counts if tiers.get(u, "no tier") == t)
        c = sum(counts[u] for u in us)
        out.append({"tier": t, "n_units": len(us), "units": ";".join(us),
                    "campaign_districts": c, "total_campaign_districts": total,
                    "share": c / total})
    return out


# ---------------------------------------------------------------- scenario (5.2)

def marginal_shift(share: float = SHARE, *, elasticity_draws=None, epsilon=None,
                   tiers=None, strata=None, rows=None) -> dict:
    """Section 5.2 marginal shift. B = 'below' units and A = 'above' units, each with 2023
    S and D present (D = 0 is kept, section 3.3; others are listed). Each B unit loses
    `share` of its 2023 screening (r = -share); the moved volume M = share * sum_B S goes
    to A in proportion to 2023 volume (r = M / sum_A S). The expected change is
    sum_{A u B} D_2023 [(1 + r)^eps - 1], applied to the point epsilon and to every valid
    bootstrap draw (percentile interval, linear); D_2023 is held fixed.

    Defaults: the registered pooled 2021-2023 tiers and the main elasticity with its
    draws. With `strata` (unit -> stratum), `epsilon` and `elasticity_draws` are dicts
    keyed by stratum; draws are paired by index and a draw degenerate (NaN) in any
    stratum is excluded.

    Not a forecast: it assumes the within-State association eps would hold under
    reallocation."""
    rows = _load(rows)
    tiers = registered_tiers(rows) if tiers is None else tiers
    if epsilon is None and elasticity_draws is None:
        if strata is not None:
            raise ValueError("stratum epsilon and draws must be given")
        e = D1.elasticity(rows, return_draws=True)
        epsilon, elasticity_draws = e["beta"], e["draws"]
    elif epsilon is None or elasticity_draws is None:
        raise ValueError("give both epsilon and elasticity_draws, or neither")
    p23 = _year(rows, 2023)
    A, B, excluded = [], [], []
    for u in sorted(tiers):
        t = tiers[u]
        if t not in ("above", "below"):
            continue
        r = p23.get(u)
        miss = ("no 2023 row" if r is None else
                "2023 screened NA" if r["screened"] is None else
                "2023 diagnosed NA" if r["diagnosed"] is None else None)
        if miss:
            excluded.append({"unit": u, "tier": t, "reason": miss})
        else:
            (A if t == "above" else B).append(u)
    out = {"share": share, "excluded": excluded, "gainers": [], "losers": [],
           "computable": True, "reason": None, "delta": None, "ci": (None, None),
           "pct": None, "pct_ci": (None, None), "epsilon": epsilon}
    sum_a = sum(p23[u]["screened"] for u in A)
    sum_b = sum(p23[u]["screened"] for u in B)
    if not A or not B or sum_a <= 0:
        out.update({"computable": False,
                    "reason": "no 'above' unit" if not A else
                              "no 'below' unit" if not B else "zero 2023 screening in A"})
        return out
    moved = share * sum_b
    units = A + B
    r = np.array([moved / sum_a] * len(A) + [-share] * len(B), dtype=float)
    S = np.array([p23[u]["screened"] for u in units], dtype=float)
    D = np.array([p23[u]["diagnosed"] for u in units], dtype=float)

    if strata is None:
        eps = np.full(len(units), float(epsilon))
        dr = np.asarray(elasticity_draws, dtype=float)
        valid = ~np.isnan(dr)
        E = np.repeat(dr[valid][:, None], len(units), axis=1)
        n_draws = dr.size
    else:
        missing = [u for u in units if u not in strata]
        if missing:
            raise ValueError(f"no stratum for {missing}")
        eps = np.array([float(epsilon[strata[u]]) for u in units])
        mats = {k: np.asarray(v, dtype=float) for k, v in elasticity_draws.items()}
        n_draws = next(iter(mats.values())).size
        valid = np.all([~np.isnan(v) for v in mats.values()], axis=0)
        E = np.column_stack([mats[strata[u]][valid] for u in units])

    gain = D * ((1.0 + r) ** eps - 1.0)
    delta = float(np.sum(gain))
    deltas = (((1.0 + r)[None, :] ** E) - 1.0) @ D
    ci = band(deltas)
    sum_d = float(np.sum(D))
    for i, u in enumerate(units):
        row = {"unit": u, "tier": tiers[u], "screened_2023": int(S[i]),
               "diagnosed_2023": int(D[i]), "r": float(r[i]),
               "screened_after": float(S[i] * (1.0 + r[i])), "epsilon": float(eps[i]),
               "delta": float(gain[i]) + 0.0}  # + 0.0 turns -0.0 into 0.0
        (out["gainers"] if i < len(A) else out["losers"]).append(row)
    out.update({"moved": moved, "r_gain": moved / sum_a, "sum_screened_a": sum_a,
                "sum_screened_b": sum_b, "screened_before": float(np.sum(S)),
                "screened_after": float(np.sum(S * (1.0 + r))), "diagnosed_2023": sum_d,
                "delta": delta, "ci": ci, "n_draws": int(n_draws),
                "n_valid": int(np.sum(valid)), "degenerate": int(n_draws - np.sum(valid))})
    if sum_d > 0:
        out["pct"] = 100.0 * delta / sum_d
        out["pct_ci"] = tuple(None if v is None else 100.0 * v / sum_d for v in ci)
    return out


# ---------------------------------------------------------------- outputs

ALIGN_FIELDS = ("analysis", "measure", "denominator", "weights", "units", "estimate",
                "null", "boot_lo", "boot_hi", "draws", "n_valid", "degenerate",
                "perm_lo", "perm_hi", "permutations", "outside_band", "n", "n_listed",
                "listed")
SHARE_FIELDS = ("classification", "tier", "n_units", "units", "campaign_districts",
                "total_campaign_districts", "share")
SCEN_FIELDS = ("analysis", "status", "tiers", "elasticity", "epsilon", "share",
               "computable", "n_gainers", "gainers", "n_losers", "losers",
               "screened_before", "moved", "r_gain", "r_loss", "screened_after",
               "diagnosed_2023", "delta", "ci_lo", "ci_hi", "pct", "pct_lo", "pct_hi",
               "draws", "n_valid", "degenerate", "n_excluded", "excluded", "reason")
UNIT_FIELDS = ("analysis", "unit", "tier", "side", "screened_2023", "diagnosed_2023",
               "r", "screened_after", "epsilon", "delta")

ALIGN_RUNS = (
    ("main", "pooled_eb", "reconstructed", "screened_2023"),
    ("unweighted", "pooled_eb", "reconstructed", "none"),
    ("registered denominator", "pooled_eb", "registered", "screened_2023"),
    ("2023 yield", "yield_2023", "reconstructed", "screened_2023"),
    ("2023 empirical Bayes", "eb_2023", "reconstructed", "screened_2023"),
)


def _align_row(label, a) -> dict:
    return {"analysis": label, "measure": a["measure"], "denominator": a["denominator"],
            "weights": a["weights"], "units": a["units_spec"], "estimate": a["rho"],
            "null": 0, "boot_lo": a["boot_ci"][0], "boot_hi": a["boot_ci"][1],
            "draws": a["n_draws"], "n_valid": a["n_valid"], "degenerate": a["degenerate"],
            "perm_lo": a["perm_band"][0], "perm_hi": a["perm_band"][1],
            "permutations": a["n_perm"], "outside_band": a["outside_band"], "n": a["n"],
            "n_listed": len(a["listed"]),
            "listed": ";".join(f"{x['unit']} ({x['reason']})" for x in a["listed"])}


def _scen_rows(label, status, tiers_label, elast_label, eps_text, s) -> tuple:
    row = {"analysis": label, "status": status, "tiers": tiers_label,
           "elasticity": elast_label, "epsilon": eps_text, "share": s["share"],
           "computable": s["computable"], "reason": s["reason"],
           "n_gainers": len(s["gainers"]),
           "gainers": ";".join(g["unit"] for g in s["gainers"]),
           "n_losers": len(s["losers"]),
           "losers": ";".join(g["unit"] for g in s["losers"]),
           "n_excluded": len(s["excluded"]),
           "excluded": ";".join(f"{e['unit']} ({e['tier']}; {e['reason']})"
                                for e in s["excluded"])}
    if s["computable"]:
        row.update({"screened_before": s["screened_before"], "moved": s["moved"],
                    "r_gain": s["r_gain"], "r_loss": -s["share"],
                    "screened_after": s["screened_after"],
                    "diagnosed_2023": s["diagnosed_2023"], "delta": s["delta"],
                    "ci_lo": s["ci"][0], "ci_hi": s["ci"][1], "pct": s["pct"],
                    "pct_lo": s["pct_ci"][0], "pct_hi": s["pct_ci"][1],
                    "draws": s["n_draws"], "n_valid": s["n_valid"],
                    "degenerate": s["degenerate"]})
    units = [{"analysis": label, "side": "gains", **g} for g in s["gainers"]]
    units += [{"analysis": label, "side": "loses", **g} for g in s["losers"]]
    return row, units


def build_results() -> dict:
    """Every estimate written by `build`, as Python objects."""
    rows = panel.load_panel()
    res = {"alignment": [(lab, alignment(m, d, w))
                         for lab, m, d, w in ALIGN_RUNS]}
    reg = registered_tiers(rows)
    rob = robust_tiers(rows)
    res["shares_registered"] = tier_shares(reg)
    res["shares_robust"] = tier_shares(rob)
    main = D1.elasticity(rows, return_draws=True)
    strata = D1.intensity_strata(rows)
    st = {k: D1.elasticity(rows, stratum=k, return_draws=True) for k in ("high", "low")}
    res["elasticity"] = {"main": main["beta"], **{k: v["beta"] for k, v in st.items()}}
    res["scenario_main"] = marginal_shift(SHARE, epsilon=main["beta"],
                                          elasticity_draws=main["draws"], tiers=reg,
                                          rows=rows)
    res["scenario_strata"] = marginal_shift(
        SHARE, epsilon={k: v["beta"] for k, v in st.items()},
        elasticity_draws={k: v["draws"] for k, v in st.items()}, tiers=reg,
        strata=strata, rows=rows)
    res["scenario_robust"] = marginal_shift(SHARE, epsilon=main["beta"],
                                            elasticity_draws=main["draws"], tiers=rob,
                                            rows=rows)
    return res


def build() -> dict:
    """file name -> CSV text for every file under outputs/ext written by this module."""
    R = build_results()
    align = [_align_row(lab, a) for lab, a in R["alignment"]]
    shares = ([{"classification": "registered pooled 2021-2023", **r}
               for r in R["shares_registered"]]
              + [{"classification": "robust (post hoc)", **r} for r in R["shares_robust"]])
    eps = R["elasticity"]
    scen, units = [], []
    for args in (("main", "main", "registered pooled 2021-2023", "main",
                  repr(eps["main"]), R["scenario_main"]),
                 ("stratum elasticity", "sensitivity", "registered pooled 2021-2023",
                  "intensity stratum", f"high={eps['high']!r};low={eps['low']!r}",
                  R["scenario_strata"]),
                 ("robust tiers (post hoc)", "post hoc sensitivity",
                  "robust (registered and between-year agree)", "main",
                  repr(eps["main"]), R["scenario_robust"])):
        row, us = _scen_rows(*args)
        scen.append(row)
        units += us
    return {"d2_alignment.csv": Y.render(ALIGN_FIELDS, align),
            "d2_tier_shares.csv": Y.render(SHARE_FIELDS, shares),
            "d2_scenario.csv": Y.render(SCEN_FIELDS, scen),
            "d2_scenario_units.csv": Y.render(UNIT_FIELDS, units)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    built = build()
    for name, text in built.items():
        with open(OUT / name, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    for name in ("d2_alignment.csv", "d2_tier_shares.csv", "d2_scenario.csv"):
        print(built[name])


if __name__ == "__main__":
    main()
