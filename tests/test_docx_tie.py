# Adapted from hssling/india-state-tb-score (MIT), tests/test_docx_tie.py, commit 05bcaa7; modified: fixtures for the unit-level tie (paragraphs, list items, table rows, superscripts), blinding in document properties, identifiers, word counts and a complete fixture manuscript folder for each submission set (v1, ext)
"""Fixture tests of verification/check_docx_tie.py. The .docx files are built with python-docx
from synthetic text; the private manuscript is never read."""
import hashlib
import json

import pytest

docx = pytest.importorskip("docx")

from verification import check_docx_tie as tie  # noqa: E402
from verification import check_manuscript_numbers as cmn  # noqa: E402

ROOT = tie.ROOT


def add_text(doc, text):
    """A paragraph from a normalised unit: ^x^ becomes a superscript run."""
    p = doc.add_paragraph()
    for i, part in enumerate(text.split("^")):
        if part:
            p.add_run(part).font.superscript = bool(i % 2)
    return p


def docx_from_units(units, path):
    """A .docx whose paragraphs and table rows are the given units, in order."""
    d = docx.Document()
    rows = []

    def flush():
        if rows:
            t = d.add_table(rows=len(rows), cols=len(rows[0]))
            for i, r in enumerate(rows):
                for j, c in enumerate(r):
                    t.cell(i, j).text = ""
                    para = t.cell(i, j).paragraphs[0]
                    for k, part in enumerate(c.split("^")):
                        if part:
                            para.add_run(part).font.superscript = bool(k % 2)
            rows.clear()

    for u in units:
        if " | " in u:
            rows.append(u.split(" | "))
        else:
            flush()
            add_text(d, u)
    flush()
    d.save(str(path))


def test_norm():
    assert tie.norm("**Table 1.** Inventory ᵃ") == "Table 1. Inventory ^a^"
    assert tie.norm("1\\. Author  *et al*.") == "1. Author et al."
    assert tie.norm("x^2^^,3^ y") == "x^2,3^ y"
    assert tie.norm("DOI: 10.5281/zenodo.XXXXXXX") == tie.norm("DOI: 10.5281/zenodo.24323627")
    assert tie.norm("a  b") == "a b"


def test_md_units():
    md = ("# Title\n\nLine one\nline two.^1^\n\n- **Item:** a\n- b\n\n1. Ref one.\n2. Ref two.\n\n"
          "| A | B |\n|---|---|\n| 1 | 73,772 \\| 73772 |\n|   sub | ᵃ |\n")
    assert tie.md_units(md) == ["Title", "Line one line two.^1^", "Item: a", "b", "1. Ref one.",
                                "2. Ref two.", "A | B", "1 | 73,772 | 73772", "sub | ^a^"]


def test_md_slice():
    md = "# T\n\n## A\n\nx\n\n## B\n\ny\n"
    assert tie.md_units(tie.md_slice(md, "## A", "## B")) == ["A", "x"]
    assert tie.md_units(tie.md_slice(md, None, "## A")) == ["T"]


def test_docx_units_and_compare(tmp_path):
    units = ["Results", "Yield was 17.3 in 2023.^19^", "Year | Yield", "2023 | 17.3 (17.1 to 17.4)"]
    f = tmp_path / "a.docx"
    docx_from_units(units, f)
    assert tie.docx_units(f) == units
    assert tie.compare("a", tie.docx_units(f), units) == []
    for i, bad in ((1, "Yield was 17.4 in 2023.^19^"), (1, "Yield was 17.3 in 2023.^24^"),
                   (1, "Yield was 17.3 in 2023.19"), (3, "2023 | 17.3 (17.1 to 17.5)")):
        other = list(units)
        other[i] = bad
        assert tie.compare("a", tie.docx_units(f), other), bad


def test_blinding_reads_document_properties(tmp_path):
    f = tmp_path / "a.docx"
    d = docx.Document()
    d.add_paragraph("Blinded text.")
    d.core_properties.author = "A. N. Author"
    d.save(str(f))
    hay = tie.docx_all_text(f)
    assert tie.blinding_problems("a.docx", hay, ["A. N. Author"])
    assert not tie.blinding_problems("a.docx", hay, ["Somebody Else"])


def test_identifiers_before_references_only():
    assert tie.identifier_problems("05_x.docx", ["Note", "see Task 7"])
    assert tie.identifier_problems("02_x.docx", ["Methods", "RS Q1216 here", "References"])
    assert not tie.identifier_problems("02_x.docx", ["Methods", "fine", "References", "Q1216"])


def test_skips_without_manuscript(tmp_path, capsys):
    assert tie.main(root=tmp_path, argv=[]) == 0
    assert capsys.readouterr().out.startswith("SKIPPED")
    (tmp_path / "manuscript" / "ext").mkdir(parents=True)
    assert tie.main(root=tmp_path, argv=[]) == 0
    assert capsys.readouterr().out.startswith("SKIPPED")


# ------------------------------------------------------------------ a complete fixture folder

SOURCES = {
    "manuscript_src.md": ("# A study title\n\n## Abstract\n\n**Results:** 35 units.^1^\n\n## Results\n\n"
                          "Yield was 17.3 (Table 1).^1^\n\n## References\n\n1. A reference. 2020.\n\n"
                          "## Figure legends\n\n**Figure 1.** A figure.\n"),
    "exhibits/tables.md": ("# Tables (generated)\n\n## Table 1. Yield\n\n| Year | Yieldᵃ |\n|---|---|\n"
                           "| 2023 | 17.3 |\n\nᵃ A note.\n\n## Table S1. More\n\n| A | B |\n|---|---|\n"
                           "| 1 | 2 |\n"),
    "first_page_src.md": ("# Title page\n\n**Title:** A study title\n\n**Author:** An Author\n\n"
                          "**Word count (Microsoft Word):** main text (Introduction to Discussion) 1,234 "
                          "words; abstract 210 words.\n\n**Declarations of interest:** none.\n\n"
                          "**Data:** DOI: 10.5281/zenodo.XXXXXXX\n"),
    "cover_letter.md": "# Cover letter\n\nDear Editors,\n\nThe Editors\nPublic Health\n",
    "record_checklist.md": "# RECORD checklist\n\n| Item | Where |\n|---|---|\n| 1 | Title |\n",
}


TABLE_CSVS = {"table1.csv": "Year,Yieldᵃ\n2023,17.3\n", "tables1.csv": "A,B\n1,2\n"}


def make_ms(tmp_path, profile):
    """A complete fixture folder of the given profile, its submission set built from the units."""
    ms = tmp_path / "manuscript"
    (ms / "exhibits").mkdir(parents=True)
    (ms / "submission").mkdir()
    for name, text in SOURCES.items():
        (ms / name).write_text(text, encoding="utf-8")
    (ms / cmn.PHRASES).write_text(json.dumps({"profile": profile, "sections": {"Abstract": ["x"]}}),
                                  encoding="utf-8")
    for name, text in TABLE_CSVS.items():
        (ms / "exhibits" / name).write_text(text, encoding="utf-8", newline="\n")
    lay = tie.LAYOUTS[profile]
    for name in lay.spec:
        want, _ = tie.expected(ms, name)
        docx_from_units(want, ms / "submission" / name)
    for name in lay.figures:
        (ms / "submission" / name).write_bytes(b"figure")
    if lay.data:
        mt = tie.make_tables()
        for name, output, _ in lay.data:
            (ms / "submission" / name).write_bytes(mt.supplementary_data_bytes(output))
    md5 = hashlib.md5(SOURCES["manuscript_src.md"].encode("utf-8")).hexdigest()
    (ms / "word_counts_word.json").write_text(json.dumps(
        {"abstract": 210, "main_text": 1234, "source_md5": md5}), encoding="utf-8")
    return ms


@pytest.fixture(params=["v1", "ext"])
def ms_dir(tmp_path, request):
    return make_ms(tmp_path, request.param)


@pytest.fixture()
def v1_dir(tmp_path):
    return make_ms(tmp_path, "v1")


@pytest.fixture()
def ext_dir(tmp_path):
    return make_ms(tmp_path, "ext")


def test_fixture_folder_ties(ms_dir):
    assert tie.problems(ms_dir, ROOT) == []


def test_layouts():
    v1, ext = tie.LAYOUTS["v1"], tie.LAYOUTS["ext"]
    assert v1.files() == ["01_title_page.docx", "02_manuscript_anonymised.docx", "03_figure1.pdf",
                          "03_figure1.tif", "04_figure2.pdf", "04_figure2.tif",
                          "05_supplementary_material.docx", "06_cover_letter.docx",
                          "07_RECORD_checklist.docx", "08_declaration_of_interests.docx",
                          "09_supplementary_data_S1a_registered.csv",
                          "10_supplementary_data_S1b_corrected.csv", "11_supplementary_data_S1.xlsx"]
    assert ext.files() == ["01_title_page.docx", "02_manuscript_anonymised.docx", "03_figure1.pdf",
                           "03_figure1.tif", "04_figure2.pdf", "04_figure2.tif", "05_figure3.pdf",
                           "05_figure3.tif", "06_figure4.pdf", "06_figure4.tif",
                           "07_supplementary_material.docx", "08_cover_letter.docx",
                           "09_RECORD_checklist.docx", "10_declaration_of_interests.docx"]
    assert ext.blinded == ("02_manuscript_anonymised.docx", "07_supplementary_material.docx")
    assert not ext.data and ext.xlsx is None and ext.complete_tables and not v1.complete_tables


def test_layout_follows_the_profile(tmp_path):
    assert tie.layout(tmp_path / "v1_audit") is tie.LAYOUTS["v1"]  # no phrases file: by the name
    assert tie.layout(tmp_path / "ext") is tie.LAYOUTS["ext"]
    d = tmp_path / "other"
    d.mkdir()
    (d / cmn.PHRASES).write_text(json.dumps({"profile": "v1", "sections": {"A": ["x"]}}), encoding="utf-8")
    assert tie.layout(d) is tie.LAYOUTS["v1"]


def test_builder_layouts_agree_with_the_tie():
    bs = pytest.importorskip("tools.build_submission")
    for prof, lay in tie.LAYOUTS.items():
        b = bs.LAYOUTS[prof]
        assert tie.figure_files(list(b.figures)) == lay.figures
        assert {b.supplement, b.cover, b.record, b.declaration} | {
            "01_title_page.docx", "02_manuscript_anonymised.docx"} == set(lay.spec)
        assert b.supplement == lay.supplement and b.data == bool(lay.data)
        if b.data:
            assert [dst for _, dst, _ in bs.DATA] == [n for n, _, _ in lay.data] and bs.XLSX == lay.xlsx


def test_extra_file_is_a_problem(ms_dir):
    (ms_dir / "submission" / "05_supplementary_material_old.docx").write_bytes(b"x")
    (ms_dir / "submission" / "_render").mkdir()  # a folder (the render output) is not a file of the set
    assert tie.problems(ms_dir, ROOT) == [
        f"EXTRA: 05_supplementary_material_old.docx is not part of the {cmn.profile_for(ms_dir)} submission set"]



def test_optional_graphical_abstract_is_allowed_but_other_extras_are_not(ms_dir):
    sub = ms_dir / "submission"
    for name in sorted(tie.OPTIONAL_FILES):
        (sub / name).write_bytes(b"x")
    (sub / "11_graphical_abstract.png").write_bytes(b"x")
    assert tie.problems(ms_dir, ROOT) == [
        f"EXTRA: 11_graphical_abstract.png is not part of the {cmn.profile_for(ms_dir)} submission set"]

def test_ext_tables_must_be_complete_as_their_csv(ext_dir):
    ex = ext_dir / "exhibits"
    (ex / "tables1.csv").write_text("A,B\n1,2\n3,4\n", encoding="utf-8")  # a row the table lacks
    found = tie.problems(ext_dir, ROOT)
    assert any(p.startswith("TABLES: tables1.csv (3 rows) differs from Table S1") for p in found)
    (ex / "tables1.csv").unlink()
    assert "TABLES: Table S1 has no tables1.csv in exhibits/" in tie.problems(ext_dir, ROOT)


def test_complete_tables_normalise_like_the_tie(tmp_path):
    ex = tmp_path / "exhibits"
    ex.mkdir()
    (ex / "tables.md").write_text("## Table S2. T\n\n| **A** | B |\n|---|---|\n| **Block** |  |\n"
                                  "|   sub ᵇ | 1,234 |\n\nNote.\n", encoding="utf-8")
    (ex / "tables2.csv").write_text("A,B\nBlock,\n  sub ᵇ,\"1,234\"\n", encoding="utf-8")
    assert tie.complete_table_problems(tmp_path) == []
    assert tie.table_csv_name("", "1") == "table1.csv" and tie.table_csv_name("S", "8") == "tables8.csv"


def test_doi_placeholder_is_a_note_not_a_problem(ms_dir):
    tp = ms_dir / "submission" / "01_title_page.docx"
    want, _ = tie.expected(ms_dir, tp.name)
    docx_from_units([w.replace("<DOI>", "XXXXXXX") for w in want], tp)
    assert tie.problems(ms_dir, ROOT) == [] and tie.notes(ms_dir)
    docx_from_units([w.replace("<DOI>", "24323627") for w in want], tp)
    assert tie.problems(ms_dir, ROOT) == [] and not tie.notes(ms_dir)


def test_spec_parts(ms_dir):
    lay = tie.layout(ms_dir)
    want, builder = tie.expected(ms_dir, lay.supplement)
    assert want[:3] == ["Supplementary material", "A study title", "Table S1. More"]
    assert builder == {"Supplementary material"}
    want, _ = tie.expected(ms_dir, "02_manuscript_anonymised.docx")
    assert want.index("Table 1. Yield") < want.index("Figure legends")
    assert "Year | Yield^a^" in want and "^a^ A note." in want
    cover, decl = [n for n in lay.spec if "cover_letter" in n or "declaration" in n]
    want, _ = tie.expected(ms_dir, cover)
    assert want[0] == "Dear Editors,"  # the '# Cover letter' heading is not part of the letter
    want, _ = tie.expected(ms_dir, decl)
    assert want == ["Declaration of interests", "Title: A study title", "Author: An Author",
                    "Declarations of interest: none."]


def test_fixture_folder_catches_changes(ms_dir):
    name = cmn.author_markers(ROOT)[0]
    sub = ms_dir / "submission"
    want, _ = tie.expected(ms_dir, "02_manuscript_anonymised.docx")
    docx_from_units([w.replace("17.3 (Table", f"17.3 {name} (Table") for w in want],
                    sub / "02_manuscript_anonymised.docx")
    found = tie.problems(ms_dir, ROOT)
    assert any(p.startswith("BLINDING in 02") for p in found)
    assert any(p.startswith("TIE 02") for p in found)


def test_markdown_change_and_word_counts(ms_dir):
    src = ms_dir / "manuscript_src.md"
    src.write_text(SOURCES["manuscript_src.md"].replace("17.3 (Table", "17.4 (Table"), encoding="utf-8")
    found = tie.problems(ms_dir, ROOT)
    assert any(p.startswith("TIE 02") for p in found)
    assert any("stale" in p for p in found)
    (ms_dir / "word_counts_word.json").unlink()
    assert any("missing" in p for p in tie.problems(ms_dir, ROOT))


def test_title_page_may_say_what_the_main_text_counts(ext_dir):
    """The extension paper counts its text box in the main text and says so on the title page."""
    tp = SOURCES["first_page_src.md"].replace(
        "(Introduction to Discussion)", "(Introduction to Discussion, with the text box, Box 1, counted in the main text)")
    (ext_dir / "first_page_src.md").write_text(tp, encoding="utf-8")
    want, _ = tie.expected(ext_dir, "01_title_page.docx")
    docx_from_units(want, ext_dir / "submission" / "01_title_page.docx")
    assert tie.problems(ext_dir, ROOT) == []
    assert tie.word_count_problems(ext_dir, ["main text (Introduction to Discussion, with Box 1) 1,234 words; "
                                             "abstract 2100 words"]) == [
        "WORDS: the title page does not quote Word's count 'abstract 210 words'"]


def test_title_page_must_quote_word_counts(ms_dir):
    w = json.loads((ms_dir / "word_counts_word.json").read_text(encoding="utf-8"))
    w["main_text"] = 1235
    (ms_dir / "word_counts_word.json").write_text(json.dumps(w), encoding="utf-8")
    assert any("does not quote" in p for p in tie.problems(ms_dir, ROOT))
    w["main_text"] = 3001
    (ms_dir / "word_counts_word.json").write_text(json.dumps(w), encoding="utf-8")
    assert any("over the limit" in p for p in tie.problems(ms_dir, ROOT))


def test_missing_file_is_a_problem(ms_dir):
    (ms_dir / "submission" / "03_figure1.tif").unlink()
    assert "MISSING: 03_figure1.tif" in tie.problems(ms_dir, ROOT)


def test_ext_needs_all_four_figures(ext_dir):
    (ext_dir / "submission" / "06_figure4.pdf").unlink()
    assert "MISSING: 06_figure4.pdf" in tie.problems(ext_dir, ROOT)


def test_ext_blinding_covers_the_supplement(ext_dir):
    name = cmn.author_markers(ROOT)[0]
    sup = ext_dir / "submission" / "07_supplementary_material.docx"
    want, _ = tie.expected(ext_dir, sup.name)
    docx_from_units(want + [f"Prepared by {name}"], sup)
    found = tie.problems(ext_dir, ROOT)
    assert any(p.startswith("BLINDING in 07") for p in found) and any(p.startswith("TIE 07") for p in found)


def test_data_files_tie_to_outputs(v1_dir):
    ms_dir = v1_dir
    sub = ms_dir / "submission"
    name = tie.LAYOUTS["v1"].data[1][0]
    lines = (sub / name).read_text(encoding="utf-8").split(chr(10))
    (sub / name).write_text(chr(10).join(lines[:-2] + lines[-1:]), encoding="utf-8", newline="")
    found = tie.problems(ms_dir, ROOT)
    assert any(p.startswith(f"DATA {name}") and "rows" in p for p in found)
    assert any("SHA-256" in p for p in found)


def test_data_cell_edit_is_caught(v1_dir):
    ms_dir = v1_dir
    sub = ms_dir / "submission"
    name = tie.LAYOUTS["v1"].data[0][0]
    text = (sub / name).read_text(encoding="utf-8")
    (sub / name).write_text(text.replace(",347,exact,", ",348,exact,", 1), encoding="utf-8", newline="")
    found = tie.problems(ms_dir, ROOT)
    assert any("verbatim column" in p for p in found) and any("SHA-256" in p for p in found)


def test_xlsx_must_match_the_csv(v1_dir):
    ms_dir = v1_dir
    lay = tie.LAYOUTS["v1"]
    openpyxl = pytest.importorskip("openpyxl")
    import csv
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, _, sheet in lay.data:
        ws = wb.create_sheet(sheet)
        with open(ms_dir / "submission" / name, newline="", encoding="utf-8") as f:
            for r in csv.reader(f):
                ws.append(r)
    xl = ms_dir / "submission" / lay.xlsx
    wb.save(xl)
    assert tie.problems(ms_dir, ROOT) == []
    wb[lay.data[0][2]]["K2"] = "999"
    wb.save(xl)
    assert any(p.startswith(f"DATA {lay.xlsx}") for p in tie.problems(ms_dir, ROOT))


def test_journal_italics(tmp_path):
    ms = ("## References\n\n1. Author A. A title. Lancet. 2010;376:1.\n2. A report. Ministry; 2024.\n\n"
          "## Figure legends\n")
    f = tmp_path / "a.docx"
    d = docx.Document()
    d.add_paragraph("References")
    p = d.add_paragraph("1. Author A. A title. ")
    p.add_run("Lancet").italic = True
    p.add_run(". 2010;376:1.")
    d.add_paragraph("2. A report. Ministry; 2024.")
    d.save(str(f))
    assert tie.italics_problems(f, ms) == []
    d.paragraphs[1].runs[1].italic = False
    d.save(str(f))
    assert tie.italics_problems(f, ms)


def test_spanning_row_ties_to_one_merged_cell():
    """A spanning row is '| **Label** | | |' in Markdown and one merged cell in Word."""
    assert tie.row_unit(["Label", "", ""]) == "Label"
    assert tie.row_unit(["A", "", "B", ""]) == "A |  | B"
    assert tie.md_units("| **Class 1 and 2 entry pairs (corrected set)** |  |  |\n") == [
        "Class 1 and 2 entry pairs (corrected set)"]
