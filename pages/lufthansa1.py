# 2026.05.05  15.00
import dash
import pandas as pd
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from datetime import datetime

# ----- 1. CONFIGURATION -----
DB_CONFIG = "postgresql+psycopg://sql_admin:sql_pass@postgresql:5432/n8n"
sql_engine = create_engine(DB_CONFIG, pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=1800,      
    connect_args={'connect_timeout': 5, 'keepalives': 1, 'keepalives_idle': 30, 'keepalives_interval': 10, 'keepalives_count': 5})

dash.register_page(__name__, icon="fa-plane", name="Lufthansa Flight", order=6)

# ---- Glass Card ----
CARD_STYLE = {
    "background": "rgba(255, 255, 255, 0.03)",
    "backdrop-filter": "blur(10px)",
    "border-radius": "15px", "border": "1px solid rgba(255, 255, 255, 0.1)",
    "padding": "15px", "width": "100%"
}

# -------------------
# LAYOUT
# -------------------
layout = dbc.Container([

    html.Div([
        html.H2("Lufthansa Dashboard", className="text-light fw-bold mb-0"),
        html.P(id='lh-metrics-update', className="text-muted small"),
    ], className="mb-3"),

    dcc.Interval(id='refresh', interval=60000),
    dcc.Store(id="lh-df-store"),

    # ---- 6 MINI CHART GRID (LIKE BYBIT) ----
    dbc.Row(id="lh-mini-charts", className="g-3 mb-4"),

    # ---- 3 SMALL KPI TABLE ----
    dbc.Row(id="lh-mini-tables", className="g-3 mb-4"),

    # ---- LOG TABLE ----
    html.Div([
        html.H5("Lufthansa Logs", className="mb-2", style={"color": "#f59e0b", "fontWeight": "500"}),
        html.Div(id='lh-log-table',
            style={"height": "300px", "overflowY": "auto", "fontSize": "12px"})
    ], style=CARD_STYLE)

], fluid=True)


# -------------------
# DATA CALLBACK
# -------------------
@callback(
    Output('lh-metrics-update', 'children'),    
    Output('lh-df-store', 'data'),
    Output('lh-mini-charts', 'children'),
    Output('lh-mini-tables', 'children'),
    Output('lh-log-table', 'children'),
    Input('refresh', 'n_intervals'),
)
def load_data_render(_):

    with sql_engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM lufthansa.flights", conn)               
        df_daily = pd.read_sql("SELECT DISTINCT ON (departure_scheduled_ts, route_key) * FROM lufthansa ORDER BY departure_scheduled_ts, route_key, id DESC")     
    if df.empty:
        return "No data", None, [], [], None
    if df_daily.empty:
        return "No data"

    # ---- parse dates (combine date + time columns) ----
    df["dep_sched_dt"] = pd.to_datetime(df["departure__scheduled__date"] + " " + df["departure__scheduled__time"], errors="coerce")
    df["dep_actual_dt"] = pd.to_datetime(df["departure__actual__date"] + " " + df["departure__actual__time"], errors="coerce")
    df["arr_sched_dt"] = pd.to_datetime(df["arrival__scheduled__date"] + " " + df["arrival__scheduled__time"], errors="coerce")
    df["arr_actual_dt"] = pd.to_datetime(df["arrival__actual__date"] + " " + df["arrival__actual__time"], errors="coerce")
    
    # ---- delays (safe) ----
    df["dep_delay_min"] = (df["dep_actual_dt"] - df["dep_sched_dt"]).dt.total_seconds() / 60
    df["arr_delay_min"] = (df["arr_actual_dt"] - df["arr_sched_dt"]).dt.total_seconds() / 60
    
    # ---- hour ----
    df["dep_hour"] = df["dep_sched_dt"].dt.hour
    df["_ingested_at"] = pd.to_datetime(df["_ingested_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # -------------------
    # 6 MINI CHARTS
    # -------------------
    mini_charts = []
    def make_card(title, content, is_graph=True):
        if is_graph:
            content.update_layout(height=200, margin=dict(l=10,r=10,t=15,b=15), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
        return dbc.Col([
        html.Div([
            html.H6(title, className="mb-1", style={"color": "#f59e0b", "fontWeight": "500"}),
            dcc.Graph(figure=content,config={'displayModeBar': False}, style={"height": "200px"}) 
            if is_graph else html.Div(content, style={"height": "200px", "overflowY": "auto"})
        ], style=CARD_STYLE)
    ], md=4) #className="d-flex"

    # 1. Daily Chart
    daily = df.groupby(df_daily["departure_scheduled_ts"].dt.floor("D")).size().reset_index(name="count")
    fig = px.bar(daily, x="departure_scheduled_ts", y="count", template="plotly_dark")
    fig.update_layout(height=250,  plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=10, b=10))

    # 1 Delay dist
    df_delay_filtered = df[df["dep_delay_min"].notna() & (df["dep_delay_min"] <= 100)]
    mini_charts.append(make_card("Departure Delay Dist", px.histogram(df_delay_filtered, x="dep_delay_min", nbins=25, template="plotly_dark")))

    # 2 Route delay
    route = df.groupby("route_key")["dep_delay_min"].mean().reset_index()
    mini_charts.append(make_card("Top Delay Routes", px.bar(route.sort_values("dep_delay_min", ascending=False).head(15), x="route_key", y="dep_delay_min", template="plotly_dark")))

    # 3 Airport traffic
    airport = df["arrival__airport_code"].value_counts().head(15).reset_index()
    airport.columns = ["airport", "count"]
    mini_charts.append(make_card("Arrival Airports", px.bar(airport, x="airport", y="count", template="plotly_dark")))

    # 4 Status
    status = df["status__code"].value_counts().reset_index()
    status.columns = ["status", "count"]
    mini_charts.append(make_card("Status", px.pie(status, names="status", values="count", hole=0.4)))

    # 5 Hour delay
    hour = df.groupby("dep_hour")["dep_delay_min"].mean().reset_index()
    mini_charts.append(make_card("Delay by Hour", px.line(hour, x="dep_hour", y="dep_delay_min", template="plotly_dark")))

    # 6 Aircraft
    aircraft = df["equipment__aircraft_code"].value_counts().reset_index()
    aircraft.columns = ["aircraft", "count"]
    mini_charts.append(make_card("Aircraft Usage", px.bar(aircraft.head(10), x="aircraft", y="count", template="plotly_dark")))

    # -------------------
    # 3 SMALL TABLE
    # -------------------
    dep_tbl = (df.groupby("route_key")["dep_delay_min"].mean().round(2).sort_values(ascending=False).head(10).reset_index())
    arr_tbl = (df.groupby("route_key")["arr_delay_min"].mean().round(2).sort_values(ascending=False).head(10).reset_index())   
    route_cnt = (df["route_key"].value_counts().head(10).reset_index())
    route_cnt.columns = ["route_key", "count"]

    def make_table(df_table):
        return dbc.Table.from_dataframe(df_table, striped=False, hover=True, responsive=True, borderless=True, className="text-light small",
        style={ "backgroundColor": "transparent", "--bs-table-bg": "transparent", "--bs-table-accent-bg": "transparent", "color": "white"})

    mini_tables = [
    make_card("Dep Delay", make_table(dep_tbl), is_graph=False),
    make_card("Arr Delay", make_table(arr_tbl), is_graph=False),
    make_card("Route Volume", make_table(route_cnt), is_graph=False)
    ]

    # -------------------
    # LOG TABLE
    # -------------------
    #table = dbc.Table.from_dataframe(df.tail(100), striped=False, borderless=True, className="text-light small")
    status_cols = [1, 23, 24, 14, 15]
    table = dbc.Table.from_dataframe(df.iloc[-100:, status_cols], striped=False, hover=True, responsive=True, borderless=True,
        className="text-light m-0", style={"backgroundColor": "transparent",  "--bs-table-bg": "transparent", "--bs-table-accent-bg": "transparent", "color": "white"})

    return f"Updated → {df['_ingested_at'].iloc[-1]}", df.to_dict("records"), mini_charts, mini_tables, table

