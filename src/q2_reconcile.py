"""Q2: discrepancies and definitions (analysis plan §7), and the reconciliation of the
two quality studies (§7.5).

Comparison groups (§7.1). Two figures are related if they have the same quantity
(`other:` excluded), the same geography and the same scope ("unspecified" a scope of its
own), and either both windows are stated and their spans intersect, or their window
labels are identical and non-blank. A window is stated if window_start is non-blank and
at least one of window_end and as_on is non-blank; its span is [window_start, the later
of window_end and as_on]. A comparison group is a connected set of related figures (the
relation is not transitive); within a group, entries are distinct (document, value)
pairs, and one row is written for every unordered pair of entries that holds at least
one related pair of figures. Entries agree if a related pair of their figures has
overlapping §6.1 intervals. Figures of the same quantity and geography that differ only
in scope are not compared; they are listed in outputs/q2_different_scope.csv.

Decision order (§7.3), for a pair that disagrees; the first class that applies is
assigned and the others are noted:

1. arithmetic error within a source: a figure fails a within-source check (§6.2,
   checks 1-3) that involves it; the failed check is cited;
2. definitional difference: both definition classes stated (not unspecified) and
   different; both definitions quoted;
3. window or cut-off difference: both windows stated and different in start, end or
   cut-off. 3a: the later cut-off or longer (containing) span gives the larger value, or
   the spans are neither nested nor from the same start, or the spans are equal; 3b: the
   later cut-off or longer span gives the smaller value. A check-4 failure enters here
   directly;
4. unexplained: none of the above, including every pair with an unstated window.
   "Unexplained" records that the published documents do not explain the difference;
   it is not a finding of error (§7.3, §12).

Labels. Comparisons that use RS Q420 (obtained after registration) or the 2024 column of
RS Q1900 are exploratory (§13, 18 November 2026). RS Q1900's January-October 2025
column against RS Q1093 is pre-specified (§9.5.5). The §7.4 items are tagged on their
pairs; the guard's per-State ratios (§9.5.2) are attached to the Q1216-Q3467 pairs, with
the label late-report-consistent for 2024 ratios above 1.05. The §9.2 named-list counts
(counts of list rows, not printed figures) are classified by the same decision order.

Two sets are written (§13, 19 November 2026). The registered set applies the rules above
as registered (outputs/q2_*.csv). The corrected set, a post-hoc deviation made after the
registered output was seen, is written to outputs/q2_*_corrected.csv: D1, a figure's span
is [window_start, window_end] where window_end is printed (as_on extends it only where
window_end is blank); where two spans are then equal and both cut-offs are stated, the
§7.3 later-cut-off direction is read from the cut-offs; D2, printed sector parts
(q1_consistency.sector_keyword) are not grouped; D3, class 1 follows the corrected Q1
checks (check 1 within one printed table or paragraph). `other:` rows of Q1 never feed
class 1 (§5.1). outputs/q2_summary_registered_vs_corrected.csv sets the counts side by
side; outputs/q2_not_formed.csv lists candidate pairs the rules do not group.

Run: python -I src/q2_reconcile.py   (runs the Q1 checks in memory for class 1)
Standard library only (§11).
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import math
import statistics
from collections import defaultdict
from datetime import date
from fractions import Fraction
from itertools import combinations

from src import q1_consistency as q1
from src.states import coarsen

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "data/extracted"
OUT = ROOT / "outputs"

CLASSES = ("1", "2", "3a", "3b", "4")
CLASS_LABEL = {
    "1": "arithmetic error within a source",
    "2": "definitional difference",
    "3a": "window or cut-off difference, direction consistent with the windows",
    "3b": "window or cut-off difference that does not explain the direction",
    "4": "unexplained",
}
RULE = {
    "1": "§7.3 (1): a figure fails a within-source check (§6.2 checks 1-3) that involves it",
    "2": "§7.3 (2): both definition classes stated and different",
    "3a": "§7.3 (3a): both windows stated and different; the later cut-off or longer "
          "window gives the larger value, or no direction is implied",
    "3b": "§7.3 (3b): both windows stated and different; the later cut-off or longer "
          "window gives the smaller value",
    "4": "§7.3 (4): none of classes 1-3 applies; the published documents do not explain "
         "the difference",
}

Q420, Q1900, Q1093 = "AU420_ulGhhr.pdf", "AU1900_PxKD5V.pdf", "AU1093_dH065I.pdf"
Q1216, Q3467, Q261, Q2511 = ("AU1216_WFw8li.pdf", "AU3467_mVGJLD.pdf", "AS261_lP7nYE.pdf",
                              "AU2511_t81pFf.pdf")
ITR2024 = "ITR2024.pdf"


def _name(r) -> str:
    return r["source_file"].replace("\\", "/").rsplit("/", 1)[-1]


# ------------------------------------------------------------------ windows (§7.1)

def stated(r) -> bool:
    return bool(r["window_start"]) and bool(r["window_end"] or r["as_on"])


def span(r, corrected: bool = False) -> tuple[date, date]:
    """Registered (§7.1): [window_start, the later of window_end and as_on]. Corrected
    (D1, §13, 19 November 2026): [window_start, window_end] where window_end is printed;
    as_on extends the span only where window_end is blank."""
    if corrected and r["window_end"]:
        return date.fromisoformat(r["window_start"]), date.fromisoformat(r["window_end"])
    ends = [date.fromisoformat(x) for x in (r["window_end"], r["as_on"]) if x]
    return date.fromisoformat(r["window_start"]), max(ends)


def related(a, b, corrected: bool = False) -> list[str]:
    out = []
    if stated(a) and stated(b):
        (a0, a1), (b0, b1) = span(a, corrected), span(b, corrected)
        if a0 <= b1 and b0 <= a1:
            out.append("windows overlap")
    if a["window_label"] and a["window_label"] == b["window_label"]:
        out.append("same window label")
    return out


def periods_intersect(a, b) -> str:
    """Descriptive only (not a §7 rule): do the periods [window_start, window_end] (or
    [window_start, as_on] where no end is printed) intersect? Blank if a start is blank.
    A 'no' marks a pair related only because a span runs on to a late as_on date."""
    def per(r):
        end = r["window_end"] or r["as_on"]
        return (date.fromisoformat(r["window_start"]), date.fromisoformat(end)) if (
            r["window_start"] and end) else None
    pa, pb = per(a), per(b)
    if pa is None or pb is None:
        return ""
    return "yes" if pa[0] <= pb[1] and pb[0] <= pa[1] else "no"


def _window_text(r) -> str:
    return (f"{r['window_start'] or '-'}..{r['window_end'] or '-'}; as_on {r['as_on'] or '-'}; "
            f"label '{r['window_label']}'; {'stated' if stated(r) else 'unstated'}")


# --------------------------------------------------------------- decision order (§7.3)

def _window_class(a, b, corrected: bool = False):
    if not (stated(a) and stated(b)):
        return None
    if (a["window_start"], a["window_end"], a["as_on"]) == (
            b["window_start"], b["window_end"], b["as_on"]):
        return None
    sa, sb = span(a, corrected), span(b, corrected)
    ia, ib = q1.interval(a), q1.interval(b)
    text = f"spans {sa[0]}..{sa[1]} and {sb[0]}..{sb[1]}"
    if sa == sb:
        if corrected and a["as_on"] and b["as_on"] and a["as_on"] != b["as_on"]:
            # D1 keeps as_on out of the span, so the §7.3 "later cut-off" is read from
            # the two stated cut-offs of the same window
            late, early, which = (ia, ib, "first") if a["as_on"] > b["as_on"] else (
                ib, ia, "second")
            text += f"; same window, cut-offs {a['as_on']} and {b['as_on']}"
            if late[1] < early[0]:
                return "3b", (text + f": the {which} (later cut-off) gives the smaller value, "
                              "which the cut-offs do not explain")
            return "3a", text + f": the {which} (later cut-off) gives the larger value"
        return "3a", text + "; equal spans (§7.3: the row is 3a)"
    if sa[0] <= sb[0] and sb[1] <= sa[1]:
        big, small, which = ia, ib, "first"
    elif sb[0] <= sa[0] and sa[1] <= sb[1]:
        big, small, which = ib, ia, "second"
    else:
        return "3a", text + "; neither nested nor from the same start: no direction implied"
    rel = "same start, later cut-off" if sa[0] == sb[0] else "nested windows"
    if big[1] < small[0]:
        return "3b", (text + f"; {rel}: the {which} (later or longer) gives the smaller "
                      "value, which the windows do not explain")
    return "3a", text + f"; {rel}: the {which} (later or longer) gives the larger value"


def classify(a, b, failed, cumulative_failed=frozenset(), corrected: bool = False) -> dict:
    """§7.3 class of a disagreeing pair of figures. `failed`: fig_id -> failed checks
    1-3 (q1_consistency.failures); `cumulative_failed`: frozensets of fig_id pairs that
    fail check 4."""
    found = []
    if frozenset((a["fig_id"], b["fig_id"])) in cumulative_failed:
        cls = "3b" if stated(a) and stated(b) else "4"
        return _result(cls, [], "check 4 (cumulative series) failed; it enters class 3 "
                       "directly (§6.2, §7.3)" + ("" if cls == "3b" else
                                                  "; a window is unstated, so class 4"))
    fails = [f"{r['fig_id']}: {d}" for r in (a, b) for d in failed.get(r["fig_id"], [])]
    if fails:
        found.append(("1", "; ".join(fails)))
    ca, cb = a["definition_class"], b["definition_class"]
    if ca and cb and "unspecified" not in (ca, cb) and ca != cb:
        found.append(("2", f"definitions: '{a['definition_verbatim']}' ({ca}) vs "
                           f"'{b['definition_verbatim']}' ({cb})"))
    w = _window_class(a, b, corrected)
    if w:
        found.append(w)
    if not found:
        why = []
        why.append("no within-source check (§6.2 checks 1-3) failed for either figure")
        why.append(f"definition classes '{ca or 'none'}' and '{cb or 'none'}' are not two "
                   "different stated classes")
        if not (stated(a) and stated(b)):
            why.append("a window is unstated (§7.1), so class 3 cannot apply")
        else:
            why.append("the stated windows are identical")
        return _result("4", [], "; ".join(why))
    return _result(found[0][0], [c for c, _ in found[1:]],
                   " | ".join(f"class {c}: {e}" for c, e in found))


def _result(cls, others, evidence):
    return {"cls": cls, "class_label": CLASS_LABEL[cls], "rule": RULE[cls], "others": others,
            "evidence": evidence}


# ------------------------------------------------------------- labels and tags

def analysis_status(a, b) -> tuple[str, str]:
    reasons = []
    for r in (a, b):
        if _name(r) == Q420:
            reasons.append("RS Q420 was obtained after registration and is used only as an "
                           "exploratory cross-check (§13, 18 November 2026)")
        if _name(r) == Q1900 and r["window_start"].startswith("2024"):
            reasons.append("RS Q1900's 2024 column is compared as an exploratory check "
                           "(§13, 18 November 2026)")
    if reasons:
        return "exploratory", "; ".join(dict.fromkeys(reasons))
    if {_name(a), _name(b)} == {Q1900, Q1093} and a["window_start"][:4] == "2025" == \
            b["window_start"][:4]:
        return "pre-specified", ("§9.5.5 and §7.4: RS Q1900's January-October 2025 column "
                                 "against RS Q1093, State by State")
    return "pre-specified", "§7.1 comparison group"


def pre_identified(a, b) -> str:
    names = {_name(a): a, _name(b): b}
    tags = []
    ya, yb = a["window_start"][:4], b["window_start"][:4]
    if {Q1216, Q3467} == set(names) and ya == yb:
        tags.append(f"§7.4 / §9.5.2: Q1216 against Q3467, {ya} (guard)")
    if ITR2024 in names and names[ITR2024]["quantity"] == "tb_cases" and \
            names[ITR2024]["definition_class"] == "notified":
        other = b if names[ITR2024] is a else a
        if _name(other) == Q261 and other["window_start"][:4] == "2023":
            tags.append("§7.4: LS Q261 2023 against the India TB Report 2024")
        if _name(other) == Q1216 and other["window_start"][:4] == "2023":
            tags.append("§7.4: Q1216 2023 against the India TB Report 2024")
    if {Q1900, Q1093} == set(names) and ya == yb == "2025":
        tags.append("§7.4 / §9.5.5: Q1900 January-October 2025 against Q1093")
    if Q2511 in names:
        tags.append("§7.4: RS Q2511 (printed window January-October 2024, as on 19 November "
                    "2024; the OGD mirror was not obtained, so the answer-mirror comparison "
                    "is not run)")
    return "; ".join(tags)


def load_guard(path: Path = EX / "guard_ratios.csv") -> dict:
    with open(path, encoding="utf-8", newline="") as f:
        return {(r["year"], r["unit"]): r for r in csv.DictReader(f)}


def guard_note(a, b, guard) -> str:
    if not guard or {_name(a), _name(b)} != {Q1216, Q3467}:
        return ""
    year = a["window_start"][:4]
    if year != b["window_start"][:4]:
        return ""
    try:
        unit = coarsen(a["geography"])
    except KeyError:
        return ""
    g = guard.get((year, unit))
    if g is None:
        return f"guard ratio not available for {unit}, {year}"
    s = f"guard ratio Q1216/Q3467 {g['ratio']} ({unit}, {year}"
    s += ", ratio of the coarsened unit)" if unit != a["geography"] else ")"
    if g["outside_0_95_1_05"] == "yes":
        s += "; outside [0.95, 1.05]: a Q2 discrepancy of the guard (§9.5.2)"
    if g["label"]:
        s += f"; {g['label']}"
    return s


# ------------------------------------------------------------------ grouping

def _uf(n):
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)
    return find, union


def _entry_text(figs, field):
    return " | ".join(dict.fromkeys(str(f[field]) for f in figs))


PAIR_COLUMNS = [
    "group_key", "quantity", "geography", "scope", "related_by", "periods_intersect",
    "a_source", "a_value", "a_value_printed", "a_fig_ids", "a_qualifier", "a_interval",
    "a_definition_class", "a_window",
    "b_source", "b_value", "b_value_printed", "b_fig_ids", "b_qualifier", "b_interval",
    "b_definition_class", "b_window",
    "same_document", "agree", "class", "class_label", "rule", "other_classes", "evidence",
    "analysis", "analysis_reason", "pre_identified", "sector_part", "origin", "note",
]


def _side(prefix, figs):
    f0 = figs[0]
    return {
        f"{prefix}_source": f0["source_file"], f"{prefix}_value": f0["value"],
        f"{prefix}_value_printed": _entry_text(figs, "value_printed"),
        f"{prefix}_fig_ids": " ".join(f["fig_id"] for f in figs),
        f"{prefix}_qualifier": _entry_text(figs, "qualifier"),
        f"{prefix}_interval": " | ".join(dict.fromkeys(q1.fmt_iv(f["_iv"]) for f in figs)),
        f"{prefix}_definition_class": _entry_text(figs, "definition_class"),
        f"{prefix}_window": " | ".join(dict.fromkeys(_window_text(f) for f in figs)),
    }


def _pair_row(key, q, geo, scope, ea, eb, fig_pairs, failed, cumf, guard, sector, origin,
              corrected=False):
    bases = sorted({b for _, _, bs in fig_pairs for b in bs})
    agree = any(q1.overlap(f["_iv"], g["_iv"]) for f, g, _ in fig_pairs)
    rep = fig_pairs[0]
    pi = sorted({periods_intersect(f, g) for f, g, _ in fig_pairs}, reverse=True)
    row = {"group_key": key, "quantity": q, "geography": geo, "scope": scope,
           "related_by": "; ".join(bases), "periods_intersect": pi[0],
           **_side("a", ea), **_side("b", eb),
           "same_document": "yes" if ea[0]["source_file"] == eb[0]["source_file"] else "no",
           "agree": "yes" if agree else "no", "class": "", "class_label": "", "rule": "",
           "other_classes": "", "evidence": "", "origin": origin}
    if not agree:
        results = [(classify(f, g, failed, cumf, corrected), f, g) for f, g, _ in fig_pairs]
        results.sort(key=lambda t: CLASSES.index(t[0]["cls"]))
        best, f, g = results[0]
        others = list(dict.fromkeys(best["others"] + [r["cls"] for r, _, _ in results[1:]
                                                       if r["cls"] != best["cls"]]))
        row.update({"class": best["cls"], "class_label": best["class_label"],
                    "rule": best["rule"], "other_classes": " ".join(others),
                    "evidence": best["evidence"]})
        rep = (f, g, None)
    status, reason = analysis_status(rep[0], rep[1])
    notes = [n for n in (guard_note(rep[0], rep[1], guard),) if n]
    part = any(f["fig_id"] in sector for f in ea + eb)
    if part:
        notes.append("a figure is a part (sector column) of a total in its own table "
                     "(check 3, row layout); the §7.1 rules have no sector field")
    row.update({"analysis": status, "analysis_reason": reason,
                "pre_identified": pre_identified(rep[0], rep[1]),
                "sector_part": "yes" if part else "no", "note": "; ".join(notes)})
    return row


def compare(rows, failed, cumulative_failed=frozenset(), guard=None, sector=frozenset(),
            corrected: bool = False):
    """Pairs of entries per §7.1 and their §7.3 classes. Returns (pair rows, info).
    corrected=True (§13, 19 November 2026, post hoc): D1 spans end at window_end where it
    is printed; D2 printed sector parts (q1.sector_keyword) are not grouped (they are
    listed in info['sector_excluded'] with the keyword that matched)."""
    figs, info = [], {"no_interval": [], "unrelated_entry_pairs": 0, "groups": [],
                      "different_scope": [], "sector_excluded": []}
    for r in rows:
        if r["quantity"].startswith("other:"):
            continue
        kw = q1.sector_keyword(r) if corrected else ""
        if kw:
            info["sector_excluded"].append({"fig_id": r["fig_id"], "keyword": kw})
            continue
        iv = q1.interval(r)
        if iv is None:
            info["no_interval"].append(r["fig_id"])
            continue
        figs.append(dict(r, _iv=iv))
    by_qg = defaultdict(list)
    for f in figs:
        by_qg[(f["quantity"], f["geography"])].append(f)
    out = []
    for (q, geo), fs in sorted(by_qg.items()):
        # different scope, otherwise related: listed, not compared
        seen = set()
        for f, g in combinations(fs, 2):
            if f["scope"] != g["scope"]:
                bs = related(f, g, corrected)
                if bs:
                    a, b = sorted([f, g], key=lambda x: (x["scope"], x["source_file"], x["value"]))
                    k = (a["scope"], a["source_file"], a["value"], b["scope"], b["source_file"],
                         b["value"])
                    if k not in seen:
                        seen.add(k)
                        info["different_scope"].append({
                            "quantity": q, "geography": geo, "a_scope": a["scope"],
                            "a_source": a["source_file"], "a_value": a["value"],
                            "a_fig_id": a["fig_id"], "b_scope": b["scope"],
                            "b_source": b["source_file"], "b_value": b["value"],
                            "b_fig_id": b["fig_id"], "related_by": "; ".join(bs),
                            "intervals_overlap": "yes" if q1.overlap(a["_iv"], b["_iv"]) else "no"})
        by_scope = defaultdict(list)
        for f in fs:
            by_scope[f["scope"]].append(f)
        for scope, members in sorted(by_scope.items()):
            members.sort(key=lambda f: f["fig_id"])
            find, union = _uf(len(members))
            rel = {}
            for i, j in combinations(range(len(members)), 2):
                bs = related(members[i], members[j], corrected)
                if bs:
                    rel[(i, j)] = bs
                    union(i, j)
            comps = defaultdict(list)
            for i in range(len(members)):
                comps[find(i)].append(i)
            comps = [c for c in comps.values() if len(c) > 1]
            comps.sort(key=lambda c: (min(members[i]["window_start"] or "9999" for i in c),
                                      min(members[i]["fig_id"] for i in c)))
            for n, comp in enumerate(comps, 1):
                key = f"{q}|{geo}|{scope}|g{n:02d}"
                idx = {i: members[i] for i in comp}
                entries = defaultdict(list)
                for i in comp:
                    entries[(members[i]["source_file"], members[i]["value"])].append(i)
                ekeys = sorted(entries, key=lambda k: (k[0], Fraction(k[1])))
                pair_rows = []
                for ka, kb in combinations(ekeys, 2):
                    fp = []
                    for i in entries[ka]:
                        for j in entries[kb]:
                            bs = rel.get((min(i, j), max(i, j)))
                            if bs:
                                fp.append((idx[i], idx[j], bs))
                    if not fp:
                        info["unrelated_entry_pairs"] += 1
                        continue
                    pair_rows.append(_pair_row(
                        key, q, geo, scope, [idx[i] for i in entries[ka]],
                        [idx[j] for j in entries[kb]], fp, failed, cumulative_failed, guard,
                        sector, "§7.1 comparison group", corrected))
                out += pair_rows
                info["groups"].append(_group_summary(key, q, geo, scope, idx, entries,
                                                     pair_rows))
    return out, info


def _group_summary(key, q, geo, scope, idx, entries, pair_rows):
    values = sorted({Fraction(k[1]) for k in entries})
    windows = sorted({(f["window_label"] or (f"{f['window_start']}..{f['window_end'] or '-'}"
                       f"{'; as on ' + f['as_on'] if f['as_on'] else ''}")) for f in idx.values()})

    def tally(rows):
        vp = defaultdict(list)
        for r in rows:
            va, vb = Fraction(r["a_value"]), Fraction(r["b_value"])
            if va == vb:
                continue
            vp[tuple(sorted((va, vb)))].append(r["class"] or "agree")
        counts = defaultdict(int)
        noted = 0
        for k, cl in vp.items():
            dis = sorted([c for c in cl if c != "agree"], key=CLASSES.index)
            counts[dis[0] if dis else "agree"] += 1
            noted += len(set(cl)) > 1
        order = ["agree"] + list(CLASSES)
        s = "; ".join(f"{c}: {counts[c]}" for c in order if counts[c])
        return s + (f" ({noted} with other classes noted)" if noted else "")
    pre = [r for r in pair_rows if r["analysis"] == "pre-specified"]
    return {"group_key": key, "quantity": q, "geography": geo, "scope": scope,
            "windows_or_labels": " | ".join(windows), "n_figures": len(idx),
            "n_entries": len(entries), "n_documents": len({k[0] for k in entries}),
            "n_distinct_values": len(values), "min_value": q1.fmt(values[0]),
            "max_value": q1.fmt(values[-1]), "n_entry_pairs": len(pair_rows),
            "n_entry_pairs_disagree": sum(r["agree"] == "no" for r in pair_rows),
            "value_pairs_by_class": tally(pair_rows),
            "value_pairs_by_class_prespecified": tally(pre),
            "n_entry_pairs_exploratory": len(pair_rows) - len(pre)}


# --------------------------------------------------------------- §9.2 named list

def named_list_rows(inventory, failed, path: Path = EX / "named_list_check.csv"):
    """The §9.2 named-list counts that differ from the CTD table, classified by §7.3."""
    with open(path, encoding="utf-8", newline="") as f:
        nl = [r for r in csv.DictReader(f) if r["match"] == "no" and r["state"] != "TOTAL"]
    ctd = {r["geography"]: r for r in inventory
           if r["fig_id"].startswith("CTD100.") and r["table_id"] == "State | Total District"}
    out = []
    for r in nl:
        a = dict(ctd[r["state"]])
        a["_iv"] = q1.interval(a)
        b = {"fig_id": f"named-list:{r['state']}", "quantity": "districts_selected",
             "value": r["named_list_rows"], "value_printed": r["named_list_rows"],
             "qualifier": "exact", "unit": "districts", "definition_class": "",
             "definition_verbatim": "rows of the named list (Annexure-I of the D.O. letter)",
             "scope": a["scope"], "window_label": "", "window_start": "", "window_end": "",
             "as_on": "", "geography": r["state"],
             "source_file": "data_raw/official/TB_Elimination_Campaign.pdf"}
        b["_iv"] = q1.interval(b)
        row = _pair_row(f"named-list|districts_selected|{r['state']}", "districts_selected",
                        r["state"], a["scope"], [a], [b], [(a, b, ["§9.2 named list"])], failed,
                        frozenset(), None, frozenset(),
                        "§9.2 named list (data/extracted/named_list_check.csv); the "
                        "named-list count is a count of list rows, not a printed figure")
        row["pre_identified"] = "§9.2: named list against the CTD table"
        out.append(row)
    return out


# ---------------------------------------------------------- §7.5 quality studies

Z = statistics.NormalDist().inv_cdf(0.975)


def wilson(x: int, n: int) -> tuple[float, float]:
    """Wilson score interval (§8.2) for x of n."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = x / n
    z2 = Z * Z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


INDICATORS = {
    "C1": ("diagnosed among people tested", "diagnosed", "tested"),
    "C2": ("tested among people screened", "tested", "screened"),
    "C3": ("tested among people with presumptive TB", "tested", "presumptive"),
    "C4": ("number needed to screen (people screened per person diagnosed)", "screened",
           "diagnosed"),
}
# where each study's national counts and its published indicators are printed
COUNTS = {"GHA2023": ("GHA2023SM", "S1 Annex", "INDIA"),
          "PGPH2025": ("PGPH2025", "Table 2", "Total")}
PUBLISHED = {"GHA2023": ("GHA2023", "Table 1", "INDIA"),
             "PGPH2025": ("PGPH2025", "Table 2", "Total")}
# the printed column that states each common indicator (its own stated denominator)
PUBLISHED_COLUMN = {
    ("GHA2023", "C1"): "pct_diagnosed", ("GHA2023", "C2"): "pct_tested",
    ("GHA2023", "C4"): "nns",
    ("PGPH2025", "C1"): "pct_diagnosed", ("PGPH2025", "C3"): "pct_tested",
    ("PGPH2025", "C4"): "nns",
}
SETTING = {"GHA2023": "national programme aggregates, first ACF cycle 2021 (S1 Annex)",
           "PGPH2025": "field cohort of 30 randomly sampled districts, January-September "
                       "2023 (Table 2)"}

QS_COLUMNS = ["study", "indicator", "common_definition", "published_value",
              "published_locator", "published_stated_denominator", "numerator", "numerator_n",
              "denominator", "denominator_n", "counts_locator", "recomputable", "recomputed",
              "ci95_low", "ci95_high", "published_within_rounding", "reason", "setting"]


def _row_of(quality, study, table, label, quantity):
    for r in quality:
        key = r["row_label"] if r["row_label"] else r["row_group"]
        if (r["study"], r["table_id"], r["quantity"]) == (study, table, quantity) and \
                key == label:
            return r
    return None


def quality_reconciliation(quality) -> list[dict]:
    out = []
    for study in ("GHA2023", "PGPH2025"):
        cs, ct, cl = COUNTS[study]
        ps, pt, pl = PUBLISHED[study]
        for ind, (definition, num, den) in INDICATORS.items():
            row = {"study": study, "indicator": ind, "common_definition": definition,
                   "setting": SETTING[study]}
            col = PUBLISHED_COLUMN.get((study, ind))
            pub = _row_of(quality, ps, pt, pl, col) if col else None
            if pub:
                row.update({"published_value": pub["printed_value"],
                            "published_locator": f"{pub['study']} {pub['locator']}",
                            "published_stated_denominator": "; ".join(
                                x for x in (pub["denominator_stated"],
                                            pub["denominator_methods"]) if x)
                            or "not stated"})
            else:
                row.update({"published_value": "not published",
                            "published_locator": "", "published_stated_denominator": ""})
            n = _row_of(quality, cs, ct, cl, num)
            d = _row_of(quality, cs, ct, cl, den)
            row.update({"numerator": num, "denominator": den,
                        "counts_locator": f"{cs} {ct}, row '{cl}'"})
            if n is None or d is None:
                missing = " and ".join(q for q, r in ((num, n), (den, d)) if r is None)
                row.update({"recomputable": "no", "numerator_n": n["value"] if n else "",
                            "denominator_n": d["value"] if d else "", "recomputed": "",
                            "ci95_low": "", "ci95_high": "", "published_within_rounding": "",
                            "reason": f"not recomputable: the study's tables print no "
                                      f"{missing} count ({cs} {ct} and the other tables read)"})
                out.append(row)
                continue
            x, m = int(n["value"]), int(d["value"])
            if ind == "C4":
                lo, hi = wilson(m, x)           # diagnosed of screened
                val, cil, cih = x / m, (1 / hi), (math.inf if lo == 0 else 1 / lo)
                fmtv = f"{val:.1f}"
                fmtl, fmth = f"{cil:.1f}", ("inf" if cih == math.inf else f"{cih:.1f}")
            else:
                lo, hi = wilson(x, m)
                val = 100 * x / m
                fmtv, fmtl, fmth = f"{val:.4f}", f"{100 * lo:.4f}", f"{100 * hi:.4f}"
            within = ""
            if pub:
                piv = q1.interval({"value": pub["value"], "value_printed": pub["printed_value"],
                                   "qualifier": "exact", "unit": pub["unit"]})
                within = "yes" if piv[0] <= Fraction(x, m) * (1 if ind == "C4" else 100) <= piv[1] \
                    else "no"
            row.update({"recomputable": "yes", "numerator_n": str(x), "denominator_n": str(m),
                        "recomputed": fmtv, "ci95_low": fmtl, "ci95_high": fmth,
                        "published_within_rounding": within,
                        "reason": ("recomputed on the common definition; Wilson interval (§8.2)"
                                   + ("; NNS interval = reciprocals of the Wilson bounds of "
                                      "diagnosed / screened" if ind == "C4" else "")
                                   + ("" if pub else "; the study publishes no value for this "
                                      "indicator"))})
            out.append(row)
    return out


def load_quality(path: Path = EX / "quality_studies.csv") -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------------- run

def _write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def pre_identified_status(pairs, guard, corrected: bool = False) -> list[dict]:
    sector_note = ("the report's Public and Private columns are not grouped (D2)" if corrected
                   else "includes the report's Public and Private columns (sector_part = yes)")
    def stats(rows):
        dis = [r for r in rows if r["agree"] == "no"]
        c = defaultdict(int)
        for r in dis:
            c[r["class"]] += 1
        return len(rows), len(dis), "; ".join(f"{k}: {c[k]}" for k in CLASSES if c[k])
    items = [
        ("RS Q2511 (answer against its OGD mirror)", "§7.4",
         lambda r: False, "not run",
         "the OGD mirror was not obtained, so its field label cannot be compared; the answer "
         "prints 'Notification in 2024 (Jan- Oct)' with '*As on 19th Nov 2024' (§13, 19 "
         "November 2026)"),
        ("RS Q2511 against the other sources in its §7.1 groups", "§7.4; §7.1",
         lambda r: "Q2511" in r["pre_identified"], "run", "window as printed"),
        ("RS Q1900 January-October 2025 against RS Q1093", "§7.4; §9.5.5",
         lambda r: "Q1900 January-October 2025 against Q1093" in r["pre_identified"], "run",
         "pre-specified"),
        ("LS Q261 2023 against the India TB Report 2024", "§7.4",
         lambda r: "LS Q261 2023" in r["pre_identified"], "run",
         sector_note),
        ("Q1216 against Q3467, 2023 and 2024 (guard)", "§7.4; §9.5.2",
         lambda r: "Q1216 against Q3467" in r["pre_identified"], "run",
         "guard ratios attached in the note column"),
        ("Q1216 2023 against the India TB Report 2024", "§7.4",
         lambda r: "Q1216 2023 against the India TB Report" in r["pre_identified"], "run",
         sector_note),
        ("Named list against the CTD table", "§9.2",
         lambda r: r["pre_identified"].startswith("§9.2"), "run", "four States differ"),
        ("RS Q420 (2025 full year) against Q1216 (exploratory)", "§13 (18 November 2026)",
         lambda r: Q420 in r["a_source"] + r["b_source"] and Q1216 in r["a_source"] + r["b_source"]
         and r["a_window"].startswith("2025-01-01..2025-12-31")
         and r["b_window"].startswith("2025-01-01..2025-12-31"), "run", "exploratory"),
        ("RS Q1900 2024 against Q1216 2024 (exploratory)", "§13 (18 November 2026)",
         lambda r: Q1900 in r["a_source"] + r["b_source"] and Q1216 in r["a_source"] + r["b_source"]
         and r["a_window"].startswith("2024-01-01..2024-12-31")
         and r["b_window"].startswith("2024-01-01..2024-12-31"), "run", "exploratory"),
    ]
    out = []
    for item, clause, sel, run, note in items:
        n, nd, cls = stats([r for r in pairs if sel(r)])
        out.append({"item": item, "plan_clause": clause, "run": run if n or run == "not run"
                    else "no pairs formed", "n_entry_pairs": n, "n_disagree": nd,
                    "classes": cls, "note": note})
    g_out = [g for g in guard.values() if g["outside_0_95_1_05"] == "yes"]
    out.append({"item": "Guard States outside [0.95, 1.05] (per coarsened unit and year)",
                "plan_clause": "§9.5.2; §7.4", "run": "recorded in the guard",
                "n_entry_pairs": len(g_out), "n_disagree": len(g_out),
                "classes": "", "note": "late-report-consistent: " + str(
                    sum(g["label"] == "late-report-consistent" for g in g_out))})
    return out


# ------------------------------------------------ candidates the rules cannot group

# Candidate discrepancies named before this analysis whose figures the §7.1 rules may not
# put in one group. Whether each pair is formed, and why not, is computed from the fields.
NOT_FORMED_CANDIDATES = [
    ("GHA2023: national ACF-diagnosed, S1 Annex against S2 Annex (and the Results sentence)",
     ["GHA2023SM.s1.india.number-diagnosed-among-tested.tb_cases",
      "GHA2023SM.s2.india.tb-acf-cases-diagnosed-among-tested-reported-as-acf-detected.tb_cases",
      "GHA2023.freq.sentence.tb_cases"]),
    ("PIB 2105575: 3.57 lakh (highlight bullet) against 3.5 lakh (body)",
     ["PIB2105575.p003.s-since-the-launch-of-100-day-3-57-lakh.tb_cases",
      "PIB2105575.p002.s-over-3-5-lakh-tb-patients.tb_cases"]),
]
NOT_FORMED_COLUMNS = ["candidate", "a_fig_id", "a_value_printed", "b_fig_id", "b_value_printed",
                      "formed_registered", "formed_corrected", "reason"]


def _why_not(a, b) -> str:
    why = []
    for f in ("quantity", "geography", "scope"):
        if a[f] != b[f]:
            why.append(f"{f} differs ('{a[f]}' / '{b[f]}')")
    if not (stated(a) and stated(b)):
        why.append("a window is unstated (" + "; ".join(
            f"{r['fig_id']}: {'stated' if stated(r) else 'unstated'}" for r in (a, b)) + ")")
    if not (a["window_label"] and a["window_label"] == b["window_label"]):
        why.append(f"window labels are not identical and non-blank ('{a['window_label']}' / "
                   f"'{b['window_label']}')")
    if a["definition_class"] != b["definition_class"]:
        why.append(f"definition classes '{a['definition_class']}' / '{b['definition_class']}'")
    return "; ".join(why)


def not_formed(inventory) -> list[dict]:
    """The descriptive 'not formed' table: pairs the §7.1 rules do not group, with the
    reason, and the national totals 9.02 crore / 3.01 lakh, searched for in the inventory."""
    by_id = {r["fig_id"]: r for r in inventory}
    out = []
    for cand, ids in NOT_FORMED_CANDIDATES:
        for x, y in combinations(ids, 2):
            a, b = by_id[x], by_id[y]
            same = all(a[f] == b[f] for f in ("quantity", "geography", "scope"))
            fr = same and bool(related(a, b))
            fc = same and bool(related(a, b, corrected=True))
            out.append({"candidate": cand, "a_fig_id": x, "a_value_printed": a["value_printed"],
                        "b_fig_id": y, "b_value_printed": b["value_printed"],
                        "formed_registered": "yes" if fr else "no",
                        "formed_corrected": "yes" if fc else "no",
                        "reason": "" if fr and fc else _why_not(a, b)})
    hits = [r["fig_id"] for r in inventory
            if ("9.02" in r["value_printed"] and "cr" in r["value_printed"].lower())
            or ("3.01" in r["value_printed"] and "lakh" in r["value_printed"].lower())]
    out.append({"candidate": "national campaign totals 9.02 crore screened / 3.01 lakh",
                "a_fig_id": " ".join(hits), "a_value_printed": "", "b_fig_id": "",
                "b_value_printed": "", "formed_registered": "no", "formed_corrected": "no",
                "reason": ("found in the inventory: " + " ".join(hits)) if hits else
                ("not found in any include = yes official source: no figure printed as "
                 "9.02 crore or 3.01 lakh is in data/figures_inventory.csv")})
    return out


# ------------------------------------------------------- the two sets and their summary

def _class_counts(pairs) -> dict:
    c = defaultdict(int)
    for r in pairs:
        c[r["class"] or "agree"] += 1
    return c


def summary_rows(reg, cor) -> list[dict]:
    rows = []

    def add(metric, a, b):
        rows.append({"metric": metric, "registered": a, "corrected": b})
    for name, sel in (("all", lambda r: True),
                      ("pre-specified", lambda r: r["analysis"] == "pre-specified"),
                      ("exploratory", lambda r: r["analysis"] == "exploratory")):
        pr = [r for r in reg["pairs"] if sel(r)]
        pc = [r for r in cor["pairs"] if sel(r)]
        add(f"Q2 entry pairs ({name})", len(pr), len(pc))
        cr, cc = _class_counts(pr), _class_counts(pc)
        for k in ["agree"] + list(CLASSES):
            add(f"Q2 {name}: {'agree' if k == 'agree' else 'class ' + k}", cr[k], cc[k])
    add("Q2 comparison groups formed (§7.1)", len(reg["info"]["groups"]),
        len(cor["info"]["groups"]))
    add("Q2 named-list rows (§9.2)", sum(r["origin"].startswith("§9.2") for r in reg["pairs"]),
        sum(r["origin"].startswith("§9.2") for r in cor["pairs"]))
    add("Q2 different-scope pairs listed", len(reg["info"]["different_scope"]),
        len(cor["info"]["different_scope"]))
    add("Q2 sector-part figures not grouped (D2)", 0, len(cor["info"]["sector_excluded"]))
    add("Q2 same-group entry pairs not directly related", reg["info"]["unrelated_entry_pairs"],
        cor["info"]["unrelated_entry_pairs"])
    for check in (q1.CHECK1, q1.CHECK2, q1.CHECK3, q1.CHECK4):
        sr = q1.summary(reg["checks"]).get(check, {"yes": 0, "no": 0, "n/a": 0})
        sc = q1.summary(cor["checks"]).get(check, {"yes": 0, "no": 0, "n/a": 0})
        for k, lab in (("yes", "pass"), ("no", "fail"), ("n/a", "n/a")):
            add(f"Q1 check {check}: {lab}", sr[k], sc[k])
    return rows


def run_set(inv, quality_rows, guard, corrected: bool) -> dict:
    checks_all = q1.run_checks(inv, quality_rows, corrected=corrected)
    checks, _ = q1.split_other(checks_all)
    failed = q1.failures(checks)
    cumf = frozenset(frozenset(r["_figs"]) for r in checks
                     if r["check"] == q1.CHECK4 and r["pass"] == "no")
    sector = frozenset() if corrected else q1.sector_parts(checks_all)
    pairs, info = compare(inv, failed, cumf, guard, sector, corrected=corrected)
    pairs += named_list_rows(inv, failed)
    return {"pairs": pairs, "info": info, "checks": checks,
            "pre": pre_identified_status(pairs, guard, corrected)}


def run(write: bool = True) -> dict:
    inv = q1.load_inventory()
    guard = load_guard()
    qrows = q1.load_quality()
    reg = run_set(inv, qrows, guard, corrected=False)
    cor = run_set(inv, qrows, guard, corrected=True)
    quality = quality_reconciliation(load_quality())
    nf = not_formed(inv)
    summ = summary_rows(reg, cor)
    if write:
        for res, suf in ((reg, ""), (cor, "_corrected")):
            info = res["info"]
            _write(OUT / f"q2_discrepancies{suf}.csv", PAIR_COLUMNS, res["pairs"])
            _write(OUT / f"q2_groups{suf}.csv", list(info["groups"][0].keys()), info["groups"])
            _write(OUT / f"q2_different_scope{suf}.csv", list(info["different_scope"][0].keys()),
                   info["different_scope"])
            _write(OUT / f"q2_pre_identified{suf}.csv", list(res["pre"][0].keys()), res["pre"])
        _write(OUT / "q2_sector_parts_corrected.csv", ["fig_id", "keyword"],
               cor["info"]["sector_excluded"])
        _write(OUT / "q2_not_formed.csv", NOT_FORMED_COLUMNS, nf)
        _write(OUT / "q2_summary_registered_vs_corrected.csv",
               ["metric", "registered", "corrected"], summ)
        _write(OUT / "q2_quality_studies.csv", QS_COLUMNS, quality)
    return {"pairs": reg["pairs"], "info": reg["info"], "pre": reg["pre"],
            "checks": reg["checks"], "corrected": cor, "quality": quality,
            "not_formed": nf, "summary": summ}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = run()
    for name, r in (("registered", res), ("corrected", res["corrected"])):
        c = _class_counts(r["pairs"])
        print(f"{name}: groups {len(r['info']['groups'])}; entry pairs {len(r['pairs'])}; "
              + "; ".join(f"{k}: {c[k]}" for k in ["agree"] + list(CLASSES) if c[k]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
