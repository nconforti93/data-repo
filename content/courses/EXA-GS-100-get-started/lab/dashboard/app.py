"""Live NYC taxi dashboard for Exacademy. Every panel is a SQL block in panels.sql, re-read every 2 seconds.

    python app.py                 # http://127.0.0.1:8050
    python app.py --port 8060
"""
from __future__ import annotations

import argparse
import json
import re
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import plotly.graph_objects as go
import pyexasol
from dash import Dash, Input, Output, dcc, html

from connection import connect, connect_or_exit

HERE = Path(__file__).resolve().parent
PANELS_FILE = HERE / "panels.sql"
HEADER = re.compile(r"^--\s*panel:\s*(?P<title>.+?)\s*\|\s*(?P<chart>\w+)\s*$", re.I | re.M)
CHARTS = {"kpi", "line", "bar", "table", "map"}

INK, INK_2, MUTED, GRID, SURFACE, PAGE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb", "#f9f9f7"
SERIES = "#2a78d6"
SEQUENTIAL = [[0.0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"], [0.75, "#1c5cab"], [1.0, "#0d366b"]]


def find_zones() -> dict:
    for p in (HERE / "taxi_zones.geojson",
              HERE.parents[3] / "datasets" / "nyc_taxi_zones" / "taxi_zones.geojson"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise SystemExit("taxi_zones.geojson not found - download it next to app.py.")


ZONES = find_zones()
ZONE_IDS = sorted({f["properties"]["LocationID"] for f in ZONES["features"]})


class Database:
    """One shared connection; Dash serves callbacks from several threads."""

    def __init__(self) -> None:
        self._lock, self._conn = threading.Lock(), None

    def query(self, sql: str) -> tuple[list[str], list[tuple]]:
        with self._lock:
            if self._conn is None:
                self._conn = connect()
            try:
                stmt = self._conn.execute(sql)
            except pyexasol.ExaQueryError:
                raise  # a problem in the SQL; the connection is fine
            except Exception:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                self._conn = None  # reconnect on the next refresh
                raise
            return stmt.column_names(), stmt.fetchall()


DB = Database()


def read_panels() -> list[dict]:
    text = PANELS_FILE.read_text(encoding="utf-8")
    heads = list(HEADER.finditer(text))
    panels = []
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        sql = body.strip().rstrip(";").strip()
        panels.append({"title": h["title"], "chart": h["chart"].lower(), "sql": sql})
    return panels


def num(v):
    return float(v) if isinstance(v, Decimal) else v


def fmt(v) -> str:
    if v is None:
        return "–"
    if isinstance(v, (int, Decimal, float)):
        v = num(v)
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    return str(v)


WORDS = {"PCT": "%", "USD": "(USD)", "ID": "ID"}


def label(col: str) -> str:
    if col != col.upper():  # a quoted alias like "Revenue (USD)" is shown as written
        return col
    text = " ".join(WORDS.get(w, w.lower()) for w in col.split("_"))
    return text[:1].upper() + text[1:]


def base_layout(fig: go.Figure, cols: list[str]) -> go.Figure:
    fig.update_layout(margin=dict(l=48, r=16, t=8, b=40), height=320, paper_bgcolor=SURFACE,
                      plot_bgcolor=SURFACE, font=dict(color=INK_2, size=13), showlegend=False,
                      hoverlabel=dict(bgcolor=SURFACE, font_color=INK))
    fig.update_xaxes(title=label(cols[0]), gridcolor=GRID, linecolor=GRID, tickfont_color=MUTED)
    fig.update_yaxes(title=label(cols[1]), gridcolor=GRID, zeroline=False, tickfont_color=MUTED)
    return fig


def render(panel: dict, cols: list[str], rows: list[tuple]):
    chart = panel["chart"]
    if chart == "kpi":
        row = rows[0] if rows else [None] * len(cols)
        return html.Div(className="tiles", children=[
            html.Div(className="tile", children=[html.Div(label(c), className="tile-label"),
                                                 html.Div(fmt(v), className="tile-value")])
            for c, v in zip(cols, row)])
    if chart == "table":
        return html.Table(className="grid", children=[
            html.Thead(html.Tr([html.Th(label(c)) for c in cols])),
            html.Tbody([html.Tr([html.Td(fmt(v)) for v in r]) for r in rows[:20]])])
    if len(cols) < 2:
        raise ValueError(f"a {chart} panel needs two columns, this query returns {len(cols)}")
    xs, ys = [r[0] for r in rows], [num(r[1]) for r in rows]
    if chart == "line":
        fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=SERIES, width=2),
                                   hovertemplate=f"%{{x}}<br>{label(cols[1])}: %{{y:,}}<extra></extra>"))
        fig.update_layout(hovermode="x")
        fig.update_xaxes(showspikes=True, spikecolor=MUTED, spikethickness=1, spikedash="solid")
        return dcc.Graph(figure=base_layout(fig, cols), config={"displayModeBar": False})
    if chart == "bar":
        fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=SERIES,
                               hovertemplate=f"%{{x}}<br>{label(cols[1])}: %{{y:,}}<extra></extra>"))
        fig.update_layout(barcornerradius=4, bargap=0.3)
        return dcc.Graph(figure=base_layout(fig, cols), config={"displayModeBar": False})
    # map: every zone is drawn, zones without rows get 0
    values = {int(num(z)): v for z, v in zip(xs, ys) if z is not None}
    names = {f["properties"]["LocationID"]: f"{f['properties']['zone']} ({f['properties']['borough']})"
             for f in ZONES["features"]}
    fig = go.Figure(go.Choropleth(
        geojson=ZONES, featureidkey="properties.LocationID", locations=ZONE_IDS,
        z=[values.get(z, 0) for z in ZONE_IDS], text=[names[z] for z in ZONE_IDS],
        colorscale=SEQUENTIAL, marker_line_color=SURFACE, marker_line_width=0.5,
        colorbar=dict(title=label(cols[1]), thickness=10, outlinewidth=0, tickfont_color=MUTED),
        hovertemplate=f"%{{text}}<br>{label(cols[1])}: %{{z:,}}<extra></extra>"))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor=SURFACE)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=420, paper_bgcolor=SURFACE)
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def card(panel: dict, body, wide: bool) -> html.Div:
    return html.Div(className="card wide" if wide else "card",
                    children=[html.H2(panel["title"]), body])


def error_card(panel: dict, err: Exception) -> html.Div:
    text = str(getattr(err, "message", "") or err).strip()
    first = text.splitlines()[0] if text else type(err).__name__
    return html.Div(className="card error", children=[
        html.H2(f"{panel['title']} - this panel has a problem"),
        html.P(first[:400]),
        html.P("Fix the SQL in panels.sql and save; the panel comes back on the next refresh.", className="hint")])


app = Dash(__name__, title="Taxi dashboard · Exacademy", update_title=None)
app.index_string = app.index_string.replace("</head>", """<style>
body{margin:0;background:%(page)s;color:%(ink)s;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 24px 4px} header h1{margin:0;font-size:22px} header p{margin:4px 0 0;color:%(ink2)s;font-size:13px}
#panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px;padding:16px 24px 32px}
.card{background:%(surface)s;border:1px solid %(grid)s;border-radius:8px;padding:14px 16px}
.card.wide{grid-column:1/-1} .card h2{margin:0 0 8px;font-size:15px;font-weight:600;color:%(ink)s}
.card.error{border-color:#d03b3b} .card.error p{margin:6px 0;font-family:ui-monospace,monospace;font-size:13px}
.card.error .hint{font-family:inherit;color:%(ink2)s}
.tiles{display:flex;flex-wrap:wrap;gap:12px} .tile{flex:1 1 200px;padding:8px 4px}
.tile-label{color:%(ink2)s;font-size:13px}
.tile-value{font-size:26px;font-weight:600;margin-top:4px;white-space:nowrap;font-variant-numeric:tabular-nums}
table.grid{border-collapse:collapse;width:100%%;font-size:14px}
table.grid th{text-align:left;color:%(ink2)s;font-weight:600;border-bottom:1px solid %(grid)s;padding:6px 8px}
table.grid td{border-bottom:1px solid %(grid)s;padding:6px 8px}
@media (max-width:480px){#panels{grid-template-columns:1fr;padding:12px}}
</style></head>""" % {"page": PAGE, "ink": INK, "ink2": INK_2, "surface": SURFACE, "grid": GRID})

app.layout = html.Div([
    html.Header([html.H1("NYC taxis, live from Exasol"), html.P(id="status")]),
    html.Div(id="panels"),
    dcc.Interval(id="tick", interval=2000),
])


@app.callback(Output("panels", "children"), Output("status", "children"), Input("tick", "n_intervals"))
def refresh(_):
    out = []
    try:
        panels = read_panels()
    except OSError as e:
        return [], f"Cannot read panels.sql: {e}"
    for p in panels:
        if p["chart"] not in CHARTS:
            out.append(error_card(p, ValueError(f"unknown chart '{p['chart']}' - use one of {sorted(CHARTS)}")))
            continue
        try:
            cols, rows = DB.query(p["sql"])
            out.append(card(p, render(p, cols, rows), wide=p["chart"] in ("kpi", "map")))
        except Exception as e:  # noqa: BLE001 - a broken panel must not take the dashboard down
            out.append(error_card(p, e))
    return out, f"{len(panels)} panels from panels.sql · refreshed {datetime.now():%H:%M:%S}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    DB._conn = connect_or_exit()  # fail fast on connection problems
    print(f"Dashboard on http://{a.host}:{a.port} - edit panels.sql and watch it update. Ctrl+C stops.")
    app.run(host=a.host, port=a.port, debug=False)
