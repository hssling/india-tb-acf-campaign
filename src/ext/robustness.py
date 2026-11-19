"""Robustness of the three headline estimates (extension plan sections 7, 8 and 9): the
specification curves, leave one out, the section 8 labels, and a descriptive cross-check
against the two quality studies (sections 4.4 and 6, last bullets).

Run as `python -I src/ext/robustness.py` to write, under outputs/ext/ (UTF-8, LF):
  spec_curve.csv     every entry of the three section 7.1 grids (24 + 24 + 16), with its
                     point estimate, bootstrap interval, and whether it agrees in sign with
                     the main estimate;
  leave_one_out.csv  section 7.2: each State and each year left out, for epsilon, rho and
                     theta (point estimates only), with the minimum, maximum and most
                     influential omission flagged;
  headline.csv       section 8: the main value, interval, null, agreement share and label
                     ('supported' | 'not established') of epsilon, rho and theta, with the
                     leave-one-out range, the sum-gap coverage and (rho) the permutation band
                     reported beside the label (they do not change it);
  crosscheck.csv     descriptive side by side: the 2021 panel State values against the GHA
                     2023 S1/S2 Annex State rows, and the national cascade against the PGPH
                     2025 cascade. No agreement metric is computed.
Columns are documented in outputs/ext/README.md.

These are observational State-level associations; nothing here is read causally.

Random numbers: `numpy.random.default_rng(20261119)` is reset before every specification-
curve entry's bootstrap (inside `d1_saturation._cluster_boot` and
`d2_targeting.bootstrap_rho`) and before the permutation (section 9).
"""
from __future__ import annotations

import csv
import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python -I src/ext/robustness.py`
    sys.path.insert(0, str(ROOT))

from src import states  # noqa: E402
from src.ext import d1_saturation as D1  # noqa: E402
from src.ext import d1_yield as Y  # noqa: E402
from src.ext import d2_targeting as T  # noqa: E402
from src.ext import d3_additionality as D3  # noqa: E402
from src.ext import panel  # noqa: E402

OUT = ROOT / "outputs" / "ext"
EXTRACTED = ROOT / "data" / "extracted"
DRAWS = Y.DRAWS
ESTIMATES = ("epsilon", "rho", "theta")
NULLS = {"epsilon": 1.0, "rho": 0.0, "theta": 0.0}
THRESHOLD = 0.8  # section 8: at least 80% of the grid agrees in sign
UNITS_LEVELS = ("all", "excluding small UTs")

# section 7.1 grids, axes in the order of the plan's table; levels as written there
AXES = {"epsilon": ("weights", "zero", "years", "units"),
        "rho": ("measure", "denominator", "weights", "units"),
        "theta": ("outcome", "scale", "weights", "units")}
LEVELS = {
    "epsilon": {"weights": ("D", "none"), "zero": ("exclude", "+0.5"),
                "years": ("all five", "excluding 2022", "2021-2023"),
                "units": UNITS_LEVELS},
    "rho": {"measure": ("pooled_eb", "yield_2023", "eb_2023"),
            "denominator": ("reconstructed", "registered"),
            "weights": ("none", "screened_2023"), "units": UNITS_LEVELS},
    "theta": {"outcome": ("public", "total"), "scale": ("absolute", "log"),
              "weights": ("none", "inverse_poisson"), "units": UNITS_LEVELS},
}
# main levels: the first level of each axis, except where the plan names another
# (rho weights: 2023 screened, section 5.1; theta weights: inverse Poisson, section 7.1)
MAIN = {"epsilon": {"weights": "D", "zero": "exclude", "years": "all five", "units": "all"},
        "rho": {"measure": "pooled_eb", "denominator": "reconstructed",
                "weights": "screened_2023", "units": "all"},
        "theta": {"outcome": "public", "scale": "absolute", "weights": "inverse_poisson",
                  "units": "all"}}
YEAR_SETS = {"all five": (2018, 2019, 2021, 2022, 2023),
             "excluding 2022": (2018, 2019, 2021, 2023),
             "2021-2023": (2021, 2022, 2023)}
DESCRIPTION = {
    "epsilon": "elasticity of ACF diagnoses to screening volume within States",
    "rho": "Spearman correlation of a State's phase-1 campaign district share with its "
           "pooled 2021-2023 ACF yield",
    "theta": "within-State difference in public notifications associated with one more "
             "ACF diagnosis"}
CI_TYPE = {"epsilon": "cluster bootstrap", "rho": "bootstrap of units",
           "theta": "cluster bootstrap"}


# ---------------------------------------------------------------- grids (7.1)

def spec_grid(estimate: str) -> list:
    """The section 7.1 grid of `estimate` ('epsilon' | 'rho' | 'theta'): the full crossing
    of its axes in the plan's order, one dict per entry with the axis levels, `entry`
    (1-based) and `main`."""
    if estimate not in AXES:
        raise ValueError(estimate)
    axes = AXES[estimate]
    out = []
    for k, combo in enumerate(itertools.product(*(LEVELS[estimate][a] for a in axes)), 1):
        e = dict(zip(axes, combo))
        e.update({"estimate": estimate, "entry": k,
                  "main": all(e[a] == MAIN[estimate][a] for a in axes)})
        out.append(e)
    return out


def _non_small(rows) -> list:
    return sorted({r["unit"] for r in rows if not r["small_ut"]})


def _result(value, ci, n, G, n_valid, degenerate, reason=None) -> dict:
    return {"value": value, "ci": ci, "n": n, "n_units": G, "n_valid": n_valid,
            "degenerate": degenerate, "computable": value is not None, "reason": reason}


def _none(reason: str) -> dict:
    return _result(None, (None, None), None, None, None, None, reason)


def run_entry(e: dict, rows=None, draws: int = DRAWS) -> dict:
    """Point estimate and bootstrap interval of one grid entry (generator reset inside
    each bootstrap). A ValueError (e.g. a rank-deficient main design) or too few units
    makes the entry non-computable, with the reason."""
    rows = panel.load_panel() if rows is None else rows
    units = None if e["units"] == "all" else _non_small(rows)
    try:
        if e["estimate"] == "epsilon":
            r = D1.elasticity(rows, weights=e["weights"], zero=e["zero"],
                              years=YEAR_SETS[e["years"]], units=units, draws=draws)
            return _result(r["beta"], r["boot_ci"], r["n_obs"], r["n_units"],
                           r["n_valid"], r["degenerate"])
        if e["estimate"] == "rho":
            use, x, y, w, _ = T.alignment_sample(e["measure"], e["denominator"],
                                                 e["weights"], units)
            rho = T.weighted_spearman(x, y, w) if len(use) >= 3 else None
            if rho is None:
                return _none(f"rho undefined (n = {len(use)})")
            boot = T.bootstrap_rho(x, y, w, draws)
            nv = int(np.sum(~np.isnan(boot)))
            return _result(rho, T.band(boot), len(use), len(use), nv, draws - nv)
        r = D3.run(e["outcome"], e["scale"], e["weights"], e["units"], draws=draws)
        return _result(r["theta"], r["cluster_ci"], r["n"], r["G"], r["n_valid"],
                       r["degenerate"])
    except ValueError as exc:
        return _none(str(exc))


# ---------------------------------------------------------------- section 8 rules

def agrees(value, main, null) -> bool:
    """True if `value` lies strictly on the same side of the null as `main`. An entry
    exactly at the null, or not computable (None), does not agree (section 8)."""
    if value is None or main is None:
        return False
    return (value > null and main > null) or (value < null and main < null)


def excludes(ci, null) -> bool:
    """True if the interval lies strictly on one side of the null."""
    lo, hi = ci
    if lo is None or hi is None:
        return False
    return lo > null or hi < null


def agreement(values, main, null) -> dict:
    """Agreement over a whole grid (section 8): the denominator is every entry; a
    non-computable entry (None) counts as not agreeing."""
    values = list(values)
    k = sum(agrees(v, main, null) for v in values)
    return {"n": len(values), "n_agree": k, "share": k / len(values),
            "n_noncomputable": sum(v is None for v in values)}


def label_rule(ci, null, share) -> str:
    """Section 8: 'supported' only if the main 95% interval excludes the null AND at least
    80% of the specification-curve entries agree in sign; otherwise 'not established'."""
    return "supported" if excludes(ci, null) and share >= THRESHOLD else "not established"


# ---------------------------------------------------------------- specification curve

def _spec_text(e: dict) -> str:
    return "; ".join(f"{a}={e[a]}" for a in AXES[e["estimate"]])


def run_spec_curve(rows=None, draws: int = DRAWS) -> list:
    """All 64 entries (epsilon, rho, theta grids in order), each with its value, interval,
    agreement with its main estimate and whether its interval also excludes the null."""
    rows = panel.load_panel() if rows is None else rows
    out = []
    for est in ESTIMATES:
        grid = spec_grid(est)
        res = [run_entry(e, rows, draws) for e in grid]
        main = next(r for e, r in zip(grid, res) if e["main"])["value"]
        null = NULLS[est]
        for e, r in zip(grid, res):
            ag = agrees(r["value"], main, null)
            ex = excludes(r["ci"], null)
            out.append({**{a: e[a] for a in AXES[est]}, "estimate": est,
                        "entry": e["entry"], "main": e["main"],
                        "specification": _spec_text(e), "value": r["value"],
                        "ci_lo": r["ci"][0], "ci_hi": r["ci"][1], "interval": CI_TYPE[est],
                        "null": null, "computable": r["computable"], "agrees": ag,
                        "interval_excludes_null": ex, "agrees_and_excludes": ag and ex,
                        "n": r["n"], "n_units": r["n_units"], "draws": draws,
                        "n_valid": r["n_valid"], "degenerate": r["degenerate"],
                        "reason": r["reason"]})
    return out


# ---------------------------------------------------------------- leave one out (7.2)

def _rho_point(measure: dict, rows, drop=None) -> tuple:
    """(rho, n) with the main exposure (reconstructed) and weights (2023 screened), for a
    given unit -> measure mapping; `drop` is omitted from the correlation sample only."""
    xv, _ = T.exposure_values("reconstructed", rows)
    wv, _ = T.weight_values("screened_2023", rows)
    use = [u for u in sorted({r["unit"] for r in rows})
           if u != drop and u in xv and u in measure and u in wv]
    x = np.array([xv[u] for u in use])
    y = np.array([measure[u] for u in use])
    w = np.array([wv[u] for u in use])
    return T.weighted_spearman(x, y, w), len(use)


def _loo_rows(est: str, omission: str, items: list, main: float) -> list:
    """items: (omitted, value or None, n, n_units, note), in sorted order. Flags the
    minimum, the maximum and the most influential omission (largest |value - main|; ties
    go to the first in sorted order) among the computable ones."""
    null = NULLS[est]
    rows = []
    for om, v, n, g, note in items:
        d = None if v is None else v - main
        rows.append({"estimate": est, "omission": omission, "omitted": om, "value": v,
                     "main": main, "diff": d, "abs_diff": None if d is None else abs(d),
                     "null": null, "same_side_as_main": agrees(v, main, null),
                     "computable": v is not None, "n": n, "n_units": g,
                     "is_min": False, "is_max": False, "most_influential": False,
                     "note": note})
    ok = [r for r in rows if r["computable"]]
    if ok:
        lo = hi = top = ok[0]
        for r in ok[1:]:
            if r["value"] < lo["value"]:
                lo = r
            if r["value"] > hi["value"]:
                hi = r
            if r["abs_diff"] > top["abs_diff"]:
                top = r
        lo["is_min"] = hi["is_max"] = top["most_influential"] = True
    return rows


def leave_one_out(rows=None) -> list:
    """Section 7.2, main specifications, point estimates only (no bootstrap).
    epsilon: each unit, and each of the five years. theta: each unit, and each of 2019,
    2022 and 2023. rho: each unit, omitted from the correlation sample only (the pooled
    measure is not recomputed); and each of 2021, 2022 and 2023, with the section 4.2
    pooling and shrinkage rerun on the remaining two years (exposure and weights as in the
    main specification)."""
    rows = panel.load_panel() if rows is None else rows
    units = sorted({r["unit"] for r in rows})
    out = []

    def eps(**kw):
        try:
            r = D1.elasticity(rows, draws=0, **kw)
            return r["beta"], r["n_obs"], r["n_units"], None
        except ValueError as exc:
            return None, None, None, str(exc)

    main = D1.elasticity(rows, draws=0)["beta"]
    items = []
    for u in units:
        v, n, g, why = eps(units=[x for x in units if x != u])
        items.append((u, v, n, g, why))
    out += _loo_rows("epsilon", "state", items, main)
    items = []
    for y in YEAR_SETS["all five"]:
        v, n, g, why = eps(years=[t for t in YEAR_SETS["all five"] if t != y])
        items.append((str(y), v, n, g, why))
    out += _loo_rows("epsilon", "year", items, main)

    pooled = {s["unit"]: s["post_mean_log"] for s in Y.analyse_pooled(rows=rows)[1]}
    main_rho, _ = _rho_point(pooled, rows)
    items = []
    for u in units:
        v, n = _rho_point(pooled, rows, drop=u)
        note = None if u in pooled else "not in the main correlation sample (no pooled value)"
        items.append((u, v, n, n, note))
    out += _loo_rows("rho", "state", items, main_rho)
    items = []
    for y in Y.POOLED_YEARS:
        keep = tuple(t for t in Y.POOLED_YEARS if t != y)
        _, st, _ = Y.analyse_pooled(years=keep, rows=rows)
        v, n = _rho_point({s["unit"]: s["post_mean_log"] for s in st}, rows)
        items.append((str(y), v, n, n, "pooling and shrinkage rerun on "
                      + " and ".join(map(str, keep))))
    out += _loo_rows("rho", "year", items, main_rho)

    def theta(**kw):
        try:
            r = D3.additionality(rows=rows, draws=0, **kw)
            return r["theta"], r["n"], r["G"], None
        except ValueError as exc:
            return None, None, None, str(exc)

    main_t = D3.additionality(rows=rows, draws=0)["theta"]
    items = []
    for u in units:
        v, n, g, why = theta(units=[x for x in units if x != u])
        items.append((u, v, n, g, why))
    out += _loo_rows("theta", "state", items, main_t)
    items = []
    for y in D3.YEARS:
        v, n, g, why = theta(years=[t for t in D3.YEARS if t != y])
        items.append((str(y), v, n, g, why))
    out += _loo_rows("theta", "year", items, main_t)
    return out


# ---------------------------------------------------------------- headline (8)

SUM_GAP = {"epsilon": "the 'excluding 2022' entries of the grid",
           "rho": "leaving out 2022 (pooling rerun on 2021 and 2023)",
           "theta": "leaving out 2022"}


def headline(curve=None, loo=None, rows=None, draws: int = DRAWS) -> list:
    """One row per headline estimate: the main value, its main interval, the null, the
    agreement share over the whole grid, and the section 8 label. Beside it, not changing
    it: the leave-one-out range, the ITR 2023 sum-gap coverage and (rho) the permutation
    band."""
    rows = panel.load_panel() if rows is None else rows
    curve = run_spec_curve(rows, draws) if curve is None else curve
    loo = leave_one_out(rows) if loo is None else loo
    out = []
    for est in ESTIMATES:
        ent = [c for c in curve if c["estimate"] == est]
        m = next(c for c in ent if c["main"])
        null = NULLS[est]
        a = agreement([c["value"] for c in ent], m["value"], null)
        n_both = sum(c["agrees_and_excludes"] for c in ent)
        ci = (m["ci_lo"], m["ci_hi"])
        row = {"estimate": est, "description": DESCRIPTION[est], "main_value": m["value"],
               "ci_lo": ci[0], "ci_hi": ci[1], "interval": CI_TYPE[est], "null": null,
               "interval_excludes_null": excludes(ci, null), "n_entries": a["n"],
               "n_agree": a["n_agree"], "agreement_share": a["share"],
               "n_noncomputable": a["n_noncomputable"],
               "noncomputable_entries": ";".join(str(c["entry"]) for c in ent
                                                 if not c["computable"]),
               "n_agree_and_interval_excludes": n_both,
               "share_agree_and_interval_excludes": n_both / a["n"],
               "label": label_rule(ci, null, a["share"]), "n": m["n"],
               "n_units": m["n_units"]}
        for om in ("state", "year"):
            rs = [r for r in loo if r["estimate"] == est and r["omission"] == om]
            lo = next(r for r in rs if r["is_min"])
            hi = next(r for r in rs if r["is_max"])
            top = next(r for r in rs if r["most_influential"])
            row.update({f"loo_{om}_min": lo["value"], f"loo_{om}_min_omitted": lo["omitted"],
                        f"loo_{om}_max": hi["value"], f"loo_{om}_max_omitted": hi["omitted"],
                        f"loo_{om}_most_influential": top["omitted"],
                        f"loo_{om}_most_influential_value": top["value"],
                        f"loo_{om}_n_same_side": sum(r["same_side_as_main"] for r in rs),
                        f"loo_{om}_n": len(rs)})
        if est == "epsilon":
            gap = [c for c in ent if c["years"] == "excluding 2022"]
            gap_vals = [c["value"] for c in gap]
        else:
            gap = [r for r in loo if r["estimate"] == est and r["omission"] == "year"
                   and r["omitted"] == "2022"]
            gap_vals = [r["value"] for r in gap]
        row.update({"sum_gap_coverage": SUM_GAP[est], "sum_gap_n": len(gap_vals),
                    "sum_gap_n_same_side": sum(agrees(v, m["value"], null)
                                               for v in gap_vals)})
        if est == "rho":
            _, x, y, w, _ = T.alignment_sample()
            row["perm_lo"], row["perm_hi"] = T.band(T.permutation_rho(x, y, w, draws))
            row["outside_perm_band"] = bool(m["value"] < row["perm_lo"]
                                            or m["value"] > row["perm_hi"])
        out.append(row)
    return out


# ---------------------------------------------------------------- cross-check

GHA_STATE = (("S1 Annex", "screened", "screened"), ("S1 Annex", "tested", "tested"),
             ("S1 Annex", "diagnosed", "diagnosed"),
             ("S1 Annex", "population", "population"),
             ("S2 Annex", "diagnosed", "acf_diagnosed_s2"),
             ("S2 Annex", "public_notified", "public_notified"),
             ("S2 Annex", "pct_acf_share", "acf_pct_of_public_notified"))
PANEL_2021 = {"screened": "screened", "tested": "tested", "diagnosed": "diagnosed",
              "population": "est_population", "acf_diagnosed_s2": "diagnosed"}
PGPH_PERIOD = "January-September 2023, 30 sampled districts"
GHA_PERIOD = "first ACF cycle 2021"


def _quality() -> list:
    with open(EXTRACTED / "quality_studies.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _num(v: str):
    v = v.strip()
    if v == "":
        return None
    f = float(v)
    return int(f) if f.is_integer() and "." not in v else f


def _gha_by_unit(q: list) -> dict:
    """(table, quantity) -> {coarse unit or 'India': (value, derivation)}; merged units
    are summed (NA if any member is NA); a merged unit's percentage is recomputed from
    its summed S2 counts."""
    raw: dict = {}
    for r in q:
        if r["study"] != "GHA2023SM":
            continue
        g = r["geography"]
        unit = "India" if g == "India" else states.coarsen(g)
        raw.setdefault((r["table_id"], r["quantity"]), {}).setdefault(unit, []).append(
            (r["row_label"], _num(r["value"]), r["printed_value"]))
    out: dict = {}
    for key, by in raw.items():
        out[key] = {}
        for u, mem in by.items():
            if len(mem) == 1:
                lab, v, printed = mem[0]
                out[key][u] = (v, "printed" if v is not None else f"not printed ({printed})")
            elif key[1] == "pct_acf_share":
                out[key][u] = None  # recomputed below
            elif any(v is None for _, v, _ in mem):
                out[key][u] = (None, "a member is not printed: "
                               + "; ".join(lab for lab, v, _ in mem if v is None))
            else:
                out[key][u] = (sum(v for _, v, _ in mem), "summed over members: "
                               + "; ".join(lab for lab, _, _ in mem))
    pct = out[("S2 Annex", "pct_acf_share")]
    for u, v in list(pct.items()):
        if v is None:
            d = out[("S2 Annex", "diagnosed")][u][0]
            n = out[("S2 Annex", "public_notified")][u][0]
            pct[u] = ((100.0 * d / n, "recomputed as 100 x summed S2 diagnosed / summed "
                       "S2 public notified (merged unit)") if d is not None and n
                      else (None, "not computable for the merged unit"))
    return out


def _cascade_values(S, Tt, D) -> dict:
    return {"screened": S, "tested": Tt, "diagnosed": D,
            "pct_tested_of_screened": 100.0 * Tt / S, "pct_diagnosed_of_tested":
            100.0 * D / Tt, "diagnosed_per_100k_screened": 100000.0 * D / S}


def crosscheck(rows=None) -> list:
    """Descriptive side by side; no agreement metric (sections 4.4 and 6, cross-checks)."""
    rows = panel.load_panel() if rows is None else rows
    q = _quality()
    gha = _gha_by_unit(q)
    p21 = {r["unit"]: r for r in rows if r["year"] == 2021}
    units = sorted({r["unit"] for r in rows})
    out = []
    for u in units + ["India"]:
        for table, qty, name in GHA_STATE:
            gv, gd = gha[(table, qty)].get(u, (None, "no row in the study table"))
            col = PANEL_2021.get(name)
            note = None
            if u == "India":
                if col:
                    vals = [p21[x][col] for x in units if x in p21]
                    have = [v for v in vals if v is not None]
                    pv = sum(have) if have else None
                    note = (f"panel value is the sum of the {len(have)} panel units with a "
                            f"value (of {len(vals)}); the study row is the printed India row")
                else:
                    pv = None
            else:
                pv = p21[u][col] if (col and u in p21) else None
            if col is None:
                note = ("the panel has no 2021 notifications (no ITR Annexure 1.2 for data "
                        "year 2021 in the panel, plan section 3.1); study value shown alone")
            elif name == "acf_diagnosed_s2":
                note = (note + "; " if note else "") + "panel value is 2021 ACF diagnosed"
            elif name == "population":
                note = ((note + "; " if note else "")
                        + "panel value is the ITR 2022 estimated population")
            out.append({"section": "state 2021", "unit": u, "quantity": name,
                        "panel_year": 2021, "panel_value": pv,
                        "panel_source": "ITR 2022 Annexure 6" if col else None,
                        "study": "GHA2023SM", "study_table": table,
                        "study_period": GHA_PERIOD, "study_value": gv,
                        "study_derivation": gd, "note": note})
    pg = {r["quantity"]: _num(r["value"]) for r in q
          if r["study"] == "PGPH2025" and r["table_id"] == "Table 2"
          and r["row_group"] == "Total"}
    pv_pg = _cascade_values(pg["screened"], pg["tested"], pg["diagnosed"])
    for year in Y.YEARS:
        ok, excl, tdef = D1._cascade(rows, year)
        A = np.array([ok[u] for u in sorted(ok)], dtype=np.int64).sum(axis=0)
        vals = _cascade_values(int(A[0]), int(A[1]), int(A[2]))
        for name, v in vals.items():
            out.append({"section": "national cascade", "unit": "India", "quantity": name,
                        "panel_year": year, "panel_value": v,
                        "panel_source": f"sum of {len(ok)} units with S, T and D present "
                                        f"and positive (as d1_decomposition.csv); tested "
                                        f"column: {tdef}",
                        "study": "PGPH2025", "study_table": "Table 2, row Total",
                        "study_period": PGPH_PERIOD, "study_value": pv_pg[name],
                        "study_derivation": ("printed" if name in pg else
                                             "computed from the printed counts"),
                        "note": ("2022 'tested' counts people examined (sensitivity only)"
                                 if tdef == "examined" else None)})
    for name, v, how in (("presumptive", pg["presumptive"], "printed"),
                         ("pct_tested_of_presumptive", 100.0 * pg["tested"] /
                          pg["presumptive"], "computed from the printed counts")):
        out.append({"section": "national cascade", "unit": "India", "quantity": name,
                    "panel_year": None, "panel_value": None, "panel_source": None,
                    "study": "PGPH2025", "study_table": "Table 2, row Total",
                    "study_period": PGPH_PERIOD, "study_value": v, "study_derivation": how,
                    "note": "the panel has no presumptive-TB step"})
    return out


# ---------------------------------------------------------------- outputs

CURVE_FIELDS = ("estimate", "entry", "main", "specification", "weights", "zero", "years",
                "measure", "denominator", "outcome", "scale", "units", "value", "ci_lo",
                "ci_hi", "interval", "null", "computable", "agrees",
                "interval_excludes_null", "agrees_and_excludes", "n", "n_units", "draws",
                "n_valid", "degenerate", "reason")
LOO_FIELDS = ("estimate", "omission", "omitted", "value", "main", "diff", "abs_diff",
              "null", "same_side_as_main", "computable", "n", "n_units", "is_min", "is_max",
              "most_influential", "note")
HEAD_FIELDS = ("estimate", "description", "label", "main_value", "ci_lo", "ci_hi",
               "interval", "null", "interval_excludes_null", "n_entries", "n_agree",
               "agreement_share", "n_noncomputable", "noncomputable_entries",
               "n_agree_and_interval_excludes", "share_agree_and_interval_excludes", "n",
               "n_units") + tuple(
    f"loo_{om}_{k}" for om in ("state", "year")
    for k in ("min", "min_omitted", "max", "max_omitted", "most_influential",
              "most_influential_value", "n_same_side", "n")) + (
    "sum_gap_coverage", "sum_gap_n", "sum_gap_n_same_side", "perm_lo", "perm_hi",
    "outside_perm_band")
CROSS_FIELDS = ("section", "unit", "quantity", "panel_year", "panel_value", "panel_source",
                "study", "study_table", "study_period", "study_value", "study_derivation",
                "note")


def build_results(draws: int = DRAWS) -> dict:
    rows = panel.load_panel()
    curve = run_spec_curve(rows, draws)
    loo = leave_one_out(rows)
    return {"curve": curve, "loo": loo, "headline": headline(curve, loo, rows, draws),
            "crosscheck": crosscheck(rows)}


def build(draws: int = DRAWS) -> dict:
    """file name -> CSV text for every file under outputs/ext written by this module."""
    R = build_results(draws)
    return {"spec_curve.csv": Y.render(CURVE_FIELDS, R["curve"]),
            "leave_one_out.csv": Y.render(LOO_FIELDS, R["loo"]),
            "headline.csv": Y.render(HEAD_FIELDS, R["headline"]),
            "crosscheck.csv": Y.render(CROSS_FIELDS, R["crosscheck"])}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    built = build()
    for name, text in built.items():
        with open(OUT / name, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    print(built["headline.csv"])


if __name__ == "__main__":
    main()
