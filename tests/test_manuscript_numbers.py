"""Tests of verification/check_manuscript_numbers.py on synthetic manuscripts (fixtures).

The manuscript and its section phrases (manuscript/section_phrases.json) are private and never
read here. Each fixture manuscript is built from the synthetic FIXTURE_PHRASES below, filled
from the committed outputs, so the tests run on a fresh clone without manuscript/.
"""
from __future__ import annotations

import io
import json
import re
import shutil
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from verification import check_all
from verification import check_manuscript_numbers as cmn

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [  # the files catalogue() and claims() read
    "outputs", "data/figures_inventory.csv", "data/search_log.csv",
    "data/extracted/exposure_checks_reconstructed.csv", "data/extracted/guard_result.csv",
    "data/extracted/exposure_share_reconstructed.csv", "data/extracted/named_list_check.csv",
    "docs/analysis_plan.md",
    "docs/registration_event.json", "ENVIRONMENT.md", "exhibits/make_figures.py",
]


# Synthetic section phrases (not the manuscript's): each {label} is a catalogue value.
FIXTURE_PHRASES: dict[str, list[str]] = {
    "Title": ["Fixture title for the number check"],
    "Abstract": [
        "Fixture abstract: {inv.n_figures} figures in {inv.n_documents} documents; {q1.totals_pass} of "
        "{q1.totals_n} totals summed.",
        "Main slope {q4.D.primary.g1} (model {q4.D.primary.model}; bootstrap {q4.D.primary.boot}) over "
        "{q4.D.primary.n} units.",
        "Placebo slope {q4.D.placebo.g1} ({q4.D.placebo.model}).",
    ],
    "Introduction": ["Fixture campaign start {date.campaign_start}."],
    "Methods": ["Fixture methods: {q4.R.primary.n} registered units."],
    "Results": [
        "Fixture inventory (Table 1).",
        "Fixture pairs (Table 2): {q2.d347} against {q2.d455} districts; pairs were unexplained.",
        "Fixture yield {q3.2023.yield} ({q3.2023.yield_ci}) in 2023 (Table 3).",
        "Fixture guard medians {guard.m2023} for 2023 and {guard.m2024} for 2024; {guard.n} units each.",
        "Fixture named-list pairs: in all {q2.q3467_pairs} pre-specified pairs.",
        "Fixture main slope {q4.D.primary.g1} ({q4.D.primary.model}) (Figure 2A).",
        "Fixture ratio exp(γ1) {q4.D.primary.eg1}; per 10 percentage points exp(0.1γ1) {q4.D.primary.e01}.",
        "Fixture intercept γ0 {q4.D.primary.g0}.",
        "Fixture placebo {q4.D.placebo.g1} (Figure 2B).",
        "Fixture unweighted S1 slope {q4.D.S1.g1}.",
    ],
    "Discussion": ["Fixture discussion: {q4.D.primary.n} units at most."],
    cmn.AI_HEADING: ["(fixture model {ai.model}, used through Claude Code)"],
    "Figure legends": ["Fixture legend start {date.campaign_start}; n = {q4.D.primary.n}."],
}


def fixture_text() -> str:
    """A manuscript made only of the fixture phrases, plus exhibit and reference scaffolding."""
    cat = cmn.catalogue_cached(ROOT)
    parts = []
    for name, phrases in FIXTURE_PHRASES.items():
        body = " ".join(cmn.fill(p, cat)[0] for p in phrases)
        if name == "Title":
            parts.append(f"# {body}\n")
            continue
        if name == "Introduction":
            body = "Active case finding.^1^ " + body
        if name == "Results":
            body = body.replace("pairs were unexplained.", "pairs were unexplained. (Figure 1).", 1)
        if name == "Figure legends":
            body = "**Figure 1.** Claims. **Figure 2.** Slopes. " + body
        if name == "Data availability" or name == "Methods":
            body += " [repository link removed for blinded review]"
        parts.append(f"## {name}\n\n{body}\n")
        if name.startswith("Declaration"):
            parts.append("## References\n\n1. A reference. 2020.\n")
    return "\n".join(parts)


@pytest.fixture(scope="module")
def text() -> str:
    return fixture_text()


@pytest.fixture(scope="module")
def gold(text) -> dict:
    return cmn.golden(text, ROOT, FIXTURE_PHRASES)["sections"]


def probs(t: str, g: dict | None) -> list[str]:
    return cmn.problems(ROOT, t, g, required=FIXTURE_PHRASES)


# ------------------------------------------------------------------ formats

def test_formats():
    assert cmn.num(-0.000367, 3) == "−0.000"
    assert cmn.num3(-0.000367) == "−0.0004" and cmn.num3(0.0422) == "0.042" and cmn.num3(0) == "0.000"
    assert cmn.signed(0.031045, 3) == "+0.031" and cmn.signed(-0.023668, 3) == "−0.024"
    assert cmn.num(0.0422, 3) == "0.042"
    assert cmn.count(2401) == "2,401"
    assert cmn.rng("−0.025", "0.100") == "−0.025 to 0.100"
    assert cmn.day("2025-02-22") == "22 February 2025"
    assert cmn.whole_or("0.000000", 3) == "0" and cmn.whole_or("0.315152", 3) == "0.315"
    with pytest.raises(ValueError):
        cmn.count(1.5)


def test_wilson_matches_q3_outputs():
    lo, hi = cmn.wilson(73772, 223879862)
    assert cmn.num(1e5 * lo, 1) == "32.7" and cmn.num(1e5 * hi, 1) == "33.2"


# ------------------------------------------------------------------ catalogue and claims

def test_catalogue_sources_name_existing_files():
    for label, (value, source) in cmn.catalogue_cached(ROOT).items():
        assert value, label
        if source.startswith("fixed"):
            continue
        path = source.split(":")[0].split(" §")[0].strip()
        assert (ROOT / path).exists(), (label, source)


def test_catalogue_key_values():
    cat = cmn.catalogue_cached(ROOT)
    assert cat["q4.D.primary.g1"][0] == "0.042"
    assert cat["q4.D.primary.model"][0] == "0.003 to 0.081"
    assert cat["q4.D.primary.boot"][0] == "−0.025 to 0.100"
    assert cat["q4.D.placebo.model"][0] == "−0.202 to −0.036"
    assert cat["q2.cor.pairs"][0] == "974" and cat["q2.reg.pairs"][0] == "1,765"
    assert cat["q1.itr2023.screened"][0] == "6,174"
    assert cat["guard.m2023"][0] == "1.040" and cat["guard.m2024"][0] == "1.023"


def test_claims_hold_on_committed_outputs():
    assert cmn.claims(ROOT) == []


# ------------------------------------------------------------------ the fixture passes

def test_clean_fixture_has_no_problem(text, gold):
    assert probs(text, gold) == []


def test_golden_maps_every_token_to_a_label(gold):
    for entries in gold.values():
        for e in entries:
            assert e["label"] != "UNACCOUNTED" and e["source"]


def test_missing_golden_is_a_problem(text):
    assert any("number_skeleton.json missing" in p for p in probs(text, None))


# ------------------------------------------------------------------ mutations are caught

@pytest.mark.parametrize("old,new,expect", [
    ("0.042", "0.043", "MISSING in Abstract"),          # changed value
    ("−0.119", "0.119", "MISSING in Abstract"),         # sign flip
    ("1.040 for 2023", "1.041 for 2023", "UNACCOUNTED"),  # changed guard median
    ("in all 72 pre-specified", "in all 73 pre-specified", "MISSING in Results"),
    ("7 December 2024", "8 December 2024", "not a catalogue date"),
])
def test_changed_numbers_are_caught(text, gold, old, new, expect):
    assert old in text
    found = probs(text.replace(old, new, 1), gold)
    assert any(expect in p for p in found), found


def test_extra_number_is_unaccounted(text, gold):
    t = text.replace("## Discussion\n\n", "## Discussion\n\nAbout 12 States differed. ", 1)
    assert any("UNACCOUNTED number in Discussion: '12'" in p for p in probs(t, gold))


def test_value_moved_to_another_section_is_caught(text, gold):
    cat = cmn.catalogue_cached(ROOT)
    ph = cmn.fill(FIXTURE_PHRASES["Results"][-1], cat)[0]
    t = text.replace(ph, "", 1).replace("## Ethical approval\n\n", "## Ethical approval\n\n" + ph + " ", 1)
    found = probs(t, gold)
    assert any(p.startswith("MISSING in Results") for p in found)
    assert any("SKELETON" in p for p in found)


def test_reordered_numbers_fail_the_golden_skeleton(text, gold):
    cat = cmn.catalogue_cached(ROOT)
    a = cmn.fill("Fixture intercept γ0 {q4.D.primary.g0}.", cat)[0]
    b = cmn.fill(next(x for x in FIXTURE_PHRASES["Results"] if x.startswith("Fixture ratio")), cat)[0]
    t = text.replace(a, "@@A@@").replace(b, a).replace("@@A@@", b)
    found = probs(t, gold)
    assert found and all(p.startswith("SKELETON Results") for p in found)


def test_stale_golden_token_is_caught(text, gold):
    g = json.loads(json.dumps(gold))
    e = next(x for x in g["Results"] if x["label"] == "q4.D.primary.g1")
    e["token"] = "0.043"
    found = probs(text, g)
    assert any("no longer in q4.D.primary.g1" in p for p in found)


def test_blinding_is_checked(text, gold):
    name = cmn.author_markers(ROOT)[0]
    found = probs(text + f"\nWritten by {name}.\n", gold)
    assert any(p.startswith("BLINDING") for p in found)
    found = probs(text.replace("[repository link removed for blinded review]", "the repository"), gold)
    assert any("placeholder" in p for p in found)


@pytest.mark.parametrize("insert,expect", [
    ("as ruling A32 decided", "WORDING: a ruling number"),
    ("see GRD-01", "decision or check identifier"),
    ("from RS Q1216", "shorthand source identifier"),
    ("after the fix round", "drafting-process language"),
    ("under D2", "internal correction code"),
    ("standardized reporting", "SPELLING"),
])
def test_internal_identifiers_and_spelling(text, gold, insert, expect):
    t = text.replace("## Discussion\n\n", f"## Discussion\n\nNote, {insert}. ", 1)
    assert any(expect in p for p in probs(t, gold))


def test_reference_and_exhibit_order(text, gold):
    t = text.replace("Active case finding.^1^", "Active case finding.^2^", 1)
    found = probs(t, gold)
    assert any("outside 1..1" in p for p in found) and any("never cited" in p for p in found)
    t = text.replace("pairs were unexplained. (Figure 1).", "pairs were unexplained.", 1)
    assert any(p.startswith("EXHIBITS: Figures cited") for p in probs(t, gold))
    t = text.replace("## Discussion\n\n", "## Discussion\n\nSee Table S9. ", 1)
    assert any("S9 does not exist" in p for p in probs(t, gold))


def test_supplementary_tables_in_order_of_first_citation(text, gold):
    ok = "See Table S1, Supplementary data S1a and S1b, Table S2, Table S3 and Table S4. "
    t = text.replace("## Discussion\n\n", "## Discussion\n\n" + ok, 1)
    assert not any("supplementary" in p for p in probs(t, gold))
    t = text.replace("## Discussion\n\n", "## Discussion\n\nSee Table S1, Supplementary data S1a and S1b, "
                     "Table S3, Table S2 and Table S4. ", 1)
    assert any("first cited out of order" in p for p in probs(t, gold))
    t = text.replace("## Discussion\n\n", "## Discussion\n\nSee Table S1, Supplementary data S1a and S1b "
                     "and Table S2. ", 1)
    assert any("never cited" in p for p in probs(t, gold))
    t = text.replace("## Discussion\n\n", "## Discussion\n\n" + ok.replace("S1a and S1b", "S1a"), 1)
    assert any("supplementary data never cited: ['S1b']" in p for p in probs(t, gold))
    t = text.replace("## Discussion\n\n", "## Discussion\n\n" + ok.replace("S1a and S1b", "S1a and S1c"), 1)
    assert any("supplementary data S1c does not exist" in p for p in probs(t, gold))
    t = text.replace("## Discussion\n\n", "## Discussion\n\nSee Tables S1a and S1b. ", 1)
    assert any("supplementary S1a does not exist" in p for p in probs(t, gold))


# ------------------------------------------------------------------ main(): skip and end to end

def run_main(root: Path, *argv: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cmn.main(root, list(argv))
    return code, buf.getvalue()


def test_skips_without_manuscript_dir(tmp_path):
    code, out = run_main(tmp_path)
    assert code == 0 and out.startswith("SKIPPED") and "kept private, not in this repository" in out


def test_skips_when_manuscript_holds_only_generated_exhibits(tmp_path):
    (tmp_path / "manuscript" / "exhibits").mkdir(parents=True)
    (tmp_path / "manuscript" / "exhibits" / "tables.md").write_text("# Tables\n", encoding="utf-8")
    code, out = run_main(tmp_path)
    assert code == 0 and out.startswith("SKIPPED") and "manuscript_src.md" in out
    assert "kept private, not in this repository" in out and "not written yet" not in out


def test_fails_when_the_phrases_file_is_missing(tmp_path):
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / cmn.MS_NAME).write_text("# T\n", encoding="utf-8")
    code, out = run_main(tmp_path)
    assert code == 1 and out.startswith("FAIL") and cmn.PHRASES in out


def test_fails_when_the_manuscript_is_missing_but_phrases_exist(tmp_path):
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / cmn.PHRASES).write_text(json.dumps({"sections": FIXTURE_PHRASES}),
                                                      encoding="utf-8")
    code, out = run_main(tmp_path)
    assert code == 1 and out.startswith("FAIL") and cmn.MS_NAME in out


@pytest.mark.parametrize("body", ["not json", "{}", '{"sections": {}}', '{"sections": {"Abstract": "x"}}'])
def test_fails_on_a_malformed_phrases_file(tmp_path, body):
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / cmn.MS_NAME).write_text("# T\n", encoding="utf-8")
    (tmp_path / "manuscript" / cmn.PHRASES).write_text(body, encoding="utf-8")
    code, out = run_main(tmp_path)
    assert code == 1 and out.startswith("FAIL")


def test_no_phrases_is_a_problem(text, gold):
    assert any(p.startswith("PHRASES") for p in cmn.problems(ROOT, text, gold, required={}))


def test_the_checker_holds_no_manuscript_phrases():
    src = (ROOT / "verification" / "check_manuscript_numbers.py").read_text(encoding="utf-8")
    assert not hasattr(cmn, "SECTION_REQUIRED") and "SECTION_REQUIRED" not in src


def test_end_to_end_regenerate_then_check(tmp_path, text):
    for rel in INPUTS:
        src, dst = ROOT / rel, tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    (tmp_path / "manuscript").mkdir()
    ms = tmp_path / "manuscript" / cmn.MS_NAME
    ms.write_text(text, encoding="utf-8", newline="\n")
    (tmp_path / "manuscript" / cmn.PHRASES).write_text(json.dumps({"sections": FIXTURE_PHRASES}),
                                                      encoding="utf-8")
    code, out = run_main(tmp_path)
    assert code == 1 and "number_skeleton.json missing" in out
    assert run_main(tmp_path, "--regenerate")[0] == 0
    sk = json.loads((tmp_path / "manuscript" / cmn.SKELETON).read_text(encoding="utf-8"))
    assert set(sk) == {"about", "sections"}
    code, out = run_main(tmp_path)
    assert code == 0 and out.strip().endswith("0 problem(s)"), out
    ms.write_text(text.replace("0.042", "0.043", 1), encoding="utf-8", newline="\n")
    code, out = run_main(tmp_path)
    assert code == 1 and "MISSING in Abstract" in out
    assert not re.search(r"\r", (tmp_path / "manuscript" / cmn.SKELETON).read_bytes().decode("utf-8"))


def test_regenerate_refuses_a_failing_text(text):
    with pytest.raises(SystemExit):
        cmn.golden(text.replace("0.042", "0.043", 1), ROOT, FIXTURE_PHRASES)


def test_check_all_runs_the_manuscript_check():
    steps = dict(check_all.STEPS)
    assert steps["check_manuscript_numbers"][-1] == "verification/check_manuscript_numbers.py"


# ------------------------------------------------------------------ the other manuscript files

def title_page(text: str) -> str:
    decl = cmn.sections(text)[cmn.AI_HEADING]
    return (f"# Title page\n\n**Data:** archived on Zenodo ({cmn.DOI_PLACEHOLDER}).\n\n"
            f"**{cmn.AI_HEADING}:** {decl}\n")


@pytest.fixture(scope="module")
def others(text) -> dict:
    return {"exhibits/tables.md": "# Tables (generated from outputs/ by exhibits/make_tables.py)\n\n"
                                  "| Source | n |\n|---|---|\n| India TB Report 2024, Annexure 6 | 35,438 |\n",
            "first_page_src.md": title_page(text),
            "cover_letter.md": "Dear Editors,\n\nRelated work at the Bulletin of the World Health Organization.\n"}


def test_clean_other_files_pass(text, gold, others):
    assert cmn.problems(ROOT, text, gold, others, required=FIXTURE_PHRASES) == []


def test_make_tables_formatter_matches_num3():
    import sys
    sys.path.insert(0, str(ROOT / "exhibits"))
    import make_tables as mt
    for x in ("-0.000367", "0.0422", "-0.119333", "0.110027"):
        assert mt.FORMATTERS["dec3"](x) == cmn.num3(x)


@pytest.mark.parametrize("name,insert,expect", [
    ("exhibits/tables.md", "| checks TOT-012 | 1 |\n", "WORDING in exhibits/tables.md"),
    ("exhibits/tables.md", "| plan §10.5 | 1 |\n", "section sign"),
    ("exhibits/tables.md", "| PGPH2025 | 1 |\n", "shorthand source identifier"),
    ("cover_letter.md", "[Date of submission]\n", "PROCESS in cover_letter.md"),
    ("cover_letter.md", "We standardized it.\n", "SPELLING in cover_letter.md"),
    ("cover_letter.md", "[author to confirm]\n", "drafting text"),
    ("first_page_src.md", "Counted by manuscript/count_words.py.\n", "a file path"),
])
def test_other_files_are_scanned(text, gold, others, name, insert, expect):
    o = dict(others)
    o[name] = o[name] + insert
    assert any(expect in p for p in cmn.problems(ROOT, text, gold, o, required=FIXTURE_PHRASES))


def test_blinding_of_the_tables(text, gold, others):
    o = dict(others)
    o["exhibits/tables.md"] += f"Prepared by {cmn.author_markers(ROOT)[0]}.\n"
    found = cmn.problems(ROOT, text, gold, o, required=FIXTURE_PHRASES)
    assert any(p.startswith("BLINDING in exhibits/tables.md") for p in found)


def test_title_page_needs_one_doi_placeholder(text, gold, others):
    o = dict(others)
    o["first_page_src.md"] = o["first_page_src.md"].replace(cmn.DOI_PLACEHOLDER, "DOI to be added")
    assert any("DOI placeholder" in p for p in cmn.problems(ROOT, text, gold, o, required=FIXTURE_PHRASES))


def test_ai_declaration_must_match_the_title_page(text, gold, others):
    o = dict(others)
    o["first_page_src.md"] = o["first_page_src.md"].replace("Claude Code", "Claude Code, and reviewed all code")
    assert any(p.startswith("DECLARATION") for p in cmn.problems(ROOT, text, gold, o, required=FIXTURE_PHRASES))
