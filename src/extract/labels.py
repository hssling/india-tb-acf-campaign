"""The State/UT label rule of analysis plan §9.2 (E3) and §11.

Step 1: match the label to a canonical name or a listed alias (`src.states`),
ignoring case and punctuation, collapsing spaces and reading "&" as "and".
Step 2: resolve it from name evidence only, from the fixed table below; each
resolution carries its evidence and is logged by the caller.
Otherwise the label is unmapped and extraction halts (UnmappedLabel), so that a
person decides; no mapping is invented.

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
    "the dadra and nagar haveli and daman and diu": (
        _DNHDD,
        "the words of the label are the canonical name preceded by the article 'The'"),
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
    raise UnmappedLabel(f"label not mappable by the label rule: {label!r}")
