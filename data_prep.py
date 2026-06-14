"""
data_prep.py
PulseIndia Digital — Ad Inventory Simulation
Generates a realistic 16-week publisher ad server log with IVT flagging.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import os

np.random.seed(42)

# ── CONFIG ──────────────────────────────────────────────────────────────────
START_DATE = datetime(2024, 7, 1)   # 16-week history starts July 1 2024
WEEKS      = 16
AD_UNITS   = ["homepage_banner", "article_mid", "article_bottom", "sidebar", "video_preroll"]
DEVICES    = ["mobile", "desktop", "tablet"]
SEGMENTS   = ["urban_male_25_44", "news_enthusiast", "finance_professional",
              "entertainment_seeker", "general_audience"]

DIWALI_WEEKS  = [16, 17]   # relative week index (Oct 28 – Nov 10 in forecast)
WEEKEND_CPM_DISCOUNT = 0.82  # weekends price 18% lower

# Base CPM by ad unit (INR)
BASE_CPM = {
    "homepage_banner":  95,
    "article_mid":      82,
    "article_bottom":   68,
    "sidebar":          55,
    "video_preroll":   140,
}

# Base available impressions per week per ad unit
BASE_AVAIL = {
    "homepage_banner":  420_000,
    "article_mid":      680_000,
    "article_bottom":   510_000,
    "sidebar":          390_000,
    "video_preroll":    180_000,
}

rows = []
log_id = 1

for week_idx in range(WEEKS):
    week_start = START_DATE + timedelta(weeks=week_idx)

    # Traffic multiplier: news cycle spikes in weeks 4,9,12 (elections/events)
    traffic_mult = 1.0
    if week_idx in [3, 4]:    traffic_mult = 1.18   # election coverage
    if week_idx in [8, 9]:    traffic_mult = 1.11   # state budget week
    if week_idx in [11, 12]:  traffic_mult = 0.78   # festive lull / low news
    if week_idx in [14, 15]:  traffic_mult = 1.22   # Diwali spike

    for ad_unit in AD_UNITS:
        for device in DEVICES:
            for segment in SEGMENTS:
                # Device weight
                dev_weight = {"mobile": 0.55, "desktop": 0.30, "tablet": 0.15}[device]
                seg_weight = {
                    "urban_male_25_44": 0.28,
                    "news_enthusiast":  0.24,
                    "finance_professional": 0.14,
                    "entertainment_seeker": 0.18,
                    "general_audience": 0.16
                }[segment]

                avail = int(BASE_AVAIL[ad_unit] * dev_weight * seg_weight
                            * traffic_mult * np.random.uniform(0.92, 1.08))

                # Sell-through rate: varies by ad unit, device, week
                base_str = np.random.uniform(0.62, 0.88)
                if device == "mobile":   base_str *= 1.07
                if ad_unit == "video_preroll": base_str *= 1.12
                if week_idx in [11, 12]: base_str *= 0.78   # low-demand lull
                base_str = min(base_str, 0.98)

                served = int(avail * base_str)

                # CPM: base + weekend discount + noise
                is_weekend = week_start.weekday() >= 5
                cpm = (BASE_CPM[ad_unit]
                       * (WEEKEND_CPM_DISCOUNT if is_weekend else 1.0)
                       * np.random.uniform(0.88, 1.14))

                revenue = round((served / 1000) * cpm, 2)

                # ── IVT FLAGGING (3 rules per IAB thresholds) ──
                ctr_simulated = np.random.uniform(0.005, 0.04)
                imp_velocity  = np.random.uniform(10, 380)   # impressions/hr
                unbillable    = (revenue == 0 and served > 0)

                # Inject ~3% bad rows
                if np.random.random() < 0.031:
                    ctr_simulated = np.random.uniform(0.36, 0.80)
                if np.random.random() < 0.015:
                    imp_velocity  = np.random.uniform(401, 900)

                is_ivt = int(
                    (ctr_simulated > 0.35) or
                    (imp_velocity  > 400)  or
                    unbillable
                )

                rows.append({
                    "log_id":                log_id,
                    "week_start":            week_start.strftime("%Y-%m-%d"),
                    "ad_unit":               ad_unit,
                    "device_type":           device,
                    "user_segment":          segment,
                    "impressions_available": avail,
                    "impressions_served":    served,
                    "revenue_inr":           revenue,
                    "cpm_inr":               round(cpm, 2),
                    "sell_through_rate":     round(base_str, 4),
                    "ctr_simulated":         round(ctr_simulated, 4),
                    "imp_velocity_per_hr":   round(imp_velocity, 1),
                    "is_ivt_flag":           is_ivt,
                })
                log_id += 1

df = pd.DataFrame(rows)

# ── RFP COMMITMENTS TABLE ────────────────────────────────────────────────────
rfp_data = [
    {
        "rfp_id":                 "RFP-001",
        "advertiser":             "HUL — Dove Campaign",
        "target_segment":         "urban_male_25_44",
        "target_device":          "mobile",
        "start_date":             "2024-10-15",
        "end_date":               "2024-11-30",
        "committed_impressions":  6_000_000,
        "agreed_cpm_inr":         92.0,
        "deal_type":              "PMP",
    },
    {
        "rfp_id":                 "RFP-002",
        "advertiser":             "Tata Consumer — Tata Tea",
        "target_segment":         "news_enthusiast",
        "target_device":          "desktop",
        "start_date":             "2024-10-20",
        "end_date":               "2024-11-30",
        "committed_impressions":  4_000_000,
        "agreed_cpm_inr":         85.0,
        "deal_type":              "PMP",
    },
]
rfp_df = pd.DataFrame(rfp_data)

# ── SAVE TO CSV ──────────────────────────────────────────────────────────────
df.to_csv("/home/claude/pulseIndia/data/inventory_log.csv", index=False)
rfp_df.to_csv("/home/claude/pulseIndia/data/rfp_commitments.csv", index=False)

# ── SAVE TO SQLITE ───────────────────────────────────────────────────────────
conn = sqlite3.connect("/home/claude/pulseIndia/data/pulseindia_inventory.db")
df.to_sql("inventory_log",    conn, if_exists="replace", index=False)
rfp_df.to_sql("rfp_commitments", conn, if_exists="replace", index=False)
conn.close()

print(f"✓ inventory_log rows   : {len(df):,}")
print(f"✓ IVT flagged rows     : {df['is_ivt_flag'].sum():,}  ({df['is_ivt_flag'].mean()*100:.1f}%)")
print(f"✓ Total impressions    : {df['impressions_available'].sum():,.0f}")
print(f"✓ Total revenue (INR)  : ₹{df['revenue_inr'].sum():,.0f}")
print(f"✓ Avg sell-through     : {df[df.is_ivt_flag==0]['sell_through_rate'].mean()*100:.1f}%")
print("✓ Data saved to CSV + SQLite")
