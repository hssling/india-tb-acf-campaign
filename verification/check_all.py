# Copied from hssling/india-state-tb-score (MIT), verification/check_all.py, commit 05bcaa7; modified: steps are pytest and the four checks of this repository (no analysis re-run, no manuscript checks); PASS/FAIL/SKIP labels
"""Run the whole verification: pytest and the checks (plan order, deviations, extraction totals, inventory
trace, recomputed Q3/Q4 outputs).

Run as: python -I verification/check_all.py   (steps run from the repo root)

Steps run as `python -I ...` subprocesses and print PASS, FAIL or SKIP. A step that prints
a line beginning "SKIPPED" (check_plan_order in a copy without .git) counts as skipped.
Prints "N/N checks passed (k skipped)"; exits 1 on any FAIL.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = [sys.executable, "-I"]

STEPS = [
    ("pytest -q", PY + ["-m", "pytest", "-q"]),
    ("check_plan_order", PY + ["verification/check_plan_order.py"]),
    ("check_deviations", PY + ["verification/check_deviations.py"]),
    ("check_extraction_totals", PY + ["verification/check_extraction_totals.py"]),
    ("check_inventory", PY + ["verification/check_inventory.py"]),
    ("check_outputs", PY + ["verification/check_outputs.py"]),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def tail(text: str, n: int = 15) -> str:
    return "\n".join("    " + ln for ln in text.strip().splitlines()[-n:])


def main() -> int:
    tally = {"passed": 0, "failed": 0, "skipped": 0}
    for name, cmd in STEPS:
        r = run(cmd)
        out = r.stdout + r.stderr
        if r.returncode != 0:
            tally["failed"] += 1
            print(f"[FAIL] {name}\n{tail(out)}")
        elif any(ln.startswith("SKIPPED") for ln in out.splitlines()):
            tally["skipped"] += 1
            print(f"[SKIP] {name}\n{tail(out)}")
        else:
            tally["passed"] += 1
            last = out.strip().splitlines()[-1] if out.strip() else ""
            print(f"[PASS] {name}: {last}")
    total = tally["passed"] + tally["failed"]
    note = f" ({tally['skipped']} skipped)" if tally["skipped"] else ""
    print(f"\n{tally['passed']}/{total} checks passed{note}")
    return 1 if tally["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
