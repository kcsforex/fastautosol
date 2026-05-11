# 2026.05.11 18.00 
import asyncio
import ccxt.async_support as ccxt
import dlt
import pandas as pd
import aiohttp
from datetime import datetime, UTC, timedelta
import time

# =========================
# CONFIGURATION
# =========================
N8N_WEBHOOK_URL = "https://n8n.petrosofteu.cloud/webhook/crypto-alert"
DB_URL = "postgresql://sql_admin:sql_pass@postgresql:5432/n8n"
FIX_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'SUI/USDT', 'HYPE/USDT', 'LTC/USDT', 
               'ETC/USDT', 'COMP/USDT', 'AVAX/USDT', 'AXS/USDT', 'LINK/USDT', 'BCH/USDT', 'TIA/USDT' ,'ZEN/USDT'] 
POLL_INTERVAL = 75 
CLEANUP_HOURS = 36

class State:
    def __init__(self):
        self.last_side = {}
        self.last_cleanup_time = 0
        self.ticker_cache = {}
        self.last_ticker_fetch = 0

state = State()

# =========================
# ANALYTICS ENGINE
# =========================
async def fetch_and_analyze(exchange, symbol, ticker_data):
    try:
        # 1. Fetch OHLCV (M5)
        bars = await exchange.fetch_ohlcv(symbol, timeframe='5m', limit=150)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        
        # 2. Indicators (EMA150)
        df["ema150"] = df["c"].ewm(span=150, min_periods=150).mean()

        ticker = ticker_data.get(symbol, {})
        info = ticker.get('info', {})
        last = df.iloc[-1]
        
        record = {
            "symbol": symbol,
            "timestamp": datetime.fromtimestamp(last['ts'] / 1000, tz=UTC),
            "open": round(float(last['o']), 2),
            "high": round(float(last['h']), 2),
            "low": round(float(last['l']), 2),
            "close": round(float(last['c']), 2),
            "volume": round(float(last['v']), 2),
            "ema150": round(float(last['ema150']), 2) if not pd.isna(last['ema150']) else None,
            "vwap": round(float(ticker.get("vwap")), 2),
            "turnover24h": round(float(info.get("turnover24h", 0)), 2),
            "price24hpcnt": round(float(info.get("price24hPcnt", 0)), 2),
            "funding": round(float(info.get("fundingRate") or info.get("lastFundingRate", 0)), 6),
            "oi": round(float(info.get("openInterest", 0)), 2),
        }

        # 3. Signal Logic
        current_side = "above" if record["close"] > (record["ema150"] or 0) else "below"
        prev_side = state.last_side.get(symbol)
        signal = None
        if prev_side == "below" and current_side == "above": signal = "LONG"
        elif prev_side == "above" and current_side == "below": signal = "SHORT"
        
        state.last_side[symbol] = current_side
        return record, signal

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None, None

# =========================
# MAIN LOOP
# =========================
async def main():
    #global last_cleanup_time, ticker_cache, last_ticker_fetch
    exchange = ccxt.bybit({"enableRateLimit": True, "rateLimit": 200, "options": {"defaultType": "linear"}})
    
    pipeline = dlt.pipeline(
        pipeline_name="crypto_strategy",
        destination=dlt.destinations.postgres(credentials=DB_URL),
        dataset_name="bybit_data"
    )

    async with aiohttp.ClientSession() as session:
        while True:
            now = time.time()
            try:
                # ----- 1. Update Ticker Cache (Every 5 mins) -----
                if now - state.last_ticker_fetch > 300:
                    try:
                        state.ticker_cache = await exchange.fetch_tickers(symbols=FIX_SYMBOLS)
                        state.last_ticker_fetch = now
                    except Exception as e:
                        print("Ticker error:", e)

                # ----- 2. Process Symbols in Parallel -----
                tasks = [fetch_and_analyze(exchange, s, state.ticker_cache) for s in FIX_SYMBOLS]
                results = await asyncio.gather(*tasks)
                records = [r for r, s in results if r]

                # ----- 3. Webhook Alerts (On crossover) -----
                for record, signal in results:
                    if signal:
                        payload = record | {"signal": signal}
                        payload["timestamp"] = payload["timestamp"].isoformat()  
                        symbol = payload["symbol"]      
                        await session.post(N8N_WEBHOOK_URL, json=payload)
                        print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] ALERT {symbol} {signal}")

                # ----- 4. SQL_DB UPSERT (Every 75 seconds) -----
                if records:
                    await asyncio.to_thread(pipeline.run, records,  table_name="bybit_candles", write_disposition="merge", primary_key=["symbol", "timestamp"])

                # ----- 5. Hourly Cleanup -----
                if (now - state.last_cleanup_time) > 3600:
                    try:
                        print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] Cleanup Starting (older than {CLEANUP_HOURS}h)")                      
                        with pipeline.sql_client() as client:    
                            table_name = client.make_qualified_table_name("bybit_candles")                        
                            threshold = datetime.now(UTC) - timedelta(hours=CLEANUP_HOURS)
                            client.execute_sql(f"DELETE FROM {table_name} WHERE timestamp < %s", threshold)
                        state.last_cleanup_time = now
                        print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] Cleanup successful.")
                        
                    except Exception as e:
                        print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] Cleanup error: {e}")

            except Exception as e:
                print(f"Loop Error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
