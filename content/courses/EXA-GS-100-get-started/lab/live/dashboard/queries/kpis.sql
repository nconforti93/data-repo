-- KPI tiles for the selected window: trips, revenue, and the tip as a share of the fare on card payments
-- (cash tips are not recorded in the TLC data). The window is minutes after 18:00 on New Year's Eve 2025.
SELECT COUNT(*)                     AS TRIPS,
       ROUND(SUM(TOTAL_AMOUNT), 0)  AS REVENUE_USD,
       ROUND(100 * SUM(CASE WHEN PAYMENT_TYPE = 1 AND FARE_AMOUNT > 0 THEN TIP_AMOUNT END)
                 / NULLIF(SUM(CASE WHEN PAYMENT_TYPE = 1 AND FARE_AMOUNT > 0 THEN FARE_AMOUNT END), 0), 1)
                                    AS CARD_TIP_PCT
FROM TAXI.V_NYE_TRIPS
WHERE PICKUP_TIME >= ADD_MINUTES(TIMESTAMP '2025-12-31 18:00:00', {start_min!d})
  AND PICKUP_TIME <  ADD_MINUTES(TIMESTAMP '2025-12-31 18:00:00', {end_min!d})
