"""D1 part 2: the elasticity of ACF diagnoses to screening volume within States, its
Poisson fixed-effects sensitivity, screening-intensity strata, and the cascade
decomposition of yield (extension plan sections 3.3, 4.2 last bullet, 4.3, 4.4, 4.5, 9).

Run as `python -I src/ext/d1_saturation.py` to write, under outputs/ext/ (UTF-8, LF):
  d1_elasticity.csv          main elasticity, the two intensity strata, Poisson FE;
  d1_decomposition.csv       national change 2021->2023, national levels and the
                             between-State variance split per main year; 2022 rows are a
                             labelled sensitivity (testing definition 'examined');
  d1_tiers_by_intensity.csv  the section 4.2 intensity sensitivity: 2021-2023 pooling,
                             shrinkage, ranks and tiers within each stratum, against that
                             stratum's own mean (via d1_yield.analyse_pooled(units=...));
  d1_intensity_strata.csv    each unit's intensity and stratum (section 4.5 listing);
  d1_elasticity_samedef.csv  POST HOC sensitivity (plan section 10, 20 November 2026): the
                             main elasticity on the data years whose screened column has
                             the same printed heading (2019 and 2021).
Columns are documented in outputs/ext/README.md.

Random numbers: `numpy.random.default_rng(20261119)` is reset at the start of every
bootstrap (section 9): each elasticity, each stratum, the Poisson model, and each
decomposition quantity (the national change, each year's national level, each year's
variance split, each 2022 sensitivity). Draw b is `rng.integers(0, G, size=G)` over the
units sorted by name (section 4.3), one call per draw.

Deviation (plan section 10, 19 November 2026): the ITR 2020 Annexure 6 estimated-population
column, the registered 2019 population of section 4.5, is misaligned with its State rows as
printed (ITR 2020 PDF page 255, printed page 231; e.g. Maharashtra 0.7 lakh, Lakshadweep
343.3 lakh, Mizoram 1241.3 lakh). The main intensity therefore does not use the 2019
population: it is the mean of S_t / P_2021 over 2021-2023 (P_2021 is present for every
unit). The registered rule is still computed (`population_2019=True`) and written beside it.

Post hoc (plan section 10, 20 November 2026; added after every registered estimate was seen):
the screened heading differs between editions (section 3.1), and State-specific shifts in the
screened count that the year effects do not absorb act as measurement error in ln S, which
would most likely bias the elasticity towards 0. `elasticity_same_definition` refits the main
model, with its own reset generator, on the two data years whose screened column has the same
printed heading, "Population screened amongst mapped vulnerable population" (2019, ITR 2020;
2021, ITR 2022). 2018 (ITR 2019, "Persons screened out of the mapped population") is listed
under a different heading in section 3.1 and is not included. No registered estimate changes.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python -I src/ext/d1_saturation.py`
    sys.path.insert(0, str(ROOT))

from src.ext import d1_yield as Y  # noqa: E402
from src.ext import panel  # noqa: E402

OUT = ROOT / "outputs" / "ext"
SEED = Y.SEED
DRAWS = Y.DRAWS
YEARS = Y.YEARS
MAIN_DECOMP_YEARS = (2018, 2019, 2021, 2023)
POISSON_TOL = 1e-10
POISSON_MAXIT = 100


# ---------------------------------------------------------------- design and WLS (4.3)

def _codes(labels) -> tuple:
    """Integer codes of labels in sorted order (Python `sorted`), and the level count."""
    labels = list(np.asarray(labels).tolist())
    lev = sorted(set(labels))
    pos = {v: i for i, v in enumerate(lev)}
    return np.array([pos[v] for v in labels], dtype=int), len(lev)


def _design_codes(x, codes, G: int, year) -> np.ndarray:
    """Columns: x; one dummy per unit code 0..G-1; one dummy per year in the sample
    except the earliest."""
    n = x.size
    U = np.zeros((n, G))
    U[np.arange(n), codes] = 1.0
    ylev = sorted(set(np.asarray(year).tolist()))[1:]
    T = np.zeros((n, len(ylev)))
    for j, t in enumerate(ylev):
        T[:, j] = year == t
    return np.column_stack([x, U, T])


def design(x, unit, year) -> np.ndarray:
    """The section 4.3 design: a column x (ln S), one dummy per unit (sorted), and one
    dummy per year except the earliest year in the sample."""
    x = np.asarray(x, dtype=float)
    codes, G = _codes(unit)
    return _design_codes(x, codes, G, np.asarray(year))


def _wls(X, y, w) -> np.ndarray:
    sw = np.sqrt(w)
    return np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]


def _usable(X, w) -> np.ndarray | None:
    """Drop all-zero columns, then return X, or None if sqrt(W) X is rank-deficient
    (section 4.3, degenerate draw). Column 0 (x) is never all zero here."""
    keep = np.any(X != 0, axis=0)
    if not keep[0]:
        return None
    X = X[:, keep]
    if np.linalg.matrix_rank(X * np.sqrt(w)[:, None]) < X.shape[1]:
        return None
    return X


def fe_wls(y, x, unit, year, w) -> tuple:
    """(beta, n): the coefficient on x from the two-way fixed-effects WLS of section 4.3,
    solved by `numpy.linalg.lstsq` on sqrt(w)-scaled X and y. No singleton handling here;
    `elasticity` drops and lists singleton units before calling the fit."""
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    X = design(x, unit, year)
    return float(_wls(X, y, w)[0]), int(y.size)


# ---------------------------------------------------------------- samples (3.3)

_SHORT = (("screened NA", "S NA"), ("diagnosed NA", "D NA"), ("zero screened", "S=0"),
          ("zero diagnoses", "D=0"), ("D >= S", "D>=S"))


def _short(reason: str) -> str:
    return "/".join(code for key, code in _SHORT if key in reason)


def _log_reason(r: dict, zero: str) -> str | None:
    """Why a unit-year cannot enter the log-scale elasticity (section 3.3), or None. Under
    zero='+0.5' a zero-diagnosed unit-year enters (section 7.1)."""
    if zero == "+0.5" and r["diagnosed"] == 0 and r["screened"] and r["screened"] > 0:
        return None
    return Y._reason(r)


def _restrict(rows, years, units, stratum) -> list:
    rows = panel.load_panel() if rows is None else rows
    keep = None if units is None else set(units)
    if stratum is not None:
        st = intensity_strata(rows)
        su = {u for u, s in st.items() if s == stratum}
        keep = su if keep is None else keep & su
    yset = None if years is None else set(years)
    return sorted((r for r in rows if (keep is None or r["unit"] in keep)
                   and (yset is None or r["year"] in yset)),
                  key=lambda r: (r["unit"], r["year"]))


def _drop_singletons(use: list) -> tuple:
    n = {}
    for r in use:
        n[r["unit"]] = n.get(r["unit"], 0) + 1
    single = sorted(u for u, k in n.items() if k == 1)
    return [r for r in use if r["unit"] not in single], single


def _by_unit(use: list, cols) -> tuple:
    """Units (sorted) and, per unit, a tuple of arrays built by `cols(rows_of_unit)`."""
    units = sorted({r["unit"] for r in use})
    return units, [cols([r for r in use if r["unit"] == u]) for u in units]


# ---------------------------------------------------------------- cluster bootstrap

def _cluster_boot(data: list, fit_one, draws: int) -> np.ndarray:
    """Section 4.3 cluster bootstrap. data[k] = (x, y, w, year) arrays of unit k (sorted
    units). Draw b: idx = rng.integers(0, G, size=G); each drawn unit brings all its rows,
    and each copy is its own cluster with its own dummy. fit_one returns the slope or None
    (degenerate). Returns an array of length `draws`, NaN at degenerate draws."""
    rng = np.random.default_rng(SEED)  # reset per analysis (section 9)
    G = len(data)
    out = np.full(draws, np.nan)
    for b in range(draws):
        idx = rng.integers(0, G, size=G)
        parts = [data[k] for k in idx]
        x = np.concatenate([p[0] for p in parts])
        y = np.concatenate([p[1] for p in parts])
        w = np.concatenate([p[2] for p in parts])
        t = np.concatenate([p[3] for p in parts])
        codes = np.concatenate([np.full(p[0].size, j) for j, p in enumerate(parts)])
        beta = fit_one(x, y, w, codes, G, t)
        if beta is not None:
            out[b] = beta
    return out


def _percentile(draws: np.ndarray) -> tuple:
    valid = draws[~np.isnan(draws)]
    if valid.size == 0:
        return (None, None)
    lo, hi = np.quantile(valid, [0.025, 0.975])
    return (float(lo), float(hi))


def _wls_one(x, y, w, codes, G, t):
    X = _usable(_design_codes(x, codes, G, t), w)
    if X is None:
        return None
    return float(_wls(X, y, w)[0])


# ---------------------------------------------------------------- elasticity (4.3)

def elasticity(rows=None, weights="D", zero="exclude", years=None, units=None,
               stratum=None, draws: int = DRAWS, return_draws: bool = False) -> dict:
    """Elasticity of diagnoses to screening volume (section 4.3):
    ln D = alpha_unit + lambda_year + eps ln S, WLS with weights D (weights='D') or none
    (weights='none' or None); zero='exclude' (main) or '+0.5' (0.5 added to every D, so
    zeros enter and the weight is D + 0.5; section 7.1). `years`, `units` and `stratum`
    ('high'|'low', section 4.5) restrict the sample.

    Returns beta, se (CR1), model_ci (beta +/- t_{G-1} se), boot_ci (cluster bootstrap,
    main interval), n_units (G), n_obs (n), p, df (G - 1), n_draws, n_valid, degenerate,
    units, singletons (listed and dropped before fitting and resampling), excluded
    (unit-years failing section 3.3, each {unit, year, reason}).

    With return_draws=True, `draws` is the array of all bootstrap slopes in draw order,
    length n_draws, NaN at degenerate draws (the stratum scenario of
    d2_targeting pairs stratum draws by index)."""
    if zero not in ("exclude", "+0.5"):
        raise ValueError(zero)
    wmode = "none" if weights in (None, "none") else weights
    if wmode not in ("D", "none"):
        raise ValueError(weights)
    sample = _restrict(rows, years, units, stratum)
    use, excl = [], []
    for r in sample:
        why = _log_reason(r, zero)
        if why:
            excl.append({"unit": r["unit"], "year": r["year"], "reason": why})
        else:
            use.append(r)
    use, single = _drop_singletons(use)
    add = 0.5 if zero == "+0.5" else 0.0

    def cols(rs):
        d = np.array([r["diagnosed"] for r in rs], dtype=float) + add
        return (np.log(np.array([r["screened"] for r in rs], dtype=float)), np.log(d),
                d if wmode == "D" else np.ones_like(d),
                np.array([r["year"] for r in rs]))

    ulist, data = _by_unit(use, cols)
    G = len(ulist)
    if G < 2:
        raise ValueError("elasticity needs at least two units with two rows")
    x = np.concatenate([d[0] for d in data])
    y = np.concatenate([d[1] for d in data])
    w = np.concatenate([d[2] for d in data])
    t = np.concatenate([d[3] for d in data])
    codes = np.concatenate([np.full(d[0].size, k) for k, d in enumerate(data)])
    X = _design_codes(x, codes, G, t)
    if _usable(X, w) is None or _usable(X, w).shape != X.shape:
        raise ValueError("main design is rank-deficient")
    coef = _wls(X, y, w)
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
    beta = float(coef[0])
    bd = _cluster_boot(data, _wls_one, draws)
    out = {"beta": beta, "se": se, "model_ci": (beta - half, beta + half),
           "boot_ci": _percentile(bd), "n_units": G, "n_obs": n, "p": p, "df": G - 1,
           "n_draws": draws, "n_valid": int(np.sum(~np.isnan(bd))),
           "degenerate": int(np.sum(np.isnan(bd))), "units": ulist,
           "singletons": single, "excluded": excl, "weights": wmode, "zero": zero,
           "years": sorted({r["year"] for r in use})}
    if return_draws:
        out["draws"] = bd
    return out


# ---------------------------------------------------------------- post hoc: same heading

SAME_DEFINITION_YEARS = (2019, 2021)
SAME_DEFINITION_HEADING = "Population screened amongst mapped vulnerable population"


def elasticity_same_definition(rows=None, draws: int = DRAWS) -> dict:
    """POST HOC (plan section 10, 20 November 2026): the main elasticity (section 4.3:
    weights D, zeros excluded, singletons dropped, CR1 model interval, cluster bootstrap with
    the generator reset) on the data years whose screened column has the same printed
    heading, SAME_DEFINITION_YEARS."""
    return elasticity(rows, years=SAME_DEFINITION_YEARS, draws=draws)


# ---------------------------------------------------------------- Poisson FE (4.3)

def _poisson_irls(X, y) -> tuple:
    """(coef, mu, converged, iterations): IRLS from the unweighted LS fit of ln(y + 0.5),
    until the maximum absolute coefficient change is < 1e-10, at most 100 iterations."""
    b = np.linalg.lstsq(X, np.log(y + 0.5), rcond=None)[0]
    for it in range(1, POISSON_MAXIT + 1):
        eta = X @ b
        mu = np.exp(eta)
        bn = _wls(X, eta + (y - mu) / mu, mu)
        if not np.all(np.isfinite(bn)):
            return bn, None, False, it
        if np.max(np.abs(bn - b)) < POISSON_TOL:
            return bn, np.exp(X @ bn), True, it
        b = bn
    return b, np.exp(X @ b), False, POISSON_MAXIT


def _poisson_one(x, y, w, codes, G, t):
    X = _usable(_design_codes(x, codes, G, t), w)
    if X is None:
        return None
    coef, _, ok, _ = _poisson_irls(X, y)
    return float(coef[0]) if ok else None


def poisson_fe_elasticity(rows=None, years=None, units=None, draws: int = DRAWS,
                          return_draws: bool = False) -> dict:
    """Poisson fixed-effects sensitivity (section 4.3): D ~ Poisson(exp(alpha_unit +
    lambda_year + eps ln S)), unweighted, zero diagnoses kept. Unit-years with S or D NA,
    or S = 0, are left out (ln S undefined) and listed; units with D = 0 in every year are
    listed and excluded; singleton units are listed and dropped. Intervals: CR1 sandwich
    (bread X'WX with W = diag(mu), meat sum_g X_g'(y_g - mu_g)(...)'X_g, c = G/(G-1),
    t_{G-1}) and the cluster bootstrap; a draw that is rank-deficient or does not converge
    in 100 iterations is degenerate. Keys as `elasticity`, plus converged, iterations,
    all_zero_units; `_X`, `_y`, `_mu` hold the fitted design for checks."""
    sample = _restrict(rows, years, units, None)
    use, excl = [], []
    for r in sample:
        S_, D_ = r["screened"], r["diagnosed"]
        why = []
        if S_ is None:
            why.append("screened NA in the source; not imputed")
        if D_ is None:
            why.append("diagnosed NA in the source; not imputed")
        if S_ == 0:
            why.append("zero screened as printed (inconsistent row, S = 0); ln S undefined")
        if why:
            excl.append({"unit": r["unit"], "year": r["year"], "reason": "; ".join(why)})
        else:
            use.append(r)
    total = {}
    for r in use:
        total[r["unit"]] = total.get(r["unit"], 0) + r["diagnosed"]
    all_zero = sorted(u for u, s in total.items() if s == 0)
    use = [r for r in use if r["unit"] not in all_zero]
    use, single = _drop_singletons(use)

    def cols(rs):
        d = np.array([r["diagnosed"] for r in rs], dtype=float)
        return (np.log(np.array([r["screened"] for r in rs], dtype=float)), d,
                np.ones_like(d), np.array([r["year"] for r in rs]))

    ulist, data = _by_unit(use, cols)
    G = len(ulist)
    x = np.concatenate([d[0] for d in data])
    y = np.concatenate([d[1] for d in data])
    t = np.concatenate([d[3] for d in data])
    codes = np.concatenate([np.full(d[0].size, k) for k, d in enumerate(data)])
    X = _design_codes(x, codes, G, t)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("main design is rank-deficient")
    coef, mu, ok, its = _poisson_irls(X, y)
    n, p = X.shape
    bread = np.linalg.inv(X.T @ (X * mu[:, None]))
    meat = np.zeros((p, p))
    for k in range(G):
        m = codes == k
        sc = X[m].T @ (y[m] - mu[m])
        meat += np.outer(sc, sc)
    V = (G / (G - 1)) * bread @ meat @ bread
    se = math.sqrt(V[0, 0])
    half = float(stats.t.ppf(0.975, G - 1)) * se
    beta = float(coef[0])
    bd = _cluster_boot(data, _poisson_one, draws)
    out = {"beta": beta, "se": se, "model_ci": (beta - half, beta + half),
           "boot_ci": _percentile(bd), "n_units": G, "n_obs": n, "p": p, "df": G - 1,
           "n_draws": draws, "n_valid": int(np.sum(~np.isnan(bd))),
           "degenerate": int(np.sum(np.isnan(bd))), "units": ulist,
           "singletons": single, "all_zero_units": all_zero, "excluded": excl,
           "converged": ok, "iterations": its,
           "years": sorted({r["year"] for r in use}), "_X": X, "_y": y, "_mu": mu}
    if return_draws:
        out["draws"] = bd
    return out


# ---------------------------------------------------------------- intensity strata (4.5)

INTENSITY_YEARS = (2019, 2021, 2022, 2023)


def intensities(rows=None, population_2019: bool = False) -> tuple:
    """({unit: (intensity, [years used])}, [(unit, reason)] unclassified).

    intensity = mean of S_t / P_t over the years with both present (S = 0 is a printed
    value and counts). Registered rule (population_2019=True, section 4.5): P_2019 is the
    ITR 2020 population; P_t for 2021-2023 is the ITR 2022 population, or the 2019 value
    carried forward if that is missing; 2018 is not used. Main rule (default; plan section
    10 deviation): the ITR 2020 population column is misprinted, so 2019 is not used and
    nothing is carried forward; P_t for 2021-2023 is the ITR 2022 population."""
    rows = panel.load_panel() if rows is None else rows
    tab, uncl = {}, []
    for u in sorted({r["unit"] for r in rows}):
        got = {r["year"]: r for r in rows if r["unit"] == u}
        p19 = got[2019]["est_population"] if 2019 in got else None
        p21 = got[2021]["est_population"] if 2021 in got else None
        vals, yrs = [], []
        for t in INTENSITY_YEARS:
            if t not in got or got[t]["screened"] is None:
                continue
            if t == 2019:
                P = p19 if population_2019 else None
            else:
                P = p21 if p21 is not None else (p19 if population_2019 else None)
            if P is None or P <= 0:
                continue
            vals.append(got[t]["screened"] / P)
            yrs.append(t)
        if vals:
            tab[u] = (sum(vals) / len(vals), yrs)
        else:
            uncl.append((u, "no year with both screened and an estimated population"
                            + ("" if population_2019 else
                               " (ITR 2020 populations not used; plan section 10)")))
    return tab, uncl


def intensity_strata(rows=None, population_2019: bool = False) -> dict:
    """unit -> 'high' | 'low': 'high' if the unit's intensity is above the median
    (`numpy.median`) over units with an intensity, otherwise 'low' (section 4.5).
    Unclassified units are absent (listed by `intensities`)."""
    tab, _ = intensities(rows, population_2019)
    med = float(np.median([tab[u][0] for u in sorted(tab)]))
    return {u: ("high" if tab[u][0] > med else "low") for u in sorted(tab)}


def _median(rows, population_2019=False) -> float:
    tab, _ = intensities(rows, population_2019)
    return float(np.median([tab[u][0] for u in sorted(tab)]))


# ---------------------------------------------------------------- decomposition (4.4)

def _cascade(rows, year) -> tuple:
    """({unit: (S, T, D)} for units with S, T and D present and positive and D < S in
    `year`; excluded [{unit, year, reason}]; testing definition of the year)."""
    ok, excl, tdef = {}, [], set()
    for r in sorted((r for r in rows if r["year"] == year), key=lambda r: r["unit"]):
        tdef.add(r.get("tested_definition", "tested"))
        S_, T_, D_ = r["screened"], r["tested"], r["diagnosed"]
        why = [f"{k} NA" if v is None else f"{k}=0" for k, v in
               (("S", S_), ("T", T_), ("D", D_)) if v is None or v == 0]
        if not why and D_ >= S_:
            why.append("D>=S")
        if why:
            excl.append({"unit": r["unit"], "year": year, "reason": "/".join(why)})
        else:
            ok[r["unit"]] = (S_, T_, D_)
    return ok, excl, "/".join(sorted(tdef))


def _boot_idx(G: int, draws: int) -> np.ndarray:
    rng = np.random.default_rng(SEED)  # reset per quantity (section 4.4)
    return np.stack([rng.integers(0, G, size=G) for _ in range(draws)])


def _cis(est: dict, mat: dict, valid) -> dict:
    return {q: _percentile(np.where(valid, mat[q], np.nan)) for q in est}


def _national(S_, T_, D_) -> dict:
    ss, st, sd = S_.sum(axis=-1), T_.sum(axis=-1), D_.sum(axis=-1)
    return {"ln_yield": np.log(sd / ss), "ln_testing": np.log(st / ss),
            "ln_positivity": np.log(sd / st)}


def decompose_level(rows=None, year: int = 2023, draws: int = DRAWS) -> dict:
    """National level of each component in `year` (section 4.4 a, last bullet), on the
    units present and positive in that year: ln(sum D/sum S) = ln(sum T/sum S) +
    ln(sum D/sum T), with cluster-bootstrap intervals."""
    rows = panel.load_panel() if rows is None else rows
    ok, excl, tdef = _cascade(rows, year)
    units = sorted(ok)
    A = np.array([ok[u] for u in units], dtype=float)
    est = {k: float(v) for k, v in _national(A[:, 0], A[:, 1], A[:, 2]).items()}
    idx = _boot_idx(len(units), draws)
    mat = _national(A[idx, 0], A[idx, 1], A[idx, 2])
    valid = np.ones(draws, dtype=bool)
    return {**est, "ci": _cis(est, mat, valid), "n_units": len(units), "units": units,
            "excluded": excl, "n_draws": draws, "n_valid": draws, "degenerate": 0,
            "testing_definition": tdef, "years": str(year)}


def decompose_change(rows=None, y0: int = 2021, y1: int = 2023,
                     draws: int = DRAWS) -> dict:
    """National change y0 -> y1 (section 4.4 a): on the units with S, T and D present and
    positive in both years, dln_yield = testing_part + positivity_part exactly, where
    testing_part = d ln(sum T/sum S) and positivity_part = d ln(sum D/sum T). Intervals:
    cluster bootstrap of units, generator reset for this quantity."""
    rows = panel.load_panel() if rows is None else rows
    c0, e0, t0 = _cascade(rows, y0)
    c1, e1, t1 = _cascade(rows, y1)
    units = sorted(set(c0) & set(c1))
    excl = e0 + e1
    present = {(r["unit"], r["year"]) for r in rows}
    for u in sorted({r["unit"] for r in rows}):
        for yy in (y0, y1):
            if (u, yy) not in present:
                excl.append({"unit": u, "year": yy, "reason": "no row"})
    A0 = np.array([c0[u] for u in units], dtype=float)
    A1 = np.array([c1[u] for u in units], dtype=float)

    def parts(a0, a1):
        n0, n1 = _national(*np.moveaxis(a0, -1, 0)), _national(*np.moveaxis(a1, -1, 0))
        return {"dln_yield": n1["ln_yield"] - n0["ln_yield"],
                "testing_part": n1["ln_testing"] - n0["ln_testing"],
                "positivity_part": n1["ln_positivity"] - n0["ln_positivity"]}

    est = {k: float(v) for k, v in parts(A0, A1).items()}
    idx = _boot_idx(len(units), draws)
    mat = parts(A0[idx], A1[idx])
    valid = np.ones(draws, dtype=bool)
    tdef = t0 if t0 == t1 else f"{t0}->{t1}"
    return {**est, "ci": _cis(est, mat, valid), "n_units": len(units), "units": units,
            "excluded": sorted(excl, key=lambda e: (e["unit"], e["year"])),
            "n_draws": draws, "n_valid": draws, "degenerate": 0,
            "testing_definition": tdef, "years": f"{y0}->{y1}"}


def _var_split(a, b) -> dict:
    """var(y) = var(a) + var(b) + 2 cov(a, b), unweighted, ddof = 1, along the last axis;
    covariance split equally between the two shares."""
    g = a.shape[-1]
    am = a - a.mean(axis=-1, keepdims=True)
    bm = b - b.mean(axis=-1, keepdims=True)
    va = (am * am).sum(axis=-1) / (g - 1)
    vb = (bm * bm).sum(axis=-1) / (g - 1)
    cab = (am * bm).sum(axis=-1) / (g - 1)
    vy = np.var(a + b, axis=-1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return {"var_total": vy, "var_testing": va, "var_positivity": vb, "cov": cab,
                "testing_share": (va + cab) / vy, "positivity_share": (vb + cab) / vy}


def decompose_variance(rows=None, year: int = 2023, draws: int = DRAWS) -> dict:
    """Between-State variance split in `year` (section 4.4 b): a = ln(T/S), b = ln(D/T)
    per unit; testing_share = (var a + cov)/var y, positivity_share = (var b + cov)/var y.
    A bootstrap draw with var(y) = 0 (every resampled y identical) is degenerate, counted
    and excluded from every quantity's interval."""
    rows = panel.load_panel() if rows is None else rows
    ok, excl, tdef = _cascade(rows, year)
    units = sorted(ok)
    A = np.array([ok[u] for u in units], dtype=float)
    a = np.log(A[:, 1] / A[:, 0])
    b = np.log(A[:, 2] / A[:, 1])
    est = {k: float(v) for k, v in _var_split(a, b).items()}
    if not (a + b != (a + b)[0]).any():
        est["testing_share"] = est["positivity_share"] = None
    idx = _boot_idx(len(units), draws)
    ya = (a + b)[idx]
    valid = np.any(ya != ya[:, :1], axis=1)
    mat = _var_split(a[idx], b[idx])
    return {**est, "ci": _cis(est, mat, valid), "n_units": len(units), "units": units,
            "excluded": excl, "n_draws": draws, "n_valid": int(valid.sum()),
            "degenerate": int((~valid).sum()), "testing_definition": tdef,
            "years": str(year)}


# ---------------------------------------------------------------- outputs

ELAST_FIELDS = ("analysis", "model", "weights", "zero", "years", "units", "estimate",
                "null", "se_cr1", "df", "model_ci_lo", "model_ci_hi", "boot_lo", "boot_hi",
                "draws", "n_valid", "degenerate", "n_units", "n_obs", "p", "n_singletons",
                "singletons", "n_excluded", "excluded", "n_all_zero_units",
                "all_zero_units", "converged", "iterations")
DECOMP_FIELDS = ("analysis", "status", "testing_definition", "years", "quantity",
                 "estimate", "boot_lo", "boot_hi", "draws", "n_valid", "degenerate",
                 "n_units", "n_excluded", "excluded")
STRATA_FIELDS = ("unit", "small_ut", "intensity", "intensity_years", "stratum", "median",
                 "intensity_registered_rule", "intensity_registered_years",
                 "stratum_registered_rule", "median_registered_rule", "note")
SAMEDEF_FIELDS = ELAST_FIELDS[:1] + ("status", "screened_heading") + ELAST_FIELDS[1:24]
TIER_FIELDS = ("stratum", "analysis", "unit", "small_ut", "intensity", "years", "n_years",
               "diagnosed", "screened", "y_log", "v_log", "post_mean_log", "post_sd_log",
               "post_lo_log", "post_hi_log", "post_per_100k", "post_lo_per_100k",
               "post_hi_per_100k", "rank_lo", "rank_hi", "n_ranked", "tier",
               "stratum_k", "stratum_mu_log", "stratum_mu_per_100k",
               "stratum_ci_lo_per_100k", "stratum_ci_hi_per_100k", "stratum_tau2",
               "stratum_i2", "tier_all_units", "tier_agrees")


def _excl_text(excl: list) -> str:
    return ";".join(f"{e['unit']} {e['year']} {_short(e['reason']) or e['reason']}"
                    for e in excl)


def _elast_row(label, model, units_label, r) -> dict:
    return {"analysis": label, "model": model, "weights": r.get("weights", "none"),
            "zero": r.get("zero", "kept"), "years": ";".join(map(str, r["years"])),
            "units": units_label, "estimate": r["beta"], "null": 1, "se_cr1": r["se"],
            "df": r["df"], "model_ci_lo": r["model_ci"][0], "model_ci_hi": r["model_ci"][1],
            "boot_lo": r["boot_ci"][0], "boot_hi": r["boot_ci"][1], "draws": r["n_draws"],
            "n_valid": r["n_valid"], "degenerate": r["degenerate"],
            "n_units": r["n_units"], "n_obs": r["n_obs"], "p": r["p"],
            "n_singletons": len(r["singletons"]), "singletons": ";".join(r["singletons"]),
            "n_excluded": len(r["excluded"]), "excluded": _excl_text(r["excluded"]),
            "n_all_zero_units": len(r["all_zero_units"]) if "all_zero_units" in r else None,
            "all_zero_units": ";".join(r.get("all_zero_units", [])) or None,
            "converged": r.get("converged"), "iterations": r.get("iterations")}


def _decomp_rows(analysis, status, r, quantities) -> list:
    out = []
    for q in quantities:
        lo, hi = r["ci"][q]
        out.append({"analysis": analysis, "status": status,
                    "testing_definition": r["testing_definition"], "years": r["years"],
                    "quantity": q, "estimate": r[q], "boot_lo": lo, "boot_hi": hi,
                    "draws": r["n_draws"], "n_valid": r["n_valid"],
                    "degenerate": r["degenerate"], "n_units": r["n_units"],
                    "n_excluded": len(r["excluded"]),
                    "excluded": _excl_text(r["excluded"])})
    return out


CHANGE_Q = ("dln_yield", "testing_part", "positivity_part")
LEVEL_Q = ("ln_yield", "ln_testing", "ln_positivity")
VAR_Q = ("var_total", "var_testing", "var_positivity", "cov", "testing_share",
         "positivity_share")


def build_results() -> dict:
    """Every estimate written by `build`, as Python objects."""
    rows = panel.load_panel()
    res = {"main": elasticity(rows), "high": elasticity(rows, stratum="high"),
           "low": elasticity(rows, stratum="low"), "poisson": poisson_fe_elasticity(rows),
           "samedef": elasticity_same_definition(rows),
           "change": decompose_change(rows, 2021, 2023),
           "levels": {y: decompose_level(rows, y) for y in MAIN_DECOMP_YEARS},
           "variance": {y: decompose_variance(rows, y) for y in MAIN_DECOMP_YEARS},
           "sens_variance_2022": decompose_variance(rows, 2022),
           "sens_change_2021_2022": decompose_change(rows, 2021, 2022),
           "sens_change_2022_2023": decompose_change(rows, 2022, 2023)}
    strata = intensity_strata(rows)
    res["strata"] = strata
    res["tiers"] = {s: Y.analyse_pooled(rows=rows,
                                        units=sorted(u for u, v in strata.items() if v == s))
                    for s in ("high", "low")}
    res["tiers_all"] = Y.analyse_pooled(rows=rows)
    return res


def build() -> dict:
    """file name -> CSV text for every file under outputs/ext written by this module."""
    rows = panel.load_panel()
    small = {r["unit"]: r["small_ut"] for r in rows}
    R = build_results()

    elast = [_elast_row("main", "fe_wls", "all", R["main"]),
             _elast_row("stratum high", "fe_wls", "high intensity", R["high"]),
             _elast_row("stratum low", "fe_wls", "low intensity", R["low"]),
             _elast_row("poisson", "poisson_fe", "all", R["poisson"])]

    dec = _decomp_rows("change", "main", R["change"], CHANGE_Q)
    for y in MAIN_DECOMP_YEARS:
        dec += _decomp_rows("level", "main", R["levels"][y], LEVEL_Q)
    for y in MAIN_DECOMP_YEARS:
        dec += _decomp_rows("variance", "main", R["variance"][y], VAR_Q)
    dec += _decomp_rows("variance", "sensitivity", R["sens_variance_2022"], VAR_Q)
    dec += _decomp_rows("change", "sensitivity", R["sens_change_2021_2022"], CHANGE_Q)
    dec += _decomp_rows("change", "sensitivity", R["sens_change_2022_2023"], CHANGE_Q)

    tab, uncl = intensities(rows)
    tab_r, uncl_r = intensities(rows, population_2019=True)
    st_r = intensity_strata(rows, population_2019=True)
    med, med_r = _median(rows), _median(rows, True)
    pooled_units = {s["unit"] for s in R["tiers_all"][1]}
    strata_out = []
    for u in sorted({r["unit"] for r in rows}):
        note = []
        if u not in tab:
            note.append(dict(uncl)[u])
        elif u not in pooled_units:
            note.append("no pooled 2021-2023 value (section 3.3); not in the tier "
                        "sensitivity")
        strata_out.append({
            "unit": u, "small_ut": small[u],
            "intensity": tab[u][0] if u in tab else None,
            "intensity_years": ";".join(map(str, tab[u][1])) if u in tab else None,
            "stratum": R["strata"].get(u, "unclassified"), "median": med,
            "intensity_registered_rule": tab_r[u][0] if u in tab_r else None,
            "intensity_registered_years": (";".join(map(str, tab_r[u][1]))
                                           if u in tab_r else None),
            "stratum_registered_rule": st_r.get(u, "unclassified"),
            "median_registered_rule": med_r, "note": "; ".join(note) or None})

    tier_all = {s["unit"]: s["tier"] for s in R["tiers_all"][1]}
    tiers_out = []
    for s in ("high", "low"):
        pool, states, _ = R["tiers"][s]
        label = f"2021-2023 {s} intensity"
        for st in states:
            row = Y._state_row(st, label, small, len(states))
            row.update({"stratum": s, "intensity": tab[st["unit"]][0],
                        "stratum_k": pool["k"], "stratum_mu_log": pool["mu"],
                        "stratum_mu_per_100k": Y._ex(pool["mu"]),
                        "stratum_ci_lo_per_100k": Y._ex(pool["ci"][0]),
                        "stratum_ci_hi_per_100k": Y._ex(pool["ci"][1]),
                        "stratum_tau2": pool["tau2"], "stratum_i2": pool["i2"],
                        "tier_all_units": tier_all[st["unit"]],
                        "tier_agrees": st["tier"] == tier_all[st["unit"]]})
            tiers_out.append(row)

    same = _elast_row("same screened definition (post hoc)", "fe_wls", "all", R["samedef"])
    same.update({"status": "post hoc sensitivity",
                 "screened_heading": SAME_DEFINITION_HEADING})

    return {"d1_elasticity.csv": Y.render(ELAST_FIELDS, elast),
            "d1_elasticity_samedef.csv": Y.render(SAMEDEF_FIELDS, [same]),
            "d1_decomposition.csv": Y.render(DECOMP_FIELDS, dec),
            "d1_intensity_strata.csv": Y.render(STRATA_FIELDS, strata_out),
            "d1_tiers_by_intensity.csv": Y.render(TIER_FIELDS, tiers_out)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    built = build()
    for name, text in built.items():
        with open(OUT / name, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    print(built["d1_elasticity.csv"])


if __name__ == "__main__":
    main()
