"""Campaign documents: the phase-1 exposure table (analysis plan §9.2) and the
campaign and press figures for the figure inventory (§5).

Exposure: CTD, *100 Days Campaign*, PDF page 7, table "State | Total District" in two
column blocks (33 State/UT rows and TOTAL), with checks E1-E7. An unmappable State
label halts extraction (no mapping is invented).

Inventory: the figures of the §5.1 quantities in the official campaign and press
documents of data_raw/official/ (other than the India TB Reports). Each figure was
located by reading the document; the specification below records where. The code
then derives value, qualifier (§6.1), definition class and scope (§7.2) and window
label (§7.1) by the plan's rules, and checks every quoted context and figure against
the PDF text of its page (or records that it was read from the page image, where the
page has no usable text layer).

Run: python -I src/extract/campaign.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import re
from dataclasses import dataclass, field

from src import inventory_rules as R
from src import states
from src.extract import labels
from src.extract.cells import parse_int
from src.extract.pdftext import page_lines

ROOT = Path(__file__).resolve().parents[2]
OFF = "data_raw/official/"
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"

CTD_FILE = OFF + "100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf"
CTD_PAGE = 7          # PDF page of the exposure table (printed page 5)
CRITERIA_PAGE = 6     # selection-criteria table (E6)

# document key -> (file, pub_date, remark on the date)
SOURCES: dict[str, tuple[str, str, str]] = {
    "CTD100": (CTD_FILE, "2024-12-05", "pub_date from the file name; no date printed"),
    "TMBA26": (OFF + "TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf", "",
               "no date printed in the document"),
    "GUIDE": (OFF + "Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf", "",
              "no date printed in the document"),
    "PIBSYN": (OFF + "doc2024127466601.pdf", "2024-12-07",
               "pub_date from the file name; no date printed"),
    "PIBBG": (OFF + "doc2024126465901.pdf", "2024-12-06", ""),
    "PIB26": (OFF + "doc2026324833001.pdf", "2026-03-24", ""),
    "PIBYER": (OFF + "doc20241228477601.pdf", "2024-12-28",
               "pub_date from the file name; no date printed"),
    "KERALA": (OFF + "TB_Elimination_Campaign.pdf", "2024-12-06",
               "pub_date of the covering letter (PDF page 1)"),
}
OWN_FILES = frozenset(f for f, _, _ in SOURCES.values())

INVENTORY_COLUMNS = [
    "fig_id", "quantity", "value", "value_printed", "qualifier", "unit",
    "definition_verbatim", "context_verbatim", "definition_class", "scope",
    "series_type", "window_label", "window_start", "window_end", "as_on",
    "as_on_basis", "geography", "source_file", "source_url", "page_or_para",
    "table_id", "pub_date", "note"]

SEP = " … "   # joins the pieces of a quoted context (heading or lead-in, then sentence)


# =================================================================== exposure table

_PAIR = re.compile(r"([^\d]+?)\s+(\d+)(?=\s|$)")


def parse_exposure_lines(lines: list[str]) -> tuple[list[tuple[str, int]], int | None]:
    """Rows (label, count) of the two-block table, left block first, and the TOTAL
    (None if no TOTAL row is printed)."""
    start = next(i for i, ln in enumerate(lines)
                 if re.fullmatch(r"State Total District State Total District", ln.strip()))
    left: list[tuple[str, int]] = []
    right: list[tuple[str, int]] = []
    total = None
    for ln in lines[start + 1:]:
        pairs = [(m.group(1).strip(), int(m.group(2))) for m in _PAIR.finditer(ln.strip())]
        if not pairs:
            break
        for k, (label, n) in enumerate(pairs):
            if label.upper() == "TOTAL":
                total = n
            else:
                (left if k == 0 else right).append((label, n))
        if total is not None:
            break
    return left + right, total


def read_exposure_table(pdf: Path, page: int = CTD_PAGE):
    return parse_exposure_lines(page_lines(pdf, page))


def map_rows(rows: list[tuple[str, int]]) -> list[tuple[str, str, int]]:
    """(label, canonical, count); UnmappedLabel halts on any unmappable label."""
    return [(lab, labels.resolve(lab).canonical, n) for lab, n in rows]


@dataclass
class ExposureResult:
    checks: list[dict]
    units: list[dict]
    rejected: bool
    reject_reasons: list[str] = field(default_factory=list)


def _fmt(x: float) -> str:
    return f"{x:.6f}".rstrip("0").rstrip(".")


def _yn(ok: bool) -> str:
    return "yes" if ok else "no"


def check_exposure(rows: list[tuple[str, str, int]], total: int | None,
                   lgd: dict[str, int | None], e6_number: int | None = None,
                   e7: tuple[int | None, int | None] = (None, None)) -> ExposureResult:
    """Checks E1-E7 of §9.2 and the exposure share of §9.3, per coarsened unit.

    rows: (label, canonical, count); lgd: coarse unit -> reconstructed LGD count at
    7 December 2024 (None where not computable)."""
    checks: list[dict] = []
    s = sum(c for _, _, c in rows)

    def add(check, inputs, expected, observed, ok, note=""):
        checks.append({"check": check, "inputs": inputs, "expected": expected,
                       "observed": observed, "pass": ok, "note": note})

    e1 = total == 347
    add("E1", "TOTAL row", "347", "" if total is None else str(total), _yn(e1),
        "" if total is not None else "no TOTAL row printed")
    e2 = total is not None and s == total
    add("E2", "sum of State/UT rows; TOTAL row", "" if total is None else str(total),
        str(s), _yn(e2))
    add("E3", "State/UT rows mapped by the label rule", "33 rows, each mapped",
        f"{len(rows)} rows, {len(rows)} mapped", _yn(len(rows) == 33),
        "an unmappable label halts extraction; step-2 resolutions are logged")

    by_unit: dict[str, int] = {}
    for _, canon, c in rows:
        u = states.coarsen(canon)
        by_unit[u] = by_unit.get(u, 0) + c
    units = []
    for u in sorted({states.coarsen(x) for x in states.ALL}):
        c = by_unit.get(u, 0)
        L = lgd.get(u)
        rec = {"unit": u, "in_table": _yn(u in by_unit), "campaign_count": c,
               "lgd_count": "" if L is None else L, "share": "", "capped": "",
               "flagged_e5": "", "computable": "yes", "reason": ""}
        if L is None or L <= 0:
            rec["computable"] = "no"
            rec["reason"] = ("LGD district count at 7 December 2024 not computable "
                             "(analysis plan §9.3)")
        else:
            share = min(1.0, c / L)
            rec["share"] = "1" if share == 1.0 else _fmt(share)
            rec["capped"] = _yn(share == 1.0)
            rec["flagged_e5"] = _yn(c > L)
            if c > L:
                rec["reason"] = "campaign count above LGD count: flagged and capped (E5)"
            elif share == 1.0:
                rec["reason"] = "every district in the campaign: capped"
        units.append(rec)

    evaluable = [u for u in units if u["computable"] == "yes"]
    below_in_table = [u for u in evaluable
                      if u["in_table"] == "yes" and u["campaign_count"] < u["lgd_count"]]
    below_all = [u for u in evaluable if u["campaign_count"] < u["lgd_count"]]
    e4 = len(below_in_table) >= 5
    add("E4", "units in the table with a computable LGD count",
        "at least 5 with campaign count below LGD count",
        f"{len(below_in_table)} of {sum(1 for u in evaluable if u['in_table'] == 'yes')}",
        _yn(e4),
        f"counting also the units absent from the table (campaign count 0): "
        f"{len(below_all)}; units whose LGD count is not computable are not evaluated: "
        f"{len(units) - len(evaluable)}")
    flagged = [u["unit"] for u in units if u["flagged_e5"] == "yes"]
    e5 = len(flagged) <= 3
    add("E5", "units with a computable LGD count", "at most 3 flagged",
        f"{len(flagged)} flagged", _yn(e5),
        ("flagged: " + "; ".join(flagged)) if flagged else "none flagged")
    if e6_number is None:
        add("E6", "criteria table (PDF page 6) and the text with it",
            "347 if a number selected is printed", "no number printed", "n/a",
            "report only")
    else:
        add("E6", "criteria table (PDF page 6) and the text with it", "347",
            str(e6_number), _yn(e6_number == 347),
            "report only; per-criterion counts are entered in the inventory, not tested")
    d, n = e7
    add("E7", "sentence with the table", f"347 districts; {len(rows)} States/UTs",
        f"{d} districts; {n} States/UTs" if d is not None else "no sentence found",
        _yn(d == 347 and n == len(rows)), "report only")

    reasons = []
    if not e1:
        reasons.append("E1 failed")
    if not e2:
        reasons.append("E2 failed")
    if not e4:
        reasons.append("E4 failed")
    if not e5:
        reasons.append("more than 3 States flagged under E5")
    return ExposureResult(checks, units, bool(reasons), reasons)


# =================================================================== inventory specs

@dataclass
class Spec:
    doc: str
    page: int
    quantity: str
    printed: str
    unit: str
    definition: str
    context: str
    occurrence: int = 1
    period: str = ""
    series: str = ""
    wstart: str = ""
    wend: str = ""
    as_on: str = ""
    geography: str = "India"
    table_id: str = ""
    para: str = ""
    note: str = ""
    image: bool = False            # read from the page image (no usable text layer)
    verify_pages: tuple[int, ...] = ()
    pub_date: str | None = None    # overrides the document's date for this page


def _campaign_window(**kw):
    return dict(wstart="2024-12-07", wend="2025-03-24", series="period", **kw)


# --- per-State tables (rows generated from the parsed table) -----------------------

def _district_table_specs(doc: str, page: int, lead: str, lines: list[str],
                          para: str) -> list[Spec]:
    rows, total = parse_exposure_lines(lines)
    out = []
    head = "State | Total District"
    for label, n in rows + [("TOTAL", total)]:
        geo = "India" if label == "TOTAL" else labels.resolve(label).canonical
        out.append(Spec(doc, page, "districts_selected", str(n), "districts",
                        "Total District", lead + SEP + head + SEP + f"{label} | {n}",
                        geography=geo, table_id=head, para=para,
                        note="" if label == "TOTAL" or labels.resolve(label).step == 1
                        else f"State label printed as '{label}'; mapped by step 2 of the "
                             "label rule (§9.2)"))
    return out


def _village_table_specs(lines: list[str]) -> list[Spec]:
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("States and UT No. of High Risk Villages and Wards"))
    head = "States and UT | No. of High Risk Villages and Wards"
    lead = "Annexure IV : High Risk Villages and Wards - State-wise"
    out = []
    for ln in lines[start + 1:]:
        m = re.fullmatch(r"(.+?) (\d[\d,]*)", ln.strip())
        if not m:
            break
        label, printed = m.group(1), m.group(2)
        geo = "India" if label == "Total" else labels.resolve(label).canonical
        out.append(Spec("TMBA26", 59, "other:high_risk_villages_wards", printed, "",
                        "No. of High Risk Villages and Wards",
                        lead + SEP + head + SEP + f"{label} | {printed}",
                        geography=geo, table_id=lead, para="Annexure IV",
                        note="unit (villages and wards) not in the §5.2 unit vocabulary"))
        if label == "Total":
            break
    return out


def _criteria_specs(doc: str, page: int, lead: str, para: str, amp: str) -> list[Spec]:
    head = "Sr. No. | Criteria* | Number of districts"
    crit = [("1", f"Death rate >=3.6% {amp} presumptive TB examination rate (testing "
                  "rate) <1700/lakh population", "195"),
            ("2", f"Death rate >=3.6% {amp} presumptive TB examination rate (testing "
                  "rate) >=1700", "119"),
            ("3", "Incidence rate >=200/lakh population", "21"),
            ("4", "TB Prevalence > 400/lakh population", "12")]
    return [Spec(doc, page, "other:districts_by_selection_criterion", n, "districts",
                 f"Number of districts: {c}", lead + SEP + head + SEP + f"{k} | {c} | {n}",
                 table_id=head, para=para,
                 note="per-criterion count; criteria may overlap (§9.2, E6)")
            for k, c, n in crit]


def _selection_sentence_specs(doc: str, page: int, sentence: str, para: str) -> list[Spec]:
    return [
        Spec(doc, page, "districts_selected", "347", "districts", "districts have been "
             "selected" if "have been" in sentence else "districts were selected",
             sentence, para=para),
        Spec(doc, page, "other:states_uts_selected", "33", "", "State/UTs", sentence,
             para=para, note="unit (States/UTs) not in the §5.2 unit vocabulary"),
        Spec(doc, page, "other:tribal_districts_selected", "38", "districts",
             "tribal districts", sentence, para=para),
        Spec(doc, page, "other:mining_districts_selected", "27", "districts",
             "mining districts", sentence, para=para),
        Spec(doc, page, "other:aspirational_districts_selected", "46", "districts",
             "aspirational districts", sentence, para=para),
    ]


def _states_spec(doc, page, context, para="", **kw) -> Spec:
    return Spec(doc, page, "other:states_uts_selected", "33", "", "States/UTs", context,
                para=para, note="unit (States/UTs) not in the §5.2 unit vocabulary", **kw)


# --- fixed specs, document by document -----------------------------------------------

def _fixed_specs() -> list[Spec]:
    S: list[Spec] = []

    # ---------------- CTD, 100 Days Campaign -------------------------------------------
    S += _criteria_specs("CTD100", 6, "Geographical prioritization" + SEP +
                         "To identify high focus districts, the following criteria has "
                         "been adopted:", "Geographical prioritization, criteria table",
                         "&")
    ctd_sentence = ("Following this process, 347 districts have been selected across 33 "
                    "State/UTs. These districts include 38 tribal districts, 27 mining "
                    "districts, and 46 aspirational districts among others.")
    S += _selection_sentence_specs("CTD100", 7, ctd_sentence,
                                   "Geographical prioritization, sentence before the table")
    tl = ("Timelines | Activities" + SEP + "Launch of Campaign – 7th December" + SEP +
          "7 December 2024 | Launch of campaign in all State/UTs & 347 Districts")
    S.append(Spec("CTD100", 9, "districts_selected", "347", "districts", "Districts", tl,
                  table_id="Timelines | Activities", para="timelines table"))
    out_lead = ("Expected outputs" + SEP + "The campaign will impact positively towards "
                "the overall goal of reducing mortality and morbidity")
    eo = "Expected outputs, item {}"
    S += [
        Spec("CTD100", 9, "other:target_additional_tb_cases", "2 lakh", "cases",
             "Detect additional 2 lakh cases",
             out_lead + SEP + "1. Detect additional 2 lakh cases", para=eo.format(1),
             note="campaign target"),
        Spec("CTD100", 9, "other:target_xray_screening_line_listed", "90%", "percent",
             "screening by X-Ray of line-listed vulnerable individuals",
             out_lead + SEP + "2. At least 90% screening by X-Ray of line-listed "
             "vulnerable individuals and 90% testing by NAAT", para=eo.format(2),
             note="campaign target"),
        Spec("CTD100", 9, "other:target_naat_testing", "90%", "percent", "testing by NAAT",
             out_lead + SEP + "2. At least 90% screening by X-Ray of line-listed "
             "vulnerable individuals and 90% testing by NAAT", occurrence=2,
             para=eo.format(2), note="campaign target"),
        Spec("CTD100", 9, "other:upfront_naat_share_existing", "30%", "percent",
             "upfront NAAT for diagnosis of TB/MDR-TB ... existing",
             out_lead + SEP + "3. Increase upfront NAAT for diagnosis of TB/MDR-TB from "
             "existing 30% to 70% testing of patients with presumptive TB.",
             para=eo.format(3), note="baseline stated with a campaign target"),
        Spec("CTD100", 9, "other:target_upfront_naat_share", "70%", "percent",
             "upfront NAAT ... testing of patients with presumptive TB",
             out_lead + SEP + "3. Increase upfront NAAT for diagnosis of TB/MDR-TB from "
             "existing 30% to 70% testing of patients with presumptive TB.",
             para=eo.format(3), note="campaign target"),
        Spec("CTD100", 9, "other:target_npy_nikshay_mitra_coverage", "100%", "percent",
             "coverage by Ni-kshay Poshan Yojana & Ni-kshay Mitra",
             out_lead + SEP + "4. 100% coverage by Ni-kshay Poshan Yojana & Ni-kshay Mitra.",
             para=eo.format(4), note="campaign target"),
        Spec("CTD100", 9, "other:target_panchayats_tb_free_certification", "50,000", "",
             "Panchayats prepared for TB free certification",
             out_lead + SEP + "5. 50,000 Panchayats prepared for TB free certification",
             para=eo.format(5), image=True,
             note="campaign target; item 5 is absent from the PDF text layer (lines with "
                  "the fi ligature are not encoded as text) and was read from the page "
                  "image; unit (Panchayats) not in the §5.2 unit vocabulary"),
    ]

    # ---------------- CTD, Guidance Document (2025) ---------------------------------
    S += _criteria_specs("GUIDE", 8, "100 Days Campaign-Geographical prioritization" + SEP
                         + "High focus districts were identified with the following "
                         "criteria:", "100 Days Campaign-Geographical prioritization, "
                         "criteria table", "and")
    g_sentence = ("Following this process, 347 districts were selected across 33 "
                  "State/UTs. These districts include 38 tribal districts, 27 mining "
                  "districts, and 46 aspirational districts among others.")
    S += _selection_sentence_specs("GUIDE", 8, g_sentence,
                                   "100 Days Campaign-Geographical prioritization, sentence")
    g_out = ("100-Day Campaign Outcome" + SEP + "The TB Mukt Bharat Abhiyaan was launched "
             "on 7th December 2024 and culminated on 24th March 2025 – the World TB Day. "
             "As part of the campaign, over 13.4 lakh Nikshay Shivirs were conducted "
             "nationwide, leading to the screening of 12.97 crore vulnerable individuals "
             "and the detection of over 7.19 lakh TB cases.")
    p10 = "100-Day Campaign Outcome"
    S += [
        Spec("GUIDE", 10, "other:nikshay_shivirs_conducted", "13.4 lakh", "",
             "Nikshay Shivirs were conducted", g_out, para=p10,
             note="unit (camps) not in the §5.2 unit vocabulary",
             **_campaign_window()),
        Spec("GUIDE", 10, "screened", "12.97 crore", "persons",
             "screening of 12.97 crore vulnerable individuals", g_out, para=p10,
             **_campaign_window()),
        Spec("GUIDE", 10, "tb_cases", "7.19 lakh", "cases",
             "detection of over 7.19 lakh TB cases", g_out, para=p10,
             **_campaign_window()),
        Spec("GUIDE", 10, "other:asymptomatic_tb_cases", "2.85 lakh", "cases",
             "asymptomatic individuals",
             "100-Day Campaign Outcome" + SEP + "This data includes 2.85 lakh asymptomatic "
             "individuals, underscoring the effectiveness of proactive community "
             "engagement and targeted screening.", para=p10, **_campaign_window()),
        Spec("GUIDE", 31, "other:asymptomatic_tb_cases", "2.85 lakh", "cases",
             "asymptomatic TB cases identified",
             "1.1.7. Screening asymptomatic TB was the mantra for the 100-day intensive TB "
             "case finding rounds. The total number of asymptomatic TB cases identified "
             "during these rounds exceeded 2.85 lakh, indicating that these cases could "
             "have continued to spread the infection in the community had they not been "
             "detected through the intensive screening strategy.",
             para="Annexure 1, para 1.1.7",
             note="'exceeded' is not a qualifier word of §6.1, so the qualifier is exact"),
    ]
    g48a = ("Operationalization of TB Mukt Bharat Abhiyaan" + SEP + "Through concerted "
            "efforts, the NTEP successfully screened 12.97 crore vulnerable individuals by "
            "organizing more than 13.46 lakh Ni-kshay Shivirs (screening camps) across "
            "States and Union Territories, during the 100-day intensive TB case finding "
            "campaign under the TB Mukt Bharat Abhiyaan.")
    g48b = g48a + SEP + ("This initiative enabled identification of 7.19 lakh TB cases, "
                         "including 2.85 lakh asymptomatic cases that might have otherwise "
                         "remained undiagnosed.")
    p48 = "Operationalization of TB Mukt Bharat Abhiyaan"
    S += [
        Spec("GUIDE", 48, "screened", "12.97 crore", "persons",
             "screened 12.97 crore vulnerable individuals", g48a, para=p48),
        Spec("GUIDE", 48, "other:nikshay_shivirs_conducted", "13.46 lakh", "",
             "Ni-kshay Shivirs (screening camps)", g48a, para=p48,
             note="unit (camps) not in the §5.2 unit vocabulary"),
        Spec("GUIDE", 48, "tb_cases", "7.19 lakh", "cases",
             "identification of 7.19 lakh TB cases", g48b, para=p48),
        Spec("GUIDE", 48, "other:asymptomatic_tb_cases", "2.85 lakh", "cases",
             "asymptomatic cases", g48b, para=p48),
        Spec("GUIDE", 48, "other:nikshay_mitras_registered", "1.05 lakh", "",
             "registration of 1.05 lakh new Ni-kshay Mitras",
             p48 + SEP + "Further, community engagement efforts led to registration of "
             "1.05 lakh new Ni-kshay Mitras who provided over 3 lakh nutrition food baskets "
             "to TB patients, ensuring comprehensive care and much needed nutritional "
             "support.", para=p48,
             note="Ni-kshay Mitras include organisations; unit left blank"),
        Spec("GUIDE", 48, "other:food_baskets_provided", "3 lakh", "",
             "nutrition food baskets",
             p48 + SEP + "Further, community engagement efforts led to registration of "
             "1.05 lakh new Ni-kshay Mitras who provided over 3 lakh nutrition food baskets "
             "to TB patients, ensuring comprehensive care and much needed nutritional "
             "support.", para=p48, note="unit (baskets) not in the §5.2 unit vocabulary"),
        Spec("GUIDE", 48, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "TB-free certification by 46,118 Gram Panchayats",
             p48 + SEP + "The achievement of TB-free certification by 46,118 Gram "
             "Panchayats also marks a significant milestone in our journey towards TB "
             "elimination.", para=p48,
             note="unit (Gram Panchayats) not in the §5.2 unit vocabulary"),
    ]

    # ---------------- CTD, TB Mukt Bharat Abhiyaan campaign document v6 (2026) ------------
    t3 = ("To accelerate the progress towards TB elimination, the Government launched a "
          "100 Days TB Mukt Bharat Abhiyaan on 7th December 2024 in 347 high priority "
          "districts across 33 States/UTs.")
    intro = "1. Introduction and Background"
    S += [Spec("TMBA26", 3, "districts_selected", "347", "districts",
               "high priority districts", t3, para=intro),
          _states_spec("TMBA26", 3, t3, para=intro)]
    jb = ("Jan Bhagidari as the central strategy also led to active involvement of over "
          "35,000 elected representatives (MPs/MLAs/MLCs/PRIs/ULBs), over 73,000 "
          "activities through PRIs, > 1 lakh activities with Youth, Schools & Colleges, "
          ">58,000 activities through 23-line ministries and community support through "
          "more than 5 lakh Ni-kshay Mitras including 2 lakh MY Bharat volunteers, "
          "exhibiting a ‘Whole-of-Society and ‘Whole-of-Government’ approach to TB "
          "elimination.")
    gt = "'>' printed before the figure; not a qualifier symbol of §6.1"
    S += [
        Spec("TMBA26", 3, "other:elected_representatives_involved", "35,000", "persons",
             "elected representatives (MPs/MLAs/MLCs/PRIs/ULBs)", jb, para=intro),
        Spec("TMBA26", 3, "other:jan_bhagidari_activities_pris", "73,000", "",
             "activities through PRIs", jb, para=intro,
             note="unit (activities) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 3, "other:jan_bhagidari_activities_youth", "1 lakh", "",
             "activities with Youth, Schools & Colleges", jb, para=intro,
             note=gt + "; unit (activities) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 3, "other:jan_bhagidari_activities_line_ministries", "58,000", "",
             "activities through 23-line ministries", jb, para=intro,
             note=gt + "; unit (activities) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 3, "other:line_ministries_involved", "23", "",
             "23-line ministries", jb, para=intro,
             note="unit (ministries) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 3, "other:nikshay_mitras_community_support", "5 lakh", "",
             "community support through more than 5 lakh Ni-kshay Mitras", jb, para=intro,
             note="Ni-kshay Mitras include organisations; unit left blank"),
        Spec("TMBA26", 3, "other:my_bharat_volunteers_nikshay_mitra", "2 lakh", "persons",
             "MY Bharat volunteers", jb, para=intro),
    ]
    prog = ("Progress made under TB Mukt Bharat Abhiyaan (07th December 2024 to 30th "
            "December 2025):")
    pw = dict(period="07th December 2024 to 30th December 2025", wstart="2024-12-07",
              wend="2025-12-30", series="period")
    b1 = "22.42 Cr vulnerable population identified with 12.46 crore line listed in Ni-kshay"
    b2 = "4.75 Cr X-rays by more than 6000 fixed facility & 510 hand-held X-rays"
    b3 = "1.56 Cr NAAT tests through more than 9,300 NAAT machines"
    lst = "list 'Progress made under TB Mukt Bharat Abhiyaan'"
    cr = "'Cr' read as crore"
    S += [
        Spec("TMBA26", 3, "population_targeted", "22.42 Cr", "persons",
             "vulnerable population identified", prog + SEP + b1, para=lst, note=cr, **pw),
        Spec("TMBA26", 3, "other:vulnerable_line_listed_nikshay", "12.46 crore",
             "persons", "line listed in Ni-kshay", prog + SEP + b1, para=lst, **pw),
        Spec("TMBA26", 3, "tested", "4.75 Cr", "tests", "X-rays", prog + SEP + b2,
             para=lst, note=cr, **pw),
        Spec("TMBA26", 3, "other:xray_fixed_facilities", "6000", "", "fixed facility",
             prog + SEP + b2, para=lst,
             note="unit (facilities) not in the §5.2 unit vocabulary", **pw),
        Spec("TMBA26", 3, "other:xray_handheld_units", "510", "", "hand-held X-rays",
             prog + SEP + b2, para=lst,
             note="unit (machines) not in the §5.2 unit vocabulary", **pw),
        Spec("TMBA26", 3, "tested", "1.56 Cr", "tests", "NAAT tests", prog + SEP + b3,
             para=lst, note=cr, **pw),
        Spec("TMBA26", 3, "other:naat_machines", "9,300", "", "NAAT machines",
             prog + SEP + b3, para=lst,
             note="unit (machines) not in the §5.2 unit vocabulary", **pw),
    ]
    b4 = ("27.28 lakh new TB cases identified of which, 9.48 lakh were asymptomatic TB "
          "cases")
    lst4 = "list 'Progress made under TB Mukt Bharat Abhiyaan' (headed on PDF page 3)"
    S += [
        Spec("TMBA26", 4, "tb_cases", "27.28 lakh", "cases", "new TB cases identified",
             prog + SEP + b4, para=lst4, verify_pages=(3, 4), **pw),
        Spec("TMBA26", 4, "other:asymptomatic_tb_cases", "9.48 lakh", "cases",
             "asymptomatic TB cases", prog + SEP + b4, para=lst4, verify_pages=(3, 4),
             **pw),
        Spec("TMBA26", 4, "other:treated_successfully", "23.99 lakh", "persons",
             "treated successfully", prog + SEP + "23.99 lakh treated successfully",
             para=lst4, verify_pages=(3, 4), **pw),
        Spec("TMBA26", 4, "other:assessed_differentiated_tb_care", "7.91 lakh", "persons",
             "TB patients assessed for Differentiated TB Care",
             prog + SEP + "7.91 lakh TB patients assessed for Differentiated TB Care",
             para=lst4, verify_pages=(3, 4), **pw),
        Spec("TMBA26", 4, "other:nikshay_mitras_registered", "5.17 lakh", "",
             "new Ni-kshay Mitras registered",
             prog + SEP + "5.17 lakh new Ni-kshay Mitras registered and 25.59 lakh poshan "
             "kits distributed.", para=lst4, verify_pages=(3, 4),
             note="Ni-kshay Mitras include organisations; unit left blank", **pw),
        Spec("TMBA26", 4, "other:poshan_kits_distributed", "25.59 lakh", "",
             "poshan kits distributed",
             prog + SEP + "5.17 lakh new Ni-kshay Mitras registered and 25.59 lakh poshan "
             "kits distributed.", para=lst4, verify_pages=(3, 4),
             note="unit (kits) not in the §5.2 unit vocabulary", **pw),
        Spec("TMBA26", 4, "other:my_bharat_volunteers_nikshay_mitra", "2 lakh", "persons",
             "MY Bharat Volunteers registered as Ni-kshay Mitra",
             prog + SEP + "More than 2 lakh MY Bharat Volunteers registered as Ni-kshay "
             "Mitra for providing psycho-social support to TB patients.", para=lst4,
             verify_pages=(3, 4), **pw),
        Spec("TMBA26", 4, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "Gram Panchayats have been awarded TB-free certification",
             "As a result of all-round targeted and collaborative efforts, over 46,118 Gram "
             "Panchayats have been awarded TB-free certification for the year 2024.",
             para="paragraph after the progress list", period="the year 2024",
             wstart="2024-01-01", wend="2024-12-31", series="period",
             note="unit (Gram Panchayats) not in the §5.2 unit vocabulary"),
    ]
    nxt = ("The TB Mukt Bharat Abhiyaan now is being re-inforced with another 100 Days "
           "Abhiyaan more targeted and focused based on the learnings, addressing the "
           "challenges with")
    S += [
        Spec("TMBA26", 4, "other:handheld_xray_introduction", "2,000", "",
             "AI enabled hand-held X-rays",
             nxt + SEP + "Introduction of more than 2,000 AI enabled hand-held X-rays with "
             "indigenously developed AI tool (DEEPCXR) for automated reading of X-ray "
             "images,", para="list of the further 100 Days Abhiyaan",
             note="context refers to a further 100 Days Abhiyaan; unit (machines) not in "
                  "the §5.2 unit vocabulary"),
        Spec("TMBA26", 4, "other:high_risk_villages_wards", "1.58 lakh", "",
             "high risk villages / wards identified",
             nxt + SEP + "1.58 lakh high risk villages / wards identified using AI based "
             "assessment of 30+ indicators", para="list of the further 100 Days Abhiyaan",
             note="context refers to a further 100 Days Abhiyaan; unit (villages and "
                  "wards) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 6, "other:high_risk_villages_wards", "1.58 lakh", "",
             "TB vulnerable villages and wards",
             "1. Target Population / Geography" + SEP + "i. TB Vulnerable Villages and "
             "Wards - Screening all individuals (above 14 years of age), irrespective of "
             "vulnerability, in the 1.58 lakh TB vulnerable villages and wards identified "
             "by an Vulnerability Mapping for TB (VMTB) AI tool based on 30+ region "
             "specific indicators", para="section 1, Target Population / Geography, a.i",
             note="unit (villages and wards) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 9, "other:high_risk_villages_wards", "1.58 lakh", "",
             "high risk villages & wards",
             "c. Route map to be prepared for all 1.58 lakh high risk villages & wards "
             "identified though AI (as per Annexure-1)",
             para="section 3, Ayushman Arogya Shivir, item c",
             note="unit (villages and wards) not in the §5.2 unit vocabulary"),
        Spec("TMBA26", 10, "other:high_risk_villages_wards", "1.58 lakh", "",
             "high risk villages & wards",
             "b. High Risk Villages & Wards - Screening all individuals in 1.58 lakh high "
             "risk villages & wards using hand-held X-rays following a pre-defined route "
             "map for Ayushman Arogya Shivir", para="item b, High Risk Villages & Wards",
             note="unit (villages and wards) not in the §5.2 unit vocabulary"),
    ]

    # ---------------- PIB synopsis (7 December 2024) ---------------------------------
    syn1 = ("the National TB Elimination Programme (NTEP), Ministry of Health and Family "
            "Welfare is launching a novel campaign, over the next 100 days, in 347 "
            "districts across the country.")
    syn2 = ("The 347 districts across 33 States/UTs have been selected based on indicators "
            "such as death rate, presumptive TB examination rate, and incidence rate as "
            "compared to the national average.")
    S += [Spec("PIBSYN", 2, "districts_selected", "347", "districts", "districts", syn1,
               para="opening panel"),
          Spec("PIBSYN", 2, "districts_selected", "347", "districts", "districts", syn2,
               para="panel on the stratified approach"),
          _states_spec("PIBSYN", 2, syn2, para="panel on the stratified approach")]

    # ---------------- PIB backgrounder (6 December 2024) -----------------------------
    bg = ("Spanning 347 districts across 33 states and union territories, the campaign "
          "represents a critical component of India’s strategy to eliminate TB and build a "
          "TB-free nation.")
    S += [Spec("PIBBG", 1, "districts_selected", "347", "districts", "districts", bg,
               para="para 1"),
          _states_spec("PIBBG", 1, bg, para="para 1")]

    # ---------------- PIB press note (24 March 2026) ---------------------------------
    kt = ("Key Takeaways" + SEP + "Under TB Mukt Bharat Abhiyaan, since 7th December 2024, "
          "over 20 crore vulnerable population is screened for TB, more than 28 lakh TB "
          "patients diagnosed.")
    since = dict(wstart="2024-12-07", series="cumulative")
    S += [
        Spec("PIB26", 1, "screened", "20 crore", "persons",
             "vulnerable population is screened for TB", kt, para="Key Takeaways",
             **since),
        Spec("PIB26", 1, "tb_cases", "28 lakh", "cases", "TB patients diagnosed", kt,
             para="Key Takeaways", **since),
        Spec("PIB26", 1, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "Gram Panchayats have been awarded TB-free certification",
             "Key Takeaways" + SEP + "Over 46,118 Gram Panchayats have been awarded "
             "TB-free certification for the year 2024.", para="Key Takeaways",
             period="the year 2024", wstart="2024-01-01", wend="2024-12-31",
             series="period",
             note="unit (Gram Panchayats) not in the §5.2 unit vocabulary"),
    ]
    p7h = "100-Day TB Mukt Bharat Abhiyaan"
    p7a = (p7h + SEP + "The Ministry of Health and Family Welfare launched one of India’s "
           "most intensive TB elimination drives called the 100-Day TB Mukt Bharat Abhiyan "
           "on 7th December 2024 in 347 high-priority districts across 33 States/UTs.")
    p7b = (p7h + SEP + "The Jan Andolan also led to active involvement of over 30,000 "
           "elected representatives and 24-line ministries and support of Ni-kshay Mitras "
           "exhibiting a whole-of-society and whole-of-government approach to TB "
           "elimination.")
    S += [
        Spec("PIB26", 7, "districts_selected", "347", "districts",
             "high-priority districts", p7a, para=p7h),
        _states_spec("PIB26", 7, p7a, para=p7h),
        Spec("PIB26", 7, "other:elected_representatives_involved", "30,000", "persons",
             "elected representatives", p7b, para=p7h),
        Spec("PIB26", 7, "other:line_ministries_involved", "24", "", "24-line ministries",
             p7b, para=p7h, note="unit (ministries) not in the §5.2 unit vocabulary"),
    ]
    p8 = ("Under TB Mukt Bharat Abhiyaan, since 7th December 2024, over 20 crore "
          "vulnerable population is screened for TB, more than 28 lakh TB patients are "
          "diagnosed including 9 lakh asymptomatic cases, which could have missed "
          "otherwise.")
    S += [
        Spec("PIB26", 8, "screened", "20 crore", "persons",
             "vulnerable population is screened for TB", p8, para=p7h, **since),
        Spec("PIB26", 8, "tb_cases", "28 lakh", "cases", "TB patients are diagnosed", p8,
             para=p7h, **since),
        Spec("PIB26", 8, "other:asymptomatic_tb_cases", "9 lakh", "cases",
             "asymptomatic cases", p8, para=p7h, **since),
        Spec("PIB26", 8, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "Gram Panchayats have been awarded TB-free certification",
             "As a result of all-round targeted and collaborative efforts, over 46,118 Gram "
             "Panchayats have been awarded TB-free certification for the year 2024.",
             para=p7h, period="the year 2024", wstart="2024-01-01", wend="2024-12-31",
             series="period",
             note="unit (Gram Panchayats) not in the §5.2 unit vocabulary"),
        Spec("PIB26", 8, "other:treatment_success_rate", "90%", "percent",
             "treatment success rate",
             "The treatment success rate under the TB Mukt Bharat Abhiyan has risen to 90%, "
             "surpassing the global average of 88%.", para=p7h),
    ]
    gz1 = ("In the isolated Gurez valley of Bandipora District, Kashmir—located 2,400 "
           "metres high in the Himalayas and cut off during winter—the NTEP Kashmir team "
           "conducted an intensive TB screening campaign.")
    gz2 = ("Using mobile testing vans equipped with advanced diagnostic machines and "
           "portable X-ray equipment, the team screened 1,250 people over three days and "
           "identified over 250 potential TB cases for further testing.")
    gzn = "sub-State figure (Gurez valley, Bandipora district)"
    S += [
        Spec("PIB26", 10, "screened", "1,250", "persons", "the team screened 1,250 people",
             gz1 + SEP + gz2, geography="Jammu and Kashmir",
             para="box 'Finding TB Cases in Remote Kashmir'", period="three days",
             series="period", note=gzn),
        Spec("PIB26", 10, "presumptive", "250", "persons",
             "potential TB cases for further testing", gz1 + SEP + gz2,
             geography="Jammu and Kashmir", para="box 'Finding TB Cases in Remote Kashmir'",
             period="three days", series="period", note=gzn),
    ]
    ai = ("AI-Led Initiatives" + SEP + "TB Screening | Cough Against TB (CATB) | 1.62+ Lakh "
          "screened; 12–16% extra yield in cases over conventional methods.")
    S += [
        Spec("PIB26", 11, "screened", "1.62+ Lakh", "persons", "screened", ai,
             table_id="AI-Led Initiatives", para="table 'AI-Led Initiatives', row TB Screening",
             note="Cough Against TB (AI tool); the source cites footnote 2 (PIB, PRID "
                  "2199422) for this row"),
        Spec("PIB26", 11, "other:extra_yield_over_conventional", "12–16%", "percent",
             "extra yield in cases over conventional methods", ai,
             table_id="AI-Led Initiatives", para="table 'AI-Led Initiatives', row TB Screening",
             note="printed as a range; value left blank; Cough Against TB (AI tool)"),
    ]

    # ---------------- PIB year-end review 2024 ---------------------------------------
    ye = ("TB Mukt Bharat – 100 Days Intensified Campaign: Government has launched a 100 "
          "Days Intensified Campaign for TB elimination on 7th December 2024." + SEP +
          "The campaign will cover 347 selected high priority districts across 33 "
          "States/UTs and will involve a comprehensive strategy to mobilise resources, "
          "raise awareness and intensify actions against TB across all prioritized "
          "districts.")
    S += [Spec("PIBYER", 6, "districts_selected", "347", "districts",
               "selected high priority districts", ye,
               para="section 3, 'TB Mukt Bharat – 100 Days Intensified Campaign'"),
          _states_spec("PIBYER", 6, ye,
                       para="section 3, 'TB Mukt Bharat – 100 Days Intensified Campaign'")]
    acf = ("6. Active Case Finding:" + SEP + "This activity has resulted in the diagnosis of "
           "an additional 3 lakh TB cases over past 6 years.")
    S.append(Spec("PIBYER", 8, "tb_cases", "3 lakh", "cases",
                  "diagnosis of an additional 3 lakh TB cases", acf,
                  para="section 3, item 6 'Active Case Finding'", period="past 6 years",
                  series="period"))
    tab = ("Achievements 2024" + SEP + "Indicators | 2024 (Jan-Oct)" + SEP +
           "Active Case Finding (Additional Cases diagnosed) | 50,620" + SEP +
           "*-Till Oct 2024")
    S.append(Spec("PIBYER", 9, "tb_cases", "50,620", "cases",
                  "Active Case Finding (Additional Cases diagnosed)", tab,
                  table_id="Achievements 2024", para="table 'Achievements 2024'",
                  period="2024 (Jan-Oct)", wstart="2024-01-01", wend="2024-10-31",
                  series="period", note="footnote '*-Till Oct 2024' printed under the "
                  "table"))
    ish = ("Integrated campaign for screening STI, HIV, TB and Hepatitis-B&C (ISHTH "
           "campaign) among inmates of prisons and other closed settings (P&OCS) was "
           "successfully concluded in March 2024." + SEP + "Through ISHTH campaign, around "
           "4.14 lakh inmates were reached out through 2290 P&OCS institutions.")
    ihc = ("IHC covered 73 districts in 12 states, and around 1,650 HIV positive cases, "
           "1,802 TB cases, 2,813 Hepatitis-C cases, 700 Hepatitis-B cases, and 641 "
           "syphilis cases have been identified through this Campaign.")
    multi = "integrated multi-disease campaign (STI, HIV, TB, hepatitis)"
    S += [
        Spec("PIBYER", 11, "screened", "4.14 lakh", "persons",
             "inmates were reached out", ish, para="section 4 (NACP), ISHTH campaign",
             note=multi + " among prison inmates"),
        Spec("PIBYER", 11, "other:ishth_institutions", "2290", "",
             "P&OCS institutions", ish, para="section 4 (NACP), ISHTH campaign",
             note=multi + "; unit (institutions) not in the §5.2 unit vocabulary"),
        Spec("PIBYER", 11, "tb_cases", "1,802", "cases",
             "TB cases ... have been identified", ihc,
             para="section 4 (NACP), Integrated Health Campaign", note=multi),
        Spec("PIBYER", 11, "other:ihc_districts", "73", "districts", "districts", ihc,
             para="section 4 (NACP), Integrated Health Campaign", note=multi),
        Spec("PIBYER", 11, "other:ihc_states", "12", "", "states", ihc,
             para="section 4 (NACP), Integrated Health Campaign",
             note=multi + "; unit (States) not in the §5.2 unit vocabulary"),
    ]

    # ---------------- Ministry letter with attachments (Kerala Medical Council copy) ----
    k1 = ("2. This campaign will cover 347 selected high priority districts across 33 "
          "state/UTs (copy enclosed) and the campaign plan along with guidelines are also "
          "enclosed.")
    k2 = ("2. This 100 days' intensified campaign will cover 347 selected high priority "
          "districts across 33 States/UTs (Annexure-I) and will involve a comprehensive "
          "strategy to mobilize resources, raise awareness and intensify actions against "
          "TB across all prioritized States/Districts.")
    img = ("read from the page image (the page has no usable text layer: page 1 text is "
           "not decodable, page 2 is a scanned image)")
    do = "D.O. letter Z-28015/191/2024-TB dated 21 November 2024, enclosed; " + img
    S += [
        Spec("KERALA", 1, "districts_selected", "347", "districts",
             "selected high priority districts", k1,
             para="Ministry of Ayush letter L-11012/2/2019-DCC, para 2", image=True,
             note=img),
        _states_spec("KERALA", 1, k1,
                     para="Ministry of Ayush letter L-11012/2/2019-DCC, para 2", image=True),
        Spec("KERALA", 2, "districts_selected", "347", "districts",
             "selected high priority districts", k2,
             para="MoHFW D.O. letter Z-28015/191/2024-TB, para 2", image=True,
             pub_date="2024-11-21", note=do),
        _states_spec("KERALA", 2, k2, para="MoHFW D.O. letter Z-28015/191/2024-TB, para 2",
                     image=True, pub_date="2024-11-21"),
    ]
    kc = ("Geographical Focus: The campaign targets 347 districts across 33 states/UTs, "
          "including high-burden of TB disease and mortality due to TB, tribal, mining, "
          "and aspirational districts.")
    cn = "Concept Note: 100 Days Campaign, section 4"
    S += [Spec("KERALA", 5, "districts_selected", "347", "districts", "districts", kc,
               para=cn),
          _states_spec("KERALA", 5, kc, para=cn)]
    keo = "5. Expected Outputs"
    ken = "Concept Note: 100 Days Campaign, section 5"
    S += [
        Spec("KERALA", 5, "other:target_additional_tb_cases", "2,00,000", "cases",
             "Identify 2,00,000 additional TB cases",
             keo + SEP + "Detection: Identify 2,00,000 additional TB cases.", para=ken,
             note="campaign target"),
        Spec("KERALA", 5, "other:target_xray_screening", "90%", "percent",
             "screening of vulnerable populations using X-rays with AI and NAAT",
             keo + SEP + "Coverage: Achieve 90% screening of vulnerable populations using "
             "X-rays with AI and NAAT.", para=ken, note="campaign target"),
        Spec("KERALA", 5, "other:target_nutrition_linkage", "100%", "percent",
             "linkage of TB patients to nutritional support",
             keo + SEP + "Support: Ensure 100% linkage of TB patients to nutritional "
             "support.", para=ken, note="campaign target"),
        Spec("KERALA", 5, "other:target_panchayats_tb_free_certification", "50,000", "",
             "panchayats for TB-free certification",
             keo + SEP + "Community Impact: Prepare 50,000 panchayats for TB-free "
             "certification.", para=ken,
             note="campaign target; unit (Panchayats) not in the §5.2 unit vocabulary"),
    ]
    return S


# =================================================================== building rows

def _manifest() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import read_manifest
    return {r["file"]: r for r in read_manifest()}


def verify_inputs() -> None:
    """SHA-256 of every input against data/source_manifest.csv; ValueError on mismatch."""
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import verify
    man = _manifest()
    for f in sorted(OWN_FILES):
        verify(ROOT / f, man[f]["sha256"])


def _norm(s: str) -> str:
    s = s.replace(" | ", " ").replace("’", "'").replace("‘", "'")
    s = re.sub(r"-\s+", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> list[str]:
    return re.findall(r"[\w%.,/&>+*'-]+", _norm(s))


def _page_text(file: str, pages: tuple[int, ...], cache: dict) -> str:
    out = []
    for p in pages:
        key = (file, p)
        if key not in cache:
            cache[key] = "\n".join(page_lines(ROOT / file, p))
        out.append(cache[key])
    return "\n".join(out)


def _verify(spec: Spec, file: str, cache: dict) -> str:
    if spec.image:
        return "page image"
    text = _norm(_page_text(file, spec.verify_pages or (spec.page,), cache))
    pieces = [p for p in spec.context.split(SEP) if p.strip()]
    if all(_norm(p) in text for p in pieces):
        return "text"
    if R.find_figure(text, _norm(spec.printed)) >= 0 and all(
            t.strip(".,;:") in text for p in pieces for t in _tokens(p)):
        return "text (loose)"
    raise ValueError(f"context not found on {file} page {spec.page}: {spec.context!r}")


def _row(spec: Spec, fig_id: str, man: dict) -> dict:
    file, pub, pub_note = SOURCES[spec.doc]
    q = spec.quantity
    qual = R.qualifier(spec.context, spec.printed, spec.occurrence)
    dcls, dkw = R.definition_class(q, spec.definition)
    scope, skw, snote = R.scope(spec.context)
    has_end = bool(spec.wend or spec.as_on)
    basis = "stated" if spec.as_on else ("window_end" if spec.wend else "bounded")
    notes = []
    if dcls:
        notes.append(f"definition_class keyword: '{dkw}'" if dkw
                     else "definition_class: no keyword matched")
    notes.append(f"scope keyword: '{skw}'" if skw else "scope: no keyword matched")
    if snote:
        notes.append(snote)
    if spec.note:
        notes.append(spec.note)
    if pub_note and spec.pub_date is None:
        notes.append(pub_note)
    page_or_para = f"PDF page {spec.page}" + (f"; {spec.para}" if spec.para else "")
    return {
        "fig_id": fig_id, "quantity": q, "value": R.value_of(spec.printed),
        "value_printed": spec.printed, "qualifier": qual, "unit": spec.unit,
        "definition_verbatim": spec.definition, "context_verbatim": spec.context,
        "definition_class": dcls, "scope": scope, "series_type": spec.series,
        "window_label": R.window_label(spec.context, spec.period, has_end),
        "window_start": spec.wstart, "window_end": spec.wend, "as_on": spec.as_on,
        "as_on_basis": basis, "geography": spec.geography, "source_file": file,
        "source_url": man[file]["url"], "page_or_para": page_or_para,
        "table_id": spec.table_id,
        "pub_date": spec.pub_date if spec.pub_date is not None else pub,
        "note": "; ".join(notes),
    }


def all_specs(cache: dict | None = None) -> list[Spec]:
    cache = {} if cache is None else cache
    S = _fixed_specs()
    ctd_lines = page_lines(ROOT / CTD_FILE, CTD_PAGE)
    S += _district_table_specs(
        "CTD100", CTD_PAGE, "Following this process, 347 districts have been selected "
        "across 33 State/UTs.", ctd_lines, "Geographical prioritization, table")
    g_file = SOURCES["GUIDE"][0]
    S += _district_table_specs(
        "GUIDE", 8, "Following this process, 347 districts were selected across 33 "
        "State/UTs.", page_lines(ROOT / g_file, 8),
        "100 Days Campaign-Geographical prioritization, table")
    S += _village_table_specs(page_lines(ROOT / SOURCES["TMBA26"][0], 59))
    order = list(SOURCES)
    return sorted(S, key=lambda s: (order.index(s.doc), s.page))


def build_inventory() -> tuple[list[dict], list[dict]]:
    """Inventory rows of the campaign documents and their provenance check."""
    man = _manifest()
    cache: dict = {}
    rows, prov = [], []
    seq: dict[tuple[str, int], int] = {}
    for spec in all_specs(cache):
        file = SOURCES[spec.doc][0]
        k = (spec.doc, spec.page)
        seq[k] = seq.get(k, 0) + 1
        fig_id = f"{spec.doc}-p{spec.page:03d}-{seq[k]:02d}"
        rows.append(_row(spec, fig_id, man))
        prov.append({"fig_id": fig_id, "source_file": file, "page": spec.page,
                     "verified": _verify(spec, file, cache)})
    return rows, prov


# =================================================================== main

def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _merge_inventory(own: list[dict]) -> list[dict]:
    """Rows of other extractors are kept as they are; this extractor's rows replace
    its own earlier rows."""
    kept = []
    if INVENTORY.exists():
        with open(INVENTORY, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r["source_file"] not in OWN_FILES]
    return kept + own


def _e7_numbers(lines: list[str]) -> tuple[int | None, int | None]:
    m = re.search(r"(\d+) districts have been selected across (\d+) State/UTs",
                  " ".join(lines))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _e6_number(criteria_lines: list[str], table_lines: list[str]) -> int | None:
    """A number of districts selected printed by the criteria table or the text with
    it: the criteria page has no total row; the sentence that follows the table and
    its footnote (top of PDF page 7) begins 'Following this process, N districts'."""
    text = " ".join(criteria_lines)
    m = re.search(r"(\d+) districts (?:have been|were) selected", text)
    if m:
        return int(m.group(1))
    head = " ".join(table_lines[:2])
    m = re.match(r"Following this process, (\d+) districts", head)
    return int(m.group(1)) if m else None


def main() -> int:
    verify_inputs()
    from src.extract import lgd as lgd_mod
    lgd_out, _, _, _ = lgd_mod.run()

    # LGD count per coarse unit (None if any member is not reconstructable)
    lgd_units: dict[str, int | None] = {}
    for s, st in lgd_out.items():
        u = states.coarsen(s)
        if u in lgd_units and lgd_units[u] is None:
            continue
        lgd_units[u] = None if st["count"] is None else lgd_units.get(u, 0) + st["count"]

    ctd = ROOT / CTD_FILE
    lines = page_lines(ctd, CTD_PAGE)
    raw_rows, total = parse_exposure_lines(lines)
    resolutions = [labels.resolve(lab) for lab, _ in raw_rows]   # halts if unmappable
    rows = [(lab, r.canonical, n) for (lab, n), r in zip(raw_rows, resolutions)]
    res = check_exposure(rows, total, lgd_units,
                         e6_number=_e6_number(page_lines(ctd, CRITERIA_PAGE), lines),
                         e7=_e7_numbers(lines))

    n_left = (len(raw_rows) + 1) // 2
    _write(EXTRACTED / "exposure_campaign.csv",
           ["row", "block", "label_printed", "canonical", "coarse_unit", "label_rule_step",
            "label_evidence", "campaign_count", "source_file", "pdf_page", "printed_page",
            "table_id"],
           [{"row": i + 1, "block": "left" if i < n_left else "right",
             "label_printed": lab, "canonical": r.canonical,
             "coarse_unit": states.coarsen(r.canonical), "label_rule_step": r.step,
             "label_evidence": r.evidence, "campaign_count": n, "source_file": CTD_FILE,
             "pdf_page": CTD_PAGE, "printed_page": 5,
             "table_id": "State | Total District (Geographical prioritization)"}
            for i, ((lab, n), r) in enumerate(zip(raw_rows, resolutions))])
    _write(EXTRACTED / "exposure_checks.csv",
           ["check", "inputs", "expected", "observed", "pass", "note"],
           res.checks + [{"check": "decision", "inputs": "E1, E2, E4, E5",
                          "expected": "table not rejected",
                          "observed": "rejected" if res.rejected else "not rejected",
                          "pass": "no" if res.rejected else "yes",
                          "note": "; ".join(res.reject_reasons)}])
    _write(EXTRACTED / "exposure_share.csv",
           ["unit", "in_table", "campaign_count", "lgd_count", "share", "capped",
            "flagged_e5", "computable", "reason"], res.units)

    inv, prov = build_inventory()
    _write(INVENTORY, INVENTORY_COLUMNS, _merge_inventory(inv))
    _write(EXTRACTED / "campaign_inventory_provenance.csv",
           ["fig_id", "source_file", "page", "verified"], prov)
    for c in res.checks:
        print(c["check"], c["pass"], "|", c["observed"], "|", c["note"])
    print("exposure table", "REJECTED: " + "; ".join(res.reject_reasons)
          if res.rejected else "not rejected")
    print(f"inventory rows from campaign documents: {len(inv)}")
    return 1 if res.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
