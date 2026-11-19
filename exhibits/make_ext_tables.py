# New for the extension (v1.1.0); keeps the conventions of exhibits/make_tables.py (no typed numbers, every numeric cell traced to its output file, row and column, Markdown and CSV output, superscript letter footnotes)
"""Render the extension paper's tables (Table 1 and Tables S1-S8) from outputs/ext/ and outputs/.

Run as: python -I exhibits/make_ext_tables.py [--out DIR]   (from the repository root)

The paper is programme guidance for Public Health: "Where does active case finding for TB still
pay in India?". Its five main display items are Table 1 (here) and Figures 1-4
(exhibits/make_ext_figures.py); everything else is supplementary (Tables S1-S8).

Standard library only. Reads outputs/ext/*.csv and outputs/*.csv only. Writes, to DIR (default
manuscript/ext/exhibits/, git-ignored and local):
- tables.md       Table 1 and Tables S1-S8 as Markdown (no vertical rules; footnotes as
                  superscript lowercase letters, in reading order);
- <table>.csv     each table as CSV (UTF-8, LF);
- trace.json      every numeric cell with its exhibit, source file, row, column, raw value and
                  formatter, so tests/test_ext_exhibits.py can re-derive it from the outputs.

No number is typed here. Labels are plain language: no file names, section signs, variable
names or internal identifiers reach a table.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript" / "ext" / "exhibits"

MAIN_TABLES = ["Table 1"]  # the main-text table; the figures are Figures 1-4 (make_ext_figures.py)
SUP = "ᵃᵇᶜᵈᵉᶠ"  # tools/build_submission.py sets these as superscript letters (at most six per table)
MINUS = "−"

H = "outputs/ext/headline.csv"
EL = "outputs/ext/d1_elasticity.csv"
DEC = "outputs/ext/d1_decomposition.csv"
POOL = "outputs/ext/d1_pooled.csv"
POOLB = "outputs/ext/d1_pooled_betweenyear.csv"
ST = "outputs/ext/d1_states.csv"
STB = "outputs/ext/d1_states_betweenyear.csv"
TBI = "outputs/ext/d1_tiers_by_intensity.csv"
EXCL = "outputs/ext/d1_excluded.csv"
AL = "outputs/ext/d2_alignment.csv"
SH = "outputs/ext/d2_tier_shares.csv"
SC = "outputs/ext/d2_scenario.csv"
SCU = "outputs/ext/d2_scenario_units.csv"
D3 = "outputs/ext/d3.csv"
LOO = "outputs/ext/leave_one_out.csv"
SPEC = "outputs/ext/spec_curve.csv"
CC = "outputs/ext/crosscheck.csv"
Q3S = "outputs/q3_yield_summary.csv"
Q2S = "outputs/q2_summary_registered_vs_corrected.csv"
Q2C = "outputs/q2_discrepancies_corrected.csv"

_CACHE: dict[str, list[dict]] = {}


def read(rel: str) -> list[dict]:
    if rel not in _CACHE:
        with open(ROOT / rel, newline="", encoding="utf-8") as f:
            _CACHE[rel] = list(csv.DictReader(f))
    return _CACHE[rel]


def row_index(rel: str, **kv) -> int:
    hits = [i for i, r in enumerate(read(rel)) if all(r[k] == v for k, v in kv.items())]
    if len(hits) != 1:
        raise ValueError(f"expected one row of {rel} for {kv}, found {len(hits)}")
    return hits[0]


# --------------------------------------------------------------------------------------
# Formatters (applied to the raw string read from the file)
# --------------------------------------------------------------------------------------
def _minus(s: str) -> str:
    return s.replace("-", MINUS)


def f_dec(d: int):
    def fmt(raw: str) -> str:
        x = float(raw)
        s = f"{x:,.{d}f}"
        if x != 0 and float(s.replace(",", "")) == 0:
            s = f"{x:,.{d + 1}f}"  # a non-zero value never prints as zero
        if float(s.replace(",", "")) == 0:
            s = s.lstrip("-")
        return _minus(s)
    fmt.__name__ = f"dec{d}"
    return fmt


def f_round0(raw: str) -> str:
    return _minus(f"{round(float(raw)):,}")


def f_pct(d: int):
    def fmt(raw: str) -> str:
        return f_dec(d)(repr(100 * float(raw)))
    fmt.__name__ = f"pct{d}"
    return fmt


def f_years(raw: str) -> str:
    return raw.replace(";", ", ")


def f_strata(raw: str) -> str:
    """'high=0.184...;low=0.428...' -> '0.18 (higher intensity), 0.43 (lower intensity)'."""
    parts = dict(p.split("=") for p in raw.split(";"))
    return f"{f_dec(2)(parts['high'])} (higher intensity), {f_dec(2)(parts['low'])} (lower intensity)"


FORMATTERS = {"dec0": f_dec(0), "dec1": f_dec(1), "dec2": f_dec(2), "dec3": f_dec(3),
              "round0": f_round0, "pct0": f_pct(0), "pct1": f_pct(1), "years": f_years,
              "strata": f_strata, "raw": lambda s: s}


def dig(raw: str) -> str:
    """Decimals for an estimate: two, or three when it is below 0.1 in size."""
    return "dec3" if abs(float(raw)) < 0.1 else "dec2"


class Trace:
    """Records where each numeric cell comes from; `exhibit` is the table being built."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.exhibit = ""

    def value(self, file: str, i: int, column: str, fmt: str) -> str:
        raw = read(file)[i][column]
        text = FORMATTERS[fmt](raw)
        self.entries.append({"exhibit": self.exhibit, "kind": "value", "file": file, "row": i,
                             "column": column, "raw": raw, "fmt": fmt, "text": text})
        return text

    def rng(self, file: str, i: int, lo: str, hi: str, fmt: str) -> str:
        return f"{self.value(file, i, lo, fmt)} to {self.value(file, i, hi, fmt)}"

    def interval(self, file: str, i: int, col: str, lo: str, hi: str, fmt: str) -> str:
        return f"{self.value(file, i, col, fmt)} ({self.rng(file, i, lo, hi, fmt)})"


class Notes:
    """Lettered footnotes, lettered in the order their marks are first placed (reading order)."""

    def __init__(self) -> None:
        self.keys: list[str] = []
        self.text: dict[str, str] = {}

    def mark(self, key: str, text: str) -> str:
        if key not in self.text:
            if len(self.keys) == len(SUP):
                raise ValueError("more than six footnotes in one table")
            self.keys.append(key)
            self.text[key] = text
        return SUP[self.keys.index(key)]

    def lettered(self) -> list[str]:
        return [f"{SUP[i]} {self.text[k]}" for i, k in enumerate(self.keys)]


# --------------------------------------------------------------------------------------
# Plain names
# --------------------------------------------------------------------------------------
def state(unit: str) -> str:
    return unit.replace(" (incl. Ladakh)", " (including Ladakh)")


TIER = {"above": "Above", "overlaps": "Overlaps", "below": "Below", "not robust": "Not robust",
        "no tier": "No pooled value"}
ESTIMATE = {"epsilon": "Elasticity (ε)", "rho": "Alignment (ρ)", "theta": "Notifications (θ)"}
YESNO = {"yes": "Yes", "no": "No"}
AXIS = {
    ("weights", "D"): "weighted by diagnoses", ("weights", "none"): "unweighted",
    ("weights", "screened_2023"): "weighted by 2023 screening",
    ("weights", "inverse_poisson"): "inverse-variance weights",
    ("zero", "exclude"): "zero counts left out", ("zero", "+0.5"): "0.5 added to zero counts",
    ("years", "all five"): "all five data years", ("years", "excluding 2022"): "2022 left out",
    ("years", "2021-2023"): "2021–2023 only",
    ("units", "all"): "all States", ("units", "excluding small UTs"): "small Union Territories left out",
    ("measure", "pooled_eb"): "pooled 2021–2023 yield", ("measure", "yield_2023"): "2023 observed yield",
    ("measure", "eb_2023"): "2023 shrunken yield",
    ("denominator", "reconstructed"): "reconstructed district count",
    ("denominator", "registered"): "registered district count",
    ("outcome", "public"): "public-sector notifications", ("outcome", "total"): "total notifications",
    ("scale", "absolute"): "absolute scale", ("scale", "log"): "log scale",
}
D3_AXES = ("outcome", "scale", "weights", "units")


def spec_text(r: dict) -> str:
    """A grid entry's specification in words, in the order of its axes."""
    axes = [p.split("=", 1)[0].strip() for p in r["specification"].split(";")]
    return "; ".join(AXIS[(a, r[a])] for a in axes)


def d3_text(r: dict) -> str:
    w = {"inverse_poisson": "inverse_poisson", "none": "none"}[r["weights"]]
    return "; ".join(AXIS[(a, w if a == "weights" else r[a])] for a in D3_AXES)


# --------------------------------------------------------------------------------------
# Layout helpers
# --------------------------------------------------------------------------------------
def md_cell(s: str) -> str:
    return s.replace("|", "\\|")


def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(md_cell(h) for h in header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(md_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def grid(sections: list[tuple[str | None, list[str], list[list[str]]]]) -> tuple[list[str], list[list[str]]]:
    """One table from several blocks: the first block's header is the table header; each later
    block opens with a bold spanning row (its title) and a bold heading row."""
    width = max(len(h) for _, h, _ in sections)

    def pad(r: list[str]) -> list[str]:
        return r + [""] * (width - len(r))

    header, rows = pad(sections[0][1]), [pad(r) for r in sections[0][2]]
    for title, h, rs in sections[1:]:
        rows.append(pad([f"**{title}**"]))
        rows.append(pad([f"**{x}**" for x in h]))
        rows += [pad(r) for r in rs]
    return header, rows


# Columns whose cells are labels (names, years, specifications), not results.
LABEL_COLUMNS = {"Estimate", "Data year", "State or Union Territory", "Model", "Years", "Year",
                 "Testing definition", "Component", "Quantity", "Specification", "Scenario",
                 "Tiers used", "Classification", "Tier", "Side", "Role", "Left out", "Note",
                 "Check within a document", "Result", "Grid", "Entry", "Interval",
                 "Main specification", "Registered tier", "Between-year tier", "Robust tier",
                 "Intensity stratum", "Tier within stratum", "Same side of the null",
                 "Agrees in sign", "Interval excludes the null", "Label", "Status"}


# --------------------------------------------------------------------------------------
# Table 1: headline estimates and robustness
# --------------------------------------------------------------------------------------
def table1(tr: Trace, fn: Notes):
    header = ["Estimate",
              "Main value (95% interval)" + fn.mark("interval", "Cluster-bootstrap percentile interval (States resampled with all their years) for ε and θ; bootstrap of States for ρ."),
              "Null", "Sample",
              "Specifications agreeing in sign" + fn.mark("spec", "Entries of the pre-specified specification grid whose estimate lies on the same side of the null as the main estimate, out of the whole grid, then the number of those whose own interval also excludes the null. Every entry is in Table S6 and Figure 4."),
              "Leave one out, lowest to highest" + fn.mark("loo", "Point estimates with each State, then each data year, left out in turn; the State or year left out is in parentheses (all omissions in Table S5)."),
              "Label" + fn.mark("label", "Pre-specified rule: supported only if the main interval excludes the null and at least 80% of the specifications agree in sign with the main estimate; otherwise not established, with the interval stated.")]
    names = {"epsilon": "Elasticity of ACF diagnoses to screening volume within States (ε)",
             "rho": "Correlation of a State's share of campaign districts with its prior yield (ρ)",
             "theta": "Difference in public-sector notifications per additional ACF diagnosis within States (θ)"}
    rows = []

    def head_row(key: str, mark: str = "") -> list[str]:
        i = row_index(H, estimate=key)
        r = read(H)[i]
        f = dig(r["main_value"])
        sample = (f"{tr.value(H, i, 'n_units', 'round0')} States" if key == "rho" else
                  f"{tr.value(H, i, 'n', 'round0')} State-years, {tr.value(H, i, 'n_units', 'round0')} States")
        spec = (f"{tr.value(H, i, 'n_agree', 'round0')} of {tr.value(H, i, 'n_entries', 'round0')} "
                f"({tr.value(H, i, 'agreement_share', 'pct0')}%); "
                f"{tr.value(H, i, 'n_agree_and_interval_excludes', 'round0')} with interval excluding the null")
        loo = (f"{tr.value(H, i, 'loo_state_min', f)} ({state(tr.value(H, i, 'loo_state_min_omitted', 'raw'))}) to "
               f"{tr.value(H, i, 'loo_state_max', f)} ({state(tr.value(H, i, 'loo_state_max_omitted', 'raw'))}) over States; "
               f"{tr.value(H, i, 'loo_year_min', f)} ({tr.value(H, i, 'loo_year_min_omitted', 'raw')}) to "
               f"{tr.value(H, i, 'loo_year_max', f)} ({tr.value(H, i, 'loo_year_max_omitted', 'raw')}) over years")
        label = r["label"][0].upper() + r["label"][1:]
        return [names[key] + mark, tr.interval(H, i, "main_value", "ci_lo", "ci_hi", f),
                tr.value(H, i, "null", "dec0"), sample, spec, loo, label]

    def sub_row(name: str, file: str, i: int, sample: str, fmt: str | None = None) -> list[str]:
        r = read(file)[i]
        f = fmt or dig(r["estimate"])
        return ["  " + name, tr.interval(file, i, "estimate", "boot_lo", "boot_hi", f),
                tr.value(file, i, "null", "dec0"), sample, "", "", ""]

    def wls_sample(file: str, i: int) -> str:
        return f"{tr.value(file, i, 'n_obs', 'round0')} State-years, {tr.value(file, i, 'n_units', 'round0')} States"

    rows.append(head_row("epsilon"))
    i = row_index(EL, analysis="poisson")
    rows.append(sub_row("Poisson model, zero counts kept", EL, i, wls_sample(EL, i)))
    strata = fn.mark("strata", "States above or below the median number screened per head of population, 2021–2023. The registered population year was misaligned with its State rows as printed and was not used (a disclosed deviation).")
    for a, name in (("stratum high", "Higher-intensity States" + strata), ("stratum low", "Lower-intensity States")):
        i = row_index(EL, analysis=a)
        rows.append(sub_row(name, EL, i, wls_sample(EL, i)))
    rows.append(head_row("rho", fn.mark("weights", "Weighted by the number screened in 2023, so a few States with very large screening volumes carry most of the weight (effective number of States about 3); the unweighted row counts each State once.")))
    i = row_index(AL, analysis="unweighted")
    rows.append(sub_row("Unweighted", AL, i, f"{tr.value(AL, i, 'n', 'round0')} States"))
    rows.append(head_row("theta"))
    i = row_index(D3, analysis="public log weights=inverse_poisson units=all")
    rows.append(sub_row("Log scale (proportional difference)", D3, i, wls_sample(D3, i), "dec3"))
    i = row_index(D3, analysis="total absolute weights=inverse_poisson units=all")
    rows.append(sub_row("Total notifications", D3, i, wls_sample(D3, i)))
    notes = ["ε: percentage change in ACF diagnoses for a 1% change in the number screened, within States "
             "(State and year fixed effects, weighted by diagnoses; five data years, 2018 to 2023); below 1, diagnoses "
             "rose less than proportionally with screening. ρ: Spearman correlation between a State's share of districts "
             "in phase 1 of the campaign and its pooled 2021–2023 ACF yield. θ: within-State difference in public-sector "
             "notifications associated with one more ACF diagnosis (2019, 2022 and 2023; weights inverse to the expected "
             "variance); were it causal, 1 would correspond to full addition and 0 to full substitution. These are "
             "reference values only, and they do not apply to the log-scale row. All three are observational State-level "
             "associations. No P values are reported."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Table S1: pooled yield by data year
# --------------------------------------------------------------------------------------
def supp_pooled(tr: Trace, fn: Notes):
    header = ["Data year", "States pooled (n)",
              "Pooled yield per 100,000 screened (95% CI)" + fn.mark("pooled", "DerSimonian–Laird random-effects mean of the States' log yields (diagnosed ÷ screened), back-transformed. It describes the typical State, not the national ratio."),
              "95% prediction interval" + fn.mark("pi", "The range expected for the yield of a new State."),
              "Between-State variance (τ²)", "I² (%)",
              "Tiers: above, overlaps, below (n)" + fn.mark("tiers", "Each State's posterior interval against the pooled mean (Table S2)."),
              "National yield per 100,000 screened (95% CI)" + fn.mark("national", "The printed India row of the India TB Report for that data year, with a Wilson interval.")]
    rows = []

    def row(label: str, file: str, i: int, national: str) -> list[str]:
        return [label, tr.value(file, i, "k", "round0"),
                tr.interval(file, i, "yield_per_100k", "ci_lo_per_100k", "ci_hi_per_100k", "dec1"),
                tr.rng(file, i, "pi_lo_per_100k", "pi_hi_per_100k", "dec1"),
                tr.value(file, i, "tau2", "dec2"), tr.value(file, i, "i2", "dec2"),
                ", ".join(tr.value(file, i, c, "round0") for c in ("n_above", "n_overlaps", "n_below")), national]

    for i, r in enumerate(read(POOL)):
        if r["analysis"] == "2021-2023":
            continue
        j = row_index(Q3S, state="India", year=r["analysis"], indicator="yield_diagnosed_per_100000")
        rows.append(row(r["analysis"], POOL, i, tr.interval(Q3S, j, "value", "lower", "upper", "dec1")))
    rows.append(row("2021–2023, pooled", POOL, row_index(POOL, analysis="2021-2023"), ""))
    mark = fn.mark("between", "Post hoc sensitivity, added after the registered tiers were seen: each State's yearly yields are combined by a within-State random-effects mean whose interval includes the variation between years.")
    rows.append(row("2021–2023, between-year (post hoc)" + mark, POOLB, 0, ""))
    return header, rows, fn.lettered()


# --------------------------------------------------------------------------------------
# Table S2: State tiers, registered and between-year, and within intensity strata
# --------------------------------------------------------------------------------------
def supp_tiers(tr: Trace, fn: Notes):
    header = ["State or Union Territory", "Data years",
              "Registered: posterior yield per 100,000 (95% interval)" + fn.mark("plugin", "Empirical-Bayes posterior of the pooled 2021–2023 yield (diagnosed ÷ screened, summed over the years with data). The intervals are plug-in: they reflect binomial sampling variance only, conditional on the estimated mean and between-State variance, and omit the variation between years within a State, so they are narrower than the true uncertainty. Tier: the posterior interval lies above the pooled mean, overlaps it or lies below it. Rank 1 is the highest yield; the rank intervals are plug-in too."),
              "Rank interval", "Registered tier",
              "Between-year (post hoc): posterior yield per 100,000 (95% interval)" + fn.mark("between", "Post hoc sensitivity, added after the registered tiers were seen: each State's yearly yields are combined by a within-State random-effects mean whose interval includes the variation between years, then shrunk and tiered as in the registered analysis."),
              "Between-year tier",
              "Robust tier" + fn.mark("robust", "Yes if the registered and the between-year tiers agree. Only these tiers are described as robust."),
              "Intensity stratum",
              "Tier within stratum" + fn.mark("stratum", "Tier against the stratum's own pooled mean, States split at the median number screened per head of population, 2021–2023.")]
    st = {r["unit"]: i for i, r in enumerate(read(ST)) if r["analysis"] == "2021-2023"}
    by = {r["unit"]: i for i, r in enumerate(read(STB))}
    tbi = {r["unit"]: i for i, r in enumerate(read(TBI))}
    none = [r["unit"] for r in read(EXCL) if r["analysis"] == "2021-2023" and r["year"] == ""]
    if set(st) != set(by):
        raise ValueError("Table S2: registered and between-year units differ")
    rows = []
    for u in sorted(set(st) | set(none), key=state):
        if u in none:
            rows.append([state(u) + fn.mark("none", "No usable year in 2021–2023 (zero diagnoses in each), so no pooled value."),
                         "", "", "", TIER["no tier"], "", "", "", "", ""])
            continue
        i, j = st[u], by[u]
        b = read(STB)[j]
        name = state(u) + (fn.mark("single", "One usable year: binomial variance only in the between-year analysis.") if b["single_year"] == "yes" else "")
        k = tbi.get(u)
        strat = ("", "") if k is None else ({"high": "Higher", "low": "Lower"}[read(TBI)[k]["stratum"]],
                                            TIER[read(TBI)[k]["tier"]])
        rows.append([name, tr.value(ST, i, "years", "years"),
                     tr.interval(ST, i, "post_per_100k", "post_lo_per_100k", "post_hi_per_100k", "dec1"),
                     tr.rng(ST, i, "rank_lo", "rank_hi", "round0"), TIER[read(ST)[i]["tier"]],
                     tr.interval(STB, j, "post_per_100k", "post_lo_per_100k", "post_hi_per_100k", "dec1"),
                     TIER[b["tier"]], YESNO[b["tier_agrees"]], strat[0], strat[1]])
    return header, rows, fn.lettered()


# --------------------------------------------------------------------------------------
# Table S3: elasticity variants and the cascade decomposition
# --------------------------------------------------------------------------------------
EL_NAMES = {"main": "Main: weighted by diagnoses, zero counts left out", "poisson": "Poisson model, zero counts kept",
            "stratum high": "Higher-intensity States", "stratum low": "Lower-intensity States"}
DEF = {"tested": "Tested", "examined": "Examined", "tested->examined": "Tested, then examined",
       "examined->tested": "Examined, then tested"}
QUANT = {"dln_yield": "Change in log yield", "testing_part": "Testing step", "positivity_part": "Positivity step",
         "ln_yield": "Log yield", "ln_testing": "Log testing rate", "ln_positivity": "Log positivity",
         "var_total": "Variance of the log yield", "var_testing": "Variance, testing step",
         "var_positivity": "Variance, positivity step", "cov": "Covariance of the two steps",
         "testing_share": "Testing share", "positivity_share": "Positivity share"}


def supp_elasticity(tr: Trace, fn: Notes):
    hA = ["Model", "Point estimate",
          "Cluster-bootstrap 95% interval" + fn.mark("boot", "States resampled with all their years; percentile interval. It is the main interval."),
          "Cluster-robust model interval", "State-years (n)", "States (n)"]
    rA = []
    for i, r in enumerate(read(EL)):
        rA.append([EL_NAMES[r["analysis"]], tr.value(EL, i, "estimate", "dec2"), tr.rng(EL, i, "boot_lo", "boot_hi", "dec2"),
                   tr.rng(EL, i, "model_ci_lo", "model_ci_hi", "dec2"), tr.value(EL, i, "n_obs", "round0"),
                   tr.value(EL, i, "n_units", "round0")])
    hB = ["Years", "Testing definition" + fn.mark("def", "In the 2022 data year the tested column counts people examined; rows involving 2022 are sensitivity analyses."),
          "Component" + fn.mark("comp", "ln(diagnosed ÷ screened) = ln(tested ÷ screened) + ln(diagnosed ÷ tested): the testing step plus the positivity step, from national sums over the States with all three counts; the two steps add up to the change in log yield exactly."),
          "Point estimate", "Cluster-bootstrap 95% interval", "States (n)"]
    rB, rC, rD = [], [], []
    for i, r in enumerate(read(DEC)):
        cells = [DEF[r["testing_definition"]], QUANT[r["quantity"]], tr.value(DEC, i, "estimate", "dec2"),
                 tr.rng(DEC, i, "boot_lo", "boot_hi", "dec2"), tr.value(DEC, i, "n_units", "round0")]
        yrs = r["years"].replace("->", " to ")
        {"change": rB, "level": rC, "variance": rD}[r["analysis"]].append([yrs] + cells)
    hD = ["Year", "Testing definition",
          "Quantity" + fn.mark("share", "Unweighted variances across States of the two log steps; the covariance is split equally, so the testing and positivity shares sum to 1."),
          "Point estimate", "Cluster-bootstrap 95% interval", "States (n)"]
    header, rows = grid([(None, hA, rA),
                         ("Cascade decomposition of the national change in yield", hB, rB),
                         ("National levels by year", ["Year", "Testing definition", "Quantity", "Point estimate",
                                                      "Cluster-bootstrap 95% interval", "States (n)"], rC),
                         ("Between-State variance of the log yield and its split by step", hD, rD)])
    notes = ["Elasticity: ln(diagnosed) on ln(screened) with State and year fixed effects, five data years. "
             "Intensity strata as in Table 1. Every interval is 95%."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Table S4: targeting: alignment variants, campaign districts by tier, the scenario
# --------------------------------------------------------------------------------------
AL_NAMES = {"main": "Main: weighted by 2023 screening", "unweighted": "Unweighted",
            "registered denominator": "Registered district count", "2023 yield": "2023 observed yield",
            "2023 empirical Bayes": "2023 shrunken yield"}
SC_NAMES = {"main": "Main: registered tiers", "stratum elasticity": "Elasticity by intensity stratum",
            "robust tiers (post hoc)": "Robust tiers only (post hoc)"}
CLASS = {"registered pooled 2021-2023": "Registered", "robust (post hoc)": "Robust (post hoc)"}
SIDE = {"gains": "Gains", "loses": "Loses"}


def supp_targeting(tr: Trace, fn: Notes):
    hA = ["Specification", "Spearman correlation",
          "Bootstrap 95% interval" + fn.mark("boot", "States resampled; the ranks are recomputed in each draw."),
          "Permutation null band" + fn.mark("perm", "The 2.5th to 97.5th percentiles of the correlation when the campaign shares are permuted over States; reported beside the estimate, it does not change its label."),
          "States (n)"]
    rA = [[AL_NAMES[r["analysis"]], tr.value(AL, i, "estimate", "dec2"), tr.rng(AL, i, "boot_lo", "boot_hi", "dec2"),
           tr.rng(AL, i, "perm_lo", "perm_hi", "dec2"), tr.value(AL, i, "n", "round0")] for i, r in enumerate(read(AL))]
    hB = ["Classification", "Tier", "States (n)", "Phase-1 campaign districts (n)",
          "Share of all phase-1 campaign districts (%)"]
    rB = [[CLASS[r["classification"]], TIER[r["tier"]], tr.value(SH, i, "n_units", "round0"),
           tr.value(SH, i, "campaign_districts", "round0"), tr.value(SH, i, "share", "pct1")]
          for i, r in enumerate(read(SH))]
    hC = ["Scenario", "Elasticity", "Gaining States (n)", "Losing States (n)", "Screening moved (people)",
          "Change in the gainers' screening (%)",
          "Expected change in diagnoses (95% interval)" + fn.mark("scen", "An illustration, not a forecast. Each below-tier State loses 10% of its 2023 screening and the moved volume goes to the above-tier States in proportion to their 2023 volume, so total screening is unchanged; the expected change applies the within-State elasticity to each State's 2023 diagnoses and assumes that it would hold under reallocation. The interval carries the uncertainty of the elasticity only. The elasticity was estimated from changes that partly reflect differing definitions of people screened between report editions. Maharashtra supplies most of the moved volume in the main scenario, and its below tier is not robust."),
          "As % of the States' 2023 diagnoses (95% interval)"]
    rC = []
    for i, r in enumerate(read(SC)):
        if r["computable"] != "yes":
            raise ValueError(f"scenario {r['analysis']} not computable")
        eps = tr.value(SC, i, "epsilon", "strata" if r["elasticity"] == "intensity stratum" else "dec2")
        rC.append([SC_NAMES[r["analysis"]], eps, tr.value(SC, i, "n_gainers", "round0"),
                   tr.value(SC, i, "n_losers", "round0"), tr.value(SC, i, "moved", "round0"),
                   tr.value(SC, i, "r_gain", "pct1"), tr.interval(SC, i, "delta", "ci_lo", "ci_hi", "round0"),
                   tr.interval(SC, i, "pct", "pct_lo", "pct_hi", "dec1")])
    hD = ["Scenario", "State or Union Territory", "Tier", "Side", "Screened in 2023 (n)", "Diagnosed in 2023 (n)",
          "Change in screening (%)", "Elasticity applied", "Expected change in diagnoses"]
    rD = [[SC_NAMES[r["analysis"]], state(r["unit"]), TIER[r["tier"]], SIDE[r["side"]],
           tr.value(SCU, i, "screened_2023", "round0"), tr.value(SCU, i, "diagnosed_2023", "round0"),
           tr.value(SCU, i, "r", "pct1"), tr.value(SCU, i, "epsilon", "dec2"), tr.value(SCU, i, "delta", "dec1")]
          for i, r in enumerate(read(SCU))]
    header, rows = grid([(None, hA, rA), ("Phase-1 campaign districts by yield tier", hB, rB),
                         ("Illustrative reallocation of screening from below-tier to above-tier States", hC, rC),
                         ("The reallocation by State", hD, rD)])
    notes = ["Observational State-level associations. Campaign districts were not concentrated in States of higher "
             "prior yield; this is consistent with selection on the published criteria (TB death rate, presumptive TB "
             "examination rate, incidence and prevalence, with districts added by States for local vulnerability) "
             "rather than on yield, which is not tested, and it is not read as a targeting failure."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Table S5: notifications (all specifications) and leave one out
# --------------------------------------------------------------------------------------
ROLE = {"main": "Main", "registered secondary (section 6)": "Registered secondary",
        "specification variant (section 7.1)": "Specification variant"}
LOO_NOTE = {"": "", "not in the main correlation sample (no pooled value)": "Not in the main sample (no pooled value)"}


def loo_note(n: str) -> str:
    if n in LOO_NOTE:
        return LOO_NOTE[n]
    if n.startswith("pooling and shrinkage rerun on "):
        return "Pooled yield re-estimated on " + n.split(" on ", 1)[1]
    raise ValueError(f"unexpected leave-one-out note {n!r}")


def supp_notifications(tr: Trace, fn: Notes):
    hA = ["Specification", "Role", "θ",
          "Cluster-bootstrap 95% interval" + fn.mark("boot", "States resampled with all their years; percentile interval (the main interval)."),
          "Cluster-robust model interval", "State-years (n)", "States (n)"]
    rA = []
    for i, r in enumerate(read(D3)):
        f = "dec3" if r["scale"] == "log" else "dec2"
        rA.append([d3_text(r), ROLE[r["role"]], tr.value(D3, i, "estimate", f), tr.rng(D3, i, "boot_lo", "boot_hi", f),
                   tr.rng(D3, i, "model_ci_lo", "model_ci_hi", f), tr.value(D3, i, "n_obs", "round0"),
                   tr.value(D3, i, "n_units", "round0")])
    hB = ["Estimate", "Left out", "Value", "Difference from the main value",
          "Same side of the null" + fn.mark("side", "Yes if the value lies strictly on the same side of the null as the main value."),
          "Observations (n)" + fn.mark("obs", "State-years for ε and θ; States for ρ."), "Note"]
    rB = []
    for i, r in enumerate(read(LOO)):
        left = state(r["omitted"]) if r["omission"] == "state" else f"Data year {tr.value(LOO, i, 'omitted', 'raw')}"
        rB.append([ESTIMATE[r["estimate"]], left, tr.value(LOO, i, "value", "dec3"), tr.value(LOO, i, "diff", "dec3"),
                   YESNO[r["same_side_as_main"]], tr.value(LOO, i, "n", "round0"), loo_note(r["note"])])
    header, rows = grid([(None, hA, rA), ("Leave one out: each State, then each data year (point estimates)", hB, rB)])
    notes = ["θ: within-State difference in notifications associated with one more ACF diagnosis, 2019, 2022 and 2023. "
             "On the log scale it is the proportional difference in notifications per proportional difference in ACF "
             "diagnoses. Inverse-variance weights: 1 ÷ notifications on the absolute scale and notifications on the log "
             "scale. Only three years overlap, so θ rests on within-State change across three years."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Table S6: the full specification grid
# --------------------------------------------------------------------------------------
INTERVAL = {"cluster bootstrap": "Cluster bootstrap", "bootstrap of units": "Bootstrap of States"}


def supp_spec(tr: Trace, fn: Notes):
    header = ["Estimate", "Entry", "Main specification", "Specification", "Value", "95% interval", "Interval",
              "Agrees in sign" + fn.mark("agree", "Yes if the value lies strictly on the same side of the null (1 for ε; 0 for ρ and θ) as the main value."),
              "Interval excludes the null", "Observations (n)" + fn.mark("obs", "State-years for ε and θ; States for ρ.")]
    rows = []
    for i, r in enumerate(read(SPEC)):
        if r["computable"] != "yes":
            raise ValueError(f"specification entry {r['estimate']} {r['entry']} not computable")
        f = dig(r["value"]) if r["estimate"] == "theta" else "dec2"
        rows.append([ESTIMATE[r["estimate"]], r["entry"], YESNO[r["main"]], spec_text(r), tr.value(SPEC, i, "value", f),
                     tr.rng(SPEC, i, "ci_lo", "ci_hi", f), INTERVAL[r["interval"]], YESNO[r["agrees"]],
                     YESNO[r["interval_excludes_null"]], tr.value(SPEC, i, "n", "round0")])
    notes = ["The full crossing of the pre-specified axes, in grid order. No entry was non-computable."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Table S7: descriptive cross-check against the two quality studies
# --------------------------------------------------------------------------------------
CC_STATE = ["screened", "tested", "diagnosed", "population"]


def supp_crosscheck(tr: Trace, fn: Notes):
    cc = read(CC)
    idx = {(r["section"], r["unit"], r["quantity"], r["panel_year"]): i for i, r in enumerate(cc)}
    hA = ["State or Union Territory"]
    for q in CC_STATE:
        hA += [f"{q.capitalize()}: report", f"{q.capitalize()}: study"]
    hA += ["ACF diagnoses: study, second table" + fn.mark("s2", "The study's second supplementary table counts ACF-detected cases against public-sector notified TB; its ACF share is printed (recomputed from summed counts for a merged unit)."),
           "Public-sector notifications: study", "ACF share of public notifications, %: study"]
    units = sorted({r["unit"] for r in cc if r["section"] == "state 2021"}, key=lambda u: (u == "India", state(u)))
    rA = []

    def cell(i: int | None, col: str, fmt: str) -> str:
        return "" if i is None or not cc[i][col] else tr.value(CC, i, col, fmt)

    for u in units:
        row = [state(u) if u != "India" else "India (sum of the States)"]
        for q in CC_STATE:
            i = idx.get(("state 2021", u, q, "2021"))
            row += [cell(i, "panel_value", "round0"), cell(i, "study_value", "round0")]
        i = idx.get(("state 2021", u, "acf_diagnosed_s2", "2021"))
        row.append(cell(i, "study_value", "round0"))
        i = idx.get(("state 2021", u, "public_notified", ""))
        row.append(cell(i, "study_value", "round0"))
        i = idx.get(("state 2021", u, "acf_pct_of_public_notified", ""))
        row.append(cell(i, "study_value", "dec1"))
        rA.append(row)
    years = sorted({r["panel_year"] for r in cc if r["section"] == "national cascade" and r["panel_year"]})
    ex = fn.mark("examined", "In the 2022 data year the tested column of the report counts people examined.")
    hB = ["Quantity"] + [y + (ex if y == "2022" else "") for y in years] + ["Study: 30 districts, January to September 2023"]
    NAT = [("screened", "People screened", "round0"), ("tested", "People tested", "round0"),
           ("diagnosed", "People diagnosed", "round0"), ("pct_tested_of_screened", "Tested among screened (%)", "dec2"),
           ("pct_diagnosed_of_tested", "Diagnosed among tested (%)", "dec2"),
           ("diagnosed_per_100k_screened", "Diagnosed per 100,000 screened", "dec1"),
           ("presumptive", "People with presumptive TB", "round0"),
           ("pct_tested_of_presumptive", "Tested among presumptive (%)", "dec1")]
    rB = []
    for q, label, f in NAT:
        row = [label]
        for y in years:
            row.append(cell(idx.get(("national cascade", "India", q, y)), "panel_value", f))
        first = next(i for i, r in enumerate(cc) if r["section"] == "national cascade" and r["quantity"] == q)
        row.append(tr.value(CC, first, "study_value", f))
        rB.append(row)
    header, rows = grid([(None, hA, rA),
                         ("National cascade: sums over the States with all three counts, beside the 30-district study", hB, rB)])
    notes = ["Values set side by side; no agreement measure is computed. Upper block: data year 2021, India TB Report "
             "2022 (report) beside the first ACF cycle of 2021 in the 2023 national quality study (study); Jammu and "
             "Kashmir and Ladakh are summed. The report has no 2021 notifications. A blank cell: no row in the study "
             "table, or not printed. Lower block: the report's national sums by data year beside the 2025 study of 30 "
             "sampled districts; the study's presumptive-TB step has no counterpart in the report."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Table S8: how to read official ACF figures (the v1.0.0 consistency and reconciliation results)
# --------------------------------------------------------------------------------------
CHECKS = [("1 cascade does not grow", "A later cascade step does not exceed an earlier one"),
          ("2 percentage recomputes", "A printed percentage recomputes from its counts"),
          ("3 total equals the sum of its parts", "A total equals the sum of its parts"),
          ("4 cumulative series never decreases", "A cumulative series never decreases")]
CLASS_KEYS = ["1", "2", "3a", "3b", "4"]


def supp_reading(tr: Trace, fn: Notes):
    post = fn.mark("post", "Three post hoc corrections of the registered rules, disclosed as deviations: a figure's window ends at its printed end date; printed public and private parts enter only the sum check; and the cascade check compares only figures from one printed cascade.")
    hA = ["Check within a document", "Registered rules: pass, fail, not run",
          "Corrected rules (post hoc): pass, fail, not run" + post]
    rA = []
    for key, label in CHECKS:
        cells = []
        for col in ("registered", "corrected"):
            cells.append(", ".join(tr.value(Q2S, row_index(Q2S, metric=f"Q1 check {key}: {res}"), col, "round0")
                                   for res in ("pass", "fail", "n/a")))
        rA.append([label] + cells)
    hB = ["Result", "Registered rules",
          "Corrected rules (post hoc)" + post]
    labels = {r["class"]: r["class_label"] for r in read(Q2C) if r["class"]}
    rB = []
    for label, metric in [("Entry pairs compared" + fn.mark("pairs", "Pairs of distinct (document, value) entries for the same quantity, geography and scope with overlapping windows or identical window labels, including exploratory pairs from two parliamentary answers added after registration."), "Q2 entry pairs (all)"),
                          ("Agree (intervals overlap)", "Q2 all: agree")] + \
                         [(f"Class {k}: {labels[k]}", f"Q2 all: class {k}") for k in CLASS_KEYS]:
        i = row_index(Q2S, metric=metric)
        rB.append([label, tr.value(Q2S, i, "registered", "round0"), tr.value(Q2S, i, "corrected", "round0")])
    header, rows = grid([(None, hA, rA),
                         ("The same campaign figure compared between official documents", hB, rB)])
    notes = ["How to read official ACF figures. Before comparing or summing published campaign figures, check that the "
             "quantity is defined the same way (notified or diagnosed), that the windows and cut-off dates match, and "
             "that totals and percentages recompute from their printed parts. Most differences between documents "
             "reflect windows or cut-off dates; class 4 records that the published documents do not explain a "
             "difference, not that a figure is wrong."]
    return header, rows, notes + fn.lettered()


# --------------------------------------------------------------------------------------
# Build and write
# --------------------------------------------------------------------------------------
TABLES = [
    ("Table 1", "Headline estimates: main value, robustness and the pre-specified label", table1, True),
    ("Table S1", "ACF yield per 100,000 people screened by data year: pooled across States and national", supp_pooled, False),
    ("Table S2", "State and Union Territory yield tiers, 2021–2023: registered, between-year (post hoc) and within intensity strata", supp_tiers, False),
    ("Table S3", "Elasticity of ACF diagnoses to screening volume, and the cascade decomposition", supp_elasticity, False),
    ("Table S4", "Targeting: alignment of campaign districts with prior yield, campaign districts by tier, and the illustrative reallocation", supp_targeting, False),
    ("Table S5", "Notifications and ACF diagnoses: every specification, and leave-one-out results for the three headline estimates", supp_notifications, False),
    ("Table S6", "The pre-specified specification grid: every entry for the three headline estimates", supp_spec, False),
    ("Table S7", "Descriptive cross-check against the two quality studies", supp_crosscheck, False),
    ("Table S8", "How to read official ACF figures: consistency of published campaign figures within and between documents", supp_reading, False),
]


def build() -> tuple[dict, Trace]:
    tr = Trace()
    ex: dict[str, dict] = {}
    for name, title, fn_, main in TABLES:
        tr.exhibit = name
        h, r, n = fn_(tr, Notes())
        ex[name] = {"title": title, "panels": [(h, r)], "notes": n, "main": main}
    return ex, tr


def write_csv(out: Path, name: str, header: list[str], rows: list[list[str]]) -> None:
    with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT), help="output folder (default manuscript/ext/exhibits)")
    out = Path(ap.parse_args(argv).out)
    out.mkdir(parents=True, exist_ok=True)
    ex, tr = build()
    md = ["# Tables\n"]
    for name, e in ex.items():
        md.append(f"## {name}. {e['title']}\n")
        for h, r in e["panels"]:
            md.append(md_table(h, r) + "\n")
            write_csv(out, name.replace(" ", "").lower(), h, r)
        for n in e["notes"]:
            md.append(n + "\n")
    (out / "tables.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    (out / "trace.json").write_text(json.dumps(tr.entries, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8", newline="\n")
    print(f"wrote {len(ex)} tables and {len(tr.entries)} traced cells to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
