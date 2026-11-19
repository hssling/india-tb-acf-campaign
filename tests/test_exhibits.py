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
         "Denominator", "Label", "Status", "Published", "Source"}


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
            for r in rows:
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
    assert ex["Table 2"]["panels"][0][1][0][3] == f"{int(q['Q2 entry pairs (all)']['corrected']):,}"


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
