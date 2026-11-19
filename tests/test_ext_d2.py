"""Task 5 (extension): D2 targeting alignment, tier shares and the marginal-shift scenario
(extension plan sections 3.3, 5.1, 5.2 and 9)."""
import csv
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "outputs" / "ext"

from src.ext import d2_targeting as T  # noqa: E402

needs_data = pytest.mark.skipif(not EXTRACTED.is_dir(), reason="data/extracted absent")
SEED = 20261119


def _csv(name):
    with open(OUT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _wpearson(x, y, w):
    """Independent weighted Pearson (numpy.cov with analytic weights)."""
    c = np.cov(np.vstack([x, y]), aweights=w)
    return c[0, 1] / math.sqrt(c[0, 0] * c[1, 1])


# ---------------------------------------------------------------- Spearman (5.1)

def test_spearman_known():
    # ties in x: average ranks [1, 2.5, 2.5, 4]; y ranks [1, 3, 2, 4]
    # Sxy = 4.5, Sxx = 4.5, Syy = 5  =>  rho = sqrt(0.9)
    x = [10.0, 20.0, 20.0, 30.0]
    y = [0.1, 0.9, 0.5, 1.2]
    assert T.weighted_spearman(x, y) == pytest.approx(math.sqrt(0.9), abs=1e-15)
    assert T.weighted_spearman(x, y, [1, 1, 1, 1]) == pytest.approx(math.sqrt(0.9),
                                                                     abs=1e-15)
    rho_sp = stats.spearmanr(x, y).statistic
    assert T.weighted_spearman(x, y) == pytest.approx(rho_sp, abs=1e-14)


def test_weighted_spearman_defined_as_plan():
    # section 5.1: unweighted average ranks, then the weighted Pearson of the ranks.
    # Hand example: ranks x [1, 2.5, 2.5, 4], y [1, 3, 2, 4], w [1, 1, 1, 3]:
    # weighted means 3 and 3; Sxy = 7.5, Sxx = 7.5, Syy = 8  =>  sqrt(7.5/8)
    x = [10.0, 20.0, 20.0, 30.0]
    y = [0.1, 0.9, 0.5, 1.2]
    w = [1.0, 1.0, 1.0, 3.0]
    assert T.weighted_spearman(x, y, w) == pytest.approx(math.sqrt(7.5 / 8), abs=1e-15)
    # the ranks are not weighted: replicating a unit by its weight would change them
    rep_x = [10.0, 20.0, 20.0, 30.0, 30.0, 30.0]
    rep_y = [0.1, 0.9, 0.5, 1.2, 1.2, 1.2]
    assert T.weighted_spearman(x, y, w) != pytest.approx(
        stats.spearmanr(rep_x, rep_y).statistic, abs=1e-6)
    # random data against an independent formula
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=25), rng.normal(size=25)
    a[3] = a[7]  # a tie
    wts = rng.uniform(1, 1e7, size=25)
    expect = _wpearson(stats.rankdata(a), stats.rankdata(b), wts)
    assert T.weighted_spearman(a, b, wts) == pytest.approx(expect, abs=1e-12)
    # undefined when either variable is constant
    assert T.weighted_spearman([1, 1, 1], [1, 2, 3]) is None


# ---------------------------------------------------------------- bootstrap and permutation

def test_bootstrap_recomputes_ranks():
    rng0 = np.random.default_rng(5)
    x, y = rng0.normal(size=12), rng0.normal(size=12)
    w = rng0.uniform(1, 100, size=12)
    got = T.bootstrap_rho(x, y, w, draws=300)
    rng = np.random.default_rng(SEED)
    exp = np.full(300, np.nan)
    for b in range(300):
        i = rng.integers(0, 12, size=12)
        xb, yb, wb = x[i], y[i], w[i]
        if np.all(xb == xb[0]) or np.all(yb == yb[0]):
            continue
        exp[b] = _wpearson(stats.rankdata(xb), stats.rankdata(yb), wb)
    assert np.allclose(got, exp, atol=1e-12, equal_nan=True)
    # a constant draw is degenerate (NaN)
    deg = T.bootstrap_rho(np.array([1.0, 1.0, 2.0]), np.array([3.0, 4.0, 5.0]),
                          np.ones(3), draws=200)
    assert np.isnan(deg).any() and not np.isnan(deg).all()


def test_permutation_reproducible():
    rng0 = np.random.default_rng(7)
    x, y = rng0.normal(size=15), rng0.normal(size=15)
    w = rng0.uniform(1, 50, size=15)
    a = T.permutation_rho(x, y, w, draws=500)
    b = T.permutation_rho(x, y, w, draws=500)
    assert np.array_equal(a, b)
    rng = np.random.default_rng(SEED)
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    exp = np.array([_wpearson(rx[rng.permutation(15)], ry, w) for _ in range(500)])
    assert np.allclose(a, exp, atol=1e-12)
    lo, hi = T.band(a)
    assert (lo, hi) == tuple(float(v) for v in np.quantile(a, [0.025, 0.975]))


def test_permutation_keeps_weights_with_units():
    # exposure ranks are permuted; yield ranks and weights stay with their units
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    y = np.array([2.0, 1.0, 4.0, 3.0, 6.0, 5.0])
    w = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 50.0])
    got = T.permutation_rho(x, y, w, draws=200)
    rng = np.random.default_rng(SEED)
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    keep, move = [], []
    for _ in range(200):
        p = rng.permutation(6)
        keep.append(_wpearson(rx[p], ry, w))
        move.append(_wpearson(rx[p], ry, w[p]))
    assert np.allclose(got, keep, atol=1e-12)
    assert not np.allclose(got, move, atol=1e-6)


# ---------------------------------------------------------------- scenario (5.2)

def _rows():
    S = {"a1": 1000, "a2": 3000, "b1": 5000, "b2": 15000, "c1": 7000, "z1": 900}
    D = {"a1": 30, "a2": 60, "b1": 10, "b2": 0, "c1": 20, "z1": None}
    return [{"unit": u, "year": 2023, "screened": S[u], "diagnosed": D[u]} for u in S]


TIERS = {"a1": "above", "a2": "above", "b1": "below", "b2": "below", "c1": "overlaps",
         "z1": "above"}


def test_shift_conserves_volume():
    r = T.marginal_shift(0.10, rows=_rows(), tiers=TIERS, epsilon=0.3,
                         elasticity_draws=np.full(50, 0.3))
    units = r["gainers"] + r["losers"]
    before = sum(u["screened_2023"] for u in units)
    after = sum(u["screened_after"] for u in units)
    assert after == pytest.approx(before, rel=1e-15)
    assert r["moved"] == pytest.approx(0.10 * (5000 + 15000))
    assert {u["unit"] for u in r["gainers"]} == {"a1", "a2"}
    assert {u["unit"] for u in r["losers"]} == {"b1", "b2"}  # D = 0 kept (section 3.3)
    assert all(u["r"] == pytest.approx(-0.10) for u in r["losers"])
    assert all(u["r"] == pytest.approx(2000 / 4000) for u in r["gainers"])
    assert [e["unit"] for e in r["excluded"]] == ["z1"]  # D NA in 2023: listed


def test_shift_zero_when_elasticity_zero():
    r = T.marginal_shift(0.10, rows=_rows(), tiers=TIERS, epsilon=0.0,
                         elasticity_draws=np.zeros(40))
    assert r["delta"] == 0.0
    assert r["ci"] == (0.0, 0.0)


def test_shift_linear_case():
    r = T.marginal_shift(0.10, rows=_rows(), tiers=TIERS, epsilon=1.0,
                         elasticity_draws=np.ones(40))
    expect = 0.5 * 30 + 0.5 * 60 - 0.10 * 10 - 0.10 * 0
    assert r["delta"] == pytest.approx(expect, rel=1e-12)
    assert r["pct"] == pytest.approx(100 * expect / 100, rel=1e-12)
    # interval from the draws, with degenerate (NaN) draws excluded
    draws = np.array([np.nan, 0.0, 1.0, 1.0, 2.0])
    r2 = T.marginal_shift(0.10, rows=_rows(), tiers=TIERS, epsilon=1.0,
                          elasticity_draws=draws)
    assert r2["n_valid"] == 4 and r2["degenerate"] == 1
    vals = [sum(d * ((1 + rr) ** e - 1) for d, rr in ((30, .5), (60, .5), (10, -.1), (0, -.1)))
            for e in (0.0, 1.0, 1.0, 2.0)]
    assert r2["ci"] == pytest.approx(tuple(np.quantile(vals, [0.025, 0.975])), rel=1e-12)


def test_shift_not_computable_without_a_tier():
    r = T.marginal_shift(0.10, rows=_rows(), tiers={"a1": "above", "c1": "overlaps"},
                         epsilon=0.3, elasticity_draws=np.full(5, 0.3))
    assert r["computable"] is False and r["delta"] is None


def test_shift_stratum_draws_paired():
    strata = {"a1": "high", "a2": "low", "b1": "high", "b2": "low"}
    hi = np.array([0.2, np.nan, 0.4, 0.3])
    lo = np.array([0.5, 0.6, np.nan, 0.5])
    r = T.marginal_shift(0.10, rows=_rows(), tiers=TIERS, strata=strata,
                         epsilon={"high": 0.3, "low": 0.5},
                         elasticity_draws={"high": hi, "low": lo})
    assert r["n_valid"] == 2 and r["degenerate"] == 2
    point = 30 * (1.5 ** 0.3 - 1) + 60 * (1.5 ** 0.5 - 1) + 10 * (0.9 ** 0.3 - 1)
    assert r["delta"] == pytest.approx(point, rel=1e-12)


# ---------------------------------------------------------------- real data

def _pooled_tiers():
    return {r["unit"]: r["tier"] for r in _csv("d1_states.csv")
            if r["analysis"] == "2021-2023"}


@needs_data
def test_scenario_uses_registered_tiers():
    from src.ext import panel
    tiers = _pooled_tiers()
    p23 = {r["unit"]: r for r in panel.load_panel() if r["year"] == 2023}

    def ok(u):
        return (u in p23 and p23[u]["screened"] is not None
                and p23[u]["diagnosed"] is not None)

    r = T.marginal_shift(0.10, epsilon=0.25, elasticity_draws=np.full(20, 0.25))
    assert [g["unit"] for g in r["gainers"]] == sorted(
        u for u, t in tiers.items() if t == "above" and ok(u))
    assert [g["unit"] for g in r["losers"]] == sorted(
        u for u, t in tiers.items() if t == "below" and ok(u))
    assert "Manipur" in {e["unit"] for e in r["excluded"]}  # above, D NA in 2023
    assert T.registered_tiers() == tiers


@needs_data
def test_alignment_main_sample():
    a = T.alignment()
    assert a["measure"] == "pooled_eb" and a["denominator"] == "reconstructed"
    assert a["weights"] == "screened_2023"
    assert a["n"] == 34 and [x["unit"] for x in a["listed"]] == ["Lakshadweep"]
    assert a["n_valid"] + a["degenerate"] == a["n_draws"] == 10000
    assert a["boot_ci"][0] <= a["boot_ci"][1] and a["perm_band"][0] < a["perm_band"][1]
    with pytest.raises(ValueError):
        T.alignment(weights=None)


@needs_data
def test_build_reproduces_committed_outputs():
    built = T.build()
    assert set(built) == {"d2_alignment.csv", "d2_tier_shares.csv", "d2_scenario.csv",
                          "d2_scenario_units.csv"}
    for name, text in built.items():
        assert (OUT / name).read_bytes() == text.encode("utf-8"), name
