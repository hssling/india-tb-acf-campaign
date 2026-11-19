"""Task 6 (extension): D3 additionality, the specification curves, leave one out, the
headline labels and the descriptive cross-check (extension plan sections 3.3, 6, 7, 8, 9)."""
import csv
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "outputs" / "ext"

from src.ext import d3_additionality as D3  # noqa: E402
from src.ext import robustness as R  # noqa: E402

needs_data = pytest.mark.skipif(not EXTRACTED.is_dir(), reason="data/extracted absent")
SEED = 20261119
NEW_FILES = ("spec_curve.csv", "leave_one_out.csv", "headline.csv", "crosscheck.csv")


def _csv(name):
    with open(OUT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- synthetic D3 panels

UNIT_FE = {"A": 300.0, "B": 1200.0, "C": 650.0, "D": 90.0, "E": 2400.0}
YEAR_FE = {2019: 0.0, 2022: 140.0, 2023: 260.0}


def _acf(i, j):
    """ACF diagnoses varying within units, not collinear with the year effects."""
    return 20 + 35 * i + 17 * j + 11 * ((i * 5 + j * 3) % 4)


def _rows(theta=1.0, log=False, noise=False, extra=()):
    rows = []
    for i, u in enumerate(sorted(UNIT_FE)):
        for j, t in enumerate(sorted(YEAR_FE)):
            a = _acf(i, j)
            e = (7.0 * (((i + 1) * (j + 2)) % 5) - 14.0) if noise else 0.0
            if log:
                n = math.exp(math.log(UNIT_FE[u]) + YEAR_FE[t] / 1000.0
                             + theta * math.log(a) + e / 100.0)
            else:
                n = UNIT_FE[u] + YEAR_FE[t] + theta * a + e
            rows.append({"unit": u, "year": t, "screened": 100000, "diagnosed": a,
                         "notified_public": n, "notified_total": 1.3 * n,
                         "small_ut": False})
    return rows + list(extra)


def _fe_wls(y, x, unit, year, w):
    """Independent two-way FE WLS: columns x, one dummy per unit, one per year except
    the earliest; numpy.linalg.lstsq on sqrt(w)-scaled X and y."""
    units = sorted(set(unit))
    years = sorted(set(year))[1:]
    X = np.column_stack([x] + [[1.0 if u == v else 0.0 for u in unit] for v in units]
                        + [[1.0 if t == s else 0.0 for t in year] for s in years])
    sw = np.sqrt(np.asarray(w, dtype=float))
    return np.linalg.lstsq(X * sw[:, None], np.asarray(y) * sw, rcond=None)[0][0]


# ---------------------------------------------------------------- D3 (section 6)

def test_additionality_synthetic():
    rows = _rows(theta=1.0)
    for w in ("inverse_poisson", "none"):
        r = D3.additionality("public", "absolute", w, rows=rows, draws=200)
        assert r["theta"] == pytest.approx(1.0, abs=1e-9)
        assert r["n"] == 15 and r["G"] == 5
        assert r["model_ci"][0] <= 1.0 <= r["model_ci"][1]
        assert r["cluster_ci"][0] == pytest.approx(1.0, abs=1e-8)
        assert r["cluster_ci"][1] == pytest.approx(1.0, abs=1e-8)
        assert r["degenerate"] + r["n_valid"] == 200
    # total outcome is 1.3 x public, so theta is 1.3
    r = D3.additionality("total", "absolute", "inverse_poisson", rows=rows, draws=0)
    assert r["theta"] == pytest.approx(1.3, abs=1e-9)
    # log scale: ln N = alpha + lambda + 1 * ln A exactly
    r = D3.additionality("public", "log", "inverse_poisson", rows=_rows(1.0, log=True),
                         draws=0)
    assert r["theta"] == pytest.approx(1.0, abs=1e-9)
    # the main weights must be named; None is rejected
    with pytest.raises(ValueError):
        D3.additionality(weights=None, rows=rows, draws=0)


def test_d3_singletons_dropped():
    extra = [{"unit": "F", "year": 2023, "screened": 5000, "diagnosed": 40,
              "notified_public": 999.0, "notified_total": 1500.0, "small_ut": False},
             {"unit": "F", "year": 2022, "screened": 5000, "diagnosed": None,
              "notified_public": 950.0, "notified_total": 1400.0, "small_ut": False}]
    rows = _rows(noise=True, extra=extra)
    r = D3.additionality("public", "absolute", "inverse_poisson", rows=rows, draws=50)
    assert r["singletons"] == ["F"]
    assert "F" not in r["units"] and r["G"] == 5 and r["n"] == 15
    assert {"unit": "F", "year": 2022} in [{"unit": e["unit"], "year": e["year"]}
                                           for e in r["excluded"]]
    base = D3.additionality("public", "absolute", "inverse_poisson",
                            rows=_rows(noise=True), draws=50)
    assert r["theta"] == base["theta"]
    assert r["cluster_ci"] == base["cluster_ci"]  # dropped before resampling too


def test_d3_log_weight_is_N():
    rows = _rows(theta=0.6, log=True, noise=True)
    y = [math.log(r["notified_public"]) for r in rows]
    x = [math.log(r["diagnosed"]) for r in rows]
    u = [r["unit"] for r in rows]
    t = [r["year"] for r in rows]
    n = [r["notified_public"] for r in rows]
    got = D3.additionality("public", "log", "inverse_poisson", rows=rows, draws=0)["theta"]
    assert got == pytest.approx(_fe_wls(y, x, u, t, n), abs=1e-10)
    assert got != pytest.approx(_fe_wls(y, x, u, t, [1 / v for v in n]), abs=1e-6)
    unw = D3.additionality("public", "log", "none", rows=rows, draws=0)["theta"]
    assert unw == pytest.approx(_fe_wls(y, x, u, t, [1.0] * len(y)), abs=1e-10)
    # absolute scale: weights 1/N
    rows = _rows(theta=0.4, noise=True)
    y = [r["notified_public"] for r in rows]
    x = [float(r["diagnosed"]) for r in rows]
    got = D3.additionality("public", "absolute", "inverse_poisson", rows=rows,
                           draws=0)["theta"]
    assert got == pytest.approx(_fe_wls(y, x, u, t, [1 / v for v in y]), abs=1e-10)


def test_d3_zero_rules():
    # A = 0 kept on the absolute scale, excluded (and listed) on the log scale
    rows = _rows(noise=True)
    rows[4] = dict(rows[4], diagnosed=0)
    ab = D3.additionality("public", "absolute", "none", rows=rows, draws=0)
    lg = D3.additionality("public", "log", "none", rows=rows, draws=0)
    assert ab["n"] == 15 and lg["n"] == 14
    assert any(e["unit"] == rows[4]["unit"] and e["year"] == rows[4]["year"]
               for e in lg["excluded"])


def test_degenerate_draws_counted():
    # unit a: ACF varies within the unit; b and c: constant ACF. A draw is rank-deficient
    # (degenerate) unless it contains a together with b or c.
    rows = []
    for u, acf in (("a", (10, 30, 25)), ("b", (40, 40, 40)), ("c", (7, 7, 7))):
        for k, t in enumerate((2019, 2022, 2023)):
            rows.append({"unit": u, "year": t, "screened": 1000, "diagnosed": acf[k],
                         "notified_public": 100.0 + 50 * k + 0.8 * acf[k] + (k == 1) * 3,
                         "notified_total": 200.0, "small_ut": False})
    draws = 400
    r = D3.additionality("public", "absolute", "none", rows=rows, draws=draws,
                         return_draws=True)
    rng = np.random.default_rng(SEED)
    expect = 0
    for _ in range(draws):
        s = set(rng.integers(0, 3, size=3).tolist())
        expect += (0 not in s) or s == {0}
    assert r["degenerate"] == expect > 0
    assert r["n_valid"] + r["degenerate"] == draws
    d = r["draws"]
    assert int(np.isnan(d).sum()) == expect
    assert r["cluster_ci"] == tuple(float(v) for v in
                                    np.quantile(d[~np.isnan(d)], [0.025, 0.975]))


# ---------------------------------------------------------------- grids and labels (7, 8)

def test_grid_sizes():
    sizes = {"epsilon": 24, "rho": 24, "theta": 16}
    for est, k in sizes.items():
        g = R.spec_grid(est)
        assert len(g) == k
        keys = [tuple(sorted((a, v) for a, v in e.items() if a in R.AXES[est]))
                for e in g]
        assert len(set(keys)) == k
        mains = [e for e in g if e["main"]]
        assert len(mains) == 1
    m = {est: next(e for e in R.spec_grid(est) if e["main"]) for est in sizes}
    assert (m["epsilon"]["weights"], m["epsilon"]["zero"], m["epsilon"]["years"],
            m["epsilon"]["units"]) == ("D", "exclude", "all five", "all")
    assert (m["rho"]["measure"], m["rho"]["denominator"], m["rho"]["weights"],
            m["rho"]["units"]) == ("pooled_eb", "reconstructed", "screened_2023", "all")
    assert (m["theta"]["outcome"], m["theta"]["scale"], m["theta"]["weights"],
            m["theta"]["units"]) == ("public", "absolute", "inverse_poisson", "all")
    assert {e["measure"] for e in R.spec_grid("rho")} == {"pooled_eb", "yield_2023",
                                                          "eb_2023"}
    assert R.NULLS == {"epsilon": 1.0, "rho": 0.0, "theta": 0.0}


def test_exact_null_does_not_agree():
    assert R.agrees(1.0, 0.24, 1.0) is False
    assert R.agrees(0.0, -0.8, 0.0) is False
    assert R.agrees(0.5, 0.24, 1.0) is True
    assert R.agrees(1.2, 0.24, 1.0) is False
    a = R.agreement([0.2, 1.0, 0.9, 1.1], main=0.24, null=1.0)
    assert (a["n"], a["n_agree"]) == (4, 2) and a["share"] == 0.5


def test_noncomputable_counts_as_disagree():
    a = R.agreement([None, 0.3, 0.2, None], main=0.24, null=1.0)
    assert a["n"] == 4 and a["n_agree"] == 2 and a["n_noncomputable"] == 2
    assert a["share"] == 0.5


def test_headline_label_rule():
    assert R.label_rule((0.02, 0.5), 1.0, 0.8) == "supported"
    assert R.label_rule((0.02, 0.5), 1.0, 0.79) == "not established"
    assert R.label_rule((0.02, 1.2), 1.0, 1.0) == "not established"
    assert R.label_rule((1.2, 1.5), 1.0, 1.0) == "supported"
    assert R.label_rule((-0.93, 0.02), 0.0, 1.0) == "not established"
    assert R.label_rule((0.0, 0.4), 0.0, 1.0) == "not established"  # touches the null
    assert R.label_rule((None, None), 0.0, 1.0) == "not established"
    # 8 of 10 agree (one non-computable, one at the null) => exactly 80%
    a = R.agreement([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, None, 0.0], main=0.3,
                    null=0.0)
    assert a["share"] == 0.8
    assert R.label_rule((0.05, 0.6), 0.0, a["share"]) == "supported"


# ---------------------------------------------------------------- real data

@pytest.fixture(scope="module")
def loo():
    return R.leave_one_out()


@needs_data
def test_rho_loo_omits_unit_only(loo):
    from src.ext import d2_targeting as T
    units, x, y, w, _ = T.alignment_sample()
    rows = [r for r in loo if r["estimate"] == "rho" and r["omission"] == "state"]
    assert len(rows) == 35
    for r in rows:
        keep = [i for i, u in enumerate(units) if u != r["omitted"]]
        expect = T.weighted_spearman(x[keep], y[keep], w[keep])
        assert r["value"] == pytest.approx(expect, abs=1e-15), r["omitted"]
    # Lakshadweep has no pooled value: omitting it leaves the main sample unchanged
    lak = next(r for r in rows if r["omitted"] == "Lakshadweep")
    assert lak["diff"] == 0.0


@needs_data
def test_loo_most_influential(loo):
    for est in ("epsilon", "rho", "theta"):
        for om in ("state", "year"):
            rs = [r for r in loo if r["estimate"] == est and r["omission"] == om
                  and r["computable"]]
            assert rs
            top = [r for r in rs if r["most_influential"]]
            assert len(top) == 1
            best = max(abs(r["diff"]) for r in rs)
            first = next(r for r in rs if abs(r["diff"]) == best)  # sorted order
            assert top[0]["omitted"] == first["omitted"]
    years = {(r["estimate"], r["omitted"]) for r in loo if r["omission"] == "year"}
    assert {o for e, o in years if e == "theta"} == {"2019", "2022", "2023"}
    assert {o for e, o in years if e == "rho"} == {"2021", "2022", "2023"}
    assert len({o for e, o in years if e == "epsilon"}) == 5


@needs_data
def test_headline_labels_follow_rule():
    rows = _csv("headline.csv")
    assert [r["estimate"] for r in rows] == ["epsilon", "rho", "theta"]
    curve = _csv("spec_curve.csv")
    for r in rows:
        ent = [c for c in curve if c["estimate"] == r["estimate"]]
        n_agree = sum(c["agrees"] == "yes" for c in ent)
        assert int(r["n_entries"]) == len(ent) and int(r["n_agree"]) == n_agree
        assert float(r["agreement_share"]) == n_agree / len(ent)
        ci = (float(r["ci_lo"]), float(r["ci_hi"]))
        assert r["label"] == R.label_rule(ci, float(r["null"]), n_agree / len(ent))


@needs_data
def test_spec_curve_main_matches_earlier_outputs():
    curve = {c["estimate"]: c for c in _csv("spec_curve.csv") if c["main"] == "yes"}
    e = next(r for r in _csv("d1_elasticity.csv") if r["analysis"] == "main")
    assert (curve["epsilon"]["value"], curve["epsilon"]["ci_lo"],
            curve["epsilon"]["ci_hi"]) == (e["estimate"], e["boot_lo"], e["boot_hi"])
    a = next(r for r in _csv("d2_alignment.csv") if r["analysis"] == "main")
    assert (curve["rho"]["value"], curve["rho"]["ci_lo"],
            curve["rho"]["ci_hi"]) == (a["estimate"], a["boot_lo"], a["boot_hi"])
    d = next(r for r in _csv("d3.csv") if r["role"] == "main")
    assert (curve["theta"]["value"], curve["theta"]["ci_lo"],
            curve["theta"]["ci_hi"]) == (d["estimate"], d["boot_lo"], d["boot_hi"])
    assert len(_csv("spec_curve.csv")) == 64


@needs_data
def test_outputs_reproducible():
    a, b = R.build(draws=60), R.build(draws=60)
    assert set(a) == set(NEW_FILES)
    for name in a:
        assert a[name] == b[name], name
        assert "\r" not in a[name]
    c, d = D3.build(draws=60), D3.build(draws=60)
    assert c == d and set(c) == {"d3.csv"} and "\r" not in c["d3.csv"]


@needs_data
def test_build_reproduces_committed_outputs():
    built = {**D3.build(), **R.build()}
    assert set(built) == {"d3.csv", *NEW_FILES}
    for name, text in built.items():
        assert (OUT / name).read_bytes() == text.encode("utf-8"), name
