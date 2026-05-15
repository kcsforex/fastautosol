import dash
from dash import html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import docker

dash.register_page(__name__, path='/', icon="fa-solid fa-server", name="Home")

# Docker client
client = docker.from_env()

def get_docker_stats():
    try:
        containers = client.containers.list()
        stats_list = []
        for c in containers:
            stats = c.stats(stream=False)

            # CPU %
            cpu_delta = (stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"])
            system_delta = (stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"])
            cpus = stats["cpu_stats"].get("online_cpus", 1)
            cpu = round((cpu_delta / system_delta) * cpus * 100, 2) if system_delta > 0 else 0

            # MEM
            mem_usage = (stats["memory_stats"].get("usage", 0) / 1024 / 1024)
            mem_limit = (stats["memory_stats"].get("limit", 1))
            mem_pct = round((stats["memory_stats"].get("usage", 0) / mem_limit) * 100, 1)

            stats_list.append({
                "ID": c.short_id,
                "Name": c.name[:30],
                "CPU": f"{cpu}%",
                "MemUsage": f"{mem_usage:.1f} MiB",
                "MemPerc": f"{mem_pct}%",
                "Status": c.status
            })

        return stats_list

    except Exception as e:
        print(e)
        return []

def make_table(stats):
    if not stats:
        return html.P("No containers found or docker not accessible.", className="text-warning")

    rows = []
    for c in stats:

        cpu_val = float(
            c["CPU"].replace("%", "")
        )

        cpu_color = (
            "danger"
            if cpu_val > 50
            else "warning"
            if cpu_val > 20
            else "success"
        )

        rows.append(

            html.Tr([

                html.Td(
                    html.Code(
                        c["ID"],
                        className="text-muted"
                    )
                ),

                html.Td(c["Name"]),

                html.Td(
                    dbc.Badge(
                        c["CPU"],
                        color=cpu_color
                    )
                ),

                html.Td(c["MemUsage"]),

                html.Td(c["MemPerc"]),

                html.Td(c["NetIO"]),

                html.Td(c["PIDs"]),

                html.Td(

                    dbc.Badge(

                        c["Status"],

                        color=(
                            "success"
                            if c["Status"] == "running"
                            else "danger"
                        )

                    )

                )

            ])

        )

    return dbc.Table(

        [

            html.Thead(

                html.Tr([

                    html.Th("ID"),

                    html.Th("Name"),

                    html.Th("CPU %"),

                    html.Th("MEM Usage"),

                    html.Th("MEM %"),

                    html.Th("NET I/O"),

                    html.Th("PIDs"),

                    html.Th("Status"),

                ])

            ),

            html.Tbody(rows)

        ],

        bordered=True,
        hover=True,
        responsive=True,
        size="sm",
        striped=True,
        className="table-dark"

    )


layout = dbc.Container([

    dbc.Row([

        dbc.Col([

            html.H3([

                html.I(
                    className="fa-solid fa-server me-2 text-primary"
                ),

                "VPS Docker Stats"

            ]),

            html.Small(
                id="vps-last-updated",
                className="text-muted"
            ),

            html.Hr(),

        ])

    ]),

    # auto refresh
    dcc.Interval(
        id="vps-interval",
        interval=10_000,
        n_intervals=0
    ),

    dbc.Row([

        dbc.Col(

            html.Div(id="vps-table")

        )

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

    updated = (
        f"Last updated: "
        f"{datetime.now().strftime('%H:%M:%S')}"
    )

    return make_table(stats), updated
