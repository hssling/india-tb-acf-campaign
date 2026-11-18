"""LGD district count per State/UT at the end of 7 December 2024 (analysis plan §9.3).

Rule, without discretion:
- start from the current list "All Districts of India" (downloaded 18 November 2026);
- reverse every modification in the modification report dated on or after
  8 December 2024, latest first; modifications dated 7 December 2024 are kept;
- the date of each row is its effective date if the row gives one, otherwise its
  modification date; the field used is logged;
- a district created is removed, abolished is restored, renamed keeps its count,
  moved between States is moved back; a split or merger is undone through the rows
  that record the districts created or abolished;
- a State with a modification that cannot be reversed from the fields the report
  gives cannot be reconstructed: it is listed and its count is not computable.

The xlsx and SpreadsheetML files are read with zipfile and xml.etree only.

Run: python -I src/extract/lgd.py   (writes data/extracted/lgd_districts_2024-12-07.csv
and data/extracted/lgd_reconstruction_log.csv)
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import date, datetime

from src import states
from src.extract import labels

ROOT = Path(__file__).resolve().parents[2]
CURRENT = "data_raw/lgd/All_Districtof_India_2026-11-18_21-18-59.xlsx"
MODS = "data_raw/lgd/alldistrictbyDate2026_11_18_21_20_13_069.xls"
OUT = ROOT / "data/extracted/lgd_districts_2024-12-07.csv"
LOG = ROOT / "data/extracted/lgd_reconstruction_log.csv"
REFERENCE = date(2024, 12, 7)

# Deviation of §13 (19 November 2026): reconstruction from official notices.
EVIDENCE = ROOT / "data/lgd_evidence"
OUT_R = ROOT / "data/extracted/lgd_districts_2024-12-07_reconstructed.csv"
LOG_R = ROOT / "data/extracted/lgd_reconstruction_log_reconstructed.csv"

_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_SS = "{urn:schemas-microsoft-com:office:spreadsheet}"


# ------------------------------------------------------------------ readers

def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _num_text(v: str) -> str:
    """'552.0' -> '552'; other text unchanged."""
    if re.fullmatch(r"-?\d+\.0+", v):
        return v.split(".")[0]
    return v


def read_xlsx_rows(path: Path) -> list[list[str]]:
    """Rows of the first worksheet as lists of cell texts (blank where empty)."""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(si.itertext()) for si in sst.iter(_X + "si")]
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for r in root.iter(_X + "row"):
        cells: dict[int, str] = {}
        for c in r.findall(_X + "c"):
            t = c.get("t")
            if t == "inlineStr":
                v = "".join(c.find(_X + "is").itertext())
            else:
                ve = c.find(_X + "v")
                v = ve.text if ve is not None and ve.text is not None else ""
                if t == "s" and v:
                    v = shared[int(v)]
                elif t in (None, "n"):
                    v = _num_text(v)
            cells[_col_index(c.get("r"))] = v.strip()
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


def read_spreadsheetml_rows(path: Path) -> list[list[str]]:
    """Rows of the first Worksheet of an XML Spreadsheet 2003 file."""
    root = ET.parse(path).getroot()
    ws = next(root.iter(_SS + "Worksheet"))
    rows = []
    for r in ws.iter(_SS + "Row"):
        cells: dict[int, str] = {}
        i = 0
        for c in r.findall(_SS + "Cell"):
            idx = c.get(_SS + "Index")
            i = int(idx) - 1 if idx else i
            d = c.find(_SS + "Data")
            cells[i] = _num_text("".join(d.itertext()).strip()) if d is not None else ""
            i += 1
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(k, "") for k in range(width)])
    return rows


# ------------------------------------------------------------------ parsing

def _find_header(rows: list[list[str]], needle: str) -> int:
    for i, r in enumerate(rows):
        if any(c.strip().lower() == needle for c in r):
            return i
    raise ValueError(f"no header row with {needle!r}")


def _col(header: list[str], *patterns: str) -> int | None:
    for j, h in enumerate(header):
        hl = h.lower()
        if all(p in hl for p in patterns):
            return j
    return None


def parse_current(rows: list[list[str]]) -> list[dict]:
    h = _find_header(rows, "district code")
    header = rows[h]
    cs, cd, cn = (_col(header, "state name"), _col(header, "district code"),
                  _col(header, "district name"))
    out = []
    for r in rows[h + 1:]:
        r = r + [""] * (len(header) - len(r))
        if not r[cd].isdigit():
            continue  # blank or footer row (report time stamp)
        out.append({"state_label": r[cs], "district_code": r[cd],
                    "district_name": r[cn]})
    return out


def parse_modifications(rows: list[list[str]]) -> tuple[list[str], list[dict]]:
    """(fields the report gives, rows). Missing fields are blank in every row."""
    h = _find_header(rows, "district code")
    header = rows[h]
    def first(*alternatives: tuple[str, ...]) -> int | None:
        for pats in alternatives:
            j = _col(header, *pats)
            if j is not None:
                return j
        return None

    cols = {
        "district_code": first(("district code",)),
        "district_name": first(("district name",)),
        "state_label": first(("state name",)),
        "effective_date": first(("effective",)),
        "modification_date": first(("modification", "date"), ("modified", "date")),
        "type": first(("type",), ("operation",)),
        "previous_state_label": first(("previous", "state"), ("old", "state")),
    }
    fields = [h for h in header if h.strip()]  # every column the report gives
    out = []
    for i, r in enumerate(rows[h + 1:], start=h + 2):
        r = r + [""] * (len(header) - len(r))
        if not r[cols["district_code"]].isdigit():
            continue  # blank or footer row (report time stamp)
        rec = {"row": i}
        for k, j in cols.items():
            rec[k] = r[j] if j is not None else ""
        out.append(rec)
    return fields, out


def parse_date(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unreadable date: {s!r}")


_KINDS = {
    "created": "created", "create": "created", "new": "created",
    "abolished": "abolished", "abolish": "abolished", "deleted": "abolished",
    "renamed": "renamed", "rename": "renamed", "name change": "renamed",
    "moved": "moved", "shifted": "moved",
}


def _canon(label: str, resolutions: dict) -> str:
    """Canonical name by the label rule; "" for a label that stays unmapped (§9.2,
    step 3: its rows are listed and not counted)."""
    r = labels.resolve_or_list(label)
    if r.step >= 2:
        resolutions[label] = r
    return r.canonical


# ------------------------------------------------------------------ reconstruction

def reconstruct(current: list[dict], mods: list[dict], reference: date = REFERENCE,
                resolutions: dict | None = None,
                unmapped: list | None = None) -> tuple[dict, list[dict]]:
    """Per canonical State: current_count, count at the end of `reference` (None if
    not reconstructable), reconstructable, reason, modification_rows; and the log.
    Rows whose State label stays unmapped are listed in `unmapped`, not counted."""
    res = resolutions if resolutions is not None else {}
    lost = unmapped if unmapped is not None else []
    counts: Counter = Counter()
    for c in current:
        s = _canon(c["state_label"], res)
        if s:
            counts[s] += 1
        else:
            lost.append({"list": "current", "state_label": c["state_label"],
                         "district_code": c["district_code"]})
    out = {s: {"current_count": n, "count": n, "reconstructable": "yes", "reason": "",
               "modification_rows": 0} for s, n in counts.items()}
    log: list[dict] = []
    todo = []

    def _state(s: str) -> dict:
        return out.setdefault(s, {"current_count": 0, "count": 0, "reconstructable": "yes",
                                  "reason": "", "modification_rows": 0})

    def _fail(s: str, why: str) -> None:
        st = _state(s)
        st["reconstructable"] = "no"
        st["reason"] = (st["reason"] + "; " if st["reason"] else "") + why

    for m in mods:
        state = _canon(m["state_label"], res)
        if not state:
            lost.append({"list": "modifications", "state_label": m["state_label"],
                         "district_code": m["district_code"]})
            log.append({"row": m["row"], "district_code": m["district_code"],
                        "district_name": m["district_name"], "state": "",
                        "date_field": "", "date": "", "type": m["type"],
                        "action": "not computable: State label unmapped (§9.2, step 3)",
                        "effect": ""})
            continue
        _state(state)["modification_rows"] += 1
        entry = {"row": m["row"], "district_code": m["district_code"],
                 "district_name": m["district_name"], "state": state,
                 "date_field": "", "date": "", "type": m["type"], "action": "",
                 "effect": ""}
        if m["effective_date"]:
            entry["date_field"], d = "effective date", parse_date(m["effective_date"])
        elif m["modification_date"]:
            entry["date_field"], d = "modification date", parse_date(m["modification_date"])
        else:
            entry["date_field"], d = "none given", None
        entry["date"] = d.isoformat() if d else ""
        if d is None:
            why = "the report gives no effective or modification date for this row"
            entry["action"] = "not reversible: " + why
            _fail(state, f"report row {m['row']}: " + why)
            log.append(entry)
            continue
        if d <= reference:
            entry["action"] = "kept: in force on the reference date"
            log.append(entry)
            continue
        kind = _KINDS.get(m["type"].strip().lower())
        if kind is None:
            why = ("the report gives no modification type for this row" if not m["type"]
                   else f"modification type {m['type']!r} cannot be reversed from the "
                        "fields the report gives")
            entry["action"] = "not reversible: " + why
            _fail(state, f"report row {m['row']}: " + why)
            log.append(entry)
            continue
        if kind == "moved" and not m["previous_state_label"]:
            why = "a move without the previous State"
            entry["action"] = "not reversible: " + why
            _fail(state, f"report row {m['row']}: " + why)
            log.append(entry)
            continue
        todo.append((d, m["row"], kind, state, m, entry))

    for d, _, kind, state, m, entry in sorted(todo, key=lambda t: (t[0], t[1]),
                                              reverse=True):
        st = _state(state)
        if kind == "created":
            st["count"] -= 1
            entry["action"], entry["effect"] = "reversed: district removed", f"{state} -1"
        elif kind == "abolished":
            st["count"] += 1
            entry["action"], entry["effect"] = "reversed: district restored", f"{state} +1"
        elif kind == "renamed":
            entry["action"], entry["effect"] = "reversed: rename (count unchanged)", "0"
        else:
            prev = _canon(m["previous_state_label"], res)
            if not prev:
                _fail(state, f"report row {m['row']}: previous State label unmapped")
                entry["action"] = "not reversible: previous State label unmapped"
                log.append(entry)
                continue
            st["count"] -= 1
            _state(prev)["count"] += 1
            entry["action"] = "reversed: district moved back"
            entry["effect"] = f"{state} -1; {prev} +1"
        log.append(entry)

    for st in out.values():
        if st["reconstructable"] == "no":
            st["count"] = None
    return out, log


# ------------------------------------------------------------------ main

def _verify_inputs() -> None:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import read_manifest, verify
    pins = {r["file"]: r["sha256"] for r in read_manifest()}
    for f in (CURRENT, MODS):
        verify(ROOT / f, pins[f])


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run() -> tuple[dict, list[dict], list[str], dict]:
    _verify_inputs()
    current = parse_current(read_xlsx_rows(ROOT / CURRENT))
    fields, mods = parse_modifications(read_spreadsheetml_rows(ROOT / MODS))
    resolutions: dict = {}
    unmapped: list = []
    out, log = reconstruct(current, mods, resolutions=resolutions, unmapped=unmapped)
    if unmapped:
        print(f"State labels unmapped (rows listed, not counted): {unmapped}")
    return out, log, fields, resolutions


def _summary(state: str, log: list[dict]) -> str:
    bad = [e for e in log if e["state"] == state and e["action"].startswith("not reversible")]
    whys = sorted({e["action"].removeprefix("not reversible: ") for e in bad})
    rows = ", ".join(str(e["row"]) for e in bad)
    return (f"{len(bad)} modification row(s) cannot be reversed from the fields the "
            f"report gives (report rows {rows}): " + "; ".join(whys))


# ================================================================== §13 deviation
# District denominator reconstructed from official notices (§13, 19 November 2026).
# The evidence (data/lgd_evidence/) is applied mechanically; the rulings below settle
# the judgement points that the evidence search left open.

RULING_LGD_FEED = (
    "ruling 1: the LGD public district feed record for a district code counts as 'the "
    "LGD public page for that district'; its effective date is the date used, and it "
    "suffices to show that a district existed before 8 December 2024")
RULINGS: dict[str, dict] = {
    "AR-01": {"note": "ruling 2: Bichom is undone on the LGD effective date of 10 January "
                      "2025 (the only dated official source), so Arunachal Pradesh = 26; "
                      "it would be 27 if the commencement of the State Act (Act 2 of 2024) "
                      "predated 8 December 2024"},
    "DL-04": {"note": "ruling 3: Shahdara is abolished by the notification of 25 December "
                      "2025, which fixes the complete list of districts in force 'in "
                      "supersession of all previous notifications'"},
    "GJ-01": {"date": "2025-09-24",
              "note": "ruling 4: the LGD effective date (24 September 2025) is used, not "
                      "the district website's 2 October 2025; both are after the "
                      "reference date"},
}
for _i in range(1, 10):
    RULINGS[f"RJ-{_i:02d}"] = {
        "note": "ruling 5: restored; both candidate dates (Gazette 29 December 2024, "
                "listing 30 December 2024) fall after the cut-off"}

# effect on the count at the reference date of undoing a change of each type
_UNDO = {"created": -1, "split": -1, "abolished": +1, "merged": +1,
         "renamed": 0, "other": 0}


def read_evidence(folder: Path = EVIDENCE) -> tuple[list[dict], list[dict]]:
    """(changes, row accounting) from the evidence folder."""
    with open(folder / "changes.csv", newline="", encoding="utf-8") as f:
        changes = list(csv.DictReader(f))
    with open(folder / "rows.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return changes, rows


def _blank_state() -> dict:
    return {"current_count": 0, "count": 0, "computable": "yes", "reason": "",
            "modification_rows": 0, "rows_accounted": 0, "undone_created": 0,
            "restored": 0, "moves_reversed": 0}


def reconstruct_from_evidence(current: list[dict], mods: list[dict], changes: list[dict],
                              accounting: list[dict], reference: date = REFERENCE,
                              rulings: dict | None = None) -> tuple[dict, list[dict]]:
    """Per canonical State: current count, reconstructed count (None if not
    computable), and the reversal log.

    count = current - created + abolished/merged-away, with moves reversed, using only
    changes dated after `reference` (a change dated on the reference date is kept).
    Every modification row of the State must be accounted for in `accounting` (by a
    change id of that State, or by 'existed-before' with a source); otherwise the
    State is not computable."""
    rulings = RULINGS if rulings is None else rulings
    res: dict = {}
    out: dict[str, dict] = {}
    for c in current:
        s = _canon(c["state_label"], res)
        if s:
            x = out.setdefault(s, _blank_state())
            x["current_count"] += 1
            x["count"] += 1

    def fail(s: str, why: str) -> None:
        x = out.setdefault(s, _blank_state())
        x["computable"] = "no"
        x["reason"] = (x["reason"] + "; " if x["reason"] else "") + why

    log: list[dict] = []
    state_of: dict[str, str] = {}
    for ch in changes:
        s = _canon(ch["state"], res)
        cid = ch["change_id"]
        state_of[cid] = s
        rule = rulings.get(cid, {})
        d = parse_date(rule.get("date", ch["date"]))
        notes = [rule["note"]] if "note" in rule else []
        if "lgdirectory.gov.in" in ch["source_url"]:
            notes.append(RULING_LGD_FEED)
        entry = {"change_id": cid, "state": s, "district_code": ch["district_code"],
                 "district_name": ch["district_name"], "change_type": ch["change_type"],
                 "date": d.isoformat() if d else "",
                 "date_kind": "effective (LGD record; ruling 4)" if "date" in rule
                 else ch["date_kind"],
                 "action": "", "effect": "", "source_url": ch["source_url"],
                 "ruling": "; ".join(notes)}
        kind = ch["change_type"].strip().lower()
        x = out.setdefault(s, _blank_state())
        if d is None:
            entry["action"] = "not applied: no date"
            fail(s, f"change {cid} has no date")
        elif d <= reference:
            entry["action"] = "kept: in force on the reference date"
        elif kind == "moved":
            entry["action"] = "not applied: the evidence gives no previous State"
            fail(s, f"change {cid}: move without previous State")
        elif kind not in _UNDO:
            entry["action"] = f"not applied: change type {kind!r} cannot be undone"
            fail(s, f"change {cid}: type {kind!r}")
        else:
            delta = _UNDO[kind]
            x["count"] += delta
            if delta < 0:
                x["undone_created"] += 1
                entry["action"], entry["effect"] = "undone: district removed", f"{s} -1"
            elif delta > 0:
                x["restored"] += 1
                entry["action"], entry["effect"] = "undone: district restored", f"{s} +1"
            else:
                entry["action"], entry["effect"] = "undone: count unchanged", "0"
        log.append(entry)

    acc = {(str(r["row"]), r["district_code"]): r for r in accounting}
    for m in mods:
        s = _canon(m["state_label"], res)
        if not s:
            continue
        x = out.setdefault(s, _blank_state())
        x["modification_rows"] += 1
        a = acc.get((str(m["row"]), m["district_code"]))
        tokens = [t.strip() for t in a["accounted_by"].split(";") if t.strip()] if a else []
        ok = bool(tokens)
        for t in tokens:
            if t == "existed-before":
                ok = ok and bool(a["source_url"].strip())
            else:
                ok = ok and state_of.get(t) == s
        if ok:
            x["rows_accounted"] += 1
        else:
            fail(s, f"report row {m['row']} (code {m['district_code']}) not accounted for")
    for x in out.values():
        if x["computable"] == "no":
            x["count"] = None
    return out, log


def run_reconstructed() -> tuple[dict, list[dict]]:
    _verify_inputs()
    current = parse_current(read_xlsx_rows(ROOT / CURRENT))
    _, mods = parse_modifications(read_spreadsheetml_rows(ROOT / MODS))
    changes, accounting = read_evidence()
    return reconstruct_from_evidence(current, mods, changes, accounting)


def write_reconstructed() -> dict:
    out, log = run_reconstructed()
    with open(EVIDENCE / "states.csv", newline="", encoding="utf-8") as f:
        ev = {r["state"]: r for r in csv.DictReader(f)}
    rows = []
    for s in sorted(out):
        x = out[s]
        e = ev.get(s)
        cnt = "" if x["count"] is None else x["count"]
        rows.append({
            "state": s, "coarse_unit": states.coarsen(s),
            "current_count": x["current_count"],
            "modification_rows": x["modification_rows"],
            "rows_accounted": x["rows_accounted"],
            "created_undone": x["undone_created"], "abolished_restored": x["restored"],
            "moves_reversed": x["moves_reversed"], "computable": x["computable"],
            "count_2024_12_07": cnt,
            "evidence_count": e["reconstructed_count"] if e else "",
            "matches_evidence": "" if not e else
            ("yes" if str(cnt) == e["reconstructed_count"] else "no"),
            "reason": x["reason"],
            "basis": ("§13 deviation (19 November 2026): reconstruction from official "
                      "notices" if x["modification_rows"] else
                      "no modification row: current count, as under §9.3")})
    _write(OUT_R, list(rows[0]), rows)
    _write(LOG_R, ["change_id", "state", "district_code", "district_name", "change_type",
                   "date", "date_kind", "action", "effect", "source_url", "ruling"], log)
    return out


def main() -> int:
    out, log, fields, resolutions = run()
    labels_by_state: dict[str, str] = {}
    for c in parse_current(read_xlsx_rows(ROOT / CURRENT)):
        labels_by_state.setdefault(labels.resolve_or_list(c["state_label"]).canonical,
                                   c["state_label"])
    rows = []
    for s in sorted(out):
        st = out[s]
        r = resolutions.get(labels_by_state.get(s, ""))
        rows.append({
            "state": s, "coarse_unit": states.coarsen(s),
            "lgd_label": labels_by_state.get(s, ""),
            "label_rule_step": r.step if r else 1,
            "label_evidence": r.evidence if r else "",
            "current_count": st["current_count"],
            "modification_rows": st["modification_rows"],
            "reconstructable": st["reconstructable"],
            "count_2024_12_07": "" if st["count"] is None else st["count"],
            "reason": _summary(s, log) if st["reconstructable"] == "no" else "",
            "source_current": CURRENT, "source_modifications": MODS,
            "report_fields": "; ".join(fields),
        })
    _write(OUT, list(rows[0]), rows)
    _write(LOG, ["row", "district_code", "district_name", "state", "date_field", "date",
                 "type", "action", "effect"], log)
    n_no = sum(1 for r in rows if r["reconstructable"] == "no")
    print(f"{len(rows)} States/UTs; {len(log)} modification rows; "
          f"{n_no} not reconstructable; fields given: {fields}")
    rec = write_reconstructed()
    n_no = sum(1 for x in rec.values() if x["computable"] == "no")
    print(f"reconstructed (§13 deviation): {n_no} States not computable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
