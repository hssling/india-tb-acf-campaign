# Copied from hssling/india-state-tb-score (MIT), src/states.py, commit 05bcaa7; modified: added coarsen()
"""Canonical State/UT names and the completeness check for joins."""
from __future__ import annotations

import re
from typing import Iterable

ALL: tuple[str, ...] = (
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
    "Bihar", "Chandigarh", "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka",
    "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal",
)

# Variant spellings seen in the reports. Keys are matched after _norm().
ALIASES: dict[str, str] = {
    "Jammu & Kashmir": "Jammu and Kashmir",
    "Andaman & Nicobar Islands": "Andaman and Nicobar Islands",
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
    "DNH and DD": "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra & Nagar Haveli and Daman & Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "NCT of Delhi": "Delhi",
    "Orissa": "Odisha",
    "Pondicherry": "Puducherry",
    "Uttaranchal": "Uttarakhand",
}

_DNHDD = "Dadra and Nagar Haveli and Daman and Diu"
# Pre-2020 (score years <= 2019): Ladakh inside J&K; DNH and DD separate.
_PRE2020 = tuple(s for s in ALL if s not in ("Ladakh", _DNHDD)) + (
    "Dadra and Nagar Haveli", "Daman and Diu")


def _norm(s: str) -> str:
    s = s.replace("&", " and ")
    return re.sub(r"\s+", " ", s).strip().casefold()


_LOOKUP: dict[str, str] = {_norm(n): n for n in ALL}
_LOOKUP.update({_norm(k): v for k, v in ALIASES.items()})
_LOOKUP.update({_norm(n): n for n in _PRE2020})
# longest first, for prefix matching
_BY_LENGTH = sorted(_LOOKUP, key=len, reverse=True)


def canonical(name: str) -> str:
    """Canonical name for a State/UT; KeyError for unknown or national rows."""
    try:
        return _LOOKUP[_norm(name)]
    except KeyError:
        raise KeyError(f"not a known State/UT: {name!r}") from None


_JKL = "Jammu and Kashmir (incl. Ladakh)"
# Units that were split or merged between the years compared are combined to the
# coarser unit in every year (J&K with Ladakh; DNH with Daman and Diu).
_COARSE: dict[str, str] = {
    "Jammu and Kashmir": _JKL,
    "Ladakh": _JKL,
    "Dadra and Nagar Haveli": _DNHDD,
    "Daman and Diu": _DNHDD,
}


def coarsen(name: str) -> str:
    """Coarse unit for a State/UT name (any spelling valid for `canonical`);
    KeyError for unknown or national rows."""
    c = canonical(name)
    return _COARSE.get(c, c)


def normalize(name: str) -> str:
    """The normalisation under which spellings are matched ("&" = "and",
    whitespace collapsed, case folded)."""
    return _norm(name)


def units(year: int) -> tuple[str, ...]:
    """The canonical State/UT names valid in score year `year`, in order."""
    return ALL if year >= 2020 else _PRE2020


def spellings(year: int) -> dict[str, str]:
    """Normalised spelling (canonical names and aliases) -> canonical name,
    for the units valid in score year `year`."""
    valid = set(units(year))
    return {k: v for k, v in _LOOKUP.items() if v in valid}


def require_all(names: Iterable[str], year: int) -> None:
    """Raise ValueError listing missing and extra units for score year `year`."""
    valid = set(units(year))
    got = set(names)
    missing = sorted(valid - got)
    extra = sorted(got - valid)
    if missing or extra:
        raise ValueError(
            f"year {year}: missing units {missing}; extra units {extra}")


# Verbatim phrases of the prevalence survey's list of abbreviations that name one
# canonical unit.
GROUP_PHRASES: dict[str, str] = {
    "Dadra, Nagar Haveli, Daman, Diu": "Dadra and Nagar Haveli and Daman and Diu",
}


def members_of(expansion: str) -> list[str]:
    """Canonical States/UTs named by a survey abbreviation's expansion. A group name
    followed by a parenthesised list ('North Eastern States (...)') is the list.
    KeyError for any part that is not a State/UT.

    A pure string helper: the analyses use it without the PDF extraction libraries."""
    m = re.fullmatch(r"[^()]*\((.*)\)", expansion)
    text = m.group(1) if m else expansion
    for phrase, name in GROUP_PHRASES.items():
        text = text.replace(phrase, name)
    return [canonical(p) for p in re.split(r",\s*|\s+And\s+", text) if p.strip()]


# "#" starts a spreadsheet error value (#N/A, #DIV/0!) that CTD prints in
# blank cells.
_NUMLIKE = re.compile(r"^(?:[\d*(#]|NA$|-$)", re.I)


def leading_state(line: str) -> tuple[str, str] | None:
    """(canonical name, rest of line) if the line starts with a State/UT name."""
    toks = line.split()
    for i in range(len(toks), 0, -1):
        if i < len(toks) and not _NUMLIKE.match(toks[i]):
            continue  # name must be followed by a value (or end the line)
        try:
            return canonical(" ".join(toks[:i])), " ".join(toks[i:])
        except KeyError:
            continue
    return None


def _split_name(line: str) -> tuple[list[str], list[str]]:
    """Tokens before the first value-like token, and the rest."""
    toks = line.split()
    k = next((j for j, t in enumerate(toks) if _NUMLIKE.match(t)), len(toks))
    return toks[:k], toks[k:]


def _is_name_prefix(text: str) -> bool:
    n = _norm(text)
    return any(key.startswith(n + " ") for key in _LOOKUP)


def join_wrapped_names(lines: list[str]) -> list[str]:
    """Rejoin State names that CTD wraps over two or three table lines.

    Examples: "Dadra and Nagar Haveli and 69.0 ..." / "Daman and Diu", and the
    annexure 7.3 form "Andaman and Nicobar 861 ..." / "Islands (97%) ...".
    A line whose name part is only a proper prefix of a known name is merged
    with the leading name-like words of the following line(s). Whatever
    follows those words on a continuation line (wrapped percentages) stays as
    its own line directly after the merged row; the extractor decides what to
    do with it.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        name, rest = _split_name(lines[i])
        text = " ".join(name)
        if name and _is_name_prefix(text):
            j, leftovers = i + 1, []
            while j < len(lines) and _is_name_prefix(text):
                cont, tail = _split_name(lines[j])
                if not cont:
                    break
                text = text + " " + " ".join(cont)
                if tail:
                    leftovers.append(" ".join(tail))
                j += 1
                if _norm(text) in _LOOKUP:
                    break
            if _norm(text) in _LOOKUP and j > i + 1:
                out.append(" ".join([text] + rest))
                out.extend(leftovers)
                i = j
                continue
        out.append(lines[i])
        i += 1
    return out
