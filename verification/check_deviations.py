# Copied from hssling/india-state-tb-score (MIT), verification/check_deviations.py, commit 05bcaa7; modified: entries are bold-dated paragraphs of section 13; exploratory labels are matched per line to the question they name; corrected/reconstructed/deviation output sets need a dated entry; data/extracted/*_reconstructed* files included
"""Check that every exploratory, corrected or reconstructed label is logged in section 13.

Run as: python -I verification/check_deviations.py

- A line of an outputs/ file containing "exploratory" (any case) is logged if one dated
  section 13 entry that says "exploratory" names the file, or names a question number the
  line also names (Q420, AU1900, RSQ420 ...) and the file's analysis (q2_ -> Q2) in the
  same entry. The only exception: a line naming no question, in the outputs README, in
  a summary file or the header line of a table, is logged if an exploratory entry names
  the file's analysis (any, for the README).
- A file whose name or text carries "corrected", "reconstructed" or "deviation"
  (outputs/ and data/extracted/*_reconstructed*) needs a dated entry containing that
  stem and naming the file or the file's analysis (q1_ -> Q1, ...).
Nothing in the plan is edited; a label without an entry is a failure.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADING = "## 13. Deviations"
DATED = re.compile(r"^\*\*(\d{1,2} \w+ \d{4})[^*]*\*\*")
QNUM = re.compile(r"(?:Q\.?\s?|AU|AS|Question\s)(\d{2,4})(?!\d)")
STEMS = {"corrected": "correct", "reconstructed": "reconstruct", "deviation": "deviation"}


def section13_entries(plan: str) -> list[tuple[str, str]]:
    """(date, text) of every bold-dated paragraph of section 13 (continuation lines kept)."""
    lines = plan.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == HEADING)
    entries: list[list[str]] = []
    for ln in lines[start + 1:]:
        m = DATED.match(ln)
        if m:
            entries.append([m.group(1), ln])
        elif entries:
            entries[-1][1] += "\n" + ln
    return [(d, t) for d, t in entries]


def _area(name: str) -> str | None:
    m = re.match(r"q(\d)_", name)
    return f"Q{m.group(1)}" if m else None


def _mentions_area(text: str, area: str | None) -> bool:
    return area is None or re.search(rf"Q{area[1]}(?!\d)", text) is not None


def _files(root: Path) -> list[Path]:
    fs = [f for f in sorted((root / "outputs").rglob("*")) if f.is_file()]
    fs += [f for f in sorted((root / "data" / "extracted").glob("*_reconstructed*"))
           if f.is_file()]
    return fs


def problems(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(unlogged labels, descriptions of logged ones)."""
    plan = (root / "docs" / "analysis_plan.md").read_text(encoding="utf-8")
    entries = section13_entries(plan)
    texts = [t for _, t in entries]
    expl = [t for t in texts if "exploratory" in t.lower()]
    expl_q = [(t, set(QNUM.findall(t))) for t in expl]
    bad: list[str] = []
    ok: list[str] = []
    for f in _files(root):
        rel = f.relative_to(root).as_posix()
        text = f.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        area = _area(f.name)
        named = any(f.name in t or rel in t for t in expl)
        n_lines = unlogged = 0
        for k, ln in enumerate(text.splitlines()):
            if "exploratory" not in ln.lower():
                continue
            n_lines += 1
            qs = set(QNUM.findall(ln))
            if named or any(qs & nums and _mentions_area(t, area) for t, nums in expl_q):
                continue
            summary_like = (rel == "outputs/README.md" or "summary" in f.name or k == 0)
            if not qs and summary_like and any(_mentions_area(t, area) for t in expl):
                continue
            unlogged += 1
        if unlogged:
            bad.append(f"{rel}: {unlogged} line(s) labelled 'exploratory' with no dated "
                       f"section 13 entry that names the file or the question")
        elif n_lines:
            ok.append(f"{rel} (exploratory, {n_lines} lines)")
        for word, stem in STEMS.items():
            if word not in low and word not in f.name.lower():
                continue
            cands = [t for t in texts if stem in t.lower()]
            if any(f.name in t or rel in t or _mentions_area(t, area) for t in cands):
                ok.append(f"{rel} ({word})")
            else:
                bad.append(f"{rel}: '{word}' with no dated section 13 entry naming the file "
                           f"or its analysis")
    return bad, ok


def main(root: Path = ROOT) -> int:
    bad, ok = problems(root)
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    print(f"OK: {len(ok)} label(s) in {len({o.split(' ')[0] for o in ok})} file(s) are "
          f"covered by dated section 13 entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
