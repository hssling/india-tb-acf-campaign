"""Figure-inventory rows (analysis plan §5.2) for the parliamentary answers and the India
TB Reports, built the way the campaign extractor builds its rows:

- context_verbatim is read literally (§5.2 as clarified in §13, 19 November 2026): a
  figure in prose has its own sentence; a table cell has "table title | column heading |
  row label";
- qualifier (§6.1), definition class and scope (§7.2) and window label (§7.1) follow by
  rule from that context and from the source's own words for the quantity;
- fig_id is a content key: document . page . table cell or sentence . quantity.

A pure helper: it imports no PDF library.
"""
from __future__ import annotations

import re

from src import inventory_rules as R

CELL = " | "


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _short(s: str) -> str:
    """A long column slug keeps its start and its end (where the sub-heading is)."""
    return s if len(s) <= 40 else s[:23].rstrip("-") + "-" + s[-16:].lstrip("-")


def fig_key(doc: str, page: int, quantity: str, *, col: str = "", row: str = "",
            sentence: str = "", key: str = "", occurrence: int = 1) -> str:
    if key:
        loc = key
    elif col or row:
        loc = ".".join(x for x in (_short(slug(col)), slug(row)[:40]) if x)
    else:
        loc = "s-" + "-".join(re.findall(r"[a-z0-9]+", sentence.lower())[:6])
    k = ".".join((doc, f"p{page:03d}", loc, quantity.replace(":", "_")))
    return k + (f".{occurrence}" if occurrence > 1 else "")


def row(*, doc: str, page: int, quantity: str, printed: str, unit: str,
        definition: str, source_file: str, source_url: str, page_or_para: str,
        pub_date: str, sentence: str = "", title: str = "", col: str = "",
        rowlabel: str = "", geography: str = "India", table_id: str = "",
        period: str = "", wstart: str = "", wend: str = "", as_on: str = "",
        series: str = "period", notes: tuple[str, ...] = (), occurrence: int = 1,
        value: str | None = None, key: str = "") -> dict:
    is_table = bool(col or rowlabel)
    ctx = CELL.join(x for x in (title, col, rowlabel) if x) if is_table else sentence
    qual = "exact" if is_table else R.qualifier(ctx, printed, occurrence)
    dcls, dkw = R.definition_class(quantity, definition)
    scope, skw, snote = R.scope(ctx)
    basis = "stated" if as_on else ("window_end" if wend else "bounded")
    n = []
    if dcls:
        n.append(f"definition_class keyword: '{dkw}'" if dkw
                 else "definition_class: no keyword matched")
    n.append(f"scope keyword: '{skw}'" if skw else "scope: no keyword matched")
    if snote:
        n.append(snote)
    if is_table:
        n.append("table cell: context is table title | column heading | row label "
                 "(§5.2, §13); no qualifier words in a cell, so exact")
    n.extend(x for x in notes if x)
    return {
        "fig_id": fig_key(doc, page, quantity, col=col, row=rowlabel, sentence=sentence,
                          key=key, occurrence=occurrence),
        "quantity": quantity,
        "value": R.value_of(printed) if value is None else value,
        "value_printed": printed, "qualifier": qual, "unit": unit,
        "definition_verbatim": definition, "context_verbatim": ctx,
        "definition_class": dcls, "scope": scope, "series_type": series,
        "window_label": R.window_label(ctx, period, bool(wend or as_on)),
        "window_start": wstart, "window_end": wend, "as_on": as_on,
        "as_on_basis": basis, "geography": geography, "source_file": source_file,
        "source_url": source_url, "page_or_para": page_or_para, "table_id": table_id,
        "pub_date": pub_date, "note": "; ".join(n)}


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"-\s+", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return re.findall(r"[\w%.,/&>+*'()-]+", norm(s))


def verify(pieces: list[str], printed: str, page_text: str) -> str:
    """'text' if every piece is in the page text, 'text (loose)' if every token of every
    piece is; ValueError otherwise (or if the figure is not on the page)."""
    text = norm(page_text)
    R.find_figure(text, norm(printed))
    if all(norm(p) in text for p in pieces):
        return "text"
    if _loose(pieces, text):
        return "text (loose)"
    raise ValueError(f"context not found on the page: {pieces!r}")


def verify_pieces(pieces: list[str], page_text: str) -> str:
    """As `verify`, without a figure: for table titles, headings and notes."""
    text = norm(page_text)
    if all(norm(p) in text for p in pieces):
        return "text"
    if _loose(pieces, text):
        return "text (loose)"
    raise ValueError(f"not found on the page: {pieces!r}")


_HYPH = re.compile(r"(?<=[a-z])-\s*(?=[a-z])")


def _loose(pieces: list[str], text: str) -> bool:
    """Every token of every piece is in the text, in any order; a word broken by a
    hyphen at a line end ("popula- tion") is read whole."""
    if all(t.strip(".,;:()") in text for p in pieces for t in tokens(p)):
        return True
    joined = _HYPH.sub("", text)
    return all(t.strip(".,;:()") in joined or _HYPH.sub("", t.strip(".,;:()")) in joined
               for p in pieces for t in tokens(p))


def check_ids(rows: list[dict]) -> None:
    ids = [r["fig_id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"fig_id collisions: {dup}")
