"""Q4 dose-response (analysis plan §9.6, §10; Task 7)."""
import math
import random
import statistics

import pytest

from src import q4_dose_response as q4
from src import source_checks as sc

FULL = {2019: 1000, 2022: 1100, 2023: 1200, 2024: 1300}


# ---------------------------------------------------------------- outcome, trend, excess

def test_zero_count_not_computable():
    for a, b in ((0, 1400), (1300, 0)):
        rec = q4.evaluate(a, b, FULL, q4.TREND_YEARS)
        assert rec["x"] is None and rec["y"] is None
        assert "zero count" in rec["reason"]
        assert q4.excess({"a": a, "b": b, "trend": FULL}) is None
    # a zero trend point makes the State not computable (never set to a value)
    rec = q4.evaluate(1300, 1400, {**FULL, 2022: 0}, q4.TREND_YEARS)
    assert rec["x"] is None and rec["beta"] is None and "zero count" in rec["reason"]
    # a zero outside the points in use does not matter (S3 omits 2019)
    rec = q4.evaluate(1300, 1400, {**FULL, 2019: 0}, q4.S3_YEARS)
    assert rec["x"] is not None
    # a missing outcome is listed with its reason, not imputed
    rec = q4.evaluate(None, 1400, FULL, q4.TREND_YEARS)
    assert rec["x"] is None and "missing" in rec["reason"]


def test_excess_value():
    beta = statistics.linear_regression(
        [2019, 2022, 2023, 2024], [math.log(v) for v in FULL.values()]).slope
    x = q4.excess({"a": 1300, "b": 1400, "trend": FULL})
    assert x == pytest.approx(math.log(1400 / 1300) - beta, abs=1e-12)


def test_trend_points_exclude_2020_2021():
    assert 2020 not in q4.TREND_YEARS and 2021 not in q4.TREND_YEARS
    pts = {**FULL, 2020: 400, 2021: 9000}
    beta, used, why = q4.trend_beta(pts, q4.TREND_YEARS)
    assert used == (2019, 2022, 2023, 2024) and why == ""
    want = statistics.linear_regression(
        list(FULL), [math.log(v) for v in FULL.values()]).slope
    assert beta == pytest.approx(want, abs=1e-12)
    with pytest.raises(ValueError):
        q4.trend_beta(pts, (2019, 2020, 2022, 2023, 2024))
    with pytest.raises(ValueError):
        q4.trend_beta(pts, (2021, 2022, 2023))


def test_trend_fallback_2022_2024():
    no2019 = {2022: 1100, 2023: 1200, 2024: 1300}
    beta, used, _ = q4.trend_beta(no2019, q4.TREND_YEARS)
    assert used == (2022, 2023, 2024)
    want = statistics.linear_regression([2022, 2023, 2024],
                                        [math.log(v) for v in no2019.values()]).slope
    assert beta == pytest.approx(want, abs=1e-12)
    assert q4.trend_beta({**no2019, 2019: None}, q4.TREND_YEARS)[1] == (2022, 2023, 2024)
    # fewer than two points: not computable
    beta, used, why = q4.trend_beta({2024: 1300}, q4.TREND_YEARS)
    assert beta is None and "fewer than two" in why


# ---------------------------------------------------------------- WLS and its interval

def test_wls_known_values():
    """Hand-solved: E = (0, 1, 2, 3), x = (1, 3, 2, 5), w = (1, 2, 1, 2).
    Σw = 6; Ē_w = 10/6 = 5/3; x̄_w = 19/6.
    Σw(E-Ē)² = (25 + 2·4 + 1 + 2·16)/9 = 66/9 = 22/3.
    Σw(E-Ē)(x-x̄) = (65 + 4 - 7 + 88)/18 = 150/18 = 25/3.
    γ1 = (25/3)/(22/3) = 25/22; γ0 = 19/6 - (25/22)(5/3) = 14/11.
    Residuals (-3/11, 13/22, -17/11, 7/22); Σw r² = 37/11; s² = (37/11)/(4-2) = 37/22.
    SE(γ1) = √((37/22)/(22/3)) = √(111/484) = √111/22."""
    E, x, w = [0, 1, 2, 3], [1, 3, 2, 5], [1, 2, 1, 2]
    slope, se, n = q4.wls(E, x, w)
    assert slope == pytest.approx(25 / 22, abs=1e-12)
    assert se == pytest.approx(math.sqrt(111) / 22, abs=1e-12)
    assert n == 4
    fit = q4.wls_fit(E, x, w)
    assert fit["gamma0"] == pytest.approx(14 / 11, abs=1e-12)
    assert fit["s2"] == pytest.approx(37 / 22, abs=1e-12)
    assert fit["df"] == 2
    t = q4.t_quantile(0.975, 2)
    assert fit["lo"] == pytest.approx(25 / 22 - t * math.sqrt(111) / 22, abs=1e-12)
    assert fit["hi"] == pytest.approx(25 / 22 + t * math.sqrt(111) / 22, abs=1e-12)
    # the weights set only the relative weighting: scaling them changes nothing
    s2, se2, _ = q4.wls(E, x, [10 * v for v in w])
    assert (s2, se2) == pytest.approx((slope, se), abs=1e-12)


def test_wls_minimum_not_met():
    assert q4.wls_fit([0, 1], [1, 2], [1, 1]) is None                   # fewer than 3
    assert q4.wls_fit([0.5, 0.5, 0.5], [1, 2, 3], [1, 1, 1]) is None    # one exposure value
    with pytest.raises(ValueError):
        q4.wls([0.5, 0.5, 0.5], [1, 2, 3], [1, 1, 1])


def test_t_quantile_tabulated():
    for df, tab in ((10, 2.228), (30, 2.042), (33, 2.035), (2, 4.303), (1, 12.706)):
        assert round(q4.t_quantile(0.975, df), 3) == tab
    assert q4.t_quantile(0.975, 100000) == pytest.approx(1.959964, abs=1e-4)
    assert q4.t_cdf(0.0, 7) == pytest.approx(0.5, abs=1e-15)
    assert q4.t_cdf(q4.t_quantile(0.975, 13), 13) == pytest.approx(0.975, abs=1e-12)


# ---------------------------------------------------------------- bootstrap

def _recs():
    rng = random.Random(5)
    return [{"unit": f"U{k:02d}", "E": rng.random(), "x": rng.gauss(0, 0.1),
             "w": rng.randint(100, 5000)} for k in range(12)]


def test_bootstrap_seeded_reproducible():
    recs = _recs()
    a = q4.bootstrap_ci(recs, draws=500)
    b = q4.bootstrap_ci(list(reversed(recs)), draws=500)     # input order is irrelevant
    assert a == b
    assert q4.bootstrap_ci(recs, draws=500, seed=1) != a
    # the draws are rng.choices(range(n), k=n) over the States sorted by name,
    # and the interval is the first and last cut of quantiles(n=40, inclusive)
    srt = sorted(recs, key=lambda r: r["unit"])
    rng = random.Random(20261118)
    vals = []
    for _ in range(500):
        idx = rng.choices(range(len(srt)), k=len(srt))
        vals.append(q4.wls([srt[i]["E"] for i in idx], [srt[i]["x"] for i in idx],
                           [srt[i]["w"] for i in idx])[0])
    cuts = statistics.quantiles(vals, n=40, method="inclusive")
    assert a["lo"] == pytest.approx(cuts[0], abs=1e-12)
    assert a["hi"] == pytest.approx(cuts[-1], abs=1e-12)
    assert a["valid"] == 500 and a["degenerate"] == 0
    assert q4.SEED == 20261118 and q4.DRAWS == 10_000


def test_bootstrap_counts_degenerate_draws():
    recs = [{"unit": "A", "E": 0.0, "x": 0.1, "w": 1}, {"unit": "B", "E": 0.0, "x": 0.2, "w": 1},
            {"unit": "C", "E": 1.0, "x": 0.5, "w": 1}]
    res = q4.bootstrap_ci(recs, draws=400)
    assert res["degenerate"] > 0 and res["valid"] + res["degenerate"] == 400


# ---------------------------------------------------------------- S8(a), S8(b)

def test_s8a_gamma1_invariant():
    recs = _recs()
    for r in recs:
        r["y"], r["beta"] = r["x"] + 0.02, 0.02
    base = q4.wls_fit([r["E"] for r in recs], [r["x"] for r in recs],
                      [r["w"] for r in recs])
    for f in (0.98, 0.95):
        scaled = q4.scale_records(recs, f)
        assert [r["w"] for r in scaled] == [r["w"] for r in recs]      # weights fixed
        fit = q4.wls_fit([r["E"] for r in scaled], [r["x"] for r in scaled],
                         [r["w"] for r in scaled])
        assert fit["gamma1"] == pytest.approx(base["gamma1"], abs=1e-9)
        assert fit["gamma0"] == pytest.approx(base["gamma0"] + math.log(f), abs=1e-9)
        assert q4.gamma1_invariant(base, fit)
    assert not q4.gamma1_invariant(base, {**base, "gamma1": base["gamma1"] + 1e-6})


def test_matrix_wls_matches_closed_form_and_recovers_exact_fit():
    E, x, w = [0, 1, 2, 3], [1, 3, 2, 5], [1, 2, 1, 2]
    m = q4.wls_matrix([[1, e] for e in E], x, w)
    c = q4.wls_fit(E, x, w)
    assert m["coef"][1] == pytest.approx(c["gamma1"], abs=1e-12)
    assert m["se"][1] == pytest.approx(c["se"], abs=1e-12)
    E3, L = [0.1, 0.4, 0.2, 0.9, 0.5, 0.7], [0.01, -0.02, 0.03, 0.0, 0.05, -0.01]
    y = [0.3 + 0.2 * e - 1.5 * l for e, l in zip(E3, L)]
    m = q4.wls_matrix([[1, e, l] for e, l in zip(E3, L)], y, [1, 2, 3, 4, 5, 6])
    assert m["coef"] == pytest.approx([0.3, 0.2, -1.5], abs=1e-9)
    assert m["df"] == 3


def test_s8b_singular_matrix_rule():
    assert q4.singular([[1.0, 0.0], [0.0, 0.0]])
    assert not q4.singular([[2.0, 0.0], [0.0, 3.0]])
    # singular when det is at most 1e-12 times the product of the diagonal entries
    assert q4.singular([[1.0, 1.0], [1.0, 1.0 + 1e-13]])
    assert not q4.singular([[1.0, 1.0], [1.0, 1.0 + 1e-6]])
    E, x, w = [0.1, 0.4, 0.2, 0.9, 0.5], [0.1, 0.2, 0.0, 0.3, 0.1], [1, 1, 1, 1, 1]
    # all ln r equal: collinear with the intercept -> singular
    assert q4.wls_matrix([[1, e, 0.03] for e in E], x, w) is None
    # all exposures equal: singular
    assert q4.wls_matrix([[1, 0.5, v] for v in (0.1, 0.2, 0.3, 0.0, 0.4)], x, w) is None
    recs = [{"unit": f"U{k}", "E": e, "x": v, "w": 1, "lnr": 0.03}
            for k, (e, v) in enumerate(zip(E, x))]
    assert q4.s8b_fit(recs)["status"].startswith("not computable")
    boot = q4.bootstrap_ci(
        [{**r, "lnr": v} for r, v in zip(recs, (0.0, 0.0, 0.0, 0.0, 0.1))],
        draws=300, covariate="lnr")
    assert boot["degenerate"] > 0 and boot["valid"] + boot["degenerate"] == 300


# ---------------------------------------------------------------- placebo

def test_placebo_uses_gate_choice():
    assert q4.placebo_sources(fallback=False)[2023] == sc.Q1216
    assert q4.placebo_sources(fallback=True)[2023] == sc.ITR2024
    assert q4.placebo_sources(fallback=False)[2022] == sc.ITR2023
    assert q4.placebo_sources(fallback=True)[2019] == sc.ITR2020
    rec = q4.placebo_evaluate(900, 1100, 1250)
    assert rec["y"] == pytest.approx(math.log(1250 / 1100))
    assert rec["beta"] == pytest.approx(math.log(1100 / 900) / 3)
    assert rec["x"] == pytest.approx(math.log(1250 / 1100) - math.log(1100 / 900) / 3)
    assert rec["w"] == pytest.approx(1 / (1 / 1100 + 1 / 1250))
    assert q4.placebo_evaluate(None, 1100, 1250)["x"] is None
    assert q4.placebo_evaluate(0, 1100, 1250)["x"] is None


# ---------------------------------------------------------------- interpretation, fallback

def test_interpretation_label_rule():
    assert q4.interpret((0.1, 0.5), (0.05, 0.6)) == "positive association"
    assert q4.interpret((-0.5, -0.1), (-0.6, -0.01)) == "negative association"
    assert q4.interpret((0.1, 0.5), (-0.01, 0.6)) == "no clear association"
    assert q4.interpret((-0.1, 0.5), (0.05, 0.6)) == "no clear association"
    assert q4.interpret((0.0, 0.5), (0.05, 0.6)) == "no clear association"   # 0 not above 0
    assert q4.interpret((0.1, 0.5), None) == "no clear association"
    assert q4.placebo_interpret((0.01, 0.2)) == q4.PLACEBO_DIFFERS
    assert q4.placebo_interpret((-0.2, -0.01)) == q4.PLACEBO_DIFFERS
    assert q4.placebo_interpret((-0.2, 0.3)) == q4.PLACEBO_NO_DIFF


def test_descriptive_fallback_when_minimum_not_met():
    recs = [{"unit": "A", "E": 0.2, "x": 0.1, "w": 10}, {"unit": "B", "E": 0.5, "x": 0.0, "w": 20}]
    res = q4.run_model(recs, draws=50)
    assert res["status"].startswith("descriptive only (§10.7)")
    assert res["gamma1"] is None
    recs = [{"unit": u, "E": 0.5, "x": v, "w": 10} for u, v in (("A", .1), ("B", .2), ("C", .3))]
    assert q4.run_model(recs, draws=50)["status"].startswith("descriptive only (§10.7)")


# ---------------------------------------------------------------- real data, both exposures

@pytest.fixture(scope="module")
def result():
    return q4.run_q4(draws=200)


def _row(result, analysis, dset):
    rows = [r for r in result["summary"] if r["analysis"] == analysis
            and r["denominator_set"] == dset]
    assert len(rows) == 1, (analysis, dset)
    return rows[0]


def test_runs_under_both_exposure_sets(result):
    assert result["guard"] == "pass" and result["primary_contrast"] == q4.FULL_YEAR
    assert _row(result, q4.PRIMARY, "R")["n"] == 16
    assert _row(result, q4.PRIMARY, "D")["n"] == 35
    assert _row(result, "S6b capped excluded", "R")["n"] == 14
    assert _row(result, "S6b capped excluded", "D")["n"] == 30
    for d in ("R", "D"):
        assert _row(result, "S7 population share", d)["status"].startswith("not run")
        assert _row(result, "S6a flagged excluded", d)["status"].startswith("empty")
        for a in ("S8(a) x0.98", "S8(a) x0.95"):
            assert _row(result, a, d)["gamma1_invariant"] == "yes"
        assert _row(result, q4.PLACEBO, d)["label"] in (q4.PLACEBO_DIFFERS,
                                                         q4.PLACEBO_NO_DIFF)
    states = [r for r in result["states"] if r["contrast"] == q4.FULL_YEAR]
    assert len(states) == 70
    r_rows = {r["unit"]: r for r in states if r["denominator_set"] == "R"}
    assert r_rows["Assam"]["computable"] == "no" and "exposure" in r_rows["Assam"]["reason"]
    assert r_rows["Bihar"]["computable"] == "yes"
    # the 2024 trend point and the outcome's 2024 count are the same number (§9.6)
    assert all(r["n2024"] == r["a"] for r in states if r["a"] != "")
    assert len([r for r in result["loo"] if r["denominator_set"] == "R"]) == 16


def test_exposure_is_exact_min_1_c_over_l():
    assert q4.exposure_share(1, 26) == 1 / 26
    assert q4.exposure_share(11, 11) == 1.0
    assert q4.exposure_share(12, 11) == 1.0                    # capped (E5)
    ex = q4.load_exposure("D")
    assert ex["Andhra Pradesh"]["E"] == 1 / 26                # file prints 0.038462
    assert ex["Uttarakhand"]["E"] == 8 / 13
    assert q4.load_exposure("R")["Assam"]["E"] is None


def test_s2_row_reports_full_sample_exposure_spread(result):
    for d in ("R", "D"):
        s2, p = _row(result, "S2 leave one out", d), _row(result, q4.PRIMARY, d)
        for k in ("exposure_sd", "exposure_min", "exposure_max", "exposure_mean_weighted",
                  "exposure_mean_unweighted"):
            assert s2[k] != "" and s2[k] == p[k]


def test_no_p_values_in_outputs(result):
    for rows in (result["summary"], result["states"], result["loo"]):
        for k in rows[0]:
            assert "p_value" not in k.lower() and "pvalue" not in k.lower()
