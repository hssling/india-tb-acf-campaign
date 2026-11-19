"""Recompute the derived Q3 and Q4 values from their traced inputs, writing nothing.

Run as: python -I verification/check_outputs.py

No code of src/ is used; the arithmetic is written out again here, with the standard
library only. Tolerance 1e-6 (the outputs print 6 decimals).

(a) outputs/q4_states.csv, every row: the inputs (a, b, n2019 ... n2024) are those of
    check_inventory; then y = ln(b/a) with its Poisson interval y +- z sqrt(1/a + 1/b),
    w = 1/(1/a + 1/b), beta (OLS slope of ln N on year over the trend points present;
    placebo: ln(N2022/N2019)/3), x = y - beta, E = min(1, campaign/LGD) from
    data/extracted/exposure_share.csv (denominator set R) or
    exposure_share_reconstructed.csv (D), the trend points used, and the computable
    flag. A cell is blank exactly when its inputs are missing.
(b) outputs/q4_summary.csv: the primary analysis, the S8 January-October analysis and the
    placebo, under both denominators: WLS of x on E with weights w over the computable
    rows (computed here), compared with n, gamma0, gamma1, SE, t, the model intervals
    and exp(gamma1). The bootstrap intervals are NOT re-derived here: they are reproduced
    by the seeded run, python -I src/q4_dose_response.py --q4.
(c) outputs/q3_yield.csv: value = 100000 x diagnosed/screened (yield), screened/diagnosed
    (NNS) or 100 x ACF/notified (share), and the Wilson bounds recomputed.
"""
import csv
import math
import statistics
import sys
from decimal import Decimal
from pathlib import Path

try:  # imported as a package (pytest) or run as a script (python -I verification/...)
    from verification import check_inventory as ci
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import check_inventory as ci

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-6
Z = statistics.NormalDist().inv_cdf(0.975)
EXPOSURE = {"R": "exposure_share.csv", "D": "exposure_share_reconstructed.csv"}
YEARS = (2019, 2022, 2023, 2024)
N_COLS = ("n2019", "n2022", "n2023", "n2024")
# summary analysis -> (contrast, weights)
MODELS = {"primary": ci.FULL, "S8 January-October": ci.JANOCT, "placebo": ci.PLACEBO}


# ------------------------------------------------------------------ small numerics

def _num(s) -> float | None:
    s = str(s).strip()
    return float(s) if s else None


def _close(cell: str, expected: float | None, what: str, label: str, bad: list) -> None:
    got = _num(cell)
    if expected is None:
        if got is not None:
            bad.append(f"{label}: {what} is {cell} but its inputs give no value")
    elif got is None:
        bad.append(f"{label}: {what} is blank but its inputs give {expected:.6f}")
    elif abs(got - expected) > TOL:
        bad.append(f"{label}: {what} is {cell} but recomputed {expected:.6f}")


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0 or x >= 1.0:
        return 0.0 if x <= 0.0 else 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_quantile(p: float, df: int) -> float:
    """Upper-tail quantile of Student t by bisection on the incomplete beta function."""
    def cdf(t: float) -> float:
        tail = 0.5 * _betai(df / 2.0, 0.5, df / (df + t * t))
        return 1.0 - tail if t > 0 else tail
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if cdf(mid) < p else (lo, mid)
    return (lo + hi) / 2.0


def wls(E: list[float], x: list[float], w: list[float]) -> dict | None:
    n = len(E)
    if n < 3 or len(set(E)) < 2:
        return None
    W = sum(w)
    eb = sum(a * b for a, b in zip(w, E)) / W
    xb = sum(a * b for a, b in zip(w, x)) / W
    sxx = sum(a * (e - eb) ** 2 for a, e in zip(w, E))
    g1 = sum(a * (e - eb) * (v - xb) for a, e, v in zip(w, E, x)) / sxx
    g0 = xb - g1 * eb
    s2 = sum(a * (v - g0 - g1 * e) ** 2 for a, e, v in zip(w, E, x)) / (n - 2)
    se, se0 = math.sqrt(s2 / sxx), math.sqrt(s2 * (1.0 / W + eb * eb / sxx))
    t = t_quantile(0.975, n - 2)
    return {"n": n, "df": n - 2, "gamma0": g0, "gamma1": g1, "se_gamma1": se, "t_0975": t,
            "gamma0_model_lo": g0 - t * se0, "gamma0_model_hi": g0 + t * se0,
            "gamma1_model_lo": g1 - t * se, "gamma1_model_hi": g1 + t * se,
            "exp_gamma1": math.exp(g1)}


# ------------------------------------------------------------------ (a) Q4 states

def exposure(root: Path, dset: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for r in ci.read(root / "data" / "extracted" / EXPOSURE[dset]):
        ok = r["computable"] == "yes" and r["campaign_count"] != "" and r["lgd_count"] != ""
        out[r["unit"]] = min(1.0, int(r["campaign_count"]) / int(r["lgd_count"])) if ok \
            else None
    return out


def beta_of(points: dict[int, float | None], placebo: bool) -> float | None:
    if placebo:
        n19, n22 = points.get(2019), points.get(2022)
        return math.log(n22 / n19) / 3.0 if n19 and n22 else None
    pts = [(t, points[t]) for t in YEARS if points.get(t) is not None]
    if len(pts) < 2 or any(v == 0 for _, v in pts):
        return None
    ts, ls = [t for t, _ in pts], [math.log(v) for _, v in pts]
    tb, lb = statistics.fmean(ts), statistics.fmean(ls)
    return sum((t - tb) * (v - lb) for t, v in zip(ts, ls)) / sum((t - tb) ** 2 for t in ts)


def recompute_row(r: dict, E: dict) -> dict:
    """Expected y, interval, w, beta, x, E, trend years and computable flag of one row."""
    placebo = r["contrast"] == ci.PLACEBO
    points = {y: _num(r[c]) for y, c in zip(YEARS, N_COLS)}
    a, b = _num(r["a"]), _num(r["b"])
    out = {"y": None, "lo": None, "hi": None, "w": None}
    if a and b:
        y, h = math.log(b / a), Z * math.sqrt(1.0 / a + 1.0 / b)
        out.update(y=y, lo=y - h, hi=y + h, w=1.0 / (1.0 / a + 1.0 / b))
    beta = beta_of(points, placebo)
    e = E.get(r["unit"])
    out.update(beta=beta, E=e,
               x=out["y"] - beta if (out["y"] is not None and beta is not None) else None)
    out["computable"] = "yes" if (out["x"] is not None and e is not None) else "no"
    if placebo:
        out["used"] = "2019, 2022 (two-point placebo benchmark, §10.6)" if beta is not None \
            else ""
    else:
        out["used"] = ", ".join(str(t) for t in YEARS if points.get(t) is not None)
    return out


def state_problems(root: Path) -> tuple[list[str], int, dict]:
    bad: list[str] = []
    expo = {d: exposure(root, d) for d in EXPOSURE}
    recs: dict[tuple, list[dict]] = {}
    n = 0
    for r in ci.read(root / "outputs" / "q4_states.csv"):
        label = f"q4_states {r['unit']} ({r['contrast']}, {r['denominator_set']})"
        e = recompute_row(r, expo[r["denominator_set"]])
        for col, key in (("y", "y"), ("y_poisson_lo", "lo"), ("y_poisson_hi", "hi"),
                         ("w", "w"), ("beta", "beta"), ("x", "x"), ("E", "E")):
            _close(r[col], e[key], col, label, bad)
        if r["trend_points_used"] != e["used"]:
            bad.append(f"{label}: trend_points_used {r['trend_points_used']!r} but the "
                       f"trend values present give {e['used']!r}")
        if r["computable"] != e["computable"]:
            bad.append(f"{label}: computable={r['computable']!r} but recomputed "
                       f"{e['computable']!r}")
        n += 1
        if e["computable"] == "yes":
            recs.setdefault((r["denominator_set"], r["contrast"]), []).append(
                {"unit": r["unit"], "x": e["x"], "E": e["E"], "w": e["w"]})
    return bad, n, recs


# ------------------------------------------------------------------ (b) Q4 summary

def summary_problems(root: Path, recs: dict) -> tuple[list[str], int]:
    bad: list[str] = []
    guard = {r["item"]: r["value"] for r in ci.read(root / "data" / "extracted"
                                                    / "guard_result.csv")}
    if guard.get("primary contrast") != ci.FULL:
        return [f"guard_result.csv primary contrast is {guard.get('primary contrast')!r}, not "
                f"{ci.FULL!r}: the fallback trend variants are not covered by this check"], 0
    summ = {(r["analysis"], r["denominator_set"]): r
            for r in ci.read(root / "outputs" / "q4_summary.csv")}
    n = 0
    for analysis, contrast in MODELS.items():
        for dset in EXPOSURE:
            row = summ.get((analysis, dset))
            label = f"q4_summary {analysis} ({dset})"
            if row is None:
                bad.append(f"{label}: row missing")
                continue
            if row["contrast"] != contrast:
                bad.append(f"{label}: contrast {row['contrast']!r}, expected {contrast!r}")
            rs = sorted(recs.get((dset, contrast), []), key=lambda r: r["unit"])
            fit = wls([r["E"] for r in rs], [r["x"] for r in rs], [r["w"] for r in rs])
            if fit is None:
                bad.append(f"{label}: no fit is possible from the computable states rows")
                continue
            if str(fit["n"]) != row["n"] or str(fit["df"]) != row["t_df"]:
                bad.append(f"{label}: n/df {row['n']}/{row['t_df']} but recomputed "
                           f"{fit['n']}/{fit['df']}")
            for col in ("gamma0", "gamma0_model_lo", "gamma0_model_hi", "gamma1",
                        "se_gamma1", "t_0975", "gamma1_model_lo", "gamma1_model_hi",
                        "exp_gamma1"):
                _close(row[col], fit[col], col, label, bad)
            n += 1
    return bad, n


# ------------------------------------------------------------------ (c) Q3 yield

def wilson(x: int, n: int) -> tuple[float, float]:
    p = x / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return (0.0 if x == 0 else max(0.0, centre - half),
            1.0 if x == n else min(1.0, centre + half))


def q3_problems(root: Path) -> tuple[list[str], int]:
    bad: list[str] = []
    n = 0
    for r in ci.read(root / "outputs" / "q3_yield.csv"):
        if r["status"] not in ("computed", "not_computable") or r["numerator"] == "":
            continue
        x, d = int(r["numerator"]), int(r["denominator"])
        label = f"q3_yield {r['state']} {r['year']} {r['indicator']} ({r['source_id']})"
        lo, hi = wilson(x, d)
        ind = r["indicator"]
        if ind == "yield_diagnosed_per_100000":
            exp = (1e5 * x / d, 1e5 * lo, 1e5 * hi)
        elif ind == "nns":
            exp = (d / x if x else None, 1 / hi, 1 / lo if lo else None)
        else:
            exp = (100 * x / d, 100 * lo, 100 * hi)
        _close(r["value"], exp[0], "value", label, bad)
        _close(r["lower"], exp[1], "lower", label, bad)
        if exp[2] is None:
            if r["upper"] != "unbounded":
                bad.append(f"{label}: upper is {r['upper']!r}, expected 'unbounded'")
        else:
            _close(r["upper"], exp[2], "upper", label, bad)
        n += 1
    return bad, n


def problems(root: Path = ROOT) -> tuple[list[str], dict]:
    b1, n1, recs = state_problems(root)
    b2, n2 = summary_problems(root, recs)
    b3, n3 = q3_problems(root)
    return b1 + b2 + b3, {"states": n1, "models": n2, "q3": n3}


def main(root: Path = ROOT) -> int:
    bad, n = problems(root)
    if bad:
        for b in bad[:60]:
            print(f"FAIL: {b}")
        if len(bad) > 60:
            print(f"FAIL: ... and {len(bad) - 60} more")
        return 1
    print(f"OK: {n['states']} q4_states rows recomputed (y, interval, w, beta, x, E); "
          f"{n['models']} model fits (primary, S8, placebo x R, D) reproduce q4_summary "
          f"(bootstrap not re-derived: python -I src/q4_dose_response.py --q4); "
          f"{n['q3']} q3_yield rows recomputed (value, Wilson bounds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
