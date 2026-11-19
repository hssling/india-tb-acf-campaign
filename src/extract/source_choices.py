"""The source-choice record of analysis plan §5.4: every source choice and extraction
decision made before any Q1-Q4 computation, in one file, data/source_choices.csv.

It is assembled from the extraction outputs in data/extracted/ (exposure checks under
both denominators, the LGD results and reconstruction log, label resolutions, printed-
total checks, the named-list cross-check, the inventory scope decisions, the Q4 source
checks, the re-check at extraction and their consequences) and from the decisions
recorded below with the clause that governs each. It reads no source document and
computes no Q result, no guard ratio and no comparison between sources.

The guard of §9.5.2 is applied to the extracted values after this record is frozen and
before any Q4 computation; its ratios, medians and decision are then added to this file
as a dated entry.

Run: python -I src/extract/source_choices.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import re

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "data/extracted"
OUT = ROOT / "data/source_choices.csv"
COLUMNS = ["decision_id", "topic", "source_file", "locator", "decision", "result",
           "rule", "evidence", "date"]

CTD = "data_raw/official/100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf"
KERALA = "data_raw/official/TB_Elimination_Campaign.pdf"
LGD_CUR = "data_raw/lgd/All_Districtof_India_2026-11-18_21-18-59.xlsx"
LGD_MOD = "data_raw/lgd/alldistrictbyDate2026_11_18_21_20_13_069.xls"
LGD_PDF = "data_raw/lgd/alldistrictbyDate2026_11_19_00_26_50_649.pdf"
GHA = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10515680/"
PGPH = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12574901/"
SUPP = "data_raw/studies/ZGHA_A_2256129_SM2351.docx"
D_A, D_B = "2026-11-19", "2026-11-19"


def _read(name: str) -> list[dict]:
    with open(EX / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rec(i, topic, source, locator, decision, result, rule, evidence, date=D_B):
    return {"decision_id": i, "topic": topic, "source_file": source, "locator": locator,
            "decision": decision, "result": result, "rule": rule, "evidence": evidence,
            "date": date}


# ================================================================== Part A

def exposure() -> list[dict]:
    out = [_rec("EXP-00", "exposure table", CTD,
                "PDF page 7 (printed page 5), 'Geographical prioritization', table "
                "'State | Total District' in two column blocks",
                "Exposure source: the CTD per-State count of phase-1 campaign districts "
                "(GO with counts), read from the hashed copy", "33 State/UT rows and a "
                "TOTAL row read; data/extracted/exposure_campaign.csv",
                "§9.1, §9.2", "the later expansion is not used (§9.1)", D_A)]
    for suffix, label, rule in (("", "registered denominator (§9.3 as written)", "§9.2"),
                                ("_reconstructed", "reconstructed denominator (§13, 19 "
                                 "November 2026)", "§9.2; §13 (19 November 2026)")):
        for c in _read(f"exposure_checks{suffix}.csv"):
            tag = "R" if suffix else ""
            cid = c["check"] if c["check"] != "decision" else "DEC"
            out.append(_rec(f"EXP-{cid}{tag}", "exposure table", CTD, "PDF pages 6-7",
                            f"{c['check']} ({label}): {c['inputs']}; expected "
                            f"{c['expected']}",
                            f"{'pass' if c['pass'] == 'yes' else 'fail'}: observed "
                            f"{c['observed']}", rule, c["note"], D_A))
        units = _read(f"exposure_share{suffix}.csv")
        capped = [u["unit"] for u in units if u["capped"] == "yes"]
        flagged = [u["unit"] for u in units if u["flagged_e5"] == "yes"]
        absent = [u["unit"] for u in units if u["in_table"] == "no"]
        nc = [u["unit"] for u in units if u["computable"] != "yes"]
        out.append(_rec(f"EXP-UNITS{'R' if suffix else ''}", "exposure table", CTD,
                        f"data/extracted/exposure_share{suffix}.csv",
                        f"Exposure shares by coarsened unit, {label}",
                        f"{len(units)} units; capped: {', '.join(capped) or 'none'}; "
                        f"flagged under E5: {', '.join(flagged) or 'none'}; not "
                        f"computable: {len(nc)}",
                        "§9.2 (E5, States absent from the table), §9.3",
                        f"units absent from the table (campaign count 0): "
                        f"{', '.join(absent)}; not computable: {', '.join(nc) or 'none'}",
                        D_A))
    return out


def lgd() -> list[dict]:
    reg = _read("lgd_districts_2024-12-07.csv")
    rec = _read("lgd_districts_2024-12-07_reconstructed.csv")
    out = [
        _rec("LGD-01", "LGD denominator", f"{LGD_CUR}; {LGD_MOD}",
             "LGD 'All Districts of India' (18 Nov 2026) and the modification report "
             "(07/12/2024-18/11/2026)",
             "Reference date 7 December 2024; date field taken row by row (effective "
             "date, else modification date) as §9.3 requires",
             f"registered result: the report gives no date and no type for any of its "
             f"154 rows (fields: {reg[0]['report_fields']}); "
             f"{sum(r['reconstructable'] == 'yes' for r in reg)} of {len(reg)} States/UTs "
             f"reconstructable",
             "§9.3", "data/extracted/lgd_districts_2024-12-07.csv; "
                     "lgd_reconstruction_log.csv (one row per modification row)", D_A),
        _rec("LGD-02", "LGD denominator", LGD_PDF,
             "LGD 'Download Only Modifications', PDF format (19 Nov 2026)",
             "Examined and not used", "the same six columns; no date or type field",
             "§13 (19 November 2026)", "pinned in the source manifest as "
                                       "author-supplied", D_A),
        _rec("LGD-03", "LGD denominator", "data/lgd_evidence/",
             "official notices and the LGD public district feed (read online)",
             "Reconstruction from official notices (deviation from §9.3; both results "
             "kept, the reconstruction reported as the main Q4 analysis)",
             f"{sum(r['computable'] == 'yes' for r in rec)} of {len(rec)} "
             f"States/UTs computable; every modification row accounted for",
             "§13 (19 November 2026)",
             "data/extracted/lgd_districts_2024-12-07_reconstructed.csv; "
             "lgd_reconstruction_log_reconstructed.csv; no official count dated 1 "
             "November-7 December 2024 was found, so the check has nothing to compare",
             D_A)]
    for r in rec:
        if r["created_undone"] not in ("", "0") or r["abolished_restored"] not in ("", "0"):
            out.append(_rec(f"LGD-S-{_slug(r['state'])}", "LGD denominator",
                            "data/lgd_evidence/", f"State: {r['state']}",
                            f"Count at 7 December 2024 for {r['state']}",
                            f"{r['count_2024_12_07']} (current {r['current_count']}; "
                            f"created undone {r['created_undone']}; abolished restored "
                            f"{r['abolished_restored']})", "§13 (19 November 2026)",
                            r["basis"], D_A))
    for r in _read("lgd_reconstruction_log_reconstructed.csv"):
        out.append(_rec(f"LGD-C-{r['change_id']}", "LGD denominator", r["source_url"],
                        f"{r['state']}: {r['district_name']} ({r['district_code']})",
                        f"{r['change_type']} dated {r['date']} ({r['date_kind']}): "
                        f"{r['action']}", r["effect"], "§13 (19 November 2026)",
                        r["ruling"], D_A))
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", s.upper()).strip("-")


# ================================================================== labels

def _part_e_files() -> frozenset[str]:
    """Source files of the Part E addendum (PQE-*); kept out of the frozen sections."""
    from src.extract import pq_more as E
    return E.OWN_FILES | {"data_raw/pq/ (Part E)"}


def _label_resolutions(include) -> dict[tuple[str, str], tuple[str, str, str]]:
    seen: dict[tuple[str, str], tuple[str, str, str]] = {}
    for name in sorted(p.name for p in EX.glob("*.csv")):
        rows = _read(name)
        if not rows or "label_rule_step" not in rows[0]:
            continue
        if not include(rows[0].get("source_file", "")):
            continue
        lab_col = next(c for c in ("label_printed", "lgd_label", "named_list_labels",
                                   "label") if c in rows[0])
        for r in rows:
            step = str(r["label_rule_step"])
            if step in ("2", "3"):
                canon = r.get("canonical") or r.get("state") or ""
                src = (r.get("source_file") or r.get("source_current")
                       or {"named_list_check.csv": KERALA}.get(name, name))
                seen.setdefault((src, r[lab_col]),
                                (step, canon, r.get("label_evidence", "")
                                 or f"see data/extracted/{name}"))
    with open(ROOT / "data/figures_inventory.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not include(r["source_file"]):
                continue
            for m in re.finditer(r"label printed as '([^']*)'; label rule step (\d): "
                                 r"([^;]*)", r["note"]):
                seen.setdefault((r["source_file"], m.group(1)),
                                (m.group(2), r["geography"], m.group(3)))
    return seen


def labels_() -> list[dict]:
    pe = _part_e_files()
    seen = _label_resolutions(lambda f: f not in pe)
    out = []
    for k, ((src, lab), (step, canon, ev)) in enumerate(sorted(seen.items()), start=1):
        out.append(_rec(f"LAB-{k:02d}", "label rule", src, f"label printed '{lab}'",
                        f"Label rule step {step}: '{lab}' -> {canon or '(not computable)'}",
                        "mapped" if canon else "not computable (listed)",
                        "§9.2 label rule (E3); §11", ev))
    return out


# ================================================================== totals, named list

def totals() -> list[dict]:
    out = []
    pe = _part_e_files()
    rows = sorted((c for c in _read("table_total_checks.csv")
                   if c["source_file"] not in pe),
                  key=lambda c: (c["source_file"], c["page"], c["table"]))
    for k, c in enumerate(rows, start=1):
        res = {"yes": "pass", "no": "fail", "n/a": "not applied"}[c["pass"]]
        out.append(_rec(f"TOT-{k:03d}", "printed totals", c["source_file"],
                        f"{c['table']} (PDF page {c['page']})",
                        "State rows checked against the printed total (§6.2 check 3; "
                        "§9.6 for Q4 sources)",
                        f"{res}: {c['rows']} rows sum to {c['sum_of_rows']}; printed "
                        f"total {c['printed_total'] or 'none'}; difference "
                        f"{c['difference'] or 'n/a'}", "§6.2 check 3; §9.6",
                        c["note"]))
    return out


def _tot_ids(source: str, table_part: str, passed: str) -> list[str]:
    """decision_ids of the printed-total rows of one table with a given result."""
    return [r["decision_id"] for r in totals() if r["source_file"] == source
            and table_part in r["locator"]
            and r["result"].startswith({"no": "fail", "yes": "pass"}[passed])]


def named() -> list[dict]:
    rows = _read("named_list_check.csv")
    tot = [r for r in rows if r["state"] == "TOTAL"][0]
    diff = [r for r in rows if r["match"] == "no" and r["state"] != "TOTAL"]
    out = [_rec("NAM-01", "named list", KERALA, "Annexure-I of the D.O. letter, PDF "
                "pages 12-28 (State column only)",
                "Named list of campaign districts found; its rows counted per State and "
                "compared with the CTD table",
                f"{tot['named_list_rows']} rows against 347; {len(diff)} States differ",
                "§9.2 (Named list)", "data/extracted/named_list_check.csv; the CTD "
                                     "counts remain the exposure", D_A),
           _rec("NAM-02", "named list", KERALA, "PDF pages 12-28",
                "Sensitivity analysis S7 (population share)", "not eligible: the named "
                "list's per-State counts do not equal the CTD table in every State",
                "§9.2 (Named list); §10.5 S7", "S7 is not run, and the paper says so",
                D_A)]
    for r in diff:
        out.append(_rec(f"NAM-S-{_slug(r['state'])}", "named list", KERALA,
                        f"State: {r['state']}", "Named-list count differs from the CTD "
                        "count", f"CTD {r['ctd_count']}; named list "
                        f"{r['named_list_rows']}", "§9.2 (Named list): a Q2 discrepancy",
                        r["note"], D_A))
    return out


def scope() -> list[dict]:
    from src.extract import online_pages as W   # Part D rows are a later addendum (WEB-*)
    out = []
    pe = _part_e_files()
    rows = sorted((r for r in _read("inventory_scope_decisions.csv")
                   if r["source_file"] not in W.OWN_FILES
                   and r["source_file"] not in pe),
                  key=lambda r: (r["source_file"], r["kind"] != "rule", r["doc"],
                                 int(r["page"]) if r["page"].isdigit() else 0,
                                 r["where"], r["figures"]))
    for k, r in enumerate(rows, start=1):
        out.append(_rec(f"SCO-{k:03d}", "inventory scope", r["source_file"],
                        (f"{r['doc']}, page {r['page']}" if r["page"] else r["doc"])
                        + (f", {r['where']}" if r["where"] else ""),
                        r["kind"] + (f" ({r['category']})" if r["category"] else ""),
                        r["decision"] or "rule",
                        "§5.1; §5.3; §13 (19 November 2026, context rule)",
                        (f"figures: {r['figures']}; " if r["figures"] else "")
                        + r["reason"]))
    return out


def quality() -> list[dict]:
    return [
        _rec("QS-01", "quality studies", f"{GHA}; {SUPP}", "Tables 1-2; supplement S1, S2",
             "GHA 2023 read from the published tables and the supplement; the Figshare "
             "dataset not used", "C1, C2, C4 computable (S1 gives screened, tested, "
             "diagnosed); C3 not computable (no presumptive count)",
             "§7.5 (Data: tables first; Figshare only where a table gives a percentage "
             "without its counts)", "data/extracted/quality_studies.csv", D_A),
        _rec("QS-02", "quality studies", PGPH, "Table 2 (Total row), Table 3",
             "PGPH 2025 read from the published tables; supporting files S1-S2 and the "
             "record-level file not downloaded (author decision)",
             "C1-C4 computable from Table 2", "§7.5", "data/extracted/quality_studies.csv",
             D_A),
        _rec("QS-03", "quality studies", f"{GHA}; {PGPH}", "HTML full texts read online "
             "on 2026-11-19", "Table cells transcribed by hand into "
             "data/transcribed/quality_studies_tables.csv; prose sentences copied from "
             "the PMC BioC JSON text", "286 cells; verified against the live pages",
             "§3.3 (HTML pages read online and cited with URL and access date)",
             "nothing saved to data_raw", D_A),
        _rec("QS-04", "quality studies", f"{GHA}; {PGPH}", "subgroup strata",
             "Non-geographic subgroup strata kept in data/extracted only, not in the "
             "inventory (ruling A16)", "excluded from the inventory",
             "§5.2 (the schema has no subgroup field)",
             "listed in inventory_scope_decisions.csv", D_A),
        _rec("QS-05", "quality studies", f"{GHA}; {PGPH}", "benchmark targets",
             "Benchmark thresholds of the ACF guidance not entered; restatements of GHA "
             "2021 figures in PGPH entered with a note (ruling A20)", "recorded",
             "§5.1", "listed in inventory_scope_decisions.csv", D_A),
        _rec("QS-06", "quality studies", SUPP, "S1 and S2 Annex, INDIA rows",
             "Printed internal differences kept as printed (S2 INDIA 41,659 against S1 "
             "INDIA diagnosed 41,306)", "entered, not reconciled", "§5.1 (no figure "
             "left out because it looks wrong)", "data/extracted/quality_studies.csv",
             D_A),
    ]


# ================================================================== Part B

def q4() -> list[dict]:
    out = []
    for k, r in enumerate(_read("q4_source_checks.csv"), start=1):
        out.append(_rec(f"Q4X-{k:02d}", "Q4 extraction checks", r["source_file"],
                        r["locator"], f"{r['source']}: §9.6 extraction checks; needed "
                        f"column(s): {r['needed_columns']}; role: {r['role']}",
                        f"{r['result']} (column check {r['column_check']}; sum check "
                        f"{r['sum_check']})", "§9.6 'Extraction checks for every Q4 "
                        "source'", r["note"]))
        out.append(_rec(f"Q4R-{k:02d}", "re-check at extraction (§9.5.4)",
                        r["source_file"], r["locator"],
                        f"{r['source']}: notes printed with the values read; wording, "
                        "as-on and window checked against the reading assumed in §9.5",
                        "no State excluded; comparability not re-judged (no note "
                        "changes window, cut-off or source)", "§9.5.4", r["recheck_954"]))
    for k, r in enumerate(_read("q4_consequences.csv"), start=1):
        out.append(_rec(f"Q4C-{k:02d}", "Q4 consequences", "data/extracted/"
                        "q4_source_checks.csv", r["item"], "Mechanical consequence of "
                        "the extraction checks", r["outcome"], r["rule"],
                        "applied by src/source_checks.py; no guard ratio computed"))
    return out


PQ = "data_raw/pq/"
ITR = "data_raw/india_tb_report/"


def outcome_tables() -> list[dict]:
    return [
        _rec("OUT-01", "outcome tables (§9.5)", PQ + "AU1216_WFw8li.pdf",
             "Annexure, PDF page 2; columns '2024 (Jan-Dec)' and '2025 (Jan-Dec)', "
             "'Number of TB cases notified'",
             "Primary Q4 contrast: full-year 2025 against full-year 2024 from Question "
             "1216; the 'Beneficiaries paid at least once' columns not used",
             "extracted: data/extracted/pq_q1216.csv (36 State/UT rows)",
             "§9.5.1", "one table, one heading, one source; as on 6 February 2026 "
                       "(37 days after 31 December 2025)"),
        _rec("OUT-02", "outcome tables (§9.5)", PQ + "AS261_lP7nYE.pdf",
             "Annexure-I, PDF pages 4-5; column '2024 (Jan- Oct)'",
             "S8 January-October 2024 from Lok Sabha Question 261 (not Question 2511)",
             "extracted: data/extracted/pq_q261.csv", "§1.3 item 2; §9.5.3",
             "the 2023 column is extracted for S8(b)"),
        _rec("OUT-03", "outcome tables (§9.5)", PQ + "AU1093_dH065I.pdf",
             "Annexure, PDF page 2; column 'TB Cases reported'",
             "S8 January-October 2025 from Question 1093",
             "extracted: data/extracted/pq_q1093.csv", "§9.5.3", ""),
        _rec("OUT-04", "outcome tables (§9.5)", PQ + "AU2511_t81pFf.pdf",
             "Annexure, PDF page 2", "Question 2511 not used for Q4; entered in the "
             "inventory for Q1-Q2", "extracted: data/extracted/pq_q2511.csv",
             "§9.5.5; §7.4",
             "as printed, the column heading reads 'State/UT wise TB cases Notification "
             "in 2024 (Jan- Oct)' and the table note '*As on 19th Nov 2024'; §7.4 "
             "describes the answer's window as the year to date and its OGD mirror's "
             "label as 'January to October'. The window is entered as printed "
             "(1 January-31 October 2024, as on 19 November 2024); the mirror was not "
             "read in this task (no network)"),
        _rec("OUT-05", "outcome tables (§9.5)", PQ + "AU1900_PxKD5V.pdf",
             "Annexure, PDF page 3", "Question 1900 obtained (pinned 18 November 2026); "
             "its 2025 (Jan to Oct) column is the pre-specified Q2 cross-check with "
             "Question 1093; its 2024 (Jan to Dec) column is exploratory",
             "obtained; extracted: data/extracted/pq_q1900.csv",
             "§5.4 ('whether Rajya Sabha Question 1900 was obtained'); §9.5.5; §13 "
             "(18 November 2026)", "does not change Q4"),
        _rec("OUT-06", "outcome tables (§9.5)", PQ + "AU420_ulGhhr.pdf",
             "Annexure-I, PDF page 3", "Question 420 used only as an exploratory Q2 "
             "cross-check of Question 1216's 2025 column", "extracted: "
             "data/extracted/pq_q420.csv; labelled exploratory",
             "§13 (18 November 2026)", "does not change Q4"),
        _rec("OUT-07", "outcome tables (§9.5)", PQ + "AU3467_mVGJLD.pdf",
             "Annexure-I, PDF page 3; 'TB patients notified' under '2023' and '2024*'",
             "Guard reference table (§9.5.2) and fallback trend point 2024",
             "extracted: data/extracted/pq_q3467.csv", "§9.5.2; §9.6", ""),
        _out08(),
        _rec("OUT-09", "outcome tables (§9.5)", PQ + "AU3001_ZXEQ3g.pdf", "whole answer",
             "Question 3001 (drug-resistant TB) not used", "not read beyond its digest",
             "§3.1.2; §9.5.5", ""),
        _rec("OUT-10", "outcome tables (§9.5)", PQ + "AU3477_SSspdQ.pdf", "whole answer",
             "Question 3477 read for the inventory", "no figure of a §5.1 quantity "
             "printed; recorded in inventory_scope_decisions.csv", "§5.3; §9.5.5", ""),
    ]


def trend() -> list[dict]:
    rows = [
        (2019, ITR + "ITR2020.pdf", "India TB Report 2020, Annexure 1.2 'TB Cases & "
         "Paediatric cases notification', column 'TB patients notified: Total', PDF page "
         "204 (printed 180), located from the list of annexures (PDF pages 201-202)",
         "same source for primary and fallback; data/extracted/itr2020_a1_2.csv"),
        (2022, ITR + "ITR2023.pdf", "India TB Report 2023, Annexure 1.2, column 'TB "
         "patients notified ... Total', PDF pages 213-214 (printed 183-184)",
         "same source for primary and fallback; data/extracted/itr2023_a1_2.csv"),
        (2023, PQ + "AU1216_WFw8li.pdf", "Question 1216, column '2023 (Jan-Dec)', "
         "'Number of TB cases notified'", "fallback (if the guard fails): India TB "
         "Report 2024, Annexure 1.2 Total, PDF pages 187-188 "
         "(data/extracted/itr2024_a1_2.csv)"),
        (2024, PQ + "AU1216_WFw8li.pdf", "Question 1216, column '2024 (Jan-Dec)', "
         "'Number of TB cases notified'", "fallback (if the guard fails): Question 3467, "
         "Annexure-I, 2024 'TB patients notified' (data/extracted/pq_q3467.csv)"),
    ]
    out = [_rec(f"TRD-{y}", "trend sources (§9.6)", f, loc,
                f"Trend point {y}: primary source", "in use (its extraction checks "
                "passed); the fallback column replaces 2023 and 2024 together only if "
                "the guard fails", "§9.6 table", ev) for y, f, loc, ev in rows]
    out.append(_rec("TRD-2020-21", "trend sources (§9.6)", "", "calendar years 2020 and "
                    "2021", "Excluded from the trend (COVID-19 disruption); the 2021 "
                    "edition (a scan) is not used", "excluded", "§3.2; §9.6", ""))
    return out


def coarsening() -> list[dict]:
    return [
        _rec("UNIT-01", "unit coarsening (§9.4)", "all State tables",
             "Jammu and Kashmir; Ladakh",
             "Combined to 'Jammu and Kashmir (incl. Ladakh)' in every source and year",
             "applied in every extracted table (coarse_unit column)", "§9.4",
             "printed separately in the CTD tables, every parliamentary answer and the "
             "India TB Reports 2022-2024; the 2019 and 2020 editions print Jammu & "
             "Kashmir only (data years 2018-2019, before Ladakh became a separate UT)"),
        _rec("UNIT-02", "unit coarsening (§9.4)", "all State tables",
             "Dadra and Nagar Haveli; Daman and Diu",
             "Combined to 'Dadra and Nagar Haveli and Daman and Diu' in every source and "
             "year", "applied in every extracted table (coarse_unit column)", "§9.4",
             "printed separately in the India TB Reports 2019 (Annexure 1.7) and 2020 "
             "(Annexures 1.2 and 6); combined in every other table read"),
        _rec("UNIT-03", "unit coarsening (§9.4)", "all State tables",
             "every State table read in Tasks 3A-3C",
             "Other pairs that one source reports separately and another combines",
             "none found", "§9.4 ('any other pair ... as found at extraction')",
             "units printed per table are listed in each data/extracted CSV "
             "(label_printed, canonical, coarse_unit)"),
    ]


def q3_tables() -> list[dict]:
    t = [("Q3T-2018", "data_raw/official/India-TB-Report-2019.pdf", "Annexure 1.7, PDF "
          "page 178 (printed 156)", 2018, "screened, tested, diagnosed (yield, NNS); no "
          "row for Madhya Pradesh, Manipur, Tripura", "itr2019_a1_7_acf.csv"),
         ("Q3T-2019", ITR + "ITR2020.pdf", "Annexure 6, PDF page 255 (printed 231)", 2019,
          "screened, tested, diagnosed (yield, NNS); no row for Chandigarh, Madhya "
          "Pradesh, Manipur", "itr2020_a6_acf.csv"),
         ("Q3T-2021", "data_raw/official/TBAnnaulReport2022.pdf", "Annexure 6, PDF page "
          "131 (printed 237)", 2021, "screened, tested, diagnosed (yield, NNS)",
          "itr2022_a6_acf.csv"),
         ("Q3T-2022", ITR + "ITR2023.pdf", "Annexure 6, PDF pages 299-300 (printed "
          "269-270)", 2022, "screened, 'TB symptomatic identified and examined', "
          "diagnosed (yield, NNS); its State rows do not sum to the printed India row "
          "in any column (failed printed-total checks "
          + ", ".join(_tot_ids(ITR + "ITR2023.pdf", "Annexure 6", "no")) + ")",
          "itr2023_a6_acf.csv"),
         ("Q3T-2023", ITR + "ITR2024.pdf", "Annexure 6, PDF page 279 (printed 248)", 2023,
          "screened, tested, diagnosed (yield, NNS)", "itr2024_a6_acf.csv")]
    out = [_rec(i, "Q3 tables (§8.4)", f, loc, f"Q3 table for {y}: the edition that "
                f"reports {y} (precedence level 1)", "used; the single value for any "
                f"summary of {y}", "§8.1; §8.4 level 1",
                f"{ev}; data/extracted/{csv_}")
           for i, f, loc, y, ev, csv_ in t]
    out += [
        _rec("Q3T-2021-GHA", "Q3 tables (§8.4)", SUPP, "S1 Annex (State screened, tested, "
             "diagnosed, first ACF cycle 2021); S2 Annex (ACF-detected and public "
             "notified TB, 2021)", "Second Q3 table for 2021: every result is reported "
             "with its source (§8.4 first paragraph); for a single summary value the "
             "India TB Report 2022 is chosen (level 1), the study being none of the five "
             "levels", "used beside the ITR 2022 table",
             "§8.4", "S2 is the only table read that gives the ACF share's numerator and "
                     "denominator together"),
        _rec("Q3T-SHARE", "Q3 tables (§8.4)", "India TB Reports 2019-2024",
             "ACF annexures", "ACF share of notifications (§8.1): the India TB Report ACF "
             "annexures print no notification count, so the share is not computed from "
             "them ('a published table gives both its numerator and its denominator')",
             "not computable from the India TB Reports; GHA S2 (2021) only",
             "§8 (opening sentence of §8.1)", "the notification annexures of the 2019 "
                                              "and 2022 editions were not extracted"),
        _rec("Q3T-2022-COL", "Q3 tables (§8.4)", ITR + "ITR2023.pdf",
             "Annexure 6, column 'TB symptomatic identified and examined, n (%)'",
             "Entered as quantity 'tested' (people examined), definition class by rule "
             "(unspecified)", "judgement: 'examined' read as tested; 'presumptive' is "
             "the alternative", "§5.1 (vocabulary); §7.2", "the chapter's sentence "
             "for the same year reads 'were examined and tested for TB diagnosis' "
             "(PDF page 63)"),
        _rec("Q3T-PQ", "Q3 tables (§8.4)", PQ, "parliamentary answers held",
             "No parliamentary answer held prints a State ACF table; the answers listed "
             "with include = yes that may (Rajya Sabha Q. 414 of 6 Feb 2024, Q. 278, "
             "Q. 279 of 4 Feb 2025, Q. 2051 of 18 Mar 2025; Lok Sabha Q. 79) are not in "
             "data_raw and were not obtained in this task",
             "not available", "§3.3 (author's permission before any download); §8.3",
             "data/search_log.csv"),
        # Addenda made at Task 6 (additions only): the Q3 summary's choices that the
        # rows above did not cover.
        _rec("Q3T-SHARE-2021", "Q3 tables (§8.4)", "data_raw/studies/ZGHA_A_2256129_SM2351.docx",
             "S2 Annex (ACF-detected and public notified TB, 2021)",
             "ACF share of notifications, 2021: GHA S2 is the only table that gives both "
             "figures, so it is the single value for the summary (§8.4 applied "
             "mechanically: one candidate); the denominator is public-sector notifications "
             "only, and the numerator is 'ACF cases diagnosed among tested'",
             "used; summary indicator acf_share_pct, 2021 only",
             "§8.1; §8.4", "India TB Report ACF annexures print no notification count "
                           "(Q3T-SHARE); an ITR notification annexure is not combined "
                           "with an ACF annexure because §8.1 requires one published "
                           "table to give both figures", "2026-11-19"),
        _rec("Q3T-NOTAB", "Q3 tables (§8.4)", "data/source_choices.csv",
             "Q3T-2018 to Q3T-2023", "Data years 2020 and 2024: no State ACF table among "
             "the Q3 tables read; listed in outputs/q3_yield.csv as not available",
             "not available", "§8.3", "no Q3T row for these years", "2026-11-19"),
    ]
    return out


def general() -> list[dict]:
    files = [PQ + f for f in ("AS261_lP7nYE.pdf", "AU1093_dH065I.pdf", "AU1216_WFw8li.pdf",
                              "AU2511_t81pFf.pdf", "AU3001_ZXEQ3g.pdf", "AU3467_mVGJLD.pdf",
                              "AU3477_SSspdQ.pdf", "AU1900_PxKD5V.pdf", "AU420_ulGhhr.pdf")]
    files += [ITR + f"ITR{y}.pdf" for y in (2020, 2023, 2024)]
    files += ["data_raw/official/India-TB-Report-2019.pdf",
              "data_raw/official/TBAnnaulReport2022.pdf"]
    return [
        _rec("SRC-01", "sources", "; ".join(files), "whole files",
             "SHA-256 of every Part B source verified against data/source_manifest.csv "
             "before reading", "all match", "§3.1, §3.2; §11", ""),
        _rec("SRC-02", "sources", PQ, "answer documents",
             "Parliamentary tables read from the answer documents themselves, not from "
             "OGD mirrors", "applied", "§3.4", "the OGD mirrors were not read in this "
                                               "task (no network)"),
        _rec("SRC-03", "sources", "India TB Reports 2019-2024", "pages without a text "
             "layer", "Every page without a text layer was rendered; OCR was used only to "
             "find passages naming ACF; figures entered from such pages were read from "
             "the rendered page", "2019: 50 pages; 2020: 47; 2022: 5; 2023: 77; 2024: 39",
             "§11 (provenance)", "inventory_scope_decisions.csv; "
                                 "itr_inventory_provenance.csv"),
        _rec("SRC-04", "inventory scope", "parliamentary answers; India TB Reports",
             "State notification tables", "State notification tables enter the "
             "inventory where §7.4 names them (Questions 2511, 1900, 1093, 261, 1216, "
             "3467; India TB Report 2024) and Question 420 (§13); the 2020 and 2023 "
             "editions' notification annexures stay in data/extracted only",
             "applied", "§5.1 (quantities of ACF and the campaign); §7.4 ('These are "
                        "entered and classified'); §13 (18 November 2026)",
             "inventory scope rules of the parliamentary answers and the India TB "
             "Reports (SCO rows)"),
    ]


GUARD_DATE = "2026-11-19"


def _guard() -> dict[str, str] | None:
    path = EX / "guard_result.csv"
    if not path.exists():
        return None
    return {r["item"]: r["value"] for r in _read("guard_result.csv")}


def _out08() -> dict:
    g = _guard()
    src = PQ + "AU1216_WFw8li.pdf; " + PQ + "AU3467_mVGJLD.pdf"
    if g is None:
        return _rec("OUT-08", "outcome tables (§9.5)", src, "the guard of §9.5.2",
                    "The guard (State ratios of Question 1216 to Question 3467 for 2023 "
                    "and 2024, their medians and the decision) is applied to the "
                    "extracted values after this freeze and before any Q4 computation, "
                    "and added to this file as a dated entry",
                    "pending: not computed at extraction", "§9.5.2; §5.4",
                    "Question 1216 passed its own extraction checks, so the guard is "
                    "not failed by extraction (Q4C rows)")
    return _rec("OUT-08", "outcome tables (§9.5)", src, "the guard of §9.5.2",
                "The guard applied to the extracted values (dated addendum GRD-01 to "
                "GRD-06)", f"{g['status']}: median 2023 {g['median ratio 2023']} (n "
                f"{g['n States 2023']}), median 2024 {g['median ratio 2024']} (n "
                f"{g['n States 2024']}); primary contrast: {g['primary contrast']}",
                "§9.5.2; §5.4", "data/extracted/guard_ratios.csv; guard_result.csv",
                GUARD_DATE)


def guard_rows() -> list[dict]:
    """Dated addendum: the guard of §9.5.2, computed after the freeze of the other
    choices and before any other Q computation."""
    g = _guard()
    if g is None:
        return []
    src = PQ + "AU1216_WFw8li.pdf; " + PQ + "AU3467_mVGJLD.pdf"
    T = "guard (§9.5.2)"
    ratios = _read("guard_ratios.csv")
    out_ = [r for r in ratios if r["outside_0_95_1_05"] == "yes"]
    left = [f"{r['unit']} ({r['year']})" for r in ratios if r["in_guard"] == "no"]
    return [
        _rec("GRD-01", T, src, "Question 1216 '2023 (Jan-Dec)', '2024 (Jan-Dec)' "
             "'Number of TB cases notified' / Question 3467 Annexure-I 'TB patients "
             "notified' (2023, 2024*), coarsened units (§9.4)",
             "Per-State ratios Q1216 / Q3467 for 2023 and 2024",
             f"{len([r for r in ratios if r['in_guard'] == 'yes'])} ratios; States left "
             f"out (missing in one table): {', '.join(left) or 'none'}",
             "§9.5.2 (Comparison)", "data/extracted/guard_ratios.csv; computed by "
             "src/q4_dose_response.py (run_guard)", GUARD_DATE),
        _rec("GRD-02", T, src, "2023", "Median 2023 ratio within [0.95, 1.05]",
             f"median {g['median ratio 2023']}; n {g['n States 2023']}",
             "§9.5.2 (Rule)", "", GUARD_DATE),
        _rec("GRD-03", T, src, "2024", "Median 2024 ratio not below 0.95 (above 1.05 "
             "reported descriptively)",
             f"median {g['median ratio 2024']}; n {g['n States 2024']}",
             "§9.5.2 (Rule)", "", GUARD_DATE),
        _rec("GRD-04", T, src, "decision", "Guard decision (a failure of Question "
             "1216's extraction checks would count as a failed guard)",
             g["status"], "§9.5.2", g["extraction checks"], GUARD_DATE),
        _rec("GRD-05", T, src, "consequence", "Mechanical consequence of the guard",
             f"primary contrast: {g['primary contrast']}; full-year contrast: "
             f"{g['full-year contrast role']}; trend: {g['trend sources']}",
             "§9.5.2 (If the guard fails); §9.6 Fallback; §10.5", "", GUARD_DATE),
        _rec("GRD-06", T, src, "State ratios outside [0.95, 1.05]",
             "Every State outside [0.95, 1.05] in either year is a Q2 discrepancy "
             "(§7.4); 2024 rows above 1.05 are labelled late-report-consistent",
             f"{g['States outside [0.95, 1.05] in 2023']} in 2023, "
             f"{g['States outside [0.95, 1.05] in 2024']} in 2024 "
             f"({g['2024 rows labelled late-report-consistent']} labelled "
             "late-report-consistent)", "§9.5.2 (State discrepancies); §7.4",
             "; ".join(f"{r['unit']} {r['year']} {r['ratio']}"
                       + (f" ({r['label']})" if r["label"] else "") for r in out_),
             GUARD_DATE),
    ]


WEB_DATE = "2026-11-19"
WEB_T = "web pages read online (§3.3, §5.3)"
SIX_PDFS = ("Lok Sabha Starred Q. 79; Rajya Sabha Unstarred Q. 414 (6 Feb 2024), Q. 278 and "
            "Q. 279 (4 Feb 2025), Q. 2051 (18 Mar 2025); the MHA advisory of 8 Jan 2025")


def online_rows() -> list[dict]:
    """Dated addendum: the include = yes web pages and the pages they cite (§5.3), read online
    and entered in the inventory after the freeze commit dbb71b3 and the guard addendum
    (11cfbe4), before any Q1-Q3 computation. Built from data/transcribed/online_pages.csv and
    src/extract/online_pages.py."""
    from src.extract import online_pages as W
    summ = W.page_summary()
    src = "data/transcribed/online_pages.csv; src/extract/online_pages.py"
    read = [p for p in summ if p["availability"] == "read"]
    una = [p for p in summ if p["availability"] != "read"]
    cited = [p for p in read if p["cited_by"]]
    inc = [p for p in read if not p["cited_by"]]
    inc_fig = [p for p in inc if p["n_rows"]]
    inc_none = [p for p in inc if not p["n_rows"]]
    cit_fig = [p for p in cited if p["n_rows"]]
    cit_none = [p for p in cited if not p["n_rows"]]
    n_rows = sum(p["n_rows"] for p in summ)
    lab = lambda ps: "; ".join(f"{p['page_key']} ({p['n_rows']})" if p["n_rows"]
                               else p["page_key"] for p in ps)
    d = WEB_DATE
    rows = [
        _rec("WEB-01", WEB_T, src, "the include = yes web pages and the cited sources",
             "The include = yes web pages were read online and entered in the inventory after "
             "the source-choice freeze commit (dbb71b3) and the guard addendum (11cfbe4), "
             "before any Q1-Q3 computation. They are recorded here as a dated addendum; no "
             "frozen row is changed",
             f"{len(read)} pages read, {n_rows} inventory rows, {len(una)} pages unavailable",
             "§3.3; §5.3; §5.4; §13 (Part D, 19 November 2026)",
             "figures_inventory.csv; inventory_scope_decisions.csv", d),
        _rec("WEB-02", WEB_T, "each page's URL", "reading method",
             "Raw HTML fetched with curl to standard output (user agent 'Mozilla/5.0') and the "
             "visible text extracted with python -I and html.parser; sentences and table cells "
             "copied from that text; nothing saved to the repository or data_raw; URL, access "
             "time (UTC) and method recorded for each page. No login, form or CAPTCHA",
             "applied; for ntep.in the user agent 'Mozilla/5.0' was refused (HTTP 406, "
             "Mod_Security) and the page was read with the user agent 'curl/8.0'",
             "§3.3 (read online, cited with URL and access date)", src, d),
        _rec("WEB-03", WEB_T, "include = yes pages with in-scope figures",
             "Pages entered in the inventory (inventory rows in brackets)", lab(inc_fig),
             "§5.1; §5.3 (first set)", src, d),
        _rec("WEB-04", WEB_T, "include = yes pages without an in-scope figure",
             "Pages read; no figure entered; what was left out is in inventory_scope_decisions.csv",
             lab(inc_none), "§5.1; rules 3–4 of the inventory scope rule", src, d),
        _rec("WEB-05", WEB_T, "cited sources (§5.3, second set)",
             "Pages that an included page names as the source of a figure, by footnote or "
             "reference list, read and entered (rows in brackets). PIB PRID 2199422 is the "
             "release cited by footnote 2 of the 24 March 2026 PIB note for the Cough Against TB "
             "figures", lab(cit_fig), "§5.3 (documents cited by name as the source of a figure; "
                                      "their own references are not followed)", src, d),
        _rec("WEB-06", WEB_T, "cited sources without an in-scope figure",
             "Cited pages read; no figure entered", lab(cit_none), "§5.3", src, d),
        _rec("WEB-07", WEB_T, "PIB PRID 2115334 (provisional row of the search log)",
             "Resolved before any figure was taken: the release (Gujarati text, 26 March 2025, "
             "PIB Ahmedabad) is a message of thanks that prints no figure of a §5.1 quantity, "
             "so it is excluded", "excluded", "§5.3 (the provisional row)",
             "data/search_log.csv is left as registered; the decision is recorded here and in "
             "inventory_scope_decisions.csv", d),
        _rec("WEB-08", WEB_T, "pages unavailable",
             "Pages that could not be read verbatim are listed as unavailable",
             "unavailable: " + "; ".join(f"{p['page_key']} ({p['url']})" for p in una),
             "§3.3 (a source that cannot be obtained is reported as unavailable)", src, d),
        _rec("WEB-09", WEB_T, "not in scope of this addendum",
             "Not read here: " + SIX_PDFS + " (PDF downloads by the author, entered later); the "
             "data.gov.in mirrors (§3.4: cross-checks only; not reachable); the PMC, PLOS, "
             "Figshare and LGD pages (read in Part C and the LGD work); the WHO pages, social "
             "media posts and PDF links among the references (not official PIB or Ministry "
             "pages, or downloads); https://nikshay.in/Home/AboutUs (reference list of PIB "
             "2114549), cited for a description of the portal, not for a figure", "not entered", "§3.3; §3.4; §5.1", src, d),
    ]
    for k, p in enumerate(summ, start=1):
        if p["availability"] == "read":
            res = (f"{p['n_rows']} inventory rows" if p["n_rows"]
                   else "read; no in-scope figure")
            dec = f"{p['title'][:110]} (read with: {p['method'][:60]}...)"
        else:
            res, dec = "unavailable", "page could not be read"
        if p["cited_by"]:
            res += "; cited source: " + p["cited_by"]
        rows.append(_rec(f"WEB-P{k:02d}", WEB_T, p["url"], f"accessed {p['accessed_utc']}",
                         dec, res, "§3.3; §5.3", src, d))
    return rows


PQE_DATE = "2026-11-19"
PQE_T = "parliamentary answers, Part E (§5.3)"


def pq_more_rows() -> list[dict]:
    """Dated addendum (Part E): five further include = yes parliamentary answers supplied
    by the author, entered after the source-choice freeze and the Part D addendum,
    before any Q1-Q3 computation; and the MHA prison advisory, not obtained."""
    from src.extract import pq_more as E
    d = PQE_DATE
    inv = [r for r in csv.DictReader(open(ROOT / "data/figures_inventory.csv",
                                          newline="", encoding="utf-8"))
           if r["source_file"] in E.OWN_FILES]
    n = {k: sum(1 for r in inv if r["source_file"] == f)
         for k, (f, _, _) in E.ANSWERS.items()}
    src = "src/extract/pq_more.py"
    rows = [_rec("PQE-01", PQE_T, "; ".join(f for f, _, _ in E.ANSWERS.values()),
                 "the five answers",
                 "Five further include = yes parliamentary answers supplied by the author "
                 "(SHA-256 verified against data/source_manifest.csv) were read and entered "
                 "in the inventory after the source-choice freeze (dbb71b3), the guard "
                 "addendum (11cfbe4) and the Part D addendum, before any Q1-Q3 "
                 "computation; no frozen row is changed",
                 f"{len(inv)} inventory rows", "§5.3; §5.4; §13 (Part E, 19 November "
                 "2026)", "figures_inventory.csv; inventory_scope_decisions.csv; "
                 "pq_more_inventory_provenance.csv", d)]
    roles = {
        "Q278": "Q1-Q2 inventory (campaign selection figures); not a Q4 source (§9.5); no "
                "State ACF table, so no Q3 table",
        "Q279": "Q1-Q2 inventory (campaign selection figures); not a Q4 source; no Q3 "
                "table",
        "Q2051": "Q1-Q2 inventory (campaign selection figures); not a Q4 source; no Q3 "
                 "table",
        "LSQ79": "Q1-Q2 inventory (campaign selection, cascade to 7 Feb 2025 and "
                 "participation figures); a Word file read with zipfile and xml.etree "
                 "(§11); not a Q4 source; no Q3 table",
        "Q414": "data/extracted only: State tables of presumptive TB tests, notifications, "
                "treatment initiation and deaths (Annexure-I) and drug-resistant TB tests, "
                "diagnosis and treatment (Annexure-II), 2019-2023; programme-wide, not ACF "
                "or campaign figures and not named in §7.4 (§5.1; SRC-04), so no inventory "
                "row; no ACF numerator, so no Q3 table (§8.1); not a Q4 source (§9.5)",
    }
    for k, key in enumerate(("Q278", "Q279", "Q2051", "LSQ79", "Q414"), start=2):
        f, q, date = E.ANSWERS[key]
        rows.append(_rec(f"PQE-{k:02d}", PQE_T, f, q, f"{q}, answered {date}: role",
                         f"{n[key]} inventory rows; " + roles[key],
                         "§5.1; §5.3; §8.1; §9.5" + ("; SRC-04" if key == "Q414" else ""),
                         src, d))
    checks = [c for c in _read("table_total_checks.csv") if c["source_file"] == E.Q414_FILE]
    tables = sorted({c["table"].split(":")[0] for c in checks})
    rows.append(_rec("PQE-07", PQE_T, E.Q414_FILE, "Annexures I and II, PDF pages 2-12",
                     "Printed-total checks of the ten Q414 State tables (one per column)",
                     f"{len(checks)} checks, all 'not applied': no table prints a Total or "
                     "India row (text layer and page image)", "§6.2 check 3",
                     "; ".join(tables) + "; data/extracted/pq_q414_annexurei_<year>.csv, "
                     "pq_q414_annexureii_<year>.csv; table_total_checks.csv", d))
    labs = _label_resolutions(lambda f: f in E.OWN_FILES)
    rows.append(_rec("PQE-08", PQE_T, E.Q414_FILE, "State labels of the Q414 tables",
                     "Label rule (§9.2) applied to every printed label",
                     "; ".join(f"'{lab}' step {st} -> {c}" for (_, lab), (st, c, _)
                               in sorted(labs.items())) or "every label mapped at step 1",
                     "§9.2 label rule; §11", "", d))
    rows.append(_rec("PQE-09", PQE_T, E.Q414_FILE, "unit coarsening",
                     "Units of the Q414 tables coarsened (§9.4)",
                     "Jammu and Kashmir with Ladakh, and Dadra and Nagar Haveli with Daman "
                     "and Diu, as before; no other pair found", "§9.4",
                     "coarse_unit column of the extracted CSVs", d))
    rows.append(_rec("PQE-10", PQE_T,
                     "https://www.mha.gov.in/sites/default/files/AdvisoryPR_08012025.pdf",
                     "MHA advisory to prisons, '100-Day Intensified Campaign on TB "
                     "Elimination' (8 January 2025), include = yes in data/search_log.csv",
                     "MHA prison advisory of 8 January 2025",
                     "unavailable: the official URL returns 404 (file removed); an "
                     "Internet Archive copy exists but was not obtained",
                     "§3.3 (a source that cannot be obtained is reported as unavailable)",
                     "no figure entered from it; Internet Archive copy "
                     "http://web.archive.org/web/20250503135936/https://www.mha.gov.in/"
                     "sites/default/files/AdvisoryPR_08012025.pdf, found through the "
                     "Wayback availability API on 2026-11-19, not obtained", d))
    return rows


def build() -> list[dict]:
    rows = (exposure() + lgd() + labels_() + totals() + named() + scope() + quality()
            + general() + q4() + outcome_tables() + trend() + coarsening() + q3_tables()
            + guard_rows() + online_rows() + pq_more_rows())
    ids = [r["decision_id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate decision_id: {dup}")
    return rows


def main() -> int:
    rows = build()
    with open(OUT, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"source_choices.csv: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
