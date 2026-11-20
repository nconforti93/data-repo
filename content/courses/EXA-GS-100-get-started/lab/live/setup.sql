-- EXA-GS-100 lesson 5 setup: the one view behind the New Year's Eve dashboard.
--
-- TAXI.V_NYE_TRIPS holds the taxi trips that started on New Year's Eve 2025 between 18:00 and 04:00 the next
-- morning, from TAXI.TRIPS (lessons 3 and 4), with the pickup zone's name and borough from TAXI.ZONES.
-- Every panel of the dashboard queries this view with the time window the learner picks on the slider,
-- so changing the view changes every panel. Run this file again to put the view back.
--
-- The dashboard reads the view as the kit's read-only user MCP_READONLY, which the starter kit creates with
-- CREATE SESSION, USE ANY SCHEMA and SELECT ANY TABLE: it reads every table and view, never changes one.
-- So no GRANT is needed here - and none is lost when the view is replaced.

CREATE OR REPLACE VIEW TAXI.V_NYE_TRIPS AS
SELECT t.PICKUP_TIME,
       t.PICKUP_ZONE_ID,
       z.ZONE_NAME  AS PICKUP_ZONE,
       z.BOROUGH    AS PICKUP_BOROUGH,
       t.DROPOFF_ZONE_ID,
       t.PAYMENT_TYPE,
       t.FARE_AMOUNT,
       t.TIP_AMOUNT,
       t.TOTAL_AMOUNT
FROM TAXI.TRIPS t
JOIN TAXI.ZONES z ON z.LOCATION_ID = t.PICKUP_ZONE_ID
WHERE t.PICKUP_TIME >= TIMESTAMP '2025-12-31 18:00:00'
  AND t.PICKUP_TIME <  TIMESTAMP '2026-01-01 04:00:00';
