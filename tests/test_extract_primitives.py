# Copied from hssling/india-state-tb-score (MIT), tests/test_extract_primitives.py, commit 05bcaa7;
# modified: PDF-dependent tests dropped; coarsen and parse_magnitude tests added.
import pytest

from src import states
from src.extract import cells

DNHDD = "Dadra and Nagar Haveli and Daman and Diu"
JKL = "Jammu and Kashmir (incl. Ladakh)"


def test_canonical_rejects_unknown():
    with pytest.raises(KeyError):
        states.canonical("Atlantis")


def test_canonical_rejects_national_rows():
    for n in ("India", "Total", "Grand Total"):
        with pytest.raises(KeyError):
            states.canonical(n)


def test_canonical_aliases_and_case():
    assert states.canonical("jammu  &  KASHMIR") == "Jammu and Kashmir"
    assert states.canonical("Orissa") == "Odisha"
    assert states.canonical("NCT of Delhi") == "Delhi"
    assert states.canonical("DNH and DD") == DNHDD
    assert states.canonical("Andaman & Nicobar Islands") == "Andaman and Nicobar Islands"


def test_all_has_36_in_table_order():
    assert len(states.ALL) == 36 and len(set(states.ALL)) == 36
    assert list(states.ALL) == sorted(states.ALL)
    assert all("&" not in s for s in states.ALL)


def test_coarsen_units():
    assert states.coarsen("Ladakh") == JKL
    assert states.coarsen("Jammu and Kashmir") == JKL
    assert states.coarsen("Jammu & Kashmir") == JKL
    assert states.coarsen("Dadra and Nagar Haveli") == DNHDD
    assert states.coarsen("Daman and Diu") == DNHDD
    assert states.coarsen("DNH and DD") == DNHDD
    assert states.coarsen(DNHDD) == DNHDD
    assert states.coarsen("Kerala") == "Kerala"
    with pytest.raises(KeyError):
        states.coarsen("Atlantis")
    # Every year's units collapse to the same 35 coarse units.
    assert {states.coarsen(s) for s in states.ALL} == {
        states.coarsen(s) for s in states.units(2019)}
    assert len({states.coarsen(s) for s in states.ALL}) == 35


def test_join_requires_all_units():
    names = [s for s in states.ALL if s != "Ladakh"]
    with pytest.raises(ValueError, match="Ladakh"):
        states.require_all(names, 2023)
    states.require_all(states.ALL, 2023)


def test_require_all_pre_2020():
    names = [s for s in states.ALL if s not in ("Ladakh", DNHDD)]
    names += ["Dadra and Nagar Haveli", "Daman and Diu"]
    states.require_all(names, 2019)
    with pytest.raises(ValueError, match="Ladakh"):
        states.require_all(names, 2021)
    with pytest.raises(ValueError, match="extra"):
        states.require_all(list(states.ALL), 2019)


def test_parse_cells():
    assert cells.parse_int("1,23,456") == 123456
    assert cells.parse_int(" 1,234,567 ") == 1234567
    assert cells.parse_int("*89") == 89 and cells.parse_int("89*") == 89
    assert cells.parse_n_pct("62795 (99%)") == (62795, 99.0)
    assert cells.parse_n_pct("62795(99%)") == (62795, 99.0)
    assert cells.parse_n_pct("1,23,456 (99.5%)") == (123456, 99.5)


@pytest.mark.parametrize("bad", ["", "  ", "-", "NA", "abc", "12 ab"])
def test_parse_int_rejects_blank_and_text(bad):
    with pytest.raises(ValueError):
        cells.parse_int(bad)


def test_parse_count_accepts_integral_floats():
    assert cells.parse_count("63.0") == 63
    assert cells.parse_count("1,234.0") == 1234
    assert cells.parse_count("311961.00") == 311961
    assert cells.parse_count("4607") == 4607
    assert cells.parse_count("1,23,456") == 123456


@pytest.mark.parametrize("bad", ["63.5", "0.3", "", "-", "NA", "abc", "1.2.0"])
def test_parse_count_rejects_non_integral_and_blank(bad):
    with pytest.raises(ValueError):
        cells.parse_count(bad)


def test_parse_int_stays_strict_on_floats():
    with pytest.raises(ValueError):
        cells.parse_int("63.0")


def test_parse_indian_magnitudes():
    assert cells.parse_magnitude("9.02 crore") == 90_200_000
    assert cells.parse_magnitude("3.01 lakh") == 301_000
    assert cells.parse_magnitude("12.97 Crore") == 129_700_000
    assert cells.parse_magnitude(" 12.5 LAKH ") == 1_250_000
    assert cells.parse_magnitude("1,234 lakh") == 123_400_000
    assert cells.parse_magnitude("5 crore") == 50_000_000


@pytest.mark.parametrize("bad", ["", "9.02", "crore", "9.02 million", "1.234567 lakh", "abc lakh"])
def test_parse_magnitude_rejects(bad):
    with pytest.raises(ValueError):
        cells.parse_magnitude(bad)


def test_leading_state_accepts_spreadsheet_error_cells():
    assert states.leading_state("Lakshadweep #N/A #N/A #N/A") == (
        "Lakshadweep", "#N/A #N/A #N/A")
    assert states.leading_state("Arunachal Pradesh 139 (89%) #DIV/0! 139 (89%)") == (
        "Arunachal Pradesh", "139 (89%) #DIV/0! 139 (89%)")
