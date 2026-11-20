# New Year's Eve on New York's taxis – the lesson 5 dashboard

A small Dash app, hosted on the starter kit's Dash Server, that shows New Year's Eve 2025 (18:00 to 04:00) on New
York's yellow taxis. Pick a time window with the slider, or press Play to sweep a one-hour window through the
night. Every panel queries one view, `TAXI.V_NYE_TRIPS` (`../setup.sql`), as the kit's read-only user
`MCP_READONLY`, with the selected window as parameters – nothing is computed in advance.

| File | What it does |
|---|---|
| `app.py` | layout, slider, Play, and the callbacks that run the queries |
| `queries/kpis.sql` | trips, revenue and card tip % for the window (tiles) |
| `queries/zones.sql` | pickups per zone for the window (map and Top 10) |
| `queries/trips_per_minute.sql` | trips per minute over the whole night (line chart) |
| `queries/sql_smoke.json` | sample windows Dash Server uses to test the queries before it deploys |
| `taxi_zones.geojson` | the taxi zone shapes for the map (NYC Open Data) |
| `dash-app.json`, `requirements.txt` | app name, route, the `starter-kit` database profile, Python packages |
| `install.sh`, `install.py` | upload the files to Dash Server and deploy the app |

No credentials live in any file: Dash Server supplies them through its `starter-kit` profile.

## Deploy it

1. Check that Dash Server runs: `exakit status` (else `exakit start dash-server`).
2. Create the view: in the `live` folder, `exasol connect -f setup.sql`.
3. Deploy: in this folder, `./install.sh` (run it again after you change a file here).
4. Open the address the script prints (default `http://127.0.0.1:5100/apps/nye-taxis`).

## Change what it shows

Rewrite the view (`CREATE OR REPLACE VIEW TAXI.V_NYE_TRIPS AS …`, for example with `AND t.PAYMENT_TYPE = 1` for
card payments only). The dashboard re-runs its queries every 5 seconds, so every panel follows – no redeploy.
`exasol connect -f setup.sql` puts the view back.
