import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path='/', icon="fa-solid fa-house", name="Home")

def info_card(icon, title, value, color="primary"):
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className=f"fa-solid {icon} fa-2x text-{color} mb-2"),
                html.H6(title, className="text-muted mb-1"),
                html.H4(value, className="fw-bold mb-0"),
            ], className="text-center")
        ])
    ], className="h-100 border-0 shadow-sm")

layout = dbc.Container([

    # Header
    dbc.Row([
        dbc.Col([
            html.H2([
                html.I(className="fa-solid fa-robot me-2 text-primary"),
                "Trading Bot Dashboard"
            ], className="mt-2 mb-0"),
            html.P("Welcome — select a module from the sidebar to get started.",
                   className="text-muted mb-4"),
            html.Hr(),
        ])
    ]),

    # Stats row
    dbc.Row([
        dbc.Col(info_card("fa-server",     "Instance",  "8GB KVM",     "primary"),  md=3),
        dbc.Col(info_card("fa-circle",     "Status",    "Online",      "success"),  md=3),
        dbc.Col(info_card("fa-gauge-high", "Load",      "Normal",      "warning"),  md=3),
        dbc.Col(info_card("fa-clock",      "Uptime",    "3d 14h",      "info"),     md=3),
    ], className="g-3 mb-4"),

    # Quick links
    dbc.Row([
        dbc.Col([
            html.H5([
                html.I(className="fa-solid fa-bolt me-2 text-warning"),
                "Quick Navigation"
            ], className="mb-3"),
            dbc.ListGroup([
                dbc.ListGroupItem([
                    html.I(className="fa-solid fa-server me-2 text-primary"),
                    "VPS System Info"
                ], href="/vps", action=True, className="bg-transparent border-secondary text-light"),
                dbc.ListGroupItem([
                    html.I(className="fa-solid fa-chart-line me-2 text-success"),
                    "ML Engine"
                ], href="/ml2", action=True, className="bg-transparent border-secondary text-light"),
            ], flush=True)
        ], md=6),

        dbc.Col([
            html.H5([
                html.I(className="fa-solid fa-circle-info me-2 text-info"),
                "About"
            ], className="mb-3"),
            dbc.Card([
                dbc.CardBody([
                    html.P("This dashboard provides tools for automated trading, "
                           "machine learning analysis, and server monitoring.",
                           className="text-muted mb-2"),
                    html.Small("Built with Dash + Bootstrap · FA7 Icons",
                               className="text-secondary"),
                ])
            ], className="border-0 shadow-sm h-100")
        ], md=6),
    ], className="g-3"),

], fluid=True, className="py-3")
