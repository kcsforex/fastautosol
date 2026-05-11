# 2026.05.11  18.00
import asyncio
import ccxt.async_support as ccxt
import dlt
import pandas as pd
import aiohttp
from datetime import datetime, UTC, timedelta
import time

# =========================
# CONFIG
# =========================
N8N_WEBHOOK_URL = "https://n8n.petrosofteu.cloud/webhook/xstock-alert"
DB_URL = "postgresql://sql_admin:sql_pass@postgresql:5432/n8n"

POLL_INTERVAL = 180
CLEANUP_HOURS = 36

STOCK_SYMBOLS = [
    'SNDKSTOCK/USDT:USDT','GOOGLSTOCK/USDT:USDT','INTCSTOCK/USDT:USDT', 'MUSTOCK/USDT:USDT','AAPLSTOCK/USDT:USDT','AMDSTOCK/USDT:USDT',
    'MSTRSTOCK/USDT:USDT','STXSTOCK/USDT:USDT','METASTOCK/USDT:USDT', 'CRCLSTOCK/USDT:USDT','QQQSTOCK/USDT:USDT','ORCLSTOCK/USDT:USDT',
    'ARMSTOCK/USDT:USDT','TXNSTOCK/USDT:USDT','MSFTSTOCK/USDT:USDT', 'MRVLSTOCK/USDT:USDT', 'ASMLSTOCK/USDT:USDT', 'NFLXSTOCK/USDT:USDT'
]

# =========================
# STATE
# =========================
class State:
    def __init__(self):
        self.last_side = {}
        self.last_cleanup_time = 0
        self.ticker_cache = {}
        self.last_ticker_fetch = 0

state = State()

# =========================
# FETCH + ANALYZE
# =========================
async def fetch_and_analyze(exchange, symbol, ticker_data):
    try:
        # ---- Fetch candles (need > 100 for EMA stability)
        bars = await exchange.fetch_ohlcv(symbol, timeframe='15m', limit=150)

        if not bars or len(bars) < 100:
            print(f"Skipping {symbol} (insufficient data)")
            return None, None

        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

        # ---- EMA100
        df["ema100"] = df["c"].ewm(span=100, min_periods=100).mean()

        ticker = ticker_data.get(symbol, {})
        info = ticker.get('info', {})
        last = df.iloc[-1]

        record = {
            "symbol": symbol,
            "timestamp": datetime.fromtimestamp(last['ts'] / 1000, tz=UTC),
            "open": float(last['o']),
            "high": float(last['h']),
            "low": float(last['l']),
            "close": float(last['c']),
            "volume": float(last['v']),
            "ema100": float(last['ema100']) if not pd.isna(last['ema100']) else None,
            "price": float(ticker.get("last", 0)),
            "volume24h": float(ticker.get("quoteVolume", 0)),
            "change24h": float(ticker.get("percentage", 0)),
        }

        if record["ema100"] is None:
            return None, None

        # ---- SIGNAL LOGIC
        current_side = "above" if record["close"] > record["ema100"] else "below"
        prev_side = state.last_side.get(symbol)

        signal = None
        if prev_side == "below" and current_side == "above":
            signal = "LONG"
        elif prev_side == "above" and current_side == "below":
            signal = "SHORT"

        state.last_side[symbol] = current_side

        return record, signal

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None, None


# =========================
# MAIN LOOP
# =========================
async def main():
    exchange = ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})

    # ---- Load + validate symbols
    markets = await exchange.load_markets()
    symbols = [s for s in STOCK_SYMBOLS if s in markets]

    pipeline = dlt.pipeline(
        pipeline_name="mexc_stock_strategy",
        destination=dlt.destinations.postgres(credentials=DB_URL),
        dataset_name="mexc_data"
    )

    async with aiohttp.ClientSession() as session:
        while True:
            now = time.time()

            try:
                # ---- 1. Refresh tickers (every 15 min)
                if now - state.last_ticker_fetch > 900:
                    try:
                        state.ticker_cache = await exchange.fetch_tickers(symbols=symbols)
                        state.last_ticker_fetch = now
                        print("Tickers updated")
                    except Exception as e:
                        print("Ticker error:", e)

                # ---- 2. Analyze all symbols
                tasks = [fetch_and_analyze(exchange, s, state.ticker_cache) for s in symbols]
                results = await asyncio.gather(*tasks)
                records = [r for r, s in results if r]

                # ---- 3. Send alerts
                for record, signal in results:
                    if signal:
                        payload = record | {"signal": signal}
                        payload["timestamp"] = payload["timestamp"].isoformat()
                        await session.post(N8N_WEBHOOK_URL, json=payload)
                        print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] ALERT {record['symbol']} {signal}")

                # ---- 4. Store to Postgres
                if records:
                    await asyncio.to_thread(pipeline.run, records, table_name="mexc_stocks", write_disposition="merge", primary_key=["symbol", "timestamp"])

                # ---- 5. Cleanup old data
                if (now - state.last_cleanup_time) > 3600:
                    try:
                        print("Cleanup starting...")
                        with pipeline.sql_client() as client:
                            table_name = client.make_qualified_table_name("mexc_stocks")
                            threshold = datetime.now(UTC) - timedelta(hours=CLEANUP_HOURS)
                            client.execute_sql(f"DELETE FROM {table_name} WHERE timestamp < %s", threshold)
                        state.last_cleanup_time = now
                        print("Cleanup done")

                    except Exception as e:
                        print("Cleanup error:", e)

            except Exception as e:
                print("Main loop error:", e)

            await asyncio.sleep(POLL_INTERVAL)

    await exchange.close()


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    asyncio.run(main())
