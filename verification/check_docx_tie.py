# Adapted from hssling/india-state-tb-score (MIT), verification/check_docx_tie.py, commit 05bcaa7; modified: every paragraph, list item, table row and reference of each Public Health submission file is tied to its Markdown source (not only the number tokens); superscripts kept as ^...^; blinding of 02 and 05 checked in every part of the package; internal identifiers; Word's word counts on the title page
"""Tie the submission .docx files to their Markdown sources.

Run as: python -I verification/check_docx_tie.py

The .docx files in manuscript/submission/ (built by tools/build_submission.py) are what the
journal receives; the Markdown files in manuscript/ are what check_manuscript_numbers.py
verifies. This check reads the .docx files with zipfile and ElementTree only and requires:

1. Text tie. Each file's units (paragraphs outside tables, and table rows as their cells
   joined by " | ") equal, in order, the units of its Markdown source(s) (SPEC): headings,
   paragraphs (lines joined), list items (bullet marker dropped; a numbered item such as a
   reference keeps its number as text), table rows (separator rows dropped). Both sides are
   normalised the same way: emphasis markers and escapes removed, a superscript written
   ^...^ (a superscript run in Word; ^1^ or a modifier letter such as ᵃ in Markdown),
   no-break spaces and runs of whitespace collapsed, and the Zenodo DOI (placeholder
   XXXXXXX or the number filled in at release) read as one token. Only the few lines the
   build adds (BUILDER) may be extra. A changed number, sign, table cell, reference number,
   superscript or inserted word in either the .docx or the Markdown is a difference.
2. Blinding. No author marker (check_manuscript_numbers.author_markers: name, ORCID,
   institution, repository; plus the title page's e-mail, telephone and postcode) occurs
   anywhere in 02 or 05 (every XML part, document properties included) or in the
   figure files.
3. Internal identifiers (check_manuscript_numbers.BANNED) do not occur in 02 (before the
   References) or 05.
4. Word's counts. manuscript/word_counts_word.json (Word's ComputeStatistics on 02, written by
   the build) belongs to the current manuscript_src.md, is within the limits (abstract 250,
   main text 3,000), and the title page quotes it.
5. Supplementary data S1a and S1b (09 and 10, CSV): one row per row of their Q2 output, the
   verbatim columns equal to the output row by row, and the SHA-256 of each file equal to that
   of the file regenerated from outputs/ by exhibits/make_tables.py now; the XLSX (11, if
   present and openpyxl is installed) holds the CSV text cell for cell. The data files are
   checked for blinding too.
6. AMA: in 02, the journal title of each article reference (and nothing else in the list) is
   in italics.

Prints "SKIPPED" and exits 0 when manuscript/ or manuscript/submission/ is absent (both are
git-ignored). Exit 1 on any problem.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_manuscript_numbers as cmn  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SUP = {"ᵃ": "a", "ᵇ": "b", "ᶜ": "c", "ᵈ": "d", "ᵉ": "e", "ᶠ": "f"}
DOI = re.compile(r"10\.5281/zenodo\.(?:\d+|X{3,})")
LIMITS = {"abstract": 250, "main_text": 3000}
BLINDED = ("02_manuscript_anonymised.docx", "05_supplementary_material.docx")
FIGURES = ("03_figure1.tif", "03_figure1.pdf", "04_figure2.tif", "04_figure2.pdf")

# Each file: a list of parts, in order. ("md", file, start, end) takes the units of the
# Markdown file from the line that starts with `start` up to the line that starts with `end`
# (None: the start or the end of the file); ("builder", text) is a line the build adds;
# ("first", file, prefix) is the one unit of the file starting with `prefix`.
SPEC: dict[str, list[tuple]] = {
    "01_title_page.docx": [("md", "first_page_src.md", None, None)],
    "02_manuscript_anonymised.docx": [
        ("md", "manuscript_src.md", None, "## Figure legends"),
        ("md", "exhibits/tables.md", "## Table 1.", "## Table S1."),
        ("md", "manuscript_src.md", "## Figure legends", None),
    ],
    "05_supplementary_material.docx": [
        ("builder", "Supplementary material"),
        ("first", "manuscript_src.md", "# "),
        ("md", "exhibits/tables.md", "## Table S1.", None),
    ],
    "06_cover_letter.docx": [("md", "cover_letter.md", "# Cover letter", None, "drop-first")],
    "07_RECORD_checklist.docx": [("md", "record_checklist.md", None, None)],
    "08_declaration_of_interests.docx": [
        ("builder", "Declaration of interests"),
        ("first", "first_page_src.md", "**Title:**"),
        ("first", "first_page_src.md", "**Author:**"),
        ("first", "first_page_src.md", "**Competing interests:**"),
    ],
}


# --------------------------------------------------------------------------------------
# Normalisation (the same for both sides)
# --------------------------------------------------------------------------------------
def norm(s: str) -> str:
    for k, v in SUP.items():
        s = s.replace(k, f"^{v}^")
    s = s.replace("**", "").replace("*", "")
    s = re.sub(r"\\(?=[^\w\s])", "", s)          # Markdown escapes such as 1\.
    s = s.replace("^^", "")                      # adjacent superscript runs
    s = DOI.sub("10.5281/zenodo.<DOI>", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------------------
# Markdown units
# --------------------------------------------------------------------------------------
def md_slice(text: str, start: str | None, end: str | None) -> str:
    lines = text.splitlines()
    i = 0 if start is None else next(k for k, ln in enumerate(lines) if ln.startswith(start))
    j = len(lines) if end is None else next(k for k, ln in enumerate(lines)
                                            if k > i and ln.startswith(end))
    return "\n".join(lines[i:j])


def md_units(text: str) -> list[str]:
    """Headings, paragraphs, list items and table rows of a Markdown text, normalised."""
    units: list[str] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            units.append(norm(" ".join(para)))
            para.clear()

    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            flush()
        elif s.startswith("#"):
            flush()
            units.append(norm(s.lstrip("#")))
        elif s.startswith("|"):
            flush()
            body = s[1:-1] if s.endswith("|") and not s.endswith("\\|") else s[1:]
            cells = re.split(r"(?<!\\)\|", body)  # an escaped \| stays inside its cell
            if all(re.fullmatch(r"\s*:?-{3,}:?\s*", c) for c in cells):
                continue
            units.append(" | ".join(norm(c) for c in cells))
        elif re.match(r"[-*+] ", s):
            flush()
            para.append(s[2:])
        elif re.match(r"\d+\. ", s):
            flush()
            para.append(s)
        else:
            para.append(s)
    flush()
    return [u for u in units if u]


# --------------------------------------------------------------------------------------
# .docx units
# --------------------------------------------------------------------------------------
def para_text(p: ET.Element) -> str:
    parts = []
    for r in p.iter(f"{W}r"):
        va = r.find(f"{W}rPr/{W}vertAlign")
        sup = va is not None and va.get(f"{W}val") == "superscript"
        txt = "".join((t.text or "") if t.tag == f"{W}t" else " "
                      for t in r if t.tag in (f"{W}t", f"{W}tab", f"{W}br"))
        parts.append(f"^{txt}^" if sup and txt.strip() else txt)
    return "".join(parts)


def docx_units(path: Path) -> list[str]:
    """Body paragraphs (outside tables) and table rows (cells joined by ' | '), in order,
    normalised; empty paragraphs left out."""
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(f"{W}body")
    units: list[str] = []
    for el in body:
        if el.tag == f"{W}p":
            u = norm(para_text(el))
            if u:
                units.append(u)
        elif el.tag == f"{W}tbl":
            for tr in el.iter(f"{W}tr"):
                cells = [" ".join(para_text(p) for p in tc.iter(f"{W}p")) for tc in tr.findall(f"{W}tc")]
                units.append(" | ".join(norm(c) for c in cells))
    return units


def docx_all_text(path: Path) -> str:
    """The text of every XML part of the package (document, headers, footers, properties,
    comments ...), tags removed."""
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                raw = z.read(name).decode("utf-8", errors="replace")
                out.append(re.sub(r"<[^>]+>", "", raw))
                out.append(raw)  # attribute values too (e.g. a hyperlink target)
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# Expected units from the SPEC
# --------------------------------------------------------------------------------------
def expected(ms_dir: Path, name: str) -> tuple[list[str], set[str]]:
    """(expected units, builder lines) of one submission file."""
    out: list[str] = []
    builder: set[str] = set()
    for part in SPEC[name]:
        if part[0] == "builder":
            out.append(norm(part[1]))
            builder.add(norm(part[1]))
        elif part[0] == "first":
            text = (ms_dir / part[1]).read_text(encoding="utf-8")
            if part[2] == "# ":  # the document title (its first line)
                hits = [norm(text.splitlines()[0].lstrip("#"))]
            else:
                hits = [u for u in md_units(text) if u.startswith(norm(part[2]))]
            if len(hits) != 1:
                raise ValueError(f"{part[1]}: {len(hits)} units start with {part[2]!r}")
            out.append(hits[0])
        else:
            text = (ms_dir / part[1]).read_text(encoding="utf-8")
            units = md_units(md_slice(text, part[2], part[3]))
            if len(part) > 4 and part[4] == "drop-first":
                units = units[1:]
            out += units
    return out, builder


def compare(name: str, got: list[str], want: list[str], limit: int = 6) -> list[str]:
    if got == want:
        return []
    out = []
    sm = difflib.SequenceMatcher(None, want, got, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        md = " // ".join(want[i1:i2])[:300] or "(nothing)"
        dx = " // ".join(got[j1:j2])[:300] or "(nothing)"
        out.append(f"TIE {name}: {tag} at markdown unit {i1 + 1}, docx unit {j1 + 1}:\n"
                   f"    markdown: {md}\n    docx:     {dx}")
        if len(out) >= limit:
            out.append(f"TIE {name}: further differences not listed")
            break
    return out


# --------------------------------------------------------------------------------------
# Blinding, identifiers, word counts
# --------------------------------------------------------------------------------------
def markers(ms_dir: Path, root: Path) -> list[str]:
    """Author markers: the plan's (name, ORCID, institution, repository) and the title page's
    e-mail, telephone digits and postcode."""
    out = list(cmn.author_markers(root))
    fp = ms_dir / "first_page_src.md"
    if fp.exists():
        t = fp.read_text(encoding="utf-8")
        out += re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t)
        out += [re.sub(r"\D", "", m) for m in re.findall(r"\+?\d[\d -]{8,}\d", t)]
        out += re.findall(r"\b\d{6}\b", t)  # Indian postal code of the affiliation
    return sorted({m for m in out if m and len(m) >= 5}, key=str.lower)


def blinding_problems(name: str, haystack: str, marks: list[str]) -> list[str]:
    low = haystack.lower()
    return [f"BLINDING in {name}: contains {m!r}" for m in marks if m.lower() in low]


def identifier_problems(name: str, units: list[str]) -> list[str]:
    text = "\n".join(units)
    if name.startswith("02_"):
        text = text.split("\nReferences\n", 1)[0]
    out = []
    for pat, what in cmn.BANNED:
        for m in re.finditer(pat, text):
            out.append(f"WORDING in {name}: {what}: {m.group()!r}")
    return out


# --------------------------------------------------------------------------------------
# Supplementary data S1a and S1b: confirmed against outputs/
# --------------------------------------------------------------------------------------
DATA = [("09_supplementary_data_S1a_registered.csv", "outputs/q2_discrepancies.csv", "S1a registered"),
        ("10_supplementary_data_S1b_corrected.csv", "outputs/q2_discrepancies_corrected.csv", "S1b corrected")]
XLSX = "11_supplementary_data_S1.xlsx"


def make_tables():
    """exhibits/make_tables.py, which writes the data files from outputs/."""
    ex = str(ROOT / "exhibits")
    if ex not in sys.path:
        sys.path.insert(0, ex)
    import make_tables as mt
    return mt


def data_problems(sub: Path, root: Path = ROOT) -> list[str]:
    """Each data CSV has one row per row of its output, its verbatim columns equal the output's
    row by row, and its SHA-256 equals that of the file regenerated from outputs/ now; the
    XLSX (if present) holds the CSV text cell for cell."""
    mt = make_tables()
    out: list[str] = []
    csv_rows: dict[str, list[list[str]]] = {}
    for name, output, sheet in DATA:
        path = sub / name
        if not path.exists():
            out.append(f"MISSING: {name}")
            continue
        raw = path.read_bytes()
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
        csv_rows[sheet] = rows
        with open(root / output, newline="", encoding="utf-8") as f:
            src = list(csv.DictReader(f))
        if len(rows) - 1 != len(src):
            out.append(f"DATA {name}: {len(rows) - 1} rows, {output} has {len(src)}")
        header = [h for h, _, _ in mt.DATA_COLUMNS]
        if rows and rows[0] != header:
            out.append(f"DATA {name}: header differs from the column dictionary")
        verbatim = [(j, col) for j, (_, col, _) in enumerate(mt.DATA_COLUMNS) if not col.startswith("=")]
        bad = [i for i, (r, s) in enumerate(zip(rows[1:], src), 1)
               if len(r) != len(header) or any(r[j] != s[col] for j, col in verbatim)]
        if bad:
            out.append(f"DATA {name}: {len(bad)} row(s) differ from {output} in a verbatim column "
                       f"(first: row {bad[0]})")
        want = hashlib.sha256(mt.supplementary_data_bytes(output)).hexdigest()
        if hashlib.sha256(raw).hexdigest() != want:
            out.append(f"DATA {name}: SHA-256 differs from the file regenerated from {output}")
    xl = sub / XLSX
    if xl.exists():
        try:
            from openpyxl import load_workbook
        except ImportError:
            return out
        wb = load_workbook(xl, read_only=True)
        for sheet, rows in csv_rows.items():
            if sheet not in wb.sheetnames:
                out.append(f"DATA {XLSX}: no sheet {sheet!r}")
                continue
            got = [["" if v is None else str(v) for v in r] for r in wb[sheet].iter_rows(values_only=True)]
            got = [r + [""] * (len(rows[0]) - len(r)) for r in got]
            if got != rows:
                k = next((i for i, (a, b) in enumerate(zip(got, rows)) if a != b), min(len(got), len(rows)))
                out.append(f"DATA {XLSX} sheet {sheet!r}: differs from the CSV at row {k + 1}")
        wb.close()
    return out


# --------------------------------------------------------------------------------------
# AMA: journal titles in italics in the reference list of 02
# --------------------------------------------------------------------------------------
JOURNAL = re.compile(r"\. ([^.]+?)\. ((?:18|19|20)\d\d;)")


def italic_text(p: ET.Element) -> str:
    parts = []
    for r in p.iter(f"{W}r"):
        i = r.find(f"{W}rPr/{W}i")
        if i is not None and i.get(f"{W}val") not in ("0", "false"):
            parts.append("".join(t.text or "" for t in r.iter(f"{W}t")))
    return "".join(parts)


def italics_problems(path: Path, ms_text: str) -> list[str]:
    """Each article reference's journal title (by JOURNAL, from the Markdown) is the italic text
    of its reference paragraph in the .docx, and nothing else in the list is italic."""
    refs = md_slice(ms_text, "## References", "## Figure legends").splitlines()
    want = {}
    for ln in refs:
        m = re.match(r"(\d+)\. ", ln)
        if m:
            j = JOURNAL.search(ln)
            want[m.group(1)] = j.group(1) if j else ""
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(f"{W}body")
    got, in_refs = {}, False
    for p in body.findall(f"{W}p"):
        t = norm(para_text(p))
        if t == "References":
            in_refs = True
            continue
        if in_refs:
            m = re.match(r"(\d+)\. ", t)
            if not m:
                if t:
                    break
                continue
            got[m.group(1)] = italic_text(p)
    out = [f"ITALICS 02 reference {k}: journal title {want[k]!r} in italics expected, "
           f"italic text is {got.get(k, '')!r}" for k in want if got.get(k, "") != want[k]]
    return out


def word_count_problems(ms_dir: Path, title_units: list[str]) -> list[str]:
    p = ms_dir / "word_counts_word.json"
    if not p.exists():
        return ["WORDS: manuscript/word_counts_word.json missing (build with Word: "
                "python -I tools/build_submission.py)"]
    w = json.loads(p.read_text(encoding="utf-8"))
    out = []
    md5 = hashlib.md5((ms_dir / "manuscript_src.md").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if w.get("source_md5") != md5:
        out.append("WORDS: word_counts_word.json is stale (manuscript_src.md changed): rebuild")
    for k, lim in LIMITS.items():
        if w[k] > lim:
            out.append(f"WORDS: Word counts {w[k]} words in the {k}, over the limit of {lim}")
    flat = " ".join(title_units)
    for want in (f"main text (Introduction to Discussion) {w['main_text']:,} words",
                 f"abstract {w['abstract']} words"):
        if want not in flat:
            out.append(f"WORDS: the title page does not quote Word's count {want!r}")
    return out


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
def problems(ms_dir: Path | None = None, root: Path = ROOT) -> list[str]:
    ms_dir = ms_dir or root / "manuscript"
    sub = ms_dir / "submission"
    out: list[str] = []
    marks = markers(ms_dir, root)
    units_of: dict[str, list[str]] = {}
    for name in SPEC:
        path = sub / name
        if not path.exists():
            out.append(f"MISSING: {name}")
            continue
        got = docx_units(path)
        units_of[name] = got
        want, builder = expected(ms_dir, name)
        out += compare(name, got, want)
        if name in BLINDED:
            out += blinding_problems(name, docx_all_text(path), marks)
            out += identifier_problems(name, got)
    for name in FIGURES:
        path = sub / name
        if not path.exists():
            out.append(f"MISSING: {name}")
            continue
        out += blinding_problems(name, path.read_bytes().decode("latin-1"), marks)
    if "02_manuscript_anonymised.docx" in units_of:
        out += italics_problems(sub / "02_manuscript_anonymised.docx",
                                (ms_dir / "manuscript_src.md").read_text(encoding="utf-8"))
    out += data_problems(sub, root)
    for name in [n for n, _, _ in DATA] + [XLSX]:
        path = sub / name
        if path.exists():
            hay = docx_all_text(path) if name.endswith(".xlsx") else path.read_text(encoding="utf-8")
            out += blinding_problems(name, hay, marks)
    if "01_title_page.docx" in units_of:
        out += word_count_problems(ms_dir, units_of["01_title_page.docx"])
    return out


def notes(ms_dir: Path) -> list[str]:
    """Reminders that are not failures."""
    p = ms_dir / "submission" / "01_title_page.docx"
    if p.exists() and "zenodo.XXXXXXX" in docx_all_text(p):
        return ["note: the title page still holds the Zenodo DOI placeholder (rebuild with --doi at release)"]
    return []


def main(root: Path = ROOT) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ms_dir = root / "manuscript"
    if not ms_dir.is_dir() or not (ms_dir / "submission").is_dir():
        print("SKIPPED: manuscript/ or manuscript/submission/ not present (kept private, not in this repository)")
        return 0
    found = problems(ms_dir, root)
    for ln in found:
        print(ln)
    for ln in notes(ms_dir):
        print(ln)
    n_units = sum(len(docx_units(ms_dir / "submission" / n)) for n in SPEC
                  if (ms_dir / "submission" / n).exists())
    print(f"docx tie: {len(SPEC)} files, {n_units} paragraphs and table rows tied to the Markdown; "
          f"blinding of 02, 05, the figures and the data; supplementary data S1a and S1b against "
          f"outputs/; journal titles in italics; {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
