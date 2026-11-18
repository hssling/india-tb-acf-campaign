"""The figure inventory (analysis plan §5): schema, provenance and window fields."""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/figures_inventory.csv"
OFFICIAL = ROOT / "data_raw/official"

COLUMNS = ["fig_id", "quantity", "value", "value_printed", "qualifier", "unit",
           "definition_verbatim", "context_verbatim", "definition_class", "scope",
           "series_type", "window_label", "window_start", "window_end", "as_on",
           "as_on_basis", "geography", "source_file", "source_url", "page_or_para",
           "table_id", "pub_date", "note"]
QUANTITIES = {"districts_selected", "population_targeted", "screened", "presumptive",
              "tested", "tb_cases", "acf_share_notifications", "nns", "yield"}


def _rows():
    with open(INVENTORY, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        assert r.fieldnames == COLUMNS
        return list(r)


def test_inventory_rows_sourced():
    rows = _rows()
    assert rows
    for r in rows:
        assert r["source_file"].strip(), r["fig_id"]
        assert r["page_or_para"].strip(), r["fig_id"]
        assert r["source_url"].strip(), r["fig_id"]
        assert r["value_printed"].strip(), r["fig_id"]
        assert r["context_verbatim"].strip(), r["fig_id"]


def test_window_fields_present():
    for r in _rows():
        for k in ("window_label", "window_start", "window_end", "as_on", "as_on_basis",
                  "series_type"):
            assert k in r
        assert r["as_on_basis"] in ("stated", "bounded", "window_end"), r["fig_id"]
        if r["as_on_basis"] == "stated":
            assert r["as_on"], r["fig_id"]
        if r["as_on_basis"] == "window_end":
            assert r["window_end"] and not r["as_on"], r["fig_id"]
        if r["window_end"] or r["window_start"]:
            assert r["series_type"] in ("period", "cumulative"), r["fig_id"]
        if r["series_type"] == "cumulative":
            assert r["window_start"], r["fig_id"]


def test_inventory_vocabularies():
    ids = set()
    for r in _rows():
        assert r["fig_id"] not in ids
        ids.add(r["fig_id"])
        q = r["quantity"]
        assert q in QUANTITIES or (q.startswith("other:") and len(q) > 6), q
        assert r["qualifier"] in ("exact", "at_least", "about", "at_most")
        assert r["unit"] in ("", "persons", "tests", "cases", "districts", "percent",
                             "ratio")
        assert r["scope"] in ("phase 1", "expanded campaign", "programme-wide",
                              "unspecified")
        if q in ("screened", "tested", "tb_cases"):
            assert r["definition_class"], r["fig_id"]


def test_inventory_geography_canonical():
    from src import states
    for r in _rows():
        if r["geography"] != "India":
            assert states.canonical(r["geography"]) == r["geography"]


@pytest.mark.skipif(not OFFICIAL.exists(), reason="data_raw absent")
def test_inventory_rebuilds_identically_from_sources():
    from src.extract import campaign
    rows, provenance = campaign.build_inventory()
    assert all(p["verified"] in ("text", "text (loose)", "page image")
               for p in provenance)
    built = [{k: str(v) for k, v in r.items()} for r in rows]
    on_disk = [r for r in _rows() if r["source_file"] in campaign.OWN_FILES]
    assert built == on_disk
