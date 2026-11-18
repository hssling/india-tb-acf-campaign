"""Rules of analysis plan §6.1 (qualifier), §7.1 (window label) and §7.2
(definition class, scope) as applied to figure-inventory rows."""
import pytest

from src import inventory_rules as R


@pytest.mark.parametrize("context, printed, expected", [
    ("over 20 crore vulnerable population is screened", "20 crore", "at_least"),
    ("more than 28 lakh TB patients", "28 lakh", "at_least"),
    ("the detection of over 7.19 lakh TB cases", "7.19 lakh", "at_least"),
    ("1.62+ Lakh screened", "1.62+ Lakh", "at_least"),
    ("25+ crore people", "25+ crore", "at_least"),
    ("25 crore+ people", "25 crore+", "at_least"),
    ("3+2 cases", "3", "exact"),
    ("3 + 2 cases", "3", "exact"),
    ("3+ 2 cases", "3", "exact"),
    ("up to 5 lakh", "5 lakh", "at_most"),
    ("nearly 9 crore", "9 crore", "about"),
    ("around 4.14 lakh inmates", "4.14 lakh", "about"),
    ("~ 100 X-rays", "100", "about"),
    ("~100 X-rays", "100", "about"),
    ("cases identified during these rounds exceeded 2.85 lakh", "2.85 lakh", "exact"),
    ("screening of 12.97 crore vulnerable individuals", "12.97 crore", "exact"),
    (">58,000 activities", "58,000", "exact"),
    ("around 1,650 HIV positive cases, 1,802 TB cases", "1,802", "exact"),
])
def test_qualifier(context, printed, expected):
    assert R.qualifier(context, printed) == expected


def test_qualifier_needs_figure_in_context():
    with pytest.raises(ValueError):
        R.qualifier("no such figure here", "347")


@pytest.mark.parametrize("quantity, definition, expected", [
    ("screened", "screened by chest X-ray", "screened by chest X-ray"),
    ("screened", "radiographic screening", "screened by chest X-ray"),
    ("screened", "symptomatic screening", "symptom-screened"),
    ("screened", "inmates were reached out", "population reached"),
    ("screened", "screening of vulnerable individuals", "unspecified"),
    ("tested", "NAAT tests", "tests done"),
    ("tested", "investigations of contacts", "unspecified"),
    ("tested", "investigations", "tests done"),
    ("tested", "presumptive cases tested", "people tested"),
    ("tested", "number of tested", "unspecified"),
    ("tested", "X-rays", "unspecified"),
    ("tb_cases", "TB cases notified", "notified"),
    ("tb_cases", "detection of TB cases", "diagnosed"),
    ("tb_cases", "TB patients diagnosed", "diagnosed"),
    ("tb_cases", "TB cases reported", "unspecified"),
    ("districts_selected", "districts", ""),
])
def test_definition_class(quantity, definition, expected):
    assert R.definition_class(quantity, definition)[0] == expected


@pytest.mark.parametrize("context, expected, flagged", [
    ("100-Day Campaign Outcome", "phase 1", False),
    ("347 districts across 33 States/UTs", "phase 1", False),
    ("selected 347.", "phase 1", False),
    ("1,347 districts", "unspecified", False),
    ("2.347 crore", "unspecified", False),
    ("3470 districts", "unspecified", False),
    ("347,000 people", "unspecified", False),
    ("expanded to all districts", "expanded campaign", False),
    ("phase ii of the Abhiyaan", "expanded campaign", False),
    ("Phase I/II of the campaign", "phase 1", True),
    ("phase 1 and 2", "phase 1", True),
    ("100 days campaign expanded nationwide", "phase 1", True),
    ("TB Mukt Bharat Abhiyaan progress", "unspecified", False),
    ("6. Active Case Finding: additional cases", "programme-wide", False),
    ("ACF yield", "programme-wide", False),
    ("TB notifications in 2023", "unspecified", False),
])
def test_scope(context, expected, flagged):
    scope, keyword, note = R.scope(context)
    assert scope == expected
    assert bool(note) == flagged


def test_scope_phase_12_is_not_combined():
    assert R.COMBINED_PHASE.search("phase 12") is None
    for s in ("Phase I/II", "phase 1 and 2", "Phase-I & II", "phase 1-2"):
        assert R.COMBINED_PHASE.search(s), s


@pytest.mark.parametrize("context, period, has_end, expected", [
    ("100-Day Campaign Outcome", "", True, "100-day campaign"),
    ("Under TB Mukt Bharat Abhiyaan, since 7th December 2024", "", False,
     "campaign to date"),
    ("Under TB Mukt Bharat Abhiyaan, since 7th December 2024", "", True, ""),
    ("Indicators 2024 (Jan-Oct)", "2024 (Jan-Oct)", True, "2024 (jan oct)"),
    ("over  the past   6 years", "past   6 years", False, "past 6 years"),
    ("TB Notification", "", False, ""),
])
def test_window_label(context, period, has_end, expected):
    assert R.window_label(context, period, has_end) == expected


@pytest.mark.parametrize("printed, value", [
    ("9.02 crore", "90200000"),
    ("22.42 Cr", "224200000"),
    ("1.62+ Lakh", "162000"),
    ("1,58,266", "158266"),
    ("2,00,000", "200000"),
    ("347", "347"),
    ("90%", "90"),
    ("88.3%", "88.3"),
    ("12–16%", ""),
])
def test_value(printed, value):
    assert R.value_of(printed) == value


def test_qualifier_second_occurrence():
    ctx = "At least 90% screening by X-Ray and 90% testing by NAAT"
    assert R.qualifier(ctx, "90%", 1) == "at_least"
    assert R.qualifier(ctx, "90%", 2) == "exact"


def test_figure_not_matched_inside_longer_number():
    assert R.find_figure("1,347 and 347", "347") == 10
