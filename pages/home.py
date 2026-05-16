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
        html.H3("VPS Docker Stats"),
        html.Small(id="home-updated", className="text-muted"),
        html.Hr(),
    ])),

    dbc.Row(dbc.Col(html.Div(id="vps-table"))),

], fluid=True, className="py-3")

