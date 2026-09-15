"""Daily stock screening across US, UK and EU markets.

Fetches quote data with a chain of fallbacks (yfinance -> Alpha Vantage ->
deterministic sample data), scores each ticker with a momentum/volume
confidence model, and writes a single JSON file consumed by the frontend
dashboard.

The module is structured so all analysis logic is pure and unit-testable:
`--mock` runs entirely offline against seeded sample data, so the pipeline can
be exercised deterministically in CI without any API keys or network access.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime
from pathlib import Path

DEFAULT_WATCHLIST = {
    "US": ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL", "META", "AMZN", "NFLX"],
    "UK": ["TSCO.L", "HSBA.L", "LLOY.L", "VOD.L", "BARC.L"],
    "EU": ["AIR.PA", "SIE.DE", "ASML.AS", "SAF.PA", "BMW.DE"],
}

# Realistic price floors/ceilings used to synthesise sample data.
PRICE_RANGES = {
    "AAPL": (150, 200), "MSFT": (300, 400), "TSLA": (150, 300),
    "NVDA": (400, 800), "GOOGL": (120, 150), "META": (300, 400),
    "AMZN": (120, 180), "NFLX": (500, 700), "TSCO.L": (2.5, 3.5),
    "HSBA.L": (6, 8), "LLOY.L": (0.4, 0.6), "VOD.L": (0.6, 0.9),
    "BARC.L": (1.5, 2.0), "AIR.PA": (120, 160), "SIE.DE": (140, 180),
    "ASML.AS": (600, 800), "SAF.PA": (180, 220), "BMW.DE": (80, 110),
}

COMPANY_NAMES = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation",
    "TSLA": "Tesla Inc.", "NVDA": "NVIDIA Corporation",
    "GOOGL": "Alphabet Inc.", "META": "Meta Platforms Inc.",
    "AMZN": "Amazon.com Inc.", "NFLX": "Netflix Inc.",
    "TSCO.L": "Tesco PLC", "HSBA.L": "HSBC Holdings PLC",
    "LLOY.L": "Lloyds Banking Group", "VOD.L": "Vodafone Group PLC",
    "BARC.L": "Barclays PLC", "AIR.PA": "Airbus SE",
    "SIE.DE": "Siemens AG", "ASML.AS": "ASML Holding NV",
    "SAF.PA": "Safran SA", "BMW.DE": "BMW AG",
}

# The default download region (equivalent to matplotlib's "Agg" behaviour): the
# script never opens interactive plots, so it is safe in headless/CI contexts.
YFINANCE_PERIODS = ("1mo", "2mo", "3mo", "6mo")

# Where the dashboard data file lives, relative to the repository root.
DEFAULT_OUTPUT = "data/processed/latest_stocks.json"


# --------------------------------------------------------------------------- #
# Pure analysis helpers (fully unit-testable, no I/O)                          #
# --------------------------------------------------------------------------- #
def price_momentum_points(price_change_pct: float) -> int:
    """Score contribution from the single-day price change."""
    if price_change_pct > 3:
        return 20
    if price_change_pct > 1:
        return 12
    if price_change_pct > 0:
        return 6
    if price_change_pct < -2:
        return -10
    return 0


def volume_points(volume_ratio: float) -> int:
    """Score contribution from the volume-to-average ratio."""
    if volume_ratio > 2.0:
        return 15
    if volume_ratio > 1.5:
        return 10
    if volume_ratio > 1.2:
        return 5
    if volume_ratio < 0.8:
        return -5
    return 0


def trend_points(five_day_change_pct: float | None) -> int:
    """Score contribution from the trailing five-day momentum.

    This is the indicator that actually exercises the (previously dead)
    ``hist_data`` argument: it confirms whether a single-day move is backed by
    a sustained short-term trend.
    """
    if five_day_change_pct is None:
        return 0
    if five_day_change_pct > 2:
        return 8
    if five_day_change_pct > 0:
        return 3
    if five_day_change_pct < -2:
        return -8
    return 0


def compute_confidence_score(
    price_change_pct: float,
    volume_ratio: float,
    five_day_change_pct: float | None = None,
) -> int:
    """Combine momentum, volume and trend signals into a 0-100 score."""
    score = 50
    score += price_momentum_points(price_change_pct)
    score += volume_points(volume_ratio)
    score += trend_points(five_day_change_pct)
    return max(0, min(100, score))


def generate_analysis_text(
    score: int, price_change_pct: float, volume_ratio: float
) -> str:
    """Human-readable English one-liner for the dashboard."""
    if score >= 75:
        base = "Strong bullish momentum"
    elif score >= 60:
        base = "Positive trend developing"
    elif score >= 45:
        base = "Watch for confirmation"
    else:
        base = "Needs stronger signals"

    if price_change_pct > 2:
        trend = "with significant price movement"
    elif price_change_pct > 0:
        trend = "with positive price action"
    else:
        trend = "consolidating at current levels"

    if volume_ratio > 1.5:
        volume = "on high volume"
    elif volume_ratio > 1.0:
        volume = "on average volume"
    else:
        volume = "volume below average"

    return f"{base} {trend} {volume}"


def company_name(ticker: str) -> str:
    """Human-readable company name, falling back to the raw ticker."""
    return COMPANY_NAMES.get(ticker, ticker)


# --------------------------------------------------------------------------- #
# Deterministic sample data generator                                          #
# --------------------------------------------------------------------------- #
class RobustStockAnalyzer:
    """Orchestrates fetching, scoring and persistence of the stock screener.

    Parameters are injected so the pipeline can be driven offline and
    deterministically in tests:

    - ``rng``: a ``random.Random`` instance used for sample-data generation.
    - ``now``: a zero-arg callable returning the current datetime.
    - ``delay``: a zero-arg callable returning seconds to sleep between ticks.
    - ``sleep``: the sleep function itself (swapped for a no-op in tests).
    - ``fetch_quote``: the live quote fetcher, replaceable with a stub.
    """

    def __init__(
        self,
        watchlist: dict[str, list[str]] | None = None,
        rng: random.Random | None = None,
        now=None,
        delay=None,
        sleep=None,
        fetch_quote=None,
    ):
        self.watchlist = watchlist if watchlist is not None else DEFAULT_WATCHLIST
        self.rng = rng or random.Random()
        self.now = now or datetime.now
        self.sleep = sleep or _time_sleep
        self.delay = delay if delay is not None else self._default_delay
        self._fetch_quote = fetch_quote or self._fetch_quote_live

    def _default_delay(self) -> float:
        return self.rng.uniform(2, 5)

    # -- data acquisition ---------------------------------------------------- #
    def _fetch_quote_live(self, ticker: str) -> dict | None:
        # yfinance is a heavy dependency; load lazily so mock/demo runs and the
        # test suite never need it installed.
        try:
            import yfinance as yf  # type: ignore

            stock = yf.Ticker(ticker)
            for period in YFINANCE_PERIODS:
                try:
                    hist = stock.history(period=period)
                except Exception:  # noqa: BLE001 - network/parse errors vary
                    continue
                if len(hist) > 5:
                    return self._record_from_history(ticker, hist)
        except Exception as exc:  # noqa: BLE001
            print(f"  yfinance failed for {ticker}: {str(exc)[:50]}")

        return self._fetch_alpha_vantage(ticker)

    def _fetch_alpha_vantage(self, ticker: str) -> dict | None:
        alpha_key = os.getenv("ALPHA_VANTAGE_KEY", "demo")
        if alpha_key == "demo":
            return None
        try:
            import requests  # type: ignore

            url = (
                "https://www.alphavantage.co/query"
                f"?function=GLOBAL_QUOTE&symbol={ticker}&apikey={alpha_key}"
            )
            data = requests.get(url, timeout=10).json()
            quote = data.get("Global Quote")
            if not quote:
                return None
            current_price = float(quote["05. price"])
            prev_close = float(quote["08. previous close"])
            price_change_pct = (
                (current_price - prev_close) / prev_close * 100 if prev_close else 0.0
            )
            volume = int(float(quote["06. volume"]))
            score = compute_confidence_score(price_change_pct, 1.0)
            return {
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "price_change": round(current_price - prev_close, 2),
                "price_change_percent": round(price_change_pct, 2),
                "volume": volume,
                "volume_ratio": 1.0,
                "company_name": company_name(ticker),
                "confidence_score": score,
                "analysis": generate_analysis_text(score, price_change_pct, 1.0),
                "catalyst": "Alpha Vantage API data",
                "data_source": "alphavantage",
                "last_updated": self.now().isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            print(f"  Alpha Vantage failed for {ticker}: {str(exc)[:50]}")
            return None

    def _record_from_history(self, ticker: str, hist) -> dict:
        """Build a record from a successful yfinance history frame."""
        closes = hist["Close"]
        current_price = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close * 100) if prev_close else 0.0

        volumes = hist["Volume"]
        current_volume = float(volumes.iloc[-1])
        avg_volume = float(volumes.tail(20).mean()) if len(volumes) >= 20 else current_volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Five-day trend now drives the indicator that used to be a dead param.
        five_day = None
        if len(closes) >= 6:
            five = float(closes.iloc[-6])
            five_day = (current_price - five) / five * 100 if five else None

        score = compute_confidence_score(price_change_pct, volume_ratio, five_day)

        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "price_change": round(price_change, 2),
            "price_change_percent": round(price_change_pct, 2),
            "volume": int(current_volume),
            "volume_ratio": round(volume_ratio, 2),
            "company_name": company_name(ticker),
            "confidence_score": score,
            "analysis": generate_analysis_text(score, price_change_pct, volume_ratio),
            "catalyst": "Live market data analysis",
            "data_source": "yfinance",
            "last_updated": self.now().isoformat(),
        }

    def _synthetic_record(self, ticker: str) -> dict:
        """Deterministic sample record for mock/demo runs (offline)."""
        lo, hi = PRICE_RANGES.get(ticker, (50, 100))
        base_price = self.rng.uniform(lo, hi)
        price_change_pct = self.rng.uniform(-3, 5)
        price_change = base_price * (price_change_pct / 100)
        current_price = base_price + price_change
        volume_ratio = self.rng.uniform(0.8, 2.5)
        score = self.rng.randint(40, 85)
        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "price_change": round(price_change, 2),
            "price_change_percent": round(price_change_pct, 2),
            "volume": self.rng.randint(1_000_000, 50_000_000),
            "volume_ratio": round(volume_ratio, 2),
            "company_name": company_name(ticker),
            "confidence_score": score,
            "analysis": generate_analysis_text(score, price_change_pct, volume_ratio),
            "catalyst": "Sample data - API limited",
            "data_source": "sample",
            "last_updated": self.now().isoformat(),
        }

    # -- orchestration ------------------------------------------------------- #
    def update_all_stocks(
        self,
        mock: bool = False,
        no_delay: bool = False,
        limit: int | None = None,
    ) -> tuple[list[dict], dict[str, int]]:
        """Analyse every ticker and return the ranked list of records."""
        print("Running stock analysis...")
        all_stocks: list[dict] = []

        for region, tickers in self.watchlist.items():
            print(f"\nAnalyzing {region} stocks:")
            tickers = tickers if limit is None else tickers[:limit]
            for i, ticker in enumerate(tickers):
                if mock:
                    record = self._synthetic_record(ticker)
                else:
                    record = self._fetch_quote(ticker)
                    if record is None:
                        record = self._synthetic_record(ticker)
                if record:
                    record["region"] = region
                    all_stocks.append(record)

                if i < len(tickers) - 1 and not no_delay:
                    delay = self.delay()
                    print(f"    Waiting {delay:.1f} seconds...")
                    self.sleep(delay)

        all_stocks.sort(key=lambda x: x["confidence_score"], reverse=True)

        sources: dict[str, int] = {}
        for stock in all_stocks:
            src = stock.get("data_source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        return all_stocks, sources

    def write_output(self, all_stocks: list[dict], sources: dict[str, int],
                     output_path: str | Path) -> Path:
        """Serialize the ranked records to ``output_path`` (created if needed)."""
        output = {
            "last_updated": self.now().isoformat(),
            "total_stocks_analyzed": len(all_stocks),
            "data_sources": sources,
            "stocks": all_stocks,
        }
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        return path


def _time_sleep(seconds: float) -> None:  # pragma: no cover - trivial passthrough
    import time

    time.sleep(seconds)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="update_data",
        description="Daily stock screening across US, UK and EU markets.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run offline against deterministic sample data (no API calls).",
    )
    parser.add_argument(
        "--no-delay",
        action="store_true",
        help="Skip the throttling sleep between tickers.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only analyze the first N tickers per region (fast smoke run).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT}, resolved from repo root).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for the sample-data RNG (makes --mock fully reproducible).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Resolve against the repository root (this file's parent's parent), so the
    # script works regardless of the caller's working directory.
    repo_root = Path(__file__).resolve().parent.parent
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    rng = random.Random(args.seed)
    analyzer = RobustStockAnalyzer(rng=rng, delay=lambda: 0.0)
    all_stocks, sources = analyzer.update_all_stocks(
        mock=args.mock, no_delay=args.no_delay, limit=args.limit
    )
    analyzer.write_output(all_stocks, sources, output_path)

    print(f"\nSUCCESS: Analyzed {len(all_stocks)} stocks")
    print(f"Data sources: {sources}")
    print(f"Data saved to: {output_path}")

    if all_stocks:
        print("\nTop stocks by confidence:")
        for i, stock in enumerate(all_stocks[:8]):
            src = stock.get("data_source", "unknown")
            print(
                f"   {i + 1}. {stock['ticker']}: {stock['confidence_score']}/100 [{src}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())