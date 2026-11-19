"""Q4: dose-response (analysis plan §9-§10).

Order of analyses (Task 7): the guard; the primary analysis; S1-S7; S8 with S8(a) and
S8(b); the placebo. Every analysis is run under both district denominators:

- **R** (registered): data/extracted/exposure_share.csv, the LGD count under §9.3 as
  written;
- **D** (deviation): data/extracted/exposure_share_reconstructed.csv, the reconstruction
  from official notices (§13, 19 November 2026). The paper presents it as the main Q4
  analysis and labels it a deviation.

Guard (§9.5.2): each State's 2023 and 2024 counts in Rajya Sabha Question 1216 are
divided by its "notified" counts in Question 3467, after unit coarsening (§9.4). States
lacking either value are left out of that year and listed.

- The guard fails if the median 2023 ratio lies outside [0.95, 1.05] or the median
  2024 ratio is below 0.95. A 2024 median above 1.05 does not fail it (late reports);
  it is reported descriptively.
- A failure of Question 1216's own extraction checks counts as a failed guard,
  whatever the medians.
- The guard is not run (the full-year contrast stays primary) if Question 1216 passes
  its extraction checks but Question 3467 fails its own, or fewer than 10 States have
  both values for either year.
- Every State whose ratio lies outside [0.95, 1.05] in either year is a Q2 discrepancy;
  2024 ratios above 1.05 are labelled late-report-consistent.
- If the guard fails, the January-October contrast (S8) becomes primary with the
  fallback trend sources for 2023 and 2024 together (§9.6).

Model (§10.1-§10.3): x_s = ln(b_s/a_s) - β_s, with β_s the OLS slope of ln N on calendar
year over the trend points (2019, 2022, 2023, 2024; never 2020 or 2021); WLS of x on the
exposure share E with w = 1/(1/a + 1/b); model interval γ1 ± t(0.975, n-2) SE(γ1) with
s² = Σ w r²/(n-2); bootstrap of 10,000 draws over the States sorted by coarsened name,
random.Random(20261118) reset before each analysis, percentile interval from
statistics.quantiles(n=40, method="inclusive"). No P values (§10.8, §12).

Pure standard library (§11).

Run: python -I src/q4_dose_response.py --guard   (the guard; writes data/extracted/guard_*)
     python -I src/q4_dose_response.py --q4      (Q4; writes outputs/q4_*.csv)
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import math
import random
import statistics

from src import compare as cp
from src import source_checks as sc
from src import states as st

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "data/extracted"
OUT = ROOT / "outputs"
YEARS = (2023, 2024)
LO, HI = 0.95, 1.05
MIN_STATES = 10
LATE = "late-report-consistent"
MISSING_NOTE = "missing in one table: left out and listed"
ZERO_NOTE = "Q3467 count is 0: ratio undefined; left out and listed"

Counts = dict[int, dict[str, int]]   # year -> coarsened unit -> count


def ratios(q1216: Counts, q3467: Counts) -> dict[int, dict[str, float]]:
    """Per-year State ratios Q1216 / Q3467 over the units with both values (a zero
    denominator leaves the unit out; guard_rows gives it its own note)."""
    out = {}
    for y in YEARS:
        a, b = q1216.get(y, {}), q3467.get(y, {})
        out[y] = {u: a[u] / b[u] for u in sorted(a.keys() & b.keys()) if b[u]}
    return out


def guard(q1216: Counts, q3467: Counts, q1216_extraction_ok: bool,
          q3467_extraction_ok: bool) -> tuple[str, dict[int, float | None], list[dict]]:
    """(status, medians, flagged_states); status is pass, fail or not_run."""
    r = ratios(q1216, q3467)
    medians = {y: (statistics.median(r[y].values()) if r[y] else None) for y in YEARS}
    flagged = []
    for y in YEARS:
        for u, x in r[y].items():
            if x < LO or x > HI:
                flagged.append({"state": u, "year": y, "ratio": x,
                                "label": LATE if (y == 2024 and x > HI) else ""})
    if not q1216_extraction_ok:
        return "fail", medians, flagged
    if not q3467_extraction_ok or any(len(r[y]) < MIN_STATES for y in YEARS):
        return "not_run", medians, flagged
    m23, m24 = medians[2023], medians[2024]
    status = "fail" if (m23 < LO or m23 > HI or m24 < LO) else "pass"
    return status, medians, flagged


def guard_consequences(status: str, extraction: dict[str, str] | None = None) -> dict:
    """Primary contrast and trend sources implied by the guard (§9.5.2, §9.6)."""
    ext = extraction or {s: "pass" for s in (sc.Q1216, sc.Q3467, sc.ITR2020,
                                               sc.ITR2023, sc.ITR2024, sc.LS261,
                                               sc.Q1093)}
    failed = status == "fail"
    return {
        "primary": ("January-October 2025 vs 2024 (S8)" if failed
                    else "full-year 2025 vs 2024"),
        "full_year_role": "descriptive (§10.7)" if failed else "primary",
        "trend": sc.trend_points(ext, fallback=failed),
        "note": ("the guard was not run; the full-year contrast stays primary and the "
                 "paper states that the guard could not be run" if status == "not_run"
                 else ""),
    }


def guard_rows(q1216: Counts, q3467: Counts) -> list[dict]:
    """One row per year and unit in either table, with its ratio or the reason it is
    left out: missing in one table, or a Q3467 count of 0 (its own note)."""
    r = ratios(q1216, q3467)
    rows = []
    for y in YEARS:
        a, b = q1216.get(y, {}), q3467.get(y, {})
        for u in sorted(a.keys() | b.keys()):
            x = r[y].get(u)
            out = x is not None and (x < LO or x > HI)
            if x is not None:
                note = ""
            elif u in a and u in b and b[u] == 0:
                note = ZERO_NOTE
            else:
                note = MISSING_NOTE
            rows.append({"year": y, "unit": u, "q1216_notified": a.get(u, ""),
                         "q3467_notified": b.get(u, ""),
                         "ratio": "" if x is None else f"{x:.6f}",
                         "in_guard": "yes" if x is not None else "no",
                         "outside_0_95_1_05": "yes" if out else "no",
                         "q2_discrepancy": "yes" if out else "no",
                         "label": LATE if (out and y == 2024 and x > HI) else "",
                         "note": note})
    return rows


# ================================================================== run on the extracted tables

def _read(name: str) -> list[dict]:
    with open(EX / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _counts(name: str, columns: dict[str, int]) -> tuple[Counts, list[str]]:
    """Coarsened counts per year from an extracted parliamentary table; rows whose label
    is not computable are listed."""
    out: Counts = {y: {} for y in YEARS}
    unmapped = []
    for r in _read(name):
        if r["column"] not in columns or r["value"] == "":
            continue
        if not r["coarse_unit"]:
            unmapped.append(r["label_printed"])
            continue
        y = columns[r["column"]]
        out[y][r["coarse_unit"]] = out[y].get(r["coarse_unit"], 0) + int(r["value"])
    return out, unmapped


def _extraction() -> dict[str, str]:
    return {r["source"]: r["result"] for r in _read("q4_source_checks.csv")}


def run_guard() -> dict:
    q1216, u1 = _counts("pq_q1216.csv", {"2023_notified": 2023, "2024_notified": 2024})
    q3467, u2 = _counts("pq_q3467.csv", {"2023_notified": 2023, "2024_notified": 2024})
    ext = _extraction()
    status, medians, flagged = guard(q1216, q3467, ext.get(sc.Q1216) == "pass",
                                     ext.get(sc.Q3467) == "pass")
    r = ratios(q1216, q3467)
    cons = guard_consequences(status, ext)
    result = {"status": status, "medians": medians,
              "n": {y: len(r[y]) for y in YEARS}, "flagged": flagged,
              "consequences": cons, "unmapped": u1 + u2,
              "rows": guard_rows(q1216, q3467),
              "extraction": {sc.Q1216: ext.get(sc.Q1216), sc.Q3467: ext.get(sc.Q3467)}}
    return result


def write_guard(result: dict) -> None:
    fields = ["year", "unit", "q1216_notified", "q3467_notified", "ratio", "in_guard",
              "outside_0_95_1_05", "q2_discrepancy", "label", "note"]
    with open(EX / "guard_ratios.csv", "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(result["rows"])
    cons = result["consequences"]
    summary = [
        {"item": "status", "value": result["status"]},
        {"item": "median ratio 2023", "value": f"{result['medians'][2023]:.6f}"},
        {"item": "median ratio 2024", "value": f"{result['medians'][2024]:.6f}"},
        {"item": "n States 2023", "value": result["n"][2023]},
        {"item": "n States 2024", "value": result["n"][2024]},
        {"item": "States outside [0.95, 1.05] in 2023",
         "value": sum(1 for x in result["flagged"] if x["year"] == 2023)},
        {"item": "States outside [0.95, 1.05] in 2024",
         "value": sum(1 for x in result["flagged"] if x["year"] == 2024)},
        {"item": "2024 rows labelled late-report-consistent",
         "value": sum(1 for x in result["flagged"] if x["label"] == LATE)},
        {"item": "extraction checks", "value": "; ".join(
            f"{k}: {v}" for k, v in result["extraction"].items())},
        {"item": "primary contrast", "value": cons["primary"]},
        {"item": "full-year contrast role", "value": cons["full_year_role"]},
        {"item": "trend sources", "value": "; ".join(
            f"{y}: {t['source']} ({t['status']})"
            for y, t in sorted(cons["trend"].items()))},
        {"item": "labels not computable", "value": "; ".join(result["unmapped"])
         or "none"},
    ]
    with open(EX / "guard_result.csv", "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["item", "value"], lineterminator="\n")
        w.writeheader()
        w.writerows(summary)


# ================================================================== Q4 constants

SEED = 20261118
DRAWS = 10_000
Z975 = statistics.NormalDist().inv_cdf(0.975)
EXCLUDED_YEARS = (2020, 2021)                 # COVID-19 disruption (§9.6)
TREND_YEARS = (2019, 2022, 2023, 2024)        # primary trend (§9.6)
S3_YEARS = (2022, 2023, 2024)                 # S3: recent trend only (§10.5)
S4_YEARS = (2019, 2022, 2023)                 # S4: three-point trend (§10.5)
S8A_FACTORS = (0.98, 0.95)                    # S8(a) (§10.5)
SINGULAR_TOL = 1e-12                          # S8(b) singular-matrix rule (§10.5)
INVARIANCE_TOL = 1e-9                         # S8(a) γ1 invariance check

FULL_YEAR = "full-year 2025 vs 2024"
JAN_OCT = "January-October 2025 vs 2024"
PLACEBO_CONTRAST = "placebo 2023 vs 2022"
PRIMARY = "primary"
PLACEBO = "placebo"

POSITIVE, NEGATIVE, NO_CLEAR = ("positive association", "negative association",
                                "no clear association")
PLACEBO_DIFFERS = ("model interval excludes 0: the more exposed States already differed "
                   "in notification trend before the campaign (§10.8)")
PLACEBO_NO_DIFF = "model interval includes 0 (§10.8)"
NOT_SEPARABLE = ("not separable from the pre-campaign difference in trend shown by the "
                 "placebo (§10.8)")

# Union territories on 7 December 2024, coarsened (§9.4; S5).
UNION_TERRITORIES = tuple(sorted({st.coarsen(n) for n in (
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry")}))

EXPOSURE_FILES = {"R": "exposure_share.csv", "D": "exposure_share_reconstructed.csv"}
DENOMINATOR_LABEL = {
    "R": "registered: LGD count under §9.3 as written",
    "D": ("deviation: LGD count reconstructed from official notices (§13, 19 November "
          "2026); the main Q4 analysis, labelled a deviation"),
}

# (source, year) -> (extracted file, column) for the annual State counts (§9.6, §10.6).
ANNUAL = {
    (sc.ITR2020, 2019): ("itr2020_a1_2.csv", "notified_total"),
    (sc.ITR2023, 2022): ("itr2023_a1_2.csv", "notified_total"),
    (sc.ITR2024, 2023): ("itr2024_a1_2.csv", "notified_total"),
    (sc.Q1216, 2023): ("pq_q1216.csv", "2023_notified"),
    (sc.Q1216, 2024): ("pq_q1216.csv", "2024_notified"),
    (sc.Q3467, 2024): ("pq_q3467.csv", "2024_notified"),
    (sc.LS261, 2023): ("pq_q261.csv", "2023_reported"),
}

S7_REASON = ("not run: the named list of campaign districts (Kerala copy of the Ministry "
             "letter) does not match the CTD table in every State (Delhi 26 vs 11, "
             "Maharashtra 52 vs 30, Tamil Nadu 26 vs 22, West Bengal 28 vs 19; "
             "data/extracted/named_list_check.csv; data/source_choices.csv NAM-01, NAM-02), "
             "so S7 is not run (§9.2 Named list; §10.5 S7)")


# ================================================================== t distribution

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 100_000):
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
        if abs(delta - 1.0) < 1e-16:
            return h
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log1p(-x))
    bt = math.exp(lbt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """Distribution function of Student's t with df degrees of freedom."""
    tail = 0.5 * _betai(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t > 0 else tail


def t_quantile(p: float, df: float) -> float:
    """The p quantile of Student's t, by bisection on t_cdf (numerical inversion, §10.2)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie in (0, 1)")
    if p < 0.5:
        return -t_quantile(1.0 - p, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < p:
        lo, hi = hi, hi * 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if mid in (lo, hi):
            break
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ================================================================== outcome, trend, excess

def trend_beta(points: dict[int, int | None], years=TREND_YEARS
               ) -> tuple[float | None, tuple[int, ...], str]:
    """(β, years used, reason): the OLS slope of ln N on calendar year over the State's
    available points among `years` (§9.6, Fit). 2020 and 2021 are never trend points.
    A State with no 2019 value uses the points from 2022 onward; at least two points are
    needed; a zero count in a point in use makes the State not computable."""
    bad = [t for t in years if t in EXCLUDED_YEARS]
    if bad:
        raise ValueError(f"{bad} are not trend points (§9.6: 2020 and 2021 excluded)")
    pts = [(t, points[t]) for t in sorted(years) if points.get(t) is not None]
    used = tuple(t for t, _ in pts)
    if any(v == 0 for _, v in pts):
        return None, used, "zero count in a trend point (§9.6)"
    if len(pts) < 2:
        return None, used, "fewer than two trend points (§9.6, §10.4)"
    ts = [t for t, _ in pts]
    ls = [math.log(v) for _, v in pts]
    tb, lb = statistics.fmean(ts), statistics.fmean(ls)
    beta = (sum((t - tb) * (v - lb) for t, v in zip(ts, ls))
            / sum((t - tb) ** 2 for t in ts))
    return beta, used, ""


def _poisson(a: int, b: int) -> tuple[float, float, float, float]:
    """(y, lower, upper, w): y = ln(b/a), its Poisson 95% interval (§10.7) and weight."""
    y = math.log(b / a)
    h = Z975 * math.sqrt(1.0 / a + 1.0 / b)
    return y, y - h, y + h, 1.0 / (1.0 / a + 1.0 / b)


def evaluate(a: int | None, b: int | None, trend: dict[int, int | None],
             years=TREND_YEARS) -> dict:
    """Outcome y = ln(b/a), its Poisson interval and weight, the trend β and the excess
    x = y - β for one State (§10.1), or the reasons it is not computable (§10.4)."""
    reasons = []
    y = lo = hi = w = None
    if a is None or b is None:
        reasons.append("missing from an outcome column (§10.4)")
    elif a == 0 or b == 0:
        reasons.append("zero count in a window (§10.4)")
    else:
        y, lo, hi, w = _poisson(a, b)
    beta, used, why = trend_beta(trend, years)
    if why:
        reasons.append(why)
    x = y - beta if (y is not None and beta is not None) else None
    return {"a": a, "b": b, "y": y, "y_lo": lo, "y_hi": hi, "w": w, "beta": beta,
            "used": used, "x": x, "reason": "; ".join(reasons)}


def excess(state: dict) -> float | None:
    """x_s = ln(b/a) - β_s for a State {"a", "b", "trend": {year: count}, ["years"]};
    None if it is not computable (§10.4)."""
    return evaluate(state.get("a"), state.get("b"), state.get("trend", {}),
                    state.get("years", TREND_YEARS))["x"]


def placebo_evaluate(n2019: int | None, n2022: int | None, n2023: int | None) -> dict:
    """Placebo (§10.6): y^P = ln(N2023/N2022), β^P = ln(N2022/N2019)/3, x^P = y^P - β^P,
    w = 1/(1/N2022 + 1/N2023). A State with no 2019 value is not computable."""
    reasons = []
    y = lo = hi = w = beta = None
    if n2022 is None or n2023 is None:
        reasons.append("missing a 2022 or 2023 count (§10.6)")
    elif n2022 == 0 or n2023 == 0:
        reasons.append("zero count in a window (§10.4)")
    else:
        y, lo, hi, w = _poisson(n2022, n2023)
    if n2019 is None:
        reasons.append("no 2019 value: not computable for the placebo (§10.6)")
    elif n2019 == 0:
        reasons.append("zero count in the 2019 point (§10.6)")
    elif n2022:
        beta = math.log(n2022 / n2019) / 3.0
    x = y - beta if (y is not None and beta is not None) else None
    return {"a": n2022, "b": n2023, "y": y, "y_lo": lo, "y_hi": hi, "w": w,
            "beta": beta, "used": (2019, 2022) if beta is not None else (),
            "x": x, "reason": "; ".join(reasons)}


def placebo_sources(fallback: bool) -> dict[int, str]:
    """Sources of the placebo counts: 2023 from Q1216, or the India TB Report 2024 if
    the trend falls back (§10.6)."""
    return {2019: sc.ITR2020, 2022: sc.ITR2023, 2023: sc.ITR2024 if fallback else sc.Q1216}


def scale_records(recs: list[dict], factor: float) -> list[dict]:
    """S8(a): the January-October 2025 counts multiplied by `factor`, weights held at
    their unscaled values (§10.5)."""
    out = []
    for r in recs:
        if r.get("a") and r.get("b"):
            y = math.log(factor * r["b"] / r["a"])
        else:
            y = r["y"] + math.log(factor)
        out.append({**r, "y": y, "x": y - r["beta"], "w": r["w"]})
    return out


# ================================================================== WLS

def _slope(E, x, w) -> float | None:
    """WLS slope, or None if the exposures are all equal."""
    W = sum(w)
    eb = sum(wi * e for wi, e in zip(w, E)) / W
    xb = sum(wi * v for wi, v in zip(w, x)) / W
    sxx = sum(wi * (e - eb) ** 2 for wi, e in zip(w, E))
    if len(set(E)) < 2 or sxx <= 0:
        return None
    return sum(wi * (e - eb) * (v - xb) for wi, e, v in zip(w, E, x)) / sxx


def wls_fit(E, x, w) -> dict | None:
    """WLS of x on E with weights w (§10.2). None if the minimum is not met (fewer than 3
    States or fewer than 2 distinct exposures). s² = Σ w r²/(n-2);
    SE(γ1) = √(s²/Σ w (E - Ē_w)²); 95% interval γ1 ± t(0.975, n-2) SE(γ1).
    γ0's interval uses SE(γ0) = √(s² (1/Σw + Ē_w²/Σ w (E - Ē_w)²))."""
    n = len(E)
    if n < 3 or len(set(E)) < 2:
        return None
    W = sum(w)
    eb = sum(wi * e for wi, e in zip(w, E)) / W
    xb = sum(wi * v for wi, v in zip(w, x)) / W
    sxx = sum(wi * (e - eb) ** 2 for wi, e in zip(w, E))
    g1 = sum(wi * (e - eb) * (v - xb) for wi, e, v in zip(w, E, x)) / sxx
    g0 = xb - g1 * eb
    s2 = sum(wi * (v - g0 - g1 * e) ** 2 for wi, e, v in zip(w, E, x)) / (n - 2)
    se = math.sqrt(s2 / sxx)
    se0 = math.sqrt(s2 * (1.0 / W + eb * eb / sxx))
    t = t_quantile(0.975, n - 2)
    return {"gamma0": g0, "gamma1": g1, "se": se, "se0": se0, "s2": s2, "n": n,
            "df": n - 2, "t": t, "lo": g1 - t * se, "hi": g1 + t * se,
            "lo0": g0 - t * se0, "hi0": g0 + t * se0}


def wls(x, y, w) -> tuple[float, float, int]:
    """(slope, se, n) of the WLS of y on x (here: excess change on exposure share)."""
    fit = wls_fit(x, y, w)
    if fit is None:
        raise ValueError("WLS minimum not met: at least 3 States and 2 distinct exposures")
    return fit["gamma1"], fit["se"], fit["n"]


def _det(A) -> float:
    M = [list(map(float, row)) for row in A]
    k, det = len(M), 1.0
    for i in range(k):
        p = max(range(i, k), key=lambda r: abs(M[r][i]))
        if M[p][i] == 0.0:
            return 0.0
        if p != i:
            M[i], M[p] = M[p], M[i]
            det = -det
        det *= M[i][i]
        for r in range(i + 1, k):
            f = M[r][i] / M[i][i]
            for c in range(i, k):
                M[r][c] -= f * M[i][c]
    return det


def singular(A) -> bool:
    """§10.5 S8(b): XᵀWX is singular if its determinant is at most 1e-12 times the
    product of its diagonal entries."""
    return _det(A) <= SINGULAR_TOL * math.prod(A[i][i] for i in range(len(A)))


def _inverse(A):
    k = len(A)
    M = [list(map(float, row)) + [1.0 if i == j else 0.0 for j in range(k)]
         for i, row in enumerate(A)]
    for i in range(k):
        p = max(range(i, k), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        piv = M[i][i]
        M[i] = [v / piv for v in M[i]]
        for r in range(k):
            if r != i:
                f = M[r][i]
                M[r] = [a - f * b for a, b in zip(M[r], M[i])]
    return [row[k:] for row in M]


def _normal_eq(X, y, w):
    k = len(X[0])
    A = [[sum(wi * xr[i] * xr[j] for wi, xr in zip(w, X)) for j in range(k)]
         for i in range(k)]
    c = [sum(wi * xr[i] * yi for wi, xr, yi in zip(w, X, y)) for i in range(k)]
    return A, c


def wls_matrix(X, y, w) -> dict | None:
    """WLS with design matrix X (rows), for S8(b) (§10.5): coefficients (XᵀWX)⁻¹XᵀWy,
    covariance s² (XᵀWX)⁻¹ with s² = Σ w r²/(n - k), t with n - k degrees of freedom.
    None if XᵀWX is singular (rule of `singular`) or n - k < 1."""
    n, k = len(X), len(X[0])
    if n - k < 1:
        return None
    A, c = _normal_eq(X, y, w)
    if singular(A):
        return None
    Ai = _inverse(A)
    coef = [sum(Ai[i][j] * c[j] for j in range(k)) for i in range(k)]
    res = [yi - sum(b * v for b, v in zip(coef, xr)) for xr, yi in zip(X, y)]
    s2 = sum(wi * r * r for wi, r in zip(w, res)) / (n - k)
    se = [math.sqrt(s2 * Ai[i][i]) for i in range(k)]
    t = t_quantile(0.975, n - k)
    return {"coef": coef, "se": se, "s2": s2, "n": n, "df": n - k, "t": t,
            "lo": [b - t * s for b, s in zip(coef, se)],
            "hi": [b + t * s for b, s in zip(coef, se)]}


def _matrix_gamma1(X, y, w) -> float | None:
    A, c = _normal_eq(X, y, w)
    if singular(A):
        return None
    Ai = _inverse(A)
    return sum(Ai[1][j] * c[j] for j in range(len(c)))


# ================================================================== bootstrap

def bootstrap_ci(records: list[dict], *, draws: int = DRAWS, seed: int = SEED,
                 covariate: str | None = None) -> dict:
    """Percentile bootstrap of γ1 (§10.3). States are sorted by name (`unit`); the
    generator is random.Random(seed), new for each call (reset before each analysis);
    each draw is rng.choices(range(n), k=n) and carries each State's x, E and w (and the
    covariate, for S8(b)). Degenerate draws (all exposures equal; with a covariate, a
    singular XᵀWX) are counted and excluded. The interval is the first and last cut of
    statistics.quantiles(valid, n=40, method="inclusive")."""
    recs = sorted(records, key=lambda r: r["unit"])
    n = len(recs)
    E = [r["E"] for r in recs]
    x = [r["x"] for r in recs]
    w = [r["w"] for r in recs]
    L = [r[covariate] for r in recs] if covariate else None
    rng = random.Random(seed)
    vals, degenerate = [], 0
    for _ in range(draws):
        idx = rng.choices(range(n), k=n)
        Ed = [E[i] for i in idx]
        xd = [x[i] for i in idx]
        wd = [w[i] for i in idx]
        if covariate:
            g = _matrix_gamma1([[1.0, E[i], L[i]] for i in idx], xd, wd)
        else:
            g = _slope(Ed, xd, wd)
        if g is None:
            degenerate += 1
        else:
            vals.append(g)
    if len(vals) < 2:
        return {"lo": None, "hi": None, "valid": len(vals), "degenerate": degenerate}
    cuts = statistics.quantiles(vals, n=40, method="inclusive")
    return {"lo": cuts[0], "hi": cuts[-1], "valid": len(vals), "degenerate": degenerate}


# ================================================================== interpretation

def interpret(model_ci, boot_ci) -> str:
    """§10.8: positive only if both intervals lie wholly above 0; negative only if both
    lie wholly below 0; otherwise no clear association."""
    if model_ci and boot_ci and None not in (*model_ci, *boot_ci):
        if model_ci[0] > 0 and boot_ci[0] > 0:
            return POSITIVE
        if model_ci[1] < 0 and boot_ci[1] < 0:
            return NEGATIVE
    return NO_CLEAR


def placebo_interpret(model_ci) -> str:
    """§10.8: a placebo model interval that excludes 0 means the more exposed States
    already differed in trend before the campaign."""
    return PLACEBO_DIFFERS if (model_ci[0] > 0 or model_ci[1] < 0) else PLACEBO_NO_DIFF


def gamma1_invariant(base: dict, scaled: dict) -> bool:
    """S8(a): a uniform factor moves γ0 only; γ1 must be unchanged (§10.5)."""
    return abs(base["gamma1"] - scaled["gamma1"]) <= INVARIANCE_TOL


# ================================================================== model runners

def _exposure_stats(E, w) -> dict:
    if not E:
        return {}
    return {"exposure_sd": statistics.stdev(E) if len(E) > 1 else None,
            "exposure_min": min(E), "exposure_max": max(E),
            "exposure_mean_weighted": sum(a * b for a, b in zip(w, E)) / sum(w),
            "exposure_mean_unweighted": statistics.fmean(E)}


def run_model(recs: list[dict], *, weighted: bool = True, draws: int = DRAWS,
              placebo: bool = False) -> dict:
    """The §10.2 model and §10.3 bootstrap on computable records {unit, E, x, w}; the
    descriptive fallback (§10.7) if the minimum is not met."""
    recs = sorted(recs, key=lambda r: r["unit"])
    if not weighted:
        recs = [{**r, "w": 1.0} for r in recs]
    E = [r["E"] for r in recs]
    x = [r["x"] for r in recs]
    w = [r["w"] for r in recs]
    out = {"n": len(recs), "gamma1": None, **_exposure_stats(E, w)}
    fit = wls_fit(E, x, w)
    if fit is None:
        why = ("fewer than 3 States" if len(recs) < 3
               else "fewer than 2 distinct exposure values")
        out["status"] = f"descriptive only (§10.7): {why} (§10.2 minimum)"
        out["label"] = "descriptive only (§10.7)"
        return out
    boot = bootstrap_ci(recs, draws=draws)
    out.update(fit=fit, boot=boot, gamma0=fit["gamma0"], gamma1=fit["gamma1"],
               status="fitted")
    out["label"] = (placebo_interpret((fit["lo"], fit["hi"])) if placebo else
                    interpret((fit["lo"], fit["hi"]), (boot["lo"], boot["hi"])))
    return out


def s8b_fit(recs: list[dict]) -> dict:
    """S8(b): x = γ0 + γ1 E + γ2 ln r with the S8 weights (§10.5)."""
    recs = sorted(recs, key=lambda r: r["unit"])
    out = {"n": len(recs), "gamma1": None}
    if len({r["lnr"] for r in recs}) <= 1:
        out["status"] = ("not computable: r_s is equal in every State, so ln r is "
                         "collinear with the intercept (§10.5 S8(b))")
        return out
    m = wls_matrix([[1.0, r["E"], r["lnr"]] for r in recs], [r["x"] for r in recs],
                   [r["w"] for r in recs])
    if m is None:
        out["status"] = ("not computable: XᵀWX singular or fewer than 4 States "
                         "(§10.5 S8(b))")
        return out
    out.update(status="fitted", matrix=m, gamma0=m["coef"][0], gamma1=m["coef"][1])
    return out


def run_s8b(recs: list[dict], *, draws: int = DRAWS) -> dict:
    out = s8b_fit(recs)
    out.update(_exposure_stats([r["E"] for r in recs], [r["w"] for r in recs]))
    if out["status"] != "fitted":
        out["label"] = out["status"]
        return out
    m = out["matrix"]
    boot = bootstrap_ci(recs, draws=draws, covariate="lnr")
    out["boot"] = boot
    out["label"] = interpret((m["lo"][1], m["hi"][1]), (boot["lo"], boot["hi"]))
    return out


# ================================================================== data assembly

def annual(source: str, year: int) -> tuple[dict[str, int], list[str]]:
    """Coarsened State counts (members summed, §9.4) of one annual column; State rows
    only (national total rows are skipped); unmapped labels are listed."""
    name, column = ANNUAL[(source, year)]
    out, unmapped = {}, []
    for r in _read(name):
        if r["column"] != column or str(r.get("is_total", "no")) == "yes":
            continue
        if not str(r["value"]).strip():
            continue
        if not r["coarse_unit"]:
            unmapped.append(r["label_printed"])
            continue
        u = r["coarse_unit"]
        out[u] = out.get(u, 0) + cp._int(r["value"])
    return out, unmapped


def load_trend(fallback: bool, ext: dict[str, str]) -> dict[int, dict]:
    """year -> {"source", "status", "counts"}; a trend source that failed its extraction
    checks leaves the year missing for every State (counts None) (§9.6)."""
    out = {}
    for year, t in sc.trend_points(ext, fallback=fallback).items():
        counts = annual(t["source"], year)[0] if t["status"] == "in use" else None
        out[year] = {"source": t["source"], "status": t["status"], "counts": counts}
    return out


def exposure_share(campaign_count: int, lgd_count: int) -> float:
    """E = min(1, c/L) (§9.3), computed exactly from the counts (combined units hold
    the summed c and L, §9.4), not from the rounded share printed in the file."""
    return min(1.0, campaign_count / lgd_count)


def load_exposure(dset: str) -> dict[str, dict]:
    out = {}
    for r in _read(EXPOSURE_FILES[dset]):
        ok = r["computable"] == "yes"
        E = (exposure_share(int(r["campaign_count"]), int(r["lgd_count"])) if ok
             else None)
        out[r["unit"]] = {"E": E, "computable": ok,
                          "capped": r["capped"] == "yes",
                          "flagged": r["flagged_e5"] == "yes",
                          "campaign_count": r["campaign_count"],
                          "lgd_count": r["lgd_count"], "reason": r["reason"]}
    return out


def _attach_exposure(rec: dict, unit: str, exposure: dict) -> dict:
    ex = exposure.get(unit)
    reasons = [rec["reason"]] if rec["reason"] else []
    if ex is None:
        reasons.append("exposure not computable: unit absent from the exposure table")
        E = None
    elif not ex["computable"]:
        reasons.append(f"exposure not computable: {ex['reason']}")
        E = None
    else:
        E = ex["E"]
    return {**rec, "unit": unit, "E": E,
            "capped": bool(ex and ex["capped"]), "flagged": bool(ex and ex["flagged"]),
            "reason": "; ".join(reasons), "computable": not reasons}


def contrast_records(pairs: dict, dropped: list, trend: dict[int, dict], years,
                     exposure: dict, units) -> list[dict]:
    """One record per unit: the outcome pair, trend, excess, weight and exposure."""
    why_dropped = dict(dropped)
    out = []
    for u in sorted(units):
        a, b = pairs.get(u, (None, None))
        pts = {y: (trend[y]["counts"] or {}).get(u) for y in trend}
        rec = evaluate(a, b, pts, years)
        if u in why_dropped:
            rec["reason"] = "; ".join(filter(None, [
                f"{why_dropped[u]} (§10.4)", rec["reason"].replace(
                    "missing from an outcome column (§10.4)", "").strip("; ")]))
        rec["points"] = pts
        out.append(_attach_exposure(rec, u, exposure))
    return out


def placebo_records(counts: dict[int, dict], exposure: dict, units) -> list[dict]:
    out = []
    for u in sorted(units):
        n19, n22, n23 = ((counts[y] or {}).get(u) for y in (2019, 2022, 2023))
        rec = placebo_evaluate(n19, n22, n23)
        rec["points"] = {2019: n19, 2022: n22, 2023: n23}
        out.append(_attach_exposure(rec, u, exposure))
    return out


# ================================================================== output rows

def _f(v, nd: int = 6) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    return f"{v:.{nd}f}"


SUMMARY_FIELDS = [
    "analysis", "denominator_set", "denominator", "contrast", "trend_points", "weights",
    "status", "n", "units_excluded_by_rule", "gamma0", "gamma0_model_lo",
    "gamma0_model_hi", "gamma1", "se_gamma1", "t_df", "t_0975", "gamma1_model_lo",
    "gamma1_model_hi", "gamma1_boot_lo", "gamma1_boot_hi", "boot_draws_valid",
    "boot_draws_degenerate", "exp_gamma1", "exp_gamma1_model_lo", "exp_gamma1_model_hi",
    "exp_0_1_gamma1", "exp_0_1_gamma1_model_lo", "exp_0_1_gamma1_model_hi",
    "gamma2_ln_r", "gamma2_model_lo", "gamma2_model_hi", "gamma1_invariant",
    "loo_gamma1_min", "loo_gamma1_max", "loo_most_influential_unit",
    "loo_most_influential_gamma1", "exposure_sd", "exposure_min", "exposure_max",
    "exposure_mean_weighted", "exposure_mean_unweighted", "label", "label_note", "note"]

STATE_FIELDS = [
    "denominator_set", "contrast", "unit", "a", "b", "y", "y_poisson_lo", "y_poisson_hi",
    "trend_points_used", "n2019", "n2022", "n2023", "n2024", "beta", "x", "E", "w",
    "capped", "flagged_e5", "union_territory", "q261_2023", "itr2024_2023", "ln_r",
    "computable", "reason"]

LOO_FIELDS = ["denominator_set", "omitted_unit", "n", "gamma1", "change_from_full",
              "status"]


def _summary(analysis: str, dset: str, contrast: str, trend: str, weights: str,
             res: dict | None = None, **extra) -> dict:
    row = {k: "" for k in SUMMARY_FIELDS}
    row.update(analysis=analysis, denominator_set=dset,
               denominator=DENOMINATOR_LABEL[dset], contrast=contrast,
               trend_points=trend, weights=weights)
    res = res or {}
    row["status"] = res.get("status", "")
    row["n"] = res.get("n", "")
    for k in ("exposure_sd", "exposure_min", "exposure_max", "exposure_mean_weighted",
              "exposure_mean_unweighted"):
        row[k] = _f(res.get(k))
    row["label"] = res.get("label", "")
    fit, mat, boot = res.get("fit"), res.get("matrix"), res.get("boot")
    if fit:
        g1, lo, hi = fit["gamma1"], fit["lo"], fit["hi"]
        row.update(gamma0=_f(fit["gamma0"]), gamma0_model_lo=_f(fit["lo0"]),
                   gamma0_model_hi=_f(fit["hi0"]), se_gamma1=_f(fit["se"]),
                   t_df=fit["df"], t_0975=_f(fit["t"]))
    elif mat:
        g1, lo, hi = mat["coef"][1], mat["lo"][1], mat["hi"][1]
        row.update(gamma0=_f(mat["coef"][0]), gamma0_model_lo=_f(mat["lo"][0]),
                   gamma0_model_hi=_f(mat["hi"][0]), se_gamma1=_f(mat["se"][1]),
                   t_df=mat["df"], t_0975=_f(mat["t"]),
                   gamma2_ln_r=_f(mat["coef"][2]), gamma2_model_lo=_f(mat["lo"][2]),
                   gamma2_model_hi=_f(mat["hi"][2]))
    if fit or mat:
        row.update(gamma1=_f(g1), gamma1_model_lo=_f(lo), gamma1_model_hi=_f(hi),
                   exp_gamma1=_f(math.exp(g1)), exp_gamma1_model_lo=_f(math.exp(lo)),
                   exp_gamma1_model_hi=_f(math.exp(hi)),
                   exp_0_1_gamma1=_f(math.exp(0.1 * g1)),
                   exp_0_1_gamma1_model_lo=_f(math.exp(0.1 * lo)),
                   exp_0_1_gamma1_model_hi=_f(math.exp(0.1 * hi)))
    if boot:
        row.update(gamma1_boot_lo=_f(boot["lo"]), gamma1_boot_hi=_f(boot["hi"]),
                   boot_draws_valid=boot["valid"], boot_draws_degenerate=boot["degenerate"])
    row.update(extra)
    return row


def _state_rows(dset: str, contrast: str, recs: list[dict], lnr: dict | None = None,
                placebo: bool = False) -> list[dict]:
    rows = []
    for r in recs:
        pts = r["points"]
        if placebo:
            used = "2019, 2022 (two-point placebo benchmark, §10.6)" if r["used"] else ""
        else:
            used = ", ".join(map(str, r["used"]))
        row = {"denominator_set": dset, "contrast": contrast, "unit": r["unit"],
               "a": _f(r["a"]), "b": _f(r["b"]), "y": _f(r["y"]),
               "y_poisson_lo": _f(r["y_lo"]), "y_poisson_hi": _f(r["y_hi"]),
               "trend_points_used": used,
               "n2019": _f(pts.get(2019)), "n2022": _f(pts.get(2022)),
               "n2023": _f(pts.get(2023)), "n2024": _f(pts.get(2024)),
               "beta": _f(r["beta"]), "x": _f(r["x"]), "E": _f(r["E"]), "w": _f(r["w"]),
               "capped": _f(r["capped"]), "flagged_e5": _f(r["flagged"]),
               "union_territory": _f(r["unit"] in UNION_TERRITORIES),
               "q261_2023": "", "itr2024_2023": "", "ln_r": "",
               "computable": _f(r["computable"]), "reason": r["reason"]}
        if lnr is not None:
            q, i, v = lnr.get(r["unit"], (None, None, None))
            row.update(q261_2023=_f(q), itr2024_2023=_f(i), ln_r=_f(v))
        rows.append(row)
    return rows


def _lnr_inputs() -> dict[str, tuple]:
    """unit -> (LS Q261 2023, ITR2024 2023, ln r or None) for S8(b) (§10.5)."""
    q261, _ = annual(sc.LS261, 2023)
    itr, _ = annual(sc.ITR2024, 2023)
    out = {}
    for u in sorted(q261.keys() | itr.keys()):
        q, i = q261.get(u), itr.get(u)
        out[u] = (q, i, math.log(q / i) if (q and i) else None)
    return out


def _loo(dset: str, recs: list[dict], weighted: bool = True) -> tuple[list[dict], dict]:
    """S2: γ1 refitted with each State left out; no bootstrap (§10.5)."""
    full = wls_fit([r["E"] for r in recs], [r["x"] for r in recs], [r["w"] for r in recs])
    rows, vals = [], []
    for r in sorted(recs, key=lambda r: r["unit"]):
        rest = [q for q in recs if q["unit"] != r["unit"]]
        fit = wls_fit([q["E"] for q in rest], [q["x"] for q in rest],
                      [q["w"] for q in rest])
        g = fit["gamma1"] if fit else None
        ch = g - full["gamma1"] if (g is not None and full) else None
        rows.append({"denominator_set": dset, "omitted_unit": r["unit"], "n": len(rest),
                     "gamma1": _f(g), "change_from_full": _f(ch),
                     "status": "fitted" if fit else
                     "descriptive only (§10.7): §10.2 minimum not met"})
        if g is not None:
            vals.append((r["unit"], g, ch))
    stats = {}
    if vals:
        top = max(vals, key=lambda v: abs(v[2]))
        stats = {"loo_gamma1_min": _f(min(v[1] for v in vals)),
                 "loo_gamma1_max": _f(max(v[1] for v in vals)),
                 "loo_most_influential_unit": top[0],
                 "loo_most_influential_gamma1": _f(top[1])}
    return rows, stats


# ================================================================== Q4 run

def run_q4(draws: int = DRAWS) -> dict:
    """Every Q4 analysis under both denominators, in the order of the plan."""
    g = run_guard()
    status = g["status"]
    fallback = status == "fail"
    ext = _extraction()
    trend = load_trend(fallback, ext)
    contrasts = sc.contrast_status(ext)
    fy = (cp.full_year_pairs(cp.load_pq("pq_q1216"))
          if contrasts["full-year 2025 vs 2024"] == "computable" else ({}, []))
    jo = (cp.jan_oct_pairs(cp.load_pq("pq_q261") + cp.load_pq("pq_q1093"))
          if contrasts["January-October 2025 vs 2024 (S8)"] == "computable" else ({}, []))
    primary_c = JAN_OCT if fallback else FULL_YEAR
    pairs = {FULL_YEAR: fy, JAN_OCT: jo}
    psrc = placebo_sources(fallback)
    pcounts = {y: (annual(s, y)[0] if ext.get(s) == "pass" else None)
               for y, s in psrc.items()}
    lnr = _lnr_inputs()
    trend_desc = {TREND_YEARS: "2019, 2022, 2023, 2024", S3_YEARS: "2022, 2023, 2024",
                  S4_YEARS: "2019, 2022, 2023"}
    src_desc = "; ".join(f"{y}: {t['source']} ({t['status']})" for y, t in trend.items())

    summary, states_out, loo_out = [], [], []
    for dset in ("R", "D"):
        exposure = load_exposure(dset)
        units = set(exposure)
        for p, d in pairs.values():
            units |= set(p) | {u for u, _ in d}

        def recs_for(contrast, years):
            p, d = pairs[contrast]
            return contrast_records(p, d, trend, years, exposure, units)

        def ok(recs):
            return [r for r in recs if r["computable"]]

        prim_all = recs_for(primary_c, TREND_YEARS)
        jo_all = recs_for(JAN_OCT, TREND_YEARS)
        fy_all = recs_for(FULL_YEAR, TREND_YEARS)
        pl_all = placebo_records(pcounts, exposure, units)
        prim = ok(prim_all)
        p_tr = trend_desc[TREND_YEARS]
        wdesc = "w = 1/(1/a + 1/b)"

        # primary
        res = run_model(prim, draws=draws)
        summary.append(_summary(PRIMARY, dset, primary_c, p_tr, wdesc, res,
                                note=f"trend sources: {src_desc}"))
        # S1-S7
        summary.append(_summary("S1 unweighted", dset, primary_c, p_tr, "w = 1",
                                run_model(prim, weighted=False, draws=draws)))
        rows, stats = _loo(dset, prim)
        loo_out += rows
        summary.append(_summary(
            "S2 leave one out", dset, primary_c, p_tr, wdesc,
            {"status": f"{len(rows)} refits, each on n - 1 States; no bootstrap (§10.5)",
             "n": len(prim) - 1, "label": "not applicable (no bootstrap, §10.5 S2)",
             # spread of exposure of the full sample the omissions are taken from (§10.2)
             **_exposure_stats([r["E"] for r in prim], [r["w"] for r in prim])},
            note="per-omission γ1 in outputs/q4_s2_leave_one_out.csv", **stats))
        for name, yrs in (("S3 trend 2022-2024", S3_YEARS),
                          ("S4 trend 2019, 2022, 2023", S4_YEARS)):
            summary.append(_summary(name, dset, primary_c, trend_desc[yrs], wdesc,
                                    run_model(ok(recs_for(primary_c, yrs)), draws=draws)))
        ut = [r for r in prim if r["unit"] in UNION_TERRITORIES]
        summary.append(_summary(
            "S5 States only", dset, primary_c, p_tr, wdesc,
            run_model([r for r in prim if r["unit"] not in UNION_TERRITORIES], draws=draws),
            units_excluded_by_rule="; ".join(r["unit"] for r in ut)))
        flagged = [r for r in prim if r["flagged"]]
        if flagged:
            summary.append(_summary(
                "S6a flagged excluded", dset, primary_c, p_tr, wdesc,
                run_model([r for r in prim if not r["flagged"]], draws=draws),
                units_excluded_by_rule="; ".join(r["unit"] for r in flagged)))
        else:
            summary.append(_summary(
                "S6a flagged excluded", dset, primary_c, p_tr, wdesc,
                {"status": "empty: no State is flagged under E5 (§9.2), so the exclusion "
                           "set is empty (§10.5 S6a)"}))
        capped = [r for r in prim if r["capped"]]
        summary.append(_summary(
            "S6b capped excluded", dset, primary_c, p_tr, wdesc,
            run_model([r for r in prim if not r["capped"]], draws=draws),
            units_excluded_by_rule="; ".join(r["unit"] for r in capped)))
        summary.append(_summary("S7 population share", dset, primary_c, "", "",
                                {"status": S7_REASON}))
        # S8 and its lag analyses
        if primary_c == FULL_YEAR:
            s8 = ok(jo_all)
            s8_res = run_model(s8, draws=draws)
            summary.append(_summary("S8 January-October", dset, JAN_OCT, p_tr, wdesc,
                                    s8_res))
        else:
            s8 = prim
            s8_res = res
            summary.append(_summary(
                "S8 full-year (descriptive)", dset, FULL_YEAR, p_tr, wdesc,
                {"status": "descriptive only (§10.7): the guard failed, so the full-year "
                           "contrast is reported descriptively (outputs/q4_states.csv)",
                 "n": len(ok(fy_all))}))
        base = s8_res.get("fit")
        for f in S8A_FACTORS:
            scaled = scale_records(s8, f)
            r8 = run_model(scaled, draws=draws)
            inv = (gamma1_invariant(base, r8["fit"]) if (base and r8.get("fit"))
                   else None)
            if inv is False:
                raise AssertionError("S8(a): γ1 changed under a uniform factor")
            summary.append(_summary(
                f"S8(a) x{f:.2f}", dset, JAN_OCT, p_tr,
                "w = 1/(1/a + 1/b) from the unscaled counts", r8,
                gamma1_invariant=_f(inv) if inv is not None else "",
                note=f"January-October 2025 counts x {f:.2f}; γ0 moves by ln {f:.2f}"))
        s8b = []
        s8b_out = []
        for r in s8:
            v = lnr.get(r["unit"], (None, None, None))[2]
            if v is None:
                s8b_out.append(r["unit"])
            else:
                s8b.append({**r, "lnr": v})
        excl = ("States lacking either 2023 count: " + "; ".join(s8b_out)) if s8b_out \
            else ""
        summary.append(_summary(
            "S8(b) with ln r", dset, JAN_OCT, p_tr, wdesc, run_s8b(s8b, draws=draws),
            units_excluded_by_rule=excl,
            note="r = LS Q261 2023 / India TB Report 2024 2023; t with n - 3 df"))
        summary.append(_summary(
            "S8(b) without ln r (same States)", dset, JAN_OCT, p_tr, wdesc,
            run_model(s8b, draws=draws), units_excluded_by_rule=excl))
        # placebo
        pl = ok(pl_all)
        pl_res = run_model(pl, draws=draws, placebo=True)
        summary.append(_summary(
            PLACEBO, dset, PLACEBO_CONTRAST,
            "2019, 2022 (β^P = ln(N2022/N2019)/3)", "w = 1/(1/N2022 + 1/N2023)", pl_res,
            note=f"2023: {psrc[2023]}; 2022: {psrc[2022]}; 2019: {psrc[2019]}"))
        if pl_res.get("label") == PLACEBO_DIFFERS:
            for row in summary:
                if row["analysis"] == PRIMARY and row["denominator_set"] == dset:
                    row["label_note"] = NOT_SEPARABLE

        states_out += _state_rows(dset, FULL_YEAR, fy_all)
        states_out += _state_rows(dset, JAN_OCT, jo_all, lnr=lnr)
        states_out += _state_rows(dset, PLACEBO_CONTRAST, pl_all, placebo=True)

    return {"guard": status, "primary_contrast": primary_c, "summary": summary,
            "states": states_out, "loo": loo_out}


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_q4(result: dict) -> None:
    _write(OUT / "q4_summary.csv", SUMMARY_FIELDS, result["summary"])
    _write(OUT / "q4_states.csv", STATE_FIELDS, result["states"])
    _write(OUT / "q4_s2_leave_one_out.csv", LOO_FIELDS, result["loo"])


def main(argv: list[str]) -> int:
    if "--guard" in argv:
        res = run_guard()
        write_guard(res)
        print(f"guard: {res['status']}; median 2023 {res['medians'][2023]:.4f} "
              f"(n={res['n'][2023]}); median 2024 {res['medians'][2024]:.4f} "
              f"(n={res['n'][2024]}); primary: {res['consequences']['primary']}")
        return 0
    if "--q4" in argv:
        res = run_q4()
        write_q4(res)
        for r in res["summary"]:
            if r["analysis"] in (PRIMARY, PLACEBO):
                print(f"{r['analysis']} [{r['denominator_set']}] n={r['n']} "
                      f"gamma1={r['gamma1']} model ({r['gamma1_model_lo']}, "
                      f"{r['gamma1_model_hi']}) boot ({r['gamma1_boot_lo']}, "
                      f"{r['gamma1_boot_hi']}): "
                      + r["label"].encode("ascii", "replace").decode())
        return 0
    print("usage: python -I src/q4_dose_response.py --guard | --q4")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
