"""Replay NYC taxi trips into TAXI.LIVE_TRIPS, one simulated minute per tick - a live data flow for the dashboard.

    python replay.py                                  # New Year's Eve 2025, 18:00-02:00, 1 simulated minute per second
    python replay.py --speed 10                       # ten times faster
    python replay.py --start "2026-01-01 00:00" --end "2026-01-01 06:00" --keep
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta

from connection import connect_or_exit

INSERT = """
INSERT INTO TAXI.LIVE_TRIPS (PICKUP_TIME, DROPOFF_TIME, PICKUP_ZONE_ID, DROPOFF_ZONE_ID, PAYMENT_TYPE,
                             FARE_AMOUNT, TIP_AMOUNT, TOTAL_AMOUNT, TRIP_DISTANCE)
SELECT PICKUP_TIME, DROPOFF_TIME, PICKUP_ZONE_ID, DROPOFF_ZONE_ID, PAYMENT_TYPE,
       CAST(FARE_AMOUNT AS DECIMAL(9,2)), CAST(TIP_AMOUNT AS DECIMAL(9,2)),
       CAST(TOTAL_AMOUNT AS DECIMAL(9,2)), CAST(TRIP_DISTANCE AS DECIMAL(9,2))
FROM TAXI.TRIPS
WHERE PICKUP_TIME >= CAST({window_start} AS TIMESTAMP)
  AND PICKUP_TIME <  CAST({window_end} AS TIMESTAMP)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2025-12-31 18:00", help="first simulated minute (YYYY-MM-DD HH:MM)")
    ap.add_argument("--end", default="2026-01-01 02:00", help="stop before this minute (YYYY-MM-DD HH:MM)")
    ap.add_argument("--speed", type=float, default=1.0, help="simulated minutes per real second")
    ap.add_argument("--keep", action="store_true", help="keep existing rows in TAXI.LIVE_TRIPS")
    a = ap.parse_args()

    start, end = datetime.fromisoformat(a.start), datetime.fromisoformat(a.end)
    conn = connect_or_exit()
    if not a.keep:
        conn.execute("TRUNCATE TABLE TAXI.LIVE_TRIPS")
    print(f"Replaying {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} into TAXI.LIVE_TRIPS "
          f"at {a.speed:g} simulated minute(s) per second. Ctrl+C stops.")

    total, tick, t, began = 0, 0, start, time.monotonic()
    try:
        while t < end:
            nxt = t + timedelta(minutes=1)
            rows = conn.execute(INSERT, {"window_start": f"{t:%Y-%m-%d %H:%M:%S}",
                                         "window_end": f"{nxt:%Y-%m-%d %H:%M:%S}"}).rowcount()
            total += rows
            print(f"\r{t:%Y-%m-%d %H:%M}  +{rows:>5,} trips   total {total:>8,}", end="", flush=True)
            t, tick = nxt, tick + 1
            time.sleep(max(0.0, began + tick / a.speed - time.monotonic()))
    except KeyboardInterrupt:
        print(f"\nStopped at {t:%Y-%m-%d %H:%M} after {total:,} trips.")
        return
    finally:
        conn.close()
    print(f"\nDone: {total:,} trips replayed.")


if __name__ == "__main__":
    main()
