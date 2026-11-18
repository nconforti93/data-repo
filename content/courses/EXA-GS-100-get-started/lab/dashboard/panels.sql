-- Every dashboard panel is one block: a header line, then one SELECT. The dashboard re-reads this file every
-- 2 seconds, so save a change and watch the panel update.
--
--   -- panel: <Title> | <chart>        chart = kpi, line, bar, table or map
--
-- What each chart reads:
--   kpi    one row; every column becomes a tile (the column name is the tile's label)
--   line   column 1 = x axis, column 2 = y value
--   bar    column 1 = bar label, column 2 = bar length
--   map    column 1 = taxi zone id (1-265), column 2 = how dark the zone is coloured
--   table  any columns, first 20 rows
-- Column names are up to you, but avoid reserved words such as VALUE, ZONE, TIME, HOUR and MINUTE.

-- panel: New Year's Eve, live | kpi
SELECT COUNT(*)                                                  AS TRIPS_SO_FAR,
       ROUND(SUM(TOTAL_AMOUNT), 0)                               AS REVENUE_USD,
       ROUND(100 * SUM(CASE WHEN PAYMENT_TYPE = 1 AND FARE_AMOUNT > 0 THEN TIP_AMOUNT END)
                 / SUM(CASE WHEN PAYMENT_TYPE = 1 AND FARE_AMOUNT > 0 THEN FARE_AMOUNT END), 1) AS CARD_TIP_PCT,
       TO_CHAR(MAX(PICKUP_TIME), 'YYYY-MM-DD HH24:MI')           AS CLOCK
FROM TAXI.LIVE_TRIPS;

-- panel: Pickups per zone | map
SELECT PICKUP_ZONE_ID AS ZONE_ID,
       COUNT(*)       AS PICKUPS
FROM TAXI.LIVE_TRIPS
GROUP BY PICKUP_ZONE_ID;

-- panel: Trips per minute | line
SELECT TRUNC(PICKUP_TIME, 'MI') AS PICKUP_MINUTE,
       COUNT(*)                 AS TRIPS
FROM TAXI.LIVE_TRIPS
GROUP BY TRUNC(PICKUP_TIME, 'MI')
ORDER BY PICKUP_MINUTE;

-- panel: Top 10 pickup zones | table
SELECT z.ZONE_NAME,
       z.BOROUGH,
       COUNT(*) AS PICKUPS
FROM TAXI.LIVE_TRIPS t
JOIN TAXI.ZONES z ON z.LOCATION_ID = t.PICKUP_ZONE_ID
GROUP BY z.ZONE_NAME, z.BOROUGH
ORDER BY PICKUPS DESC
LIMIT 10;
