"""
charts.py — PulseIndia Digital
Generates all 6 analysis charts for the pre-sales inventory report.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import sqlite3

# ── Shared style ─────────────────────────────────────────────────────────────
BLUE   = "#1F4E79"
LBLUE  = "#2E75B6"
ORANGE = "#C55A11"
GREEN  = "#375623"
RED    = "#C00000"
GRAY   = "#D9D9D9"
BG     = "#FAFAFA"

plt.rcParams.update({
    "font.family":     "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor":  BG,
    "figure.facecolor": "white",
    "axes.titlesize":  13,
    "axes.titleweight": "bold",
    "axes.titlepad":   14,
})

def fmt_lakh(x, pos):
    return f"₹{x/1e5:.1f}L"

def fmt_impr(x, pos):
    return f"{x/1e6:.1f}M"

# ── Load data ────────────────────────────────────────────────────────────────
history  = pd.read_csv("/home/claude/pulseIndia/outputs/weekly_history.csv")
forecast = pd.read_csv("/home/claude/pulseIndia/outputs/forecast_results.csv")
pmp      = pd.read_csv("/home/claude/pulseIndia/outputs/pmp_model.csv")
seg      = pd.read_csv("/home/claude/pulseIndia/outputs/segment_analysis.csv")

conn = sqlite3.connect("/home/claude/pulseIndia/data/pulseindia_inventory.db")
raw  = pd.read_sql("SELECT * FROM inventory_log", conn)
conn.close()

history["week_start"]  = pd.to_datetime(history["week_start"])
forecast["week_start"] = pd.to_datetime(forecast["week_start"])

# ── CHART 1: Weekly Sell-Through Rate (16 weeks) ─────────────────────────────
fig, ax = plt.subplots(figsize=(11, 4.5))
clean = raw[raw.is_ivt_flag == 0]
wk = clean.groupby("week_start").agg(
    avail=("impressions_available","sum"),
    served=("impressions_served","sum")
).reset_index()
wk["str"] = wk["served"] / wk["avail"] * 100
wk["week_start"] = pd.to_datetime(wk["week_start"])

ax.bar(range(len(wk)), wk["str"], color=LBLUE, alpha=0.85, zorder=2, label="Sell-Through %")
ax.axhline(wk["str"].mean(), color=ORANGE, lw=1.8, ls="--", label=f"16-wk avg: {wk['str'].mean():.1f}%", zorder=3)
ax.axhline(78, color=GRAY, lw=1.2, ls=":", zorder=1)

for i, v in enumerate(wk["str"]):
    ax.text(i, v + 0.8, f"{v:.0f}%", ha="center", fontsize=8, color=BLUE)

ax.set_xticks(range(len(wk)))
ax.set_xticklabels([d.strftime("%b %d") for d in wk["week_start"]], rotation=45, ha="right", fontsize=8)
ax.set_ylabel("Sell-Through Rate (%)")
ax.set_ylim(0, 105)
ax.set_title("PulseIndia Digital — 16-Week Sell-Through Rate Trend (IVT Excluded)")
ax.legend(fontsize=9)
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
plt.tight_layout()
plt.savefig("/home/claude/pulseIndia/charts/chart1_sell_through_trend.png", dpi=150)
plt.close()
print("✓ Chart 1: Sell-Through Trend")

# ── CHART 2: CPM vs Sell-Through Scatter (pricing elasticity) ────────────────
fig, ax = plt.subplots(figsize=(8, 5))
sample = clean.sample(400, random_state=42)
colors = sample["device_type"].map({"mobile": LBLUE, "desktop": ORANGE, "tablet": GREEN})
ax.scatter(sample["cpm_inr"], sample["sell_through_rate"]*100,
           c=colors, alpha=0.55, s=30, edgecolors="none")

from scipy import stats
slope, intercept, r, p, _ = stats.linregress(sample["cpm_inr"], sample["sell_through_rate"]*100)
xs = np.linspace(sample["cpm_inr"].min(), sample["cpm_inr"].max(), 100)
ax.plot(xs, slope*xs + intercept, color=RED, lw=1.8, label=f"Trend  r = {r:.2f}")

import matplotlib.patches as mpatches
legend_els = [
    mpatches.Patch(color=LBLUE,   label="Mobile"),
    mpatches.Patch(color=ORANGE,  label="Desktop"),
    mpatches.Patch(color=GREEN,   label="Tablet"),
    plt.Line2D([0],[0], color=RED, lw=1.8, label=f"Trend  r = {r:.2f}"),
]
ax.legend(handles=legend_els, fontsize=9)
ax.set_xlabel("CPM (INR)")
ax.set_ylabel("Sell-Through Rate (%)")
ax.set_title("CPM vs Sell-Through Rate — Pricing Elasticity Analysis")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
plt.tight_layout()
plt.savefig("/home/claude/pulseIndia/charts/chart2_cpm_vs_str_scatter.png", dpi=150)
plt.close()
print("✓ Chart 2: CPM vs Sell-Through Scatter")

# ── CHART 3: 6-Week Inventory Forecast vs Commitments ────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))
x = np.arange(len(forecast))
w = 0.35

b1 = ax.bar(x - w/2, forecast["committable_after_buffer"]/1e6, w,
            color=LBLUE, label="Committable Inventory (after 15% buffer)", alpha=0.9)
b2 = ax.bar(x + w/2, forecast["total_committed"]/1e6, w,
            color=ORANGE, label="Total RFP Committed", alpha=0.9)

for bar in b1:
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02,
            f"{bar.get_height():.1f}M", ha="center", fontsize=8, color=BLUE)
for bar in b2:
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02,
            f"{bar.get_height():.1f}M", ha="center", fontsize=8, color=ORANGE)

ax.set_xticks(x)
ax.set_xticklabels([pd.to_datetime(d).strftime("%b %d") for d in forecast["week_start"]], fontsize=9)
ax.set_ylabel("Impressions (Millions)")
ax.set_title("Pre-Sales Forecast: Committable Inventory vs RFP Commitments (Oct 14 – Nov 25, 2024)")
ax.legend(fontsize=9)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_impr))
plt.tight_layout()
plt.savefig("/home/claude/pulseIndia/charts/chart3_forecast_vs_commitments.png", dpi=150)
plt.close()
print("✓ Chart 3: Forecast vs Commitments")

# ── CHART 4: PMP vs Open Auction Revenue ─────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))
scenarios   = pmp["Scenario"].str.split("(").str[0].str.strip()
open_rev    = pmp["Open Auction Revenue (INR)"] / 1e5
pmp_rev     = pmp["PMP Revenue (INR)"]          / 1e5
x = np.arange(len(scenarios))
w = 0.35

ax.bar(x - w/2, open_rev, w, color=GRAY,   label="Open Auction Revenue", edgecolor=BLUE, lw=0.8)
ax.bar(x + w/2, pmp_rev,  w, color=LBLUE,  label="PMP Revenue (₹89.37 CPM floor)", alpha=0.9)

for i, (ov, pv, ul) in enumerate(zip(open_rev, pmp_rev, pmp["Revenue Uplift (%)"])):
    clr = RED if ul < 0 else GREEN
    ax.text(i, max(ov, pv) + 0.08, f"{ul:+.1f}%", ha="center", fontsize=9,
            color=clr, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(scenarios, fontsize=9)
ax.set_ylabel("Revenue (₹ Lakhs)")
ax.set_title("PMP vs Open Auction Revenue — 3-Scenario Comparison")
ax.legend(fontsize=9)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_lakh))
plt.tight_layout()
plt.savefig("/home/claude/pulseIndia/charts/chart4_pmp_vs_open_auction.png", dpi=150)
plt.close()
print("✓ Chart 4: PMP vs Open Auction")

# ── CHART 5: Audience Segment Heatmap (CPM by segment × device) ──────────────
pivot = seg.pivot_table(index="user_segment", columns="device_type", values="avg_cpm", aggfunc="mean")
fig, ax = plt.subplots(figsize=(8, 5))
im = ax.imshow(pivot.values, cmap="Blues", aspect="auto")

ax.set_xticks(range(len(pivot.columns)))
ax.set_yticks(range(len(pivot.index)))
ax.set_xticklabels([c.capitalize() for c in pivot.columns], fontsize=10)
ax.set_yticklabels([s.replace("_", " ").title() for s in pivot.index], fontsize=9)

for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):
        val = pivot.values[i, j]
        if not np.isnan(val):
            ax.text(j, i, f"₹{val:.0f}", ha="center", va="center",
                    fontsize=10, color="white" if val > 89 else BLUE, fontweight="bold")

plt.colorbar(im, ax=ax, label="Avg CPM (INR)", shrink=0.8)
ax.set_title("Audience Segment × Device CPM Heatmap\n(Used for RFP Targeting Validation)")
plt.tight_layout()
plt.savefig("/home/claude/pulseIndia/charts/chart5_segment_heatmap.png", dpi=150)
plt.close()
print("✓ Chart 5: Segment Heatmap")

# ── CHART 6: IVT Flag Distribution ──────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

ivt_counts = raw["is_ivt_flag"].value_counts()
ax1.pie([ivt_counts.get(0,0), ivt_counts.get(1,0)],
        labels=["Valid Traffic", "IVT Flagged"],
        colors=[LBLUE, RED], autopct="%1.1f%%", startangle=90,
        textprops={"fontsize": 10})
ax1.set_title("IVT Flag Rate\n(Rule-Based: CTR >35%, Velocity >400/hr)")

ivt_by_unit = raw.groupby(["ad_unit","is_ivt_flag"]).size().unstack(fill_value=0)
ivt_by_unit["ivt_rate"] = ivt_by_unit[1] / (ivt_by_unit[0] + ivt_by_unit[1]) * 100
ivt_by_unit["ivt_rate"].plot(kind="barh", ax=ax2, color=RED, alpha=0.8)
ax2.set_xlabel("IVT Rate (%)")
ax2.set_title("IVT Rate by Ad Unit")
ax2.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))

plt.suptitle("Invalid Traffic (IVT) Analysis — PulseIndia Digital", fontweight="bold", fontsize=12)
plt.tight_layout()
plt.savefig("/home/claude/pulseIndia/charts/chart6_ivt_analysis.png", dpi=150)
plt.close()
print("✓ Chart 6: IVT Analysis")
print("\n✓ All 6 charts saved to /charts/")
