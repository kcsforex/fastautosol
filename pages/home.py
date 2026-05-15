import dash
from dash import html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import subprocess, json

dash.register_page(__name__, path='/', icon="fa-solid fa-server", name="Home")

def get_docker_stats():
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=15
        )
        return [json.loads(l) for l in result.stdout.strip().split("\n") if l]
    except Exception as e:
        return []

def make_table(stats):
    if not stats:
        return html.P("No containers found or docker not accessible.", className="text-warning")

    rows = []
    for c in stats:
        # shorten name
        name = c.get("Name", "")[:30]
        cpu  = c.get("CPUPerc", "-")
        mem  = c.get("MemUsage", "-")
        memp = c.get("MemPerc", "-")
        net  = c.get("NetIO", "-")
        blk  = c.get("BlockIO", "-")
        pids = c.get("PIDs", "-")

        # color CPU cell
        cpu_val = float(cpu.replace("%","")) if "%" in cpu else 0
        cpu_color = "danger" if cpu_val > 50 else "warning" if cpu_val > 20 else "success"

        rows.append(html.Tr([
            html.Td(html.Code(c.get("ID","")[:12], className="text-muted")),
            html.Td(name),
            html.Td(dbc.Badge(cpu, color=cpu_color)),
            html.Td(mem),
            html.Td(memp),
            html.Td(net),
            html.Td(blk),
            html.Td(pids),
        ]))

    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("ID"), html.Th("Name"), html.Th("CPU %"),
            html.Th("MEM Usage"), html.Th("MEM %"),
            html.Th("NET I/O"), html.Th("Block I/O"), html.Th("PIDs"),
        ])),
        html.Tbody(rows)
    ], bordered=True, hover=True, responsive=True, size="sm", className="table-dark")

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H3([html.I(className="fa-solid fa-server me-2 text-primary"), "VPS Docker Stats"]),
            html.Small(id="vps-last-updated", className="text-muted"),
            html.Hr(),
        ])
    ]),

    # Auto-refresh every 10 seconds
    dcc.Interval(id="vps-interval", interval=10_000, n_intervals=0),

    dbc.Row([
        dbc.Col(html.Div(id="vps-table"))
    ])
], fluid=True, className="py-3")

@callback(
    Output("vps-table", "children"),
    Output("vps-last-updated", "children"),
    Input("vps-interval", "n_intervals")
)
def update_stats(_):
    from datetime import datetime
    stats = get_docker_stats()
    updated = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
    return make_table(stats), updated
