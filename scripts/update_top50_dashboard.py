import json
import os
from datetime import datetime

import pandas as pd

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


def stooq_symbol(sym: str) -> str:
    return sym.replace(".", "-").lower() + ".us"


def fetch_close_series(tickers):
    close_data = {}
    failures = []

    for sym in tickers:
        stooq = stooq_symbol(sym)
        url = f"https://stooq.com/q/d/l/?s={stooq}&i=d"
        try:
            df = pd.read_csv(url, usecols=["Date", "Close"])
            if df.empty:
                failures.append(sym)
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df[(df["Date"] >= START_DATE) & (df["Date"] < END_DATE)]
            if df.empty:
                failures.append(sym)
                continue
            close_data[sym] = df.set_index("Date")["Close"].rename(sym)
        except Exception:
            failures.append(sym)

    if not close_data:
        raise SystemExit("No data downloaded from Stooq. Aborting.")

    close = pd.DataFrame(close_data).sort_index()
    return close, failures


def compute_signal(close: pd.DataFrame) -> pd.DataFrame:
    signal_12_1 = close.shift(21) / close.shift(252) - 1
    latest_date = signal_12_1.dropna(how="all").index.max()

    latest_sig = signal_12_1.loc[latest_date]
    latest_px = close.loc[latest_date]

    valid = latest_sig.dropna()
    valid = valid[latest_px[valid.index] > 5]

    ranked = valid.sort_values(ascending=False)
    return ranked.to_frame("signal_12_1"), latest_date


def main():
    close, failures = fetch_close_series(TOP_50_TICKERS)
    ranked, as_of_date = compute_signal(close)

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
                "signal_12_1": float(row["signal_12_1"]),
                "rank": int(row["rank"]),
                "action": row["action"],
            }
        )

    payload = {
        "as_of_date": as_of_date.date().isoformat(),
        "signal": "12-1 momentum",
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
