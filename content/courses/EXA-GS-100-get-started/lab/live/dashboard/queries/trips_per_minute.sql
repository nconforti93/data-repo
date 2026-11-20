-- Trips per minute over the whole night, for the line chart (the selected window is drawn on top of it).
SELECT TRUNC(PICKUP_TIME, 'MI')  AS PICKUP_MINUTE,
       COUNT(*)                  AS TRIPS
FROM TAXI.V_NYE_TRIPS
GROUP BY TRUNC(PICKUP_TIME, 'MI')
ORDER BY PICKUP_MINUTE
