"""Part E: five further parliamentary answers (dated addendum; §5.1, §5.3, §13)."""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"
RAW = ROOT / "data_raw/pq/AU414.pdf"


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _own():
    from src.extract import pq_more as E
    return [r for r in _read(INVENTORY) if r["source_file"] in E.OWN_FILES]


def test_q414_printed_total_checks():
    """Each Q414 table: one check per column; no Total or India row is printed, so the
    sum check is not applied and the record says so; the recorded sum is the sum of the
    extracted State values."""
    from src import source_checks as sc
    from src.extract import pq_more as E
    checks = {c["table"]: c for c in _read(EXTRACTED / "table_total_checks.csv")}
    for t in E.Q414_TABLES:
        rows = _read(EXTRACTED / t.csv_name)
        n_units = len({r["label_printed"] for r in rows})
        assert n_units in (35, 36), t.csv_name
        for c in t.columns:
            ck = checks[t.check_name(c)]
            vals = [int(r["value"]) for r in rows if r["column"] == c.key and r["value"]]
            assert int(ck["sum_of_rows"]) == sum(vals)
            assert ck["printed_total"] == "" and ck["pass"] == "n/a"
            assert ck["note"].startswith(sc.NO_TOTAL)


def test_q414_rows_carry_provenance_and_units():
    from src import states
    from src.extract import pq_more as E
    for t in E.Q414_TABLES:
        for r in _read(EXTRACTED / t.csv_name):
            assert r["source_file"] and r["pdf_pages"] and r["table_id"]
            assert r["window_start"] and r["window_end"]
            assert r["as_on_basis"] == "bounded" and not r["as_on"]
            assert states.canonical(r["canonical"]) == r["canonical"]
            assert r["coarse_unit"] == states.coarsen(r["canonical"])


def test_inventory_rows_sourced():
    rows = _own()
    assert rows
    for r in rows:
        assert r["source_file"].strip() and r["page_or_para"].strip(), r["fig_id"]
        assert r["source_url"].strip() and r["value_printed"].strip(), r["fig_id"]
        assert r["context_verbatim"].strip(), r["fig_id"]
        assert r["pub_date"], r["fig_id"]


def test_window_fields_present():
    from src import inventory_rules as R
    for r in _own():
        for k in ("window_label", "window_start", "window_end", "as_on", "as_on_basis",
                  "series_type"):
            assert k in r
        assert r["as_on_basis"] == "bounded" and not r["as_on"], r["fig_id"]
        if r["series_type"] == "cumulative":
            assert r["window_start"], r["fig_id"]
        R.find_figure(r["context_verbatim"], r["value_printed"])
        assert r["definition_verbatim"] in r["context_verbatim"], r["fig_id"]
        assert R.scope(r["context_verbatim"])[0] == r["scope"], r["fig_id"]
        assert R.window_label(r["context_verbatim"], "",
                              bool(r["window_end"] or r["as_on"])) == r["window_label"]


def test_q414_not_in_inventory():
    from src.extract import pq_more as E
    assert not [r for r in _own() if r["source_file"] == E.Q414_FILE]


@pytest.mark.skipif(not RAW.exists(), reason="data_raw absent")
def test_part_e_inventory_rebuilds_identically():
    from src.extract import pq_more as E
    rows, prov = E.build_inventory()
    assert all(p["method"] in ("text", "text (loose)") for p in prov)
    assert [{k: str(v) for k, v in r.items()} for r in rows] == _own()
    for t in E.Q414_TABLES:
        assert [{k: str(v) for k, v in r.items()} for r in E.q414_rows(t)] == \
            _read(EXTRACTED / t.csv_name)


def test_source_choices_part_e_addendum():
    from src.extract import source_choices as S
    rows = S.build()
    e = [r for r in rows if r["decision_id"].startswith("PQE-")]
    text = " ".join(r["source_file"] + " " + r["decision"] + " " + r["result"] for r in e)
    for f in ("AU278_alnANG.pdf", "AU279_lXzMCu.pdf", "AU2051_PXcr4v.pdf", "AU414.pdf",
              "AS79_mh2ZZK.docx"):
        assert f in text, f
    assert any("MHA" in r["decision"] and r["result"].startswith("unavailable")
               for r in e)
    assert all(r["date"] == "2026-11-19" for r in e)
    # the addendum follows every frozen row
    ids = [r["decision_id"] for r in rows]
    assert ids.index(e[0]["decision_id"]) > max(
        k for k, i in enumerate(ids) if not i.startswith("PQE-"))
    path = ROOT / "data/source_choices.csv"
    assert _read(path) == [{k: str(v) for k, v in r.items()} for r in rows]
