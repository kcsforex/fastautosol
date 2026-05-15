import dash
from dash import html, dcc, callback, Output, Input
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import dash_bootstrap_components as dbc
import pandas as pd
import docker

dash.register_page(__name__, path="/", icon="fa-solid fa-server", name="Home")

def fetch_one(c) -> dict:
    s = c.stats(stream=False)

    cpu_delta    = s["cpu_stats"]["cpu_usage"]["total_usage"] - s["precpu_stats"]["cpu_usage"]["total_usage"]
    system_delta = s["cpu_stats"]["system_cpu_usage"]         - s["precpu_stats"]["system_cpu_usage"]
    cpus         = s["cpu_stats"].get("online_cpus", 1)
    cpu_pct      = round((cpu_delta / system_delta) * cpus * 100, 2) if system_delta > 0 else 0.0

    mem_bytes = s["memory_stats"].get("usage", 0)
    mem_mib   = mem_bytes / 1024 / 1024
    mem_pct   = round(mem_bytes / s["memory_stats"].get("limit", 1) * 100, 1)

    return {
        "ID":        c.short_id,
        "Name":      c.name[:30],
        "CPU %":     f"{cpu_pct}%",
        "MEM Usage": f"{mem_mib:.1f} MiB",
        "MEM %":     f"{mem_pct}%",
        "Status":    c.status,
    }


def get_docker_stats() -> pd.DataFrame:
    try:
        client     = docker.from_env()  # fresh client every call to avoid stale connections
        containers = client.containers.list()
        with ThreadPoolExecutor(max_workers=len(containers) or 1) as ex:
            rows = list(ex.map(fetch_one, containers))
        return pd.DataFrame(rows)
    except Exception as e:
        print(e)
        return pd.DataFrame()


layout = dbc.Container([

    dbc.Row(dbc.Col([
        html.H3([html.I(className="fa-solid fa-server me-2 text-primary"), "VPS Docker Stats"]),
        html.Small(id="vps-last-updated", className="text-muted"),
        html.Hr(),
    ])),

    dcc.Interval(id="vps-interval", interval=10_000, n_intervals=0),

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
        table = dbc.Table.from_dataframe(
            df,
            bordered=True,
            hover=True,
            responsive=True,
            size="sm",
            striped=True,
            className="table-dark",
        )

    updated = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
    return table, updated
