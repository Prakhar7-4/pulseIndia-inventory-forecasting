-- ============================================================
-- Database: pulseindia_inventory.db (SQLite)
-- Author: Prakhar Agrawal | Project: Pre-Sales Inventory Forecasting
-- ============================================================

-- ── QUERY 1: Weekly Sell-Through Trend (16-week history, IVT excluded) ──────
SELECT
    week_start,
    SUM(impressions_available)                                          AS total_available,
    SUM(impressions_served)                                             AS total_served,
    ROUND(SUM(impressions_served) * 100.0 / SUM(impressions_available), 2) AS sell_through_pct,
    ROUND(AVG(cpm_inr), 2)                                             AS avg_cpm_inr,
    ROUND(SUM(revenue_inr), 0)                                         AS total_revenue_inr
FROM inventory_log
WHERE is_ivt_flag = 0
GROUP BY week_start
ORDER BY week_start;


-- ── QUERY 2: Audience Segment Performance (RFP targeting validation) ─────────
SELECT
    user_segment,
    device_type,
    SUM(impressions_available)                                              AS segment_inventory,
    SUM(impressions_served)                                                 AS segment_served,
    ROUND(SUM(impressions_served) * 100.0 / SUM(impressions_available), 2) AS avg_sell_through_pct,
    ROUND(AVG(cpm_inr), 2)                                                 AS avg_cpm_inr,
    ROUND(SUM(revenue_inr), 0)                                             AS total_revenue_inr
FROM inventory_log
WHERE is_ivt_flag = 0
GROUP BY user_segment, device_type
ORDER BY avg_cpm_inr DESC;


-- ── QUERY 3: Ad Unit Performance Summary ─────────────────────────────────────
SELECT
    ad_unit,
    SUM(impressions_available)                                              AS total_available,
    ROUND(SUM(impressions_served) * 100.0 / SUM(impressions_available), 2) AS sell_through_pct,
    ROUND(AVG(cpm_inr), 2)                                                 AS avg_cpm_inr,
    ROUND(SUM(revenue_inr), 0)                                             AS revenue_inr
FROM inventory_log
WHERE is_ivt_flag = 0
GROUP BY ad_unit
ORDER BY revenue_inr DESC;


-- ── QUERY 4: IVT Analysis — Volume and Revenue Impact ────────────────────────
SELECT
    is_ivt_flag,
    COUNT(*)                          AS row_count,
    SUM(impressions_served)           AS impressions_affected,
    ROUND(SUM(revenue_inr), 0)        AS revenue_inr,
    ROUND(AVG(ctr_simulated) * 100, 2) AS avg_ctr_pct
FROM inventory_log
GROUP BY is_ivt_flag;


-- ── QUERY 5: Overbooking Risk Check for Campaign Window ──────────────────────
-- Checks if committed RFP impressions exceed available inventory per week
SELECT
    il.week_start,
    il.user_segment,
    il.device_type,
    SUM(il.impressions_available)                                   AS weekly_available,
    COALESCE(rc.committed_impressions / 6, 0)                       AS weekly_committed,
    SUM(il.impressions_available) - COALESCE(rc.committed_impressions / 6, 0)
                                                                    AS net_available,
    CASE
        WHEN SUM(il.impressions_available) - COALESCE(rc.committed_impressions / 6, 0) < 0
        THEN 'OVERBOOKED ⚠'
        ELSE 'SAFE ✓'
    END                                                             AS booking_status
FROM inventory_log il
LEFT JOIN rfp_commitments rc
    ON il.user_segment = rc.target_segment
    AND il.device_type  = rc.target_device
WHERE il.week_start BETWEEN '2024-10-14' AND '2024-11-30'
  AND il.is_ivt_flag = 0
GROUP BY il.week_start, il.user_segment, il.device_type
ORDER BY il.week_start, il.user_segment;


-- ── QUERY 6: CPM Percentile Distribution (for PMP floor pricing) ─────────────
SELECT
    ad_unit,
    ROUND(MIN(cpm_inr), 2)                     AS min_cpm,
    ROUND(AVG(cpm_inr), 2)                     AS avg_cpm,
    ROUND(MAX(cpm_inr), 2)                     AS max_cpm,
    COUNT(*)                                   AS observations
FROM inventory_log
WHERE is_ivt_flag = 0
GROUP BY ad_unit
ORDER BY avg_cpm DESC;
