# 2026.04.10  12.00
import dash
import pandas as pd
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pages.lufthansa_ml as lh_ml   
from sqlalchemy import create_engine, text
from datetime import datetime

# ----- 1. CONFIGURATION -----
DB_CONFIG = "postgresql+psycopg://sql_admin:sql_pass@postgresql:5432/n8n"
sql_engine = create_engine(DB_CONFIG, pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=1800,      
    connect_args={'connect_timeout': 5, 'keepalives': 1, 'keepalives_idle': 30, 'keepalives_interval': 10, 'keepalives_count': 5})

dash.register_page(__name__, icon="fa-plane", name="Lufthansa ML", order=7)

CARD_STYLE = {
    "background": "rgba(255, 255, 255, 0.03)",
    "backdrop-filter": "blur(10px)",
    "border-radius": "15px",
    "border": "1px solid rgba(255, 255, 255, 0.1)",
    "padding": "20px"
}

layout = dbc.Container([

    html.Div([
        html.H2("Lufthansa Flight Info", className="text-light fw-bold mb-0"),
        html.P(id='lh-metrics-update', className="text-muted small"),
    ], className="mb-4"),

    dcc.Interval(id='refresh', interval=60000),
    dcc.Store(id="lh-df-store"),

    html.Div([
        html.H5("Daily Ingestion Volume", className="text-light mb-3"),
        dcc.Graph(id='lh-daily-chart', config={'displayModeBar': False})
    ], style=CARD_STYLE, className="mb-4"),

    html.Div([
        html.H5("Execution Logs", className="text-light mb-3"),
        html.Div(id='lh-table-container',
            style={"height": "300px", "overflowY": "auto", "fontSize": "12px"})
    ], style=CARD_STYLE, className="mb-4"),

    
    html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Regression Model", className="text-light small"),
                        dbc.Select(
                            id="lh-reg-model",
                            options=[
                                {"label": "Linear Regression", "value": "lin"},
                                {"label": "Decision Tree (Reg)", "value": "tree_reg"},
                                {"label": "Random Forest (Reg)", "value": "rf_reg"},
                                {"label": "GBM (sklearn)", "value": "gbm_reg"},
                                {"label": "HistGB (sklearn)", "value": "hgb_reg"},
                            ],
                            value="lin",
                            size="sm",
                        ),
                    ],
                    md=3,
                ),

                dbc.Col(
                    [
                        html.Label("Classification Model", className="text-light small"),
                        dbc.Select(
                            id="lh-clf-model",
                            options=[
                                {"label": "Logistic Regression", "value": "log"},
                                {"label": "Decision Tree (Clf)", "value": "tree_clf"},
                                {"label": "Random Forest (Clf)", "value": "rf_clf"},
                                {"label": "GBM (sklearn)", "value": "gbm_clf"},
                                {"label": "HistGB (sklearn)", "value": "hgb_clf"},
                            ],
                            value="log",
                            size="sm",
                        ),
                    ],
                    md=3,
                ),

                dbc.Col(
                    dbc.Button(
                        "Run ML Prediction",
                        id="run-ml",
                        color="primary",
                        size="sm",
                        n_clicks=0,
                        style={"marginTop": "20px"},
                    ),
                    md=2,
                ),

                dbc.Col(html.Div(id="ml-kpi-lin", className="text-light"), md=2),
                dbc.Col(html.Div(id="ml-kpi-log", className="text-light"), md=2),
            ]
        ),

        dbc.Row(
            [
                dbc.Col(
                    html.Div(id="lh-ml-table", className="text-light")
                )
            ]
        ),
    ],
    style=CARD_STYLE,
    className="mb-4",
)


], fluid=True)


@callback(
    Output('lh-metrics-update', 'children'),
    Output('lh-table-container', 'children'),
    Output('lh-daily-chart', 'figure'),
    Output('lh-df-store', 'data'),
    Input('refresh', 'n_intervals'),

)
def load_data_render(_):

    with sql_engine.connect() as conn:
        query = """
            SELECT DISTINCT ON (departure_scheduled_ts, route_key) *
            FROM lufthansa
            ORDER BY departure_scheduled_ts, route_key, id DESC
        """
        df = pd.read_sql(query, conn)

    if df.empty:
        return "No data", html.Div("No data", className="text-light"), go.Figure(), None

    # ---- Convert ingestion time ----
    df["ingested_at"] = pd.to_datetime(df["ingested_at"])
    df["ingested_at"] = (df["ingested_at"].dt.strftime("%Y-%m-%d %H:%M:%S"))
    
    # ---- Build daily chart ----
    daily = df.groupby(df["departure_scheduled_ts"].dt.floor("D")).size().reset_index(name="count")
    fig = px.bar(daily, x="departure_scheduled_ts", y="count", template="plotly_dark")
    fig.update_layout(height=250,  plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=10, b=10))

    # ---- Logs table ----
    status_cols = [1, 2, 3, 4, 6, 10, 11, 13]
    table = dbc.Table.from_dataframe(df.iloc[-100:, status_cols], striped=False, hover=True, responsive=True, borderless=True,
        className="text-light m-0", style={"backgroundColor": "transparent",  "--bs-table-bg": "transparent", "--bs-table-accent-bg": "transparent", "color": "white"})

    return f"Updated → {df['ingested_at'].iloc[-1]}", table, fig, df.to_dict("records")

@callback(
        [Output('ml-kpi-lin', 'children'),
        Output('ml-kpi-log', 'children'),
        Output('lh-ml-table', 'children')],
        [Input('run-ml', 'n_clicks')],   
        [State('lh-reg-model', 'value'),
        State('lh-clf-model', 'value'),
        State('lh-df-store','data')],
        prevent_initial_call=True)
    
def run_ml_clicks(n_clicks, reg_choice, clf_choice, data):  
    
    if not data:
        msg = "No data for ML"
        return msg, "-", "-", "-"

    df = pd.DataFrame(data)
    data_ml = lh_ml.prepare(df)

    # -------------------------
    #   REGRESSION MODEL SWITCH
    # -------------------------
    if reg_choice == "lin":
        reg_model, reg_metrics = lh_ml.train_linear(data_ml)
    elif reg_choice == "tree_reg":
        reg_model, reg_metrics = lh_ml.train_tree_linear(data_ml)
    elif reg_choice == "rf_reg":
        reg_model, reg_metrics = lh_ml.train_rf_linear(data_ml)
    elif reg_choice == "gbm_reg":
        reg_model, reg_metrics = lh_ml.train_gbm_linear(data_ml)
    elif reg_choice == "hgb_reg":
        reg_model, reg_metrics = lh_ml.train_hgb_linear(data_ml) 
    else:
        reg_model, reg_metrics = lh_ml.train_linear(data_ml)

    reg_kpi0 = html.Div([
        html.Div(f"RMSE: {reg_metrics['rmse']:.1f}"),
        html.Div(f"MAE: {reg_metrics['mae']:.1f}"),
        html.Div(f"R² : {reg_metrics['r2']:.3f}"),
    ])

    reg_kpi = html.Div(
    [
        html.H6("Regression", className="text-light mb-2"),

        html.Div(
            [
                html.Div(
                    [
                        html.Span("RMSE", className="text-muted"),
                        html.Span(f"{reg_metrics['rmse']:.1f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
                html.Div(
                    [
                        html.Span("MAE", className="text-muted"),
                        html.Span(f"{reg_metrics['mae']:.1f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
                html.Div(
                    [
                        html.Span("R²", className="text-muted"),
                        html.Span(f"{reg_metrics['r2']:.3f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
            ],
            className="small",
        ),
    ],
    style={
        "backgroundColor": "#1f2933",
        "height": "140px",              # same height as classification card
        "padding": "10px 12px",
        "borderRadius": "8px",
        "border": "1px solid #2d3748",
    },
)


    # Predict on latest rows
    reg_pred = lh_ml.predict_latest_linear(reg_model, data_ml, n=15)

    
    # -------------------------
    #   CLASSIFICATION MODEL SWITCH
    # -------------------------
    if clf_choice == "log":
        clf_model, clf_metrics = lh_ml.train_logistic(data_ml)
    elif clf_choice == "tree_clf":
        clf_model, clf_metrics = lh_ml.train_tree_logistic(data_ml)
    elif clf_choice == "rf_clf":
        clf_model, clf_metrics = lh_ml.train_rf_logistic(data_ml)
    elif clf_choice == "gbm_clf":
        clf_model, clf_metrics = lh_ml.train_gbm_logistic(data_ml)
    elif clf_choice == "hgb_clf":
        clf_model, clf_metrics = lh_ml.train_hgb_logistic(data_ml)
    else:
        clf_model, clf_metrics = lh_ml.train_logistic(data_ml)

    clf_kpi0 = html.Div([
        html.Div(f"Accuracy:  {clf_metrics['acc']:.3f}"),
        html.Div(f"Precision: {clf_metrics['prec']:.3f}"),
        html.Div(f"Recall:    {clf_metrics['rec']:.3f}"),
        html.Div(f"F1-score:  {clf_metrics['f1']:.3f}"),
    ])

    clf_kpi = html.Div(
    [
        html.H6("Classification", className="text-light mb-2"),

        html.Div(
            [
                html.Div(
                    [
                        html.Span("Accuracy", className="text-muted"),
                        html.Span(f"{clf_metrics['acc']:.3f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
                html.Div(
                    [
                        html.Span("Precision", className="text-muted"),
                        html.Span(f"{clf_metrics['prec']:.3f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
                html.Div(
                    [
                        html.Span("Recall", className="text-muted"),
                        html.Span(f"{clf_metrics['rec']:.3f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
                html.Div(
                    [
                        html.Span("F1-score", className="text-muted"),
                        html.Span(f"{clf_metrics['f1']:.3f}", className="fw-bold"),
                    ],
                    className="d-flex justify-content-between",
                ),
            ],
            className="small",
        ),
    ],
    style={
        "backgroundColor": "#1f2933",   # dark card bg
        "height": "140px",              # fixed height
        "padding": "10px 12px",
        "borderRadius": "8px",
        "border": "1px solid #2d3748",
    },
)

    clf_pred = lh_ml.predict_latest_logistic(clf_model, data_ml, n=15)

    comp = pd.merge(reg_pred, clf_pred, on=["route_key", "dep_sched"], how="outer", validate="one_to_one", sort=False)
    comp[["arrival_delay", "pred_delay"]] = comp[["arrival_delay", "pred_delay"]].astype("float64").round(1)
    comp["pred_prob_delay"] = comp["pred_prob_delay"].astype("float64").round(3)    
    reg_clf_table = dbc.Table.from_dataframe(comp, striped=False, hover=True, responsive=True, borderless=True, className="text-light m-0",      
        style={"height": "250px", "overflowY": "auto", "overflowX": "hidden",  "fontSize": "12px",
               "backgroundColor": "transparent",  "--bs-table-bg": "transparent", "--bs-table-accent-bg": "transparent"})
    
    return reg_kpi, clf_kpi, reg_clf_table
