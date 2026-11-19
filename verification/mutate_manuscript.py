# Adapted from hssling/india-state-tb-score (MIT), verification/mutate_manuscript.py, commit 05bcaa7; modified: named mutations of the Markdown sources and of the submission .docx files, each applied to a temporary copy of manuscript/ and run through check_manuscript_numbers and check_docx_tie; the number-token sweep kept as --sweep and extended to the anonymised .docx
"""Mutation test of the manuscript checks (check_manuscript_numbers and check_docx_tie).

Run as: python -I verification/mutate_manuscript.py [--manuscript-dir DIR] [--sweep]

The manuscript folder DIR (default manuscript/ext; manuscript/v1_audit for v1.0.0; git-ignored)
is copied to a temporary folder for every mutation; the real files are never written. Each named mutation (MUTATIONS) changes one thing in the copy, and both
checks are run on it: check_manuscript_numbers.problems (on the copied Markdown, against the
committed outputs) and check_docx_tie.problems (on the copied Markdown and .docx files). A
mutation is caught if either check reports at least one problem. The unmutated copy must
pass both, or nothing is run.

The kinds required by the brief: a number changed in the .docx only, a number changed in
the Markdown only, the author's name inserted into a blinded file (text and document
properties), a reference number swapped, a table cell edited, a gamma sign flipped, and an
internal identifier inserted; also the supplementary data files (a CSV cell, a CSV row, an XLSX
cell) and the italics of a journal title. The manuscript text a mutation edits (its anchor) quotes
the manuscript, so it is not kept here: it is read from "mutation_anchors" in the private
<folder>/section_phrases.json. A mutation whose anchor is missing or not found counts as NOT
APPLIED and fails the run, so an anchor that drifts cannot pass silently.

--sweep also runs two exhaustive sweeps, in memory or on single-file copies:
  * every number token of manuscript_src.md (all sections but the References): the last
    digit is increased by one (9 becomes 0); check_manuscript_numbers must catch each;
  * every number token in the text of 02_manuscript_anonymised.docx (tables and references
    included): the same change; check_docx_tie must catch each.

Prints a table of the results; exits 1 if any mutation is not applied or not caught.
Prints "SKIPPED" and exits 0 when <folder>/ or <folder>/submission/ is absent.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_docx_tie as tie  # noqa: E402
from verification import check_manuscript_numbers as cmn  # noqa: E402

DOC = "word/document.xml"
CORE = "docProps/core.xml"
MS_02 = "submission/02_manuscript_anonymised.docx"
SUP_05 = "submission/05_supplementary_material.docx"
TITLE_01 = "submission/01_title_page.docx"
DATA_09 = "submission/09_supplementary_data_S1a_registered.csv"
DATA_10 = "submission/10_supplementary_data_S1b_corrected.csv"
XLSX_11 = "submission/11_supplementary_data_S1.xlsx"


class NotApplied(Exception):
    """The mutation's anchor was not found in the copy."""


# --------------------------------------------------------------------------------------
# Editing helpers (on the copy)
# --------------------------------------------------------------------------------------
def edit_text(path: Path, old: str, new: str) -> None:
    s = path.read_text(encoding="utf-8")
    if old not in s:
        raise NotApplied(f"{path.name}: {old!r} not found")
    path.write_text(s.replace(old, new, 1), encoding="utf-8", newline="\n")


def rewrite_part(path: Path, part: str, fn: Callable[[str], str]) -> None:
    """Rewrite one XML part of a .docx package with fn(xml)."""
    tmp = path.with_suffix(".mut")
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == part:
                data = fn(data.decode("utf-8")).encode("utf-8")
            zo.writestr(item, data)
    tmp.replace(path)


def edit_docx(path: Path, old: str, new: str, part: str = DOC) -> None:
    """Replace the first `old` in the XML of `part` (text inside one w:t element)."""
    def fn(xml: str) -> str:
        if old not in xml:
            raise NotApplied(f"{path.name}:{part}: {old!r} not found")
        return xml.replace(old, new, 1)
    rewrite_part(path, part, fn)


def set_creator(path: Path, name: str) -> None:
    """Write `name` as the document's author (dc:creator) in docProps/core.xml."""
    def fn(xml: str) -> str:
        tag = f"<dc:creator>{name}</dc:creator>"
        out, n = re.subn(r"<dc:creator\s*/>|<dc:creator>[^<]*</dc:creator>", tag, xml, count=1)
        if n == 0:
            out, n = re.subn(r"</cp:coreProperties>", tag + "</cp:coreProperties>", xml, count=1)
        if n == 0:
            raise NotApplied(f"{path.name}: no coreProperties element")
        return out
    rewrite_part(path, CORE, fn)


def swap_superscript(path: Path, old: str, new: str) -> None:
    """Change the first superscript run whose whole text is `old` (a citation) to `new`."""
    def fn(xml: str) -> str:
        pat = re.compile(r'(<w:vertAlign w:val="superscript"/>(?:(?!</w:r>).)*?<w:t(?: [^>]*)?>)'
                         + re.escape(old) + r"(</w:t>)", re.S)
        out, n = pat.subn(lambda m: m.group(1) + new + m.group(2), xml, count=1)
        if n == 0:
            raise NotApplied(f"{path.name}: no superscript run {old!r}")
        return out
    rewrite_part(path, DOC, fn)


def drop_italic(path: Path) -> None:
    """Remove the first italic property (the first journal title of the reference list)."""
    def fn(xml: str) -> str:
        out, n = re.subn(r"<w:i\s*/>", "", xml, count=1)
        if n == 0:
            raise NotApplied(f"{path.name}: no italic run")
        return out
    rewrite_part(path, DOC, fn)


def drop_last_row(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").split("\n")
    if len(lines) < 3:
        raise NotApplied(f"{path.name}: no data row")
    path.write_text("\n".join(lines[:-2] + lines[-1:]), encoding="utf-8", newline="")


def edit_xlsx(path: Path, sheet: str, cell: str, value: str) -> None:
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise NotApplied("openpyxl not installed") from None
    if not path.exists():
        raise NotApplied(f"{path.name} not built")
    wb = load_workbook(path)
    wb[sheet][cell] = value
    wb.save(path)


def author_name() -> str:
    return cmn.author_markers(ROOT)[0]


def marker(pred: Callable[[str], bool], ms_dir: Path) -> str:
    hits = [m for m in tie.markers(ms_dir, ROOT) if pred(m)]
    if not hits:
        raise NotApplied("no such author marker")
    return hits[0]


# --------------------------------------------------------------------------------------
# Anchors: the manuscript text each mutation edits is private (it quotes the manuscript), so it is
# read from the copied folder's section_phrases.json ("mutation_anchors"), never kept here.
# --------------------------------------------------------------------------------------
def anchor(d: Path, mid: str):
    """The private anchor text (or list of texts) of mutation `mid`."""
    try:
        a = cmn.load_phrase_file(d).get("mutation_anchors", {}).get(mid)
    except (OSError, ValueError) as e:
        raise NotApplied(f"{cmn.PHRASES}: {e}") from None
    if not a:
        raise NotApplied(f"no anchor for mutation {mid} in {cmn.PHRASES}")
    return a


def bumped(s: str) -> str:
    """`s` with its first number token's last digit increased by one."""
    m = NUMBER.search(s)
    if not m:
        raise NotApplied(f"no number in anchor {s!r}")
    return s[:m.start()] + bump(m.group()) + s[m.end():]


def flipped(s: str) -> str:
    """`s` with the sign of its first number token reversed."""
    m = NUMBER.search(s)
    if not m:
        raise NotApplied(f"no number in anchor {s!r}")
    if m.start() > 0 and s[m.start() - 1] == cmn.MINUS:
        return s[:m.start() - 1] + s[m.start():]
    return s[:m.start()] + cmn.MINUS + s[m.start():]


def change(edit: Callable[[Path, str, str], None], rel: str, mid: str,
           how: Callable[[str], str]) -> Callable[[Path], None]:
    def fn(d: Path) -> None:
        a = anchor(d, mid)
        edit(d / rel, a, how(a))
    return fn


def insert(edit: Callable[[Path, str, str], None], rel: str, mid: str, extra: Callable[[Path], str],
           before: bool = False) -> Callable[[Path], None]:
    def fn(d: Path) -> None:
        a, x = anchor(d, mid), extra(d)
        edit(d / rel, a, x + a if before else a + x)
    return fn


def renumber_pair(rel: str, mid: str) -> Callable[[Path], None]:
    """Swap the leading numbers of two reference-list anchors (entries 2 and 3 become 3 and 2)."""
    def fn(d: Path) -> None:
        a, b = anchor(d, mid)
        na, nb = NUMBER.search(a), NUMBER.search(b)
        if not (na and nb):
            raise NotApplied(f"no reference numbers in anchors of {mid}")
        edit_docx(d / rel, a, a[:na.start()] + nb.group() + a[na.end():])
        edit_docx(d / rel, b, b[:nb.start()] + na.group() + b[nb.end():])
    return fn


# --------------------------------------------------------------------------------------
# The named mutations: (id, kind, what is changed, function of the copied manuscript dir)
# --------------------------------------------------------------------------------------
Mutation = tuple[str, str, str, Callable[[Path], None]]
MUTATIONS: list[Mutation] = [
    ("1a", "number, docx only", "02 Results: the inventory figure count increased by 1",
     change(edit_docx, MS_02, "1a", bumped)),
    ("1b", "number, docx only", "01 title page: abstract word count increased by 1",
     change(edit_docx, TITLE_01, "1b", bumped)),
    ("2a", "number, markdown only", "manuscript_src.md Results: a shortfall in people screened increased by 1",
     change(edit_text, cmn.MS_NAME, "2a", bumped)),
    ("2b", "number, markdown only", "manuscript_src.md Abstract: a count of printed totals increased by 1",
     change(edit_text, cmn.MS_NAME, "2b", bumped)),
    ("3a", "author name, blinded docx", "02 Discussion text: the author's name inserted",
     insert(edit_docx, MS_02, "3a", lambda d: f" ({author_name()})")),
    ("3b", "author name, blinded docx", "02 document properties: author (dc:creator) set to the name",
     lambda d: set_creator(d / MS_02, author_name())),
    ("3c", "author e-mail, blinded docx", "05 note under Table S2: the author's e-mail inserted",
     insert(edit_docx, SUP_05, "3c", lambda d: marker(lambda m: "@" in m, d) + " ", before=True)),
    ("3d", "repository URL, blinded docx", "02 Data availability: placeholder replaced by the URL",
     lambda d: edit_docx(d / MS_02, "[repository link removed for blinded review]",
                         marker(lambda m: m.startswith("http"), d))),
    ("4a", "reference number, markdown", "manuscript_src.md: citation ^19^ -> ^24^",
     lambda d: edit_text(d / "manuscript_src.md", "^19^", "^24^")),
    ("4b", "reference number, docx only", "02: superscript citation 19 -> 24",
     lambda d: swap_superscript(d / MS_02, "19", "24")),
    ("4c", "reference number, docx only", "02 References: entries 2 and 3 renumbered 3 and 2",
     renumber_pair(MS_02, "4c")),
    ("5a", "table cell, docx only", "02 Table 3: a yield cell increased by 0.1",
     change(edit_docx, MS_02, "5a", bumped)),
    ("5b", "table cell, docx only", "05 Table S3: a yield cell increased by 0.1",
     change(edit_docx, SUP_05, "5b", bumped)),
    ("5c", "table cell, markdown only", "tables.md Table 1: the inventory figure count increased by 1",
     change(edit_text, "exhibits/tables.md", "5c", bumped)),
    ("6a", "gamma sign, markdown", "manuscript_src.md Results: the sign of the main γ1 reversed",
     change(edit_text, cmn.MS_NAME, "6a", flipped)),
    ("6b", "gamma sign, docx only", "02 Results: the sign of the main γ1 reversed",
     change(edit_docx, MS_02, "6b", flipped)),
    ("6c", "gamma sign, docx only", "05 Table S4: the sign of the placebo γ1 reversed",
     change(edit_docx, SUP_05, "6c", flipped)),
    ("7a", "internal identifier, markdown", "manuscript_src.md Methods: '(RS Q1216)' inserted",
     insert(edit_text, cmn.MS_NAME, "7a", lambda d: " (RS Q1216)")),
    ("7b", "internal identifier, docx only", "02 Discussion: '(Task 7)' inserted",
     insert(edit_docx, MS_02, "7b", lambda d: " (Task 7)")),
    ("7c", "internal identifier, docx only", "05 note under Table S2: 'ITR2024' inserted",
     insert(edit_docx, SUP_05, "7c", lambda d: "ITR2024 ", before=True)),
    ("8a", "supplementary data, CSV", "09 (S1a): first A value 347 -> 348",
     lambda d: edit_text(d / DATA_09, ",347,exact,", ",348,exact,")),
    ("8b", "supplementary data, CSV", "10 (S1b): last row deleted",
     lambda d: drop_last_row(d / DATA_10)),
    ("8c", "supplementary data, XLSX", "11, sheet S1b: cell K2 (A value, printed) set to 999",
     lambda d: edit_xlsx(d / XLSX_11, "S1b corrected", "K2", "999")),
    ("9a", "AMA italics, docx only", "02 References: italics removed from the first journal title",
     lambda d: drop_italic(d / MS_02)),
]


# --------------------------------------------------------------------------------------
# Running the checks on a copy
# --------------------------------------------------------------------------------------
def copy_manuscript(src: Path, dst_root: Path) -> Path:
    dst = dst_root / "manuscript"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("_render", "__pycache__", "*.png"))
    return dst


def cmn_problems(ms_dir: Path) -> list[str]:
    text = (ms_dir / cmn.MS_NAME).read_text(encoding="utf-8")
    sk = ms_dir / cmn.SKELETON
    gold = json.loads(sk.read_text(encoding="utf-8"))["sections"] if sk.exists() else None
    others = {n: (ms_dir / n).read_text(encoding="utf-8") for n in cmn.OTHER_FILES if (ms_dir / n).exists()}
    if not (ms_dir / cmn.PHRASES).exists():
        return [f"PHRASES: {cmn.PHRASES} missing"]
    return cmn.problems(ROOT, text, gold, others, required=cmn.section_phrases(ms_dir))


def tie_problems(ms_dir: Path) -> list[str]:
    return tie.problems(ms_dir, ROOT)


def run_named(src: Path, mutations: list[Mutation] = MUTATIONS,
              checks: dict[str, Callable[[Path], list[str]]] | None = None) -> list[dict]:
    """Apply each mutation to a fresh copy of `src`; return one result row per mutation."""
    checks = checks or {"check_manuscript_numbers": cmn_problems, "check_docx_tie": tie_problems}
    rows = []
    with tempfile.TemporaryDirectory() as td:
        base = copy_manuscript(src, Path(td) / "base")
        for name, fn in checks.items():
            found = fn(base)
            if found:
                raise SystemExit(f"the unmutated copy fails {name}; fix that first:\n" + "\n".join(found[:5]))
        for mid, kind, what, fn in mutations:
            d = copy_manuscript(src, Path(td) / f"m{mid}")
            row = {"id": mid, "kind": kind, "what": what, "applied": True, "by": [], "first": ""}
            try:
                fn(d)
            except NotApplied as e:
                row.update(applied=False, first=str(e))
                rows.append(row)
                continue
            for name, check in checks.items():
                found = check(d)
                if found:
                    row["by"].append(name)
                    row["first"] = row["first"] or found[0].splitlines()[0]
            rows.append(row)
            shutil.rmtree(d, ignore_errors=True)
    return rows


# --------------------------------------------------------------------------------------
# Sweeps over every number token
# --------------------------------------------------------------------------------------
NUMBER = re.compile(r"\d+(?:,\d{3}(?!\d))*(?:\.\d+)?")


def bump(tok: str) -> str:
    """The token with its last digit increased by one (9 becomes 0)."""
    return tok[:-1] + str((int(tok[-1]) + 1) % 10)


def md_token_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every number token outside the References section."""
    spans, pos, in_refs = [], 0, False
    for line in text.splitlines(keepends=True):
        if line.startswith("## "):
            in_refs = line.strip() == "## References"
        elif not in_refs:
            spans += [(pos + m.start(), pos + m.end()) for m in NUMBER.finditer(line)]
        pos += len(line)
    return spans


def sweep_md(text: str, check: Callable[[str], list[str]]) -> tuple[int, int, list[str]]:
    caught, escaped = 0, []
    spans = md_token_spans(text)
    for a, b in spans:
        mutated = text[:a] + bump(text[a:b]) + text[b:]
        if check(mutated):
            caught += 1
        else:
            escaped.append(f"...{text[max(0, a - 30):b + 10]}...".replace("\n", " "))
    return caught, len(spans), escaped


def docx_token_spans(xml: str) -> list[tuple[int, int]]:
    """(start, end) in the XML of every number token inside a w:t element."""
    out = []
    for m in re.finditer(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", xml):
        out += [(m.start(1) + t.start(), m.start(1) + t.end()) for t in NUMBER.finditer(m.group(1))]
    return out


def sweep_docx(path: Path, want: list[str]) -> tuple[int, int, list[str]]:
    """Bump every number token of the .docx text; the tie must report a difference each time."""
    with zipfile.ZipFile(path) as z:
        xml = z.read(DOC).decode("utf-8")
    spans = docx_token_spans(xml)
    caught, escaped = 0, []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / path.name
        for a, b in spans:
            shutil.copyfile(path, tmp)
            rewrite_part(tmp, DOC, lambda _x, a=a, b=b: xml[:a] + bump(xml[a:b]) + xml[b:])
            if tie.compare(path.name, tie.docx_units(tmp), want):
                caught += 1
            else:
                escaped.append(xml[max(0, a - 40):b + 10])
    return caught, len(spans), escaped


# --------------------------------------------------------------------------------------
def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ms, argv = cmn.manuscript_dir(root, argv)
    name = cmn.rel(ms, root)
    if not ms.is_dir() or not (ms / "submission").is_dir():
        print(f"SKIPPED: {name}/ or {name}/submission/ not present (kept private, not in this repository)")
        return 0
    rows = run_named(ms)
    bad = 0
    print("| # | Kind | Mutation | Caught by | First problem reported |")
    print("|---|------|----------|-----------|------------------------|")
    for r in rows:
        if not r["applied"]:
            res = "NOT APPLIED"
        elif r["by"]:
            res = " and ".join(r["by"])
        else:
            res = "NOT CAUGHT"
        bad += res in ("NOT APPLIED", "NOT CAUGHT")
        first = r["first"].replace("|", "/")[:110]
        print(f"| {r['id']} | {r['kind']} | {r['what']} | {res} | {first} |")
    print(f"named mutations: {len(rows) - bad} of {len(rows)} caught")
    if "--sweep" in argv:
        text = (ms / cmn.MS_NAME).read_text(encoding="utf-8")
        gold = json.loads((ms / cmn.SKELETON).read_text(encoding="utf-8"))["sections"]
        others = cmn.load_others(ms)
        required = cmn.section_phrases(ms)
        c, t, e = sweep_md(text, lambda s: cmn.problems(root, s, gold, others, required=required))
        print(f"sweep, manuscript_src.md number tokens (check_manuscript_numbers): caught {c} of {t}")
        for x in e:
            print("  UNCAUGHT", x)
        p = ms / MS_02
        want, _ = tie.expected(ms, p.name)
        c2, t2, e2 = sweep_docx(p, want)
        print(f"sweep, {p.name} number tokens (check_docx_tie): caught {c2} of {t2}")
        for x in e2:
            print("  UNCAUGHT", x)
        bad += len(e) + len(e2)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
