"""Task 4 (extension): D1 elasticity of diagnoses to screening volume, Poisson FE
sensitivity, intensity strata and cascade decomposition (extension plan sections 3.3,
4.3, 4.4, 4.5 and 9)."""
import csv
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "outputs" / "ext"

from src.ext import d1_saturation as S  # noqa: E402

needs_data = pytest.mark.skipif(not EXTRACTED.is_dir(), reason="data/extracted absent")
SEED = 20261119


def _csv(name):
    with open(OUT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- synthetic panels

UNIT_FE = {"A": -6.0, "B": -5.2, "C": -7.1, "D": -6.6, "E": -5.9}
YEAR_FE = {2018: 0.0, 2019: 0.15, 2021: -0.3, 2022: -0.45, 2023: -0.6}


def _exact_arrays(slope=0.7, drop=()):
    """y = alpha_u + lambda_t + slope * x exactly, x varying within units."""
    ys, xs, us, ts, ws = [], [], [], [], []
    for i, u in enumerate(sorted(UNIT_FE)):
        for j, t in enumerate(sorted(YEAR_FE)):
            if (u, t) in drop:
                continue
            x = 9.0 + 0.37 * i + 0.91 * j + 0.13 * ((i * 7 + j * 3) % 5)
            ys.append(UNIT_FE[u] + YEAR_FE[t] + slope * x)
            xs.append(x)
            us.append(u)
            ts.append(t)
            ws.append(10.0 + 3 * i + j)
    return (np.array(ys), np.array(xs), np.array(us), np.array(ts), np.array(ws))


def _rows(slope=0.7, noise=True):
    """Panel rows whose diagnosed counts follow D = exp(alpha + lambda) * S^slope."""
    rows = []
    for i, u in enumerate(sorted(UNIT_FE)):
        for j, t in enumerate(sorted(YEAR_FE)):
            s = int(20000 * (1 + i) * (1 + 0.6 * j) * (1 + 0.2 * ((i + 2 * j) % 3)))
            mu = math.exp(UNIT_FE[u] + YEAR_FE[t] + 4.0) * s ** slope / 10.0
            d = max(1, int(round(mu * (1.0 + (0.05 * ((i * 3 + j) % 4) - 0.075
                                                if noise else 0.0)))))
            rows.append({"unit": u, "year": t, "screened": s, "tested": max(d, s // 20),
                         "diagnosed": d, "tested_definition":
                             "examined" if t == 2022 else "tested",
                         "est_population": None, "small_ut": False})
    return rows


# ---------------------------------------------------------------- fixed effects

def test_fe_recovers_known_slope():
    y, x, u, t, w = _exact_arrays(0.7)
    beta, n = S.fe_wls(y, x, u, t, w)
    assert beta == pytest.approx(0.7, abs=1e-9)
    assert n == 25
    # unweighted too
    beta1, _ = S.fe_wls(y, x, u, t, np.ones_like(w))
    assert beta1 == pytest.approx(0.7, abs=1e-9)


def test_fe_unbalanced():
    y, x, u, t, w = _exact_arrays(0.7, drop={("B", 2021), ("D", 2018)})
    beta, n = S.fe_wls(y, x, u, t, w)
    assert beta == pytest.approx(0.7, abs=1e-9) and n == 23
    # through elasticity(): a unit missing a year keeps its other years
    rows = [r for r in _rows() if not (r["unit"] == "B" and r["year"] == 2021)]
    res = S.elasticity(rows, draws=50)
    assert res["n_units"] == 5 and res["n_obs"] == 24
    assert "B" in res["units"]


# ---------------------------------------------------------------- bootstrap

def test_cluster_bootstrap_resamples_units():
    rows = _rows()
    res = S.elasticity(rows, draws=6, return_draws=True)
    assert len(res["draws"]) == 6
    units = sorted(UNIT_FE)
    G = len(units)
    by = {u: [r for r in rows if r["unit"] == u] for u in units}
    rng = np.random.default_rng(SEED)
    for b in range(6):
        idx = rng.integers(0, G, size=G)
        y, x, cl, t, w = [], [], [], [], []
        for pos, k in enumerate(idx):
            for r in by[units[k]]:  # every drawn unit brings all its rows
                y.append(math.log(r["diagnosed"]))
                x.append(math.log(r["screened"]))
                cl.append(pos)  # each copy is its own cluster, with its own dummy
                t.append(r["year"])
                w.append(r["diagnosed"])
        ref, n = S.fe_wls(np.array(y), np.array(x), np.array(cl), np.array(t),
                          np.array(w, dtype=float))
        assert n == sum(len(by[units[k]]) for k in idx)
        assert res["draws"][b] == pytest.approx(ref, abs=1e-12), b
    # the generator is reset per analysis: the same call gives the same draws
    again = S.elasticity(rows, draws=6, return_draws=True)
    assert np.array_equal(again["draws"], res["draws"])
    lo, hi = res["boot_ci"]
    valid = res["draws"][~np.isnan(res["draws"])]
    assert (lo, hi) == tuple(np.quantile(valid, [0.025, 0.975]))
    assert res["degenerate"] + res["n_valid"] == 6


def test_model_ci_is_cr1_with_t_g_minus_1():
    from scipy import stats
    rows = _rows()
    res = S.elasticity(rows, draws=10)
    G, n, p = res["n_units"], res["n_obs"], res["p"]
    assert p == 1 + G + 4  # ln S, one dummy per unit, years except the earliest
    half = stats.t.ppf(0.975, G - 1) * res["se"]
    assert res["model_ci"] == pytest.approx((res["beta"] - half, res["beta"] + half))
    # CR1 by hand
    d = np.array([r["diagnosed"] for r in rows], dtype=float)
    s = np.array([r["screened"] for r in rows], dtype=float)
    X = S.design(np.log(s), np.array([r["unit"] for r in rows]),
                 np.array([r["year"] for r in rows]))
    y = np.log(d)
    coef = np.linalg.lstsq(X * np.sqrt(d)[:, None], y * np.sqrt(d), rcond=None)[0]
    r_ = y - X @ coef
    bread = np.linalg.inv(X.T @ (X * d[:, None]))
    meat = np.zeros((p, p))
    for u in sorted(UNIT_FE):
        m = np.array([r["unit"] == u for r in rows])
        sc = X[m].T @ (d[m] * r_[m])
        meat += np.outer(sc, sc)
    c = G / (G - 1) * (n - 1) / (n - p)
    V = c * bread @ meat @ bread
    assert res["se"] == pytest.approx(math.sqrt(V[0, 0]), rel=1e-9)
    assert res["beta"] == pytest.approx(coef[0], abs=1e-12)


def test_singletons_dropped_and_listed():
    rows = _rows()
    # unit F: one usable row (its other years have zero diagnoses)
    for t, d in ((2018, 3), (2019, 0), (2021, 0)):
        rows.append({"unit": "F", "year": t, "screened": 5000, "tested": 100,
                     "diagnosed": d, "tested_definition": "tested",
                     "est_population": None, "small_ut": False})
    res = S.elasticity(rows, draws=20)
    assert res["singletons"] == ["F"]
    assert "F" not in res["units"] and res["n_units"] == 5 and res["n_obs"] == 25
    base = S.elasticity(_rows(), draws=20)
    assert res["beta"] == pytest.approx(base["beta"], abs=1e-12)
    assert res["boot_ci"] == base["boot_ci"]  # dropped before resampling
    listed = {(e["unit"], e["year"]) for e in res["excluded"]}
    assert {("F", 2019), ("F", 2021)} <= listed


@needs_data
def test_singletons_real_panel_listed():
    # Lakshadweep: D = 2 in 2018, S = 0 in 2019, D = 0 in 2021-2023 -> one usable row
    res = S.elasticity(None, draws=5)
    assert "Lakshadweep" in res["singletons"]
    assert "Lakshadweep" not in res["units"]
    row = [r for r in _csv("d1_elasticity.csv") if r["analysis"] == "main"][0]
    assert "Lakshadweep" in row["singletons"].split(";")


# ---------------------------------------------------------------- Poisson

def test_poisson_fe_matches_known():
    # noiseless (non-integer) counts: the MLE is the true slope exactly
    rows = _rows(0.7, noise=False)
    for r in rows:
        r["diagnosed"] = (math.exp(UNIT_FE[r["unit"]] + YEAR_FE[r["year"]] + 4.0)
                          * r["screened"] ** 0.7 / 10.0)
    res = S.poisson_fe_elasticity(rows, draws=10)
    assert res["converged"] and res["beta"] == pytest.approx(0.7, abs=1e-8)

    # integer counts with zeros: zeros are kept, the score equations hold at the MLE,
    # an all-zero unit is listed and excluded
    rows = _rows(0.7)
    small = [{"unit": "Z", "year": t, "screened": 300 + 50 * k, "tested": 10,
              "diagnosed": 0, "tested_definition": "tested", "est_population": None,
              "small_ut": True} for k, t in enumerate(sorted(YEAR_FE))]
    few = [{"unit": "Y", "year": t, "screened": 2000 + 400 * k, "tested": 30,
            "diagnosed": d, "tested_definition": "tested", "est_population": None,
            "small_ut": True} for k, (t, d) in enumerate(zip(sorted(YEAR_FE),
                                                           (0, 2, 0, 1, 3)))]
    res = S.poisson_fe_elasticity(rows + small + few, draws=10)
    assert res["converged"]
    assert res["all_zero_units"] == ["Z"] and "Z" not in res["units"]
    assert res["n_obs"] == 30 and res["n_units"] == 6  # Y's zero rows are kept
    X, y, mu = res["_X"], res["_y"], res["_mu"]
    assert np.max(np.abs(X.T @ (y - mu))) < 1e-6
    assert abs(res["beta"] - 0.7) < 0.05
    lo, hi = res["model_ci"]
    assert lo < res["beta"] < hi


# ---------------------------------------------------------------- intensity strata

def _intensity_rows():
    # five units; populations printed for 2019 (ITR 2020) and 2021 (ITR 2022)
    spec = {  # unit: (P2019, P2021, {year: S})
        "A": (1000, 1000, {2019: 100, 2021: 300, 2022: 300, 2023: 300}),  # 0.25 / 0.3
        "B": (1000, None, {2019: 500, 2021: 500, 2022: 500, 2023: 100}),  # carried
        "C": (None, 2000, {2021: 200, 2022: 0, 2023: 400}),  # 0.1
        "D": (500, 1000, {2018: 900, 2019: 50, 2021: 50, 2022: 50}),  # 0.075 / 0.05
        "E": (None, None, {2021: 10, 2022: 10}),  # no population: unclassified
    }
    rows = []
    for u, (p19, p21, s) in spec.items():
        for t, sv in s.items():
            rows.append({"unit": u, "year": t, "screened": sv, "tested": None,
                         "diagnosed": 1, "est_population":
                             p19 if t == 2019 else (p21 if t == 2021 else None)})
    return rows


def test_intensity_strata_median_split():
    rows = _intensity_rows()
    # registered rule (section 4.5): 2019 with P2019; 2021-2023 with P2021, else P2019
    # carried forward; 2018 not used; S = 0 is a printed value and counts
    tab, uncl = S.intensities(rows, population_2019=True)
    assert tab["A"][0] == pytest.approx((0.1 + 0.3 + 0.3 + 0.3) / 4)
    assert tab["B"][0] == pytest.approx((0.5 + 0.5 + 0.5 + 0.1) / 4)
    assert tab["C"][0] == pytest.approx((0.1 + 0.0 + 0.2) / 3)
    assert tab["D"][0] == pytest.approx((0.1 + 0.05 + 0.05) / 3)  # 2018 not used
    assert [u for u, _ in uncl] == ["E"]
    st = S.intensity_strata(rows, population_2019=True)
    med = float(np.median([tab[u][0] for u in "ABCD"]))
    assert st == {u: ("high" if tab[u][0] > med else "low") for u in "ABCD"}
    assert st == {"A": "high", "B": "high", "C": "low", "D": "low"}
    # main rule (plan section 10 deviation): the printed 2019 populations are not used;
    # 2019 drops out and nothing is carried forward
    tab2, uncl2 = S.intensities(rows)
    assert tab2["A"][0] == pytest.approx(0.3)
    assert "B" not in tab2 and [u for u, _ in uncl2] == ["B", "E"]
    assert tab2["D"][0] == pytest.approx(0.05) and tab2["D"][1] == [2021, 2022]
    st2 = S.intensity_strata(rows)
    assert st2 == {"A": "high", "C": "low", "D": "low"}  # median 0.1 is low
    # odd count: the median unit is low
    assert sum(v == "high" for v in st2.values()) == 1


# ---------------------------------------------------------------- decomposition

def test_decomposition_adds_up():
    rows = _rows()
    ch = S.decompose_change(rows, 2021, 2023, draws=50)
    assert ch["testing_part"] + ch["positivity_part"] == pytest.approx(ch["dln_yield"],
                                                                        abs=1e-12)
    r0 = [r for r in rows if r["year"] == 2021]
    r1 = [r for r in rows if r["year"] == 2023]
    want = (math.log(sum(r["diagnosed"] for r in r1) / sum(r["screened"] for r in r1))
            - math.log(sum(r["diagnosed"] for r in r0) / sum(r["screened"] for r in r0)))
    assert ch["dln_yield"] == pytest.approx(want, abs=1e-12)
    for q in ("dln_yield", "testing_part", "positivity_part"):
        lo, hi = ch["ci"][q]
        assert lo <= hi
    va = S.decompose_variance(rows, 2023, draws=50)
    assert va["testing_share"] + va["positivity_share"] == pytest.approx(1.0, abs=1e-12)
    a = np.log([r["tested"] / r["screened"] for r in r1])
    b = np.log([r["diagnosed"] / r["tested"] for r in r1])
    assert va["var_total"] == pytest.approx(np.var(a + b, ddof=1), abs=1e-12)
    cov = np.cov(a, b, ddof=1)[0, 1]
    assert va["testing_share"] == pytest.approx((np.var(a, ddof=1) + cov) / va["var_total"])
    # a draw with var(y) = 0 is degenerate, counted and excluded: with two units, every
    # draw that picks the same unit twice
    two = [r for r in rows if r["unit"] == "A"] + [
        dict(r, unit="A2", diagnosed=2 * r["diagnosed"]) for r in rows if r["unit"] == "A"]
    deg = S.decompose_variance(two, 2023, draws=40)
    rng = np.random.default_rng(SEED)
    same = sum(int(i[0] == i[1]) for i in (rng.integers(0, 2, size=2) for _ in range(40)))
    assert 0 < same < 40
    assert deg["degenerate"] == same and deg["n_valid"] == 40 - same


@needs_data
def test_decomposition_excludes_2022_main():
    out = _csv("d1_decomposition.csv")
    main = [r for r in out if r["status"] == "main"]
    assert main
    for r in main:
        assert "2022" not in r["years"], r
        assert r["testing_definition"] == "tested"
    sens = [r for r in out if "2022" in r["years"]]
    assert {r["years"] for r in sens} == {"2022", "2021->2022", "2022->2023"}
    for r in sens:
        assert r["status"] == "sensitivity" and "examined" in r["testing_definition"]
    assert {r["years"] for r in main if r["analysis"] == "variance"} == {
        "2018", "2019", "2021", "2023"}
    assert {r["years"] for r in main if r["analysis"] == "change"} == {"2021->2023"}
    for r in out:
        assert float(r["boot_lo"]) <= float(r["boot_hi"]), r


# ---------------------------------------------------------------- outputs

@needs_data
def test_elasticity_output_rows():
    out = {r["analysis"]: r for r in _csv("d1_elasticity.csv")}
    assert set(out) == {"main", "stratum high", "stratum low", "poisson"}
    for r in out.values():
        assert float(r["model_ci_lo"]) <= float(r["estimate"]) <= float(r["model_ci_hi"])
        assert float(r["boot_lo"]) <= float(r["boot_hi"])
        assert int(r["n_valid"]) + int(r["degenerate"]) == int(r["draws"]) == 10000
    assert out["main"]["zero"] == "exclude" and out["poisson"]["zero"] == "kept"


@needs_data
def test_build_reproduces_committed_outputs():
    built = S.build()
    assert set(built) == {"d1_elasticity.csv", "d1_decomposition.csv",
                          "d1_tiers_by_intensity.csv", "d1_intensity_strata.csv",
                          "d1_elasticity_samedef.csv"}
    for name, text in built.items():
        assert (OUT / name).read_bytes() == text.encode("utf-8"), name


def test_same_definition_elasticity_is_the_main_model_on_2019_and_2021():
    """POST HOC (plan section 10, 20 November 2026): the main estimator, bootstrap and seed,
    restricted to the two data years whose screened column has the same printed heading."""
    rows = _rows(slope=0.6)
    got = S.elasticity_same_definition(rows, draws=200)
    want = S.elasticity(rows, years=(2019, 2021), draws=200)
    assert S.SAME_DEFINITION_YEARS == (2019, 2021)
    assert got["years"] == [2019, 2021]
    for k in ("beta", "se", "model_ci", "boot_ci", "n_units", "n_obs", "p"):
        assert got[k] == want[k], k
    # two years: one dummy per unit plus one year dummy beside ln S
    assert got["p"] == 1 + got["n_units"] + 1


@needs_data
def test_same_definition_output_row():
    (r,) = _csv("d1_elasticity_samedef.csv")
    assert r["analysis"] == "same screened definition (post hoc)"
    assert r["status"] == "post hoc sensitivity" and r["years"] == "2019;2021"
    assert r["screened_heading"] == S.SAME_DEFINITION_HEADING
    assert r["weights"] == "D" and r["zero"] == "exclude" and r["null"] == "1"
    assert float(r["model_ci_lo"]) <= float(r["estimate"]) <= float(r["model_ci_hi"])
    assert int(r["n_valid"]) + int(r["degenerate"]) == int(r["draws"]) == 10000
    main = {x["analysis"]: x for x in _csv("d1_elasticity.csv")}["main"]
    assert int(r["n_obs"]) < int(main["n_obs"])
