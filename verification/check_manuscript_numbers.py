# Adapted from hssling/india-state-tb-score (MIT), verification/check_manuscript_numbers.py, commit 05bcaa7; modified: rewritten for the ACF campaign study (two profiles: the v1.0.0 audit catalogue of Q1-Q4 values from outputs/ and data/, and the extension catalogue from outputs/ext/; section-scoped phrases; a golden skeleton that maps every number token to its source; checks for blinding, internal identifiers and reference order)
"""Check every number in the blinded manuscript against the committed outputs.

Run as: python -I verification/check_manuscript_numbers.py [--manuscript-dir DIR] [--regenerate]

The manuscript folder (default manuscript/ext, the extension paper; the audit-framed v1.0.0
manuscript is checked with --manuscript-dir manuscript/v1_audit) is git-ignored, kept private and
not in this repository. A relative DIR is taken from the repository root. When the folder is
absent this prints "SKIPPED: <folder>/ not present (kept private, not in this repository)" and
exits 0, and check_all counts the step as skipped. It is skipped in the same way when the folder
holds neither manuscript_src.md nor section_phrases.json (as in a clone where the tests have
written <folder>/exhibits/). If one of those two files is present without the other, the check
FAILS (exit 1): it never passes without its phrases.

Profiles. Each folder is checked under one profile: "ext" (the extension paper: catalogue_ext()
from outputs/ext/, outputs/ for the box and the national yield, the extension plan and both
registration records; claims_ext(); Table 1, Figures 1-4, Tables S1-S8, Box 1) or "v1" (the
v1.0.0 audit manuscript: catalogue_v1(), claims_v1(); Tables 1-3, Figures 1-2, Tables S1-S4 and
Supplementary data S1a/S1b). The profile is the "profile" key of the folder's
section_phrases.json if present, else "v1" for a folder named v1_audit and "ext" otherwise.

When <folder>/manuscript_src.md is present, these checks run on every section except the
References (each section's text with its whitespace collapsed):

1. Section phrases. <folder>/section_phrases.json (git-ignored, kept with the manuscript
   because the phrases quote it) lists, for each section, phrases with {label}
   placeholders. Each label is a value of the profile's catalogue, derived from outputs/ (and, where
   the outputs are built from them, data/, the registered plan and ENVIRONMENT.md), and
   formatted by the helpers below. Every filled phrase must occur whole in its own
   section, so a changed value, a sign flip or a value moved to another section fails.
2. Every number is accounted for. Each number token of a section is assigned a label:
   the placeholder of a phrase occurrence that covers it, or a FIXED pattern (exhibit,
   question, analysis and class names, years 2018-2026, dates that are catalogue values,
   reference superscripts, the plan's constants). A token with no label is UNACCOUNTED.
3. The golden skeleton. <folder>/number_skeleton.json holds, for each section, the
   ordered list of {token, label, source} of the reviewed text. The current text must
   give the same tokens with the same labels in the same order, and each golden label
   must still resolve in the catalogue to the same token. Regenerate only after review:
   python -I verification/check_manuscript_numbers.py --regenerate
4. Claims (the profile's claims function): statements the prose makes in words (no clear association; the placebo's
   interval excludes 0; the guard passed; S7 not run; ...) are re-tested on the outputs.
5. Exhibits: the profile's main tables and figures are each cited, first citations in order,
   each figure has a legend; supplementary tables cited exist, first cited in order. References: every superscript is in range, each
   reference is cited, and references are numbered in order of first citation.
6. Blinding and wording: no author name, ORCID, institution or repository address (read
   from the plan's header); no internal identifiers (rulings, decision IDs, task numbers,
   shorthand source IDs); no listed American spellings.

Exit 1 on any problem.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MS_DIR = "manuscript/ext"  # the extension paper; the v1.0.0 audit manuscript is manuscript/v1_audit
V1_EXHIBITS = "manuscript/v1_audit/exhibits"  # where exhibits/make_figures.py writes the v1.0.0 figures
SKIP_DIR = "SKIPPED: {d}/ not present (kept private, not in this repository)"
SKIP_MS = "SKIPPED: {d}/manuscript_src.md not present (kept private, not in this repository)"
MS_NAME = "manuscript_src.md"
PHRASES = "section_phrases.json"
SKELETON = "number_skeleton.json"

# --------------------------------------------------------------------------------------
# Number formats: the only place they are fixed
# --------------------------------------------------------------------------------------
MINUS = "−"  # U+2212; a negative that rounds to zero keeps its sign ("−0.000"), as in the tables
TO = " to "  # every interval: "0.003 to 0.081"
MONTHS = ("January February March April May June July August September October November "
          "December").split()


def num(x: float | str, dp: int) -> str:
    s = f"{float(x):.{dp}f}"
    return MINUS + s[1:] if s.startswith("-") else s


def num3(x: float | str) -> str:
    """Three decimals; a non-zero value that would print as 0.000 gets four ("−0.0004"),
    as in exhibits/make_tables.py."""
    s = num(x, 3)
    return num(x, 4) if float(x) != 0 and float(s.replace(MINUS, "-")) == 0 else s


def signed(x: float | str, dp: int) -> str:
    """A change with its sign: "+0.031", "−0.024"."""
    s = num(x, dp)
    return s if s.startswith(MINUS) else "+" + s


def count(n: int | str) -> str:
    v = float(n)
    if v != int(v):
        raise ValueError(f"not an integer count: {n!r}")
    s = f"{int(v):,}"
    return MINUS + s[1:] if s.startswith("-") else s


def rng(lo: str, hi: str) -> str:
    return f"{lo}{TO}{hi}"


def day(iso: str) -> str:
    """'2025-02-22' -> '22 February 2025'."""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def whole_or(x: float | str, dp: int) -> str:
    """0 and 1 as '0' and '1'; other values with dp decimals."""
    v = float(x)
    return str(int(v)) if v == int(v) else num(v, dp)


# --------------------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------------------
def read_csv(root: Path, rel: str) -> list[dict]:
    with open(root / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def one(rows: list[dict], what: str, **kv) -> dict:
    hits = [r for r in rows if all(r[k] == v for k, v in kv.items())]
    if len(hits) != 1:
        raise ValueError(f"{what}: {len(hits)} rows match {kv}")
    return hits[0]


def wilson(x: int, n: int) -> tuple[float, float]:
    z = statistics.NormalDist().inv_cdf(0.975)
    p = x / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def plan_text(root: Path) -> str:
    return (root / "docs" / "analysis_plan.md").read_text(encoding="utf-8")


def plan_has(root: Path, s: str, where: str) -> str:
    """s, after confirming the registered plan states it (so the constant is the plan's)."""
    if s not in plan_text(root):
        raise ValueError(f"the plan ({where}) does not state {s!r}")
    return s


def summary_metric(root: Path, metric: str, col: str) -> str:
    return one(read_csv(root, "outputs/q2_summary_registered_vs_corrected.csv"), "q2 summary",
               metric=metric)[col]


def q4row(root: Path, dset: str, analysis: str) -> dict:
    return one(read_csv(root, "outputs/q4_summary.csv"), "q4_summary", denominator_set=dset,
               analysis=analysis)


def fig_value(root: Path, fig_id: str) -> dict:
    return one(read_csv(root, "data/figures_inventory.csv"), "inventory", fig_id=fig_id)


def disc_rows(root: Path) -> list[dict]:
    return read_csv(root, "outputs/q2_discrepancies_corrected.csv")


def side(r: dict, pred) -> tuple[str, str] | None:
    """('a' or 'b', the other side) of the first side of pair r for which pred(prefix) holds."""
    for s, o in (("a", "b"), ("b", "a")):
        if pred(s):
            return s, o
    return None


# --------------------------------------------------------------------------------------
# Catalogue: label -> (text, source)
# --------------------------------------------------------------------------------------
def catalogue_v1(root: Path) -> dict[str, tuple[str, str]]:
    """The v1.0.0 audit manuscript's catalogue (Q1-Q4)."""
    c: dict[str, tuple[str, str]] = {}

    def put(label: str, text: str, source: str) -> None:
        if label in c:
            raise ValueError(f"duplicate catalogue label {label}")
        c[label] = (text, source)

    # ---- dates (a date anywhere in the text must be one of these) -------------------------
    reg = json.loads((root / "docs" / "registration_event.json").read_text(encoding="utf-8"))
    pushed = reg["pushed_at"]  # 2026-11-18T17:59:29Z
    put("date.registration", day(pushed), "docs/registration_event.json: pushed_at")
    put("reg.time", pushed[11:16] + " UTC", "docs/registration_event.json: pushed_at")
    put("date.campaign_start", plan_has(root, "7 December 2024", "§1.1"), "docs/analysis_plan.md §1.1")
    put("date.novelty", plan_has(root, "18 November 2026", "§1.1"), "docs/analysis_plan.md §1.1 (novelty check)")
    window = plan_has(root, "1 December 2022 to 18 November 2026", "§5.3")
    put("plan.search_window", window, "docs/analysis_plan.md §5.3")

    # ---- inventory and search -------------------------------------------------------------
    inv = read_csv(root, "data/figures_inventory.csv")
    put("inv.n_figures", count(len(inv)), "data/figures_inventory.csv: rows")
    put("inv.n_documents", count(len({r["source_file"] for r in inv})),
        "data/figures_inventory.csv: distinct source_file")
    log = read_csv(root, "data/search_log.csv")
    put("search.n_records", count(len(log)), "data/search_log.csv: rows")
    put("search.n_included", count(sum(r["include"] == "yes" for r in log)),
        "data/search_log.csv: include = yes")
    put("plan.magnitudes", plan_has(root, "1 lakh = 100,000; 1 crore = 10,000,000", "§5.2"),
        "docs/analysis_plan.md §5.2")
    lakh, crore = 100_000 / 1e6, 10_000_000 / 1e6  # the plan's magnitudes in millions (figure axes)
    put("plan.magnitudes_million", f"1 lakh = {lakh:g} million; 1 crore = {crore:g} million",
        "docs/analysis_plan.md §5.2, converted to millions")
    lb = [r for r in disc_rows(root) for s in "ab" if r[f"{s}_value_printed"] == "25 crore"
          and r[f"{s}_qualifier"] == "at_least"]
    if not lb:
        raise ValueError("no 'over 25 crore' lower bound in q2_discrepancies_corrected.csv")
    put("example.lower_bound", "25 crore",
        "outputs/q2_discrepancies_corrected.csv: value_printed '25 crore', qualifier at_least")

    # ---- exposure table ---------------------------------------------------------------------
    e7 = one(read_csv(root, "data/extracted/exposure_checks_reconstructed.csv"), "E7", check="E7")
    m = re.fullmatch(r"(\d+) districts; (\d+) States/UTs", e7["observed"])
    put("exp.districts", m.group(1), "data/extracted/exposure_checks_reconstructed.csv: E7 observed")
    put("exp.states", m.group(2), "data/extracted/exposure_checks_reconstructed.csv: E7 observed")

    # ---- Q1 -------------------------------------------------------------------------------------
    q1 = read_csv(root, "outputs/q1_checks.csv")
    fails3 = [r for r in q1 if r["check"].startswith("3") and r["pass"] == "no"]

    def diff_of(fragment: str) -> str:
        r = one([x for x in fails3 if fragment in x["inputs"]], f"check 3 failure {fragment}")
        d = int(re.search(r"difference (-?\d+)", r["observed"]).group(1))
        if d >= 0:
            raise ValueError(f"{fragment}: parts do not fall short (difference {d})")
        return count(-d)

    src = "outputs/q1_checks.csv: check 3 failure, observed difference"
    put("q1.itr2023.screened", diff_of("Vulnerable individuals screened"), src)
    put("q1.itr2023.examined", diff_of("identified and examined"), src)
    put("q1.itr2023.diagnosed", diff_of("TB patients diagnosed"), src)
    put("q1.pgph.presumptive", diff_of("Presumptive TB n"), src)
    put("q1.pgph.screened", diff_of("Screened n (%)col"), src)
    put("q1.totals_pass", count(summary_metric(root, "Q1 check 3 total equals the sum of its parts: pass", "registered")),
        "outputs/q2_summary_registered_vs_corrected.csv: Q1 check 3 pass (registered)")
    n3 = sum(int(summary_metric(root, f"Q1 check 3 total equals the sum of its parts: {k}", "registered"))
             for k in ("pass", "fail", "n/a"))
    put("q1.totals_n", count(n3), "outputs/q2_summary_registered_vs_corrected.csv: Q1 check 3 pass+fail+n/a")
    put("q1.cascade_fail_registered",
        count(summary_metric(root, "Q1 check 1 cascade does not grow: fail", "registered")),
        "outputs/q2_summary_registered_vs_corrected.csv: Q1 check 1 fail (registered)")
    put("q1.cascade_pass_corrected",
        count(summary_metric(root, "Q1 check 1 cascade does not grow: pass", "corrected")),
        "outputs/q2_summary_registered_vs_corrected.csv: Q1 check 1 pass (corrected)")
    other = read_csv(root, "outputs/q1_other_descriptive.csv")
    pct = [r for r in other if r["check"].startswith("2")]
    put("q1.pct_pass", count(sum(r["pass"] == "yes" for r in pct)),
        "outputs/q1_other_descriptive.csv: check 2 pass = yes")
    put("q1.pct_n", count(sum(r["pass"] in ("yes", "no") for r in pct)),
        "outputs/q1_other_descriptive.csv: check 2 pass = yes or no")
    tot = [r for r in other if r["check"].startswith("3")]
    put("q1.other_totals_pass", count(sum(r["pass"] == "yes" for r in tot)),
        "outputs/q1_other_descriptive.csv: check 3 pass = yes")
    put("q1.other_totals_n", count(sum(r["pass"] in ("yes", "no") for r in tot)),
        "outputs/q1_other_descriptive.csv: check 3 pass = yes or no")
    fem = one([r for r in pct if r["pass"] == "no"], "the failing percentage")
    if "Female" not in fem["inputs"]:
        raise ValueError("the failing percentage is not the Female row")
    put("q1.female_printed", re.search(r"\('(\d+\.\d)'\)", fem["inputs"]).group(1) + "%",
        "outputs/q1_other_descriptive.csv: failing check 2, printed percentage")
    rec = float(re.search(r"100 n/d \[([\d.]+),", fem["observed"]).group(1))
    put("q1.female_recomputed", num(rec, 1) + "%",
        "outputs/q1_other_descriptive.csv: failing check 2, 100 n/d")
    ann = one([r for r in other if r["check"].startswith("3") and r["pass"] == "no"], "Annexure IV")
    d = int(re.search(r"difference (-?\d+)", ann["observed"]).group(1))
    if "Annexure IV" not in ann["inputs"] or d >= 0:
        raise ValueError("the descriptive sum failure is not Annexure IV falling short")
    put("q1.annex_iv", count(-d), "outputs/q1_other_descriptive.csv: check 3 failure, difference")

    # ---- Q2 --------------------------------------------------------------------------------
    s = "outputs/q2_summary_registered_vs_corrected.csv: "
    put("q2.reg.pairs", count(summary_metric(root, "Q2 entry pairs (all)", "registered")), s + "Q2 entry pairs (all), registered")
    put("q2.reg.groups", count(summary_metric(root, "Q2 comparison groups formed (§7.1)", "registered")), s + "groups, registered")
    put("q2.cor.pairs", count(summary_metric(root, "Q2 entry pairs (all)", "corrected")), s + "Q2 entry pairs (all), corrected")
    put("q2.cor.groups", count(summary_metric(root, "Q2 comparison groups formed (§7.1)", "corrected")), s + "groups, corrected")
    for k in ("agree", "class 1", "class 2", "class 3a", "class 3b", "class 4"):
        put(f"q2.cor.{k.replace('class ', 'c')}", count(summary_metric(root, f"Q2 all: {k}", "corrected")),
            s + f"Q2 all: {k}, corrected")
    for k in ("agree", "class 1", "class 2", "class 3a", "class 3b", "class 4"):
        kk = k.replace("class ", "c")
        put(f"q2.cor.pre.{kk}", count(summary_metric(root, f"Q2 pre-specified: {k}", "corrected")),
            s + f"Q2 pre-specified: {k}, corrected")
        put(f"q2.reg.pre.{kk}", count(summary_metric(root, f"Q2 pre-specified: {k}", "registered")),
            s + f"Q2 pre-specified: {k}, registered")
    for st in ("corrected", "registered"):
        put(f"q2.{st[:3]}.pre.pairs", count(summary_metric(root, "Q2 entry pairs (pre-specified)", st)),
            s + f"Q2 entry pairs (pre-specified), {st}")
        put(f"q2.{st[:3]}.expl", count(summary_metric(root, "Q2 entry pairs (exploratory)", st)),
            s + f"Q2 entry pairs (exploratory), {st}")
    rows = disc_rows(root)
    dist = [r for r in rows if r["quantity"] == "districts_selected" and r["geography"] == "India"
            and r["agree"] == "no"]
    v455 = {r["a_value_printed"] for r in dist} | {r["b_value_printed"] for r in dist}
    if v455 != {"455", "347"} or any(r["class"] != "4" for r in dist):
        raise ValueError(f"national district discrepancies are not all 455 against 347, class 4: {v455}")
    put("q2.d455", "455", "outputs/q2_discrepancies_corrected.csv: districts_selected, India, class 4")
    put("q2.d347", "347", "outputs/q2_discrepancies_corrected.csv: districts_selected, India, class 4")
    fig455 = set()
    for r in dist:
        a, _ = side(r, lambda p: r[f"{p}_value_printed"] == "455")
        fig455.add(r[f"{a}_fig_ids"].split(" | ")[0])
    pub455 = {fig_value(root, f)["pub_date"] for f in fig455}
    if len(pub455) != 1:
        raise ValueError(f"455 figures from several dates: {pub455}")
    put("date.pib455", day(next(iter(pub455))), "data/figures_inventory.csv: pub_date of the 455 figure")
    all455 = sorted({r["pub_date"] for r in read_csv(root, "data/figures_inventory.csv")
                     if r["quantity"] == "districts_selected" and r["geography"] == "India" and r["value"] == "455"})
    if len(all455) != 2 or not pub455 <= set(all455) or all455[0][:4] != all455[1][:4]:
        raise ValueError(f"expected two 455 releases in one year: {all455}")
    d1, d2 = (day(x).rsplit(" ", 1)[0] for x in all455)
    put("q2.d455_dates", f"{d1} and {d2} {all455[0][:4]}",
        "data/figures_inventory.csv: pub_date of every national 455 districts figure")

    def pair(qty: str, a_val: str, b_val: str) -> dict:
        hits = [r for r in rows if r["quantity"] == qty and {r["a_value_printed"], r["b_value_printed"]} == {a_val, b_val}]
        if not hits:
            raise ValueError(f"no {qty} pair {a_val} / {b_val}")
        return hits[0]

    r = pair("screened", "5.63 crore", "12.97 crore")
    if r["class"] != "4":
        raise ValueError("5.63 crore / 12.97 crore is not class 4")
    a, _ = side(r, lambda p: r[f"{p}_value_printed"] == "5.63 crore")
    q79 = r[f"{a}_fig_ids"].split(" | ")[0]
    put("date.lsq79", day(fig_value(root, q79)["pub_date"]), "data/figures_inventory.csv: pub_date of the 5.63 crore figure")
    src2 = "outputs/q2_discrepancies_corrected.csv: value_printed"
    put("q2.q79.screened", "5.63 crore", src2)
    put("q2.later.screened", "12.97 crore", src2)
    r = pair("tb_cases", "1.59 lakh", "7.19 lakh")
    put("q2.q79.cases", "1.59 lakh", src2)
    put("q2.later.cases", "7.19 lakh", src2)
    r = pair("screened", "2.23 crore", "223879862")
    if r["class"] != "4" or r["a_source"] != r["b_source"]:
        raise ValueError("2.23 crore / 223879862 is not a class 4 pair within one document")
    put("q2.itr2022.text", "2.23 crore", src2)
    put("q2.itr2022.annex", count(223879862 if "223879862" in (r["a_value"], r["b_value"]) else 0), src2)
    put("q2.itr2022.annex_crore", num(223879862 / 1e7, 2) + " crore", src2 + " (value / 10,000,000)")
    pre = read_csv(root, "outputs/q2_pre_identified_corrected.csv")
    named = one(pre, "named list", item="Named list against the CTD table")
    put("q2.named_states", count(named["n_disagree"]), "outputs/q2_pre_identified_corrected.csv: named list n_disagree")
    q3467 = [r for r in rows if r["class"] == "4" and r["geography"] != "India" and r["analysis"] == "pre-specified"
             and r["quantity"] == "tb_cases"]
    if any("AU3467" not in (r["a_source"] + r["b_source"]) for r in q3467):
        raise ValueError("a State-level pre-specified class 4 pair does not involve RS Q3467")
    put("q2.q3467_pairs", count(len(q3467)),
        "outputs/q2_discrepancies_corrected.csv: class 4, State, tb_cases, pre-specified (all RS Q3467)")
    nf = read_csv(root, "outputs/q2_not_formed.csv")[-1]
    m = re.search(r"(\d+\.\d+ crore) screened / (\d+\.\d+ lakh)", nf["candidate"])
    if not nf["reason"].startswith("not found"):
        raise ValueError("q2_not_formed: last row is not the not-found record")
    put("q2.notfound.screened", m.group(1), "outputs/q2_not_formed.csv: last row, candidate")
    put("q2.notfound.cases", m.group(2), "outputs/q2_not_formed.csv: last row, candidate")
    class1 = [r for r in rows if r["class"] == "1"]
    pg = {r[f"{p}_value_printed"] for r in class1 for p in "ab" if "PMC12574901" in r[f"{p}_source"]}
    if pg != {"581 633"}:
        raise ValueError(f"class 1 pairs do not all involve the PGPH total 581 633: {pg}")
    put("q2.pgph_screened", count(581633), "outputs/q2_discrepancies_corrected.csv: class 1, PGPH value_printed")

    # quality studies
    qs = read_csv(root, "outputs/q2_quality_studies.csv")
    for study, key in (("GHA2023", "gha"), ("PGPH2025", "pgph")):
        c1 = one(qs, "C1", study=study, indicator="C1")
        c4 = one(qs, "C4", study=study, indicator="C4")
        for r in (c1, c4):
            if r["published_within_rounding"] != "yes":
                raise ValueError(f"{study} {r['indicator']}: published value not reproduced")
        x, n = int(c1["numerator_n"]), int(c1["denominator_n"])
        lo, hi = wilson(x, n)
        f = "outputs/q2_quality_studies.csv: " + study
        put(f"qs.{key}.c1_pub", num(c1["published_value"], 1) + "%", f + " C1 published_value")
        put(f"qs.{key}.c1_rec", num(100 * x / n, 2) + "%", f + " C1 numerator_n / denominator_n")
        put(f"qs.{key}.c1_ci", rng(num(100 * lo, 2), num(100 * hi, 2)), f + " C1 Wilson interval (§8.2)")
        xs, nd = int(c4["numerator_n"]), int(c4["denominator_n"])  # screened, diagnosed
        lo, hi = wilson(nd, xs)
        put(f"qs.{key}.nns", count(round(xs / nd)), f + " C4 numerator_n / denominator_n")
        put(f"qs.{key}.nns_ci", rng(count(round(1 / hi)), count(round(1 / lo))), f + " C4 reciprocal Wilson bounds")
        if abs(float(c1["recomputed"]) - 100 * x / n) > 1e-3 or abs(float(c4["recomputed"]) - xs / nd) > 0.05:
            raise ValueError(f"{study}: recomputation disagrees with outputs")
    pg2 = one(qs, "PGPH C2", study="PGPH2025", indicator="C2")
    m = re.search(r"(\d+) randomly sampled districts, (\w+)-(\w+) (\d{4})", pg2["setting"])
    put("qs.pgph.districts", m.group(1), "outputs/q2_quality_studies.csv: PGPH2025 setting")
    gha_set = one(qs, "GHA C1", study="GHA2023", indicator="C1")["setting"]
    if "first ACF cycle 2021" not in gha_set:
        raise ValueError("GHA setting is not the first ACF cycle of 2021")

    # ---- Q3 ------------------------------------------------------------------------------------
    q3 = read_csv(root, "outputs/q3_yield_summary.csv")
    for y in ("2018", "2019", "2021", "2022", "2023"):
        yr = one(q3, "yield", state="India", year=y, indicator="yield_diagnosed_per_100000")
        nn = one(q3, "nns", state="India", year=y, indicator="nns")
        f = f"outputs/q3_yield_summary.csv: India {y}"
        put(f"q3.{y}.yield", num(yr["value"], 1), f + " yield value")
        put(f"q3.{y}.yield_ci", rng(num(yr["lower"], 1), num(yr["upper"], 1)), f + " yield lower, upper")
        put(f"q3.{y}.nns", count(round(float(nn["value"]))), f + " nns value")
    sh = one(q3, "share", state="India", year="2021", indicator="acf_share_of_public_sector_notifications_pct")
    put("q3.share", num(sh["value"], 2) + "%", "outputs/q3_yield_summary.csv: India 2021 ACF share value")
    put("q3.share_ci", rng(num(sh["lower"], 2), num(sh["upper"], 2)), "outputs/q3_yield_summary.csv: India 2021 ACF share lower, upper")

    # ---- Q4 ------------------------------------------------------------------------------------
    g = {r["item"]: r["value"] for r in read_csv(root, "data/extracted/guard_result.csv")}
    put("guard.m2023", num(g["median ratio 2023"], 3), "data/extracted/guard_result.csv: median ratio 2023")
    put("guard.m2024", num(g["median ratio 2024"], 3), "data/extracted/guard_result.csv: median ratio 2024")
    if g["n States 2023"] != g["n States 2024"]:
        raise ValueError("guard: different numbers of units in 2023 and 2024")
    put("guard.n", g["n States 2023"], "data/extracted/guard_result.csv: n States 2023 (= 2024)")
    put("guard.out2023", g["States outside [0.95, 1.05] in 2023"],
        "data/extracted/guard_result.csv: States outside [0.95, 1.05] in 2023")
    put("plan.guard_band", plan_has(root, "0.95 to 1.05", "§9.5.2"), "docs/analysis_plan.md §9.5.2")
    put("plan.guard_floor", plan_has(root, "below 0.95", "§9.5.2"), "docs/analysis_plan.md §9.5.2")
    put("plan.draws", count(int(plan_has(root, "10,000", "§10.3").replace(",", ""))), "docs/analysis_plan.md §10.3")
    put("plan.per10", plan_has(root, "per 10 percentage points", "§10.2"), "docs/analysis_plan.md §10.2")
    units = read_csv(root, "data/extracted/exposure_share_reconstructed.csv")
    put("q4.units_total", count(len(units)), "data/extracted/exposure_share_reconstructed.csv: rows")
    for dset in ("D", "R"):
        for an, key in (("primary", "primary"), ("placebo", "placebo"), ("S1 unweighted", "S1"),
                        ("S3 trend 2022-2024", "S3"), ("S4 trend 2019, 2022, 2023", "S4"),
                        ("S5 States only", "S5"), ("S6b capped excluded", "S6b"), ("S8 January-October", "S8")):
            r = q4row(root, dset, an)
            f = f"outputs/q4_summary.csv: {an}, set {dset}"
            p = f"q4.{dset}.{key}"
            put(f"{p}.n", count(r["n"]), f + ", n")
            put(f"{p}.g1", num3(r["gamma1"]), f + ", gamma1")
            put(f"{p}.model", rng(num3(r["gamma1_model_lo"]), num3(r["gamma1_model_hi"])), f + ", gamma1_model_lo/hi")
            put(f"{p}.boot", rng(num3(r["gamma1_boot_lo"]), num3(r["gamma1_boot_hi"])), f + ", gamma1_boot_lo/hi")
        r = q4row(root, dset, "primary")
        f = f"outputs/q4_summary.csv: primary, set {dset}"
        put(f"q4.{dset}.primary.e01", f"{num(r['exp_0_1_gamma1'], 3)} ({rng(num(r['exp_0_1_gamma1_model_lo'], 3), num(r['exp_0_1_gamma1_model_hi'], 3))})",
            f + ", exp_0_1_gamma1 and its model interval")
        put(f"q4.{dset}.primary.g0", f"{num(r['gamma0'], 3)} ({rng(num(r['gamma0_model_lo'], 3), num(r['gamma0_model_hi'], 3))})",
            f + ", gamma0 and its model interval")
        put(f"q4.{dset}.exposure", f"{whole_or(r['exposure_min'], 3)} to {whole_or(r['exposure_max'], 3)} "
            f"(SD {num(r['exposure_sd'], 3)}; weighted mean {num(r['exposure_mean_weighted'], 3)}, "
            f"unweighted mean {num(r['exposure_mean_unweighted'], 3)})",
            f + ", exposure_min, exposure_max, exposure_sd, exposure_mean_weighted, exposure_mean_unweighted")
        put(f"q4.{dset}.primary.eg1", f"{num(r['exp_gamma1'], 3)} ({rng(num(r['exp_gamma1_model_lo'], 3), num(r['exp_gamma1_model_hi'], 3))})",
            f + ", exp_gamma1 and its model interval")
        s2 = q4row(root, dset, "S2 leave one out")
        f2 = f"outputs/q4_summary.csv: S2 leave one out, set {dset}"
        put(f"q4.{dset}.S2.range", rng(num(s2["loo_gamma1_min"], 3), num(s2["loo_gamma1_max"], 3)), f2 + ", loo_gamma1_min/max")
        put(f"q4.{dset}.S2.most", num(s2["loo_most_influential_gamma1"], 3), f2 + ", loo_most_influential_gamma1")
        loo = [r for r in read_csv(root, "outputs/q4_s2_leave_one_out.csv") if r["denominator_set"] == dset]
        lo_r = min(loo, key=lambda r: float(r["gamma1"]))
        hi_r = max(loo, key=lambda r: float(r["gamma1"]))
        fl = f"outputs/q4_s2_leave_one_out.csv: set {dset}"
        put(f"q4.{dset}.S2.min", f"{num(lo_r['gamma1'], 3)} without {lo_r['omitted_unit']}", fl + ", lowest gamma1 and its omitted_unit")
        put(f"q4.{dset}.S2.max", f"{num(hi_r['gamma1'], 3)} without {hi_r['omitted_unit']}", fl + ", highest gamma1 and its omitted_unit")
        put(f"q4.{dset}.S2.changes", f"{signed(lo_r['change_from_full'], 3)} and {signed(hi_r['change_from_full'], 3)}",
            fl + ", change_from_full of the lowest and highest")
        put(f"q4.{dset}.S2.unit", s2["loo_most_influential_unit"], f2 + ", loo_most_influential_unit")
    lak = one(read_csv(root, "outputs/q4_states.csv"), "Lakshadweep", denominator_set="D",
              contrast="full-year 2025 vs 2024", unit="Lakshadweep")
    put("q4.lak", f"exposure {whole_or(lak['E'], 3)}, excess change {num(lak['x'], 2)}",
        "outputs/q4_states.csv: D, full-year, Lakshadweep, E and x")
    mf = (root / "exhibits" / "make_figures.py").read_text(encoding="utf-8")
    m = re.search(r"^YLIM_A = \((-?[\d.]+), (-?[\d.]+)\)", mf, re.M)
    put("fig.ylim", rng(num(m.group(1), 2), num(m.group(2), 2)), "exhibits/make_figures.py: YLIM_A")
    big = fig_value(root, "PIB2335615.p013.s-48-64-lakh-new-tb-cases.tb_cases")
    put("fig.48", big["value_printed"], "data/figures_inventory.csv: PIB2335615 p013 value_printed")
    put("date.pib2335615", day(big["pub_date"]), "data/figures_inventory.csv: PIB2335615 pub_date")
    fig1 = root / V1_EXHIBITS / "figure1_data.csv"
    if fig1.exists() and not any(r["fig_id"] == big["fig_id"] for r in read_csv(root, f"{V1_EXHIBITS}/figure1_data.csv")):
        raise ValueError("Figure 1 does not plot the 48.64 lakh point")

    # ---- software and the AI disclosure --------------------------------------------------------
    env = (root / "ENVIRONMENT.md").read_text(encoding="utf-8")
    put("sw.python", "Python " + re.search(r"Python (\d+\.\d+\.\d+)", env).group(1), "ENVIRONMENT.md")
    put("sw.pdfplumber", "pdfplumber " + re.search(r"pdfplumber (\d+\.\d+\.\d+)", env).group(1), "ENVIRONMENT.md")
    put("ai.model", "Claude Opus 5.5", "fixed: the AI assistant disclosed (model name)")
    return c


@lru_cache(maxsize=8)
def catalogue_cached(root: Path, profile: str = "ext") -> dict[str, tuple[str, str]]:
    return PROFILES[profile].catalogue(root)


# --------------------------------------------------------------------------------------
# Claims stated in words, re-tested on the outputs
# --------------------------------------------------------------------------------------
def claims_v1(root: Path) -> list[str]:
    """Claims of the v1.0.0 audit manuscript."""
    out: list[str] = []

    def need(ok: bool, msg: str) -> None:
        if not ok:
            out.append(f"CLAIM fails: {msg}")

    for dset in ("D", "R"):
        p = q4row(root, dset, "primary")
        need(p["label"] == "no clear association", f"{dset} primary is 'no clear association'")
        need("not separable" in p["label_note"], f"{dset} primary is labelled not separable from the placebo")
        pl = q4row(root, dset, "placebo")
        need(float(pl["gamma1_model_hi"]) < 0, f"{dset} placebo model interval lies below 0 (excludes 0)")
        for r in read_csv(root, "outputs/q4_summary.csv"):
            if r["denominator_set"] == dset and r["status"] == "fitted" and r["analysis"] != "placebo":
                need(r["label"] == "no clear association", f"{dset} {r['analysis']}: no clear association")
        need(q4row(root, dset, "S6a flagged excluded")["status"].startswith("empty"), f"{dset} S6a empty")
        need(q4row(root, dset, "S7 population share")["status"].startswith("not run")
             and "named list" in q4row(root, dset, "S7 population share")["status"], f"{dset} S7 not run (named list)")
        need(q4row(root, dset, "S8(b) with ln r")["status"].startswith("not computable"), f"{dset} S8(b) not computable")
        for f in ("0.98", "0.95"):
            need(q4row(root, dset, f"S8(a) x{f}")["gamma1_invariant"] == "yes", f"{dset} S8(a) x{f} leaves gamma1 unchanged")
    d = q4row(root, "D", "primary")
    need(float(d["gamma1_model_lo"]) > 0 and float(d["gamma1_boot_lo"]) < 0,
         "D primary: model interval excludes 0, bootstrap interval does not")
    need(float(d["gamma0_model_hi"]) < 0, "D primary: the intercept is negative")
    need(d["boot_draws_degenerate"] == "0", "D primary: no degenerate bootstrap draw")
    named_bad = {r["state"] for r in read_csv(root, "data/extracted/named_list_check.csv")
                 if r["match"] == "no" and r["state"] != "TOTAL"}
    loo = read_csv(root, "outputs/q4_s2_leave_one_out.csv")
    infl = {min((r for r in loo if r["denominator_set"] == "D"), key=lambda r: float(r["gamma1"]))["omitted_unit"],
            max((r for r in loo if r["denominator_set"] == "D"), key=lambda r: float(r["gamma1"]))["omitted_unit"],
            q4row(root, "R", "S2 leave one out")["loo_most_influential_unit"]}
    need(len(named_bad) == 4 and infl <= named_bad,
         "the influential units are among the four States where the named list and CTD's table disagree")
    need(float(q4row(root, "D", "S1 unweighted")["gamma1"]) * float(d["gamma1"]) < 0, "S1 reverses the sign (D)")
    for an in ("S4 trend 2019, 2022, 2023", "S5 States only", "S6b capped excluded", "S8 January-October"):
        r = q4row(root, "D", an)
        need(float(r["gamma1_model_lo"]) < 0 < float(r["gamma1_model_hi"]), f"D {an}: model interval includes 0")
    rs2 = q4row(root, "R", "S2 leave one out")
    need(rs2["loo_most_influential_unit"] == "West Bengal" and float(rs2["loo_most_influential_gamma1"]) < 0
         < float(q4row(root, "R", "primary")["gamma1"]), "R S2: leaving out West Bengal reverses the sign")
    g = {r["item"]: r["value"] for r in read_csv(root, "data/extracted/guard_result.csv")}
    need(g["status"] == "pass" and g["primary contrast"] == "full-year 2025 vs 2024", "the guard passed; full year primary")
    e5 = one(read_csv(root, "data/extracted/exposure_checks_reconstructed.csv"), "E5", check="E5")
    need(e5["observed"] == "0 flagged", "no State flagged under E5")
    natd = [r for r in read_csv(root, "data/figures_inventory.csv")
            if r["quantity"] == "districts_selected" and r["geography"] == "India"]
    need({r["value"] for r in natd} == {"347", "455"}
         and len({r["pub_date"] for r in natd if r["value"] == "455"}) == 2
         and len({r["source_file"] for r in natd if r["value"] == "455"}) == 2,
         "national district counts are 347, except 455 in two releases")
    pre = read_csv(root, "outputs/q2_pre_identified_corrected.csv")
    for item in ("LS Q261 2023 against the India TB Report 2024", "Q1216 2023 against the India TB Report 2024"):
        need(one(pre, item, item=item)["n_disagree"] == "0", f"{item}: identical in every State")
    q1 = read_csv(root, "outputs/q1_checks.csv")
    f1 = [r for r in q1 if r["check"].startswith("1") and r["pass"] == "no"]
    need(all("ITR2024.pdf" in r["inputs"] and ".p054." in r["inputs"] and ".p188" in r["inputs"] for r in f1),
         "registered cascade failures set ITR2024 ACF figures against another table of the same report")
    f3 = [r for r in q1 if r["check"].startswith("3") and r["pass"] == "no"]
    need(sorted({("ITR2023" if "ITR2023" in r["inputs"] else "PGPH" if "PGPH2025" in r["inputs"] else "?") for r in f3})
         == ["ITR2023", "PGPH"], "the sum-check failures come from two sources")
    c4 = one(q1, "check 4", check="4 cumulative series never decreases")
    need(c4["pass"] == "n/a" and "no cumulative figure" in c4["note"], "check 4 had no input")
    need(summary_metric(root, "Q1 check 1 cascade does not grow: fail", "corrected") == "0", "corrected cascade: no failure")
    rows = disc_rows(root)
    c2 = [r for r in rows if r["class"] == "2"]
    need(all({r["a_definition_class"], r["b_definition_class"]} == {"notified", "diagnosed"} for r in c2),
         "every class 2 pair is notified against diagnosed")
    c1 = [r for r in rows if r["class"] == "1"]
    need(all(r["quantity"] == "screened" and r["geography"] == "India" for r in c1), "class 1 pairs: national screened")
    q3 = read_csv(root, "outputs/q3_yield.csv")
    for y in ("2020", "2024"):
        need(any(r["year"] == y and r["status"] == "not_available" for r in q3), f"no table for {y}")
    ys = {y: float(one(read_csv(root, "outputs/q3_yield_summary.csv"), "y", state="India", year=y,
                       indicator="yield_diagnosed_per_100000")["value"]) for y in ("2021", "2022", "2023")}
    need(ys["2021"] > ys["2022"] > ys["2023"], "national yield fell from 2021 to 2023")
    allys = [float(r["value"]) for r in read_csv(root, "outputs/q3_yield_summary.csv")
             if r["state"] == "India" and r["indicator"] == "yield_diagnosed_per_100000"]
    need(max(allys) == ys["2021"], "national yield peaked in 2021")
    sh = one(read_csv(root, "outputs/q3_yield_summary.csv"), "share", state="India", year="2021",
             indicator="acf_share_of_public_sector_notifications_pct")
    need(sh["chosen_source"] == "GHA2023-S2", "the ACF share comes from the 2023 study's supplement")
    return out

# --------------------------------------------------------------------------------------
# The extension paper (profile "ext"): catalogue from outputs/ext/ (and outputs/ for the box and
# the national yield), the extension plan and both registration records
# --------------------------------------------------------------------------------------
def ext_csv(root: Path, name: str) -> list[dict]:
    return read_csv(root, f"outputs/ext/{name}.csv")


def ext_plan_text(root: Path) -> str:
    return (root / "docs" / "extension_plan.md").read_text(encoding="utf-8")


def ext_plan_has(root: Path, s: str, where: str) -> str:
    """s, after confirming the registered extension plan states it."""
    if s not in re.sub(r"\s+", " ", ext_plan_text(root)):
        raise ValueError(f"the extension plan ({where}) does not state {s!r}")
    return s


def and_list(items: list[str]) -> str:
    """'A, B and C'."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def pct(x: float | str, dp: int = 1) -> str:
    return num(100 * float(x), dp) + "%"


def ext_rho_weights(root: Path) -> dict[str, float]:
    """The main correlation's weights: 2023 screened (data/ext/panel.csv) of the units in the main
    correlation sample (outputs/ext/d2_alignment.csv main row: n units, listed units left out)."""
    main = one(ext_csv(root, "d2_alignment"), "rho main", analysis="main")
    left = {x.split(" (")[0] for x in main["listed"].split(";") if x}
    w = {r["unit"]: float(r["screened"]) for r in read_csv(root, "data/ext/panel.csv")
         if r["year"] == "2023" and r["screened"] and r["unit"] not in left}
    if len(w) != int(main["n"]):
        raise ValueError(f"rho weights: {len(w)} units, the main row has n = {main['n']}")
    return w


def catalogue_ext(root: Path) -> dict[str, tuple[str, str]]:
    """The extension paper's catalogue: label -> (text as printed, source)."""
    c: dict[str, tuple[str, str]] = {}

    def put(label: str, text: str, source: str) -> None:
        if label in c:
            raise ValueError(f"duplicate catalogue label {label}")
        c[label] = (text, source)

    # ---- registration (both pushes) and the campaign ---------------------------------------
    reg = json.loads((root / "docs" / "registration_event.json").read_text(encoding="utf-8"))
    put("date.registration", day(reg["pushed_at"]), "docs/registration_event.json: pushed_at")
    put("reg.time", reg["pushed_at"][11:16] + " UTC", "docs/registration_event.json: pushed_at")
    ext = json.loads((root / "docs" / "registration_event_ext.json").read_text(encoding="utf-8"))
    put("date.registration_ext", day(ext["pushed_at"]), "docs/registration_event_ext.json: pushed_at")
    put("reg_ext.time", ext["pushed_at"][11:16] + " UTC", "docs/registration_event_ext.json: pushed_at")
    put("date.campaign_start", plan_has(root, "7 December 2024", "§1.1"), "docs/analysis_plan.md §1.1")
    e7 = one(read_csv(root, "data/extracted/exposure_checks_reconstructed.csv"), "E7", check="E7")
    m = re.fullmatch(r"(\d+) districts; (\d+) States/UTs", e7["observed"])
    put("exp.districts", m.group(1), "data/extracted/exposure_checks_reconstructed.csv: E7 observed")
    put("exp.states", m.group(2), "data/extracted/exposure_checks_reconstructed.csv: E7 observed")

    # ---- panel units -------------------------------------------------------------------------
    panel = read_csv(root, "data/ext/panel.csv")
    per_year = {y: len({r["unit"] for r in panel if r["year"] == y}) for y in ("2018", "2019", "2021", "2022", "2023")}
    if per_year["2018"] != per_year["2019"] or len({per_year[y] for y in ("2021", "2022", "2023")}) != 1:
        raise ValueError(f"panel units per year: {per_year}")
    put("panel.units_early", count(per_year["2018"]), "data/ext/panel.csv: units in 2018 (= 2019)")
    put("panel.units_late", count(per_year["2021"]), "data/ext/panel.csv: units in 2021 (= 2022 = 2023)")

    # ---- plan constants ----------------------------------------------------------------------
    put("plan.draws", count(int(ext_plan_has(root, "10,000 draws", "§4.3").split()[0].replace(",", ""))),
        "docs/extension_plan.md §4.3")
    put("plan.agree", ext_plan_has(root, "at least 80%", "§8").split()[-1], "docs/extension_plan.md §8")
    put("plan.sd_ratio", ext_plan_has(root, "a median of about 20 times", "§10"),
        "docs/extension_plan.md §10 (19 November 2026, post hoc tier sensitivity)")
    ext_plan_has(root, "θ = 1 would correspond to full addition and θ = 0 to full substitution", "§6")
    put("plan.theta_refs", "0 and 1", "docs/extension_plan.md §6 (θ = 1 full addition, θ = 0 full substitution)")

    # ---- pooled yield (D1) and the national yield --------------------------------------------
    pooled = ext_csv(root, "d1_pooled")
    for a in ("2018", "2019", "2021", "2022", "2023", "2021-2023"):
        r = one(pooled, "d1_pooled", analysis=a)
        f = f"outputs/ext/d1_pooled.csv: {a}"
        put(f"pool.{a}.yield", num(r["yield_per_100k"], 1), f + ", yield_per_100k")
        put(f"pool.{a}.ci", rng(num(r["ci_lo_per_100k"], 1), num(r["ci_hi_per_100k"], 1)), f + ", ci_*_per_100k")
        put(f"pool.{a}.pi", rng(num(r["pi_lo_per_100k"], 1), num(r["pi_hi_per_100k"], 1)), f + ", pi_*_per_100k")
        put(f"pool.{a}.k", count(r["k"]), f + ", k")
        for t in ("above", "overlaps", "below"):
            put(f"pool.{a}.{t}", count(r[f"n_{t}"]), f + f", n_{t}")
    by = one(ext_csv(root, "d1_pooled_betweenyear"), "between-year", analysis="2021-2023 between-year (post hoc)")
    f = "outputs/ext/d1_pooled_betweenyear.csv"
    put("by.agree", count(by["n_tier_agrees"]), f + ": n_tier_agrees")
    put("by.k", count(by["k"]), f + ": k")
    for t in ("above", "overlaps", "below"):
        put(f"by.robust_{t}", count(by[f"robust_{t}"]), f + f": robust_{t}")
    bys = ext_csv(root, "d1_states_betweenyear")
    for t in ("above", "below"):
        names = sorted(r["unit"] for r in bys if r["tier_registered"] == t and r["tier_agrees"] == "yes")
        if len(names) != int(by[f"robust_{t}"]):
            raise ValueError(f"robust {t}: {len(names)} names, {by[f'robust_{t}']} counted")
        put(f"by.names_{t}", and_list(names),
            f"outputs/ext/d1_states_betweenyear.csv: units with tier_registered {t} and tier_agrees yes")
    q3 = read_csv(root, "outputs/q3_yield_summary.csv")
    for y in ("2018", "2021", "2023"):
        yr = one(q3, "yield", state="India", year=y, indicator="yield_diagnosed_per_100000")
        f = f"outputs/q3_yield_summary.csv: India {y}"
        put(f"q3.{y}.yield", num(yr["value"], 1), f + " yield value")
        put(f"q3.{y}.yield_ci", rng(num(yr["lower"], 1), num(yr["upper"], 1)), f + " yield lower, upper")

    # ---- elasticity --------------------------------------------------------------------------
    el = ext_csv(root, "d1_elasticity")
    for a, key in (("main", "main"), ("poisson", "poisson"), ("stratum high", "high"), ("stratum low", "low")):
        r = one(el, "d1_elasticity", analysis=a)
        f = f"outputs/ext/d1_elasticity.csv: {a}"
        put(f"eps.{key}.est", num(r["estimate"], 2), f + ", estimate")
        put(f"eps.{key}.boot", rng(num(r["boot_lo"], 2), num(r["boot_hi"], 2)), f + ", boot_lo/hi")
        put(f"eps.{key}.model", rng(num(r["model_ci_lo"], 2), num(r["model_ci_hi"], 2)), f + ", model_ci_lo/hi")
        put(f"eps.{key}.units", count(r["n_units"]), f + ", n_units")
        put(f"eps.{key}.obs", count(r["n_obs"]), f + ", n_obs")
    r = one(ext_csv(root, "d1_elasticity_samedef"), "d1_elasticity_samedef",
            analysis="same screened definition (post hoc)")
    f = "outputs/ext/d1_elasticity_samedef.csv: same screened definition (post hoc)"
    put("eps.samedef.est", num(r["estimate"], 2), f + ", estimate")
    put("eps.samedef.boot", rng(num(r["boot_lo"], 2), num(r["boot_hi"], 2)), f + ", boot_lo/hi")
    put("eps.samedef.model", rng(num(r["model_ci_lo"], 2), num(r["model_ci_hi"], 2)), f + ", model_ci_lo/hi")
    put("eps.samedef.units", count(r["n_units"]), f + ", n_units")
    put("eps.samedef.obs", count(r["n_obs"]), f + ", n_obs")
    ins = ext_csv(root, "d1_intensity_strata")
    put("int.switched", count(sum(r["stratum"] != r["stratum_registered_rule"] for r in ins)),
        "outputs/ext/d1_intensity_strata.csv: stratum differs from stratum_registered_rule")
    put("int.n", count(len(ins)), "outputs/ext/d1_intensity_strata.csv: rows")

    # ---- decomposition -----------------------------------------------------------------------
    dec = ext_csv(root, "d1_decomposition")
    for q, key in (("dln_yield", "dln"), ("testing_part", "testing"), ("positivity_part", "positivity")):
        r = one(dec, "decomposition", analysis="change", status="main", quantity=q)
        f = f"outputs/ext/d1_decomposition.csv: change, main, {q}"
        put(f"dec.{key}.est", num(r["estimate"], 2), f + ", estimate")
        put(f"dec.{key}.ci", rng(num(r["boot_lo"], 2), num(r["boot_hi"], 2)), f + ", boot_lo/hi")
        put("dec.n" if key == "dln" else f"dec.{key}.n", count(r["n_units"]), f + ", n_units")
    for y in ("2018", "2023"):
        r = one(dec, "share", analysis="variance", status="main", years=y, quantity="testing_share")
        f = f"outputs/ext/d1_decomposition.csv: variance, {y}, testing_share"
        put(f"dec.share.{y}", f"{num(r['estimate'], 2)} ({rng(num(r['boot_lo'], 2), num(r['boot_hi'], 2))})",
            f + ", estimate and boot_lo/hi")

    # ---- headline: grids, labels, leave one out ----------------------------------------------
    hl = {r["estimate"]: r for r in ext_csv(root, "headline")}
    f = "outputs/ext/headline.csv"
    for e in ("epsilon", "rho", "theta"):
        r = hl[e]
        put(f"hl.{e}.agree", f"{count(r['n_agree'])} of {count(r['n_entries'])}", f + f": {e} n_agree, n_entries")
        put(f"hl.{e}.excl", count(r["n_agree_and_interval_excludes"]), f + f": {e} n_agree_and_interval_excludes")
    if hl["epsilon"]["n_entries"] != hl["rho"]["n_entries"] or hl["rho"]["null"] != hl["theta"]["null"]:
        raise ValueError("headline: the ε and ρ grids differ in size, or the ρ and θ nulls differ")
    put("hl.grids", f"{count(hl['epsilon']['n_entries'])} entries for ε and ρ, {count(hl['theta']['n_entries'])} for θ",
        f + ": n_entries")
    put("hl.nulls", f"{whole_or(hl['epsilon']['null'], 2)} for ε, {whole_or(hl['rho']['null'], 2)} for ρ and θ",
        f + ": null")
    r = hl["epsilon"]
    put("hl.epsilon.loo", f"{num(r['loo_state_min'], 2)} ({r['loo_state_min_omitted']}) to "
                          f"{num(r['loo_state_max'], 2)} ({r['loo_state_max_omitted']})",
        f + ": epsilon loo_state_min/max and omitted")
    put("hl.epsilon.loo_years", f"{num(r['loo_year_min'], 2)} ({r['loo_year_min_omitted']}) to "
                                f"{num(r['loo_year_max'], 2)} ({r['loo_year_max_omitted']})",
        f + ": epsilon loo_year_min/max and omitted")
    put("hl.rho.loo_max", num(hl["rho"]["loo_state_max"], 2), f + ": rho loo_state_max")
    put("hl.theta.loo_state", num(hl["theta"]["loo_state_max"], 2), f + ": theta loo_state_max")
    put("hl.theta.loo_year", num(hl["theta"]["loo_year_max"], 2), f + ": theta loo_year_max")

    # ---- targeting ---------------------------------------------------------------------------
    al = ext_csv(root, "d2_alignment")
    for a, key in (("main", "main"), ("unweighted", "unw")):
        r = one(al, "d2_alignment", analysis=a)
        f = f"outputs/ext/d2_alignment.csv: {a}"
        put(f"rho.{key}.est", num(r["estimate"], 2), f + ", estimate")
        put(f"rho.{key}.boot", rng(num(r["boot_lo"], 2), num(r["boot_hi"], 2)), f + ", boot_lo/hi")
        put(f"rho.{key}.n", count(r["n"]), f + ", n")
    w = ext_rho_weights(root)
    tot = sum(w.values())
    top2 = sorted(w, key=lambda u: -w[u])[:2]
    put("rho.top2_share", f"{round(100 * (w[top2[0]] + w[top2[1]]) / tot)}%",
        "data/ext/panel.csv: 2023 screened of the two heaviest units over the main correlation sample")
    kish = tot * tot / sum(v * v for v in w.values())
    if abs(kish - round(kish)) > 0.1:
        raise ValueError(f"effective number of States {kish:.3f} is not about a whole number")
    put("rho.kish", count(round(kish)), "data/ext/panel.csv: (Σw)²/Σw² of the main correlation weights")
    ts = ext_csv(root, "d2_tier_shares")
    for t in ("above", "overlaps", "below"):
        r = one(ts, "tier share", classification="registered pooled 2021-2023", tier=t)
        put(f"tier.{t}.pct", pct(r["share"]), f"outputs/ext/d2_tier_shares.csv: registered, {t}, share")
    put("tier.total", count(r["total_campaign_districts"]), "outputs/ext/d2_tier_shares.csv: total_campaign_districts")
    sc = ext_csv(root, "d2_scenario")
    r = one(sc, "scenario", analysis="main")
    f = "outputs/ext/d2_scenario.csv: main"
    put("sc.share", f"{100 * float(r['share']):g}%", f + ", share")
    put("sc.gainers", count(r["n_gainers"]), f + ", n_gainers")
    put("sc.losers", count(r["n_losers"]), f + ", n_losers")
    put("sc.n_states", count(int(r["n_gainers"]) + int(r["n_losers"])), f + ", n_gainers + n_losers")
    put("sc.r_gain", pct(r["r_gain"]), f + ", r_gain")
    put("sc.delta", count(round(float(r["delta"]))), f + ", delta")
    put("sc.ci", rng(count(round(float(r["ci_lo"]))), count(round(float(r["ci_hi"])))), f + ", ci_lo/hi")
    put("sc.pct", num(r["pct"], 1) + "%", f + ", pct")
    units = ext_csv(root, "d2_scenario_units")
    mh = one(units, "Maharashtra", analysis="main", unit="Maharashtra")
    put("sc.mh_moved", f"{round(100 * float(r['share']) * float(mh['screened_2023']) / float(r['moved']))}%",
        "outputs/ext/d2_scenario_units.csv (Maharashtra screened_2023 × share) ÷ d2_scenario.csv moved")
    r = one(sc, "scenario", analysis="robust tiers (post hoc)")
    f = "outputs/ext/d2_scenario.csv: robust tiers (post hoc)"
    put("sc.robust.delta", count(round(float(r["delta"]))), f + ", delta")
    put("sc.robust.ci", rng(count(round(float(r["ci_lo"]))), count(round(float(r["ci_hi"])))), f + ", ci_lo/hi")
    r = one(sc, "scenario", analysis="stratum elasticity")
    f = "outputs/ext/d2_scenario.csv: stratum elasticity"
    put("sc.stratum.delta", count(round(float(r["delta"]))), f + ", delta")
    put("sc.stratum.ci", rng(count(round(float(r["ci_lo"]))), count(round(float(r["ci_hi"])))), f + ", ci_lo/hi")

    # ---- notifications -----------------------------------------------------------------------
    d3 = ext_csv(root, "d3")
    for key, kv, dp in (("main", dict(analysis="main"), 2),
                        ("log", dict(outcome="public", scale="log", weights="inverse_poisson", units="all"), 3),
                        ("total", dict(outcome="total", scale="absolute", weights="inverse_poisson", units="all"), 2)):
        hits = [x for x in d3 if all(x[k] == v for k, v in kv.items()) and (key == "main" or x["role"] != "main")]
        if len(hits) != 1:
            raise ValueError(f"d3 {key}: {len(hits)} rows")
        r = hits[0]
        f = f"outputs/ext/d3.csv: {key}"
        put(f"theta.{key}.est", num3(r["estimate"]) if dp == 3 else num(r["estimate"], 2), f + ", estimate")
        put(f"theta.{key}.boot", rng(num3(r["boot_lo"]), num3(r["boot_hi"])) if dp == 3
            else rng(num(r["boot_lo"], 2), num(r["boot_hi"], 2)), f + ", boot_lo/hi")
        if key == "main":
            put("theta.main.units", count(r["n_units"]), f + ", n_units")
            put("theta.main.obs", count(r["n_obs"]), f + ", n_obs")

    # ---- descriptive cross-check -------------------------------------------------------------
    cc = read_csv(root, "outputs/ext/crosscheck.csv")
    r = one(cc, "positivity 2023", section="national cascade", quantity="pct_diagnosed_of_tested", panel_year="2023")
    put("cc.pos_panel", num(r["panel_value"], 2) + "%", "outputs/ext/crosscheck.csv: national 2023 pct_diagnosed_of_tested, panel_value")
    put("cc.pos_study", num(r["study_value"], 2) + "%", "outputs/ext/crosscheck.csv: national 2023 pct_diagnosed_of_tested, study_value")
    pg2 = one(read_csv(root, "outputs/q2_quality_studies.csv"), "PGPH C2", study="PGPH2025", indicator="C2")
    put("cc.districts", re.search(r"(\d+) randomly sampled districts", pg2["setting"]).group(1),
        "outputs/q2_quality_studies.csv: PGPH2025 setting")

    # ---- the box (v1.0.0 consistency checks) -------------------------------------------------
    s = "outputs/q2_summary_registered_vs_corrected.csv: "
    put("box.totals_pass", count(summary_metric(root, "Q1 check 3 total equals the sum of its parts: pass", "registered")),
        s + "Q1 check 3 pass (registered)")
    n3 = sum(int(summary_metric(root, f"Q1 check 3 total equals the sum of its parts: {k}", "registered"))
             for k in ("pass", "fail", "n/a"))
    put("box.totals_n", count(n3), s + "Q1 check 3 pass+fail+n/a (registered)")
    put("box.cascade_reg_pass", count(summary_metric(root, "Q1 check 1 cascade does not grow: pass", "registered")),
        s + "Q1 check 1 pass (registered)")
    put("box.cascade_reg_n", count(sum(int(summary_metric(root, f"Q1 check 1 cascade does not grow: {k}", "registered"))
                                   for k in ("pass", "fail", "n/a"))),
        s + "Q1 check 1 pass+fail+n/a (registered)")
    put("box.cascade_pass", count(summary_metric(root, "Q1 check 1 cascade does not grow: pass", "corrected")),
        s + "Q1 check 1 pass (corrected)")
    for st in ("corrected", "registered"):
        put(f"box.{st[:3]}.c4", count(summary_metric(root, "Q2 pre-specified: class 4", st)),
            s + f"Q2 pre-specified: class 4, {st}")
        put(f"box.{st[:3]}.pairs", count(summary_metric(root, "Q2 entry pairs (pre-specified)", st)),
            s + f"Q2 entry pairs (pre-specified), {st}")

    # ---- software and the AI disclosure ------------------------------------------------------
    env = (root / "ENVIRONMENT.md").read_text(encoding="utf-8")
    for pkg in ("Python", "numpy", "scipy", "matplotlib"):
        put(f"sw.{pkg.lower()}", f"{pkg} " + re.search(rf"{pkg} (\d+\.\d+\.\d+)", env).group(1), "ENVIRONMENT.md")
    put("ai.model", "Claude Opus 5.5", "fixed: the AI assistant disclosed (model name)")
    return c


def claims_ext(root: Path) -> list[str]:
    """Statements the extension paper makes in words, re-tested on the outputs."""
    out: list[str] = []

    def need(ok: bool, msg: str) -> None:
        if not ok:
            out.append(f"CLAIM fails: {msg}")

    hl = {r["estimate"]: r for r in ext_csv(root, "headline")}
    need(hl["epsilon"]["label"] == "supported", "ε is supported")
    need(hl["rho"]["label"] == "not established", "ρ is not established")
    need(hl["theta"]["label"] == "not established", "θ is not established")
    el = one(ext_csv(root, "d1_elasticity"), "main", analysis="main")
    need(float(el["boot_hi"]) < 1 and float(el["model_ci_hi"]) < 1, "both ε intervals exclude 1 (lie below it)")
    grid = ext_csv(root, "spec_curve")
    eg = [r for r in grid if r["estimate"] == "epsilon"]
    need(all(r["value"] and float(r["value"]) < 1 and float(r["ci_hi"]) < 1 for r in eg),
         "every ε grid entry and its interval lie below 1")
    need(hl["epsilon"]["n_agree_and_interval_excludes"] == hl["epsilon"]["n_agree"],
         "every agreeing ε entry has an interval excluding the null")
    need(hl["rho"]["n_agree_and_interval_excludes"] == "0" and hl["theta"]["n_agree_and_interval_excludes"] == "0",
         "no ρ or θ entry has an interval excluding the null")
    need(sum(float(r["value"]) < 0 for r in grid if r["estimate"] == "theta") == 12,
         "twelve θ entries are negative")
    rho = hl["rho"]
    need(float(rho["ci_lo"]) < 0 < float(rho["ci_hi"]), "the ρ interval includes 0")
    need(rho["loo_state_max_omitted"] == "Maharashtra" and rho["loo_state_most_influential"] == "Maharashtra",
         "leaving out Maharashtra moves ρ most")
    th = hl["theta"]
    need(float(th["ci_lo"]) < 0 and float(th["ci_hi"]) > 1, "the θ interval includes both 0 and 1")
    need(float(th["main_value"]) < 0 < float(th["loo_state_max"]) and th["loo_state_max_omitted"] == "Uttar Pradesh",
         "θ changes sign without Uttar Pradesh")
    need(float(th["loo_year_max"]) > 0 and th["loo_year_max_omitted"] == "2019", "θ changes sign without 2019")
    tg = [r for r in grid if r["estimate"] == "theta"]
    pos = [r for r in tg if float(r["value"]) > 0]
    need(len(pos) == 4 and all(r["scale"] == "log" and r["weights"] == "inverse_poisson" for r in pos),
         "the positive θ entries are the four weighted log-scale entries")
    dec = ext_csv(root, "d1_decomposition")

    def ch(q: str) -> dict:
        return one(dec, q, analysis="change", status="main", quantity=q)
    need(float(ch("dln_yield")["boot_lo"]) < 0 < float(ch("dln_yield")["boot_hi"]), "the fall in log yield is imprecise (CI includes 0)")
    need(float(ch("positivity_part")["boot_hi"]) < 0, "the positivity step fell (CI below 0)")
    need(float(ch("testing_part")["boot_lo"]) < 0 < float(ch("testing_part")["boot_hi"]), "the testing step is imprecise (CI includes 0)")
    ts = ext_csv(root, "d2_tier_shares")
    sh = {r["tier"]: float(r["share"]) for r in ts if r["classification"] == "registered pooled 2021-2023"}
    need(sh["above"] < sh["below"], "fewer campaign districts in above-tier than in below-tier States")
    w = ext_rho_weights(root)
    need(set(sorted(w, key=lambda u: -w[u])[:2]) == {"Maharashtra", "Uttar Pradesh"},
         "Maharashtra and Uttar Pradesh carry the most weight")
    bys = {r["unit"]: r for r in ext_csv(root, "d1_states_betweenyear")}
    need(bys["Maharashtra"]["tier_registered"] == "below" and bys["Maharashtra"]["tier_agrees"] == "no",
         "Maharashtra's below tier is not robust")
    units = [r for r in ext_csv(root, "d2_scenario_units") if r["analysis"] == "main"]
    need(max(units, key=lambda r: float(r["screened_2023"]))["unit"] == "Maharashtra"
         and one(units, "MH", unit="Maharashtra")["side"] == "loses", "Maharashtra supplies most of the moved volume")
    st = {r["unit"]: r for r in ext_csv(root, "d1_states") if r["analysis"] == "2021-2023"}
    need(st["Delhi"]["rank_hi"] == "1" and st["Delhi"]["tier"] == "above" and bys["Delhi"]["tier"] == "overlaps",
         "Delhi ranks first under the registered analysis and overlaps the mean between years")
    need("Lakshadweep" not in st, "Lakshadweep has no pooled value")
    pooled = {r["analysis"]: float(r["yield_per_100k"]) for r in ext_csv(root, "d1_pooled")}
    need(pooled["2018"] > pooled["2023"], "the pooled yield fell from 2018 to 2023")
    q3 = read_csv(root, "outputs/q3_yield_summary.csv")
    ys = {y: float(one(q3, "y", state="India", year=y, indicator="yield_diagnosed_per_100000")["value"])
          for y in ("2021", "2023")}
    need(ys["2021"] > ys["2023"], "the national yield fell from 2021 to 2023")
    return out

# --------------------------------------------------------------------------------------
# Section phrases: private, read at run time from <manuscript folder>/section_phrases.json
# --------------------------------------------------------------------------------------
def load_phrase_file(ms_dir: Path) -> dict:
    """The private phrases file of a manuscript folder (git-ignored, like the manuscript).

    {"sections": {section: [phrase with {label} placeholders, ...]}, "mutation_anchors": {...}}.
    The phrases quote the manuscript, so they are kept with it and never committed."""
    p = ms_dir / PHRASES
    d = json.loads(p.read_text(encoding="utf-8"))
    secs = d.get("sections") if isinstance(d, dict) else None
    if not isinstance(secs, dict) or not secs or not all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
            for k, v in secs.items()):
        raise ValueError(f"{PHRASES}: 'sections' must map section names to lists of phrases")
    return d


def section_phrases(ms_dir: Path) -> dict[str, list[str]]:
    return load_phrase_file(ms_dir)["sections"]


# --------------------------------------------------------------------------------------
# Fixed (non-result) number patterns: each token they cover gets the pattern's label
# --------------------------------------------------------------------------------------
SUPPLEMENT_V1 = ["S1", "S2", "S3", "S4"]  # supplementary tables, in order of first citation
SUPP_DATA_V1 = ["S1a", "S1b"]  # supplementary data files (CSV and XLSX); each must be cited
FIXED_V1: list[tuple[str, str]] = [
    ("reference", r"\^[\d,–]+\^"),
    ("exhibit", r"\bTables? S\d[ab]?(?: and S\d[ab]?)?"),
    ("exhibit", r"\bSupplementary data S\d[ab](?: and S\d[ab])?"),
    ("exhibit", r"\b(?:Table|Figure)s? [1-3][AB]?\b(?:, footnote [a-z])?"),
    ("question", r"\bQ[1-4]\b"),
    ("analysis", r"\bS[1-8](?:[ab]\b|\([ab]\))?"),
    ("parameter", r"exp\(0\.1γ1\)|γ[01]"),
    ("class", r"\((?:[1-4]|3[ab])\)|\b[Cc]lass [1-4]\b"),
    ("ci_level", r"\b95% (?:CI|interval)"),
    ("campaign", r"\b100[- ]days?\b"),
    ("yield_scale", r"per 100,000 screened|\b100,000 × diagnosed"),
    ("threshold", r"\b(?:exclude[sd]?|including|side of) 0\b|\bcapped at 1\b"),
    ("per10", r"\bPer 10 percentage points\b|\bper 10 percentage points\b"),
    ("date", r"\b\d{1,2} (?:" + "|".join(MONTHS) + r") 20\d\d\b"),
    ("year", r"(?<![\d.,])20(?:1[89]|2[0-6])(?![\d]|[.,]\d)"),
]
NUMBER = re.compile(r"\d+(?:,\d{3}(?!\d))*(?:\.\d+)?")
PHRASE_LITERAL_OK = re.compile(r"^(?:\d+)$")

SUPPLEMENT_EXT = [f"S{k}" for k in range(1, 9)]  # the extension paper: Tables S1-S8, no data files
FIXED_EXT: list[tuple[str, str]] = [
    ("reference", r"\^[\d,–]+\^"),
    ("exhibit", r"\bTables? S\d\b"),
    ("exhibit", r"\b(?:Table|Figure)s? [1-4][A-D]?\b"),
    ("exhibit", r"\bBox 1\b"),
    ("ci_level", r"\b95%"),
    ("campaign", r"\b100[- ]day\b|\bphase[- ]1\b"),
    ("yield_scale", r"per 100,000(?: people)? screened"),
    ("unit_change", r"\b(?:each|a) 1% "),
    ("null", r"ε < 1\b|θ = [01]\b|\b(?:exclude[sd]?|excluding|including|includes|below|exceed|side of|towards) [01]\b"
             r"|\bby 0 and 1\b"),
    ("date", r"\b\d{1,2} (?:" + "|".join(MONTHS) + r") 20\d\d\b"),
    ("year", r"(?<![\d.,])20(?:1[89]|2[0-6])(?![\d]|[.,]\d)"),
]


class Profile(NamedTuple):
    """What a manuscript of one framing must contain: its catalogue, its claims, its fixed number
    patterns, and its exhibits (main tables and figures, supplementary tables and data files)."""
    catalogue: Callable[[Path], dict]
    claims: Callable[[Path], list]
    fixed: list
    tables: list
    figures: list
    supplement: list
    supp_data: list


PROFILES: dict[str, Profile] = {
    "v1": Profile(catalogue_v1, claims_v1, FIXED_V1, [1, 2, 3], [1, 2], SUPPLEMENT_V1, SUPP_DATA_V1),
    "ext": Profile(catalogue_ext, claims_ext, FIXED_EXT, [1], [1, 2, 3, 4], SUPPLEMENT_EXT, []),
}
DEFAULT_PROFILE = "ext"


def profile_for(ms_dir: Path) -> str:
    """The profile of a manuscript folder: the "profile" key of its section_phrases.json if it has
    one; otherwise "v1" for a folder named v1_audit and "ext" for any other."""
    p = ms_dir / PHRASES
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            d = {}
        if isinstance(d, dict) and d.get("profile") in PROFILES:
            return d["profile"]
    return "v1" if ms_dir.name == "v1_audit" else DEFAULT_PROFILE


def sections(text: str) -> dict[str, str]:
    """Heading -> whitespace-collapsed text, for the title and every '## ' section but References."""
    out: dict[str, list[str]] = {}
    cur = None
    for ln in text.splitlines():
        if ln.startswith("# ") and not out:
            out["Title"] = [ln[2:]]
            cur = None
        elif ln.startswith("## "):
            cur = ln[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    return {k: re.sub(r"\s+", " ", "\n".join(v)).strip() for k, v in out.items() if k != "References"}


def fill(template: str, cat: dict) -> tuple[str, list[tuple[int, int, str]]]:
    """The filled phrase, and (start, end, label) of each placeholder in it."""
    out, spans, pos = "", [], 0
    for m in re.finditer(r"\{([^}]+)\}", template):
        out += template[pos:m.start()]
        val = cat[m.group(1)][0]
        spans.append((len(out), len(out) + len(val), m.group(1)))
        out += val
        pos = m.end()
    return out + template[pos:], spans


def _occurrences(body: str, phrase: str) -> list[int]:
    pat = re.compile(r"(?<![\d.,−-])" + re.escape(phrase) + r"(?![\d]|[.,]\d)")
    return [m.start() for m in pat.finditer(body)]


def date_labels(cat: dict) -> dict[str, str]:
    return {v[0]: k for k, v in cat.items() if k.startswith("date.")}


def assign(name: str, body: str, cat: dict, required: list[str],
           fixed: list[tuple[str, str]]) -> tuple[list[dict], list[str]]:
    """Label every number token of one section; return (skeleton entries, problems)."""
    probs: list[str] = []
    labels: dict[int, tuple[str, str]] = {}  # token start -> (label, source)
    toks = [(m.start(), m.end(), m.group()) for m in NUMBER.finditer(body)]
    # 1) phrases
    for tpl in required:
        phrase, spans = fill(tpl, cat)
        occ = _occurrences(body, phrase)
        if not occ:
            probs.append(f"MISSING in {name}: {phrase!r}")
            continue
        for at in occ:
            for s, e, t in toks:
                for ps, pe, lab in spans:
                    if at + ps <= s and e <= at + pe and s not in labels:
                        labels[s] = (lab, cat[lab][1])
    # 2) fixed patterns
    dates = date_labels(cat)
    for kind, pat in fixed:
        for m in re.finditer(pat, body):
            for s, e, t in toks:
                if m.start() <= s and e <= m.end() and s not in labels:
                    if kind == "date":
                        lab = dates.get(m.group())
                        if lab is None:
                            probs.append(f"DATE in {name} is not a catalogue date: {m.group()!r}")
                            continue
                        labels[s] = (lab, cat[lab][1])
                    else:
                        labels[s] = (f"fixed:{kind}", f"fixed {kind}: {m.group()}")
    entries = []
    for s, e, t in toks:
        if s not in labels:
            ctx = body[max(0, s - 40):e + 20]
            probs.append(f"UNACCOUNTED number in {name}: {t!r} in ...{ctx}...")
            entries.append({"token": t, "label": "UNACCOUNTED", "source": ""})
        else:
            entries.append({"token": t, "label": labels[s][0], "source": labels[s][1]})
    return entries, probs


def skeleton(text: str, root: Path, required: dict[str, list[str]],
             profile: str = "ext") -> tuple[dict[str, list[dict]], list[str]]:
    cat = catalogue_cached(root, profile)
    secs = sections(text)
    out, probs = {}, []
    for name in required:
        if name not in secs:
            probs.append(f"MISSING section {name!r}")
    for name, body in secs.items():
        entries, p = assign(name, body, cat, required.get(name, []), PROFILES[profile].fixed)
        out[name] = entries
        probs += p
    return out, probs


def skeleton_problems(now: dict[str, list[dict]], gold: dict[str, list[dict]] | None, root: Path,
                      profile: str = "ext") -> list[str]:
    if gold is None:
        return [f"{SKELETON} missing: after review run python -I verification/check_manuscript_numbers.py --regenerate"]
    cat = catalogue_cached(root, profile)
    out = []
    for name in sorted(set(now) | set(gold)):
        a = [(x["token"], x["label"]) for x in gold.get(name, [])]
        b = [(x["token"], x["label"]) for x in now.get(name, [])]
        if a != b:
            k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            out.append(f"SKELETON {name}: entry {k + 1} is {b[k] if k < len(b) else '(none)'}, golden has "
                       f"{a[k] if k < len(a) else '(none)'} ({len(b)} tokens now, {len(a)} golden)")
        for x in gold.get(name, []):
            lab = x["label"]
            if lab.startswith("fixed:"):
                continue
            if lab not in cat:
                out.append(f"SKELETON {name}: golden label {lab} is not in the catalogue")
            elif x["token"] not in [t for t in NUMBER.findall(cat[lab][0])]:
                out.append(f"SKELETON {name}: golden token {x['token']!r} is no longer in {lab} = {cat[lab][0]!r}")
    return out


# --------------------------------------------------------------------------------------
# Exhibits, references, blinding and wording
# --------------------------------------------------------------------------------------
def exhibit_problems(text: str, profile: str = "ext") -> list[str]:
    pr = PROFILES[profile]
    SUPPLEMENT, SUPP_DATA = pr.supplement, pr.supp_data
    secs = sections(text)
    body = " ".join(v for k, v in secs.items() if k not in ("Title", "Abstract", "Figure legends"))
    out = []
    for kind, want in (("Table", pr.tables), ("Figure", pr.figures)):
        seen = [int(n) for n in re.findall(rf"\b{kind}s? ([1-9])[A-D]?\b", body)]
        first = list(dict.fromkeys(seen))
        if sorted(first) != want:
            out.append(f"EXHIBITS: {kind}s cited {first}, expected each of {want}")
        elif first != want:
            out.append(f"EXHIBITS: first citations of {kind}s out of order: {first}")
    sup: list[str] = []
    for m in re.finditer(r"\bTables? (S\d[ab]?)(?: and (S\d[ab]?))?", body):
        for s in m.groups():
            if s and s not in SUPPLEMENT:
                out.append(f"EXHIBITS: supplementary {s} does not exist")
            elif s:
                sup.append(s)
    first = list(dict.fromkeys(sup))
    if first and first != [s for s in SUPPLEMENT if s in first]:
        out.append(f"EXHIBITS: supplementary tables first cited out of order: {first}")
    never = [s for s in SUPPLEMENT if s not in first]
    if never and sup:
        out.append(f"EXHIBITS: supplementary tables never cited: {never}")
    data: list[str] = []
    for m in re.finditer(r"\bSupplementary data (S\d+[a-z]?)(?: and (S\d+[a-z]?))?", body):
        for s in m.groups():
            if s and s not in SUPP_DATA:
                out.append(f"EXHIBITS: supplementary data {s} does not exist")
            elif s:
                data.append(s)
    never = [s for s in SUPP_DATA if s not in data]
    if never and (data or sup):
        out.append(f"EXHIBITS: supplementary data never cited: {never}")
    legends = secs.get("Figure legends", "")
    for n in pr.figures:
        if f"Figure {n}." not in legends:
            out.append(f"EXHIBITS: no legend for Figure {n}")
    return out


def reference_problems(text: str) -> list[str]:
    refs = text.split("\n## References", 1)
    if len(refs) != 2:
        return ["REFERENCES: no '## References' section"]
    entries = re.findall(r"(?m)^(\d+)\. ", refs[1].split("\n## ", 1)[0])
    n = len(entries)
    out = []
    if [int(e) for e in entries] != list(range(1, n + 1)):
        out.append("REFERENCES: list not numbered 1..n")
    order: list[int] = []
    for m in re.finditer(r"\^([\d,–]+)\^", refs[0] + "\n" + refs[1].split("\n## ", 1)[-1]):
        for part in m.group(1).split(","):
            a, _, b = part.partition("–")
            order += list(range(int(a), int(b or a) + 1))
    for k in sorted(set(order)):
        if not 1 <= k <= n:
            out.append(f"REFERENCES: citation {k} outside 1..{n}")
    first = list(dict.fromkeys(order))
    if first != sorted(first):
        out.append(f"REFERENCES: not numbered in order of first citation: {first}")
    never = sorted(set(range(1, n + 1)) - set(order))
    if never:
        out.append(f"REFERENCES: never cited: {never}")
    if n > 50:
        out.append(f"REFERENCES: {n} references, the journal allows at most 50")
    return out


BANNED = [
    (r"\b[Rr]uling\b|\bA\d{2}\b", "a ruling number"),
    (r"\b(?:GRD|OUT|TOT|NAM|WEB|PQE|Q3T|LGD)-\d", "a decision or check identifier"),
    (r"\bTask \d|\bfix round\b|\breviewer\b|\bcontroller\b|\bimplementer\b|\bdispatch", "drafting-process language"),
    (r"\bD[1-3]\b", "an internal correction code"),
    (r"\b(?:RS|LS) Q\d+|\bQ\d{3,4}\b|\bITR20\d\d\b|\bGHA20\d\d\b|\bPGPH20\d\d\b|\bPRID\b", "a shorthand source identifier"),
    (r"§", "a section sign (plan sections are internal)"),
]
AMERICAN = [r"\banalyz", r"\bstandardiz", r"(?<!World Health )\borganiz", r"\bprogram\b", r"\bprograms\b", r"\bcolor",
            r"\bcenter", r"\bbehavior", r"\bmodeling\b", r"\blabeled\b", r"\bminimiz", r"\bprioritiz",
            r"\brecogniz", r"\butiliz", r"\bcategoriz", r"\bhospitaliz", r"\bemphasiz"]


def author_markers(root: Path) -> list[str]:
    """Strings that would unblind the manuscript: from the plan's Author and Repository lines."""
    head = plan_text(root).split("\n---", 1)[0]
    # a State or Union Territory name is a unit of the analysis, not an identifier of the author
    states = {r["unit"] for r in read_csv(root, "data/extracted/exposure_share_reconstructed.csv")} | {"India"}
    marks: list[str] = []
    for ln in head.splitlines():
        if ln.startswith("**Author:**"):
            body = ln.split(":**", 1)[1]
            marks += [p.strip(" .") for p in re.split(r",", body) if len(p.strip(" .")) >= 5
                      and "Professor" not in p and "Single author" not in p and p.strip(" .") not in states]
            orcid = re.search(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", body)
            if orcid:
                marks.append(orcid.group())
        if ln.startswith("**Repository:**"):
            url = ln.split(":**", 1)[1].strip()
            marks += [url, url.split("github.com/")[-1].split("/")[0]]
    marks += ["zenodo", "github.com"]
    return [m for m in marks if m]


PROCESS = [
    (r"\[(?!repository link removed for blinded review\])[^\]\n]*\]", "a bracketed placeholder or note"),
    (r"(?:manuscript|outputs|data|verification|exhibits)/\S+|\.py\b", "a file path"),
    (r"\bTODO\b|\bto be confirmed\b|\bauthor to confirm\b|\bdate of submission\b", "drafting text"),
    (r"X{3,}", "a placeholder"),
]
DOI_PLACEHOLDER = "DOI: 10.5281/zenodo.XXXXXXX"
OTHER_FILES = {  # file in manuscript/ -> blinded?
    "exhibits/tables.md": True,
    "first_page_src.md": False,
    "cover_letter.md": False,
}


def other_file_problems(name: str, text: str, root: Path, blinded: bool) -> list[str]:
    """Internal identifiers, American spellings, process text and (for blinded files) unblinding,
    in a manuscript file other than manuscript_src.md."""
    out = []
    body = text
    if name == "exhibits/tables.md":
        body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("# Tables (generated"))
    for pat, what in BANNED:
        for m in re.finditer(pat, body):
            out.append(f"WORDING in {name}: {what}: {m.group()!r}")
    for pat in AMERICAN:
        for m in re.finditer(pat, body, re.I):
            out.append(f"SPELLING in {name}: American form {m.group()!r}")
    if blinded:
        for mk in author_markers(root):
            if mk.lower() in body.lower():
                out.append(f"BLINDING in {name}: contains {mk!r}")
    else:
        rest = body.replace(DOI_PLACEHOLDER, " ")
        for pat, what in PROCESS:
            for m in re.finditer(pat, rest):
                out.append(f"PROCESS in {name}: {what}: {m.group()!r}")
        if name == "first_page_src.md" and body.count(DOI_PLACEHOLDER) != 1:
            out.append(f"PROCESS in {name}: the single Zenodo DOI placeholder {DOI_PLACEHOLDER!r} is missing")
    return out


def wording_problems(text: str, root: Path) -> list[str]:
    out = []
    lower = text.lower()
    for m in author_markers(root):
        if m.lower() in lower:
            out.append(f"BLINDING: the manuscript contains {m!r}")
    body = text.split("\n## References", 1)[0]
    for pat, what in BANNED:
        for m in re.finditer(pat, body):
            out.append(f"WORDING: {what}: {m.group()!r}")
    for pat in AMERICAN:
        for m in re.finditer(pat, body, re.I):
            out.append(f"SPELLING: American form {m.group()!r}")
    if "[repository link removed for blinded review]" not in text:
        out.append("BLINDING: the placeholder '[repository link removed for blinded review]' is missing")
    return out


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
def manuscript_dir(root: Path, argv: list[str]) -> tuple[Path, list[str]]:
    """(the manuscript folder, the other arguments): --manuscript-dir DIR (default
    manuscript/ext); a relative DIR is taken from `root`."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--manuscript-dir", default=DEFAULT_MS_DIR)
    a, rest = ap.parse_known_args(argv)
    d = Path(a.manuscript_dir)
    return (d if d.is_absolute() else root / d), rest


def rel(p: Path, root: Path) -> str:
    """A folder's name for messages: relative to `root` where it can be, with '/'."""
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def load_gold(ms_dir: Path) -> dict | None:
    p = ms_dir / SKELETON
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["sections"]


AI_HEADING = "Declaration of Generative AI and AI-assisted technologies in the writing process"


def declaration_problems(text: str, title_page: str) -> list[str]:
    """The AI declaration of the blinded manuscript must be the title page's, word for word."""
    blinded = sections(text).get(AI_HEADING, "")
    m = re.search(r"\*\*" + re.escape(AI_HEADING) + r":\*\* *(.+)", title_page)
    page = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    if not blinded or not page:
        return ["DECLARATION: the AI declaration is missing from the manuscript or the title page"]
    if blinded != page:
        return ["DECLARATION: the AI declaration differs between the manuscript and the title page"]
    return []


def load_others(ms_dir: Path) -> dict[str, str]:
    """The other manuscript files of the folder that exist, by name (none in a fresh clone)."""
    out = {}
    for name in OTHER_FILES:
        p = ms_dir / name
        if p.exists():
            out[name] = p.read_text(encoding="utf-8")
    return out


def problems(root: Path, text: str, gold: dict | None, others: dict[str, str] | None = None, *,
             required: dict[str, list[str]], profile: str = "ext") -> list[str]:
    """Every problem of the manuscript text; `required` is the section phrases (section_phrases());
    `profile` is "ext" (the extension paper) or "v1" (the v1.0.0 audit manuscript)."""
    if not required:
        return [f"PHRASES: no section phrases ({PHRASES} missing or empty)"]
    now, out = skeleton(text, root, required, profile)
    for name, body in (others or {}).items():
        out += other_file_problems(name, body, root, OTHER_FILES[name])
    if others and "first_page_src.md" in others:
        out += declaration_problems(text, others["first_page_src.md"])
    out += skeleton_problems(now, gold, root, profile)
    out += PROFILES[profile].claims(root)
    out += exhibit_problems(text, profile)
    out += reference_problems(text)
    out += wording_problems(text, root)
    return out


def golden(text: str, root: Path, required: dict[str, list[str]], profile: str = "ext") -> dict:
    now, probs = skeleton(text, root, required, profile)
    if probs:
        raise SystemExit("cannot regenerate the skeleton while phrases or numbers fail:\n" + "\n".join(probs))
    return {
        "about": "Golden numeric skeleton of manuscript_src.md: for each section, every number "
                 "token in reading order with the catalogue label that accounts for it and that label's "
                 "source (file and column). Written by verification/check_manuscript_numbers.py "
                 "--regenerate after review; checked on every run.",
        "sections": now,
    }


def main(root: Path = ROOT, argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # problems quote "−" and "≥"
    ms_dir, argv = manuscript_dir(root, argv)
    name = rel(ms_dir, root)
    if not ms_dir.is_dir():
        print(SKIP_DIR.format(d=name))
        return 0
    ms, ph = ms_dir / MS_NAME, ms_dir / PHRASES
    if not ms.exists() and not ph.exists():
        print(SKIP_MS.format(d=name))
        return 0
    if not ms.exists() or not ph.exists():
        have, lack = (MS_NAME, PHRASES) if ms.exists() else (PHRASES, MS_NAME)
        print(f"FAIL: {name}/{have} is present but {name}/{lack} is missing; the check cannot "
              f"run without both (the section phrases are kept, git-ignored, beside the manuscript)")
        return 1
    try:
        required = section_phrases(ms_dir)
    except ValueError as e:  # json.JSONDecodeError is a ValueError
        print(f"FAIL: {name}/{PHRASES} cannot be read: {e}")
        return 1
    profile = profile_for(ms_dir)
    text = ms.read_text(encoding="utf-8")
    if "--regenerate" in argv:
        g = golden(text, root, required, profile)
        (ms_dir / SKELETON).write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8", newline="\n")
        n = sum(len(v) for v in g["sections"].values())
        print(f"wrote {name}/{SKELETON}: {n} number tokens in {len(g['sections'])} sections")
        return 0
    others = load_others(ms_dir)
    found = problems(root, text, load_gold(ms_dir), others, required=required, profile=profile)
    for ln in found:
        print(ln)
    gold = load_gold(ms_dir) or {}
    n_tok = sum(len(v) for v in gold.values())
    n_traced = sum(1 for v in gold.values() for x in v if not x["label"].startswith("fixed:"))
    n_ph = sum(len(v) for v in required.values())
    print(f"[{profile}] {n_tok} number tokens ({n_traced} traced to a source file, {n_tok - n_traced} fixed labels), "
          f"{n_ph} section phrases, {len(catalogue_cached(root, profile))} catalogue values, {len(others)} other "
          f"manuscript files scanned; {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
