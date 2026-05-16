import dash
from dash import html, dcc, callback, Output, Input
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import dash_bootstrap_components as dbc
import pandas as pd
import docker

dash.register_page(__name__, path="/", icon="fa-solid fa-server", name="Home", order=0)


layout = dbc.Container([

    dbc.Row(dbc.Col([
        html.H3([html.I(className="fa-solid fa-server me-2 text-primary"), "VPS Docker Stats"]),
        html.Small(id="vps-last-updated", className="text-muted"),
        html.Hr(),
    ])),

    dcc.Interval(id="vps-interval", interval=60*1000, n_intervals=0),
    dbc.Row(dbc.Col(html.Div(id="vps-table"))),

], fluid=True, className="py-3")


@callback(
    Output("vps-table", "children"),
    Output("vps-last-updated", "children"),
    Input("vps-interval", "n_intervals"),
)
def update_stats(_):
    df = get_docker_stats()

    if df.empty:
        table = html.P("No containers found or Docker not accessible.", className="text-warning")
    else:
        table = dbc.Table.from_dataframe(df, bordered=True, hover=True, responsive=True, size="sm", striped=True, className="table-dark")

    updated = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
    return table, updated
