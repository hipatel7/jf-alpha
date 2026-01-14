import json
import os
import time
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

TOP_50_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOG",
    "GOOGL",
    "META",
    "BRK.B",
    "LLY",
    "AVGO",
    "JPM",
    "V",
    "MA",
    "XOM",
    "UNH",
    "WMT",
    "PG",
    "COST",
    "HD",
    "ABBV",
    "MRK",
    "CVX",
    "PEP",
    "KO",
    "ORCL",
    "NFLX",
    "ADBE",
    "CRM",
    "CSCO",
    "ACN",
    "LIN",
    "MCD",
    "AMAT",
    "DHR",
    "TXN",
    "NKE",
    "QCOM",
    "AMD",
    "UPS",
    "VZ",
    "TMO",
    "ABT",
    "INTU",
    "PM",
    "IBM",
    "CAT",
    "GE",
    "BA",
    "GS",
    "RTX",
]

START_DATE = "2024-01-01"
END_DATE = "2026-02-01"
CACHE_DAYS = 7
FMP_API_URL = "https://financialmodelingprep.com/api/v3"


def fetch_json(url: str) -> dict:
    with urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_float(value):
    try:
        if value in (None, "", "None"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_close_series(tickers):
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise SystemExit("Missing FMP_API_KEY in environment.")

    close_data = {}
    failures = []

    for sym in tickers:
        params = {
            "from": START_DATE,
            "to": END_DATE,
            "apikey": api_key,
        }
        url = f"{FMP_API_URL}/historical-price-full/{sym}?{urlencode(params)}"
        try:
            payload = fetch_json(url)
            history = payload.get("historical", []) if isinstance(payload, dict) else []
            if not history:
                failures.append(sym)
                continue
            df = pd.DataFrame(history)[["date", "close"]]
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
            df = df[(df["date"] >= START_DATE) & (df["date"] < END_DATE)]
            if df.empty:
                failures.append(sym)
                continue
            close_data[sym] = df.set_index("date")["close"].rename(sym)
        except Exception:
            failures.append(sym)
        time.sleep(0.3)

    if not close_data:
        raise SystemExit("No data downloaded from Stooq. Aborting.")

    close = pd.DataFrame(close_data).sort_index()
    return close, failures


def load_fundamentals_cache(cache_path: str):
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        as_of = datetime.strptime(payload.get("as_of", ""), "%Y-%m-%d").date()
        if datetime.utcnow().date() - as_of > timedelta(days=CACHE_DAYS):
            return None
        return payload
    except Exception:
        return None


def fetch_fundamentals(tickers):
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise SystemExit("Missing FMP_API_KEY in environment.")

    data = {}
    for idx, symbol in enumerate(tickers, start=1):
        params = {"apikey": api_key}
        url = f"{FMP_API_URL}/ratios-ttm/{symbol}?{urlencode(params)}"
        try:
            payload = fetch_json(url)
        except URLError:
            payload = {}

        ratios = payload[0] if isinstance(payload, list) and payload else {}
        data[symbol] = {
            "pe_ratio": parse_float(ratios.get("peRatioTTM")),
            "pb_ratio": parse_float(ratios.get("priceToBookRatioTTM")),
            "roe": parse_float(ratios.get("returnOnEquityTTM")),
            "operating_margin": parse_float(ratios.get("operatingProfitMarginTTM")),
            "profit_margin": parse_float(ratios.get("netProfitMarginTTM")),
        }

        time.sleep(0.3)

    return data


def compute_signal(close: pd.DataFrame, fundamentals: dict) -> pd.DataFrame:
    signal_12_1 = close.shift(21) / close.shift(252) - 1
    latest_date = signal_12_1.dropna(how="all").index.max()

    latest_sig = signal_12_1.loc[latest_date]
    latest_px = close.loc[latest_date]

    valid = latest_sig.dropna()
    valid = valid[latest_px[valid.index] > 5]

    momentum = valid.sort_values(ascending=False).rename("momentum_12_1")

    value_rows = {}
    quality_rows = {}
    for ticker in momentum.index:
        metrics = fundamentals.get(ticker, {})
        pe = metrics.get("pe_ratio")
        pb = metrics.get("pb_ratio")
        roe = metrics.get("roe")
        op_margin = metrics.get("operating_margin")
        profit_margin = metrics.get("profit_margin")

        value_parts = []
        if pe and pe > 0:
            value_parts.append(1.0 / pe)
        if pb and pb > 0:
            value_parts.append(1.0 / pb)
        value_rows[ticker] = sum(value_parts) / len(value_parts) if value_parts else None

        quality_parts = []
        if roe is not None:
            quality_parts.append(roe)
        margin = op_margin if op_margin is not None else profit_margin
        if margin is not None:
            quality_parts.append(margin)
        quality_rows[ticker] = sum(quality_parts) / len(quality_parts) if quality_parts else None

    value_series = pd.Series(value_rows, name="value_raw")
    quality_series = pd.Series(quality_rows, name="quality_raw")

    def zscore(series: pd.Series) -> pd.Series:
        valid_vals = series.dropna()
        if valid_vals.empty or valid_vals.std() == 0:
            return pd.Series(0.0, index=series.index)
        return (series - valid_vals.mean()) / valid_vals.std()

    momentum_z = zscore(momentum)
    quality_z = zscore(quality_series)
    value_z = zscore(value_series)

    composite = (momentum_z + quality_z + value_z) / 3.0

    ranked = pd.DataFrame(
        {
            "momentum_12_1": momentum,
            "quality_raw": quality_series,
            "value_raw": value_series,
            "momentum_z": momentum_z,
            "quality_z": quality_z,
            "value_z": value_z,
            "composite_score": composite,
        }
    ).sort_values("composite_score", ascending=False)

    return ranked, latest_date


def main():
    if load_dotenv:
        load_dotenv()
    close, failures = fetch_close_series(TOP_50_TICKERS)
    cache_path = os.path.join(os.getcwd(), "dashboard", "data", "fundamentals_cache.json")
    cache = load_fundamentals_cache(cache_path)
    if cache:
        fundamentals = cache.get("data", {})
        fundamentals_as_of = cache.get("as_of")
    else:
        fundamentals = fetch_fundamentals(TOP_50_TICKERS)
        fundamentals_as_of = datetime.utcnow().date().isoformat()
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"as_of": fundamentals_as_of, "data": fundamentals}, f, indent=2)

    ranked, as_of_date = compute_signal(close, fundamentals)

    total = len(ranked)
    if total == 0:
        raise SystemExit("No valid signals to rank.")

    n = max(1, total // 5)  # top/bottom 20% of available symbols
    ranked["rank"] = range(1, total + 1)
    ranked["action"] = "HOLD"
    ranked.loc[ranked.index[:n], "action"] = "BUY"
    ranked.loc[ranked.index[-n:], "action"] = "SELL"

    records = []
    for ticker, row in ranked.reset_index().iterrows():
        records.append(
            {
                "ticker": row["index"],
                "momentum_12_1": float(row["momentum_12_1"]),
                "quality_raw": None if pd.isna(row["quality_raw"]) else float(row["quality_raw"]),
                "value_raw": None if pd.isna(row["value_raw"]) else float(row["value_raw"]),
                "composite_score": float(row["composite_score"]),
                "rank": int(row["rank"]),
                "action": row["action"],
            }
        )

    payload = {
        "as_of_date": as_of_date.date().isoformat(),
        "fundamentals_as_of": fundamentals_as_of,
        "signal": "Composite (momentum + quality + value)",
        "universe_size": total,
        "buy_count": int((ranked["action"] == "BUY").sum()),
        "sell_count": int((ranked["action"] == "SELL").sum()),
        "records": records,
    }

    out_dir = os.path.join(os.getcwd(), "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "top50_signals.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    js_path = os.path.join(out_dir, "top50_signals.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.TOP50_DATA = ")
        json.dump(payload, f)
        f.write(";")

    if failures:
        failures_path = os.path.join(out_dir, "top50_failed.csv")
        pd.DataFrame({"ticker": failures}).to_csv(failures_path, index=False)

    print(f"Wrote {out_path} ({total} symbols) as of {payload['as_of_date']}")


if __name__ == "__main__":
    main()
