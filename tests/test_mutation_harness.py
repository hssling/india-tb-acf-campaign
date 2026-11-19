# Adapted from hssling/india-state-tb-score (MIT), tests/test_mutation_harness.py, commit 05bcaa7; modified: tests of the named-mutation runner, the .docx editing helpers and the number-token sweeps, on synthetic files
"""Fixture tests of verification/mutate_manuscript.py. They use synthetic files, not the
(git-ignored) manuscript."""
import zipfile

import pytest

docx = pytest.importorskip("docx")

from verification import mutate_manuscript as mm  # noqa: E402


def make_docx(path):
    d = docx.Document()
    p = d.add_paragraph("Yield was 17.3 in 2023.")
    p.add_run("19").font.superscript = True
    d.add_paragraph("2. Alpha. 3. Beta.")
    d.save(str(path))


def xml(path, part=mm.DOC):
    with zipfile.ZipFile(path) as z:
        return z.read(part).decode("utf-8")


def test_bump():
    assert mm.bump("0.99") == "0.90" and mm.bump("10,000") == "10,001" and mm.bump("7") == "8"


def test_md_token_spans_skip_references():
    text = "## Results\n\nA 12 and 3.5.\n\n## References\n\n1. Ref 2020.\n\n## Figure legends\n\nn = 35\n"
    toks = [text[a:b] for a, b in mm.md_token_spans(text)]
    assert toks == ["12", "3.5", "35"]


def test_edit_docx_and_not_applied(tmp_path):
    f = tmp_path / "a.docx"
    make_docx(f)
    mm.edit_docx(f, "17.3", "17.4")
    assert "17.4" in xml(f) and "17.3" not in xml(f)
    with pytest.raises(mm.NotApplied):
        mm.edit_docx(f, "no such text", "x")


def test_set_creator(tmp_path):
    f = tmp_path / "a.docx"
    make_docx(f)
    mm.set_creator(f, "Some Name")
    assert "<dc:creator>Some Name</dc:creator>" in xml(f, mm.CORE)
    assert docx.Document(str(f)).core_properties.author == "Some Name"


def test_swap_superscript_changes_only_the_citation(tmp_path):
    f = tmp_path / "a.docx"
    make_docx(f)
    mm.swap_superscript(f, "19", "24")
    d = docx.Document(str(f))
    runs = d.paragraphs[0].runs
    assert runs[-1].text == "24" and runs[-1].font.superscript
    assert runs[0].text == "Yield was 17.3 in 2023."
    with pytest.raises(mm.NotApplied):
        mm.swap_superscript(f, "17.3", "17.4")  # not a superscript run


def test_docx_token_spans(tmp_path):
    f = tmp_path / "a.docx"
    make_docx(f)
    x = xml(f)
    assert [x[a:b] for a, b in mm.docx_token_spans(x)] == ["17.3", "2023", "19", "2", "3"]


def test_run_named_counts_caught_escaped_and_not_applied(tmp_path):
    src = tmp_path / "manuscript"
    src.mkdir()
    (src / "a.md").write_text("value 12\n", encoding="utf-8")

    def changed(d):
        return [] if (d / "a.md").read_text(encoding="utf-8") == "value 12\n" else ["changed"]

    muts = [
        ("1", "number", "12 -> 13", lambda d: mm.edit_text(d / "a.md", "12", "13")),
        ("2", "none", "a no-op the check cannot see", lambda d: None),
        ("3", "anchor", "missing anchor", lambda d: mm.edit_text(d / "a.md", "99", "98")),
    ]
    rows = mm.run_named(src, muts, {"changed": changed})
    by = {r["id"]: r for r in rows}
    assert by["1"]["applied"] and by["1"]["by"] == ["changed"]
    assert by["2"]["applied"] and by["2"]["by"] == []
    assert not by["3"]["applied"]
    assert (src / "a.md").read_text(encoding="utf-8") == "value 12\n"  # the source is untouched


def test_run_named_refuses_a_failing_baseline(tmp_path):
    src = tmp_path / "manuscript"
    src.mkdir()
    with pytest.raises(SystemExit):
        mm.run_named(src, [], {"always": lambda d: ["fails"]})


def test_sweep_md_with_a_blind_check():
    text = "## Results\n\nA 12 and 3.5.\n"
    assert mm.sweep_md(text, lambda t: t != text)[:2] == (2, 2)
    caught, total, escaped = mm.sweep_md(text, lambda t: False)
    assert caught == 0 and len(escaped) == total == 2


def test_named_mutations_cover_the_required_kinds():
    kinds = " ".join(k for _, k, _, _ in mm.MUTATIONS)
    for k in ("number, docx only", "number, markdown only", "author name", "reference number",
              "table cell", "gamma sign", "internal identifier"):
        assert k in kinds, k


def test_skips_without_manuscript(tmp_path, capsys):
    assert mm.main([], root=tmp_path) == 0
    assert capsys.readouterr().out.startswith("SKIPPED")


def test_anchors_are_read_from_the_private_phrases_file(tmp_path):
    import json
    d = tmp_path / "manuscript"
    d.mkdir()
    (d / "section_phrases.json").write_text(json.dumps(
        {"sections": {"Abstract": ["x"]}, "mutation_anchors": {"2a": "row by 6,174 people", "6a": "was −0.5"}}),
        encoding="utf-8")
    assert mm.anchor(d, "2a") == "row by 6,174 people"
    assert mm.bumped(mm.anchor(d, "2a")) == "row by 6,175 people"
    assert mm.flipped(mm.anchor(d, "6a")) == "was 0.5" and mm.flipped("was 0.5") == "was −0.5"
    with pytest.raises(mm.NotApplied):
        mm.anchor(d, "9z")
    with pytest.raises(mm.NotApplied):
        mm.anchor(tmp_path, "2a")  # no phrases file


def test_mutation_harness_holds_no_manuscript_text():
    from pathlib import Path
    src = (Path(mm.__file__)).read_text(encoding="utf-8")
    for s in ("In conclusion", "79 of 84", "national row by", "February 2026 date"):
        assert s not in src, s
