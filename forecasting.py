"""
forecasting.py
PulseIndia Digital — Pre-Sales Inventory Forecasting + PMP Revenue Model
Uses Holt-Winters Exponential Smoothing for 6-week campaign window forecast.
"""

import pandas as pd
import numpy as np
import sqlite3
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings
warnings.filterwarnings("ignore")

# ── LOAD DATA ────────────────────────────────────────────────────────────────
conn = sqlite3.connect("/home/claude/pulseIndia/data/pulseindia_inventory.db")

df = pd.read_sql("""
    SELECT week_start,
           SUM(impressions_available) AS avail,
           SUM(impressions_served)    AS served,
           SUM(revenue_inr)           AS revenue,
           AVG(cpm_inr)               AS avg_cpm
    FROM inventory_log
    WHERE is_ivt_flag = 0
    GROUP BY week_start
    ORDER BY week_start
""", conn)

rfp = pd.read_sql("SELECT * FROM rfp_commitments", conn)
conn.close()

df["week_start"] = pd.to_datetime(df["week_start"])
df["sell_through"] = df["served"] / df["avail"]

# ── HOLT-WINTERS FORECAST ─────────────────────────────────────────────────────
# Train on all 16 historical weeks, forecast next 6 (campaign window)
series = df["avail"].values

model = ExponentialSmoothing(
    series,
    trend="add",
    seasonal="add",
    seasonal_periods=4,    # monthly seasonality within weekly data
    initialization_method="estimated"
).fit(optimized=True)

forecast_raw = model.forecast(6)

# ── DIWALI TRAFFIC MULTIPLIER ────────────────────────────────────────────────
# Source: Google Trends data for "Diwali news" shows +22% traffic in Oct W4–Nov W1
# Campaign weeks: Oct 15 – Nov 30 → weeks 17–22 relative to July start
diwali_multipliers = np.array([1.00, 1.00, 1.22, 1.22, 1.08, 1.05])

forecast_adjusted = forecast_raw * diwali_multipliers

# ── CONSERVATIVE BUFFER ───────────────────────────────────────────────────────
# Standard industry practice: withhold 15% of available inventory
# to avoid overbooking (remnant buffer for last-minute open auction)
BUFFER = 0.15
forecast_committable = forecast_adjusted * (1 - BUFFER)

# ── BUILD FORECAST TABLE ──────────────────────────────────────────────────────
campaign_weeks = pd.date_range("2024-10-14", periods=6, freq="W-MON")

# Weekly RFP commitments (total impressions spread evenly across 6 weeks)
rfp1_weekly = rfp[rfp["rfp_id"] == "RFP-001"]["committed_impressions"].values[0] / 6
rfp2_weekly = rfp[rfp["rfp_id"] == "RFP-002"]["committed_impressions"].values[0] / 6

# RFP-2 starts Oct 20 → skip first week
rfp2_weekly_vec = np.array([0, rfp2_weekly, rfp2_weekly, rfp2_weekly, rfp2_weekly, rfp2_weekly])
rfp1_weekly_vec = np.full(6, rfp1_weekly)

total_committed = rfp1_weekly_vec + rfp2_weekly_vec
net_available   = forecast_committable - total_committed

forecast_df = pd.DataFrame({
    "week_start":                    campaign_weeks.strftime("%Y-%m-%d"),
    "raw_forecast":                  forecast_raw.astype(int),
    "diwali_adjusted":               forecast_adjusted.astype(int),
    "committable_after_buffer":      forecast_committable.astype(int),
    "rfp1_committed_weekly":         rfp1_weekly_vec.astype(int),
    "rfp2_committed_weekly":         rfp2_weekly_vec.astype(int),
    "total_committed":               total_committed.astype(int),
    "net_available_impressions":     net_available.astype(int),
    "overbooking_risk":              net_available < 0,
})

forecast_df["status"] = forecast_df["overbooking_risk"].map(
    {True: "OVERBOOKED ⚠", False: "SAFE ✓"}
)

# ── PMP vs OPEN AUCTION REVENUE MODEL ────────────────────────────────────────
# Historical benchmarks from our data
hist_avg_cpm       = df["avg_cpm"].mean()         # actual avg from data
hist_avg_str       = df["sell_through"].mean()     # actual sell-through

# P75 CPM as PMP floor (justified: advertisers pay premium for guarantee)
p75_cpm = df["avg_cpm"].quantile(0.75)

total_campaign_impressions = int(forecast_committable.sum())

scenarios = {
    "Conservative (70% fill)": 0.70,
    "Base (85% fill)":         0.85,
    "Optimistic (95% fill)":   0.95,
}

pmp_rows = []
for label, fill_rate in scenarios.items():
    open_rev = (total_campaign_impressions * hist_avg_str * hist_avg_cpm) / 1000
    pmp_rev  = (total_campaign_impressions * fill_rate   * p75_cpm)       / 1000
    uplift   = ((pmp_rev - open_rev) / open_rev) * 100

    pmp_rows.append({
        "Scenario":                     label,
        "Fill Rate":                    f"{fill_rate*100:.0f}%",
        "PMP CPM Floor (INR)":          round(p75_cpm, 2),
        "Open Auction Revenue (INR)":   round(open_rev, 0),
        "PMP Revenue (INR)":            round(pmp_rev, 0),
        "Revenue Uplift (%)":           round(uplift, 1),
    })

pmp_df = pd.DataFrame(pmp_rows)

# ── SEGMENT VALIDATION FOR RFPs ──────────────────────────────────────────────
conn = sqlite3.connect("/home/claude/pulseIndia/data/pulseindia_inventory.db")
seg_df = pd.read_sql("""
    SELECT user_segment, device_type,
           SUM(impressions_available) AS total_avail,
           ROUND(AVG(sell_through_rate)*100,2) AS avg_str_pct,
           ROUND(AVG(cpm_inr),2) AS avg_cpm
    FROM inventory_log
    WHERE is_ivt_flag = 0
    GROUP BY user_segment, device_type
    ORDER BY avg_cpm DESC
""", conn)
conn.close()

# ── SAVE ALL RESULTS ──────────────────────────────────────────────────────────
forecast_df.to_csv("/home/claude/pulseIndia/outputs/forecast_results.csv", index=False)
pmp_df.to_csv("/home/claude/pulseIndia/outputs/pmp_model.csv", index=False)
seg_df.to_csv("/home/claude/pulseIndia/outputs/segment_analysis.csv", index=False)
df.to_csv("/home/claude/pulseIndia/outputs/weekly_history.csv", index=False)

# ── PRINT SUMMARY ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  PULSEINDIA DIGITAL — PRE-SALES FORECAST SUMMARY")
print("="*60)
print(f"\n  Historical Avg Sell-Through : {hist_avg_str*100:.1f}%")
print(f"  Historical Avg CPM (INR)    : ₹{hist_avg_cpm:.2f}")
print(f"  P75 CPM (PMP Floor)         : ₹{p75_cpm:.2f}")
print(f"\n  6-Week Committable Inventory: {int(forecast_committable.sum()):,} impressions")
print(f"  Total RFP Commitment        : {int(total_committed.sum()):,} impressions")
print(f"  Net Buffer Remaining        : {int(net_available.sum()):,} impressions")
print(f"\n  Overbooking Risk Weeks      : {forecast_df['overbooking_risk'].sum()}")

print("\n\n── FORECAST TABLE ──────────────────────────────────────")
print(forecast_df[["week_start","committable_after_buffer",
                    "total_committed","net_available_impressions","status"]].to_string(index=False))

print("\n\n── PMP vs OPEN AUCTION REVENUE MODEL ───────────────────")
print(pmp_df.to_string(index=False))

print("\n\n── TOP SEGMENTS BY CPM ──────────────────────────────────")
print(seg_df.head(10).to_string(index=False))
print("\n✓ All outputs saved to /outputs/")
