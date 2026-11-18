# Copied from hssling/india-state-tb-score (MIT), src/extract/annex.py, commit 05bcaa7; modified: Cell, split_cells, pct_only and split_name kept; the row assembler rewritten to keep each row's printed label (the label rule of analysis plan §9.2 maps it, not the parser), to read past a national row printed before the last State row, and to place the cells of a row that prints fewer cells than the header by their x positions
"""State/UT annexure rows of the India TB Reports.

A row is a printed label followed by its cells. Labels wrapped over two or three lines
are rejoined ("Andaman & Nicobar" / values / "Islands"). The label is kept as printed;
`labels.resolve_or_list` maps it later. Wrapped percentages that sit on their own line
are skipped (their counts are already in the row).

pdfplumber may be imported only under src/extract/.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import pdfplumber

from src import states
from src.extract import pdftext


class Cell(NamedTuple):
    n: str | None  # the count as printed; None for a blank cell
    pct: str | None
    raw: str


# "(NA)" is printed as the percentage of a zero denominator: "0 (NA)".
_PCT = re.compile(r"^\(\s*(?:-?\d+(?:\.\d+)?\s*%?|NA)\s*\)$")
_NUM = re.compile(r"^\*?\d[\d,]*(?:\.\d+)?\*?$")
_TOKEN = re.compile(r"\(\s*(?:-?\d+(?:\.\d+)?\s*%?|NA)\s*\)|\S+")
BLANKS = frozenset({"NA", "-", "–", "#N/A", "#DIV/0!"})


def split_cells(text: str) -> list[Cell]:
    """Cells of the value part of a row: a count with an optional "(pct)" after it, a
    blank marker, or a lone "(pct)" without a count (a blank count)."""
    out: list[Cell] = []
    for tok in _TOKEN.findall(text):
        if _PCT.match(tok):
            last = out[-1] if out else None
            if last is not None and last.n is not None and last.pct is None:
                out[-1] = Cell(last.n, tok, f"{last.raw} {tok}")
            else:
                out.append(Cell(None, tok, tok))
        elif tok in BLANKS:
            out.append(Cell(None, None, tok))
        elif _NUM.match(tok):
            out.append(Cell(tok, None, tok))
        else:
            raise ValueError(f"unexpected token {tok!r} in row {text!r}")
    return out


def pct_only(cs: list[Cell]) -> bool:
    """True for a line of wrapped percentages (no count, no blank marker)."""
    return bool(cs) and all(c.n is None and c.pct is not None and c.raw == c.pct
                            for c in cs)


_VALUE_START = re.compile(r"^(?:\*?\d|\(|#)")


def _is_value(tok: str) -> bool:
    return bool(_VALUE_START.match(tok)) or tok in BLANKS


def split_name(line: str) -> tuple[list[str], str]:
    """Leading words before the first value-like token, and the rest."""
    toks = line.split()
    k = next((j for j, t in enumerate(toks) if _is_value(t)), len(toks))
    return toks[:k], " ".join(toks[k:])


# ---------------------------------------------------------------- label prefixes

def _norm(s: str) -> str:
    return states.normalize(re.sub(r"[^\w&\s]", " ", s))


_KEYS = sorted({states.normalize(k) for k in states.spellings(2019)}
               | {states.normalize(k) for k in states.spellings(2023)})


def is_prefix(name: str) -> bool:
    """The words are a known State/UT spelling or the start of one."""
    n = _norm(name)
    return bool(n) and any(k == n or k.startswith(n + " ") for k in _KEYS)


def is_complete(name: str) -> bool:
    return _norm(name) in _KEYS


@dataclass
class Row:
    label: str
    cells: list[Cell] | None
    lines: list[str] = field(default_factory=list)


def assemble_rows(lines: list[str], ncells: int, national: str,
                  footer: re.Pattern | None = None) -> list[Row]:
    """Rows of one table page in printed order, the national row included.

    Lines before the first State/UT label are header lines. A line is a new row (a
    label with or without its values), a continuation of the current label, the
    current row's values, or a line of wrapped percentages. The table ends at the
    first line that is none of these (a note or a page footer)."""
    rows: list[Row] = []
    cur: Row | None = None
    started = False
    for raw in lines:
        line = footer.sub(" ", raw).strip() if footer is not None else raw.strip()
        if not line:
            continue
        words, rest = split_name(line)
        name = " ".join(words)
        if not started:
            if words and (is_prefix(name) or name == national):
                started = True
            else:
                continue
        try:
            cs = split_cells(rest) if rest else []
        except ValueError:
            break                                   # a note: the table has ended
        has_values = bool(cs) and not pct_only(cs)
        if words:
            joined = (cur.label + " " + name) if cur is not None else name
            # a continuation of the current label: "Andaman & Nicobar 580 .." /
            # "Islands"; "Dadra And Nagar" / "Haveli And Daman 980 .." / "And Diu";
            # "Dadra and Nagar Haveli and 1100 .." / "Daman and Diu"
            if cur is not None and is_prefix(joined) and (
                    (not has_values and (not is_complete(cur.label)
                                         or not is_prefix(name)))
                    or (has_values and cur.cells is None
                        and not is_complete(cur.label))):
                cur.label = joined
                cur.lines.append(raw)
                if has_values:
                    cur.cells = cs
                continue
            if not has_values and not is_prefix(name) and name != national:
                break                               # a note after the table
            cur = Row(name, cs if has_values else None, [raw])
            rows.append(cur)
            continue
        if has_values:
            if cur is None or cur.cells is not None:
                break                               # a page number after the table
            cur.cells = cs
            cur.lines.append(raw)
    for r in rows:
        if r.cells is None:
            raise ValueError(f"row {r.label!r} has no values: {r.lines!r}")
    return rows


# ------------------------------------------------- cells placed by x position

_NUMTOK = re.compile(r"^(?:\*?\d[\d,]*(?:\.\d+)?\*?|\(\s*-?\d+(?:\.\d+)?\s*%?\s*\)|NA|-)$")


def positioned_cells(pdf: Path, page: int, label: str, ncells: int,
                     full_rows: list[str]) -> list[Cell]:
    """Cells of a row that prints fewer cells than the header (a blank cell left
    empty), placed by x position: each column's centre is the median centre of that
    cell in rows printing all `ncells` cells. Only for pages whose text is upright."""
    with pdfplumber.open(pdf) as doc:
        pg = doc.pages[page - 1]
        if pdftext._is_rotated(pg.chars):
            raise ValueError("positioned cells need an upright page")
        words = pg.extract_words()

    def line_of(first_word: str):
        hits = [w for w in words if w["text"] == first_word]
        out = []
        for h in hits:
            same = sorted((w for w in words if abs(w["top"] - h["top"]) < 2.5),
                          key=lambda w: w["x0"])
            out.append(same)
        return out

    centres: list[list[float]] = [[] for _ in range(ncells)]
    for lab in full_rows:
        for ln in line_of(lab.split()[0]):
            nums = [w for w in ln if _NUMTOK.match(w["text"])]
            if len(nums) == ncells:
                for k, w in enumerate(nums):
                    centres[k].append((w["x0"] + w["x1"]) / 2)
    med = [sorted(c)[len(c) // 2] for c in centres]
    target = [ln for ln in line_of(label.split()[0])]
    if len(target) != 1:
        raise ValueError(f"row {label!r} found {len(target)} times on page {page}")
    nums = [w for w in target[0] if _NUMTOK.match(w["text"])]
    out: list[Cell | None] = [None] * ncells
    for w in nums:
        x = (w["x0"] + w["x1"]) / 2
        k = min(range(ncells), key=lambda i: abs(med[i] - x))
        if out[k] is not None:
            raise ValueError(f"two cells of {label!r} fall in column {k}")
        t = w["text"]
        out[k] = Cell(None, None, t) if t in BLANKS else Cell(t, None, t)
    return [c if c is not None else Cell(None, None, "") for c in out]
