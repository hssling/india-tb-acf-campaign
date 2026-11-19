"""Q1: consistency checks of the published figures (analysis plan §6).

Every figure is first turned into an interval [lo, hi] (§6.1):

- h is half a unit in the last printed digit, in the magnitude printed (lakh, crore,
  million). A count printed in full digits (no magnitude word, no decimals) has h = 0;
  a percentage or ratio printed as an integer has h = 0.5 (it is a rounded quantity,
  not a count). "about" takes the same h, but an integer count read "about" takes 0.5.
- exact and about: [v - h, v + h] (never below 0); at_least: [v, inf); at_most: [0, v].
  The qualifier is the inventory's `qualifier` field, assigned at extraction by the
  §6.1 rule (`src.inventory_rules.qualifier`); it is not re-read here.

Checks (§6.2), each written to outputs/q1_checks.csv with the columns check, inputs,
expected, observed, pass, note (one row per check instance; the source is named first
in `inputs`):

1. The cascade does not grow. Cell: one source, identical window_start, window_end,
   as_on and window_label, same geography and scope. Order screened >= presumptive >=
   tested >= TB cases diagnosed >= TB cases notified, for every pair of steps present.
   `tested` enters only as people tested or unspecified; an unspecified `tb_cases`
   figure is compared only with screened, presumptive and tested. One definition class
   per step (ruling A21): a step that holds figures of more than one definition class
   in a cell is not compared in that cell (an n/a row says so), so that, for example, a
   'screened by chest X-ray' sub-count is never set against the presumptive count.
   Fails if upper(earlier) < lower(later).
2. Percentages recompute. A stated percentage p with numerator n and denominator d from
   the same source passes if interval(p) overlaps [100 n_lo / d_hi, 100 n_hi / d_lo].
   n and d are read from the same table (same source, table_id, geography and window)
   or, for prose, from the same sentence (same context_verbatim). Which quantities are
   n and d is read from the percentage's quantity name (PCT below). A percentage whose
   n or d is not printed with it is not checked (one n/a summary row per source).
3. Totals equal the sum of their parts. Passes if [sum lo - 1, sum hi + 1] overlaps the
   interval of the printed total. Two layouts are recognised from the table fields:
   (a) a column: State/UT rows against the India row (row label India, INDIA, Total or
   TOTAL) of the same source, table, quantity, column heading and window;
   (b) a row: columns "<heading>: <part>" against "<heading>: Total" of the same row.
   Percent and ratio columns are not summed.
4. A cumulative series never decreases: series_type cumulative, same quantity,
   definition class, scope, geography and window_start, non-blank as_on, ordered by
   as_on across documents. A failure goes to Q2 class 3 (§7.3), never to class 1.

The two quality studies' stratified tables (data/extracted/quality_studies.csv; strata
are not inventory figures) are checked by the same rules 1-3 (PGPH Tables 2-3, GHA
Table 2); a stratum total that is also an inventory figure carries its fig_id.

`other:` quantities (§5.1) are kept out of the checks, with two exceptions noted on each
row: a stated percentage (check 2) is a derived `other:` quantity whose numerator and
denominator are named quantities, and count tables of `other:` quantities are summed
under check 3 (for example the high-risk villages of the 2026 campaign document).

Run: python -I src/q1_consistency.py
Standard library only (§11).
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import math
import re
from collections import defaultdict
from fractions import Fraction

from src.inventory_rules import qualifier as _qualifier
from src.inventory_rules import value_of as _value_of

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/figures_inventory.csv"
QUALITY = ROOT / "data/extracted/quality_studies.csv"
OUT = ROOT / "outputs/q1_checks.csv"
COLUMNS = ["check", "inputs", "expected", "observed", "pass", "note"]

INF = math.inf
CHECK1 = "1 cascade does not grow"
CHECK2 = "2 percentage recomputes"
CHECK3 = "3 total equals the sum of its parts"
CHECK4 = "4 cumulative series never decreases"

# ------------------------------------------------------------------ §6.1 interval

_RANGE = re.compile(r"\d\s*[–-]\s*\d")
_SYMBOLS = re.compile(r"[+~≈><≤≥%*]")
_NUM = re.compile(r"(\d[\d,\s]*(?:\.\d+)?)\s*(lakhs?|crores?|cr|million)?", re.I)
_MULT = {"lakh": 100000, "lakhs": 100000, "crore": 10 ** 7, "crores": 10 ** 7,
         "cr": 10 ** 7, "million": 10 ** 6}
_COUNT_UNITS = ("persons", "tests", "cases", "districts", "")


def printed_parts(printed: str) -> tuple[int, int, Fraction] | None:
    """(decimals, multiplier, printed number) of a printed figure; None for a range or
    no number in digits."""
    t = (printed or "").strip()
    if not t or _RANGE.search(t):
        return None
    t = _SYMBOLS.sub(" ", t)
    m = _NUM.search(t)
    if not m:
        return None
    digits = re.sub(r"[,\s]", "", m.group(1))
    decimals = len(digits.split(".", 1)[1]) if "." in digits else 0
    mult = _MULT[m.group(2).lower()] if m.group(2) else 1
    return decimals, mult, Fraction(digits)


def half_unit(row: dict) -> Fraction | None:
    """Half a unit of the last printed digit, in the figure's own magnitude. A magnitude
    stated only in the column heading (for example 'Estimated Population (Lakhs)',
    printed '3.9', value 390000) is read from value / printed number."""
    parts = printed_parts(row["value_printed"])
    if parts is None:
        return None
    decimals, mult, number = parts
    if mult == 1 and number and str(row.get("value", "")).strip():
        scale = Fraction(str(row["value"])) / number
        if scale > 1 and scale.denominator == 1 and set(str(scale.numerator)[1:]) <= {"0"}                 and str(scale.numerator)[0] == "1":
            mult = scale.numerator
    count = row.get("unit", "") in _COUNT_UNITS
    if decimals == 0 and mult == 1 and count and row["qualifier"] != "about":
        return Fraction(0)
    return Fraction(1, 2) * Fraction(1, 10 ** decimals) * mult


def interval(row: dict):
    """(lo, hi) of a figure (§6.1); Fractions, hi may be math.inf. None if the figure
    has no single value (a printed range)."""
    if not str(row.get("value", "")).strip():
        return None
    h = half_unit(row)
    if h is None:
        return None
    v = Fraction(str(row["value"]))
    q = row["qualifier"]
    if q == "at_least":
        return (v, INF)
    if q == "at_most":
        return (Fraction(0), v)
    if q not in ("exact", "about"):
        raise ValueError(f"unknown qualifier {q!r}")
    return (max(v - h, Fraction(0)), v + h)


def interval_from_text(context: str, printed: str, unit: str = "persons"):
    """Interval of `printed` as it appears in `context`: the §6.1 qualifier rule
    (inventory_rules.qualifier) and the §5.2 value rule, then interval()."""
    return interval({"value": _value_of(printed), "value_printed": printed,
                     "qualifier": _qualifier(context, printed), "unit": unit})


def overlap(a, b) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def fmt(x) -> str:
    if x == INF:
        return "inf"
    x = Fraction(x)
    if x.denominator == 1:
        return str(x.numerator)
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    return s


def fmt_iv(iv) -> str:
    return f"[{fmt(iv[0])}, {fmt(iv[1])}]"


# ------------------------------------------------------------ check primitives

def cascade_ok(earlier, later) -> bool:
    """§6.2 check 1: fails if the upper bound of the earlier step is below the lower
    bound of the later step."""
    return not (earlier[1] < later[0])


def recompute(n, d):
    lo = Fraction(0) if d[1] == INF else 100 * n[0] / d[1]
    hi = INF if (d[0] == 0 or n[1] == INF) else 100 * n[1] / d[0]
    return (lo, hi)


def percentage_ok(p, n, d) -> bool:
    """§6.2 check 2."""
    return overlap(p, recompute(n, d))


def parts_interval(parts):
    lo = sum((p[0] for p in parts), Fraction(0))
    hi = INF if any(p[1] == INF for p in parts) else sum((p[1] for p in parts), Fraction(0))
    return (lo - 1, hi + 1 if hi != INF else INF)


def sum_of_parts_ok(parts, total) -> bool:
    """§6.2 check 3: [sum lo - 1, sum hi + 1] overlaps the printed total."""
    return overlap(parts_interval(parts), total)


def _row(check, source, inputs, expected, observed, passed, note, figs):
    return {"check": check, "inputs": f"source: {source}; {inputs}", "expected": expected,
            "observed": observed, "pass": passed, "note": note, "_figs": list(figs),
            "_source": source}


def _desc(r) -> str:
    return f"{r['fig_id']} ('{r['value_printed']}' {r['qualifier']})"


# ----------------------------------------------------------------- check 1

ORDER = ("screened", "presumptive", "tested", "diagnosed", "notified")
_TB = {"diagnosed": "diagnosed", "notified": "notified", "unspecified": "tb_unspecified"}


def step_of(row: dict) -> str | None:
    q, c = row["quantity"], row["definition_class"]
    if q in ("screened", "presumptive"):
        return q
    if q == "tested":
        return "tested" if c in ("people tested", "unspecified") else None
    if q == "tb_cases":
        return _TB.get(c)
    return None


def _step_pairs(present):
    for i, a in enumerate(ORDER):
        for b in ORDER[i + 1:]:
            if a in present and b in present:
                yield a, b
    if "tb_unspecified" in present:
        for a in ("screened", "presumptive", "tested"):
            if a in present:
                yield a, "tb_unspecified"


def _cascade_cells(cells, source_of, label_of):
    out = []
    for key, members in sorted(cells.items(), key=lambda kv: str(kv[0])):
        steps = defaultdict(list)
        for r in members:
            steps[r["_step"]].append(r)
        usable = {}
        for s, rs in steps.items():
            classes = sorted({r["definition_class"] for r in rs})
            if len(classes) > 1:
                out.append(_row(CHECK1, source_of(key), f"{label_of(key)}; step {s}: "
                                + ", ".join(_desc(r) for r in rs), "", "", "n/a",
                                f"not compared: step '{s}' holds several definition classes "
                                f"({'; '.join(classes)}); one definition class per step "
                                "(§6.2 check 1, ruling A21)", [r["fig_id"] for r in rs]))
                continue
            usable[s] = rs
        for a, b in _step_pairs(usable):
            for ra in usable[a]:
                for rb in usable[b]:
                    ia, ib = ra["_iv"], rb["_iv"]
                    ok = cascade_ok(ia, ib)
                    note = ""
                    if not ok and "unspecified" in (ra["definition_class"], rb["definition_class"]):
                        note = "failure involves an unspecified definition class"
                    out.append(_row(
                        CHECK1, source_of(key),
                        f"{label_of(key)}; earlier {a}: {_desc(ra)}; later {b}: {_desc(rb)}",
                        f"upper({a}) >= lower({b})",
                        f"{a} {fmt_iv(ia)}; {b} {fmt_iv(ib)}", "yes" if ok else "no",
                        note, [ra["fig_id"], rb["fig_id"]]))
    return out


def cascade_checks(rows) -> list[dict]:
    cells = defaultdict(list)
    for r in rows:
        s = step_of(r)
        iv = interval(r)
        if s is None or iv is None:
            continue
        key = (r["source_file"], r["window_start"], r["window_end"], r["as_on"],
               r["window_label"], r["geography"], r["scope"])
        cells[key].append(dict(r, _step=s, _iv=iv))

    def label(k):
        return (f"cell: geography {k[5]}, scope {k[6]}, window {k[1] or '-'}..{k[2] or '-'}, "
                f"as_on {k[3] or '-'}, label '{k[4]}'")
    return _cascade_cells(cells, lambda k: k[0], label)


# ----------------------------------------------------------------- check 2

_TESTED = {"people tested", "unspecified"}
_DIAG = {"diagnosed", "unspecified"}
# percentage quantity -> ((numerator quantity, classes), (denominator quantity, classes));
# classes None = any. Read from the quantity names assigned at extraction.
PCT = {
    "other:pct_diagnosed_among_tested": (("tb_cases", _DIAG), ("tested", _TESTED)),
    "other:pct_diagnosed_among_examined": (("tb_cases", _DIAG), ("tested", _TESTED)),
    "other:pct_tested_among_screened": (("tested", _TESTED), ("screened", None)),
    "other:pct_examined_among_screened": (("tested", _TESTED), ("screened", None)),
    "other:pct_presumptive_among_screened": (("presumptive", None), ("screened", None)),
    "other:pct_symptomatic_among_screened": (("presumptive", None), ("screened", None)),
    "other:pct_tested_among_presumptive": (("tested", _TESTED), ("presumptive", None)),
    "other:pct_mapped_population_screened": (("screened", None), ("population_targeted", None)),
    "other:pct_population_mapped_high_risk": (("population_targeted", None),
                                              ("other:estimated_population", None)),
    "other:pct_population_identified_vulnerable": (("population_targeted", None),
                                                   ("other:estimated_population", None)),
    "other:pct_population_screened": (("screened", None), ("other:estimated_population", None)),
    "other:pct_screened_by_chest_radiograph": (("screened", {"screened by chest X-ray"}),
                                               ("screened", {"unspecified"})),
    "other:pct_rapid_molecular_among_tested": (("other:rapid_molecular_tests_used", None),
                                               ("tested", _TESTED)),
    "acf_share_notifications": (("tb_cases", _DIAG), ("other:public_sector_tb_notified", None)),
}


def _scope_key(r):
    if r["table_id"]:
        return ("table", r["source_file"], r["table_id"], r["geography"], r["window_start"],
                r["window_end"])
    return ("prose", r["source_file"], r["context_verbatim"], r["geography"])


def _pick(cands, spec):
    q, classes = spec
    hits = [c for c in cands if c["quantity"] == q
            and (classes is None or c["definition_class"] in classes) and c["_iv"] is not None]
    values = {c["value"] for c in hits}
    if not hits:
        return None, "absent"
    if len(values) > 1:
        return None, "ambiguous: " + ", ".join(_desc(c) for c in hits)
    return hits[0], "ok"


def percentage_checks(rows, run_elsewhere=frozenset()) -> list[dict]:
    """Check 2 on inventory rows. `run_elsewhere`: percentages whose check is made on the
    stratified quality-study table instead (left out of the not-run summary)."""
    pool = defaultdict(list)
    for r in rows:
        pool[_scope_key(r)].append(dict(r, _iv=interval(r)))
    out, absent = [], defaultdict(list)
    for r in rows:
        if r["quantity"] not in PCT or r["unit"] != "percent":
            continue
        p = interval(r)
        if p is None:
            continue
        cands = [c for c in pool[_scope_key(r)] if c["fig_id"] != r["fig_id"]]
        num_spec, den_spec = PCT[r["quantity"]]
        n, sn = _pick(cands, num_spec)
        d, sd = _pick([c for c in cands if n is None or c["fig_id"] != n["fig_id"]], den_spec)
        where = "same table" if r["table_id"] else "same sentence"
        if n is None or d is None:
            if "ambiguous" in sn or "ambiguous" in sd:
                out.append(_row(CHECK2, r["source_file"], f"percentage {_desc(r)}", "", "", "n/a",
                                f"not run: numerator {sn}; denominator {sd} ({where})",
                                [r["fig_id"]]))
            elif r["fig_id"] not in run_elsewhere:
                absent[r["source_file"]].append(r["fig_id"])
            continue
        rec = recompute(n["_iv"], d["_iv"])
        ok = overlap(p, rec)
        note = "" if not r["quantity"].startswith("other:") else (
            "a stated percentage (an other: quantity) of named numerator and denominator")
        out.append(_row(CHECK2, r["source_file"],
                        f"percentage {_desc(r)}; numerator {_desc(n)}; denominator {_desc(d)} "
                        f"({where})",
                        f"p overlaps 100 n/d = {fmt_iv(rec)}",
                        f"p {fmt_iv(p)}; 100 n/d {fmt_iv(rec)}", "yes" if ok else "no", note,
                        [r["fig_id"], n["fig_id"], d["fig_id"]]))
    for src, figs in sorted(absent.items()):
        out.append(_row(CHECK2, src, f"{len(figs)} percentage(s): " + ", ".join(figs), "", "",
                        "n/a", "not run: numerator or denominator not printed in the same "
                        "table or sentence", figs))
    return out


# ----------------------------------------------------------------- check 3

TOTAL_LABELS = {"india", "total"}
_SKIP_UNITS = ("percent", "ratio")


def _segments(r):
    return r["context_verbatim"].split(" | ")


def _sum_row(source, inputs, total, parts, note):
    ivs = [p["_iv"] for p in parts]
    piv = parts_interval(ivs)
    ok = overlap(piv, total["_iv"])
    s = sum(Fraction(str(p["value"])) for p in parts)
    diff = s - Fraction(str(total["value"]))
    return _row(CHECK3, source,
                f"{inputs}; total {_desc(total)}; {len(parts)} parts: "
                + ", ".join(p["fig_id"] for p in parts),
                f"[sum lo - 1, sum hi + 1] = {fmt_iv(piv)} overlaps total {fmt_iv(total['_iv'])}",
                f"sum of parts {fmt(s)}; printed total {fmt(Fraction(str(total['value'])))}; "
                f"difference {fmt(diff)}", "yes" if ok else "no", note,
                [total["fig_id"]] + [p["fig_id"] for p in parts])


def sum_checks(rows) -> list[dict]:
    out = []
    usable = []
    for r in rows:
        if not r["table_id"] or r.get("unit", "") in _SKIP_UNITS:
            continue
        iv = interval(r)
        if iv is None:
            continue
        usable.append(dict(r, _iv=iv))
    # (a) column totals
    cols = defaultdict(list)
    for r in usable:
        seg = _segments(r)
        if len(seg) < 2:
            continue
        key = (r["source_file"], r["table_id"], r["quantity"], r["definition_class"],
               " | ".join(seg[:-1]), r["window_start"], r["window_end"], r["as_on"])
        cols[key].append(r)
    for key, rs in sorted(cols.items()):
        totals = [r for r in rs if r["geography"] == "India"
                  and _segments(r)[-1].strip().lower() in TOTAL_LABELS]
        parts = [r for r in rs if r["geography"] != "India"]
        if not totals or len(parts) < 2:
            continue
        note = ("other: quantity (§5.1 keeps other: figures out of §6; summed here as a "
                "printed table total)") if key[2].startswith("other:") else ""
        if len(totals) > 1:
            out.append(_row(CHECK3, key[0], f"table {key[1]}; column '{key[4]}'", "", "", "n/a",
                            "not run: more than one total row", [t["fig_id"] for t in totals]))
            continue
        out.append(_sum_row(key[0], f"table {key[1]}; column '{key[4]}'; State/UT rows "
                            "against the India row", totals[0], parts, note))
    # (b) row totals: "<heading>: <part>" against "<heading>: Total"
    rows_ = defaultdict(list)
    for r in usable:
        seg = _segments(r)
        if len(seg) < 2 or ": " not in seg[-2]:
            continue
        head, part = seg[-2].rsplit(": ", 1)
        key = (r["source_file"], r["table_id"], r["quantity"], r["geography"], seg[-1], head,
               r["window_start"], r["window_end"], r["as_on"])
        rows_[key].append(dict(r, _part=part.strip()))
    for key, rs in sorted(rows_.items()):
        totals = [r for r in rs if r["_part"].lower() == "total"]
        parts = [r for r in rs if r["_part"].lower() != "total"]
        if len(totals) != 1 or len(parts) < 2:
            continue
        out.append(_sum_row(key[0], f"table {key[1]}; row '{key[4]}'; columns '{key[5]}: "
                            + "/".join(p["_part"] for p in parts) + "' against "
                            f"'{key[5]}: Total'", totals[0], parts, ""))
    return out


def sector_parts(results) -> set[str]:
    """fig_ids that are parts of a row total (check 3, layout b), e.g. Public and
    Private columns of a notification table."""
    out = set()
    for r in results:
        if r["check"] == CHECK3 and "against '" in r["inputs"] and "columns '" in r["inputs"]:
            out.update(r["_figs"][1:])
    return out


# ----------------------------------------------------------------- check 4

def cumulative_checks(rows) -> list[dict]:
    series = defaultdict(list)
    for r in rows:
        if (r["series_type"] != "cumulative" or not r["as_on"] or not r["window_start"]
                or r["quantity"].startswith("other:")):
            continue
        iv = interval(r)
        if iv is None:
            continue
        key = (r["quantity"], r["definition_class"], r["scope"], r["geography"],
               r["window_start"])
        series[key].append(dict(r, _iv=iv))
    out = []
    for key, rs in sorted(series.items()):
        rs.sort(key=lambda r: r["as_on"])
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if b["as_on"] == a["as_on"]:
                    continue
                ok = not (b["_iv"][1] < a["_iv"][0])
                out.append(_row(CHECK4, f"{a['source_file']} / {b['source_file']}",
                                f"series {key}; earlier {_desc(a)} as on {a['as_on']}; later "
                                f"{_desc(b)} as on {b['as_on']}", "upper(later) >= lower(earlier)",
                                f"earlier {fmt_iv(a['_iv'])}; later {fmt_iv(b['_iv'])}",
                                "yes" if ok else "no", "a failure is passed to Q2 class 3 (§7.3)",
                                [a["fig_id"], b["fig_id"]]))
    if not out:
        out.append(_row(CHECK4, "all documents", "no input", "", "", "n/a",
                        "not run: no cumulative figure of a §5.1 quantity has a non-blank "
                        "as_on (§6.2 check 4 needs one)", []))
    return out


# ------------------------------------------------- quality-study strata (not inventory)

_QS_TABLES = {("PGPH2025", "Table 2"), ("PGPH2025", "Table 3"), ("GHA2023", "Table 2")}
_QS_TO_INV = {"screened": "screened", "presumptive": "presumptive", "tested": "tested",
              "diagnosed": "tb_cases", "rapid_test": "other:rapid_molecular_tests_used"}
_QS_STEP = {"screened": "screened", "presumptive": "presumptive", "tested": "tested",
            "diagnosed": "diagnosed"}
# (study, percentage quantity) -> (numerator, denominator) as each study states it
_QS_PCT = {
    ("PGPH2025", "pct_presumptive"): ("presumptive", "screened"),
    ("PGPH2025", "pct_tested"): ("tested", "presumptive"),
    ("PGPH2025", "pct_diagnosed"): ("diagnosed", "tested"),
    ("PGPH2025", "pct_rapid_test"): ("rapid_test", "tested"),
    ("PGPH2025", "pct_screened_col"): ("screened", "TOTAL:screened"),
    ("GHA2023", "pct_tested"): ("tested", "screened"),
    ("GHA2023", "pct_diagnosed"): ("diagnosed", "tested"),
}


def _qs_fig(q, inv_index):
    fid = inv_index.get((q["source"], q["table_id"], _QS_TO_INV.get(q["quantity"]), q["value"]))
    loc = f"QS:{q['study']} {q['locator']}"
    return {"fig_id": fid or loc, "_loc": loc, "_inv": fid, "quantity": q["quantity"],
            "value": q["value"], "value_printed": q["printed_value"], "qualifier": "exact",
            "unit": q["unit"], "definition_class": "", "source_file": q["source"],
            "_group": q["row_group"], "_label": q["row_label"], "_col": q["column_label"],
            "_table": q["table_id"], "_study": q["study"]}


def strata_checks(quality, inventory, checked=frozenset()) -> list[dict]:
    """Checks 1-3 on the stratified tables. `checked`: inventory percentages already
    run under check 2 (a Total-row percentage that is one of them is not run twice)."""
    inv_index, inv_pct = {}, {}
    for r in inventory:
        if r["geography"] == "India" and r["table_id"]:
            inv_index[(r["source_file"], r["table_id"], r["quantity"], r["value"])] = r["fig_id"]
            if r["unit"] == "percent":
                inv_pct[(r["source_file"], r["table_id"], r["value"])] = r["fig_id"]
    figs = []
    for q in quality:
        if (q["study"], q["table_id"]) not in _QS_TABLES:
            continue
        f = _qs_fig(q, inv_index)
        f["_iv"] = interval(f)
        if f["_iv"] is not None:
            figs.append(f)
    out = []
    note = "stratified table of a quality study (data/extracted/quality_studies.csv)"

    def d(f):
        return f"{f['fig_id']} ('{f['value_printed']}')"
    # check 1 and 2 per stratum row (the Total row is checked through the inventory)
    by_row = defaultdict(list)
    for f in figs:
        by_row[(f["source_file"], f["_study"], f["_table"], f["_group"], f["_label"])].append(f)
    totals = {(f["_study"], f["_table"], f["quantity"], f["_col"]): f
              for f in figs if f["_group"] == "Total"}
    total_by_q = {(f["_study"], f["_table"], f["quantity"]): f
                  for f in figs if f["_group"] == "Total" and f["unit"] != "percent"}
    cells = {}
    for key, fs in by_row.items():
        if key[3] == "Total":
            continue
        cell = [dict(f, _step=_QS_STEP[f["quantity"]]) for f in fs if f["quantity"] in _QS_STEP]
        for f in cell:
            f["definition_class"] = "unspecified" if f["_step"] in ("screened", "tested") else (
                "diagnosed" if f["_step"] == "diagnosed" else "")
        cells[key] = cell
    out += _cascade_cells(cells, lambda k: k[0],
                          lambda k: f"{k[1]} {k[2]}, stratum '{k[3]}: {k[4]}'")
    for key, fs in sorted(by_row.items()):
        counts = {f["quantity"]: f for f in fs if f["unit"] != "percent"}
        for f in fs:
            spec = _QS_PCT.get((f["_study"], f["quantity"]))
            if spec is None:
                continue
            if key[3] == "Total":
                fid = inv_pct.get((f["source_file"], f["_table"], f["value"]))
                if fid in checked:
                    continue
                f = dict(f, fig_id=fid or f["fig_id"])
            n = counts.get(spec[0])
            dq = spec[1]
            dd = (total_by_q.get((f["_study"], f["_table"], dq.split(":", 1)[1]))
                  if dq.startswith("TOTAL:") else counts.get(dq))
            if n is None or dd is None:
                continue
            rec = recompute(n["_iv"], dd["_iv"])
            ok = overlap(f["_iv"], rec)
            out.append(_row(CHECK2, key[0],
                            f"{key[1]} {key[2]}, stratum '{key[3]}: {key[4]}'; percentage {d(f)}; "
                            f"numerator {d(n)}; denominator {d(dd)}",
                            f"p overlaps 100 n/d = {fmt_iv(rec)}",
                            f"p {fmt_iv(f['_iv'])}; 100 n/d {fmt_iv(rec)}",
                            "yes" if ok else "no", note,
                            [f["fig_id"], n["fig_id"], dd["fig_id"]]))
    # check 3: each stratum group's rows against the Total row, per column
    groups = defaultdict(list)
    for f in figs:
        if f["_group"] != "Total" and f["unit"] != "percent" and f["quantity"] != "nns":
            groups[(f["source_file"], f["_study"], f["_table"], f["_group"], f["quantity"],
                    f["_col"])].append(f)
    for key, parts in sorted(groups.items()):
        total = totals.get((key[1], key[2], key[4], key[5]))
        if total is None or len(parts) < 2:
            continue
        out.append(_sum_row(key[0], f"{key[1]} {key[2]}; stratum group '{key[3]}'; column "
                            f"'{key[5]}'", total, parts, note))
    return out


# ------------------------------------------------------------------------- run

def load_inventory(path: Path = INVENTORY) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_quality(path: Path = QUALITY) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run_checks(inventory, quality=()) -> list[dict]:
    pct = percentage_checks(inventory)
    checked = {r["_figs"][0] for r in pct if r["pass"] in ("yes", "no")}
    strata = strata_checks(list(quality), inventory, checked)
    pct = percentage_checks(inventory, {r["_figs"][0] for r in strata if r["check"] == CHECK2})
    return (cascade_checks(inventory) + pct + sum_checks(inventory)
            + cumulative_checks(inventory) + strata)


def failures(results) -> dict[str, list[str]]:
    """fig_id -> descriptions of the failed within-source checks (1-3) involving it."""
    out = defaultdict(list)
    for r in results:
        if r["pass"] == "no" and r["check"][0] in "123":
            desc = f"check {r['check']} failed ({r['inputs'][:160]}...; observed {r['observed']})"
            for fid in r["_figs"]:
                out[fid].append(desc)
    return dict(out)


def write(results, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(results)


def summary(results) -> dict:
    out = defaultdict(lambda: {"yes": 0, "no": 0, "n/a": 0})
    for r in results:
        out[r["check"]][r["pass"]] += 1
    return dict(out)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    inv = load_inventory()
    res = run_checks(inv, load_quality())
    write(res)
    for check, c in sorted(summary(res).items()):
        print(f"{check}: pass {c['yes']}, fail {c['no']}, n/a {c['n/a']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
