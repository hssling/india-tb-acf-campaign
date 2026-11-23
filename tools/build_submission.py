# Adapted from hssling/india-state-tb-score (MIT), manuscript/build_docx.py, commit 05bcaa7; modified: Public Health (Elsevier) submission set; sources are the private manuscript_src.md, first_page_src.md, cover_letter.md, record_checklist.md and exhibits/tables.md; tables with top, header and bottom rules only; superscript letter footnotes; line numbers; TIFF from the vector PDF
"""Build the Public Health submission set into <manuscript folder>/submission/ (git-ignored, private).

Run as: python -I tools/build_submission.py [--manuscript-dir DIR] [--out DIR] [--doi 10.5281/zenodo.NNNNNNN] [--no-word]

The manuscript folder is DIR: default manuscript/ext (the extension paper); the audit-framed
v1.0.0 manuscript is built with --manuscript-dir manuscript/v1_audit. A relative DIR is taken
from the repository root.

Needs pandoc on PATH, python-docx, Pillow and PyMuPDF (fitz); Microsoft Word (through
PowerShell COM) for the word counts unless --no-word. Sources (in the folder, git-ignored):
manuscript_src.md (blinded), first_page_src.md, cover_letter.md, record_checklist.md and
exhibits/ (tables.md, figure1.pdf ... figureN.pdf). Nothing is written outside the folder.
The folder's profile (verification/check_manuscript_numbers.profile_for: the "profile" key of
its section_phrases.json) selects the submission set (LAYOUTS). --out DIR writes the set to DIR
instead of <folder>/submission (a relative DIR is taken from the repository root). The build
refuses to write into a folder that holds a SUBMITTED_YYYY-MM-DD.txt manifest: a submitted set is
frozen.

Output (docs/journal_rules.md; Elsevier generic style): A4, 2.5 cm margins, Times New Roman
12 pt, double spacing, page numbers at the foot; continuous line numbers in the anonymised
manuscript. Tables: no vertical rules, only the top, header and bottom rules; footnote marks
as superscript lowercase letters; 10 pt single-spaced cells (9 pt in the landscape supplement).

Profile "ext" (manuscript/ext, the extension paper; 4 figures + Table 1 = 5 display items):
  01_title_page.docx              title page (not blinded); --doi fills the Zenodo DOI, otherwise
                                  the placeholder is highlighted
  02_manuscript_anonymised.docx   blinded text, Box 1, References, Table 1, figure legends
  03_figure1.tif / 03_figure1.pdf Figure 1: TIFF (LZW, TIFF_DPI) and the vector PDF
  04_figure2 ... 06_figure4       Figures 2 to 4, likewise
  07_supplementary_material.docx  Tables S1 to S8, landscape (blinded). Every table is complete
                                  here (each equals its CSV row for row, checked by
                                  check_docx_tie), so there are no separate data files
  08_cover_letter.docx
  09_RECORD_checklist.docx
  10_declaration_of_interests.docx

Profile "ijtb" (manuscript/ext_v2, the Indian Journal of Tuberculosis version; docs of the set in
verification/check_docx_tie.py). Sources, besides those above: highlights.md, declarations.md,
declaration_of_interests.md, copyright_transfer.md and supplement_text.md. manuscript_src.md is
unblinded with blinding spans (check_manuscript_numbers.render); --doi fills the Zenodo DOI in every
file that holds the placeholder.
  01_Cover_Letter.docx, 02_Title_Page.docx, 03_Manuscript.docx (unblinded, line-numbered),
  04_Highlights.docx, 05_Figure_Captions.docx (each legend under its PNG preview),
  06_Declarations.docx, 07_Declaration_of_Interests.docx, 08_Copyright_Transfer.docx and .pdf
  (through Word; not with --no-word), 09_Supplementary_Material.docx (the supplementary text and
  Tables S1 to S9, landscape), 10_RECORD_Checklist.docx, 11_Figure_1.tif to 14_Figure_4.tif
  (TIFF_DPI_IJTB, LZW, from the vector PDF), 91_Manuscript_Blinded.docx (the blinded rendering),
  92_Figure_1_preview.png to 95_Figure_4_preview.png (copies of exhibits/figureN.png). Word counts
  are taken on 03.

Profile "v1" (manuscript/v1_audit, the audit-framed v1.0.0 manuscript):
  01, 02 (Tables 1-3), 03-04 Figures 1-2, 05_supplementary_material.docx (Tables S1 to S4 and
  the column dictionary of the data), 06 cover letter, 07 RECORD checklist, 08 declaration of
  interests, 09_supplementary_data_S1a_registered.csv and 10_supplementary_data_S1b_corrected.csv
  (every Q2 entry pair, copied from <folder>/exhibits/, written there by exhibits/make_tables.py)
  and 11_supplementary_data_S1.xlsx (both, one sheet each; only if openpyxl is installed).

Word's own counts of the abstract and the main text of 02 go to
<folder>/word_counts_word.json (tools/word_count_word.ps1); the title page must quote them
(verification/check_docx_tie.py checks it). The text of every .docx is tied to its Markdown
source by verification/check_docx_tie.py.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import NamedTuple

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.run import Run

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification.check_manuscript_numbers import profile_for, render  # noqa: E402

DEFAULT_MS_DIR = "manuscript/ext"  # the extension paper; v1.0.0 (audit framing) is manuscript/v1_audit
MS = ROOT / DEFAULT_MS_DIR
EX = MS / "exhibits"
OUT = MS / "submission"


class Layout(NamedTuple):
    """The file names of one submission set (the same as verification/check_docx_tie.LAYOUTS)."""
    figures: tuple[str, ...]   # the file-number prefix of Figure 1, 2, ...
    supplement: str
    cover: str
    record: str
    declaration: str
    data: bool                 # v1: supplementary data S1a and S1b (CSV) and the XLSX


LAYOUTS: dict[str, Layout] = {
    "v1": Layout(("03", "04"), "05_supplementary_material.docx", "06_cover_letter.docx",
                 "07_RECORD_checklist.docx", "08_declaration_of_interests.docx", True),
    "ext": Layout(("03", "04", "05", "06"), "07_supplementary_material.docx", "08_cover_letter.docx",
                  "09_RECORD_checklist.docx", "10_declaration_of_interests.docx", False),
}
# The IJTB set (profile "ijtb"): the figure prefixes are those of 11_Figure_1.tif ... 14_Figure_4.tif;
# its other files are named in build_ijtb (and in verification/check_docx_tie.LAYOUTS["ijtb"]).
LAYOUTS["ijtb"] = Layout(("11", "12", "13", "14"), "09_Supplementary_Material.docx", "01_Cover_Letter.docx",
                         "10_RECORD_Checklist.docx", "07_Declaration_of_Interests.docx", False)
LAY = LAYOUTS["ext"]
TIFF_DPI_IJTB = 600  # the journal's rule for the IJTB set: 600 dpi TIFF print masters
SUBMITTED = re.compile(r"SUBMITTED_\d{4}-\d{2}-\d{2}\.txt")


def configure(ms_dir: Path, out: Path | None = None) -> None:
    """Point the build at a manuscript folder: its sources, exhibits/, its output folder (default
    <folder>/submission) and its set."""
    global MS, EX, OUT, LAY
    MS, EX, OUT = ms_dir, ms_dir / "exhibits", out or ms_dir / "submission"
    LAY = LAYOUTS[profile_for(ms_dir)]


def frozen(out: Path) -> list[str]:
    """The SUBMITTED_ manifests in `out` (a submitted set, which the build must not overwrite)."""
    return sorted(p.name for p in out.iterdir() if p.is_file() and SUBMITTED.fullmatch(p.name)) if out.is_dir() else []


FONT = "Times New Roman"
DOI_PLACEHOLDER = "10.5281/zenodo.XXXXXXX"
DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")
TIFF_DPI = 1000  # Elsevier artwork: line art 1000 dpi (combination 500, halftone 300)
PAGEBREAK = '\n\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'
INDENT = "\u00a0"  # no-break space; tables.md marks a sub-row by leading spaces in its first cell
SUP_LETTERS = {"ᵃ": "a", "ᵇ": "b", "ᶜ": "c", "ᵈ": "d", "ᵉ": "e", "ᶠ": "f"}
PANDOC_FROM = "markdown+pipe_tables+superscript+fenced_divs+raw_attribute-smart-subscript-citations-tex_math_dollars-raw_html-auto_identifiers"


# --------------------------------------------------------------------------------------
# Markdown preparation (the sources are never written)
# --------------------------------------------------------------------------------------
def read(rel: str) -> str:
    return (MS / rel).read_text(encoding="utf-8")


def sup_letters(md: str) -> str:
    """Unicode modifier letters (ᵃ) as Markdown superscripts (^a^), so Word sets a real
    superscript lowercase letter."""
    for k, v in SUP_LETTERS.items():
        md = md.replace(k, f"^{v}^")
    return md


def literal_numbers(md: str) -> str:
    """Numbered list items ('1. Author ...') kept as literal text, so the reference numbers
    are part of the text (and of the tie check), not Word list numbering; each item is its
    own paragraph."""
    return re.sub(r"(?m)^(\d+)\. ", r"\n\1\\. ", md)


# AMA: the journal title of an article reference, between its title and 'YYYY;' (AMA journal
# abbreviations carry no full stops). Reports, web pages and parliamentary answers do not match.
JOURNAL = re.compile(r"\. ([^.]+?)\. ((?:18|19|20)\d\d;)")


def italic_journals(refs: str) -> str:
    """Each journal title of the reference list in italics (AMA)."""
    out = []
    for ln in refs.splitlines():
        if re.match(r"\d+\. ", ln):
            ln = JOURNAL.sub(lambda m: f". *{m.group(1)}*. {m.group(2)}", ln, count=1)
        out.append(ln)
    return "\n".join(out) + "\n"


def between(text: str, start: str, end: str | None) -> str:
    """text from the line that starts with `start` up to (not including) the line that starts
    with `end` (or the end of the text)."""
    i = text.index("\n" + start) + 1 if not text.startswith(start) else 0
    j = text.index("\n" + end, i) + 1 if end else len(text)
    return text[i:j]


def table_block(md: str) -> str:
    """One '## Table N. Title' section of tables.md as pandoc Markdown: the title as a
    'Table Title' paragraph ('Table N.' bold), the table(s), and the notes below as
    'Table Note' paragraphs."""
    lines = md.strip("\n").splitlines()
    m = re.match(r"## ((?:Table|Supplementary data) S?\d+[ab]?(?: and S\d+[ab]?)?\.) (.*)", lines[0])
    if not m:
        raise SystemExit(f"not a table heading: {lines[0]!r}")
    out = ['::: {custom-style="Table Title"}', f"**{m.group(1)}** {m.group(2)}", ":::", ""]
    para: list[str] = []
    for ln in lines[1:] + [""]:
        if ln.startswith("|"):
            # the leading spaces of a sub-row's first cell survive pandoc as no-break spaces
            out.append(re.sub(r"^\|( {2,})(?=\S)", lambda m: "| " + INDENT * (len(m.group(1)) - 1), ln))
            continue
        if ln.strip():
            para.append(ln)
            continue
        if para:
            out += ["", '::: {custom-style="Table Note"}', " ".join(para), ":::", ""]
            para = []
        elif out[-1] != "":
            out.append("")
    return sup_letters("\n".join(out)) + "\n"


def tables(names_from: str, names_to: str | None) -> list[str]:
    """The '## Table ...' sections of tables.md from names_from up to names_to."""
    part = between(read("exhibits/tables.md"), names_from, names_to)
    blocks = re.split(r"(?m)^(?=## )", part)
    return [table_block(b) for b in blocks if b.startswith(("## Table ", "## Supplementary data "))]


def manuscript_md(blinded: bool = False) -> str:
    """The manuscript, its tables and its figure legends; the source's blinding spans rendered
    unblinded (the default) or blinded."""
    ms = render(read("manuscript_src.md"), blinded=blinded)
    body = between(ms, "# ", "## References")
    refs = between(ms, "## References", "## Figure legends")
    legends = between(ms, "## Figure legends", None)
    parts = [body.rstrip(), PAGEBREAK, literal_numbers(italic_journals(refs)).rstrip()]
    for t in tables("## Table 1.", "## Table S1."):
        parts += [PAGEBREAK, t]
    parts += [PAGEBREAK, legends]
    return "".join(parts)


def title_page_md(doi: str | None) -> str:
    fp = read("first_page_src.md")
    if fp.count(DOI_PLACEHOLDER) != 1:
        raise SystemExit(f"first_page_src.md must hold the DOI placeholder {DOI_PLACEHOLDER} once")
    if doi:
        fp = fp.replace(DOI_PLACEHOLDER, doi)
    return fp


def supplement_md(text: str | None = None) -> str:
    """The supplementary material: a heading, the title, `text` (the supplementary text, if any) and
    Tables S1 onwards."""
    title = read("manuscript_src.md").splitlines()[0]
    if not title.startswith("# "):
        raise SystemExit("manuscript_src.md must start with its '# ' title")
    parts = ["# Supplementary material\n\n", title[2:].strip(), "\n"]
    if text:
        parts += ["\n", text.strip("\n"), "\n"]
    for i, t in enumerate(tables("## Table S1.", None)):
        parts += [PAGEBREAK, t]
    return "".join(parts)


def cover_letter_md() -> str:
    """The cover letter without its '# Cover letter' heading; the lines of one paragraph
    (the address block) kept apart by hard line breaks."""
    cl = read("cover_letter.md")
    lines = cl.splitlines()
    if not lines[0].startswith("# "):
        raise SystemExit("cover_letter.md must start with a '# ' heading")
    blocks = re.split(r"\n\s*\n", "\n".join(lines[1:]).strip())
    out = []
    for b in blocks:
        bl = b.splitlines()
        if len(bl) > 1 and not any(ln.lstrip().startswith(("-", "|")) for ln in bl):
            b = "\\\n".join(bl)
        out.append(b)
    return "\n\n".join(out) + "\n"


def declaration_md(doi: str | None) -> str:
    """Elsevier's separate declaration of interests: the title, the author and the title
    page's declarations-of-interest statement, word for word."""
    fp = title_page_md(doi)
    keep = []
    for key in ("**Title:**", "**Author:**", "**Declarations of interest:**"):
        hit = [ln for ln in fp.splitlines() if ln.startswith(key)]
        if len(hit) != 1:
            raise SystemExit(f"first_page_src.md: expected one line starting {key}")
        keep.append(hit[0])
    return "# Declaration of interests\n\n" + "\n\n".join(keep) + "\n"


# --------------------------------------------------------------------------------------
# pandoc and the reference document
# --------------------------------------------------------------------------------------
def set_font(obj, size: float | None = 12) -> None:
    """Times New Roman (every script slot) at `size` for a style or a run."""
    obj.font.name = FONT
    if size:
        obj.font.size = Pt(size)
    rpr = obj.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]


def make_reference(path: Path) -> None:
    raw = subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"],
                         capture_output=True, check=True).stdout
    path.write_bytes(raw)
    doc = Document(str(path))
    for name in ("Table Title", "Table Note"):
        if name not in [s.name for s in doc.styles]:
            doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH).base_style = doc.styles["Normal"]
    for st in doc.styles:
        if st.type == WD_STYLE_TYPE.PARAGRAPH:
            set_font(st, 12)
            st.font.color.rgb = None
            pf = st.paragraph_format
            pf.line_spacing = 2.0
            pf.space_before = Pt(0)
            pf.space_after = Pt(6)
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            if st.name.startswith("Heading") or st.name == "Title":
                st.font.bold = True
                st.font.italic = False
                pf.keep_with_next = True
                pf.space_before = Pt(12)
        elif st.type == WD_STYLE_TYPE.CHARACTER:
            set_font(st, None)
            st.font.color.rgb = None
    doc.styles["Heading 1"].font.size = Pt(14)
    tt = doc.styles["Table Title"]
    tt.paragraph_format.keep_with_next = True
    tt.paragraph_format.line_spacing = 1.5
    tn = doc.styles["Table Note"]
    set_font(tn, 10)
    tn.paragraph_format.line_spacing = 1.0
    tn.paragraph_format.space_before = Pt(3)
    tn.paragraph_format.space_after = Pt(3)
    doc.save(str(path))


def run_pandoc(md: str, out: Path, ref: Path, tmp: Path, resources: Path | None = None) -> None:
    src = tmp / (out.stem + ".md")
    src.write_text(md, encoding="utf-8")
    extra = ["--resource-path", str(resources)] if resources else []
    subprocess.run(["pandoc", str(src), "-f", PANDOC_FROM, "--reference-doc", str(ref),
                    "-o", str(out)] + extra, check=True)


# --------------------------------------------------------------------------------------
# Post-processing with python-docx
# --------------------------------------------------------------------------------------
def page_setup(doc, landscape: bool = False, line_numbers: bool = False) -> None:
    for sec in doc.sections:
        if landscape:
            sec.orientation = WD_ORIENT.LANDSCAPE
            sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
        else:
            sec.orientation = WD_ORIENT.PORTRAIT
            sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Cm(2.5)
        sec.footer_distance = Cm(1.25)
        sp = sec._sectPr
        for e in sp.findall(qn("w:lnNumType")):
            sp.remove(e)
        if line_numbers:
            ln = OxmlElement("w:lnNumType")
            ln.set(qn("w:countBy"), "1")
            ln.set(qn("w:restart"), "continuous")
            ln.set(qn("w:distance"), "283")
            anchor = None
            for tag in ("w:pgBorders", "w:paperSrc", "w:pgMar"):
                anchor = sp.find(qn(tag))
                if anchor is not None:
                    break
            anchor.addnext(ln)
        p = sec.footer.paragraphs[0] if sec.footer.paragraphs else sec.footer.add_paragraph()
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        for kind in ("begin", "instr", "separate", "text", "end"):
            if kind == "instr":
                e = OxmlElement("w:instrText")
                e.set(qn("xml:space"), "preserve")
                e.text = " PAGE "
            elif kind == "text":
                e = OxmlElement("w:t")
                e.text = "1"
            else:
                e = OxmlElement("w:fldChar")
                e.set(qn("w:fldCharType"), kind)
            run._r.append(e)
        set_font(run, 11)


def border(tag: str, val: str = "single", sz: int = 8) -> OxmlElement:
    e = OxmlElement(f"w:{tag}")
    e.set(qn("w:val"), val)
    if val != "nil":
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "000000")
    return e


TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
               "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders",
               "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"]
TCPR_ORDER = ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap",
              "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"]


def reorder(parent, order: list[str]) -> None:
    kids = sorted(list(parent), key=lambda e: order.index(e.tag.split("}")[1])
                  if e.tag.split("}")[1] in order else len(order))
    for e in kids:
        parent.remove(e)
    for e in kids:
        parent.append(e)


def col_texts(t) -> list[list[str]]:
    """The cell texts of each column (a merged spanning cell is left out: it spans the table)."""
    cols: list[list[str]] = [[] for _ in t.columns]
    for tr in t._tbl.findall(qn("w:tr")):
        tcs = tr.findall(qn("w:tc"))
        if len(tcs) != len(cols):
            continue
        for j, tc in enumerate(tcs):
            cols[j].append("".join(x.text or "" for x in tc.iter(qn("w:t"))).replace(INDENT, " "))
    return cols


def col_mins(t, size: float) -> list[float]:
    """Each column's minimum width (twips): its longest word, the cell margins and a little slack."""
    char = size * 20 * 0.5          # twips per character: half an em
    pad = 2 * 108 + 20              # the cell margins and a little slack
    return [(max((len(w) for s in texts for w in s.split()), default=3) + 1) * char + pad
            for texts in col_texts(t)]


def fit_size(t, total: int, size: float, floor: float = 7.0) -> float:
    """`size`, or the largest smaller size (in half points, down to `floor`) at which every
    column's longest word fits, so that no number or word breaks inside a cell."""
    while sum(col_mins(t, size)) >= total and size - 0.5 >= floor:
        size -= 0.5
    return size


def col_widths(t, total: int, size: float) -> list[int]:
    """Column widths (twips). Each column is at least as wide as its longest word, so that a
    number such as 205,331,541 never breaks (fit_size chooses a size at which this is
    possible); the rest of the width goes to the columns whose typical (90th centile) cell
    would otherwise wrap."""
    char = size * 20 * 0.5          # twips per character: half an em
    pad = 2 * 108 + 20              # the cell margins and a little slack
    mins, wants = col_mins(t, size), []
    for j, texts in enumerate(col_texts(t)):
        lengths = sorted(len(s.strip()) for s in texts[1:]) or [3]
        typical = lengths[int(0.9 * (len(lengths) - 1))]  # 90th centile of the body cells
        wants.append(max(min(typical, 150) * char + pad, mins[j]))
    if sum(mins) >= total:
        raw = [total * m / sum(mins) for m in mins]
    elif sum(wants) <= total:
        raw = [w + (total - sum(wants)) * w / sum(wants) for w in wants]
    else:
        # every column wraps: widths in proportion to the typical cell, so the long columns
        # wrap to about the same number of lines; a column below its minimum is held there
        fixed: dict[int, float] = {}
        while True:
            free = total - sum(fixed.values())
            rest = sum(w for j, w in enumerate(wants) if j not in fixed)
            raw = [fixed.get(j, free * w / rest) for j, w in enumerate(wants)]
            low = [j for j, (x, m) in enumerate(zip(raw, mins)) if j not in fixed and x < m]
            if not low:
                break
            for j in low:
                fixed[j] = mins[j]
    widths = [int(round(x)) for x in raw]
    widths[-1] += total - sum(widths)
    return widths


def is_bold_run(r) -> bool:
    rpr = r.find(qn("w:rPr"))
    b = rpr.find(qn("w:b")) if rpr is not None else None
    return b is not None and b.get(qn("w:val")) not in ("0", "false")


def cell_texts(tr) -> list[str]:
    return ["".join(x.text or "" for x in tc.iter(qn("w:t"))) for tc in tr.findall(qn("w:tc"))]


def is_bold_row(tr) -> bool:
    """Every non-empty run of the row is bold (a heading row of a block, '| **Years** | ...')."""
    runs = [r for r in tr.iter(qn("w:r")) if "".join(x.text or "" for x in r.iter(qn("w:t"))).strip()]
    return bool(runs) and all(map(is_bold_run, runs))


def spanning_rows(tbl, first: int = 1) -> list[int]:
    """Rows from `first` on (after the header by default) whose first cell is wholly bold and
    whose other cells are empty (tables.md writes '| **Label** | | ... |'): each becomes one cell
    spanning the table, and the row after it heads the block below."""
    out = []
    for i, tr in enumerate(tbl.findall(qn("w:tr"))):
        tcs = tr.findall(qn("w:tc"))
        if i < first or len(tcs) < 2:
            continue
        texts = ["".join(x.text or "" for x in tc.iter(qn("w:t"))) for tc in tcs]
        runs = [r for r in tcs[0].iter(qn("w:r")) if "".join(x.text or "" for x in r.iter(qn("w:t"))).strip()]
        if texts[0].strip() and not any(x.strip() for x in texts[1:]) and runs and all(map(is_bold_run, runs)):
            out.append(i)
    return out


def set_cell_border(tc, edge: str, val: str, sz: int = 6) -> None:
    tb = tc.get_or_add_tcPr().find(qn("w:tcBorders"))
    old = tb.find(qn(f"w:{edge}"))
    new = border(edge, val, sz)
    if old is not None:
        old.addprevious(new)
        tb.remove(old)
    else:
        tb.append(new)


def merge_spanning_rows(tbl, total: int) -> None:
    """One cell across the table for each spanning row, with a rule above it; a rule below the
    heading row that follows it."""
    rows = tbl.findall(qn("w:tr"))
    ncols = len(tbl.tblGrid.findall(qn("w:gridCol")))
    for i in spanning_rows(tbl, first=0):
        tcs = rows[i].findall(qn("w:tc"))
        for tc in tcs[1:]:
            rows[i].remove(tc)
        tcPr = tcs[0].get_or_add_tcPr()
        tcPr.find(qn("w:tcW")).set(qn("w:w"), str(total))
        for e in tcPr.findall(qn("w:gridSpan")):
            tcPr.remove(e)
        gs = OxmlElement("w:gridSpan")
        gs.set(qn("w:val"), str(ncols))
        tcPr.append(gs)
        reorder(tcPr, TCPR_ORDER)
        set_cell_border(tcs[0], "top", "single")
        if i + 1 < len(rows):
            for tc in rows[i + 1].findall(qn("w:tc")):
                set_cell_border(tc, "bottom", "single")


GAP = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:pPr>'
       '<w:suppressLineNumbers/><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>'
       '<w:rPr><w:sz w:val="2"/>'
       '</w:rPr></w:pPr></w:p>')


def split_blocks(doc) -> int:
    """A table with spanning rows (a block label, '| **Label** | | ... |', with its own heading
    row below) is split before each spanning row into separate Word tables, kept apart by an
    empty 1-pt paragraph (not line-numbered). Each block then repeats its own label and column headings on a new
    page, not the first block's headings, and gets column widths of its own. The rows, and their
    order, are unchanged. Returns the number of blocks made."""
    from docx.oxml import parse_xml
    n = 0
    for t in list(doc.tables):
        tbl = t._tbl
        idx = spanning_rows(tbl)
        if not idx:
            continue
        rows = tbl.findall(qn("w:tr"))
        anchor = tbl
        for a, b in zip(idx, idx[1:] + [len(rows)]):
            new = OxmlElement("w:tbl")
            new.append(copy.deepcopy(tbl.tblPr))
            new.append(copy.deepcopy(tbl.tblGrid))
            for tr in rows[a:b]:
                new.append(tr)  # moved, not copied
            gap = parse_xml(GAP)
            anchor.addnext(gap)
            gap.addnext(new)
            anchor = new
            n += 1
    return n


def followed_by_block(tbl) -> bool:
    """The table is followed (after the gap paragraph) by a block split from it."""
    gap = tbl.getnext()
    nxt = gap.getnext() if gap is not None and gap.tag == qn("w:p") and not "".join(
        x.text or "" for x in gap.iter(qn("w:t"))) else None
    return nxt is not None and nxt.tag == qn("w:tbl") and 0 in spanning_rows(nxt, first=0)


def format_table(t, total: int, size: float) -> None:
    """Top, header and bottom rules only (no vertical rules), and a rule above a spanning row
    and below the heading row under it; fixed widths over the text block; the header row (for
    a block, its label and heading rows) repeated on each page; single-spaced cells at `size`
    pt. A table followed by its next block has no bottom rule: the block's top rule is it."""
    tbl = t._tbl
    rows0 = tbl.findall(qn("w:tr"))
    heads = 1  # header rows: the column headings, or a block's label and its heading row
    if 0 in spanning_rows(tbl, first=0):
        heads = 2 if len(rows0) > 1 and is_bold_row(rows0[1]) else 1
    closed = not followed_by_block(tbl)
    pr = tbl.tblPr
    for tag in ("tblW", "tblInd", "tblLayout", "jc", "tblBorders"):
        for e in pr.findall(qn(f"w:{tag}")):
            pr.remove(e)
    tw = OxmlElement("w:tblW")
    tw.set(qn("w:w"), str(total))
    tw.set(qn("w:type"), "dxa")
    pr.append(tw)
    bd = OxmlElement("w:tblBorders")
    for edge, val in (("top", "single"), ("left", "nil"), ("bottom", "single"), ("right", "nil"),
                      ("insideH", "nil"), ("insideV", "nil")):
        bd.append(border(edge, val))
    pr.append(bd)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    pr.append(lay)
    reorder(pr, TBLPR_ORDER)
    widths = col_widths(t, total, size)
    for c, w in zip(tbl.tblGrid.findall(qn("w:gridCol")), widths):
        c.set(qn("w:w"), str(w))
    rows = tbl.findall(qn("w:tr"))
    for i, tr in enumerate(rows):
        trPr = tr.get_or_add_trPr()
        for tag in ("w:cantSplit", "w:tblHeader"):
            for e in trPr.findall(qn(tag)):
                trPr.remove(e)
        trPr.append(OxmlElement("w:cantSplit"))
        if i < heads:
            trPr.append(OxmlElement("w:tblHeader"))
        for tc, w in zip(tr.findall(qn("w:tc")), widths):
            tcPr = tc.get_or_add_tcPr()
            for tag in ("w:tcW", "w:tcBorders"):
                for e in tcPr.findall(qn(tag)):
                    tcPr.remove(e)
            e = OxmlElement("w:tcW")
            e.set(qn("w:w"), str(w))
            e.set(qn("w:type"), "dxa")
            tcPr.append(e)
            tb = OxmlElement("w:tcBorders")
            tb.append(border("top", "single") if i == 0 else border("top", "nil"))
            tb.append(border("left", "nil"))
            tb.append(border("bottom", "single", 6) if i == heads - 1 or (i == len(rows) - 1 and closed)
                      else border("bottom", "nil"))
            tb.append(border("right", "nil"))
            tcPr.append(tb)
            reorder(tcPr, TCPR_ORDER)
    merge_spanning_rows(tbl, total)
    for i, row in enumerate(t.rows):
        for c in row.cells:
            for p in c.paragraphs:
                pf = p.paragraph_format
                pf.line_spacing = 1.0
                pf.space_before = Pt(1)
                pf.space_after = Pt(1)
                pf.keep_with_next = i < heads  # header rows stay with the first body row
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                lead = len(p.text) - len(p.text.lstrip(INDENT))
                if lead and p.runs:  # a sub-row: the no-break spaces become an indent
                    p.runs[0].text = p.runs[0].text.lstrip(INDENT)
                    pf.left_indent = Pt(size * lead / 2)
                for r in p.runs:
                    set_font(r, size)
                    if i < heads:
                        r.font.bold = True


def move_page_breaks(doc) -> None:
    """Each paragraph that holds only a page break (PAGEBREAK) is removed and the paragraph after
    it starts a new page instead (page break before). A break paragraph that falls at the top of
    a page would otherwise leave an empty page, and with line numbers a numbered empty line."""
    body = doc.element.body
    for p in list(body.iterchildren(qn("w:p"))):
        brs = list(p.iter(qn("w:br")))
        if not brs or any(b.get(qn("w:type")) != "page" for b in brs) or "".join(
                x.text or "" for x in p.iter(qn("w:t"))).strip():
            continue
        nxt = p.getnext()
        if nxt is None or nxt.tag != qn("w:p"):
            continue
        from docx.text.paragraph import Paragraph
        Paragraph(nxt, doc._body).paragraph_format.page_break_before = True
        body.remove(p)


def highlight(doc, pattern: re.Pattern) -> None:
    """Yellow highlight on the text matching `pattern` (the item the author completes)."""
    for p in doc.paragraphs:
        for run in list(p.runs):
            parts = pattern.split(run.text)
            if len(parts) == 1:
                continue
            anchor = run._r
            for part in parts:
                if not part:
                    continue
                r = copy.deepcopy(run._r)
                anchor.addnext(r)
                anchor = r
                nr = Run(r, p)
                nr.text = part
                if pattern.fullmatch(part):
                    nr.font.highlight_color = WD_COLOR_INDEX.YELLOW
            run._r.getparent().remove(run._r)


APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
           'extended-properties"><Company></Company><Manager></Manager></Properties>')


def scrub_app_xml(path: Path) -> None:
    """docProps/app.xml reduced to empty Company and Manager (no template, application,
    editing time or counts)."""
    tmp = path.with_suffix(".scrub")
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "docProps/app.xml":
                data = APP_XML.encode("utf-8")
            zo.writestr(item, data)
    tmp.replace(path)


def postprocess(path: Path, *, landscape: bool = False, line_numbers: bool = False,
                table_pt: float = 10, placeholder: bool = False) -> None:
    doc = Document(str(path))
    page_setup(doc, landscape=landscape, line_numbers=line_numbers)
    move_page_breaks(doc)
    split_blocks(doc)
    total = (16838 if landscape else 11906) - 2 * 1417
    for t in doc.tables:
        # a wide table on a portrait page (seven or more columns) one point smaller, so that it
        # keeps to one page; smaller still if a column's longest word would not fit
        wide = not landscape and len(t.columns) >= 7
        format_table(t, total, fit_size(t, total, table_pt - 1 if wide else table_pt))
    if placeholder:
        highlight(doc, re.compile("(" + re.escape(DOI_PLACEHOLDER) + ")"))
    cp = doc.core_properties
    for attr in ("author", "last_modified_by", "title", "comments", "keywords", "subject",
                 "category", "identifier", "content_status", "language", "version"):
        setattr(cp, attr, "")
    cp.revision = 1
    doc.save(str(path))
    scrub_app_xml(path)


# --------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------
def figures(ijtb: bool = False) -> list[str]:
    """TIFF print masters rendered from the vector PDFs (and, except for the IJTB set, the PDFs
    copied): <prefix>_figure<k>.tif/.pdf at TIFF_DPI, or <prefix>_Figure_<k>.tif at TIFF_DPI_IJTB."""
    import fitz  # PyMuPDF
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    lines = []
    dpi = TIFF_DPI_IJTB if ijtb else TIFF_DPI
    for i, prefix in enumerate(LAY.figures, 1):
        pdf = EX / f"figure{i}.pdf"
        if not ijtb:
            shutil.copyfile(pdf, OUT / f"{prefix}_figure{i}.pdf")
        page = fitz.open(str(pdf))[0]
        pix = page.get_pixmap(dpi=dpi, alpha=False, colorspace=fitz.csRGB)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        r, g, b = im.split()
        grey = r.tobytes() == g.tobytes() == b.tobytes()
        if grey:
            im = r
        tif = OUT / (f"{prefix}_Figure_{i}.tif" if ijtb else f"{prefix}_figure{i}.tif")
        im.save(tif, format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
        chk = Image.open(tif)
        w_in, h_in = page.rect.width / 72, page.rect.height / 72
        lines.append(f"{tif.name}: {chk.mode} {chk.size[0]}x{chk.size[1]} px, "
                     f"{chk.info.get('dpi')} dpi, {chk.info.get('compression')}, "
                     f"{w_in:.2f} x {h_in:.2f} in ({w_in * 2.54:.1f} x {h_in * 2.54:.1f} cm)")
    return lines


# --------------------------------------------------------------------------------------
# Supplementary data S1a and S1b
# --------------------------------------------------------------------------------------
DATA = [("supplementary_data_S1a_registered.csv", "09_supplementary_data_S1a_registered.csv", "S1a registered"),
        ("supplementary_data_S1b_corrected.csv", "10_supplementary_data_S1b_corrected.csv", "S1b corrected")]
XLSX = "11_supplementary_data_S1.xlsx"


def supplementary_data() -> list[str]:
    """Copy the CSV files written by exhibits/make_tables.py; with openpyxl (if installed) one
    workbook with a sheet for each, every cell as the CSV text."""
    import csv
    lines = []
    sheets = []
    for src, dst, sheet in DATA:
        shutil.copyfile(EX / src, OUT / dst)
        with open(OUT / dst, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        sheets.append((sheet, rows))
        lines.append(f"{dst}: {len(rows) - 1} pairs, {len(rows[0])} columns")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        (OUT / XLSX).unlink(missing_ok=True)
        return lines + [f"{XLSX}: not built (openpyxl not installed)"]
    wb = Workbook()
    wb.remove(wb.active)
    for sheet, rows in sheets:
        ws = wb.create_sheet(sheet)
        for r in rows:
            ws.append(r)
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.freeze_panes = "A2"
    for attr in ("creator", "lastModifiedBy", "title", "subject", "description", "keywords"):
        setattr(wb.properties, attr, None)
    wb.save(OUT / XLSX)
    return lines + [f"{XLSX}: sheets {', '.join(s for s, _ in sheets)}"]


# --------------------------------------------------------------------------------------
# Word counts (Microsoft Word, through PowerShell COM)
# --------------------------------------------------------------------------------------
def word_counts(docx: Path) -> dict:
    out = MS / "word_counts_word.json"
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(ROOT / "tools" / "word_count_word.ps1"), str(docx), str(out)], check=True)
    w = json.loads(out.read_text(encoding="utf-8-sig"))
    end = "Conclusions" if "Conclusions" in w.get("sections", {}) else "Discussion"
    w["counted_by"] = (f"Microsoft Word (ComputeStatistics) on {docx.name}: "
                       "abstract = Abstract heading to Keywords; main text = Introduction to "
                       f"{end}" + (" plus the text box (Box 1)" if "Box" in w.get("sections", {}) else "")
                       + ", headings excluded")
    w["source_md5"] = hashlib.md5(read("manuscript_src.md").encode("utf-8")).hexdigest()
    out.write_text(json.dumps(w, indent=1) + "\n", encoding="utf-8", newline="\n")
    return w


# --------------------------------------------------------------------------------------
# The IJTB set (profile "ijtb")
# --------------------------------------------------------------------------------------
IJTB_PREVIEW = "{n}_Figure_{k}_preview.png"


def fill_doi(md: str, doi: str | None) -> str:
    return md.replace(DOI_PLACEHOLDER, doi) if doi else md


def captions_md() -> str:
    """The title, then the figure legends, each under its PNG preview."""
    ms = read("manuscript_src.md")
    title = ms.splitlines()[0]
    legends = between(ms, "## Figure legends", None)
    head, *rest = re.split(r"(?m)^(?=\*\*Figure \d+\.\*\*)", legends)
    parts = [title, "\n\n", head.rstrip("\n"), "\n\n"]
    for k, leg in enumerate(rest, 1):
        parts += [f"![]({IJTB_PREVIEW.format(n=91 + k, k=k)}){{width=6.3in}}\n\n", leg.rstrip("\n"), "\n\n"]
    return "".join(parts)


def previews() -> list[str]:
    lines = []
    for k in range(1, len(LAY.figures) + 1):
        dst = OUT / IJTB_PREVIEW.format(n=91 + k, k=k)
        shutil.copyfile(EX / f"figure{k}.png", dst)
        lines.append(f"{dst.name}: copy of exhibits/figure{k}.png")
    return lines


def to_pdf(docx: Path, pdf: Path) -> None:
    """Export a .docx to PDF through Word (tools/docx_to_pdf.ps1)."""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(ROOT / "tools" / "docx_to_pdf.ps1"), str(docx), str(pdf)], check=True)


def ijtb_jobs(doi: str | None) -> list[tuple[str, str, dict]]:
    ph = dict(placeholder=not doi)
    return [
        ("01_Cover_Letter.docx", fill_doi(cover_letter_md(), doi), ph),
        ("02_Title_Page.docx", title_page_md(doi), ph),
        ("03_Manuscript.docx", fill_doi(manuscript_md(), doi), dict(line_numbers=True, **ph)),
        ("04_Highlights.docx", read("highlights.md"), {}),
        ("05_Figure_Captions.docx", captions_md(), {}),
        ("06_Declarations.docx", fill_doi(read("declarations.md"), doi), ph),
        ("07_Declaration_of_Interests.docx", read("declaration_of_interests.md"), {}),
        ("08_Copyright_Transfer.docx", read("copyright_transfer.md"), {}),
        ("09_Supplementary_Material.docx", supplement_md(read("supplement_text.md")), dict(landscape=True, table_pt=9)),
        ("10_RECORD_Checklist.docx", read("record_checklist.md"), {}),
        ("91_Manuscript_Blinded.docx", manuscript_md(blinded=True), dict(line_numbers=True)),
    ]


def build_ijtb(a) -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ref = tmp / "reference.docx"
        make_reference(ref)
        for ln in previews():
            print(ln)
        jobs = ijtb_jobs(a.doi)
        for name, md, kw in jobs:
            out = OUT / name
            run_pandoc(md, out, ref, tmp, resources=OUT)
            postprocess(out, **kw)
            print("built", name)
    for ln in figures(ijtb=True):
        print(ln)
    made = {n for n, _, _ in jobs} | {f"{p}_Figure_{i}.tif" for i, p in enumerate(LAY.figures, 1)}
    made |= {IJTB_PREVIEW.format(n=91 + k, k=k) for k in range(1, len(LAY.figures) + 1)}
    made |= {"08_Copyright_Transfer.pdf", "15_Graphical_Abstract.tif"}
    if not a.no_word:
        to_pdf(OUT / "08_Copyright_Transfer.docx", OUT / "08_Copyright_Transfer.pdf")
        print("built 08_Copyright_Transfer.pdf (Word)")
        w = word_counts(OUT / "03_Manuscript.docx")
        print(f"Word counts: abstract {w['abstract']}, main text {w['main_text']} (limits 250 and 3,000)")
    for f in sorted(OUT.iterdir()):
        if f.is_file() and f.name not in made:
            print(f"note: {f.name} is not part of this set (left from an earlier build?); remove it")
    print("built into", OUT)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doi", help="the Zenodo version DOI (10.5281/zenodo.NNNNNNN) for the title page")
    ap.add_argument("--no-word", action="store_true", help="skip Word's word counts")
    ap.add_argument("--manuscript-dir", default=DEFAULT_MS_DIR,
                    help="the manuscript folder (default manuscript/ext; v1.0.0: manuscript/v1_audit)")
    ap.add_argument("--out", help="the output folder (default <manuscript folder>/submission)")
    a = ap.parse_args(argv)
    if a.doi and not DOI_RE.match(a.doi):
        raise SystemExit(f"--doi must look like 10.5281/zenodo.NNNNNNN, not {a.doi!r}")
    d = Path(a.manuscript_dir)
    o = Path(a.out) if a.out else None
    configure(d if d.is_absolute() else ROOT / d, None if o is None else (o if o.is_absolute() else ROOT / o))
    if not MS.is_dir():
        raise SystemExit(f"{a.manuscript_dir} not present (it is private)")
    if frozen(OUT):
        raise SystemExit(f"{OUT} holds {', '.join(frozen(OUT))}: a submitted set is frozen; build into a new folder")
    OUT.mkdir(exist_ok=True)
    if a.doi:  # the DOI this set is filled with; check_docx_tie holds every .docx to it
        (MS / "release_doi.txt").write_text(a.doi + "\n", encoding="utf-8", newline="\n")
    if profile_for(MS) == "ijtb":
        return build_ijtb(a)
    print(f"profile {profile_for(MS)}: {len(LAY.figures)} figures, supplement {LAY.supplement}, "
          f"{'supplementary data files' if LAY.data else 'no data files'}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ref = tmp / "reference.docx"
        make_reference(ref)
        jobs = [
            ("01_title_page.docx", title_page_md(a.doi), dict(placeholder=not a.doi)),
            ("02_manuscript_anonymised.docx", manuscript_md(), dict(line_numbers=True)),
            (LAY.supplement, supplement_md(), dict(landscape=True, table_pt=9)),
            (LAY.cover, cover_letter_md(), {}),
            (LAY.record, read("record_checklist.md"), {}),
            (LAY.declaration, declaration_md(a.doi), {}),
        ]
        for name, md, kw in jobs:
            out = OUT / name
            run_pandoc(md, out, ref, tmp)
            postprocess(out, **kw)
            print("built", name)
    for ln in figures():
        print(ln)
    if LAY.data:
        for ln in supplementary_data():
            print(ln)
    made = {n for n, _, _ in jobs} | {f"{p}_figure{i}.{x}" for i, p in enumerate(LAY.figures, 1)
                                      for x in ("tif", "pdf")}
    made |= ({dst for _, dst, _ in DATA} | {XLSX}) if LAY.data else set()
    for f in sorted(OUT.iterdir()):
        if f.is_file() and f.name not in made:
            print(f"note: {f.name} is not part of this set (left from an earlier build?); remove it")
    if not a.no_word:
        w = word_counts(OUT / "02_manuscript_anonymised.docx")
        print(f"Word counts: abstract {w['abstract']}, main text {w['main_text']} "
              f"(limits 250 and 3,000)")
    print("built into", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
