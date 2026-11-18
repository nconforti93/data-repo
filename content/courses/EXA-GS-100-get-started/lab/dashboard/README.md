# Live taxi dashboard

A small Dash app that shows New York taxi trips arriving in Exasol, live. Every panel is one SQL query in
`panels.sql`; the app re-reads the file every 2 seconds, so you change a panel by editing SQL and saving.

Needs Python 3.11+, the `TAXI` schema from the course (TRIPS, ZONES, LIVE_TRIPS) and `taxi_zones.geojson`
in this folder.

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Connection

With Exasol Personal on this machine there is nothing to set: the app connects to `127.0.0.1:8563` as `sys`,
reads the password from your Exasol Personal `secrets.json` and uses `nocertcheck`, as the local deployment's
connection instructions say.

For a database elsewhere (for example Exasol Personal in your cloud account) set `EXASOL_DSN`, `EXASOL_USER`,
`EXASOL_PASSWORD` and `EXASOL_FINGERPRINT` – the certificate fingerprint from that deployment's
`connection-instructions.txt`. The app refuses a remote database without a fingerprint.

## 3. Run

Two terminals, both with the virtual environment active:

```bash
python replay.py          # replays New Year's Eve 2025, 18:00-02:00, one simulated minute per second
python app.py             # open http://127.0.0.1:8050
```

`python replay.py --speed 10` runs ten times faster; `--start` / `--end` pick another window; `--keep` adds to
the rows already in `TAXI.LIVE_TRIPS` instead of starting empty.

## 4. Change a panel

Open `panels.sql`, edit a query or add a block, save. A block starts with a header line:

```text
-- panel: Average fare per borough | bar
```

Charts: `kpi` (one row, a tile per column), `line` (x, y), `bar` (label, length), `map` (zone id, shade) and
`table`. Charts read the first two columns, so name them as you like – but avoid reserved words such as
`VALUE`, `ZONE`, `TIME`, `HOUR` and `MINUTE`. A panel with an error shows the message in place of the chart
and comes back as soon as the SQL is fixed.
