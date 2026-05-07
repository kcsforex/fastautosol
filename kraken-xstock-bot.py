# 2026.05.02 8.00
import asyncio
import dlt
import pandas as pd
import aiohttp
from datetime import datetime, UTC, timedelta
import time
import os

# =========================
# CONFIGURATION
# =========================
N8N_WEBHOOK_URL = "https://n8n.petrosofteu.cloud/webhook/xstock-alert"
DB_URL = "postgresql://sql_admin:sql_pass@postgresql:5432/n8n"
POLL_INTERVAL = 180  # 3 minutes refresh
CLEANUP_HOURS = 24

XSTOCKS = {
    'AAPLxUSD': 'Apple', 'ABBVxUSD': 'AbbVie', 'ABTxUSD': 'Abbott', 'ACNxUSD': 'Accenture',
    'AMBRxUSD': 'Ambr', 'AMDxUSD': 'AMD', 'AMZNxUSD': 'Amazon', 'APPxUSD': 'AppLovin',
    'AVGOxUSD': 'Broadcom', 'AZNxUSD': 'AstraZeneca', 'BACxUSD': 'Bank of America',
    'BMNRxUSD': 'BioMarin', 'BTBTxUSD': 'Bit Digital',
    'BTGOxUSD': 'B2Gold', 'CMCSAxUSD': 'Comcast', 'COINxUSD': 'Coinbase', 'COPXxUSD': 'Copper Miners',
    'CRCLxUSD': 'Cercadia', 'CRMxUSD': 'Salesforce', 'CRWDxUSD': 'CrowdStrike',
    'CSCOxUSD': 'Cisco', 'CVXxUSD': 'Chevron', 'DFDVxUSD': 'Defined Outcome',
    'DHRxUSD': 'Danaher', 'GLDxUSD': 'Gold ETF', 'GMExUSD': 'GameStop', 'GOOGLxUSD': 'Alphabet',
    'GSxUSD': 'Goldman Sachs', 'HONxUSD': 'Honeywell', 'HOODxUSD': 'Robinhood',
    'IBMxUSD': 'IBM', 'IEMGxUSD': 'Emerging Mkts', 'IJRxUSD': 'S&P Small-Cap',
    'INTCxUSD': 'Intel', 'IWMxUSD': 'Russell 2000', 'JNJxUSD': 'J&J', 'JPMxUSD': 'JPMorgan',
    'KOxUSD': 'Coca-Cola', 'KRAQxUSD': 'Kraken Robotics', 'LINxUSD': 'Linde',
    'LLYxUSD': 'Eli Lilly', 'MCDxUSD': 'McDonalds', 'MDTxUSD': 'Medtronic',
    'METAxUSD': 'Meta', 'MRKxUSD': 'Merck', 'MRVLxUSD': 'Marvell', 'MSFTxUSD': 'Microsoft',
    'MSTRxUSD': 'MicroStrategy', 'NFLXxUSD': 'Netflix', 'NVDAxUSD': 'NVIDIA',
    'NVOxUSD': 'Novo Nordisk', 'OPENxUSD': 'Opendoor', 'ORCLxUSD': 'Oracle',
    'PALLxUSD': 'Palladium ETF', 'PEPxUSD': 'PepsiCo', 'PFExUSD': 'Pfizer',
    'PGxUSD': 'Procter & Gamble', 'PLTRxUSD': 'Palantir', 'PMxUSD': 'Philip Morris',
    'PPLTxUSD': 'Platinum ETF', 'QQQxUSD': 'Nasdaq 100', 'SCHFxUSD': 'Intl Equity',
    'SLVxUSD': 'Silver ETF', 'SPYxUSD': 'S&P 500', 'STRCxUSD': 'Sarcos', 'TBLLxUSD': 'Treasury ETF',
    'TMOxUSD': 'Thermo Fisher', 'TONXxUSD': 'Tonix Pharma', 'TQQQxUSD': '3x Nasdaq',
    'TSLAxUSD': 'Tesla', 'UNHxUSD': 'UnitedHealth', 'VxUSD': 'Visa', 'VTIxUSD': 'Total Stock',
    'VTxUSD': 'Total World', 'XOMxUSD': 'Exxon Mobil'
}

class State:
    def __init__(self):
        self.last_cleanup_time = 0
        self.last_snapshot_time = 0
        self.last_fetch_time = 0
        self.last_side = {} # Tracks Price vs VWAP position

state = State()

# =========================
# DATA FETCHING & ANALYSIS
# =========================
async def fetch_and_analyze_stocks(session):
    url = "https://api.kraken.com/0/public/Ticker"
    params = {"pair": ",".join(list(XSTOCKS.keys())), "asset_class": "tokenized_asset"}
    
    try:
        async with session.get(url, params=params, timeout=15) as resp:
            response = await resp.json()
            if response.get("error"):
                print(f"Kraken API Error: {response['error']}")
                return [], []

            data = response["result"]
            records = []
            alerts = []
            now = datetime.now(UTC)

            for xsymbol, info in data.items():
                current_price = round(float(info["c"][0]), 2)
                vwap24h = round(float(info["p"][1]), 2)
                
                record = {
                    "symbol": xsymbol,
                    "name": XSTOCKS.get(xsymbol, "Unknown"),
                    "price": current_price,
                    "volume24h": round(float(info["v"][1]), 2),
                    "vwap24h": vwap24h,
                    "trades24h": int(info["t"][1]),
                    "timestamp": now
                }
                records.append(record)

                # --- Signal Logic (Similar to crypto_bot_dlt.py) ---
                current_side = "above" if current_price > vwap24h else "below"
                prev_side = state.last_side.get(xsymbol)
                
                signal = None
                if prev_side == "below" and current_side == "above":
                    signal = "LONG"
                elif prev_side == "above" and current_side == "below":
                    signal = "SHORT"
                
                state.last_side[xsymbol] = current_side

                if signal:
                    alerts.append({**record, "signal": signal})

            return records, alerts

    except Exception as e:
        print(f"Fetch Error: {e}")
        return [], []

# =========================
# MAIN LOOP
# =========================
async def main():
    pipeline = dlt.pipeline(
        pipeline_name="xstock_strategy",
        destination=dlt.destinations.postgres(credentials=DB_URL),
        dataset_name="kraken_data"
    )

    async with aiohttp.ClientSession() as session:
        while True:
            now = time.time()
            try:
                # 1. Fetch and Analyze
                try:
                    records, alerts = await fetch_and_analyze_stocks(session)
                except Exception as e:
                    print("Ticker error:", e) 
              
                # 2. Immediate Webhook Alerts (On Crossover)
                for alert in alerts:
                    payload = alert.copy()
                    payload["timestamp"] = payload["timestamp"].isoformat()
                    await session.post(N8N_WEBHOOK_URL, json=payload)
                    print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] ALERT {payload['symbol']} {payload['signal']}")
		
		        # 3. Pipeline/SQL
                if records:
                    await asyncio.to_thread(pipeline.run, records, table_name="xstock_prices", write_disposition="merge", primary_key=["symbol", "timestamp"])

                # 4. Hourly Cleanup
                if (now - state.last_cleanup_time) > 3600:
                    try:
                        with pipeline.sql_client() as client:
                            table = client.make_qualified_table_name("xstock_prices")
                            threshold = datetime.now(UTC) - timedelta(hours=CLEANUP_HOURS)
                            client.execute_sql(f"DELETE FROM {table} WHERE timestamp < %s", threshold)
                        state.last_cleanup_time = now
                        print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] Kraken xStock cleanup OK.")
                    except Exception as e:
                        print(f"Kraken xStock Cleanup error: {e}")

            except Exception as e:
                print(f"Stock Loop Error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
