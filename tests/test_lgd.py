"""LGD district denominator at 7 December 2024 (analysis plan §9.3)."""
import zipfile
from datetime import date
from pathlib import Path

import pytest

from src.extract import lgd

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data_raw/lgd/All_Districtof_India_2026-11-18_21-18-59.xlsx"
MODS = ROOT / "data_raw/lgd/alldistrictbyDate2026_11_18_21_20_13_069.xls"


def _cur(*rows):
    return [{"state_label": s, "district_code": c, "district_name": n}
            for s, c, n in rows]


def _mod(row, code, state, *, eff="", mod="", kind="", prev=""):
    return {"row": row, "district_code": code, "district_name": f"D{code}",
            "state_label": state, "effective_date": eff, "modification_date": mod,
            "type": kind, "previous_state_label": prev}


CURRENT_LIST = _cur(("Goa", "1", "North Goa"), ("Goa", "2", "South Goa"),
                    ("Goa", "3", "New Goa"), ("Kerala", "4", "K1"),
                    ("Kerala", "5", "K2"), ("Assam", "6", "A1"),
                    ("Sikkim", "7", "S1"))


def test_created_after_reference_date_is_removed():
    mods = [_mod(10, "3", "Goa", eff="2025-01-10", kind="created")]
    out, log = lgd.reconstruct(CURRENT_LIST, mods)
    assert out["Goa"]["count"] == 2 and out["Goa"]["current_count"] == 3
    assert log[0]["action"] == "reversed: district removed"
    assert log[0]["date_field"] == "effective date"


def test_modification_on_reference_date_is_kept():
    mods = [_mod(10, "3", "Goa", mod="2024-12-07", kind="created")]
    out, log = lgd.reconstruct(CURRENT_LIST, mods)
    assert out["Goa"]["count"] == 3
    assert log[0]["action"].startswith("kept")
    assert log[0]["date_field"] == "modification date"


def test_rename_abolish_and_move_are_reversed():
    mods = [_mod(1, "4", "Kerala", eff="2025-02-01", kind="renamed"),
            _mod(2, "99", "Kerala", eff="2025-03-01", kind="abolished"),
            _mod(3, "6", "Assam", eff="2025-04-01", kind="moved", prev="Sikkim")]
    out, log = lgd.reconstruct(CURRENT_LIST, mods)
    assert out["Kerala"]["count"] == 3        # 2 now, +1 restored, rename 0
    assert out["Assam"]["count"] == 0
    assert out["Sikkim"]["count"] == 2
    # reversed latest first
    assert [e["row"] for e in log] == [3, 2, 1]


def test_row_without_date_or_type_makes_state_not_reconstructable():
    mods = [_mod(5, "3", "Goa")]
    out, log = lgd.reconstruct(CURRENT_LIST, mods)
    assert out["Goa"]["reconstructable"] == "no"
    assert out["Goa"]["count"] is None
    assert "no effective or modification date" in out["Goa"]["reason"]
    assert out["Kerala"]["reconstructable"] == "yes"
    assert log[0]["action"].startswith("not reversible")


def test_row_with_date_but_no_type_is_not_reversible():
    mods = [_mod(5, "3", "Goa", eff="2025-05-05")]
    out, _ = lgd.reconstruct(CURRENT_LIST, mods)
    assert out["Goa"]["reconstructable"] == "no"
    assert "type" in out["Goa"]["reason"]


def test_unmappable_state_halts():
    with pytest.raises(KeyError):
        lgd.reconstruct(_cur(("Atlantis", "1", "X")), [])


def test_spreadsheetml_and_xlsx_readers(tmp_path):
    xml = """<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Report"><ss:Table>
<Row><Cell ss:Index="1"><Data ss:Type="String">Head</Data></Cell></Row>
<Row><Cell ss:Index="1"><Data ss:Type="String">District Code</Data></Cell>
<Cell ss:Index="2"><Data ss:Type="String">District Name(In English)</Data></Cell>
<Cell ss:Index="3"><Data ss:Type="String">State Code</Data></Cell>
<Cell ss:Index="4"><Data ss:Type="String">State Name (In English)</Data></Cell></Row>
<Row><Cell ss:Index="1"><Data ss:Type="Number">3</Data></Cell>
<Cell ss:Index="2"><Data ss:Type="String">New Goa</Data></Cell>
<Cell ss:Index="4"><Data ss:Type="String">Goa</Data></Cell></Row>
</ss:Table></Worksheet></Workbook>"""
    p = tmp_path / "m.xls"
    p.write_text(xml, encoding="utf-8")
    rows = lgd.read_spreadsheetml_rows(p)
    assert rows[2] == ["3", "New Goa", "", "Goa"]
    fields, mods = lgd.parse_modifications(rows)
    assert mods[0]["district_code"] == "3" and mods[0]["state_label"] == "Goa"
    assert mods[0]["effective_date"] == "" and mods[0]["type"] == ""
    assert not any("effective" in f.lower() for f in fields)

    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>All Districts</t></is></c></row>'
             '<row r="2"><c r="A2" t="inlineStr"><is><t>S.No.</t></is></c>'
             '<c r="C2" t="inlineStr"><is><t>State Name (In English)</t></is></c>'
             '<c r="D2" t="inlineStr"><is><t>District Code</t></is></c>'
             '<c r="E2" t="inlineStr"><is><t>District Name(In English)</t></is></c></row>'
             '<row r="3"><c r="A3" t="n"><v>1.0</v></c>'
             '<c r="C3" t="inlineStr"><is><t>Goa</t></is></c><c r="D3" t="n"><v>552.0</v></c>'
             '<c r="E3" t="inlineStr"><is><t>South Goa</t></is></c></row></sheetData></worksheet>')
    x = tmp_path / "c.xlsx"
    with zipfile.ZipFile(x, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    rows = lgd.read_xlsx_rows(x)
    assert rows[2][:5] == ["1", "", "Goa", "552", "South Goa"]
    cur = lgd.parse_current(rows)
    assert cur == [{"state_label": "Goa", "district_code": "552",
                    "district_name": "South Goa"}]


def test_date_parsing():
    assert lgd.parse_date("07/12/2024") == date(2024, 12, 7)
    assert lgd.parse_date("2025-01-10") == date(2025, 1, 10)
    assert lgd.parse_date("2025-01-10T00:00:00.000") == date(2025, 1, 10)
    assert lgd.parse_date("") is None


needs_lgd = pytest.mark.skipif(not (CURRENT.exists() and MODS.exists()),
                               reason="data_raw absent")


@needs_lgd
def test_real_lgd_files_parse():
    cur = lgd.parse_current(lgd.read_xlsx_rows(CURRENT))
    assert len(cur) > 700
    fields, mods = lgd.parse_modifications(lgd.read_spreadsheetml_rows(MODS))
    assert mods and all(m["district_code"] for m in mods)
