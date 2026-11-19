"""The guard of analysis plan §9.5.2 (Task 7 of the implementation plan)."""
from src import q4_dose_response as q4
from src import source_checks as sc

UNITS = [f"State {k:02d}" for k in range(12)]


def _tables(m23: float, m24: float, n: int = 12):
    """Q3467 counts of 1000 in every State; Q1216 counts give ratio m in every State,
    so the median is m."""
    q3467 = {y: {u: 1000 for u in UNITS[:n]} for y in (2023, 2024)}
    q1216 = {2023: {u: round(m23 * 1000) for u in UNITS[:n]},
             2024: {u: round(m24 * 1000) for u in UNITS[:n]}}
    return q1216, q3467


def test_guard_median_ratio_bounds():
    # a 2023 median of 1.00 with a 2024 median of 1.00 passes
    status, med, _ = q4.guard(*_tables(1.00, 1.00), True, True)
    assert status == "pass" and med[2023] == 1.0 and med[2024] == 1.0
    # a 2023 median of 0.94 fails
    assert q4.guard(*_tables(0.94, 1.00), True, True)[0] == "fail"
    # a 2024 median of 1.08 passes (with 2023 at 1.00), and is reported descriptively
    status, med, flagged = q4.guard(*_tables(1.00, 1.08), True, True)
    assert status == "pass" and med[2024] == 1.08
    assert flagged and all(f["year"] == 2024 and f["label"] == q4.LATE for f in flagged)
    # a 2024 median of 0.94 fails
    assert q4.guard(*_tables(1.00, 0.94), True, True)[0] == "fail"
    # a failure of Q1216's extraction checks gives fail, whatever the medians
    assert q4.guard(*_tables(1.00, 1.00), False, True)[0] == "fail"
    assert q4.guard(*_tables(1.00, 1.00), False, False)[0] == "fail"
    # a failed guard switches the primary to the January-October contrast and the
    # trend to the fallback sources
    c = q4.guard_consequences("fail")
    assert c["primary"] == "January-October 2025 vs 2024 (S8)"
    assert c["trend"][2023]["source"] == sc.ITR2024
    assert c["trend"][2024]["source"] == sc.Q3467
    c = q4.guard_consequences("pass")
    assert c["primary"] == "full-year 2025 vs 2024"
    assert c["trend"][2023]["source"] == sc.Q1216
    # fewer than 10 states with both values for either year gives not_run, with the
    # full-year contrast still primary
    q1216, q3467 = _tables(1.00, 1.00)
    for u in UNITS[9:]:
        del q3467[2024][u]
    assert q4.guard(q1216, q3467, True, True)[0] == "not_run"
    assert q4.guard_consequences("not_run")["primary"] == "full-year 2025 vs 2024"
    # Q3467 failing its extraction checks (Q1216 passing): not_run
    assert q4.guard(*_tables(1.00, 1.00), True, False)[0] == "not_run"


def test_guard_flags_q2_discrepancies_both_years():
    q1216, q3467 = _tables(1.00, 1.00)
    q1216[2023]["State 00"] = 1060      # 1.06 in 2023
    q1216[2024]["State 01"] = 940       # 0.94 in 2024
    q1216[2024]["State 02"] = 1100      # 1.10 in 2024
    _, _, flagged = q4.guard(q1216, q3467, True, True)
    got = {(f["state"], f["year"]): f["label"] for f in flagged}
    assert got == {("State 00", 2023): "", ("State 01", 2024): "",
                   ("State 02", 2024): q4.LATE}


def test_guard_leaves_out_states_missing_in_either_table():
    q1216, q3467 = _tables(1.00, 1.00)
    del q3467[2023]["State 00"]
    r = q4.ratios(q1216, q3467)
    assert "State 00" not in r[2023] and len(r[2023]) == 11 and len(r[2024]) == 12


def test_q4_module_imports_without_pdf_libraries():
    import subprocess
    import sys
    from pathlib import Path
    code = ("import sys; sys.path.insert(0, '.'); sys.modules['pdfplumber'] = None; "
            "import src.q4_dose_response")
    r = subprocess.run([sys.executable, "-I", "-c", code],
                       cwd=Path(__file__).resolve().parents[1],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
