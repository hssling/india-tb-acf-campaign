"""The State/UT label rule of analysis plan §9.2 (E3) and §11.

Step 1: match the label to a canonical name or a listed alias (`src.states`),
ignoring case and punctuation, collapsing spaces and reading "&" as "and".
Step 2: resolve it from name evidence only, from the fixed table below; each
resolution carries its evidence and is logged by the caller.
Otherwise the label is unmapped: `resolve` raises UnmappedLabel, and
`resolve_or_list` applies step 3 (the row's State is not computable and is listed;
its count still enters the printed-total checks). No mapping is invented.

A pure string helper: it imports no PDF library.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src import states

_DNHDD = "Dadra and Nagar Haveli and Daman and Diu"

# Step-2 resolutions from name evidence only (never row position or values).
# Keys are matched after _clean() and states.normalize().
STEP2: dict[str, tuple[str, str]] = {
    "dnh and dnd": (
        _DNHDD,
        "abbreviation: DNH = Dadra and Nagar Haveli, DND = Daman and Diu; the expansion "
        "names exactly one State/UT (the example given in analysis plan §9.2)"),
    "dnh g dnd": (
        _DNHDD,
        "the page prints 'G' between the abbreviations; DNH = Dadra "
        "and Nagar Haveli and DND = Daman and Diu expand to exactly one State/UT"),
    "jammu g kashmir": (
        "Jammu and Kashmir",
        "the page prints 'G' between the words; the words Jammu and "
        "Kashmir name exactly one State/UT"),
    "dadra nagar haveli diu daman": (
        _DNHDD,
        "the words of the label name Dadra and Nagar Haveli and Daman and Diu (the "
        "printed 'Dadra Nagar Haveli' and 'Diu Daman' joined by a slash), and the combined "
        "unit names exactly one State/UT"),
    "the dadra and nagar haveli and daman and diu": (
        _DNHDD,
        "the words of the label are the canonical name preceded by the article 'The'"),
    "dadra and nagar haveli and diu and daman": (
        _DNHDD,
        "the words of the label are those of Dadra and Nagar Haveli and Daman and Diu "
        "with 'Diu' and 'Daman' printed in reverse order; they name exactly one State/UT "
        "(RS Q. 1093 Annexure)"),
    "lakshwadeep": (
        "Lakshadweep",
        "the label is the one word 'Lakshwadeep', the letters of Lakshadweep with 'adw' "
        "printed as 'wad'; no other State/UT name is close (India TB Report 2019, "
        "Annexure 1.7)"),
}


class UnmappedLabel(KeyError):
    """A label that neither step of the label rule maps to one State/UT."""


@dataclass(frozen=True)
class Resolution:
    label: str
    canonical: str
    step: int
    evidence: str


def _clean(label: str) -> str:
    # punctuation other than "&" is ignored (read as a space)
    return re.sub(r"[^\w&\s]", " ", label)


def resolve(label: str) -> Resolution:
    cleaned = _clean(label)
    try:
        return Resolution(label, states.canonical(cleaned), 1, "")
    except KeyError:
        pass
    key = states.normalize(cleaned)
    if key in STEP2:
        canon, evidence = STEP2[key]
        return Resolution(label, states.canonical(canon), 2, evidence)
    # the words of the label, with spaces lost or inserted by line wrapping in the
    # PDF ignored ("TamilNadu", "Chhattisgar h"), must name exactly one State/UT
    squeezed = key.replace(" ", "")
    hits = sorted({states.canonical(n) for n in states.ALL
                   if states.normalize(n).replace(" ", "") == squeezed})
    if len(hits) == 1 and squeezed:
        return Resolution(label, hits[0], 2,
                          f"the words of the label are the canonical name '{hits[0]}' "
                          "once spaces lost or inserted by line wrapping are ignored")
    raise UnmappedLabel(f"label not mappable by the label rule: {label!r}")


def resolve_or_list(label: str) -> Resolution:
    """The label rule with its step 3 (§9.2): a label that fits no canonical name, or
    more than one, gives step 3 with a blank canonical name; the caller lists the row
    as not computable and keeps its count in printed-total checks."""
    try:
        return resolve(label)
    except UnmappedLabel:
        return Resolution(label, "", 3, "fits no canonical State/UT name, or more than "
                          "one: State not computable (§9.2, step 3)")
