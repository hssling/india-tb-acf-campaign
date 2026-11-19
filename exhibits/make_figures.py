# Adapted from hssling/india-state-tb-score (MIT), exhibits/make_figures.py, commit 05bcaa7; modified: rewritten for the ACF campaign study (Figure 1 timeline of national campaign claims, Figure 2 Q4 scatter with the WLS fit and the placebo); only the conventions (matplotlib Agg, greyscale, marker shape and fill carry identity, no numbers on the image, no timestamps in the files) are kept
"""Figures 1 and 2 of the manuscript: deterministic rendering of outputs/ and data/ by code.

Run as: python -I exhibits/make_figures.py   (from the repository root)

Matplotlib is required; if it is not installed the script prints a message to stderr and
exits 1.
Every figure is a plot of committed files (data/figures_inventory.csv, outputs/q4_states.csv,
outputs/q4_summary.csv). No image is generated, edited or retouched by artificial
intelligence or by hand. Output, in manuscript/exhibits/ (git-ignored, local):
- figure1.pdf / figure2.pdf   vector (Public Health accepts PDF or EPS);
- figure1.png / figure2.png   300 dpi raster, greyscale;
- figure1_data.csv / figure2_data.csv   the plotted points, with their source rows;
- figure_notes.md             what each figure plots, for the legends.
Greyscale only; no numbers are printed on the images.
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

try:
    import matplotlib
except ImportError:
    if __name__ != "__main__":
        raise
    print("make_figures: matplotlib is not installed; figures not built (tables are unaffected)",
          file=sys.stderr)
    sys.exit(1)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript" / "exhibits"
DPI = 300
MINUS = "−"
CAMPAIGN_START = "2024-12-07"
CAMPAIGN_LABELS = {"100-day campaign", "campaign to date", "since december 2024", "first 30 days"}
MARKERS = {"notified": "s", "diagnosed": "^", "unspecified": "o", "": "o"}


def read(rel: str) -> list[dict]:
    with open(ROOT / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(name: str, rows: list[dict]) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def claim_date(r: dict) -> str:
    """The date a claim is made for: the publication date, else the printed window end, else as_on."""
    return r["pub_date"] or r["window_end"] or r["as_on"]


def is_campaign_claim(r: dict) -> bool:
    """National claim of the campaign: India, screened or TB cases, linked to the campaign by its
    stated start (7 December 2024), its scope (phase 1, expanded campaign) or its window label."""
    if r["geography"] != "India" or r["quantity"] not in ("screened", "tb_cases"):
        return False
    d = claim_date(r)
    if not d or d < CAMPAIGN_START:
        return False
    return (r["window_start"] == CAMPAIGN_START or r["scope"] in ("phase 1", "expanded campaign")
            or r["window_label"] in CAMPAIGN_LABELS)


def stated_definition(r: dict, inv: list[dict]) -> str:
    """The definition class plotted for a claim. A claim whose own words state no definition takes the
    definition that the same document prints for the same quantity and value elsewhere, if exactly one
    is stated (for example, a release that calls 48.64 lakh both "new TB cases identified" and "TB
    Cases Detected": "detect" is the diagnosed keyword). Otherwise its own class is kept."""
    own = r["definition_class"] or "unspecified"
    if own != "unspecified":
        return own
    other = {x["definition_class"] for x in inv
             if x["source_file"] == r["source_file"] and x["quantity"] == r["quantity"]
             and x["value"] == r["value"] and x["definition_class"] not in ("", "unspecified")}
    return other.pop() if len(other) == 1 else own


def figure1_points() -> list[dict]:
    seen, pts = set(), []
    inv = read("data/figures_inventory.csv")
    for r in inv:
        if not is_campaign_claim(r):
            continue
        dc = stated_definition(r, inv)
        key = (r["source_file"], r["quantity"], r["value"], r["qualifier"], dc, claim_date(r))
        if key in seen:
            continue
        seen.add(key)
        pts.append({"fig_id": r["fig_id"], "quantity": r["quantity"], "value": r["value"],
                    "qualifier": r["qualifier"], "definition_class": dc,
                    "date": claim_date(r), "source_file": r["source_file"]})
    pts.sort(key=lambda p: (p["quantity"], p["date"], float(p["value"])))
    return pts


def figure2_points() -> tuple[list[dict], dict, dict]:
    st = [r for r in read("outputs/q4_states.csv") if r["denominator_set"] == "D" and r["computable"] == "yes"]
    summ = {r["analysis"]: r for r in read("outputs/q4_summary.csv") if r["denominator_set"] == "D"}
    main = [r for r in st if r["contrast"] == "full-year 2025 vs 2024"]
    plc = [r for r in st if r["contrast"] == "placebo 2023 vs 2022"]
    return main, plc, summ


def setup() -> None:
    plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.linewidth": 0.6,
                         "pdf.fonttype": 42, "svg.hashsalt": "acf", "axes.unicode_minus": True})


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None, "Creator": "", "Producer": ""})
    fig.savefig(OUT / f"{name}.png", dpi=DPI, metadata={"Software": None})
    plt.close(fig)


def figure1() -> list[dict]:
    pts = figure1_points()
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 5.6), sharex=True)
    for ax, q, ylab in ((axes[0], "screened", "People screened (millions)"),
                        (axes[1], "tb_cases", "TB cases diagnosed or notified (millions)")):
        for p in (p for p in pts if p["quantity"] == q):
            x = date.fromisoformat(p["date"])
            y = float(p["value"]) / 1e6
            hollow = p["qualifier"] != "exact"
            ax.scatter([x], [y], marker=MARKERS.get(p["definition_class"], "o"), s=34,
                       facecolor="white" if hollow else "black", edgecolor="black", linewidth=0.9, zorder=3)
        ax.set_ylabel(ylab)
        ax.grid(axis="y", color="#e0e0e0", linewidth=0.5)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[1].set_xlabel("Date of the published claim")
    handles = [Line2D([], [], marker=m, linestyle="", markerfacecolor="black", markeredgecolor="black", label=l)
               for l, m in (("Defined as notified", "s"), ("Defined as diagnosed", "^"), ("Definition not stated", "o"))]
    handles.append(Line2D([], [], marker="o", linestyle="", markerfacecolor="white", markeredgecolor="black",
                          label="Stated as a lower bound (hollow)"))
    axes[0].legend(handles=handles, loc="upper left", frameon=False, fontsize=8)
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    save(fig, "figure1")
    write_csv("figure1_data.csv", pts)
    return pts


YLIM_A = (-0.15, 0.35)  # panel A y-axis; units above the top edge are marked with an arrow


def figure2() -> list[dict]:
    main, plc, summ = figure2_points()
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.4), sharex=True)
    out = []
    for ax, rows, key, ylab, tag in ((axes[0], main, "primary", "Excess change in log notifications, 2025 vs 2024", "primary"),
                                     (axes[1], plc, "placebo", "Excess change in log notifications, 2023 vs 2022", "placebo")):
        ws = [float(r["w"]) for r in rows]
        wmax = max(ws)
        for r in rows:
            e, x, w = float(r["E"]), float(r["x"]), float(r["w"])
            if tag == "primary" and x > YLIM_A[1]:
                ax.scatter([e], [YLIM_A[1]], marker="^", s=40, facecolor="black", edgecolor="black", clip_on=False, zorder=5)
                out.append({"panel": tag, "unit": r["unit"], "E": r["E"], "x": r["x"], "w": r["w"]})
                continue
            ax.scatter([e], [x], s=10 + 70 * w / wmax, facecolor="#b0b0b0", edgecolor="black", linewidth=0.6, zorder=3)
            out.append({"panel": tag, "unit": r["unit"], "E": r["E"], "x": r["x"], "w": r["w"]})
        s = summ[key]
        e_lo, e_hi = min(float(r["E"]) for r in rows), max(float(r["E"]) for r in rows)
        g0, g1 = float(s["gamma0"]), float(s["gamma1"])
        ax.plot([e_lo, e_hi], [g0 + g1 * e_lo, g0 + g1 * e_hi], color="black", linewidth=1.2, zorder=4)
        if tag == "primary":
            ax.set_ylim(*YLIM_A)
        ax.axhline(0, color="#808080", linewidth=0.5, linestyle=":")
        ax.set_xlabel("Exposure: share of districts in the campaign (E)")
        ax.set_ylabel(ylab, fontsize=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_title("A" if tag == "primary" else "B", loc="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "figure2")
    write_csv("figure2_data.csv", out)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    setup()
    p1, p2 = figure1(), figure2()
    clip = [r for r in p2 if r["panel"] == "primary" and float(r["x"]) > YLIM_A[1]]
    clipped = " ".join(f"the unit {r['unit']} (E = {float(r['E']):.0f}, x = {float(r['x']):.2f}) lies above the top edge and is marked with an upward arrow at the edge; "
                       "the fitted line is the full fit including this unit." for r in clip)
    notes = [
        "# Figure notes (generated by exhibits/make_figures.py)\n",
        "## Figure 1\nNational claims of the 2024–2026 TB campaign in official documents, by the date of the claim "
        "(publication date; the printed window end where no publication date is given). Upper panel: people screened. "
        "Lower panel: TB cases diagnosed or notified. A claim enters when it is a national figure linked to the campaign "
        "by its stated start of 7 December 2024, by first-phase or expanded-campaign scope, or by a campaign window label; "
        "identical claims repeated in one document are plotted once. Marker shape: the definition printed with the figure "
        "(notified, diagnosed, or not stated); a claim whose own words state no definition takes the one the same "
        "document prints for the same value elsewhere, if exactly one is stated. Hollow marker: stated as a lower bound. "
        "Caption: the 48.64 lakh point (PIB release of 12 November 2026) is plotted as diagnosed: the release calls it "
        "\"new TB cases identified\" and also \"TB Cases Detected\". The 27.28 lakh point of the 2026 campaign document "
        "states no definition.\n",
        "## Figure 2\nThe dose–response analysis under the reconstructed district denominator (the main analysis, a "
        "deviation from the registered denominator). Panel A: excess change x in log notifications, 2025 against 2024, against the exposure share E, one point "
        "per State or Union Territory; point area proportional to the weight; line = weighted least-squares fit on all units. "
        "Panel A's y-axis is clipped to " + f"{YLIM_A[0]} to {YLIM_A[1]}".replace("-", MINUS) + "; " + clipped + " "
        "Panel B: the placebo contrast, 2023 against 2022, against the same exposure; its y-axis is not clipped. "
        "\n",
    ]
    (OUT / "figure_notes.md").write_text("\n".join(notes), encoding="utf-8", newline="\n")
    print(f"wrote figure1 ({len(p1)} points) and figure2 ({len(p2)} points) to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
