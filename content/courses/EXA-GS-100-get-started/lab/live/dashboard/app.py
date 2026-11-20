"""EXA-GS-100 lesson 5: New Year's Eve 2025 on New York's yellow taxis, with a time slider.

Every panel queries one view, TAXI.V_NYE_TRIPS (lab/live/setup.sql), as the kit's read-only user, through
Dash Server's starter-kit profile - no credentials in any file. Moving the slider (or pressing Play) runs the
queries in queries/*.sql again with the selected window as parameters: nothing is pre-computed. A slow refresh
re-runs them every few seconds too, so a learner who rewrites the view sees every panel follow without
touching the dashboard.
"""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, Patch, State, ctx, dcc, html

HERE = Path(__file__).parent
_spec = importlib.util.spec_from_file_location("dse", HERE / "dash_server_exasol.py")
dse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dse)

TITLE = "New Year's Eve on New York's taxis"
SUBTITLE = "Dec 31, 2025, 18:00 to Jan 1, 2026, 04:00 · every panel queries the view TAXI.V_NYE_TRIPS"
NIGHT_START = datetime(2025, 12, 31, 18, 0)
NIGHT_MIN = 600                  # 18:00 -> 04:00
STEP_MIN = 5                     # slider step
PLAY_WINDOW_MIN = 60             # Play uses this width when the whole night is selected
PLAY_STEP_MIN = 5                # Play moves the window 5 minutes per tick ...
PLAY_TICK_MS = 500               # ... twice a second: about a minute for the night
REFRESH_MS = 5000                # picks up a rewritten view without touching the dashboard
MAP_MAX_PER_HOUR = 400           # fixed colour scale, so the shading means the same at every time
LINE_MAX_PER_MINUTE = 240        # fixed scale for trips per minute (the night peaks at 232)

INK, MUTED, FAINT, LINE = "#0f172a", "#64748b", "#94a3b8", "#e2e8f0"
NAVY, ACCENT, BG = "#1f3047", "#2563eb", "#f3f4f6"
CARD = {"background": "white", "borderRadius": "10px", "padding": "10px 14px",
        "boxShadow": "0 1px 3px rgba(0,0,0,.08)", "minWidth": 0}
CARD_TITLE = {"fontWeight": 600, "fontSize": "14px", "color": INK, "marginBottom": "4px"}
# One hue, light to dark: more pickups per hour, darker blue; a zone with no pickups at all stays white.
# The steps sit low, so a quiet zone (a few dozen pickups an hour) is already visible; 400+ is the darkest.
MAP_SCALE = [[0.0, "#ffffff"], [0.01, "#dbeafe"], [0.08, "#93c5fd"], [0.25, "#3b82f6"], [0.55, "#1d4ed8"],
             [1.0, "#172554"]]

# 263 shapes for 260 zone ids (two zones have several shapes): every shape gets its own id, and its colour
# comes from its zone's LocationID.
ZONES_GEOJSON = json.loads((HERE / "taxi_zones.geojson").read_text(encoding="utf-8"))
SHAPE_ZONE, SHAPE_NAME = [], []
for i, feature in enumerate(ZONES_GEOJSON["features"]):
    props = feature.get("properties") or {}
    feature["id"] = str(i)
    SHAPE_ZONE.append(int(props.get("LocationID") or props.get("location_id") or -1))
    SHAPE_NAME.append(f"{props.get('zone', '?')} ({props.get('borough', '?')})")
SHAPE_IDS = [str(i) for i in range(len(SHAPE_ZONE))]


def clock(minutes):
    return (NIGHT_START + timedelta(minutes=minutes)).strftime("%H:%M")


def ts(minutes):
    return (NIGHT_START + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def error_box(message):
    return html.Div([html.Strong("Exasol query failed"),
                     html.Pre(message or "Unknown error",
                              style={"whiteSpace": "pre-wrap", "wordBreak": "break-word", "margin": "6px 0 0",
                                     "fontSize": "12px", "maxHeight": "160px", "overflow": "auto"})],
                    style={"background": "#fff7ed", "border": "1px solid #fdba74", "borderRadius": "8px",
                           "padding": "10px", "color": INK, "fontSize": "13px", "minWidth": 0})


def kpi(label, value):
    return html.Div([html.Div(label, style={"fontSize": "11px", "color": MUTED, "textTransform": "uppercase",
                                            "letterSpacing": "0.05em"}),
                     html.Div(value, style={"fontSize": "22px", "fontWeight": 700, "color": NAVY,
                                            "marginTop": "2px", "fontVariantNumeric": "tabular-nums"})],
                    style={**CARD, "flex": "1 1 110px", "padding": "8px 14px"})


def kpi_tiles(row):
    if dse.has_error(row):
        return [error_box(row.get("_error"))]
    trips, revenue, tip = num(row.get("TRIPS")), num(row.get("REVENUE_USD")), num(row.get("CARD_TIP_PCT"))
    return [kpi("Trips", "—" if trips is None else f"{int(trips):,}"),
            kpi("Revenue", "—" if revenue is None else f"${int(revenue):,}"),
            kpi("Card tip %", "—" if tip is None else f"{tip:.1f}%")]


def map_base():
    fig = go.Figure(go.Choroplethmap(
        geojson=ZONES_GEOJSON, locations=SHAPE_IDS, z=[0] * len(SHAPE_IDS), customdata=[0] * len(SHAPE_IDS),
        text=SHAPE_NAME, zmin=0, zmax=MAP_MAX_PER_HOUR, colorscale=MAP_SCALE,
        marker={"opacity": 0.8, "line": {"width": 0.4, "color": "white"}},
        hovertemplate="%{text}<br>%{customdata:,} pickups in the window (%{z:,.0f} per hour)<extra></extra>",
        colorbar={"title": {"text": "Pickups<br>per hour", "font": {"size": 11}}, "thickness": 10, "len": 0.5,
                  "x": 0.99, "xanchor": "right", "y": 0.98, "yanchor": "top", "tickfont": {"size": 10},
                  "bgcolor": "rgba(255,255,255,.85)"},
    ))
    fig.update_layout(height=498, margin={"l": 0, "r": 0, "t": 0, "b": 0}, uirevision="keep",
                      map={"style": "carto-positron", "center": {"lat": 40.752, "lon": -73.905}, "zoom": 9.95})
    return fig


def map_patch(rows, minutes):
    patch = Patch()
    counts = {} if dse.has_error(rows) else {int(num(r["ZONE_ID"])): int(num(r["PICKUPS"])) for r in rows}
    per_shape = [counts.get(zone, 0) for zone in SHAPE_ZONE]
    patch["data"][0]["customdata"] = per_shape
    patch["data"][0]["z"] = [round(n * 60 / minutes, 1) for n in per_shape]
    return patch


def window_shape(start, end):
    return {"type": "rect", "xref": "x", "yref": "paper", "x0": ts(start), "x1": ts(end), "y0": 0, "y1": 1,
            "fillcolor": "rgba(37,99,235,0.14)", "line": {"width": 1, "color": "rgba(37,99,235,0.6)"},
            "layer": "below"}


def line_figure(rows, start, end):
    fig = go.Figure(layout={
        "height": 134, "margin": {"l": 44, "r": 8, "t": 6, "b": 22}, "plot_bgcolor": "white",
        "uirevision": "keep", "showlegend": False, "hovermode": "x",
        "xaxis": {"range": [ts(0), ts(NIGHT_MIN)], "gridcolor": "#f1f5f9", "tickformat": "%H:%M",
                  "tickvals": [ts(m) for m in (120, 240, 360, 480)],
                  "tickfont": {"size": 10, "color": MUTED}, "showspikes": True, "spikethickness": 1,
                  "spikecolor": FAINT, "spikedash": "solid"},
        "yaxis": {"gridcolor": LINE, "range": [0, LINE_MAX_PER_MINUTE], "tickfont": {"size": 10, "color": MUTED}},
        "shapes": [window_shape(start, end)],
    })
    if dse.has_error(rows):
        fig.add_annotation(text="Query failed - see the tiles above", showarrow=False, x=0.5, y=0.5,
                           xref="paper", yref="paper", font={"color": "#c2410c"})
        return fig
    trips = [num(r["TRIPS"]) or 0 for r in rows]
    if trips and max(trips) > LINE_MAX_PER_MINUTE:            # a view with more trips: make room
        fig.update_yaxes(range=[0, max(trips) * 1.05])
    fig.add_trace(go.Scatter(x=[r["PICKUP_MINUTE"] for r in rows], y=trips,
                             mode="lines", line={"color": ACCENT, "width": 1.5},
                             hovertemplate="%{x|%H:%M}  %{y:,} trips<extra></extra>"))
    return fig


def top_table(rows):
    if dse.has_error(rows):
        return error_box(rows[0].get("_error"))
    top = sorted(((int(num(r["PICKUPS"])), str(r["ZONE_NAME"]), str(r["BOROUGH"])) for r in rows),
                 key=lambda t: (-t[0], t[1]))[:10]
    if not top:
        return html.Div("No trips in this window.", style={"color": FAINT, "padding": "8px 0"})
    most = top[0][0]
    th = {"textAlign": "left", "padding": "3px 8px", "fontSize": "11px", "color": MUTED, "fontWeight": 500,
          "borderBottom": f"1px solid {LINE}"}
    td = {"padding": "2px 8px", "fontSize": "12.5px", "color": INK, "borderBottom": "1px solid #f1f5f9",
          "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"}
    body = []
    for rank, (pickups, zone, borough) in enumerate(top, start=1):
        bar = html.Div(style={"height": "8px", "borderRadius": "4px", "background": ACCENT, "opacity": 0.55,
                              "width": f"{max(4, round(100 * pickups / most))}%"})
        body.append(html.Tr([html.Td(rank, style={**td, "color": MUTED}),
                             html.Td(zone, style=td, title=zone),
                             html.Td(borough, style={**td, "color": MUTED}),
                             html.Td(f"{pickups:,}", style={**td, "textAlign": "right",
                                                             "fontVariantNumeric": "tabular-nums"}),
                             html.Td(bar, style=td)]))
    # table-layout: fixed takes the column widths from the header row
    head = html.Thead(html.Tr([html.Th("#", style={**th, "width": "26px"}), html.Th("Pickup zone", style=th),
                               html.Th("Borough", style={**th, "width": "21%"}),
                               html.Th("Pickups", style={**th, "textAlign": "right", "width": "15%"}),
                               html.Th("", style={**th, "width": "17%"})]))
    return html.Table([head, html.Tbody(body)],
                      style={"borderCollapse": "collapse", "width": "100%", "tableLayout": "fixed"})


def release_session(server):
    """Close this request's database session now.

    Dash Server (0.2.1) keeps one session per request thread and serves every request on a new thread, so
    without this each slider move would leave a session open until Python's garbage collector finds it -
    and Exasol Personal allows 20 sessions in all. Harmless if a later Dash Server version changes this.
    """
    try:
        server.extensions["exasol_dashboard_service"].connection_manager.close_all_for_thread()
    except Exception:  # noqa: BLE001 - never let the clean-up break a panel
        pass


def create_dash_app(server, url_base_pathname, metadata):
    app = Dash(__name__, server=server, routes_pathname_prefix="/",
               requests_pathname_prefix=url_base_pathname.rstrip("/") + "/", title=TITLE)

    def query(sql_file, params=None, one=False):
        loader = dse.load_row if one else dse.load_rows
        return loader(server, metadata, __file__, sql_file, params=params or {})

    marks = {m: {"label": clock(m), "style": {"fontSize": "11px", "color": MUTED}}
             for m in range(0, NIGHT_MIN + 1, 60)}
    play_style = {"background": NAVY, "color": "white", "border": "none", "borderRadius": "8px",
                  "padding": "8px 16px", "fontSize": "14px", "fontWeight": 600, "cursor": "pointer",
                  "minWidth": "96px"}

    app.layout = html.Div(
        style={"fontFamily": "system-ui, -apple-system, Segoe UI, sans-serif", "background": BG,
               "padding": "12px 14px", "boxSizing": "border-box", "color": INK,
               "minHeight": "calc(100vh - 34px)"},             # 34 px: Dash Server's footer
        children=[
            dcc.Interval(id="play-tick", interval=PLAY_TICK_MS, disabled=True),
            dcc.Interval(id="refresh", interval=REFRESH_MS),
            html.Div(style={**CARD, "background": NAVY, "color": "white", "marginBottom": "10px",
                            "display": "flex", "alignItems": "baseline", "gap": "14px", "flexWrap": "wrap"},
                     children=[html.Div(TITLE, style={"fontSize": "18px", "fontWeight": 700}),
                               html.Div(SUBTITLE, style={"fontSize": "12.5px", "color": "#cbd5e1"})]),
            html.Div(style={**CARD, "display": "flex", "alignItems": "center", "gap": "18px",
                            "marginBottom": "10px", "padding": "8px 14px"}, children=[
                html.Button("▶ Play", id="play", n_clicks=0, style=play_style),
                html.Div(style={"flex": 1, "minWidth": 0, "paddingTop": "6px",
                                "--Dash-Fill-Interactive-Strong": ACCENT}, children=[
                    dcc.RangeSlider(id="window", min=0, max=NIGHT_MIN, step=STEP_MIN, value=[0, NIGHT_MIN],
                                    marks=marks, allowCross=False, pushable=STEP_MIN, updatemode="mouseup",
                                    allow_direct_input=False, tooltip=None),
                ]),
                html.Div(style={"textAlign": "right", "minWidth": "150px"}, children=[
                    html.Div("Selected window", style={"fontSize": "11px", "color": MUTED,
                                                       "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                    html.Div(id="window-label", style={"fontSize": "20px", "fontWeight": 700, "color": NAVY,
                                                       "fontVariantNumeric": "tabular-nums"}),
                ]),
            ]),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "10px"}, children=[
                html.Div(style={**CARD, "flex": "1.2 1 480px"}, children=[
                    html.Div("Pickups per taxi zone", style=CARD_TITLE),
                    dcc.Graph(id="zone-map", figure=map_base(),
                              config={"scrollZoom": False, "displayModeBar": False}),
                ]),
                html.Div(style={"display": "flex", "flexDirection": "column", "gap": "10px", "minWidth": 0,
                                "flex": "1 1 400px"}, children=[
                    html.Div(id="kpis", style={"display": "flex", "flexWrap": "wrap", "gap": "10px"}),
                    html.Div(style=CARD, children=[
                        html.Div("Trips per minute (the shaded part is your window)", style=CARD_TITLE),
                        dcc.Graph(id="trips-line", config={"displayModeBar": False}),
                    ]),
                    html.Div(style=CARD, children=[
                        html.Div("Top 10 pickup zones", style=CARD_TITLE),
                        html.Div(id="top-table"),
                    ]),
                ]),
            ]),
        ],
    )

    # The label follows the handles while they are dragged, in the browser; the panels follow on release.
    app.clientside_callback(
        """function (drag, value) {
            const trig = ((dash_clientside.callback_context.triggered || [])[0] || {}).prop_id || '';
            const w = (trig.endsWith('drag_value') && drag) ? drag : value;
            const t = m => new Date(Date.UTC(2025, 11, 31, 18, m)).toISOString().slice(11, 16);
            return t(w[0]) + ' – ' + t(w[1]);
        }""",
        Output("window-label", "children"), Input("window", "drag_value"), Input("window", "value"),
    )

    # Play and Pause run in the browser: a step only moves the slider, and the slider's new value runs the
    # queries (update below). On the server, a Play tick arriving while a click was still on its way made Dash
    # drop the click - Pause then needed a second click.
    app.clientside_callback(
        """function (clicks, ticks, w, stopped) {
            const NIGHT = %d, STEP = %d, WIDTH = %d, nu = dash_clientside.no_update;
            const clicked = (dash_clientside.callback_context.triggered || [])
                .some(t => t.prop_id === 'play.n_clicks');
            const start = w[0], end = w[1], width = end - start;
            if (clicked) {
                if (!stopped) return [nu, true, '▶ Play'];                       // playing: pause
                if (width >= NIGHT) return [[0, WIDTH], false, '❚❚ Pause'];      // whole night: sweep one hour
                if (end >= NIGHT) return [[0, width], false, '❚❚ Pause'];        // at the end: start again
                return [nu, false, '❚❚ Pause'];
            }
            const shift = Math.min(STEP, NIGHT - end);
            if (shift <= 0) return [nu, true, '▶ Play'];                         // reached 04:00: stop
            return [[start + shift, end + shift], nu, nu];
        }""" % (NIGHT_MIN, PLAY_STEP_MIN, PLAY_WINDOW_MIN),
        Output("window", "value"), Output("play-tick", "disabled"), Output("play", "children"),
        Input("play", "n_clicks"), Input("play-tick", "n_intervals"),
        State("window", "value"), State("play-tick", "disabled"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("kpis", "children"), Output("zone-map", "figure"), Output("trips-line", "figure"),
        Output("top-table", "children"),
        Input("window", "value"), Input("refresh", "n_intervals"),
    )
    def update(window, _refresh):
        start, end = window
        params = {"start_min": int(start), "end_min": int(end)}
        totals = query("queries/kpis.sql", params, one=True) or {}
        zones = query("queries/zones.sql", params)
        if ctx.triggered_id == "window":                     # slider moved: only the shading changes
            line = Patch()
            line["layout"]["shapes"][0] = window_shape(start, end)
        else:                                                 # first load or refresh: re-read the whole night
            line = line_figure(query("queries/trips_per_minute.sql"), start, end)
        release_session(server)
        return kpi_tiles(totals), map_patch(zones, end - start), line, top_table(zones)

    return app
