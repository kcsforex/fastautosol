import dash
from dash import html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import docker
from datetime import datetime, timezone

dash.register_page(
    __name__,
    path='/',
    icon="fa-solid fa-server",
    name="Home"
)

# Docker client
client = docker.from_env()

# ---------- HELPERS ----------

def cpu_percent(stats):
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )

        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )

        online_cpus = stats["cpu_stats"].get("online_cpus", 1)

        if system_delta > 0:
            return round(
                (cpu_delta / system_delta) * online_cpus * 100.0,
                2
            )

    except Exception:
        pass

    return 0.0


def format_mb(v):
    return f"{round(v / 1024 / 1024, 1)} MiB"


def format_net(v):
    return f"{round(v / 1024 / 1024, 2)} MB"


def uptime_from(started_at):
    try:
        dt = datetime.fromisoformat(
            started_at.replace("Z", "+00:00")
        )

        delta = datetime.now(timezone.utc) - dt

        total_hours = int(delta.total_seconds() // 3600)

        if total_hours < 24:
            return f"{total_hours}h"

        days = total_hours // 24
        hours = total_hours % 24

        return f"{days}d {hours}h"

    except Exception:
        return "-"


# ---------- DOCKER STATS ----------

def get_docker_stats():

    rows = []

    try:
        containers = client.containers.list(all=False)

        for c in containers:

            stats = c.stats(stream=False)

            # memory
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)

            mem_pct = round((mem_usage / mem_limit) * 100, 2)

            # network
            networks = stats.get("networks", {})

            rx = sum(
                v.get("rx_bytes", 0)
                for v in networks.values()
            )

            tx = sum(
                v.get("tx_bytes", 0)
                for v in networks.values()
            )

            # pids
            pids = stats.get(
                "pids_stats",
                {}
            ).get("current", 0)

            # restart count
            restart_count = c.attrs.get(
                "RestartCount",
                0
            )

            # uptime
            started_at = c.attrs["State"].get(
                "StartedAt",
                ""
            )

            rows.append({
                "id": c.short_id,
                "name": c.name[:35],
                "status": c.status,
                "cpu": cpu_percent(stats),
                "mem_usage": format_mb(mem_usage),
                "mem_pct": mem_pct,
                "net_io": f"{format_net(rx)} / {format_net(tx)}",
                "pids": pids,
                "restart_count": restart_count,
                "uptime": uptime_from(started_at),
                "image": (
                    c.image.tags[0]
                    if c.image.tags
                    else "none"
                )
            })

        # sort by CPU desc
        rows.sort(
            key=lambda x: x["cpu"],
            reverse=True
        )

        return rows

    except Exception as e:
        print(f"Docker stats error: {e}")
        return []


# ---------- KPI CARDS ----------

def make_kpis(stats):

    total_containers = len(stats)

    total_cpu = round(
        sum(c["cpu"] for c in stats),
        1
    )

    total_mem = round(
        sum(
            float(c["mem_usage"].split()[0])
            for c in stats
        ),
        1
    )

    unhealthy = len([
        c for c in stats
        if c["status"] != "running"
    ])

    cards = dbc.Row([

        dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.H6("Containers"),
                    html.H3(total_containers)
                ])
            ], className="shadow-sm"),
            md=3
        ),

        dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total CPU"),
                    html.H3(f"{total_cpu}%")
                ])
            ], className="shadow-sm"),
            md=3
        ),

        dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.H6("RAM Usage"),
                    html.H3(f"{total_mem} MiB")
                ])
            ], className="shadow-sm"),
            md=3
        ),

        dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.H6("Unhealthy"),
                    html.H3(unhealthy)
                ])
            ], className="shadow-sm"),
            md=3
        ),

    ], className="mb-3")

    return cards


# ---------- TABLE ----------

def make_table(stats):

    if not stats:
        return html.P(
            "No containers found or Docker socket not accessible.",
            className="text-warning"
        )

    rows = []

    for c in stats:

        cpu_color = (
            "danger"
            if c["cpu"] > 50
            else "warning"
            if c["cpu"] > 20
            else "success"
        )

        mem_color = (
            "danger"
            if c["mem_pct"] > 80
            else "warning"
            if c["mem_pct"] > 50
            else "success"
        )

        rows.append(

            html.Tr([

                html.Td(
                    html.Code(
                        c["id"],
                        className="text-muted"
                    )
                ),

                html.Td(c["name"]),

                html.Td(
                    dbc.Badge(
                        f'{c["cpu"]:.2f}%',
                        color=cpu_color
                    )
                ),

                html.Td(c["mem_usage"]),

                html.Td(
                    dbc.Badge(
                        f'{c["mem_pct"]}%',
                        color=mem_color
                    )
                ),

                html.Td(c["net_io"]),

                html.Td(c["pids"]),

                html.Td(c["restart_count"]),

                html.Td(c["uptime"]),

                html.Td(
                    dbc.Badge(
                        c["status"],
                        color=(
                            "success"
                            if c["status"] == "running"
                            else "danger"
                        )
                    )
                ),

            ])

        )

    return dbc.Table(

        [

            html.Thead(

                html.Tr([

                    html.Th("ID"),
                    html.Th("Container"),
                    html.Th("CPU %"),
                    html.Th("RAM"),
                    html.Th("RAM %"),
                    html.Th("NET I/O"),
                    html.Th("PIDs"),
                    html.Th("Restarts"),
                    html.Th("Uptime"),
                    html.Th("Status"),

                ])

            ),

            html.Tbody(rows)

        ],

        bordered=True,
        hover=True,
        responsive=True,
        striped=True,
        size="sm",
        className="table-dark align-middle"

    )


# ---------- LAYOUT ----------

layout = dbc.Container([

    dbc.Row([

        dbc.Col([

            html.H3([
                html.I(
                    className="fa-solid fa-server me-2 text-primary"
                ),
                "VPS Docker Monitor"
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
            html.Div(id="vps-kpis")
        )
    ]),

    dbc.Row([
        dbc.Col(
            html.Div(id="vps-table")
        )
    ])

], fluid=True, className="py-3")


# ---------- CALLBACK ----------

@callback(
    Output("vps-kpis", "children"),
    Output("vps-table", "children"),
    Output("vps-last-updated", "children"),
    Input("vps-interval", "n_intervals")
)
def update_stats(_):

    stats = get_docker_stats()

    updated = (
        f"Last updated: "
        f"{datetime.now().strftime('%H:%M:%S')}"
    )

    return (
        make_kpis(stats),
        make_table(stats),
        updated
    )
