# 2026.02.23  12.00
import os
import httpx
import asyncio
import pandas as pd
import requests
from fastapi.responses import StreamingResponse, FileResponse
import io
from fastapi import APIRouter
from sqlalchemy import create_engine
from pathlib import Path
import tempfile

router = APIRouter()

# ----- CONFIGURATION -----
#DB_CONFIG = "postgresql+psycopg://sql_admin:sql_pass@72.62.151.169:5432/n8n"
DB_CONFIG = "postgresql+psycopg://sql_admin:sql_pass@postgresql:5432/n8n"
sql_engine = create_engine(DB_CONFIG, pool_size=5, max_overflow=10, pool_pre_ping=True)

def get_lufthansa_token():
    CLIENT_ID = os.getenv("LH_CLIENT_ID")
    CLIENT_SECRET = os.getenv("LH_CLIENT_SECRET")
    token_url = "https://api.lufthansa.com/v1/oauth/token"
    payload = {"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()
    return resp.json()["access_token"]

async def fetch_route(client, token, origin, dest, flight_date, sem):
    url = f"https://api.lufthansa.com/v1/operations/customerflightinformation/route/{origin}/{dest}/{flight_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with sem:
        try:
            resp = await client.get(url, headers=headers, timeout=10)
            await asyncio.sleep(0.5)
            if resp.status_code != 200: return None
            
            json_data = resp.json()
            flights = json_data.get("FlightInformation", {}).get("Flights", {}).get("Flight", [])
            if not flights: return None

            df = pd.json_normalize(flights)
            df["route_key"] = f"{origin}-{dest}"
            return df
        except Exception:
            return None

@router.get("/lh_flights/parquet")
async def get_flightroute_parquet():
    with sql_engine.connect() as conn:
        query = """SELECT id, route_key, departure_airport_code, departure_terminal_gate, departure_status_code, arrival_airport_code, 
        arrival_terminal_gate, arrival_status_code, operatingcarrier_airlineid, operatingcarrier_flightnumber, equipment_aircraftcode FROM lufthansa ORDER BY id DESC"""
        df = pd.read_sql(query, conn)

    # Create parquet in memory (no file on disk)
    buffer = io.BytesIO()
    df.to_parquet(buffer, engine="pyarrow", index=False) 
    buffer.seek(0)  # Reset position 
    return StreamingResponse(buffer, media_type="application/octet-stream", headers={"Content-Disposition": "attachment; filename=lufthansa.parquet"})

@router.get("/lh_flights/{flight_date}")
async def get_flightroute_details(flight_date: str):
    token = get_lufthansa_token()
    
    ROUTES_FULL = [
    # FRA Routes - Long Haul
    ("FRA", "SIN"), ("FRA", "HND"), ("FRA", "LAX"), ("FRA", "JFK"), ("FRA", "EWR"), ("FRA", "ORD"), ("FRA", "IAD"), ("FRA", "BOS"), ("FRA", "DEN"), ("FRA", "SFO"),
    ("FRA", "MIA"), ("FRA", "YYZ"), ("FRA", "MEX"), ("FRA", "DEL"), ("FRA", "BOM"), ("FRA", "BLR"), ("FRA", "HYD"), ("FRA", "ICN"), ("FRA", "GRU"), ("FRA", "DXB"),
    ("FRA", "CAI"), ("FRA", "TLV"), ("FRA", "BEY"), 
    # FRA Routes - European
    ("FRA", "LHR"), ("FRA", "LCY"), ("FRA", "CDG"), ("FRA", "AMS"), ("FRA", "MAD"), ("FRA", "BCN"), ("FRA", "LIS"), ("FRA", "ATH"), ("FRA", "IST"), ("FRA", "BER"),
    ("FRA", "HAM"), ("FRA", "DUS"), ("FRA", "MUC"), ("FRA", "VIE"), ("FRA", "ZRH"), ("FRA", "CPH"), ("FRA", "OSL"), ("FRA", "HEL"), ("FRA", "WAW"), ("FRA", "PRG"),
    ("FRA", "BUD"), ("FRA", "MXP"), ("FRA", "TLS"), ("FRA", "MAN"), ("FRA", "DUB"),
    # MUC Routes - Long Haul
    ("MUC", "LAX"), ("MUC", "SFO"), ("MUC", "DEN"), ("MUC", "ORD"), ("MUC", "EWR"), ("MUC", "JFK"), ("MUC", "BOS"), ("MUC", "DEL"), ("MUC", "BOM"), ("MUC", "BLR"),
    ("MUC", "BKK"), ("MUC", "JNB"), ("MUC", "CPT"), ("MUC", "DXB"),
    # MUC Routes - European
    ("MUC", "LHR"), ("MUC", "CDG"), ("MUC", "AMS"), ("MUC", "MAD"), ("MUC", "BCN"), ("MUC", "LIS"), ("MUC", "ATH"), ("MUC", "BER"), ("MUC", "HAM"), ("MUC", "DUS"),
    ("MUC", "FRA"), ("MUC", "VIE"), ("MUC", "ZRH"), ("MUC", "CPH"), ("MUC", "OSL"), ("MUC", "WAW"), ("MUC", "PRG"), ("MUC", "BUD"), ("MUC", "FCO"), ("MUC", "MXP"),
    ("MUC", "MAN"), ("MUC", "DUB"), ("MUC", "TLV"),
    ]   
    
    sem = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [fetch_route(client, token, o, d, flight_date, sem) for o, d in ROUTES_FULL]
        results = await asyncio.gather(*tasks)

    all_dataframes = [df for df in results if df is not None]
    if not all_dataframes: return []
        
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    combined_df.columns = [c.replace('.', '_') for c in combined_df.columns]

    combined_df = combined_df.drop(columns=[
            "Departure_Terminal_Name", "Arrival_Terminal_Name", 
            "Departure_Status_Description", "Arrival_Status_Description", "Status_Description",
            "MarketingCarrierList_MarketingCarrier_AirlineID",
            "MarketingCarrierList_MarketingCarrier_FlightNumber",
            "MarketingCarrierList_MarketingCarrier",
    ], errors="ignore")
        
    combined_df["ingested_at"] = pd.Timestamp.now().isoformat()
    combined_df = combined_df.where(pd.notnull(combined_df), None)

    rename_map = {
            "Departure_AirportCode": "departure_airport_code",
            "Departure_Scheduled_Date": "departure_scheduled_date",
            "Departure_Scheduled_Time": "departure_scheduled_time",
            "Departure_Actual_Date": "departure_actual_date",
            "Departure_Actual_Time": "departure_actual_time",
            "Departure_Terminal_Gate": "departure_terminal_gate",
            "Departure_Status_Code": "departure_status_code",
            "Arrival_AirportCode": "arrival_airport_code",
            "Arrival_Scheduled_Date": "arrival_scheduled_date",
            "Arrival_Scheduled_Time": "arrival_scheduled_time",
            "Arrival_Actual_Date": "arrival_actual_date",
            "Arrival_Actual_Time": "arrival_actual_time",
            "Arrival_Terminal_Gate": "arrival_terminal_gate",
            "Arrival_Status_Code": "arrival_status_code",
            "OperatingCarrier_AirlineID": "operatingcarrier_airlineid",
            "OperatingCarrier_FlightNumber": "operatingcarrier_flightnumber",
            "Equipment_AircraftCode": "equipment_aircraftcode",
            "Status_Code": "status_code",
            "route_key": "route_key",
            "ingested_at": "ingested_at",
    }

    combined_df = combined_df.rename(columns=rename_map)
            
    return combined_df.to_dict(orient="records")
