# Copied from hssling/india-state-tb-score (MIT), verification/check_plan_order.py, commit 05bcaa7; modified: registration commit read from docs/registration_event.json (2a422a2); byte-identical frozen text; guarded paths are outputs/ and the Q computation modules; LGD-deviation commit 0ebcca1 must precede the first outcome-data commit
"""Check that the analysis plan was registered before any Q computation or output.

Run as: python -I verification/check_plan_order.py

1. The text of docs/analysis_plan.md above the "## 13. Deviations" heading is
   byte-identical at the registration commit and at every commit in registration..HEAD
   (git rev-list, merged side branches included), so an edit that was later reverted is
   also caught.
2. The registration commit is an ancestor of HEAD and a strict ancestor of every commit
   touching outputs/ or a Q computation module (src/q1_consistency.py,
   src/q2_reconcile.py, src/q3_yield.py, src/q4_dose_response.py).
3. The LGD-deviation commit (0ebcca1, plan section 13) is a strict ancestor of every
   commit that touched outcome data: data/extracted/**/pq_*.csv or itr20*_a1_2.csv (file
   names matched at any depth over the full history, deletions included; --no-renames, so a
   rename is listed as a deletion and an addition and both names are matched).

In a copy without .git (a release archive) the history cannot be checked: this prints
"SKIPPED: not a git checkout ..." and exits 0; check_all counts the step as skipped.
"""
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LGD_DEVIATION = "0ebcca1"
GUARDED = ("outputs", "src/q1_consistency.py", "src/q2_reconcile.py", "src/q3_yield.py",
           "src/q4_dose_response.py")
OUTCOME_DIR = "data/extracted"
OUTCOME_DATA = ("pq_*.csv", "itr20*_a1_2.csv")   # file-name patterns, at any depth
PLAN = "docs/analysis_plan.md"
HEADING = b"## 13. Deviations"


def git(repo: Path, *args: str, ok=(0,), text=True) -> subprocess.CompletedProcess:
    kw = {"text": True, "encoding": "utf-8"} if text else {}
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, **kw)
    if r.returncode not in ok:
        err = r.stderr if text else r.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip()}")
    return r


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", a, b, ok=(0, 1)).returncode == 0


def plan_above_section13(repo: Path, rev: str) -> bytes:
    """The bytes of the plan above the line '## 13. Deviations' (exactly one such line)."""
    data = git(repo, "show", f"{rev}:{PLAN}", text=False).stdout
    pos, found = 0, []
    for line in data.split(b"\n"):
        if line.rstrip(b"\r") == HEADING:
            found.append(pos)
        pos += len(line) + 1
    if len(found) != 1:
        raise RuntimeError(f"{PLAN} at {rev}: expected one {HEADING.decode()!r} heading, "
                           f"found {len(found)}")
    return data[:found[0]]


def commits_touching_names(repo: Path, directory: str, patterns: tuple[str, ...]) -> list[str]:
    """Commits (full history, no simplification) that touch a file under `directory`
    whose base name matches a pattern, at any depth; deletions and renames included."""
    out = git(repo, "log", "--full-history", "--no-renames", "--name-only", "--format=%x00%H",
              "--", directory).stdout
    hits = []
    for block in out.split("\x00")[1:]:
        sha, *names = block.split("\n")
        if any(fnmatch.fnmatchcase(n.rsplit("/", 1)[-1], pat) for n in names if n.strip()
               for pat in patterns):
            hits.append(sha.strip())
    return hits


def registered_commit(repo: Path) -> str:
    return json.loads((repo / "docs" / "registration_event.json")
                      .read_text(encoding="utf-8"))["registered_commit"]


def problems(repo: Path = ROOT, registration: str | None = None,
             guarded: tuple[str, ...] = GUARDED, lgd: str | None = LGD_DEVIATION,
             outcome: tuple[str, ...] = OUTCOME_DATA) -> list[str]:
    out: list[str] = []
    registration = registration or registered_commit(repo)
    reg = git(repo, "rev-parse", "--verify", f"{registration}^{{commit}}").stdout.strip()
    if not is_ancestor(repo, reg, "HEAD"):
        return [f"registration commit {registration[:7]} is not an ancestor of HEAD"]
    for c in git(repo, "log", "--full-history", "--format=%H", "--", *guarded).stdout.split():
        if c == reg or not is_ancestor(repo, reg, c):
            out.append(f"commit {c[:7]} touches outputs/ or a Q computation module but is "
                       f"not a descendant of the registration commit {registration[:7]}")
    frozen = plan_above_section13(repo, reg)
    for c in git(repo, "rev-list", f"{reg}..HEAD").stdout.split():
        try:
            same = plan_above_section13(repo, c) == frozen
        except RuntimeError as e:
            out.append(f"commit {c[:7]}: {PLAN} above section 13 cannot be read ({e})")
            continue
        if not same:
            out.append(f"commit {c[:7]}: {PLAN} above section 13 differs from its content at "
                       f"the registration commit {registration[:7]}")
    if lgd:
        lg = git(repo, "rev-parse", "--verify", f"{lgd}^{{commit}}").stdout.strip()
        for c in commits_touching_names(repo, OUTCOME_DIR, outcome):
            if c == lg or not is_ancestor(repo, lg, c):
                out.append(f"commit {c[:7]} touches outcome data (pq_*.csv, itr20*_a1_2.csv) "
                           f"but the LGD-deviation commit {lgd} is not its strict ancestor")
    return out


NOT_GIT = ("SKIPPED: not a git checkout (clone the repository to verify history and byte "
           "reproduction)")


def main(root: Path = ROOT) -> int:
    if not (root / ".git").exists():
        print(NOT_GIT)
        return 0
    bad = problems(root)
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    reg = registered_commit(root)
    n = len(git(root, "rev-list", f"{reg}..HEAD").stdout.split())
    print(f"OK: {reg[:7]} is an ancestor of HEAD; plan text above section 13 is "
          f"byte-identical across {n} later commits; no output or Q module commit precedes "
          f"it; {LGD_DEVIATION} precedes every outcome-data commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
