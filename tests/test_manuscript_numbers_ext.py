"""Tests of verification/check_manuscript_numbers.py for the extension paper (profile "ext"), on
synthetic manuscripts (fixtures).

The extension manuscript and its section phrases (manuscript/ext/, git-ignored) are private and
never read here. Each fixture manuscript is built from the synthetic FIXTURE_PHRASES below,
filled from the committed outputs (outputs/ext/ and, for the box, outputs/), so the tests run on
a fresh clone. The v1.0.0 audit profile is tested in tests/test_manuscript_numbers.py.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from verification import check_manuscript_numbers as cmn

ROOT = Path(__file__).resolve().parents[1]
P = "ext"
INPUTS = [  # the files catalogue_ext(), claims_ext() and the blinding check read
    "outputs", "data/ext/panel.csv",
    "data/extracted/exposure_checks_reconstructed.csv", "data/extracted/exposure_share_reconstructed.csv",
    "docs/analysis_plan.md", "docs/extension_plan.md",
    "docs/registration_event.json", "docs/registration_event_ext.json", "ENVIRONMENT.md",
]

# Synthetic section phrases (not the manuscript's): each {label} is a catalogue value.
FIXTURE_PHRASES: dict[str, list[str]] = {
    "Title": ["Fixture title for the extension number check"],
    "Abstract": [
        "Fixture pooled yield {pool.2018.yield} ({pool.2018.ci}) and {pool.2023.yield} ({pool.2023.ci}).",
        "Fixture elasticity ε {eps.main.est} ({eps.main.boot}); {hl.epsilon.agree} specifications below 1.",
        "Fixture ρ {rho.main.est} ({rho.main.boot}) and θ {theta.main.est} ({theta.main.boot}).",
    ],
    "Introduction": ["Fixture campaign start {date.campaign_start} in {exp.districts} districts."],
    "Methods": [
        "Fixture registrations {date.registration} at {reg.time} and {date.registration_ext} at {reg_ext.time}.",
        "Fixture grids ({hl.grids}); nulls ({hl.nulls}); at least {plan.agree} agreeing.",
        "Fixture software {sw.python} with {sw.numpy}.",
    ],
    "Results": [
        "Fixture States: {by.names_above}.",
        "Fixture total notifications {theta.total.est} ({theta.total.boot}).",
        "Fixture scenario {sc.delta} ({sc.ci}); effective number of States about {rho.kish}.",
        "Fixture positivity {dec.positivity.est} ({dec.positivity.ci}).",
    ],
    "Discussion": ["Fixture discussion: {eps.main.units} States."],
    "Box 1. How to read official ACF figures": [
        "Fixture box: {box.cor.c4} of {box.cor.pairs} ({box.reg.c4} of {box.reg.pairs}).",
    ],
    cmn.AI_HEADING: ["(fixture model {ai.model}, used through Claude Code)"],
    "Figure legends": ["Fixture legend: the null ({hl.nulls})."],
}

SCAFFOLD = {  # exhibit citations and legends, in order of first citation
    "Introduction": "Active case finding.^1^ ",
    "Results": "See Figure 1A, Table S1, Figure 2, Table S2, Table 1, Table S3, Figure 3, Table S4, "
               "Table S5, Figure 4, Table S6 and Table S7. ",
    "Box 1. How to read official ACF figures": "See Table S8. ",
    "Figure legends": "**Figure 1.** A. **Figure 2.** B. **Figure 3.** C. **Figure 4.** D. ",
}


def fixture_text() -> str:
    cat = cmn.catalogue_cached(ROOT, P)
    parts = []
    for name, phrases in FIXTURE_PHRASES.items():
        body = " ".join(cmn.fill(p, cat)[0] for p in phrases)
        if name == "Title":
            parts.append(f"# {body}\n")
            continue
        body = SCAFFOLD.get(name, "") + body
        if name == "Methods":
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
    return cmn.golden(text, ROOT, FIXTURE_PHRASES, P)["sections"]


def probs(t: str, g: dict | None, others: dict | None = None) -> list[str]:
    return cmn.problems(ROOT, t, g, others, required=FIXTURE_PHRASES, profile=P)


# ------------------------------------------------------------------ profiles

def test_profiles_and_the_default():
    assert cmn.DEFAULT_PROFILE == "ext" and set(cmn.PROFILES) == {"v1", "ext"}
    ext = cmn.PROFILES["ext"]
    assert ext.tables == [1] and ext.figures == [1, 2, 3, 4]
    assert ext.supplement == [f"S{k}" for k in range(1, 9)] and ext.supp_data == []
    v1 = cmn.PROFILES["v1"]
    assert v1.tables == [1, 2, 3] and v1.figures == [1, 2] and v1.supp_data == ["S1a", "S1b"]


def test_profile_for_a_folder(tmp_path):
    assert cmn.profile_for(tmp_path / "manuscript" / "v1_audit") == "v1"
    assert cmn.profile_for(tmp_path / "manuscript" / "ext") == "ext"
    d = tmp_path / "other"
    d.mkdir()
    (d / cmn.PHRASES).write_text(json.dumps({"profile": "v1", "sections": {"A": ["x"]}}), encoding="utf-8")
    assert cmn.profile_for(d) == "v1"
    (d / cmn.PHRASES).write_text("not json", encoding="utf-8")
    assert cmn.profile_for(d) == "ext"


# ------------------------------------------------------------------ catalogue and claims

def test_catalogue_sources_name_existing_files():
    for label, (value, source) in cmn.catalogue_cached(ROOT, P).items():
        assert value, label
        if source.startswith("fixed"):
            continue
        path = source.split(":")[0].split(" §")[0].split(" (")[0].strip()
        assert (ROOT / path).exists(), (label, source)


def test_catalogue_matches_the_printed_exhibits():
    cat = {k: v[0] for k, v in cmn.catalogue_cached(ROOT, P).items()}
    assert cat["eps.main.est"] == "0.24" and cat["eps.main.boot"] == "0.02 to 0.51"
    assert cat["eps.main.model"] == "−0.08 to 0.56"
    assert cat["rho.main.est"] == "−0.82" and cat["rho.main.boot"] == "−0.93 to 0.02"
    assert cat["theta.main.boot"] == "−2.20 to 1.80"
    assert cat["theta.total.boot"] == "−3.64 to 1.26"  # as printed in Table 1 (not 1.27)
    assert cat["theta.log.est"] == "0.004" and cat["theta.log.boot"] == "−0.016 to 0.032"
    assert cat["sc.delta"] == "1,347" and cat["sc.ci"] == "125 to 3,165"
    assert cat["rho.kish"] == "3" and cat["rho.top2_share"] == "77%" and cat["sc.mh_moved"] == "77%"
    assert (cat["by.robust_above"], cat["by.robust_overlaps"], cat["by.robust_below"]) == ("8", "4", "9")
    assert cat["hl.grids"] == "24 entries for ε and ρ, 16 for θ"
    assert cat["box.cor.c4"] == "103" and cat["box.cor.pairs"] == "722"
    assert cat["box.reg.c4"] == "348" and cat["box.reg.pairs"] == "1,405"
    assert cat["box.cascade_reg_pass"] == "805" and cat["box.cascade_reg_n"] == "810"
    assert cat["box.cascade_pass"] == "776" and cat["sc.n_states"] == "29"
    assert cat["date.registration_ext"] == "19 November 2026" and cat["reg_ext.time"] == "16:21 UTC"


def test_catalogue_values_appear_in_the_tables_where_printed():
    tables = ROOT / cmn.DEFAULT_MS_DIR / "exhibits" / "tables.md"
    if not tables.exists():
        pytest.skip("the extension tables are not built in this copy")
    md = tables.read_text(encoding="utf-8")
    cat = {k: v[0] for k, v in cmn.catalogue_cached(ROOT, P).items()}
    for k in ("eps.main.est", "eps.main.boot", "rho.unw.boot", "theta.total.boot", "sc.ci",
              "pool.2021-2023.pi", "dec.dln.ci"):
        assert cat[k] in md, k


def test_claims_hold_on_committed_outputs():
    assert cmn.claims_ext(ROOT) == []


def copy_inputs(dst: Path) -> None:
    for rel in INPUTS:
        src, to = ROOT / rel, dst / rel
        to.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, to)


def test_a_changed_label_breaks_a_claim(tmp_path):
    copy_inputs(tmp_path)
    p = tmp_path / "outputs" / "ext" / "headline.csv"
    rows = list(csv.DictReader(p.open(encoding="utf-8", newline="")))
    rows[0]["label"] = "not established"  # epsilon
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    assert any("ε is supported" in x for x in cmn.claims_ext(tmp_path))


# ------------------------------------------------------------------ the fixture passes

def test_clean_fixture_has_no_problem(text, gold):
    assert probs(text, gold) == []


def test_golden_maps_every_token(gold):
    assert all(e["label"] != "UNACCOUNTED" and e["source"] for v in gold.values() for e in v)


# ------------------------------------------------------------------ mutations are caught

@pytest.mark.parametrize("old,new,expect", [
    ("0.02 to 0.51", "0.03 to 0.51", "MISSING in Abstract"),        # changed interval
    ("−0.82", "0.82", "MISSING in Abstract"),                       # sign flip
    ("1,347", "1,348", "MISSING in Results"),                       # scenario
    ("1.26", "1.27", "MISSING in Results"),                         # θ total upper bound
    ("103 of 722", "104 of 722", "MISSING in Box 1"),               # the box
    ("7 December 2024", "8 December 2024", "not a catalogue date"),
])
def test_changed_numbers_are_caught(text, gold, old, new, expect):
    assert old in text
    assert any(expect in p for p in probs(text.replace(old, new, 1), gold))


def test_extra_number_is_unaccounted(text, gold):
    t = text.replace("## Discussion\n\n", "## Discussion\n\nAbout 12 States differed. ", 1)
    assert any("UNACCOUNTED number in Discussion: '12'" in p for p in probs(t, gold))


def test_fixed_patterns_of_the_extension():
    body = ("ε < 1 means less; θ = 1 and θ = 0; intervals exclude 1 and can exceed 1, a share bounded "
            "by 0 and 1; the 100-day campaign, phase 1, per 100,000 people screened, each 1% increase, "
            "95% CI, Figure 3B, Table S8, Box 1, 2021–2023.^4–7^")
    entries, problems = cmn.assign("X", body, {}, [], cmn.FIXED_EXT)
    assert problems == [] and all(e["label"].startswith("fixed:") for e in entries)
    entries, problems = cmn.assign("X", "a share of 0.79", {}, [], cmn.FIXED_EXT)
    assert any("UNACCOUNTED" in p for p in problems)


@pytest.mark.parametrize("old,new,expect", [
    ("See Figure 1A, Table S1, Figure 2,", "See Figure 2, Table S1, Figure 1A,", "first citations of Figures out of order"),
    ("Table S4, Table S5", "Table S5, Table S4", "supplementary tables first cited out of order"),
    ("Table S6 and Table S7", "Table S6 and Table S9", "S9 does not exist"),
    ("**Figure 4.** D. ", "", "no legend for Figure 4"),
    (", Figure 4, Table S6", ", Table S6", "Figures cited"),
    (", Table 1, ", ", Table 2, ", "Tables cited"),
])
def test_exhibits_of_the_extension(text, gold, old, new, expect):
    assert old in text
    assert any(expect in p for p in probs(text.replace(old, new, 1), gold))


def test_v1_exhibit_rules_do_not_apply(text, gold):
    # Figures 3 and 4 and Tables S5-S8 exist only in the extension profile
    assert not any(p.startswith("EXHIBITS") for p in probs(text, gold))
    found = cmn.exhibit_problems(text, "v1")
    assert any("S5 does not exist" in p for p in found)


@pytest.mark.parametrize("insert,expect", [
    ("under D2", "internal correction code"),
    ("as ruling A32 decided", "a ruling number"),
    ("see plan §10", "section sign"),
    ("modeling the yield", "SPELLING"),
])
def test_internal_identifiers_and_spelling(text, gold, insert, expect):
    t = text.replace("## Discussion\n\n", f"## Discussion\n\nNote, {insert}. ", 1)
    assert any(expect in p for p in probs(t, gold))


def test_blinding(text, gold):
    found = probs(text + f"\nWritten by {cmn.author_markers(ROOT)[0]}.\n", gold)
    assert any(p.startswith("BLINDING") for p in found)


def test_other_files_and_the_ai_declaration(text, gold):
    decl = cmn.sections(text)[cmn.AI_HEADING]
    others = {"exhibits/tables.md": "# Tables\n\n| Item | n |\n|---|---|\n| States | 34 |\n",
              "first_page_src.md": f"# Title page\n\n**Data:** Zenodo ({cmn.DOI_PLACEHOLDER}).\n\n"
                                   f"**{cmn.AI_HEADING}:** {decl}\n",
              "cover_letter.md": "Dear Editors,\n\nRelated manuscripts: IJMR_4457_2026.\n"}
    assert probs(text, gold, others) == []
    o = dict(others)
    o["first_page_src.md"] = o["first_page_src.md"].replace("Claude Code", "Claude Code and more")
    assert any(p.startswith("DECLARATION") for p in probs(text, gold, o))
    o = dict(others)
    o["cover_letter.md"] += "See outputs/ext/d3.csv.\n"
    assert any("a file path" in p for p in probs(text, gold, o))


# ------------------------------------------------------------------ main(): end to end

def run_main(root: Path, *argv: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cmn.main(root, list(argv))
    return code, buf.getvalue()


def test_end_to_end_regenerate_then_check(tmp_path, text):
    copy_inputs(tmp_path)
    ms_dir = tmp_path / cmn.DEFAULT_MS_DIR
    ms_dir.mkdir(parents=True)
    ms = ms_dir / cmn.MS_NAME
    ms.write_text(text, encoding="utf-8", newline="\n")
    (ms_dir / cmn.PHRASES).write_text(json.dumps({"sections": FIXTURE_PHRASES}, ensure_ascii=False),
                                      encoding="utf-8")
    code, out = run_main(tmp_path)
    assert code == 1 and "number_skeleton.json missing" in out
    assert run_main(tmp_path, "--regenerate")[0] == 0
    code, out = run_main(tmp_path)
    assert code == 0 and out.strip().endswith("0 problem(s)") and out.startswith("[ext]"), out
    ms.write_text(text.replace("−0.82", "−0.83", 1), encoding="utf-8", newline="\n")
    code, out = run_main(tmp_path)
    assert code == 1 and "MISSING in Abstract" in out
    assert b"\r" not in (ms_dir / cmn.SKELETON).read_bytes()
