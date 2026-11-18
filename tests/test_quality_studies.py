"""Quality-study extraction (analysis plan §5, §7.5): printed-total checks, provenance."""
import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QS = ROOT / "data/extracted/quality_studies.csv"
INV = ROOT / "data/figures_inventory.csv"
STUDIES = ROOT / "data_raw/studies"

from src.extract import quality_studies as q  # noqa: E402


def _cells(study, table):
    """{(row_group, row_label): {column_label: printed_cell}}; a footnote letter glued
    to 'Not classifiable' is dropped from the key (the label is printed with footnote c
    in Table 2 and b in Table 3)."""
    out = {}
    for r in q.read_transcribed():
        if r["study"] == study and r["table_id"] == table:
            lab = re.sub(r"^(Not classifiable)[a-z]$", r"\1", r["row_label"])
            out.setdefault((r["row_group"], lab), {})[r["column_label"]] = \
                r["printed_cell"]
    return out


def _n(cell):
    return int(q.parse_cell(cell)[0].replace(" ", ""))


def _p(cell):
    return float(q.parse_cell(cell)[1])


def test_parse_cell():
    assert q.parse_cell("581 633 (100.0)") == ("581 633", "100.0")
    assert q.parse_cell("117 a (1.6)") == ("117", "1.6")
    assert q.parse_cell("3311 (5.2)b") == ("3311", "5.2")
    assert q.parse_cell("48 (<0.1)") == ("48", "<0.1")
    assert q.parse_cell("902 (18.1) a") == ("902", "18.1")
    assert q.parse_cell("4971") == ("4971", "")
    with pytest.raises(ValueError):
        q.parse_cell("")


def test_gha_table2_rows_agree_with_their_own_printed_indicators():
    t = _cells("GHA2023", "Table 2")
    assert len(t) == 26
    for key, c in t.items():
        s, te, d = (int(c[k]) for k in ("Number screened", "Number tested",
                                        "Number diagnosed"))
        assert f"{100 * te / s:.1f}" == c["% Tested"], key
        assert f"{100 * d / te:.1f}" == c["% Diagnosed"], key
        assert (round(s / d) if d else 0) == int(c["NNS"]), key


def test_gha_table1_india_row_printed():
    t = _cells("GHA2023", "Table 1")[("", "INDIA")]
    assert sorted(t.values()) == ["1.0", "2824", "3.7", "9.3"]


def _pg2():
    return _cells("PGPH2025", "Table 2")


def test_pgph_table2_total_matches_text_counts():
    tot = _pg2()[("Total", "")]
    assert [_n(tot[k]) for k in ("Screened n (%)col", "Presumptive TB n (%)row",
                                 "Tested n (%)row", "Diagnoseda n (%)row")] == \
        [581633, 11357, 7527, 117]
    assert tot["NNS"] == "4971"


# Strata whose printed rows do not sum to the printed Total, as printed (cells
# re-read twice online): (group, column) -> printed Total minus sum of rows. Recorded,
# never corrected.
PRINTED_GAPS = {("Elderly", "Presumptive TB n (%)row"): 9,
                ("Type of high-risk population", "Screened n (%)col"): 2560}


@pytest.mark.parametrize("group", ["Gender", "Elderly", "Residence",
                                   "Type of high-risk population",
                                   "Facility-based high-risk group"])
def test_pgph_strata_sum_to_printed_total(group):
    t = _pg2()
    tot = t[("Total", "")]
    for col in ("Screened n (%)col", "Presumptive TB n (%)row", "Tested n (%)row",
                "Diagnoseda n (%)row"):
        s = sum(_n(c[col]) for (g, _), c in t.items() if g == group)
        assert _n(tot[col]) - s == PRINTED_GAPS.get((group, col), 0), (group, col)


def test_pgph_table2_row_percentages_match_counts():
    for key, c in _pg2().items():
        s = _n(c["Screened n (%)col"])
        p = _n(c["Presumptive TB n (%)row"])
        te = _n(c["Tested n (%)row"])
        d = _n(c["Diagnoseda n (%)row"])
        assert abs(100 * p / s - _p(c["Presumptive TB n (%)row"])) < 0.06, key
        if key != ("Gender", "Female"):   # printed 64.4; the printed counts give 64.2
            assert abs(100 * te / p - _p(c["Tested n (%)row"])) < 0.06, key
        assert abs(100 * d / te - _p(c["Diagnoseda n (%)row"])) < 0.06 or te == 0, key


def test_pgph_table3_tested_equals_table2_tested_and_sums():
    t2, t3 = _pg2(), _cells("PGPH2025", "Table 3")
    for key, c in t3.items():
        assert int(c["Tested N"]) == _n(t2[key]["Tested n (%)row"]), key
    rapid = "Rapid molecular diagnostic test n (%)row"
    for group in ("Gender", "Elderly", "Residence", "Facility-based high-risk group",
                  "Type of high-risk population"):
        assert sum(_n(c[rapid]) for (g, _), c in t3.items() if g == group) == \
            _n(t3[("Total", "")][rapid]), group


@pytest.mark.skipif(not STUDIES.exists(), reason="data_raw absent")
def test_supplement_s1_state_rows_sum_to_printed_india_row():
    s1, _ = q.read_supplement()
    india = next(r for r in s1 if r[0] == "INDIA")
    states = [r for r in s1 if r[0] != "INDIA" and r[1].isdigit()]
    assert len(states) == 35
    for i in (2, 3, 4):   # screened, tested, diagnosed: exact
        assert sum(int(r[i]) for r in states) == int(india[i])
    # population: the printed INDIA row is 1 below the sum of the State rows
    assert sum(int(r[1]) for r in states) - int(india[1]) == 1


@pytest.mark.skipif(not STUDIES.exists(), reason="data_raw absent")
def test_supplement_s2_india_row():
    _, s2 = q.read_supplement()
    india = next(r for r in s2 if r[0] == "INDIA")
    assert india[1:] == ["1443305", "41659", "2.9"]


def _qs():
    with open(QS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_every_quality_row_has_locator_and_source():
    rows = _qs()
    assert len(rows) > 200
    for r in rows:
        assert r["source"].strip() and r["locator"].strip(), r
        assert r["table_id"].strip() and r["column_label"].strip(), r
        assert r["printed_value"].strip(), r
        assert r["quantity"].strip() and r["study"] in ("GHA2023", "GHA2023SM", "PGPH2025")


def test_quality_rows_carry_denominator_columns():
    rows = _qs()
    assert {"denominator_stated", "denominator_methods"} <= set(rows[0])
    pct = [r for r in rows if r["quantity"].startswith("pct_")]
    assert pct and all(r["denominator_stated"] or r["denominator_methods"] for r in pct)


def _mine():
    with open(INV, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["source_file"] in q.OWN_FILES]


def test_inventory_rows_sourced():
    rows = _mine()
    assert len(rows) >= 30
    for r in rows:
        for k in ("source_file", "source_url", "page_or_para", "context_verbatim",
                  "value_printed", "pub_date", "definition_verbatim"):
            assert r[k].strip(), (r["fig_id"], k)


def test_window_fields_present():
    rows = _mine()
    for r in rows:
        assert r["as_on_basis"] in ("stated", "bounded", "window_end"), r["fig_id"]
        if r["as_on_basis"] == "window_end":
            assert r["window_end"] and not r["as_on"]
        if r["window_start"] or r["window_end"]:
            assert r["series_type"] in ("period", "cumulative")
    pg = [r for r in rows if r["fig_id"].startswith("PGPH")]
    assert {(r["window_start"], r["window_end"]) for r in pg} == \
        {("2023-01-01", "2023-09-30")}
    gha = [r for r in rows if r["fig_id"].startswith("GHA")]
    assert all(r["window_start"] == "" and r["window_end"] == "" for r in gha)


def test_fig_id_is_a_content_key_not_a_sequence():
    ids = [r["fig_id"] for r in _mine()]
    assert len(set(ids)) == len(ids)
    for r in _mine():
        study, rest = r["fig_id"].split(".", 1)
        assert study in ("GHA2023", "PGPH2025", "GHA2023SM")
        assert r["fig_id"].endswith("." + r["quantity"].replace(":", "_")), r["fig_id"]


def test_context_convention():
    """Table cells: title | column heading | row label; prose: the sentence only."""
    for r in _mine():
        if r["table_id"]:
            assert len(r["context_verbatim"].split(" | ")) >= 3, r["fig_id"]
        else:
            assert " | " not in r["context_verbatim"] and " … " not in r["context_verbatim"]


def test_quality_csv_rebuilds_identically():
    if not STUDIES.exists():
        pytest.skip("data_raw absent")
    rows, inv = q.build()
    assert _qs() == [{k: str(v) for k, v in r.items()} for r in rows]
    assert {r["fig_id"]: r for r in inv} == {r["fig_id"]: r for r in _mine()}


def test_dnhdd_label_resolves_at_step_2():
    from src.extract import labels
    for lab in ("Dadra Nagar Haveli /Diu Daman", "Dadra Nagar Haveli/Diu Daman"):
        r = labels.resolve(lab)
        assert r.canonical == "Dadra and Nagar Haveli and Daman and Diu" and r.step == 2
        assert "exactly one State/UT" in r.evidence


def _prose():
    return [r for r in _mine() if not r["table_id"]]


def test_prose_contexts_are_full_sentences():
    rows = _prose()
    assert len(rows) > 30
    for r in rows:
        c = r["context_verbatim"]
        assert c.rstrip().endswith((".", "?", "!", ".)")), r["fig_id"]
        assert c[0].isupper() or c[0].isdigit(), r["fig_id"]
        assert "verbatim from the PMC BioC JSON" in r["note"], r["fig_id"]
        assert "not machine-verified" not in r["note"], r["fig_id"]


def test_pinned_prose_contexts():
    rows = {r["fig_id"]: r for r in _prose()}
    gha = rows["GHA2023.abs.sentence.other_pct_population_screened"]
    assert "first ACF cycle" in gha["context_verbatim"]
    assert gha["context_verbatim"].startswith("At the national level, for the first ACF")
    assert (gha["scope"], gha["window_label"]) == ("programme-wide", "first acf cycle")
    assert rows["GHA2023.res.sentence.nns"]["context_verbatim"] == "The NNS was 2824."
    assert rows["GHA2023.res.sentence.other_pct_population_screened"][
        "context_verbatim"].startswith("At the national level, 9.3%")
    t = rows["PGPH2025.res-tested.sentence.tested"]
    assert t["context_verbatim"].startswith("Of 11 357")
    s = rows["PGPH2025.res-screened.sentence.screened"]
    assert s["context_verbatim"].startswith("During the 1031 ACF activity days")
    assert "of the 7 837 170 high-risk population" in s["context_verbatim"]
    assert s["scope"] == "programme-wide"
    assert rows["PGPH2025.res-screened.sentence.other_high_risk_population_denominator"][
        "value"] == "7837170"
    a = rows["PGPH2025.abs-scale.sentence.other_pct_mapped_population_screened"]
    assert a["context_verbatim"].startswith("The two scale indicators (target, observed)")
    assert rows["PGPH2025.abs-screened.sentence.screened"]["value"] == "581633"
    assert {r["value"] for r in rows.values() if r["quantity"] == "other:pct_rapid_molecular_among_tested"} == {"26.4", "26"}


def test_state_rows_enter_with_canonical_geography():
    from src import states
    rows = _mine()
    st = [r for r in rows if r["geography"] not in ("India", "")]
    for q in ("screened", "tested", "tb_cases", "nns"):
        assert len({r["geography"] for r in st if r["quantity"] == q}) >= 34, q
    for r in st:
        assert states.canonical(r["geography"]) == r["geography"]
    dn = [r for r in st if r["geography"] == "Dadra and Nagar Haveli and Daman and Diu"]
    assert dn and all("label rule step 2" in r["note"] for r in dn)
    assert not [r for r in rows if r["geography"] == ""]


def test_subgroup_strata_not_in_inventory_and_decision_recorded():
    assert not [r for r in _mine() if "Elderly" in r["context_verbatim"]
                and r["table_id"] in ("Table 2", "Table 3")]
    for r in _mine():
        if r["table_id"] in ("Table 2", "Table 3"):
            assert r["context_verbatim"].endswith("| Total"), r["fig_id"]
    with open(ROOT / "data/extracted/inventory_scope_decisions.csv", newline="",
              encoding="utf-8") as f:
        dec = [r for r in csv.DictReader(f) if r["source_file"] in q.OWN_FILES]
    cats = [r for r in dec if r["category"] == "subgroup strata"]
    assert len(cats) == 4 and all(r["decision"] == "not entered" for r in cats)


def test_all_state_cells_enter():
    rows = _mine()
    st = [r for r in rows if r["geography"] not in ("India", "")]

    def n(q, tid):
        return len({r["geography"] for r in st if r["quantity"] == q
                    and r["table_id"] == tid})
    for q in ("other:pct_population_screened", "other:pct_tested_among_screened",
              "other:pct_diagnosed_among_tested", "nns"):
        assert n(q, "Table 1") == 35, q
    assert sum(1 for r in st if r["table_id"] == "Table 1") == 35 * 4
    assert n("other:population_in_districts_with_acf_data", "S1 Annex") == 35
    assert n("other:public_sector_tb_notified", "S2 Annex") == 35
    assert n("acf_share_notifications", "S2 Annex") == 35
    assert n("tb_cases", "S2 Annex") == 35
    assert all(r["unit"] == "percent" for r in st if r["quantity"].startswith("other:pct_"))
    with open(ROOT / "data/extracted/inventory_scope_decisions.csv", newline="",
              encoding="utf-8") as f:
        dec = [r for r in csv.DictReader(f)]
    assert not [r for r in dec if "percentage columns" in r["where"]]
    assert not [r for r in dec if r["figures"].startswith("57 211 032")]


def test_remaining_pgph_figures_enter():
    rows = {r["fig_id"]: r for r in _prose()}
    pop = rows["PGPH2025.res-population.sentence.other_population_30_districts"]
    assert pop["value"] == "57211032" and pop["unit"] == "persons"
    tx = rows["PGPH2025.abs-quality.sentence.other_pct_diagnosed_put_on_treatment"]
    assert tx["value"] == "100" and tx["unit"] == "percent"
    assert tx["context_verbatim"].startswith("The four quality indicators")
    x = rows["PGPH2025.res-xray.sentence.screened"]
    assert x["definition_class"] == "screened by chest X-ray" and x["value"] == "9321"


def test_curly_apostrophe_in_methods_wording():
    assert "district’s population" in q.GHA_M["pct_screened"]
    assert "'" not in q.GHA_M["pct_screened"]
