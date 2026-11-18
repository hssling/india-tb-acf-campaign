"""Keyword and qualifier rules of the analysis plan applied to figure-inventory rows.

- qualifier: §6.1 (words directly before the figure; "+" and "~" symbols);
- definition_class and scope: §7.2 (case-insensitive whole-word keywords, the stems
  notif, diagnos, detect, symptom and radiograph matching as word prefixes);
- window_label: §7.1;
- value_of: §5.2 (Indian magnitude words converted).

Pure standard library: analysis modules may import it without the PDF libraries.
"""
from __future__ import annotations

import re
from decimal import Decimal

from src.extract.cells import parse_int, parse_magnitude

# ------------------------------------------------------------------ qualifier (§6.1)

_AT_LEAST = ("more than", "over", "above", "exceeding", "at least")
_AT_MOST = ("up to", "less than", "under", "below", "at most")
_ABOUT = ("nearly", "around", "approximately", "about", "almost", "close to")
_PLUS = re.compile(r"\d[\d,.]*(?: ?(?:lakhs?|crores?))?\+(?!\s*\d)", re.I)
_TILDE = re.compile(r"~ ?$")
_BREAK = re.compile(r"[,;:()•●\n]")


def _has_word(text: str, phrase: str) -> bool:
    return re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I) is not None


def find_figure(context: str, printed: str, occurrence: int = 1) -> int:
    """Index of the `occurrence`-th appearance of `printed` in `context` as a whole
    figure (not inside a longer number); ValueError if absent."""
    pat = r"(?<![\d,.])" + re.escape(printed) + r"(?![\d])"
    hits = [m.start() for m in re.finditer(pat, context)]
    if len(hits) < occurrence:
        raise ValueError(f"figure {printed!r} (occurrence {occurrence}) not in context "
                         f"{context!r}")
    return hits[occurrence - 1]


def qualifier(context: str, printed: str, occurrence: int = 1) -> str:
    """exact, at_least, about or at_most for the `occurrence`-th appearance of
    `printed` in `context`. ValueError if the figure is not in its context."""
    start = find_figure(context, printed, occurrence)
    before = context[:start]
    # the one to three words directly before the figure (within its clause)
    clause = _BREAK.split(before)[-1]
    words = " ".join(re.findall(r"[A-Za-z]+", clause)[-3:])
    plus = _PLUS.match(context, start) is not None
    tilde = _TILDE.search(before) is not None
    if plus or any(_has_word(words, p) for p in _AT_LEAST):
        return "at_least"
    if any(_has_word(words, p) for p in _AT_MOST):
        return "at_most"
    if tilde or any(_has_word(words, p) for p in _ABOUT):
        return "about"
    return "exact"


# ------------------------------------------------------- definition class (§7.2)

_STEMS = ("notif", "diagnos", "detect", "symptom", "radiograph")


def _kw(text: str, keyword: str) -> bool:
    k = keyword.lower()
    pat = r"\b" + re.escape(k)
    if not any(k == s for s in _STEMS):
        pat += r"\b"
    return re.search(pat, text, re.I) is not None


_PERSON = ("person", "persons", "patient", "patients", "individual", "individuals",
           "contact", "contacts")
_TESTED_WITH = ("person", "persons", "people", "individual", "individuals", "patient",
                "patients", "presumptive")


def definition_class(quantity: str, definition: str) -> tuple[str, str]:
    """(class, keyword that matched). Quantities without classes give ("", "")."""
    d = definition
    if quantity == "screened":
        for kws, cls in ((("x-ray", "x ray", "cxr", "radiograph"), "screened by chest X-ray"),
                         (("symptom",), "symptom-screened"),
                         (("reached", "covered", "visited", "contacted"),
                          "population reached")):
            for k in kws:
                if _kw(d, k):
                    return cls, k
        return "unspecified", ""
    if quantity == "tested":
        for k in ("tests", "testing done", "investigations", "number of test"):
            if _kw(d, k):
                if k == "investigations" and any(_kw(d, p) for p in _PERSON):
                    continue
                return "tests done", k
        if _kw(d, "tested"):
            for p in _TESTED_WITH:
                if _kw(d, p):
                    return "people tested", f"tested + {p}"
        return "unspecified", ""
    if quantity == "tb_cases":
        if _kw(d, "notif"):
            return "notified", "notif"
        for k in ("diagnos", "detect"):
            if _kw(d, k):
                return "diagnosed", k
        return "unspecified", ""
    return "", ""


# ------------------------------------------------------------------ scope (§7.2)

_P347 = re.compile(r"(?<![\w,.])347(?![\d,.]*\d)")
_PHASE1 = ("100 day", "100-day", "100 days", "phase 1", "phase i", "phase-i")
_PHASE2 = ("expanded", "extended", "expansion", "all districts", "phase 2", "phase ii",
           "phase-ii", "second phase")
_CAMPAIGN = ("Abhiyan", "Abhiyaan", "campaign", "campaigns")
_ACF = ("active case finding", "ACF")
COMBINED_PHASE = re.compile(r"\bphase[\s-]*(?:i|1)\s*(?:/|&|-|and)\s*(?:ii|2)\b", re.I)


def _first(text: str, kws) -> str:
    for k in kws:
        if _kw(text, k):
            return k
    return ""


def scope(context: str) -> tuple[str, str, str]:
    """(scope, keyword that matched, note flag). The note flags a text holding both a
    phase 1 and a phase 2 keyword, or a combined phase."""
    k1 = _first(context, _PHASE1) or ("347" if _P347.search(context) else "")
    k2 = _first(context, _PHASE2)
    note = ""
    if k1 and k2:
        note = f"mixed-phase scope: '{k1}' and '{k2}' (§7.2)"
    if COMBINED_PHASE.search(context):
        note = (note + "; " if note else "") + "combined phase (§7.2)"
    if k1:
        return "phase 1", k1, note
    if k2:
        return "expanded campaign", k2, note
    k = _first(context, _CAMPAIGN)
    if k:
        return "unspecified", k, note
    k = _first(context, _ACF)
    if k:
        return "programme-wide", k, note
    return "unspecified", "", note


# ------------------------------------------------------------- window label (§7.1)

def window_label(context: str, period_words: str, has_end_date: bool) -> str:
    """'100-day campaign', 'campaign to date', or the period words as printed
    (lower-cased, hyphens read as spaces, spaces collapsed); blank if none."""
    if _first(context, ("100 day", "100-day", "100 days")):
        return "100-day campaign"
    if (_first(context, ("Abhiyan", "Abhiyaan", "campaign"))
            and _first(context, ("since", "from")) and not has_end_date):
        return "campaign to date"
    words = period_words.lower().replace("-", " ").replace("–", " ")
    return re.sub(r"\s+", " ", words).strip()


# ------------------------------------------------------------------- value (§5.2)

_RANGE = re.compile(r"\d\s*[–-]\s*\d")


def value_of(printed: str) -> str:
    """The figure as a number (string); blank for a range."""
    t = printed.strip()
    if _RANGE.search(t):
        return ""
    t = t.replace("+", " ").replace("~", " ").replace(">", " ")
    t = re.sub(r"\bCr\b", "crore", t)
    t = re.sub(r"\b(lakh|crore)s\b", r"\1", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    if t.endswith("%"):
        return str(Decimal(t[:-1].strip()))
    if re.search(r"(lakh|crore)$", t, re.I):
        return str(parse_magnitude(t))
    return str(parse_int(t))
