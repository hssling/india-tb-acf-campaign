"""Task 3 (extension): D1 pooled yield, empirical-Bayes shrinkage, rank intervals and tiers
(extension plan sections 3.3, 4.1, 4.2 and 9)."""
import csv
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "outputs" / "ext"

from src.ext import d1_yield as Y  # noqa: E402

needs_data = pytest.mark.skipif(not EXTRACTED.is_dir(), reason="data/extracted absent")


def _csv(name):
    with open(OUT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_dl_known_values():
    # Three published BCG vaccine trials (Colditz et al., JAMA 1994; metafor dat.bcg):
    # Hart & Sutherland 1977, TPT Madras 1980, Comstock et al. 1974.
    # (TB+ vaccinated, n vaccinated, TB+ control, n control); y = log risk ratio.
    trials = [(62, 13598, 248, 12867), (505, 88391, 499, 88391), (186, 50634, 141, 27338)]
    y = [math.log((a / n1) / (c / n2)) for a, n1, c, n2 in trials]
    v = [1 / a - 1 / n1 + 1 / c - 1 / n2 for a, n1, c, n2 in trials]
    # hand computation, DerSimonian-Laird (plan section 4.1), standard library only
    w = [1 / vi for vi in v]
    sw = w[0] + w[1] + w[2]
    mu_f = (w[0] * y[0] + w[1] * y[1] + w[2] * y[2]) / sw
    q = w[0] * (y[0] - mu_f) ** 2 + w[1] * (y[1] - mu_f) ** 2 + w[2] * (y[2] - mu_f) ** 2
    c = sw - (w[0] ** 2 + w[1] ** 2 + w[2] ** 2) / sw
    tau2 = max(0.0, (q - 2) / c)
    i2 = max(0.0, (q - 2) / q) * 100
    ws = [1 / (vi + tau2) for vi in v]
    mu = (ws[0] * y[0] + ws[1] * y[1] + ws[2] * y[2]) / (ws[0] + ws[1] + ws[2])
    se = math.sqrt(1 / (ws[0] + ws[1] + ws[2]))
    # the hand values, written out (Q = 88.9176, C = 193.1139)
    assert round(mu, 4) == -0.5813 and round(tau2, 4) == 0.4501 and round(i2, 4) == 97.7507

    r = Y.dl_pool(np.array(y), np.array(v))
    assert round(r["mu"], 4) == round(mu, 4) == -0.5813
    assert round(r["tau2"], 4) == round(tau2, 4) == 0.4501
    assert round(r["i2"], 4) == round(i2, 4) == 97.7507
    assert round(r["se"], 4) == round(se, 4)
    assert r["k"] == 3
    z = stats.norm.ppf(0.975)
    assert r["ci"] == pytest.approx((mu - z * se, mu + z * se), abs=1e-12)
    half = stats.t.ppf(0.975, 1) * math.sqrt(tau2 + se ** 2)  # t_{k-2}, k = 3
    assert r["pi"] == pytest.approx((mu - half, mu + half), abs=1e-12)


def test_dl_no_heterogeneity_gives_zero_tau2_and_i2():
    r = Y.dl_pool(np.array([0.1, 0.1, 0.1]), np.array([0.01, 0.02, 0.03]))
    assert r["tau2"] == 0.0 and r["i2"] == 0.0 and r["mu"] == pytest.approx(0.1)


def test_eb_shrinks_small_states_more():
    mu, tau2 = 0.0, 0.25
    y = np.array([1.0, 1.0])
    v = np.array([0.01, 1.0])  # the second unit is small (large sampling variance)
    m, sd = Y.eb_shrink(y, v, mu, tau2)
    assert abs(m[1] - mu) < abs(m[0] - mu)
    assert m[0] == pytest.approx((0.01 / 0.26) * mu + (0.25 / 0.26) * 1.0)
    assert sd[1] == pytest.approx(math.sqrt(1.0 * 0.25 / 1.25))
    # tau2 = 0: every posterior mean is mu with SD 0
    m0, sd0 = Y.eb_shrink(y, v, mu, 0.0)
    assert list(m0) == [mu, mu] and list(sd0) == [0.0, 0.0]


def test_rank_intervals_reproducible():
    m = np.array([0.0, 0.1, 0.5, -0.2])
    sd = np.array([0.1, 0.2, 0.05, 0.3])
    a = Y.rank_intervals(m, sd, np.random.default_rng(20261119))
    b = Y.rank_intervals(m, sd, np.random.default_rng(20261119))
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    assert all(1 <= lo <= hi <= 4 for lo, hi in zip(*a))
    # zero SD everywhere (tau2 = 0): every rank is 1
    lo, hi = Y.rank_intervals(np.zeros(3), np.zeros(3), np.random.default_rng(20261119))
    assert list(lo) == [1, 1, 1] and list(hi) == [1, 1, 1]


def test_tier_rule_uses_state_interval():
    assert Y.tier(0.2, 0.5, 0.1) == "above"
    assert Y.tier(-0.1, 0.5, 0.1) == "overlaps"
    assert Y.tier(-0.5, -0.2, 0.1) == "below"
    # extreme heterogeneity: tau2 = 10. The prediction interval of the pooled mean is very
    # wide and contains the State, but the tier uses the State's own posterior interval.
    mu, tau2 = 0.0, 10.0
    y, v = np.array([3.0, 0.05, -3.0]), np.array([0.01, 0.01, 0.01])
    m, sd, lo, hi, tiers = Y.classify(y, v, mu, tau2)
    z = stats.norm.ppf(0.975)
    assert lo == pytest.approx(m - z * sd) and hi == pytest.approx(m + z * sd)
    pi_half = stats.t.ppf(0.975, 1) * math.sqrt(tau2)
    assert -pi_half < y[0] < pi_half  # inside the prediction interval
    assert list(tiers) == ["above", "overlaps", "below"]


@needs_data
def test_outputs_have_intervals():
    pooled = _csv("d1_pooled.csv")
    states = _csv("d1_states.csv")
    assert {r["analysis"] for r in pooled} == {"2018", "2019", "2021", "2022", "2023",
                                               "2021-2023"}
    assert pooled and states
    for r in pooled:
        for lo, hi in (("ci_lo_log", "ci_hi_log"), ("pi_lo_log", "pi_hi_log"),
                       ("ci_lo_per_100k", "ci_hi_per_100k"),
                       ("pi_lo_per_100k", "pi_hi_per_100k")):
            assert r[lo] != "" and r[hi] != "" and float(r[lo]) <= float(r[hi]), (r, lo)
    for r in states:
        for lo, hi in (("post_lo_log", "post_hi_log"), ("post_lo_per_100k", "post_hi_per_100k"),
                       ("rank_lo", "rank_hi")):
            assert r[lo] != "" and r[hi] != "" and float(r[lo]) <= float(r[hi]), (r, lo)
        assert r["tier"] in ("above", "overlaps", "below")


@needs_data
def test_zero_years_excluded_and_listed():
    from src.ext import panel as P
    rows = P.load_panel()
    zeros = {(r["unit"], r["year"]) for r in rows if r["diagnosed"] == 0}
    assert ("Goa", 2023) in zeros and ("Lakshadweep", 2021) in zeros
    states = _csv("d1_states.csv")
    excluded = _csv("d1_excluded.csv")
    in_year = {(r["unit"], int(r["analysis"])) for r in states if r["analysis"] != "2021-2023"}
    listed = {(r["unit"], int(r["year"])): r["reason"] for r in excluded
              if r["analysis"] != "2021-2023" and r["analysis"] == r["year"]}
    pooled_listed = {(r["unit"], r["year"]): r["reason"] for r in excluded
                     if r["analysis"] == "2021-2023"}
    for key in zeros:
        assert key not in in_year, key
        assert key in listed and "zero diagnoses" in listed[key], key
        if key[1] in (2021, 2022, 2023):
            assert "zero diagnoses" in pooled_listed[(key[0], str(key[1]))], key
    # module level: the zero unit-year is not in the year's pooling sample
    assert "Goa" not in Y.year_sample(2023)[0]
    # pooled 2021-2023: zero unit-years are left out before summing, and the unit's
    # contributed years are counted
    pooled = {r["unit"]: r for r in states if r["analysis"] == "2021-2023"}
    assert pooled["Goa"]["n_years"] == "2"
    assert pooled["Goa"]["years"] == "2021;2022"
    goa = [r for r in rows if r["unit"] == "Goa" and r["year"] in (2021, 2022)]
    assert int(pooled["Goa"]["diagnosed"]) == sum(r["diagnosed"] for r in goa)
    assert int(pooled["Goa"]["screened"]) == sum(r["screened"] for r in goa)
    # Lakshadweep has D = 0 in 2021, 2022 and 2023: no pooled value, and listed
    assert "Lakshadweep" not in pooled
    assert Y.pooled_state_yield("Lakshadweep") == (None, None)
    assert ("Lakshadweep", "") in pooled_listed
    assert {(u, yr) for u, yr in listed if u == "Lakshadweep"} >= {
        ("Lakshadweep", 2021), ("Lakshadweep", 2022), ("Lakshadweep", 2023)}
    # NA rows are listed too (2023 Manipur, diagnosed NA)
    assert ("Manipur", 2023) in listed and ("Manipur", 2023) not in in_year


@needs_data
def test_pooled_state_yield_matches_output():
    states = {r["unit"]: r for r in _csv("d1_states.csv") if r["analysis"] == "2021-2023"}
    m, sd = Y.pooled_state_yield("Kerala")
    assert repr(m) == states["Kerala"]["post_mean_log"]
    assert repr(sd) == states["Kerala"]["post_sd_log"]
