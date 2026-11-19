"""Comparability layer for the Q4 outcome tables (analysis plan §9.5; Task 4).

`comparable(a, b)` judges whether two extracted counts may be compared. It requires:

1. Same quantity, same words, same source (§9.5, ruling A1). The quantity wording is the
   phrase "TB cases reported" / "TB cases notified", found in the printed column heading
   or, if the heading carries only a period (Q261: "2024 (Jan- Oct)"), in the printed
   table title. Wording is compared after whitespace and case normalisation (the
   typographic dash and the asterisk footnote mark are also normalised). The source is the
   stated data source ("Ni-kshay", "Ni-kshay portal" -> ni-kshay). Public plus private
   coverage is not required (a stated limitation, §9.5.3 (a)).
2. Same window: same start and end calendar month/day, and the same number of calendar
   months. Length is counted in calendar months, not days, because 2024 is a leap year
   (Jan-Dec 2024 has 366 days, Jan-Dec 2025 has 365) and the plan treats them as the same
   window (§9.5.1 (b)).
3. Cut-off (§9.5): either each as-on date within 60 days after its own window end, or,
   for a single-document contrast, one shared as-on date within 60 days after the end of
   the later window. An as-on date never precedes the end of the window it describes.

Unstated cut-off (§9.5.3): where a source states no as-on date (as_on_basis "bounded"),
the cut-off cannot be later than the answer date, so the answer date is the bound, and
the condition is judged on that bound (Q261: 43 days; Q1093: 39 days). §9.5.3 (c) states
that the condition is met "under either reading" (stated date read as the cut-off, or the
bound), so the bound is the weaker reading and is the one implemented here.

Pairs: `full_year_pairs` (primary contrast, §9.5.1) and `jan_oct_pairs` (S8, §9.5.3) build
per-unit pairs of counts over units already coarsened (§9.4; counts of members summed).
A unit missing on either side is left out and listed with its reason (§10.4). Nothing here
computes a regression, excess or any Q result. Standard library only.
"""
from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "data/extracted"
MAX_LAG_DAYS = 60

# Row column ids (data/extracted/pq_*.csv).
FULL_YEAR_COLS = ("2024_notified", "2025_notified")
JAN_OCT_COLS = ("2024_jan_oct_reported", "2025_jan_oct_reported")

_QUANTITY = re.compile(r"\btb\s+cases?\s+(reported|notified)\b")


def _d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x))


def _norm(s) -> str:
    s = str(s or "").lower().replace("–", "-").replace("—", "-").replace("*", " ")
    return re.sub(r"\s+", " ", s).strip(" .:;,")


_PERIOD_WORDS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                 "dec", "january", "february", "march", "april", "june", "july", "august",
                 "september", "october", "november", "december", "since", "to", "for"}


def _phrase(text) -> str | None:
    m = _QUANTITY.search(_norm(text))
    return re.sub(r"\s+", " ", m.group(0).replace("cases", "case")) if m else None


def _period_only(heading: str) -> bool:
    """True if the heading is only years, months, ranges and punctuation (Q261: '2024
    (Jan- Oct)'): no quantity words such as number, beneficiaries, cases, notified."""
    words = re.findall(r"[a-z]+", _norm(heading))
    return bool(words) and all(w in _PERIOD_WORDS for w in words)


def quantity_wording(row: dict) -> str:
    """The normalised quantity phrase ("tb case reported|notified"; case/cases are one
    form, grammatical number is not a different quantity). Taken from the heading; only
    if the heading is period-only is the table title used. Otherwise the normalised
    heading, so no other column inherits the title's phrase."""
    heading = row.get("column_heading")
    p = _phrase(heading)
    if p:
        return p
    if _period_only(heading or ""):
        p = _phrase(row.get("table_title"))
        if p:
            return p
    return _norm(heading)


def source_name(row: dict) -> str:
    s = re.sub(r"\(.*?\)", "", _norm(row.get("data_source")))
    s = re.sub(r"\bportal\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _months(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def _same_window(a: dict, b: dict) -> tuple[bool, str]:
    sa, ea = _d(a["window_start"]), _d(a["window_end"])
    sb, eb = _d(b["window_start"]), _d(b["window_end"])
    if (sa.month, sa.day) != (sb.month, sb.day) or (ea.month, ea.day) != (eb.month, eb.day):
        return False, f"windows differ in calendar span ({sa}..{ea} vs {sb}..{eb})"
    if _months(sa, ea) != _months(sb, eb):
        return False, "windows differ in length"
    return True, ""


def effective_as_on(row: dict) -> date:
    """The stated as-on date or, where none is stated ("bounded"), the answer date, the
    upper bound of the cut-off (§9.5.3)."""
    basis = str(row.get("as_on_basis", "")).strip()
    if basis == "bounded":
        if not row.get("answer_date"):
            raise ValueError("bounded as_on with no answer date")
        return _d(row["answer_date"])
    if basis == "stated":
        if not row.get("as_on"):
            raise ValueError("stated as_on missing")
        return _d(row["as_on"])
    raise ValueError(f"unknown as_on_basis {basis!r}")


def _lag_ok(as_on: date, window_end: date) -> bool:
    return 0 <= (as_on - window_end).days <= MAX_LAG_DAYS


def comparable(a: dict, b: dict) -> tuple[bool, str]:
    """(True, "") if the two counts may be compared, else (False, reason)."""
    wa, wb = quantity_wording(a), quantity_wording(b)
    if wa != wb:
        return False, f"different wording ({wa!r} vs {wb!r})"
    sa, sb = source_name(a), source_name(b)
    if not sa or sa != sb:
        return False, f"different or unstated source ({sa!r} vs {sb!r})"
    ok, why = _same_window(a, b)
    if not ok:
        return False, why
    ea, eb = _d(a["window_end"]), _d(b["window_end"])
    asa, asb = effective_as_on(a), effective_as_on(b)
    if _lag_ok(asa, ea) and _lag_ok(asb, eb):
        return True, ""
    # single-document contrast: one shared stated as-on date (§9.5)
    same_doc = (a.get("source_file") and a.get("source_file") == b.get("source_file")
                and str(a.get("as_on_basis")) == "stated" == str(b.get("as_on_basis"))
                and asa == asb)
    if same_doc:
        if _lag_ok(asa, max(ea, eb)):
            return True, ""
        return False, (f"shared as-on {asa} is {(asa - max(ea, eb)).days} days after the later "
                       f"window end (limit {MAX_LAG_DAYS})")
    return False, (f"as-on beyond {MAX_LAG_DAYS} days after its own window end "
                   f"({asa} vs {ea}; {asb} vs {eb})")


def _unit_rows(rows, col: str) -> dict:
    """unit -> member rows of that column (combined members are summed, §9.4)."""
    out = {}
    for r in rows:
        if r.get("column") != col or str(r.get("is_total", "no")) == "yes":
            continue
        if not str(r.get("value", "")).strip():
            continue
        out.setdefault(r["coarse_unit"], []).append(r)
    return out


def _int(v) -> int:
    f = float(str(v).strip())
    if f != int(f):
        raise ValueError(f"count is not an integer: {v!r}")
    return int(f)


def _pairs(rows, cols):
    rows = list(rows)
    ra, rb = (_unit_rows(rows, c) for c in cols)
    out, dropped = {}, []
    for u in sorted({r["coarse_unit"] for r in rows if r.get("column") in cols}):
        if u not in ra or u not in rb:
            dropped.append((u, f"missing in {cols[0] if u not in ra else cols[1]}"))
            continue
        bad = next(((x, y) for x in ra[u] for y in rb[u] if not comparable(x, y)[0]), None)
        if bad:
            dropped.append((u, "not comparable: " + comparable(*bad)[1]))
            continue
        out[u] = (sum(_int(r["value"]) for r in ra[u]), sum(_int(r["value"]) for r in rb[u]))
    return out, dropped


def full_year_pairs(rows) -> tuple[dict, list]:
    """(pairs, dropped): pairs is unit -> (N2024, N2025) from the full-year 'notified'
    columns of Q1216 (§9.5.1); dropped lists (unit, reason) for every unit left out
    (§10.4). Comparability is checked for every member row of a coarsened unit."""
    return _pairs(rows, FULL_YEAR_COLS)


def jan_oct_pairs(rows) -> tuple[dict, list]:
    """(pairs, dropped) for S8: Jan-Oct 2024 (LS Q261) against Jan-Oct 2025 (RS Q1093)."""
    return _pairs(rows, JAN_OCT_COLS)


# Stated data source of each Q4 pq document: the note printed with each table
# ("Data Source: Ni-kshay" in Q1216 and Q261; "Data source: Ni-kshay portal" in Q1093),
# as read in the re-check of data/extracted/q4_source_checks.csv (§9.5.4).
DATA_SOURCE = {
    "data_raw/pq/AU1216_WFw8li.pdf": "Ni-kshay",
    "data_raw/pq/AS261_lP7nYE.pdf": "Ni-kshay",
    "data_raw/pq/AU1093_dH065I.pdf": "Ni-kshay portal",
    # data_raw/pq/AU3467_mVGJLD.pdf (RS Q3467) is deliberately absent: the PDF prints no
    # "Data source:" line (the only mention is in body text), so its source is unstated
    # and comparable() refuses its rows. The guard is a ratio and never calls comparable().
}


def load_pq(name: str) -> list[dict]:
    """Read data/extracted/<name>.csv and attach `data_source` (DATA_SOURCE)."""
    with open(EX / f"{name}.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["data_source"] = DATA_SOURCE.get(r["source_file"], "")
    return rows
