# Adapted from hssling/india-state-tb-score (MIT), manuscript/build_docx.py, commit 05bcaa7; modified: Public Health (Elsevier) submission set; sources are the private manuscript_src.md, first_page_src.md, cover_letter.md, record_checklist.md and exhibits/tables.md; tables with top, header and bottom rules only; superscript letter footnotes; line numbers; TIFF from the vector PDF
"""Build the Public Health submission set into manuscript/submission/ (git-ignored, private).

Run as: python -I tools/build_submission.py [--doi 10.5281/zenodo.NNNNNNN] [--no-word]

Needs pandoc on PATH, python-docx, Pillow and PyMuPDF (fitz); Microsoft Word (through
PowerShell COM) for the word counts unless --no-word. Sources (manuscript/, git-ignored):
manuscript_src.md (blinded), first_page_src.md, cover_letter.md, record_checklist.md and
exhibits/ (tables.md, figure1.pdf, figure2.pdf). Nothing is written outside manuscript/.

Output (docs/journal_rules.md; Elsevier generic style): A4, 2.5 cm margins, Times New Roman
12 pt, double spacing, page numbers at the foot; continuous line numbers in the anonymised
manuscript. Tables: no vertical rules, only the top, header and bottom rules; footnote marks
as superscript lowercase letters; 10 pt single-spaced cells (9 pt in the landscape supplement).

  01_title_page.docx              title page (not blinded); --doi fills the Zenodo DOI
  02_manuscript_anonymised.docx   blinded text, References, Tables 1-3, figure legends
  03_figure1.tif / 03_figure1.pdf Figure 1: TIFF (LZW, TIFF_DPI) and the vector PDF
  04_figure2.tif / 04_figure2.pdf Figure 2
  05_supplementary_material.docx  Tables S1 to S4 and the column dictionary of the data (blinded)
  09_supplementary_data_S1a_registered.csv, 10_supplementary_data_S1b_corrected.csv
                                  Supplementary data S1a and S1b: every Q2 entry pair (copied from
                                  manuscript/exhibits/, written there by exhibits/make_tables.py)
  11_supplementary_data_S1.xlsx   both, one sheet each (only if openpyxl is installed)
  06_cover_letter.docx
  07_RECORD_checklist.docx
  08_declaration_of_interests.docx

Word's own counts of the abstract and the main text of 02 go to
manuscript/word_counts_word.json (tools/word_count_word.ps1); the title page must quote them
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

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.run import Run

ROOT = Path(__file__).resolve().parents[1]
MS = ROOT / "manuscript"
EX = MS / "exhibits"
OUT = MS / "submission"
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


def manuscript_md() -> str:
    ms = read("manuscript_src.md")
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


def supplement_md() -> str:
    title = read("manuscript_src.md").splitlines()[0]
    if not title.startswith("# "):
        raise SystemExit("manuscript_src.md must start with its '# ' title")
    parts = ["# Supplementary material\n\n", title[2:].strip(), "\n"]
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
    page's competing-interests statement, word for word."""
    fp = title_page_md(doi)
    keep = []
    for key in ("**Title:**", "**Author:**", "**Competing interests:**"):
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


def run_pandoc(md: str, out: Path, ref: Path, tmp: Path) -> None:
    src = tmp / (out.stem + ".md")
    src.write_text(md, encoding="utf-8")
    subprocess.run(["pandoc", str(src), "-f", PANDOC_FROM, "--reference-doc", str(ref),
                    "-o", str(out)], check=True)


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


def col_widths(t, total: int, size: float) -> list[int]:
    """Column widths (twips). Each column is at least as wide as its longest word, so that a
    number such as 205,331,541 never breaks; the rest of the width goes to the columns whose
    typical (90th centile) cell would otherwise wrap."""
    char = size * 20 * 0.5          # twips per character: half an em
    pad = 2 * 108 + 20              # the cell margins and a little slack
    mins, wants = [], []
    for j in range(len(t.columns)):
        texts = [row.cells[j].text.replace(INDENT, " ") for row in t.rows if j < len(row.cells)]
        longest_word = max((len(w) for s in texts for w in s.split()), default=3)
        lengths = sorted(len(s.strip()) for s in texts[1:]) or [3]
        typical = lengths[int(0.9 * (len(lengths) - 1))]  # 90th centile of the body cells
        mins.append((longest_word + 1) * char + pad)
        wants.append(max(min(typical, 150) * char + pad, mins[-1]))
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


def format_table(t, total: int, size: float) -> None:
    """Top, header and bottom rules only (no vertical rules); fixed widths over the text
    block; the header row repeated on each page; single-spaced cells at `size` pt."""
    tbl = t._tbl
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
        if i == 0:
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
            tb.append(border("bottom", "single", 6) if i == 0 or i == len(rows) - 1
                      else border("bottom", "nil"))
            tb.append(border("right", "nil"))
            tcPr.append(tb)
            reorder(tcPr, TCPR_ORDER)
    for i, row in enumerate(t.rows):
        for c in row.cells:
            for p in c.paragraphs:
                pf = p.paragraph_format
                pf.line_spacing = 1.0
                pf.space_before = Pt(1)
                pf.space_after = Pt(1)
                pf.keep_with_next = False
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                lead = len(p.text) - len(p.text.lstrip(INDENT))
                if lead and p.runs:  # a sub-row: the no-break spaces become an indent
                    p.runs[0].text = p.runs[0].text.lstrip(INDENT)
                    pf.left_indent = Pt(size * lead / 2)
                for r in p.runs:
                    set_font(r, size)
                    if i == 0:
                        r.font.bold = True


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
    total = (16838 if landscape else 11906) - 2 * 1417
    for t in doc.tables:
        format_table(t, total, table_pt)
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
def figures() -> list[str]:
    import fitz  # PyMuPDF
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    lines = []
    for i, prefix in ((1, "03"), (2, "04")):
        pdf = EX / f"figure{i}.pdf"
        shutil.copyfile(pdf, OUT / f"{prefix}_figure{i}.pdf")
        page = fitz.open(str(pdf))[0]
        pix = page.get_pixmap(dpi=TIFF_DPI, alpha=False, colorspace=fitz.csRGB)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        r, g, b = im.split()
        grey = r.tobytes() == g.tobytes() == b.tobytes()
        if grey:
            im = r
        tif = OUT / f"{prefix}_figure{i}.tif"
        im.save(tif, format="TIFF", compression="tiff_lzw", dpi=(TIFF_DPI, TIFF_DPI))
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
    w["counted_by"] = ("Microsoft Word (ComputeStatistics) on 02_manuscript_anonymised.docx: "
                       "abstract = Abstract heading to Keywords; main text = Introduction to "
                       "Discussion, headings excluded")
    w["source_md5"] = hashlib.md5(read("manuscript_src.md").encode("utf-8")).hexdigest()
    out.write_text(json.dumps(w, indent=1) + "\n", encoding="utf-8", newline="\n")
    return w


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doi", help="the Zenodo version DOI (10.5281/zenodo.NNNNNNN) for the title page")
    ap.add_argument("--no-word", action="store_true", help="skip Word's word counts")
    a = ap.parse_args(argv)
    if a.doi and not DOI_RE.match(a.doi):
        raise SystemExit(f"--doi must look like 10.5281/zenodo.NNNNNNN, not {a.doi!r}")
    if not MS.is_dir():
        raise SystemExit("manuscript/ not present (it is private)")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ref = tmp / "reference.docx"
        make_reference(ref)
        jobs = [
            ("01_title_page.docx", title_page_md(a.doi), dict(placeholder=not a.doi)),
            ("02_manuscript_anonymised.docx", manuscript_md(), dict(line_numbers=True)),
            ("05_supplementary_material.docx", supplement_md(), dict(landscape=True, table_pt=9)),
            ("06_cover_letter.docx", cover_letter_md(), {}),
            ("07_RECORD_checklist.docx", read("record_checklist.md"), {}),
            ("08_declaration_of_interests.docx", declaration_md(a.doi), {}),
        ]
        for name, md, kw in jobs:
            out = OUT / name
            run_pandoc(md, out, ref, tmp)
            postprocess(out, **kw)
            print("built", name)
    for ln in figures():
        print(ln)
    for ln in supplementary_data():
        print(ln)
    if not a.no_word:
        w = word_counts(OUT / "02_manuscript_anonymised.docx")
        print(f"Word counts: abstract {w['abstract']}, main text {w['main_text']} "
              f"(limits 250 and 3,000)")
    print("built into", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
