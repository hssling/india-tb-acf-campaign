# New for the extension (v1.1.0); keeps the conventions of exhibits/make_figures.py (matplotlib Agg, greyscale, marker shape and fill carry identity, no timestamps in the files)
"""Figures 1-4 of the extension paper: deterministic rendering of outputs/ext/ and outputs/ by code.

Run as: python -I exhibits/make_ext_figures.py [--out DIR]   (from the repository root)

Matplotlib and Pillow are required; if matplotlib is not installed the script prints a message
to stderr and exits 1. Every figure is a plot of committed output files; no image is generated,
edited or retouched by artificial intelligence or by hand. Output, in DIR (default
manuscript/ext/exhibits/, git-ignored and local):
- figureN.pdf          vector (Public Health accepts PDF or EPS);
- figureN.tif          600 dpi greyscale TIFF (LZW), rendered from the same figure;
- figureN.png          300 dpi greyscale preview;
- figure_trace.json    every plotted value and every number written on a figure, with its
                       output file, row, column and raw value (as trace.json for the tables);
- figure_notes.md      what each figure plots, for the legends.

  Figure 1  National yield and its cascade decomposition over time
  Figure 2  State yield tiers, 2021-2023 (registered intervals; robust tiers marked)
  Figure 3  Targeting: campaign district share against pooled yield; the illustrative scenario
  Figure 4  Robustness: the specification grid of the three headline estimates

Greyscale only; minus signs are U+2212. The files carry no creation dates, so a rebuild is
byte-identical.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

try:
    import matplotlib
except ImportError:
    if __name__ != "__main__":
        raise
    print("make_ext_figures: matplotlib is not installed; figures not built (tables are unaffected)",
          file=sys.stderr)
    sys.exit(1)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_ext_tables as et  # noqa: E402

ROOT = et.ROOT
OUT = et.OUT
FIGURES = ["figure1", "figure2", "figure3", "figure4"]
DPI_PNG = 300
DPI_TIFF = 600
MINUS = et.MINUS
GREY = "#8c8c8c"
LIGHT = "#d9d9d9"
Q4 = "outputs/q4_states.csv"
read = et.read


class FTrace:
    """Every plotted value (fmt 'raw') and every number written on a figure (its formatter)."""

    def __init__(self, exhibit: str) -> None:
        self.exhibit = exhibit
        self.entries: list[dict] = []

    def value(self, file: str, i: int, column: str, fmt: str = "raw") -> str:
        raw = read(file)[i][column]
        text = et.FORMATTERS[fmt](raw)
        self.entries.append({"exhibit": self.exhibit, "kind": "value", "file": file, "row": i,
                             "column": column, "raw": raw, "fmt": fmt, "text": text})
        return text

    def num(self, file: str, i: int, column: str) -> float:
        return float(self.value(file, i, column))

    def interval(self, file: str, i: int, col: str, lo: str, hi: str, fmt: str) -> str:
        return (f"{self.value(file, i, col, fmt)} ({self.value(file, i, lo, fmt)} to "
                f"{self.value(file, i, hi, fmt)})")


# --------------------------------------------------------------------------------------
# Data of each figure (read from the outputs and traced)
# --------------------------------------------------------------------------------------
def figure1_points(tr: FTrace | None = None) -> dict:
    tr = tr or FTrace("Figure 1")
    pooled, national = [], []
    for i, r in enumerate(read(et.POOL)):
        if r["analysis"] == "2021-2023":
            continue
        y = r["analysis"]
        pooled.append({"year": y, "mu": tr.num(et.POOL, i, "yield_per_100k"),
                       "ci": (tr.num(et.POOL, i, "ci_lo_per_100k"), tr.num(et.POOL, i, "ci_hi_per_100k")),
                       "pi": (tr.num(et.POOL, i, "pi_lo_per_100k"), tr.num(et.POOL, i, "pi_hi_per_100k"))})
        j = et.row_index(et.Q3S, state="India", year=y, indicator="yield_diagnosed_per_100000")
        national.append({"year": y, "value": tr.num(et.Q3S, j, "value")})
    change = []
    for q in ("dln_yield", "testing_part", "positivity_part"):
        i = et.row_index(et.DEC, analysis="change", status="main", quantity=q)
        change.append({"quantity": q, "est": tr.num(et.DEC, i, "estimate"),
                       "ci": (tr.num(et.DEC, i, "boot_lo"), tr.num(et.DEC, i, "boot_hi"))})
    share = []
    for i, r in enumerate(read(et.DEC)):
        if r["analysis"] == "variance" and r["quantity"] == "testing_share":
            share.append({"year": r["years"], "examined": r["testing_definition"] == "examined",
                          "est": tr.num(et.DEC, i, "estimate"),
                          "ci": (tr.num(et.DEC, i, "boot_lo"), tr.num(et.DEC, i, "boot_hi"))})
    share.sort(key=lambda s: s["year"])
    return {"pooled": pooled, "national": national, "change": change, "share": share}


TIER_ORDER = ["above", "overlaps", "below"]


def figure2_points(tr: FTrace | None = None) -> list[dict]:
    """One point per State with a pooled 2021-2023 value, grouped by registered tier (above,
    overlaps, below) and alphabetical within a tier: a tiered map, not a league table."""
    tr = tr or FTrace("Figure 2")
    st = {r["unit"]: i for i, r in enumerate(read(et.ST)) if r["analysis"] == "2021-2023"}
    pts = []
    for j, b in enumerate(read(et.STB)):
        i = st[b["unit"]]
        pts.append({"unit": b["unit"], "name": et.state(b["unit"]), "tier": read(et.ST)[i]["tier"],
                    "robust": tr.value(et.STB, j, "tier_agrees") == "yes",
                    "post": tr.num(et.ST, i, "post_per_100k"),
                    "ci": (tr.num(et.ST, i, "post_lo_per_100k"), tr.num(et.ST, i, "post_hi_per_100k")),
                    "b_ci": (tr.num(et.STB, j, "post_lo_per_100k"), tr.num(et.STB, j, "post_hi_per_100k"))})
    pts.sort(key=lambda p: (TIER_ORDER.index(p["tier"]), p["name"]))
    return pts


def figure2_mean(tr: FTrace) -> dict:
    i = et.row_index(et.POOL, analysis="2021-2023")
    return {"mu": tr.num(et.POOL, i, "yield_per_100k"),
            "ci": (tr.num(et.POOL, i, "ci_lo_per_100k"), tr.num(et.POOL, i, "ci_hi_per_100k"))}


def figure3_points(tr: FTrace | None = None) -> dict:
    tr = tr or FTrace("Figure 3")
    expo = {r["unit"]: i for i, r in enumerate(read(Q4))
            if r["denominator_set"] == "D" and r["contrast"] == "full-year 2025 vs 2024"}
    w23 = {r["unit"]: i for i, r in enumerate(read(et.ST)) if r["analysis"] == "2023"}
    q3 = {r["state"]: i for i, r in enumerate(read(et.Q3S))
          if r["year"] == "2023" and r["indicator"] == "yield_diagnosed_per_100000"}
    pts = []
    for i, r in enumerate(read(et.ST)):
        if r["analysis"] != "2021-2023":
            continue
        u = r["unit"]
        if u in w23:
            w = tr.num(et.ST, w23[u], "screened")
        else:  # a unit without a usable 2023 yield still has its printed 2023 number screened
            w = tr.num(et.Q3S, q3[u], "denominator")
        pts.append({"unit": u, "name": et.state(u), "E": tr.num(Q4, expo[u], "E"),
                    "y": tr.num(et.ST, i, "post_per_100k"), "w": w})
    h = et.row_index(et.H, estimate="rho")
    a = et.row_index(et.AL, analysis="unweighted")
    rho = {"weighted": tr.interval(et.H, h, "main_value", "ci_lo", "ci_hi", "dec2"),
           "unweighted": tr.interval(et.AL, a, "estimate", "boot_lo", "boot_hi", "dec2")}
    scen = []
    for key, label in (("main", "Registered tiers"), ("robust tiers (post hoc)", "Robust tiers\n(post hoc)")):
        i = et.row_index(et.SC, analysis=key)
        scen.append({"label": label, "delta": tr.num(et.SC, i, "delta"),
                     "ci": (tr.num(et.SC, i, "ci_lo"), tr.num(et.SC, i, "ci_hi")),
                     "text": tr.interval(et.SC, i, "delta", "ci_lo", "ci_hi", "round0")})
    return {"points": pts, "rho": rho, "scenario": scen}


def figure4_points(tr: FTrace | None = None) -> dict:
    """Panels: ε, ρ, θ on the absolute scale, θ on the log scale; entries sorted by value."""
    tr = tr or FTrace("Figure 4")
    panels: dict[str, list] = {"epsilon": [], "rho": [], "theta_absolute": [], "theta_log": []}
    for i, r in enumerate(read(et.SPEC)):
        key = r["estimate"] if r["estimate"] != "theta" else f"theta_{r['scale']}"
        panels[key].append({"entry": int(r["entry"]), "main": r["main"] == "yes",
                            "value": tr.num(et.SPEC, i, "value"),
                            "ci": (tr.num(et.SPEC, i, "ci_lo"), tr.num(et.SPEC, i, "ci_hi")),
                            "excludes": r["interval_excludes_null"] == "yes",
                            "null": tr.num(et.SPEC, i, "null")})
    for v in panels.values():
        v.sort(key=lambda p: (p["value"], p["entry"]))
    return panels


def figure4_titles(tr: FTrace) -> dict:
    out = {}
    for key, name in (("epsilon", "Elasticity (ε)"), ("rho", "Alignment (ρ)"),
                      ("theta", "Notifications (θ), absolute scale")):
        i = et.row_index(et.H, estimate=key)
        lab = read(et.H)[i]["label"]
        out[key] = (f"{name}\n{tr.value(et.H, i, 'n_agree', 'round0')} of "
                    f"{tr.value(et.H, i, 'n_entries', 'round0')} agree in sign "
                    f"({tr.value(et.H, i, 'agreement_share', 'pct0')}%); {lab}")
    return out


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
def setup() -> None:
    plt.rcParams.update({"font.size": 7.5, "font.family": "DejaVu Sans", "axes.linewidth": 0.6,
                         "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42,
                         "svg.hashsalt": "acf-ext", "axes.unicode_minus": True,
                         "axes.titlesize": 7.5, "legend.fontsize": 6.8})


def plain(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def minus(s: str) -> str:
    return s.replace("-", MINUS)


def log_axis(axis, ticks: list[float]) -> None:
    axis.set_major_locator(FixedLocator(ticks))
    axis.set_minor_locator(NullLocator())
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}"))


def panel_title(ax, letter: str, text: str = "") -> None:
    ax.set_title(f"{letter}  {text}".rstrip(), loc="left", fontweight="bold")


def render_figure1(d: dict):
    fig, axes = plt.subplots(1, 3, figsize=(7.48, 2.9), gridspec_kw={"width_ratios": [1.35, 0.95, 1.15]})
    ax = axes[0]
    xs = list(range(len(d["pooled"])))
    for x, p, n in zip(xs, d["pooled"], d["national"]):
        ax.plot([x - 0.12] * 2, p["pi"], color=GREY, linewidth=0.8, zorder=2)
        ax.plot([x - 0.12] * 2, p["ci"], color="black", linewidth=2.2, solid_capstyle="butt", zorder=3)
        ax.scatter([x - 0.12], [p["mu"]], marker="s", s=16, color="black", zorder=4)
        ax.scatter([x + 0.14], [n["value"]], marker="o", s=18, facecolor="white", edgecolor="black",
                   linewidth=0.9, zorder=4)
    ax.set_yscale("log")
    ax.set_ylim(1.5, 8000)  # headroom above the highest interval for the legend
    log_axis(ax.yaxis, [2, 5, 10, 20, 50, 100, 200, 500, 1000])
    ax.set_xticks(xs, [p["year"] for p in d["pooled"]])
    ax.set_xlim(-0.6, len(xs) - 0.4)
    ax.set_xlabel("Data year")
    ax.set_ylabel("ACF yield per 100,000 screened (log scale)")
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.5)
    ax.set_axisbelow(True)
    handles = [Line2D([], [], marker="s", color="black", linewidth=2.2, markersize=4,
                      label="Pooled State yield, 95% CI"),
               Line2D([], [], color=GREY, linewidth=0.8, label="95% prediction interval"),
               Line2D([], [], marker="o", linestyle="", markerfacecolor="white", markeredgecolor="black",
                      markersize=4.5, label="National yield")]
    ax.legend(handles=handles, loc="upper right", frameon=False, handlelength=1.6)
    panel_title(ax, "A")
    plain(ax)

    ax = axes[1]
    labels = {"dln_yield": "Yield", "testing_part": "Testing step", "positivity_part": "Positivity step"}
    for k, c in enumerate(d["change"]):
        y = len(d["change"]) - 1 - k
        ax.plot(c["ci"], [y, y], color="black", linewidth=1.0)
        ax.scatter([c["est"]], [y], marker="D" if c["quantity"] == "dln_yield" else "o", s=20,
                   color="black", zorder=3)
    ax.axvline(0, color=GREY, linewidth=0.6, linestyle="--")
    ax.set_yticks(range(len(d["change"])), [labels[c["quantity"]] for c in reversed(d["change"])])
    ax.set_ylim(-0.6, len(d["change"]) - 0.4)
    ax.set_xlabel("Change in log, 2021 to 2023 (95% CI)")
    panel_title(ax, "B")
    plain(ax)

    ax = axes[2]
    xs = list(range(len(d["share"])))
    for x, s in zip(xs, d["share"]):
        ax.plot([x, x], s["ci"], color="black", linewidth=1.0)
        ax.scatter([x], [s["est"]], marker="o", s=20, facecolor="white" if s["examined"] else "black",
                   edgecolor="black", linewidth=0.9, zorder=3)
    ax.axhline(0.5, color=GREY, linewidth=0.6, linestyle=":")
    ax.set_xticks(xs, [s["year"] for s in d["share"]], fontsize=6.5)
    ax.set_xlim(-0.6, len(xs) - 0.4)
    ax.set_ylim(0, 1.2)
    ax.set_xlabel("Data year")
    ax.set_ylabel("Testing share of between-State variance")
    handles = [Line2D([], [], marker="o", linestyle="", markerfacecolor="white", markeredgecolor="black",
                      markersize=4.5, label="People examined, not tested")]
    ax.legend(handles=handles, loc="lower left", frameon=False, handlelength=1.0)
    panel_title(ax, "C")
    plain(ax)
    fig.tight_layout(w_pad=1.2)
    return fig


TIER_LABEL = {"above": "Above the pooled mean", "overlaps": "Overlaps the pooled mean",
              "below": "Below the pooled mean"}


def render_figure2(pts: list[dict], mean: dict):
    fig, ax = plt.subplots(figsize=(5.6, 8.0))
    rows, y, ylabels, yticks, heads = [], 0.0, [], [], []
    for t in TIER_ORDER:
        sub = [p for p in pts if p["tier"] == t]
        if not sub:
            continue
        heads.append((t, y))
        y += 1
        for p in sub:
            rows.append((y, p))
            yticks.append(y)
            ylabels.append(p["name"])
            y += 1
        y += 0.4
    ax.axvspan(*mean["ci"], color="#efefef", zorder=0, linewidth=0)
    ax.axvline(mean["mu"], color=GREY, linewidth=0.8, linestyle="--", zorder=1)
    for yy, p in rows:
        ax.plot(p["b_ci"], [yy + 0.28] * 2, color=GREY, linewidth=0.7, zorder=2)
        ax.plot(p["ci"], [yy, yy], color="black", linewidth=1.6, solid_capstyle="butt", zorder=3)
        ax.scatter([p["post"]], [yy], marker="o", s=22, facecolor="black" if p["robust"] else "white",
                   edgecolor="black", linewidth=0.9, zorder=4)
    for t, yy in heads:  # a tier heading on its own row, above its States
        ax.text(1.6, yy + 0.15, f"Registered tier: {TIER_LABEL[t].lower()}", ha="left", va="center",
                fontweight="bold", fontsize=7)
    ax.set_xscale("log")
    ax.set_xlim(1.5, 400)
    log_axis(ax.xaxis, [2, 5, 10, 20, 50, 100, 200])
    ax.set_yticks(yticks, ylabels)
    ax.set_ylim(y - 0.4 + 0.2, -0.8)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Pooled ACF yield per 100,000 screened, 2021–2023 (log scale)", loc="right")
    plain(ax)
    handles = [Line2D([], [], marker="o", linestyle="", color="black", markersize=4.5,
                      label="Robust tier: the same under the between-year sensitivity"),
               Line2D([], [], marker="o", linestyle="", markerfacecolor="white", markeredgecolor="black",
                      markersize=4.5, label="Tier changes under the between-year sensitivity"),
               Line2D([], [], color="black", linewidth=1.6,
                      label="Registered 95% interval (plug-in: binomial variance only, so too narrow)"),
               Line2D([], [], color=GREY, linewidth=0.7,
                      label="Between-year 95% interval (post hoc sensitivity)"),
               Line2D([], [], color=GREY, linewidth=0.8, linestyle="--", label="Pooled mean (shading: 95% CI)")]
    fig.legend(handles=handles, loc="lower left", ncol=1, frameon=False, bbox_to_anchor=(0.02, 0.0),
               handlelength=1.8)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    return fig


def render_figure3(d: dict):
    fig, axes = plt.subplots(1, 2, figsize=(7.48, 3.3), gridspec_kw={"width_ratios": [2.1, 1]})
    ax = axes[0]
    pts = d["points"]
    wmax = max(p["w"] for p in pts)
    for p in sorted(pts, key=lambda p: -p["w"]):  # large circles first, small ones on top
        ax.scatter([p["E"]], [p["y"]], s=6 + 380 * p["w"] / wmax, facecolor=LIGHT, edgecolor="black",
                   linewidth=0.6, zorder=3)
    for p in sorted(pts, key=lambda p: -p["w"])[:2]:  # the two heaviest States, named below their circle
        r = (6 + 380 * p["w"] / wmax) ** 0.5 / 2
        ax.annotate(p["name"], (p["E"], p["y"]), xytext=(0, -r - 2), textcoords="offset points",
                    ha="center", va="top", fontsize=6.8)
    ax.set_yscale("log")
    ax.set_ylim(1.5, 1000)  # headroom so the correlation annotation clears the highest point (Delhi)
    log_axis(ax.yaxis, [2, 5, 10, 20, 50, 100, 200, 500, 1000])
    ax.set_xlim(-0.05, 1.05)
    ax.set_xlabel("Share of the State's districts in phase 1 of the campaign")
    ax.set_ylabel("Pooled 2021–2023 ACF yield per 100,000 screened")
    ax.text(0.99, 0.98, f"Spearman ρ, weighted by 2023 screening: {d['rho']['weighted']}\n"
                        f"Spearman ρ, unweighted: {d['rho']['unweighted']}",
            transform=ax.transAxes, ha="right", va="top", fontsize=6.8)
    ax.text(0.99, 0.02, "Circle area: people screened in 2023", transform=ax.transAxes, ha="right",
            va="bottom", fontsize=6.5, color="#404040")
    panel_title(ax, "A")
    plain(ax)

    ax = axes[1]
    sc = d["scenario"]
    for k, s in enumerate(sc):
        y = len(sc) - 1 - k
        ax.plot(s["ci"], [y, y], color="black", linewidth=1.0)
        ax.scatter([s["delta"]], [y], marker="o", s=22, color="black", zorder=3)
        ax.annotate(s["text"], (s["ci"][0], y), xytext=(0, 6), textcoords="offset points", ha="left",
                    va="bottom", fontsize=6.5)
    ax.axvline(0, color=GREY, linewidth=0.6, linestyle="--")
    ax.set_yticks(range(len(sc)), [s["label"] for s in reversed(sc)])
    ax.set_ylim(-0.6, len(sc) - 0.2)
    ax.set_xlabel("Expected change in ACF diagnoses\n(95% interval)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: minus(f"{v:,.0f}")))
    panel_title(ax, "B", "Illustration, not a forecast")
    plain(ax)
    fig.tight_layout(w_pad=1.5)
    return fig


def render_figure4(d: dict, titles: dict):
    fig, axes = plt.subplots(2, 2, figsize=(7.48, 5.4))
    spec = [("epsilon", "A", titles["epsilon"]), ("rho", "B", titles["rho"]),
            ("theta_absolute", "C", titles["theta"]),
            ("theta_log", "D", "Notifications (θ), log scale\nentries of the same grid as C")]
    for ax, (key, letter, title) in zip(axes.flat, spec):
        pts = d[key]
        for x, p in enumerate(pts, 1):
            ax.plot([x, x], p["ci"], color="black" if p["excludes"] else "#a6a6a6", linewidth=0.9)
            if p["main"]:
                ax.scatter([x], [p["value"]], marker="D", s=30, color="black", zorder=4)
            else:
                ax.scatter([x], [p["value"]], marker="o", s=12, facecolor="black" if p["excludes"] else "white",
                           edgecolor="black", linewidth=0.7, zorder=3)
        ax.axhline(pts[0]["null"], color=GREY, linewidth=0.8, linestyle="--")
        ax.set_xlim(0.3, len(pts) + 0.7)
        ax.set_xticks([])
        ax.set_xlabel("Specifications, sorted by estimate")
        ax.set_ylabel("Estimate (95% interval)")
        panel_title(ax, letter, title)
        plain(ax)
    handles = [Line2D([], [], marker="D", linestyle="", color="black", markersize=4.5, label="Main specification"),
               Line2D([], [], marker="o", color="black", linewidth=0.9, markersize=3.5,
                      label="Interval excludes the null"),
               Line2D([], [], marker="o", color="#a6a6a6", markerfacecolor="white", markeredgecolor="black",
                      linewidth=0.9, markersize=3.5, label="Interval includes the null"),
               Line2D([], [], color=GREY, linewidth=0.8, linestyle="--", label="Null value")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.05, 1, 1), h_pad=1.6)
    return fig


def fig_texts(fig) -> list[str]:
    """Every string drawn on a figure (titles, labels, tick labels, legends, annotations)."""
    fig.canvas.draw()
    out = [t.get_text() for t in fig.texts]
    for leg in fig.legends:
        out += [t.get_text() for t in leg.get_texts()]
    for ax in fig.axes:
        out += [ax.get_title(loc="left"), ax.get_title(), ax.get_xlabel(), ax.get_ylabel()]
        out += [t.get_text() for t in ax.get_xticklabels() + ax.get_yticklabels()]
        out += [t.get_text() for t in ax.texts]
        if ax.get_legend():
            out += [t.get_text() for t in ax.get_legend().get_texts()]
    return [t for t in out if t]


def save(fig, out: Path, name: str) -> None:
    from PIL import Image
    fig.savefig(out / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None, "Creator": None,
                                               "Producer": None})
    for dpi, ext in ((DPI_PNG, "png"), (DPI_TIFF, "tif")):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, metadata={"Software": None})
        im = Image.open(io.BytesIO(buf.getvalue())).convert("L")
        if ext == "png":
            im.save(out / f"{name}.png", format="PNG", dpi=(dpi, dpi))
        else:
            im.save(out / f"{name}.tif", format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
    plt.close(fig)


NOTES = """# Figure notes (generated by the figure builder; drafts for the legends)

## Figure 1
National yield and its cascade decomposition over time. A: the pooled ACF yield per 100,000 people screened for the typical State in each data year (random-effects mean across States, square, with its 95% confidence interval as a thick bar and its 95% prediction interval as a thin grey bar), beside the national yield from the printed India row of the India TB Report (open circle). Data year 2020 is not in the State panel. B: the change from 2021 to 2023 in the log yield and its two additive parts, the testing step (log tested per screened) and the positivity step (log diagnosed per tested), from national sums over the States with all three counts, with cluster-bootstrap 95% intervals. C: the share of the between-State variance of the log yield attributable to the testing step, by data year, with cluster-bootstrap 95% intervals; the rest is the positivity step. Intervals can exceed 1 because the covariance between the two steps is split equally between them, so a share is not bounded by 0 and 1; they are not truncated. In 2022 the report counts people examined rather than tested (open circle, a sensitivity analysis).

## Figure 2
State and Union Territory yield tiers, pooled 2021–2023. Each State's empirical-Bayes posterior yield (circle) and its registered 95% interval (black bar), grouped by its registered tier against the pooled mean (dashed line; shading, its 95% confidence interval) and listed alphabetically within each tier; the order is not a ranking. The registered intervals are plug-in: they reflect binomial sampling variance only and omit the variation between years within a State, so they are too narrow. The grey bar is the interval from a post hoc sensitivity that includes the variation between years. A filled circle marks a robust tier (the same under both analyses); an open circle marks a tier that changes under the sensitivity. Lakshadweep has no pooled value.

## Figure 3
Targeting. A: each State's share of districts in phase 1 of the campaign against its pooled 2021–2023 ACF yield; circle area is proportional to people screened in 2023, the weight of the main correlation, so a few States carry most of the weight. The two largest are named. The Spearman correlations, weighted and unweighted, are given with bootstrap 95% intervals; neither is established under the pre-specified rule. B: an illustrative reallocation, not a forecast: each below-tier State gives 10% of its 2023 screening to the above-tier States in proportion to their volume, and the expected change in diagnoses applies the within-State elasticity, assuming it would hold under reallocation; 95% intervals carry the uncertainty of the elasticity only. Upper row, the registered tiers; lower row, only the tiers that are robust to the post hoc between-year sensitivity.

## Figure 4
Robustness: every entry of the pre-specified specification grid for the three headline estimates, sorted by its estimate, with its 95% interval (cluster bootstrap for the elasticity and the notification association; bootstrap of States for the correlation). The diamond is the main specification; a filled circle and black bar mark an entry whose interval excludes the null, an open circle and grey bar one whose interval includes it; the dashed line is the null (1 for the elasticity, 0 otherwise). Panel titles give the number of entries on the same side of the null as the main estimate, out of the whole grid, and the pre-specified label. The notification grid has 16 entries: 8 on the absolute scale (C) and 8 on the log scale (D), whose estimates are proportional differences.
"""


def build(out: Path = OUT) -> dict:
    """Render the four figures into `out`; return their texts, the numbers written on them
    (annotations) and the trace of every plotted value."""
    out.mkdir(parents=True, exist_ok=True)
    setup()
    trace, texts, notes = [], {}, {}
    t1, t2, t3, t4 = (FTrace(f"Figure {k}") for k in range(1, 5))
    figs = {"figure1": render_figure1(figure1_points(t1)),
            "figure2": render_figure2(figure2_points(t2), figure2_mean(t2))}
    d3 = figure3_points(t3)
    figs["figure3"] = render_figure3(d3)
    figs["figure4"] = render_figure4(figure4_points(t4), figure4_titles(t4))
    notes = {"Figure 1": [], "Figure 2": [],
             "Figure 3": [d3["rho"]["weighted"], d3["rho"]["unweighted"]] + [s["text"] for s in d3["scenario"]],
             "Figure 4": [figs["figure4"].axes[k].get_title(loc="left") for k in range(3)]}
    for name, fig in figs.items():
        texts[name] = fig_texts(fig)
        save(fig, out, name)
    for t in (t1, t2, t3, t4):
        trace += t.entries
    (out / "figure_trace.json").write_text(json.dumps(trace, indent=1, ensure_ascii=False) + "\n",
                                           encoding="utf-8", newline="\n")
    (out / "figure_notes.md").write_text(NOTES, encoding="utf-8", newline="\n")
    return {"texts": texts, "annotations": notes, "trace": trace}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT), help="output folder (default manuscript/ext/exhibits)")
    out = Path(ap.parse_args(argv).out)
    res = build(out)
    print(f"wrote {', '.join(FIGURES)} (PDF, TIFF {DPI_TIFF} dpi, PNG {DPI_PNG} dpi) and "
          f"{len(res['trace'])} traced values to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
