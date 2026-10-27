"""Draw the README charts from the aggregate answer tables in outputs/business_answers/.

Usage (from the project root):  python analysis/make_charts.py
Inputs are aggregates only (no comments or identifiers).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "outputs" / "business_answers"
OUT = ROOT / "outputs" / "charts"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b4b3ad"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e8e7e3"
WORSENING = ["Kestrel Parramatta", "Kestrel Bendigo", "Kestrel Dandenong", "Kestrel Liverpool"]

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def title(ax, main, sub):
    ax.set_title(main, loc="left", fontsize=12, fontweight="bold", color=INK, pad=22)
    ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9, color=INK2)


# 1. Monthly negative share: the four worsening dealers vs everyone else
m = pd.read_csv(DATA / "q2b.csv")
fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(m))
for col, colour, label in [("worsening_four_pct", ORANGE, "Parramatta, Bendigo, Dandenong, Liverpool"),
                           ("rest_of_group_pct", BLUE, "Other 20 dealerships")]:
    ax.plot(x, m[col], color=colour, lw=2, marker="o", ms=5)
    ax.text(len(m) - 0.7, m[col].iloc[-1], label, color=INK, fontsize=9, va="center")
ax.axvline(7, color=GREY, lw=1, ls="--")
ax.text(7.1, 44, "Dandenong online\nbooking live 5 May", fontsize=8, color=INK2, va="top")
ax.set_xticks(list(x), [pd.Period(p).strftime("%b %y") for p in m["month"]], fontsize=8)
ax.set_ylabel("% of rated responses negative (1–2)")
ax.set_ylim(0, 46)
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_xlim(-0.3, len(m) + 3.2)
title(ax, "Four sites drove the rise in negative feedback",
      "Negative share by month, Oct 2025 – Sep 2026. The rest of the group stayed flat at about 20–23%.")
fig.tight_layout()
fig.savefig(OUT / "monthly_trend.png", dpi=160)

# 2. H1 vs H2 by dealership (dumbbell), sufficient samples only
d = pd.read_csv(DATA / "q2a.csv")
d = d[d["comparison_sample_sufficient"]].sort_values("change_pts")
fig, ax = plt.subplots(figsize=(8, 6.5))
for i, r in enumerate(d.itertuples()):
    hot = r.dealership_name in WORSENING
    ax.plot([r.h1_pct, r.h2_pct], [i, i], color=ORANGE if hot else GREY, lw=2, zorder=1)
    ax.scatter(r.h1_pct, i, s=36, color="white", edgecolor=INK2, lw=1.5, zorder=2)
    ax.scatter(r.h2_pct, i, s=36, color=ORANGE if hot else INK2, zorder=3)
    if hot:
        ax.text(r.h2_pct + 0.8, i, f"+{r.change_pts:.0f} pts", va="center", fontsize=8, color=INK)
ax.set_yticks(range(len(d)), [n.replace("Kestrel ", "") for n in d["dealership_name"]], fontsize=8)
ax.set_xlabel("% of rated responses negative")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.scatter([], [], s=36, color="white", edgecolor=INK2, lw=1.5, label="Oct–Mar (H1)")
ax.scatter([], [], s=36, color=INK2, label="Apr–Sep (H2)")
ax.legend(frameon=False, loc="lower right", fontsize=8)
title(ax, "Negative share, first half vs second half",
      "All departments. Noosa and Shepparton left out (too few responses / closed 31 Mar).")
fig.tight_layout()
fig.savefig(OUT / "h1_vs_h2_by_dealer.png", dpi=160)

# 3. What grew at the four worsening dealers
t = pd.read_csv(DATA / "q2c.csv").sort_values("h2_driver_pct")
t = t[t["theme_id"] != "other"]
fig, ax = plt.subplots(figsize=(8, 4.2))
y = range(len(t))
ax.barh([i + 0.2 for i in y], t["h1_driver_pct"], height=0.36, color=BLUE, label="Oct–Mar (H1)")
ax.barh([i - 0.2 for i in y], t["h2_driver_pct"], height=0.36, color=ORANGE, label="Apr–Sep (H2)")
for i, r in enumerate(t.itertuples()):
    ax.text(r.h2_driver_pct + 0.6, i - 0.2, f"{r.h2_driver_pct:.0f}%", va="center", fontsize=8, color=INK)
LABELS = {"waiting_time_scheduling": "Waiting/booking", "communication_follow_up": "Communication",
          "parts_availability": "Parts availability", "workmanship_repair_quality": "Repair quality",
          "pricing_value": "Price/value", "sales_process": "Sales process", "staff_service": "Staff service",
          "vehicle_product": "Vehicle/product"}
ax.set_yticks(list(y), [LABELS.get(s, s) for s in t["theme_id"]], fontsize=8)
ax.set_xlabel("% of negative responses mentioning the theme negatively (AI-labelled)")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.legend(frameon=False, loc="lower right", fontsize=8)
title(ax, "At the four worsening sites, booking and wait complaints grew most",
      "Gemini themes on negative-rated responses. Parts availability is over-tagged (see AI evaluation).")
fig.tight_layout()
fig.savefig(OUT / "worsening_site_themes.png", dpi=160)

print("charts written to", OUT)
