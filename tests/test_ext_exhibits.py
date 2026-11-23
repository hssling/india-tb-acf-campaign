"""Extension exhibits (Public Health): the five main display items and Tables S1-S8 build from
outputs/ext/ and outputs/ only; every numeric cell traces to an output value; no internal
identifiers; Figure 2's robust marking and Table 1's labels follow the outputs."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "exhibits")):
    if p not in sys.path:
        sys.path.insert(0, p)

import make_ext_tables as et  # noqa: E402
from verification import check_manuscript_numbers as cmn  # noqa: E402

NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?")
IDENTIFIERS = cmn.BANNED + [
    (r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", "a variable name"),
    (r"\.(?:csv|py|json|md)\b|\b(?:outputs|data|exhibits|src|manuscript)/", "a file path"),
    (r"\b(?:epsilon|rho|theta|tier_agrees|pooled_eb|inverse_poisson)\b", "a variable name"),
    (r"\bQ[1-4]\b|\bv1\.\d|\bplan\b", "an internal reference"),
    (r"\b[A-Z]{2,}\d{4}\b", "a shorthand source identifier"),
]


def read(rel: str) -> list[dict]:
    with open(ROOT / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tokens(text: str) -> set[str]:
    return set(NUM.findall(text))


@pytest.fixture(scope="module")
def built():
    return et.build()


@pytest.fixture(scope="module")
def ef():
    pytest.importorskip("matplotlib")
    import make_ext_figures
    return make_ext_figures


@pytest.fixture(scope="module")
def rendered(ef, tmp_path_factory):
    out = tmp_path_factory.mktemp("figs")
    return out, ef.build(out)


def cells(ex: dict):
    """(exhibit, column header, cell) for every body cell; a spanning row's next row heads
    the block below it (as in exhibits/make_tables.py)."""
    for name, e in ex.items():
        for header, rows in e["panels"]:
            head, span = header, False
            for r in rows:
                if span:
                    head, span = [c.strip("*") for c in r], False
                    continue
                if r[0].startswith("**") and not any(c.strip() for c in r[1:]):
                    span = True
                    continue
                for j, c in enumerate(r):
                    yield name, head[j], c


# ------------------------------------------------------------------ structure

def test_at_most_five_main_display_items(built, ef):
    ex, _ = built
    main = [k for k, v in ex.items() if v["main"]]
    assert main == et.MAIN_TABLES == ["Table 1"]
    assert ef.FIGURES == ["figure1", "figure2", "figure3", "figure4"]
    assert len(main) + len(ef.FIGURES) <= 5


def test_supplementary_tables_s1_to_s8(built):
    ex, _ = built
    assert list(ex) == ["Table 1"] + [f"Table S{i}" for i in range(1, 9)]
    assert all(not ex[k]["main"] for k in ex if k != "Table 1")


def test_every_row_has_the_header_width(built):
    ex, _ = built
    for name, e in ex.items():
        for header, rows in e["panels"]:
            assert all(len(r) == len(header) for r in rows), name


# ------------------------------------------------------------------ tracing

def test_reads_only_outputs(built, rendered):
    _, tr = built
    _, res = rendered
    files = {e["file"] for e in tr.entries} | {e["file"] for e in res["trace"]}
    assert files and all(f.startswith("outputs/") for f in files), files
    assert any(f.startswith("outputs/ext/") for f in files)
    for mod in ("make_ext_tables.py", "make_ext_figures.py"):
        src = (ROOT / "exhibits" / mod).read_text(encoding="utf-8")
        assert not re.search(r"""read\(\s*["'](?!outputs/)""", src), mod


def check_entry(e: dict, cache: dict) -> None:
    if e["file"] not in cache:
        cache[e["file"]] = read(e["file"])
    rows = cache[e["file"]]
    if e["kind"] == "value":
        assert rows[e["row"]][e["column"]] == e["raw"], e
        assert et.FORMATTERS[e["fmt"]](e["raw"]) == e["text"], e
    elif e["kind"] == "count":
        sel = [r for r in rows if all(r[k] == v for k, v in e["filters"].items())]
        assert f"{len(sel):,}" == e["text"], e
    elif e["kind"] == "stat":
        vals = [float(r[e["column"]]) for r in rows if all(r[k] == v for k, v in e["filters"].items())]
        assert repr(et.STATS[e["op"]](vals)) == e["raw"], e
        assert et.FORMATTERS[e["fmt"]](e["raw"]) == e["text"], e
    else:
        raise AssertionError(f"unknown trace kind {e['kind']}")


def test_table_trace_matches_outputs(built):
    _, tr = built
    cache: dict = {}
    for e in tr.entries:
        check_entry(e, cache)
    assert len(tr.entries) > 1000


def test_every_numeric_cell_is_traced(built):
    ex, tr = built
    traced: dict[str, set] = {}
    for e in tr.entries:
        traced.setdefault(e["exhibit"], set()).update(tokens(e["text"]))
    untraced = []
    for name, head, c in cells(ex):
        if head in et.LABEL_COLUMNS:
            continue
        for t in tokens(c.replace("−", "")):
            if t not in traced.get(name, set()):
                untraced.append((name, head, c))
    assert not untraced, untraced[:10]


def test_label_columns_hold_no_result(built):
    """A label column may hold years, small counts in words' place and the 0.5 of the zero
    handling, never a result value."""
    ex, _ = built
    for name, head, c in cells(ex):
        if head in et.LABEL_COLUMNS:
            for t in tokens(c):
                assert re.fullmatch(r"20\d\d|\d{1,2}|0\.5|100,000", t), (name, head, c)


def test_figure_trace_matches_outputs(rendered):
    _, res = rendered
    cache: dict = {}
    for e in res["trace"]:
        check_entry(e, cache)
    figs = {e["exhibit"] for e in res["trace"]}
    assert figs == {"Figure 1", "Figure 2", "Figure 3", "Figure 4"}


def test_figure_annotations_are_traced(rendered):
    _, res = rendered
    for fig, texts in res["annotations"].items():
        traced = set()
        for e in res["trace"]:
            if e["exhibit"] == fig:
                traced |= tokens(e["text"])
        for t in texts:
            for tok in tokens(t.replace("−", "")):
                assert tok in traced, (fig, t, tok)


# ------------------------------------------------------------------ content

def test_table1_labels_equal_headline(built):
    ex, _ = built
    (header, rows), = ex["Table 1"]["panels"]
    j = header.index(next(h for h in header if h.startswith("Label")))
    labels = [r[j] for r in rows if r[j]]
    assert [lab.lower() for lab in labels] == [r["label"] for r in read("outputs/ext/headline.csv")]


def test_table1_main_values(built):
    ex, _ = built
    (header, rows), = ex["Table 1"]["panels"]
    main_rows = [r for r in rows if r[-1]]
    for r, h in zip(main_rows, read("outputs/ext/headline.csv")):
        d = 3 if abs(float(h["main_value"])) < 0.1 else 2
        want = et.FORMATTERS[f"dec{d}"](h["main_value"])
        assert r[1].startswith(want + " ("), (r[1], want)
    sub = [r[0] for r in rows if r[0].startswith("  ")]
    assert any("Poisson" in s for s in sub) and any("log scale" in s.lower() for s in sub)
    assert sum("intensity" in s for s in sub) == 2


def test_figure2_robust_marking_matches_betweenyear(ef):
    pts = ef.figure2_points()
    by = {r["unit"]: r["tier_agrees"] == "yes" for r in read("outputs/ext/d1_states_betweenyear.csv")}
    assert {p["unit"]: p["robust"] for p in pts} == by
    reg = {r["unit"]: r["tier"] for r in read("outputs/ext/d1_states.csv") if r["analysis"] == "2021-2023"}
    assert all(p["tier"] == reg[p["unit"]] for p in pts)
    n = read("outputs/ext/d1_pooled_betweenyear.csv")[0]
    assert sum(p["robust"] for p in pts) == int(n["n_tier_agrees"])


def test_figure2_is_not_a_league_table(ef):
    pts = ef.figure2_points()
    order = ["above", "overlaps", "below"]
    assert [p["tier"] for p in pts] == sorted((p["tier"] for p in pts), key=order.index)
    for t in order:
        names = [p["name"] for p in pts if p["tier"] == t]
        assert names == sorted(names)


def test_figure4_has_every_specification(ef):
    d = ef.figure4_points()
    assert sum(len(v) for v in d.values()) == 64
    for v in d.values():
        vals = [p["value"] for p in v]
        assert vals == sorted(vals)


# ------------------------------------------------------------------ wording and style

def all_text(ex: dict) -> list[tuple[str, str]]:
    out = []
    for name, e in ex.items():
        out.append((name, e["title"]))
        out += [(name, n) for n in e["notes"]]
        for header, rows in e["panels"]:
            out += [(name, h) for h in header]
            out += [(name, c) for r in rows for c in r]
    return out


def identifier_problems(pairs) -> list:
    bad = []
    for where, t in pairs:
        for pat, what in IDENTIFIERS:
            for m in re.finditer(pat, t):
                bad.append((where, what, m.group()))
        for pat in cmn.AMERICAN:
            for m in re.finditer(pat, t, re.I):
                bad.append((where, "American spelling", m.group()))
    return bad


def test_no_internal_identifiers_in_tables(built):
    ex, _ = built
    assert not identifier_problems(all_text(ex))


def test_no_internal_identifiers_in_figures(rendered):
    out, res = rendered
    pairs = [(f, t) for f, texts in res["texts"].items() for t in texts]
    notes = (out / "figure_notes.md").read_text(encoding="utf-8")
    pairs += [("figure_notes", ln) for ln in notes.splitlines() if not ln.startswith("# Figure notes (generated")]
    assert not identifier_problems(pairs)


def test_unicode_minus_everywhere(built, rendered):
    ex, _ = built
    _, res = rendered
    texts = [t for _, t in all_text(ex)] + [t for v in res["texts"].values() for t in v]
    assert not [t for t in texts if re.search(r"(?<![\w-])-\d", t)]
    assert any("−" in t for v in res["texts"].values() for t in v)  # a negative tick or value


def test_footnote_letters_in_reading_order(built):
    ex, _ = built
    for name, e in ex.items():
        marks = [ch for header, rows in e["panels"] for cell in header + [c for r in rows for c in r]
                 for ch in cell if ch in et.SUP]
        first = list(dict.fromkeys(marks))
        assert first == list(et.SUP[:len(first)]), name
        lettered = [n[0] for n in e["notes"] if n[0] in et.SUP]
        assert lettered == first, name


# ------------------------------------------------------------------ files

def files_digest(d: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir()) if p.is_file()}


def test_tables_build_byte_reproducible(tmp_path):
    for sub in ("a", "b"):
        r = subprocess.run([sys.executable, "-I", str(ROOT / "exhibits" / "make_ext_tables.py"),
                            "--out", str(tmp_path / sub)], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    a, b = files_digest(tmp_path / "a"), files_digest(tmp_path / "b")
    assert a == b and {"tables.md", "trace.json", "table1.csv", "tables8.csv"} <= set(a)
    for n in a:
        assert b"\r" not in (tmp_path / "a" / n).read_bytes(), n
    trace = json.loads((tmp_path / "a" / "trace.json").read_text(encoding="utf-8"))
    assert trace and all(e["file"].startswith("outputs/") for e in trace)


def test_figures_build_deterministic(ef, rendered, tmp_path):
    out, _ = rendered
    ef.build(tmp_path)
    a, b = files_digest(out), files_digest(tmp_path)
    assert a == b
    for i in range(1, 5):
        for ext in ("pdf", "png", "tif"):
            assert (out / f"figure{i}.{ext}").stat().st_size > 5000


def test_tiff_is_greyscale_at_least_300_dpi(ef, rendered):
    from PIL import Image
    out, _ = rendered
    for i in range(1, 5):
        im = Image.open(out / f"figure{i}.tif")
        assert im.mode == "L" and min(im.info["dpi"]) >= 300 and im.info.get("compression") == "tiff_lzw"


# ------------------------------------------------------------------ the "ijtb" set (Indian Journal of Tuberculosis)

@pytest.fixture(scope="module")
def built_ijtb():
    return et.build("ijtb")


def test_ijtb_set_adds_table2_and_s9_only(built, built_ijtb):
    ex, _ = built
    ij, _ = built_ijtb
    assert list(ij) == ["Table 1", "Table 2"] + [f"Table S{i}" for i in range(1, 10)]
    assert [k for k, v in ij.items() if v["main"]] == et.MAIN_TABLES_IJTB
    for k in ex:  # the shared tables are identical in both sets
        assert ij[k] == ex[k], k


def test_ijtb_trace_matches_outputs(built_ijtb):
    ex, tr = built_ijtb
    cache: dict = {}
    for e in tr.entries:
        check_entry(e, cache)
    traced: dict[str, set] = {}
    for e in tr.entries:
        traced.setdefault(e["exhibit"], set()).update(tokens(e["text"]))
    untraced = [(n, h, c) for n, h, c in cells(ex) if h not in et.LABEL_COLUMNS
                for t in tokens(c.replace("−", "")) if t not in traced.get(n, set())]
    assert not untraced, untraced[:10]
    files = {e["file"] for e in tr.entries}
    assert all(f.startswith("outputs/") for f in files), files


def test_table2_number_needed_to_screen_is_the_reciprocal_of_the_yield(built_ijtb):
    ex, _ = built_ijtb
    for r in ex["Table 2"]["panels"][0][1]:
        y = float(r[3].split(" (")[0])
        nns = int(r[4].split(" (")[0].replace(",", ""))
        assert abs(nns - 100000 / y) <= 0.5 + 100000 / y * 0.002, r  # the yield cell is rounded


def test_table_s9_has_every_state(built_ijtb):
    ex, _ = built_ijtb
    units = {r["unit"] for r in read("outputs/ext/d1_intensity_strata.csv")}
    assert len(ex["Table S9"]["panels"][0][1]) == len(units)
