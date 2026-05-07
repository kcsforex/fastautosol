# 2026.05.06  18.00
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from contextlib import asynccontextmanager
import asyncio

import apis.crm_api_dlt as crm_dlt
import apis.bybit_api as bybit
import apis.kraken_api as kraken
import apis.lufthansa_api as lufthansa
import apis.serper_places_api as serper_places
import apis.serper_places_api_email as serper_places_email
import apis.movies_api_dlt as movies_dlt
import apis.youtube_api as youtube
import apis.youtube_api_dlt as youtube_dlt

# ----- 1. Initalize Dash -----
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True, # compress=True
    external_stylesheets=[dbc.themes.DARKLY, "https://use.fontawesome.com/releases/v5.15.4/css/all.css"])

# ----- 2. NOW IMPORT YOUR PAGES -----
from pages import home, bybit_ccharts, bybit_lcharts, crm_rag, crm_rag_mcp, mexc_charts, mcp, lufthansa1, lufthansa2

# ----- 3. FASTAPI WRAPPER -----
server = FastAPI(title="Dash Main App", lifespan=lambda app: youtube.mcp.session_manager.run())
server.mount("/youtube", youtube.mcp.streamable_http_app())

# ----- 4. API ROUTERS -----
server.include_router(crm_dlt.router,       prefix="/api/crm_dlt",       tags=["CRM DLT"])
server.include_router(bybit.router,         prefix="/api/bybit",         tags=["Bybit"])
server.include_router(kraken.router,        prefix="/api/kraken",        tags=["Kraken"])
server.include_router(lufthansa.router,     prefix="/api/lufthansa",     tags=["Lufthansa"])
server.include_router(serper_places.router, prefix="/api/serper",        tags=["Serper Places"])
server.include_router(serper_places_email.router, prefix="/api/serper_email",        tags=["Serper Places Email"])
server.include_router(movies_dlt.router,    prefix="/api/movies_dlt",    tags=["Movies DLT"])
server.include_router(youtube.router,       prefix="/api/youtube",       tags=["Youtube Single/Multi Channel"])
server.include_router(youtube_dlt.router,   prefix="/api/youtube_dlt",   tags=["Youtube Single/Multi Channel DLT"])

# ----- 5. HEALTH ENDPOINT -----
@server.get("/health")
def health():
    return {"status": "ok"}

# ----- 6. Mount Dash to FastAPI -----
server.mount("/", WSGIMiddleware(app.server))

# ----- 7. SIDEBAR & LAYOUT  (Your Modern Layout) -----
SIDEBAR_STYLE = {
    "position": "fixed", "top": "15px", "left": "15px", "bottom": "15px",
    "width": "220px", "padding": "2rem 1rem",
    "background": "rgba(255, 255, 255, 0.1)",
    "backdrop-filter": "blur(15px)",
    "border-radius": "20px",
    "border": "1px solid rgba(255, 255, 255, 0.1)",
    "box-shadow": "0 8px 32px 0 rgba(0, 0, 0, 0.5)"
}

sidebar = html.Div([
    html.H5("PETROSOFT(EU) CLOUD", className="text-center mb-4", style={"letterSpacing": "2px", "color": "ivory"}),
    
    html.Div([
        html.Div([
            html.I(className="fas fa-user-circle fa-2x text-info"),
            html.Div([
                html.P("Admin Console", className="mb-0", style={"fontSize": "14px", "fontWeight": "bold"}),
                html.P("8GB - 2vCPU", className="text-muted small mb-0")
            ], className="ms-3")
        ], className="d-flex align-items-center p-3", style={"background": "rgba(0,0,0,0.3)", "borderRadius": "15px"})
    ], className="mb-4"),

    html.Hr(style={"color": "rgba(255,255,255,0.3)"}),

    dbc.Nav([
        dbc.NavLink([
            html.Div([
                html.I(className=f"fas {page.get('icon', 'fa-chart-line')} me-2"),
                html.Span(page["name"]),
            ], className="d-flex align-items-center")
        ], href=page["relative_path"], active="exact", className="mb-2 py-2 ps-2 rounded-3 text-light")
        for page in dash.page_registry.values()
    ], vertical=True, pills=True),
], style=SIDEBAR_STYLE)

app.layout = html.Div([
    sidebar,
    html.Div(dash.page_container, style={
        "marginLeft": "250px", "padding": "2rem",
        "background": "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
        "minHeight": "100vh"
    })
])
