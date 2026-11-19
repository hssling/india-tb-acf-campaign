"""D3: do State notifications move with State ACF diagnoses? The within-State association
between ACF diagnoses and notifications (extension plan sections 3.3, 6, 7.1 and 9).

Run as `python -I src/ext/d3_additionality.py` to write outputs/ext/d3.csv (UTF-8, LF):
the main estimate and every variant of the section 7.1 grid (outcome x scale x weights x
units), each with its CR1 model interval and its cluster-bootstrap interval. Columns are
documented in outputs/ext/README.md.

Model (section 6): N_st = alpha_s + lambda_t + theta A_st + e_st, t in {2019, 2022, 2023},
where N is public-sector notifications (main; total notifications secondary) and A is ACF
diagnosed. Absolute scale (main): weights 1/N_st, the inverse Poisson variance of N_st.
Log scale: ln N = alpha + lambda + theta_log ln A, weights N_st (the inverse Poisson variance
of ln N_st), unit-years with A = 0 excluded. The design, the CR1 model interval and the
cluster bootstrap are those of section 4.3 (`d1_saturation`). Units with one row in the
estimation sample are listed and dropped before fitting and before resampling.

theta is the within-State difference in public notifications associated with one more ACF
diagnosis. It is an observational association. Were the association causal, theta = 1 would
correspond to full addition and theta = 0 to full substitution; these are reference values
only. The null is 0.

Random numbers: `numpy.random.default_rng(20261119)` is reset at the start of every
bootstrap (section 9), inside `d1_saturation._cluster_boot`.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python -I src/ext/d3_additionality.py`
    sys.path.insert(0, str(ROOT))

from src.ext import d1_saturation as D1  # noqa: E402
from src.ext import d1_yield as Y  # noqa: E402
from src.ext import panel  # noqa: E402

OUT = ROOT / "outputs" / "ext"
DRAWS = Y.DRAWS
YEARS = (2019, 2022, 2023)
OUTCOMES = ("public", "total")
SCALES = ("absolute", "log")
WEIGHTS = ("inverse_poisson", "none")
MAIN = {"outcome": "public", "scale": "absolute", "weights": "inverse_poisson"}


# ---------------------------------------------------------------- sample (3.3, 6)

def _reason(r: dict, outcome: str, scale: str, weights: str) -> str | None:
    """Why a unit-year cannot enter this D3 entry (section 3.3), or None."""
    A, N = r["diagnosed"], r[f"notified_{outcome}"]
    out = []
    if A is None:
        out.append("A NA")
    if N is None:
        out.append("N NA")
    if N == 0 and (scale == "log" or weights == "inverse_poisson"):
        out.append("N=0")
    if A == 0 and scale == "log":
        out.append("A=0")
    return "/".join(out) if out else None


_WHY = {"A NA": "ACF diagnosed NA in the source; not imputed",
        "N NA": "notifications NA in the source; not imputed",
        "N=0": "zero notifications; excluded from 1/N-weighted and log-scale entries",
        "A=0": "zero ACF diagnoses; excluded from the log scale (section 3.3)"}


def sample(rows=None, outcome="public", scale="absolute", weights="inverse_poisson",
           units=None, years=YEARS) -> tuple:
    """(usable rows sorted by unit and year, excluded [{unit, year, code, reason}]).
    Only rows of `years` (and of `units`, if given) are considered."""
    rows = panel.load_panel() if rows is None else rows
    keep = None if units is None else set(units)
    yset = set(years)
    use, excl = [], []
    for r in sorted((r for r in rows if r["year"] in yset
                     and (keep is None or r["unit"] in keep)),
                    key=lambda r: (r["unit"], r["year"])):
        code = _reason(r, outcome, scale, weights)
        if code:
            excl.append({"unit": r["unit"], "year": r["year"], "code": code,
                         "reason": "; ".join(_WHY[c] for c in code.split("/"))})
        else:
            use.append(r)
    return use, excl


# ---------------------------------------------------------------- model (6, 4.3)

def _check(outcome, scale, weights) -> None:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, not {outcome!r}")
    if scale not in SCALES:
        raise ValueError(f"scale must be one of {SCALES}, not {scale!r}")
    if weights is None:
        raise ValueError("weights must be named: 'inverse_poisson' (main) or 'none'")
    if weights not in WEIGHTS:
        raise ValueError(f"weights must be one of {WEIGHTS}, not {weights!r}")


def additionality(outcome: str = "public", scale: str = "absolute",
                  weights: str = "inverse_poisson", units=None, rows=None,
                  years=YEARS, draws: int = DRAWS, return_draws: bool = False) -> dict:
    """Section 6: the within-State association theta of notifications with ACF diagnoses.

    outcome 'public' (main) or 'total'; scale 'absolute' (main: N on A) or 'log' (ln N on
    ln A); weights 'inverse_poisson' (main: 1/N absolute, N log, where N is this entry's
    outcome) or 'none'. weights=None is rejected, to avoid confusing "default" with
    "unweighted". `units` and `years` restrict the sample.

    Returns theta, se (CR1), model_ci (theta +/- t_{G-1} se), cluster_ci (cluster
    bootstrap, the main interval), n (unit-years), G (units), p, df, n_draws, n_valid,
    degenerate (rank-deficient draws, counted and excluded), units, singletons (listed and
    dropped before fitting and resampling), excluded, and the specification. With
    return_draws=True, `draws` holds every bootstrap slope in draw order (NaN at degenerate
    draws)."""
    _check(outcome, scale, weights)
    use, excl = sample(rows, outcome, scale, weights, units, years)
    use, single = D1._drop_singletons(use)
    key = f"notified_{outcome}"

    def cols(rs):
        a = np.array([r["diagnosed"] for r in rs], dtype=float)
        n = np.array([r[key] for r in rs], dtype=float)
        if weights == "none":
            w = np.ones_like(n)
        else:  # inverse Poisson variance of the outcome: 1/N absolute, N log
            w = n if scale == "log" else 1.0 / n
        x, y = (np.log(a), np.log(n)) if scale == "log" else (a, n)
        return x, y, w, np.array([r["year"] for r in rs])

    ulist, data = D1._by_unit(use, cols)
    G = len(ulist)
    if G < 2:
        raise ValueError("additionality needs at least two units with two rows")
    x = np.concatenate([d[0] for d in data])
    y = np.concatenate([d[1] for d in data])
    w = np.concatenate([d[2] for d in data])
    t = np.concatenate([d[3] for d in data])
    codes = np.concatenate([np.full(d[0].size, k) for k, d in enumerate(data)])
    X = D1._design_codes(x, codes, G, t)
    U = D1._usable(X, w)
    if U is None or U.shape != X.shape:
        raise ValueError("main design is rank-deficient")
    coef = D1._wls(X, y, w)
    n, p = X.shape
    resid = y - X @ coef
    bread = np.linalg.inv(X.T @ (X * w[:, None]))
    meat = np.zeros((p, p))
    for k in range(G):
        m = codes == k
        sc = X[m].T @ (w[m] * resid[m])
        meat += np.outer(sc, sc)
    c = G / (G - 1) * (n - 1) / (n - p)
    V = c * bread @ meat @ bread
    se = math.sqrt(V[0, 0])
    half = float(stats.t.ppf(0.975, G - 1)) * se
    theta = float(coef[0])
    bd = D1._cluster_boot(data, D1._wls_one, draws)
    out = {"theta": theta, "se": se, "model_ci": (theta - half, theta + half),
           "cluster_ci": D1._percentile(bd), "n": n, "G": G, "p": p, "df": G - 1,
           "n_draws": draws, "n_valid": int(np.sum(~np.isnan(bd))),
           "degenerate": int(np.sum(np.isnan(bd))), "units": ulist, "singletons": single,
           "excluded": excl, "outcome": outcome, "scale": scale, "weights": weights,
           "years": sorted({r["year"] for r in use})}
    if return_draws:
        out["draws"] = bd
    return out


# ---------------------------------------------------------------- memo (real panel)

_MEMO: dict = {}


def cached(outcome: str, scale: str, weights: str, units=None,
           draws: int = DRAWS) -> dict:
    """`additionality` on the registered panel, memoised within one process (the
    robustness module reuses the entries written to d3.csv; results are identical)."""
    key = (outcome, scale, weights, None if units is None else tuple(sorted(units)), draws)
    if key not in _MEMO:
        _MEMO[key] = additionality(outcome, scale, weights, units=units, draws=draws)
    return dict(_MEMO[key])


def non_small_ut_units(rows=None) -> list:
    """Units that are not small UTs (plan section 3.2), sorted."""
    rows = panel.load_panel() if rows is None else rows
    return sorted({r["unit"] for r in rows if not r["small_ut"]})


# ---------------------------------------------------------------- outputs

FIELDS = ("analysis", "role", "outcome", "scale", "weights", "units", "years", "estimate",
          "null", "se_cr1", "df", "model_ci_lo", "model_ci_hi", "boot_lo", "boot_hi",
          "draws", "n_valid", "degenerate", "n_units", "n_obs", "p", "n_singletons",
          "singletons", "n_excluded", "excluded")
UNITS_LABEL = {"all": "all", "excluding small UTs": "excluding small UTs"}


def _role(outcome, scale, weights, units) -> str:
    if units == "all" and weights == "inverse_poisson":
        if (outcome, scale) == ("public", "absolute"):
            return "main"
        return "registered secondary (section 6)"
    return "specification variant (section 7.1)"


def entries() -> list:
    """The 16 D3 specifications of section 7.1, in grid order (outcome x scale x weights
    x units), as (outcome, scale, weights, units label)."""
    return [(o, s, w, u) for o in OUTCOMES for s in SCALES for w in ("none", "inverse_poisson")
            for u in ("all", "excluding small UTs")]


def run(outcome, scale, weights, units_label, draws: int = DRAWS) -> dict:
    units = None if units_label == "all" else non_small_ut_units()
    return cached(outcome, scale, weights, units, draws)


def row(outcome, scale, weights, units_label, r) -> dict:
    name = ("main" if _role(outcome, scale, weights, units_label) == "main" else
            f"{outcome} {scale} weights={weights} units={units_label}")
    return {"analysis": name, "role": _role(outcome, scale, weights, units_label),
            "outcome": outcome, "scale": scale, "weights": weights, "units": units_label,
            "years": ";".join(map(str, r["years"])), "estimate": r["theta"], "null": 0,
            "se_cr1": r["se"], "df": r["df"], "model_ci_lo": r["model_ci"][0],
            "model_ci_hi": r["model_ci"][1], "boot_lo": r["cluster_ci"][0],
            "boot_hi": r["cluster_ci"][1], "draws": r["n_draws"], "n_valid": r["n_valid"],
            "degenerate": r["degenerate"], "n_units": r["G"], "n_obs": r["n"], "p": r["p"],
            "n_singletons": len(r["singletons"]), "singletons": ";".join(r["singletons"]),
            "n_excluded": len(r["excluded"]),
            "excluded": ";".join(f"{e['unit']} {e['year']} {e['code']}"
                                 for e in r["excluded"])}


def build(draws: int = DRAWS) -> dict:
    """file name -> CSV text: d3.csv, the main row first, then the other entries in grid
    order."""
    out = []
    for spec in entries():
        out.append(row(*spec, run(*spec, draws=draws)))
    out.sort(key=lambda r: r["role"] != "main")  # stable: main first, grid order after
    return {"d3.csv": Y.render(FIELDS, out)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    built = build()
    for name, text in built.items():
        with open(OUT / name, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    print(built["d3.csv"])


if __name__ == "__main__":
    main()
