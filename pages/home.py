# 2026.05.05  11.00
import dash
from dash import html, callback, Output, Input
import dash_bootstrap_components as dbc
import pandas as pd
import sys
import platform
import os
import shutil
import psutil
from importlib.metadata import version, PackageNotFoundError

CARD_STYLE = {
    "background": "rgba(255, 255, 255, 0.03)", "backdropFilter": "blur(10px)",
    "borderRadius": "15px", "border": "1px solid rgba(255, 255, 255, 0.1)", "padding": "20px"}

TABLE_STYLE = { "backgroundColor": "transparent", "--bs-table-bg": "transparent", "--bs-table-accent-bg": "transparent", "color": "white",}

PACKAGES = ["fastapi", "fastmcp", "pandas", "dash", "dash-bootstrap-components", "ccxt", "scikit-learn", "SQLAlchemy", "dlt", "psycopg"]

def get_runtime_info():
    info_header = [("Python Version", sys.version.split()[0]), ("OS Platform", platform.platform()[:11])]
    pkg_rows = []
    for p in PACKAGES:
        try:
            pkg_rows.append((p, version(p)))
        except PackageNotFoundError:
            pkg_rows.append((p, "not installed"))

    return info_header, pkg_rows

def get_host_metrics():
    cpu = psutil.cpu_percent(interval=0.5)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")

    return [ ("CPU Usage", f"{cpu} %"), ("CPU Cores", psutil.cpu_count(logical=True)), ("CPU Frequency", f"{cpu_freq.current:.0f} MHz"),
        ("Memory Usage", f"{mem.percent} %"), ("Memory Total", f"{mem.total / (1024**3):.1f} GB"),
        ("Disk Usage", f"{disk.used / disk.total * 100:.1f} %"), ("Disk Total", f"{disk.total / (1024**3):.1f} GB")]

dash.register_page( __name__, path="/", name="Overview", icon="fa-home", order=0)

layout = dbc.Container([

    # Header
    html.Div([
        html.H1("System Control Center", className="text-light fw-bold"),
        html.P("Monitoring 4 Data Grabbers & 1 ML Engine", className="text-muted"),
    ], className="mb-5"),

    # ----- Status cards -----
    dbc.Row([
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H5("Crypto Engine", className="text-info"),
                html.P("Status: Active", className="small"),
                html.Div("BTC: $96,432", className="h4"),
                dbc.Button("Crypto", href="/bybit", size="sm", color="info", outline=True)
            ]), style={"background": "rgba(255,255,255,0.05)"}), width=4),

        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H5("Lufthansa API", className="text-warning"),
                html.P("Status: Syncing", className="small"),
                html.Div("Last: 2m ago", className="h4"),
                dbc.Button("Lufthansa", href="/lufthansa", size="sm", color="warning", outline=True) 
            ]), style={"background": "rgba(255,255,255,0.05)"}), width=4),

        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H5("ML Engine", className="text-success"),
                html.P("Backend: Databricks", className="small"),
                html.Div("98% Acc", className="h4"),
                dbc.Button("DatabrickML", href="/databricks", size="sm", color="success", outline=True)
            ]), style={"background": "rgba(255,255,255,0.05)"}), width=4)
        
    ], className="mb-5"),

    dbc.Row([
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                dbc.Row([
                dbc.Col(html.H4("Runtime Environment", className="text-info fw-semibold"), width="auto"),
                 dbc.Col(dbc.Button("Refresh", id="refresh-btn", color="info", outline=True, size="sm", className="mt-3"), width="auto")
                ],   align="center", justify="between", className="mb-3"),
                html.Div(id="env-table")
            ]), style=CARD_STYLE), width=6),

    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.H4("Package Versions", className="text-info fw-semibold"),
                html.Div(id="packages-table"),
            ]), style=CARD_STYLE), width=6),

    ], className="mb-4")

], fluid=True)


@callback(
    Output("env-table", "children"),
    Output("packages-table", "children"),
    Input("refresh-btn", "n_clicks"),
)
def render_tables(_):
    
    runtime_info, pkg_rows = get_runtime_info()
    host_metrics = get_host_metrics()

    env_df = pd.DataFrame(runtime_info + host_metrics, columns=["Metric", "Value"])

    env_tbl = dbc.Table.from_dataframe(env_df, striped=False, hover=True, responsive=True, borderless=True, className="text-light table-sm m-0",
        style=TABLE_STYLE)

    pkg_df = pd.DataFrame(pkg_rows, columns=["Package", "Version"])

    pkg_tbl = dbc.Table.from_dataframe(pkg_df, striped=False, hover=True, responsive=True, borderless=True, className="text-light table-sm m-0", #font-monospace"
        style=TABLE_STYLE)

    return env_tbl, pkg_tbl
