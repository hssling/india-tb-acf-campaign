"""Web pages read online (analysis plan §3.3, §5.3; Part D): transcription, inventory rows,
scope decisions and the dated source-choice addendum."""
import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/figures_inventory.csv"
TRANSCRIBED = ROOT / "data/transcribed/online_pages.csv"
SCOPE = ROOT / "data/extracted/inventory_scope_decisions.csv"
CHOICES = ROOT / "data/source_choices.csv"

from src.extract import online_pages as W  # noqa: E402


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _own():
    return [r for r in _read(INVENTORY) if r["source_file"] in W.OWN_FILES]


def _pages():
    return [r for r in _read(TRANSCRIBED) if r["kind"] == "page"]


# ------------------------------------------------------------- transcription

def test_every_page_has_url_time_method_and_status():
    pages = _pages()
    assert len(pages) >= 40
    keys = [p["page_key"] for p in pages]
    assert len(keys) == len(set(keys))
    for p in pages:
        assert p["url"].startswith("https://"), p["page_key"]
        assert re.fullmatch(r"2026-11-19T\d\d:\d\d:\d\dZ", p["accessed_utc"]), p["page_key"]
        assert p["method"].strip() and p["availability"] in ("read", "unavailable")
        if p["availability"] == "read":
            assert p["title"].strip(), p["page_key"]
        else:
            assert p["note"].strip(), p["page_key"]


def test_every_figure_text_has_locator_and_a_page():
    rows = _read(TRANSCRIBED)
    keys = {r["page_key"] for r in rows if r["kind"] == "page"}
    n = 0
    for r in rows:
        if r["kind"] == "page":
            continue
        n += 1
        assert r["page_key"] in keys and r["text"].strip(), r
        assert r["kind"] in ("sentence", "cell", "lead-in", "bullet")
        if r["kind"] == "cell":
            assert r["column_heading"].strip() and r["row_label"].strip(), r
        else:
            assert re.search(r"(para|bullet) \d+", r["locator"]), r
    assert n > 80


def test_transcribed_sentences_end_in_sentence_punctuation():
    for r in _read(TRANSCRIBED):
        if r["kind"] == "sentence":
            assert r["text"].rstrip().endswith((".", "?", "!", ".)", "..")), r["locator"]
            assert r["text"][0].isupper() or r["text"][0].isdigit(), r["locator"]


# ------------------------------------------------------------- inventory rows

def test_inventory_rows_sourced():
    rows = _own()
    assert len(rows) > 100
    for r in rows:
        assert r["source_file"].strip() and r["page_or_para"].strip(), r["fig_id"]
        assert r["source_url"].strip() == r["source_file"], r["fig_id"]
        assert r["value_printed"].strip() and r["context_verbatim"].strip(), r["fig_id"]
        assert "online_pages.csv" in r["note"], r["fig_id"]


def test_window_fields_present():
    for r in _own():
        for k in ("window_label", "window_start", "window_end", "as_on", "as_on_basis",
                  "series_type"):
            assert k in r
        assert r["as_on_basis"] in ("stated", "bounded", "window_end"), r["fig_id"]
        if r["as_on_basis"] == "stated":
            assert r["as_on"], r["fig_id"]
        if r["window_start"] or r["window_end"]:
            assert r["series_type"] in ("period", "cumulative"), r["fig_id"]
        if r["series_type"] == "cumulative":
            assert r["window_start"], r["fig_id"]
        if r["as_on_basis"] == "bounded":
            assert r["pub_date"] or "no date printed" in r["note"], r["fig_id"]


def test_prose_contexts_are_full_sentences_and_match_the_transcription():
    from src import inventory_rules as R
    tr = {}
    for t in _read(TRANSCRIBED):
        if t["kind"] in ("sentence", "bullet"):
            tr[(t["page_key"], t["locator"].split(";")[0])] = t["text"]
    texts = set(tr.values())
    for r in _own():
        ctx = r["context_verbatim"]
        if r["table_id"]:
            assert ctx.endswith("| TB Screening"), r["fig_id"]
            continue
        assert ctx in texts, r["fig_id"]
        if "(highlight bullet)" not in r["page_or_para"]:     # a bullet is kept as printed
            assert ctx.rstrip().endswith((".", "?", "!", ".)", "..")), r["fig_id"]
        assert " | " not in ctx and " … " not in ctx
        R.find_figure(ctx, r["value_printed"])
        assert R.scope(ctx)[0] == r["scope"], r["fig_id"]
        if r["quantity"] in ("screened", "tested", "tb_cases"):
            assert r["definition_verbatim"] in ctx, r["fig_id"]
            assert R.definition_class(r["quantity"], r["definition_verbatim"])[0] \
                == r["definition_class"], r["fig_id"]


def test_highlight_bullet_figures_enter_as_printed():
    bullets = {(t["page_key"], t["locator"].split(";")[0]): t["text"]
               for t in _read(TRANSCRIBED) if t["kind"] == "bullet"}
    assert len(bullets) >= 20
    pages = {p["page_key"]: p["url"] for p in _pages()}
    rows = [r for r in _own() if "(highlight bullet)" in r["page_or_para"]]
    assert len(rows) == 39
    for r in rows:
        assert r["context_verbatim"] in bullets.values(), r["fig_id"]
    r = [x for x in rows if x["value_printed"] == "3.57 lakh"]
    assert len(r) == 1 and r[0]["source_file"] == pages["2105575"]
    assert r[0]["context_verbatim"].startswith("Since the launch of 100-day campaign")
    dec = [d for d in _read(SCOPE) if d["source_file"] in W.OWN_FILES]
    assert not [d for d in dec if d["category"] == "headline bullet"]


def test_no_duplicate_fig_ids():
    ids = [r["fig_id"] for r in _read(INVENTORY)]
    assert len(ids) == len(set(ids))
    rows, _ = W.build()
    built = [r["fig_id"] for r in rows]
    assert len(built) == len(set(built))
    with pytest.raises(ValueError):
        W.check_ids([{"fig_id": "a"}, {"fig_id": "a"}])


def test_inventory_rebuilds_identically_from_the_transcription():
    rows, _ = W.build()
    assert [{k: str(v) for k, v in r.items()} for r in rows] == _own()


def test_every_cited_pair_is_in_the_inventory():
    own = {(r["source_file"], r["quantity"]) for r in _own()}
    by_page = {p["page_key"]: p["url"] for p in _pages()}
    assert (by_page["2199422"], "screened") in own          # cited by the 24 March 2026 note
    assert (by_page["2112158"], "districts_selected") in own  # the 455-district figure
    assert (by_page["2081662"], "districts_selected") in own


# ------------------------------------------------------------- scope decisions

def test_scope_decisions_cover_every_page_without_rows():
    dec = [r for r in _read(SCOPE) if r["source_file"] in W.OWN_FILES]
    assert any(r["kind"] == "rule" for r in dec)
    with_rows = {r["source_file"] for r in _own()}
    for p in _pages():
        if p["url"] not in with_rows:
            assert any(d["source_file"] == p["url"] and d["kind"] in ("exclusion", "unavailable")
                       for d in dec), p["page_key"]
    for d in dec:
        assert d["reason"].strip(), d
    # PRID 2115334: the provisional row of §5.3 is resolved and excluded with its reason
    d = [x for x in dec if "2115334" in x["source_file"]]
    assert d and "no figure" in d[0]["reason"]


def test_scope_decisions_merge_keeps_other_rows():
    other = [r for r in _read(SCOPE) if r["source_file"] not in W.OWN_FILES]
    assert len(other) > 100
    merged = W._merge_scope(W.scope_decisions())
    assert [r for r in merged if r["source_file"] not in W.OWN_FILES] == other


# ------------------------------------------------------------- source-choice addendum

def test_source_choices_addendum_is_dated_and_rebuilds():
    from src.extract import source_choices as S
    rows = S.build()
    web = [r for r in rows if r["decision_id"].startswith("WEB-")]
    assert len(web) >= 6
    assert all(r["date"] == "2026-11-19" for r in web)
    topics = " ".join(r["topic"] for r in web)
    assert "web pages" in topics
    text = " ".join(r["decision"] + " " + r["result"] for r in web)
    assert "2199422" in text and "unavailable" in text
    # existing frozen rows are unchanged: no SCO row names a Part D page
    assert not [r for r in rows if r["decision_id"].startswith("SCO-")
                and r["source_file"] in W.OWN_FILES]
    assert rows[-len(web):] == web          # appended after the guard addendum
    assert _read(CHOICES) == [{k: str(v) for k, v in r.items()} for r in rows]


def test_plan_section_13_has_the_part_d_and_guard_order_entries():
    text = (ROOT / "docs/analysis_plan.md").read_text(encoding="utf-8")
    head, sec13 = text.split("## 13. Deviations", 1)
    assert "Part D (19 November 2026)" in sec13
    assert "dated addendum to data/source_choices.csv" in sec13
    assert "dbb71b3" in sec13 and "OUT-08, GRD-01..06" in sec13
    assert "11cfbe4" in sec13 or "guard result" in sec13
    assert "Part D" not in head
