"""Task 9a: exhibits build from outputs/ and every numeric cell traces to an output value."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "exhibits"))
import make_tables as mt  # noqa: E402

PLAIN = {"Data year", "Class", "Quantity and scope", "Evidence", "Row", "Source table", "Analysis", "Study",
         "Indicator", "Geography", "Scope", "A source", "B source", "Quantity", "Class of entry pair", "State",
         "Denominator", "Label", "Status", "Published", "Source", "Source of A", "Source of B",
         "Quantity, geography and scope", "Group"}


def read(rel):
    with open(ROOT / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def built():
    return mt.build()


def test_main_text_exhibits_at_most_five(built):
    ex, _ = built
    main_tables = [k for k, v in ex.items() if v["main"]]
    assert main_tables == mt.MAIN_TABLES
    n_figures = 2  # Figure 1 and Figure 2, see make_figures.py
    assert len(main_tables) + n_figures <= 5


def test_values_trace_to_outputs(built):
    _, tr = built
    cache = {}
    for e in tr.entries:
        if e["file"] not in cache:
            cache[e["file"]] = read(e["file"])
        rows = cache[e["file"]]
        if e["kind"] == "value":
            assert rows[e["row"]][e["column"]] == e["raw"]
            assert mt.FORMATTERS[e["fmt"]](e["raw"]) == e["text"]
        elif e["kind"] == "count":
            sel = [r for r in rows if all(r[k] == v for k, v in e["filters"].items())]
            got = len({r[e["distinct"]] for r in sel}) if e["distinct"] else len(sel)
            assert f"{got:,}" == e["text"]
        elif e["kind"] == "prefix_count":
            assert f"{sum(r[e['column']].startswith(e['prefix']) for r in rows):,}" == e["text"]
        elif e["kind"] == "prefix_count_distinct":
            got = len({r[e["distinct"]] for r in rows if r[e["column"]].startswith(e["prefix"])})
            assert f"{got:,}" == e["text"]
    assert len(tr.entries) > 1000


def test_every_numeric_cell_is_traced(built):
    ex, tr = built
    traced = {e["text"] for e in tr.entries}
    untraced = []
    for name, e in ex.items():
        for header, rows in e["panels"]:
            span = False
            for r in rows:
                if span:  # the heading row of a block below a spanning row
                    header, span = [c.strip("*") for c in r], False
                    continue
                if r[0].startswith("**") and not any(c.strip() for c in r[1:]):
                    span = True  # a spanning row: the next row heads the block below it
                    continue
                for j, c in enumerate(r):
                    c = c.strip()
                    if not c or not any(ch.isdigit() for ch in c) or header[j] in PLAIN or c in traced:
                        continue
                    parts = [p.strip() for p in c.replace(" (", " to ").replace(")", "").split(" to ")]
                    if all(p in traced for p in parts):
                        continue
                    untraced.append((name, header[j], c))
    assert not untraced, untraced[:10]


def test_spot_checks_against_outputs(built):
    ex, _ = built
    t3 = ex["Table 3"]["panels"][0][1]
    s = read("outputs/q3_yield_summary.csv")
    r = next(x for x in s if x["state"] == "India" and x["year"] == "2023" and x["indicator"] == "nns")
    row = next(x for x in t3 if x[0] == "2023")
    assert f"{float(r['value']):,.0f}" in row[5]
    assert f"{int(r['denominator']):,}" == row[2]
    q = {x["metric"]: x for x in read("outputs/q2_summary_registered_vs_corrected.csv")}
    assert ex["Table 2"]["panels"][0][1][0][4] == f"{int(q['Q2 entry pairs (all)']['corrected']):,}"


def test_build_writes_local_files():
    r = subprocess.run([sys.executable, "-I", str(ROOT / "exhibits" / "make_tables.py")], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    t = (ROOT / "manuscript" / "exhibits" / "tables.md").read_text(encoding="utf-8")
    assert "\r" not in t


def test_figures_build():
    pytest.importorskip("matplotlib")
    r = subprocess.run([sys.executable, "-I", str(ROOT / "exhibits" / "make_figures.py")], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for n in ("figure1.png", "figure1.pdf", "figure2.png", "figure2.pdf"):
        assert (ROOT / "manuscript" / "exhibits" / n).stat().st_size > 5000


def test_md_table_escapes_a_pipe_inside_a_cell():
    out = mt.md_table(["A", "B"], [["73,772 | 73772", "41,659"]])
    assert out.splitlines()[-1] == r"| 73,772 \| 73772 | 41,659 |"


def test_table_s1_totals_equal_table_2(built):
    ex, _ = built
    rows = ex["Table S1"]["panels"][0][1]
    t2 = ex["Table 2"]["panels"][0][1]
    totals = [r for r in rows if r[1] == "All groups"]
    assert [r[0] for r in totals] == ["Registered", "Corrected (post hoc)"]
    for tot, col in zip(totals, (2, 4)):  # Table 2 columns: registered all, corrected all
        assert tot[5] == t2[0][col] and tot[6] == t2[1][col]
        assert tot[7:] == [r[col] for r in t2[2:7]]


def test_supplementary_data_has_every_pair():
    for _, f, _, _ in mt.Q2_SETS:
        header, rows = mt.supplementary_data(f)
        src = read(f)
        assert len(rows) == len(src) and header == [h for h, _, _ in mt.DATA_COLUMNS]
        j = header.index("Evidence")
        assert all(r[j] == s["evidence"] for r in rows for s in [src[int(r[0]) - 1]])
        assert mt.supplementary_data_bytes(f).decode("utf-8").count(chr(10)) >= len(src) + 1


def test_table_2_evidence_is_short(built):
    ex, _ = built
    rows = ex["Table 2"]["panels"][0][1]
    i = next(k for k, r in enumerate(rows) if r[0] == f"**{mt.SPAN_T2}**")
    pairs = rows[i + 2:]
    assert pairs and all(r[0][0] in "12" and len(r[-1]) <= 40 for r in pairs)


def test_table_2_is_one_grid(built):
    ex, _ = built
    (header, rows), = ex["Table 2"]["panels"]
    assert all(len(r) == len(header) for r in rows)
    i = next(k for k, r in enumerate(rows) if r[0] == f"**{mt.SPAN_T2}**")
    assert not any(c.strip() for c in rows[i][1:]) and rows[i + 1][0] == "**Class**"


def test_table_1_rows_sum_to_the_inventory(built):
    ex, _ = built
    rows = ex["Table 1"]["panels"][0][1]
    total = int(rows[0][1].replace(",", ""))
    parts = [int(r[1].replace(",", "")) for r in rows[1:] if r[0].startswith("  ") and not r[0].strip().startswith("Check")]
    assert sum(parts) == total
    labels = [r[0].strip() for r in rows]
    assert "ACF share of notifications" in labels and "People with presumptive TB" in labels


def test_table_3_footnotes_in_reading_order(built):
    ex, _ = built
    (header, rows), = ex["Table 3"]["panels"]
    marks = [ch for cell in header + [c for r in rows for c in r] for ch in cell if ch in mt.SUP]
    assert list(dict.fromkeys(marks)) == list(mt.SUP[:3])
    notes = ex["Table 3"]["notes"]
    assert [n[0] for n in notes] == list(mt.SUP[:3]) and "per cent" not in " ".join(notes)


def test_make_figures_without_matplotlib_exits_1(tmp_path):
    """Run directly with matplotlib hidden: a message on stderr and exit code 1."""
    (tmp_path / "matplotlib.py").write_text("raise ImportError('hidden for the test')\n", encoding="utf-8")
    code = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); "
            "runpy.run_path(sys.argv[2], run_name='__main__')")
    r = subprocess.run([sys.executable, "-I", "-c", code, str(tmp_path),
                        str(ROOT / "exhibits" / "make_figures.py")], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 1 and "matplotlib is not installed" in r.stderr and r.stdout == ""
