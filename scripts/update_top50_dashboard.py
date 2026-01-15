import json
import os
import time
from datetime import datetime, timedelta
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

START_DATE = "2023-01-01"
END_DATE = "2026-02-01"
CACHE_DAYS = 7
FMP_API_URL = "https://financialmodelingprep.com/stable"
SP500_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"


def fetch_json(url: str):
    request = Request(url, headers={"User-Agent": "jf-alpha-dashboard/1.0"})
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "jf-alpha-dashboard/1.0"})
    with urlopen(request) as response:
        return response.read().decode("utf-8")


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
            "symbol": sym,
            "from": START_DATE,
            "to": END_DATE,
            "apikey": api_key,
        }
        url = f"{FMP_API_URL}/historical-price-eod/full?{urlencode(params)}"
        for attempt in range(3):
            try:
                payload = fetch_json(url)
                if isinstance(payload, dict):
                    if payload.get("error") or payload.get("status") == "error":
                        raise ValueError("FMP error response")
                    history = payload.get("historical", [])
                else:
                    history = payload
                if not history:
                    raise ValueError("Empty price response")
                df = pd.DataFrame(history)[["date", "close"]]
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date"])
                df = df[(df["date"] >= START_DATE) & (df["date"] < END_DATE)]
                if df.empty:
                    raise ValueError("No price rows in date range")
                close_data[sym] = df.set_index("date")["close"].rename(sym)
                break
            except Exception as exc:
                if isinstance(exc, HTTPError) and exc.code == 429:
                    time.sleep(6.0)
                else:
                    time.sleep(1.5)
                if attempt == 2:
                    failures.append(sym)
        time.sleep(0.6)

    if not close_data:
        raise SystemExit("No price data downloaded from FMP. Aborting.")

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
    for symbol in tickers:
        params = {"symbol": symbol, "apikey": api_key}
        url = f"{FMP_API_URL}/ratios?{urlencode(params)}"
        payload = {}
        for attempt in range(3):
            try:
                payload = fetch_json(url)
                break
            except Exception as exc:
                if isinstance(exc, HTTPError) and exc.code == 429:
                    time.sleep(6.0)
                else:
                    time.sleep(1.5)
        ratios = payload[0] if isinstance(payload, list) and payload else {}
        data[symbol] = {
            "pe_ratio": parse_float(ratios.get("priceEarningsRatio")),
            "pb_ratio": parse_float(ratios.get("priceToBookRatio")),
            "roe": parse_float(ratios.get("returnOnEquity")),
            "operating_margin": parse_float(ratios.get("operatingProfitMargin")),
            "profit_margin": parse_float(ratios.get("netProfitMargin")),
        }
        time.sleep(0.3)

    return data


def fetch_market_caps(tickers):
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise SystemExit("Missing FMP_API_KEY in environment.")

    caps = {}
    for symbol in tickers:
        params = {"symbol": symbol, "apikey": api_key}
        url = f"{FMP_API_URL}/quote?{urlencode(params)}"
        payload = []
        for attempt in range(3):
            try:
                payload = fetch_json(url)
                break
            except Exception as exc:
                if isinstance(exc, HTTPError) and exc.code == 429:
                    time.sleep(6.0)
                else:
                    time.sleep(1.5)
        if isinstance(payload, list) and payload:
            item = payload[0]
            market_cap = parse_float(item.get("marketCap"))
            if market_cap is not None:
                caps[symbol] = market_cap
        time.sleep(0.4)

    return caps


def get_sp500_tickers():
    table = pd.read_csv(SP500_URL)
    return table["Symbol"].dropna().unique().tolist()


def get_nasdaq100_tickers():
    html = fetch_html(NASDAQ100_URL)
    tables = pd.read_html(StringIO(html))
    for table in tables:
        cols = [str(c).lower() for c in table.columns]
        if any("ticker" in c for c in cols):
            tickers = table[table.columns[0]].dropna().astype(str).tolist()
            return tickers
    raise SystemExit("Failed to parse Nasdaq-100 tickers from Wikipedia.")


def compute_signal(
    close: pd.DataFrame, fundamentals: dict, tickers: list, spy_close: pd.Series
) -> tuple:
    signal_12_1 = close.shift(21) / close.shift(252) - 1
    latest_date = signal_12_1.dropna(how="all").index.max()

    available = [t for t in tickers if t in signal_12_1.columns]
    if not available:
        return pd.DataFrame(), latest_date

    latest_sig = signal_12_1.loc[latest_date, available]
    latest_px = close.loc[latest_date, available]

    valid = latest_sig.dropna()
    valid = valid[latest_px[valid.index] > 5]
    if valid.empty:
        return pd.DataFrame(), latest_date

    momentum = valid.sort_values(ascending=False).rename("momentum_12_1")

    # Relative strength vs SPY (12-month return difference)
    spy_return = None
    if latest_date in spy_close.index:
        spy_return = spy_close.loc[latest_date] / spy_close.shift(252).loc[latest_date] - 1

    rs_scores = {}
    for ticker in momentum.index:
        if spy_return is None:
            rs_scores[ticker] = None
            continue
        series = close[ticker]
        if latest_date not in series.index:
            rs_scores[ticker] = None
            continue
        stock_return = series.loc[latest_date] / series.shift(252).loc[latest_date] - 1
        rs_scores[ticker] = stock_return - spy_return

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
        quality_rows[ticker] = (
            sum(quality_parts) / len(quality_parts) if quality_parts else None
        )

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

    ma50 = close[available].rolling(50).mean().loc[latest_date]
    ma150 = close[available].rolling(150).mean().loc[latest_date]
    ma200 = close[available].rolling(200).mean().loc[latest_date]
    ma200_prev = close[available].rolling(200).mean().shift(20).loc[latest_date]

    rs_series = pd.Series(rs_scores, name="rs_score")
    rs_valid = rs_series.dropna()
    rs_threshold = rs_valid.quantile(0.8) if not rs_valid.empty else None

    sepa_rows = {}
    for ticker in momentum.index:
        price = latest_px[ticker]
        sma50 = ma50.get(ticker)
        sma150 = ma150.get(ticker)
        sma200 = ma200.get(ticker)
        sma200_prev = ma200_prev.get(ticker)
        rs_score = rs_series.get(ticker)

        if any(pd.isna(x) for x in [price, sma50, sma150, sma200, sma200_prev]):
            sepa_rows[ticker] = False
            continue
        if rs_threshold is not None and (rs_score is None or rs_score < rs_threshold):
            sepa_rows[ticker] = False
            continue

        sepa_rows[ticker] = bool(
            price > sma50
            and price > sma150
            and price > sma200
            and sma50 > sma150
            and sma150 > sma200
            and sma200 > sma200_prev
        )

    ranked = pd.DataFrame(
        {
            "momentum_12_1": momentum,
            "quality_raw": quality_series,
            "value_raw": value_series,
            "momentum_z": momentum_z,
            "quality_z": quality_z,
            "value_z": value_z,
            "composite_score": composite,
            "rs_score": pd.Series(rs_scores, name="rs_score"),
            "ma_50": ma50,
            "ma_150": ma150,
            "ma_200": ma200,
            "sepa_pass": pd.Series(sepa_rows, name="sepa_pass"),
        }
    ).sort_values("composite_score", ascending=False)

    return ranked, latest_date


def build_universes():
    sp500 = get_sp500_tickers()
    nasdaq100 = get_nasdaq100_tickers()

    sp500_caps = fetch_market_caps(sp500)
    sorted_caps_desc = sorted(sp500_caps.items(), key=lambda x: x[1], reverse=True)
    sorted_caps_asc = list(reversed(sorted_caps_desc))
    top100 = [ticker for ticker, _ in sorted_caps_desc][:100]
    bottom100 = [ticker for ticker, _ in sorted_caps_asc][:100]

    return {
        "nasdaq100": {
            "name": "Nasdaq-100",
            "tickers": nasdaq100,
        },
        "sp500_top100": {
            "name": "S&P 500 Top 100",
            "tickers": top100,
        },
        "sp500_bottom100": {
            "name": "S&P 500 Bottom 100",
            "tickers": bottom100,
        },
    }


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if load_dotenv:
        load_dotenv(dotenv_path=os.path.join(root_dir, ".env"))

    universes = build_universes()
    base_tickers = sorted({t for u in universes.values() for t in u["tickers"]})
    all_tickers = list(base_tickers)
    if "SPY" not in all_tickers:
        all_tickers.append("SPY")

    close, failures = fetch_close_series(all_tickers)
    spy_close = close.get("SPY", pd.Series(dtype=float))

    cache_path = os.path.join(root_dir, "dashboard", "data", "fundamentals_cache.json")
    cache = load_fundamentals_cache(cache_path)
    if cache:
        fundamentals = cache.get("data", {})
        fundamentals_as_of = cache.get("as_of")
    else:
        fundamentals = fetch_fundamentals(base_tickers)
        fundamentals_as_of = datetime.utcnow().date().isoformat()
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"as_of": fundamentals_as_of, "data": fundamentals}, f, indent=2)

    universe_payloads = []
    as_of_date = None

    for universe_id, info in universes.items():
        ranked, latest_date = compute_signal(
            close, fundamentals, info["tickers"], spy_close
        )
        as_of_date = latest_date

        total = len(ranked)
        if total == 0:
            continue

        n = max(1, total // 5)
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
                    "quality_raw": None
                    if pd.isna(row["quality_raw"])
                    else float(row["quality_raw"]),
                    "value_raw": None
                    if pd.isna(row["value_raw"])
                    else float(row["value_raw"]),
                    "composite_score": float(row["composite_score"]),
                    "rs_score": None
                    if pd.isna(row["rs_score"])
                    else float(row["rs_score"]),
                    "ma_50": None if pd.isna(row["ma_50"]) else float(row["ma_50"]),
                    "ma_150": None
                    if pd.isna(row["ma_150"])
                    else float(row["ma_150"]),
                    "ma_200": None
                    if pd.isna(row["ma_200"])
                    else float(row["ma_200"]),
                    "sepa_pass": bool(row["sepa_pass"]),
                    "rank": int(row["rank"]),
                    "action": row["action"],
                }
            )

        sepa_candidates = [r for r in records if r["sepa_pass"]]
        sepa_top = sepa_candidates[:5]

        sepa_charts = []
        for candidate in sepa_top:
            ticker = candidate["ticker"]
            if ticker not in close.columns:
                continue
            series = close[ticker].dropna()
            spy_series = spy_close.reindex(series.index).dropna()
            series = series.loc[spy_series.index]

            ma50_series = series.rolling(50).mean()
            ma150_series = series.rolling(150).mean()
            ma200_series = series.rolling(200).mean()

            tail = series.index[-220:] if len(series.index) > 220 else series.index
            dates = [d.date().isoformat() for d in tail]

            def to_list(s):
                return [None if pd.isna(v) else float(v) for v in s.loc[tail]]

            rs_line = series.loc[tail] / spy_series.loc[tail]
            rs_norm = rs_line / rs_line.iloc[0] if not rs_line.empty else rs_line

            sepa_charts.append(
                {
                    "ticker": ticker,
                    "dates": dates,
                    "close": to_list(series),
                    "ma50": to_list(ma50_series),
                    "ma150": to_list(ma150_series),
                    "ma200": to_list(ma200_series),
                    "rs_line": to_list(rs_norm),
                    "rs_score": candidate.get("rs_score"),
                }
            )

        universe_payloads.append(
            {
                "id": universe_id,
                "name": info["name"],
                "universe_size": total,
                "buy_count": int((ranked["action"] == "BUY").sum()),
                "sell_count": int((ranked["action"] == "SELL").sum()),
                "sepa_count": len(sepa_candidates),
                "sepa_candidates": sepa_candidates,
                "sepa_charts": sepa_charts,
                "records": records,
            }
        )

    payload = {
        "as_of_date": as_of_date.date().isoformat() if as_of_date else "",
        "fundamentals_as_of": fundamentals_as_of,
        "signal": "Composite (momentum + quality + value)",
        "universes": universe_payloads,
        "price_failures": failures,
    }

    out_dir = os.path.join(root_dir, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "top50_signals.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    js_path = os.path.join(out_dir, "top50_signals.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.TOP50_DATA = ")
        json.dump(payload, f)
        f.write(";")

    print(
        f"Wrote {out_path} ({len(universe_payloads)} universes) as of {payload['as_of_date']}"
    )


if __name__ == "__main__":
    main()
