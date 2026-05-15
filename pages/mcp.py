# 2026.04.13 18.00
import uuid
import dash
from dash import html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
import pandas as pd
import requests

dash.register_page(__name__, name="AI Min Analytics", icon="fa-solid fa-robot", order=8)

CARD_STYLE = {
    "background": "rgba(255,255,255,0.03)", "backdropFilter": "blur(10px)",
    "borderRadius": "15px", "border": "1px solid rgba(255,255,255,0.1)", "padding": "20px"
}

N8N_WEBHOOK = "https://n8n.petrosofteu.cloud/webhook/ai-query"
SESSION_ID = str(uuid.uuid4())

def call_n8n(query: str) -> str:
    try:
        payload = {"query": query, "sessionId": SESSION_ID }
        response = requests.post(N8N_WEBHOOK, json=payload, timeout=30, headers={"Content-Type": "application/json"})    
        result_json = response.json()
        
    except requests.exceptions.Timeout:
        return "Error: N8N timed out after 30s"
    except requests.exceptions.ConnectionError:
        return f"Error: Cannot reach N8N at {N8N_WEBHOOK}"

    return result_json

# ── Layout ────
layout = dbc.Container([
    html.Div([
        html.H1("AI Analytics — Connection Test", className="text-light fw-bold"),
        html.P("Minimal test: Dash → N8N → Mistral → Dash", className="text-muted"),
    ], className="mb-4"),

    dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col(
                dbc.Input(id="chat-input", placeholder="e.g. What is 2 plus 2?", type="text", className="bg-dark text-light border-0"), width=10),
            dbc.Col(
                dbc.Button("Ask", id="run-query", color="info", className="w-100"), width=2)]) 
        ]), style=CARD_STYLE, className="mb-4"),

        dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("Analytics", className="text-info fw-semibold mb-3"), 
            dcc.Loading(html.Div(id="answer-table", className="text-light", style={"maxHeight": "400px", "overflowY": "auto"}))     
        ]), style=CARD_STYLE), width=8),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("AI Insights", className="text-info fw-semibold mb-3"), dcc.Loading(html.Div(id="answer-insight", className="text-light"))
        ]), style=CARD_STYLE), width=4),
    ]),
], fluid=True)
        

@callback(
    Output("answer-table", "children"),
    Output("answer-insight", "children"),
    Input("run-query",        "n_clicks"),
    State("chat-input",       "value"),
    prevent_initial_call=True
)

def run_query(n_clicks, query):  
    
    if not n_clicks or not query:
        return "Ask a question."   
    result = call_n8n(query)
    
    data_output = result.get("data", [])  
    insight_output = result.get("insight") or result.get("explanation") or result.get("error") or "No insight returned."

    if data_output:
        df = pd.DataFrame(data_output)
        table = html.Div(
            dbc.Table.from_dataframe(df, striped=True, hover=True, bordered=False, className="text-light mb-0",
            style={"minWidth": "100%", "whiteSpace": "nowrap", "backgroundColor": "transparent",  "--bs-table-bg": "transparent", "--bs-table-accent-bg": "transparent"}))           
    else:
        table = html.Div( "No data returned.", className="text-muted fst-italic")

    insight = html.Div(html.P(insight_output, className="text-muted fst-italic"), style={"whiteSpace": "pre-wrap"})
    
    return table, insight
