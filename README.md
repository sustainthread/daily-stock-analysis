# Daily Stock Analysis Dashboard

Live dashboard: https://sustainthread.github.io/daily-stock-analysis/

## Features

- Daily stock screening across US, UK, EU markets
- Technical analysis indicators (momentum + volume + trend confidence model)
- Confidence-scoring system (0-100)
- Responsive web dashboard

## How it works

`scripts/update_data.py` fetches a quote for every ticker on the watchlist using
a fallback chain:

1. **yfinance** — for the most recent 1-6 months of history.
2. **Alpha Vantage** — needs `ALPHA_VANTAGE_KEY` in the environment.
3. **Sample data** — deterministic seeded data as a last resort so a run never
   fails outright.

Each quote is scored with `compute_confidence_score`, which combines a
single-day price-momentum signal, a volume ratio signal, and a trailing
five-day trend confirmation into a 0-100 score. Results are written to
`data/processed/latest_stocks.json` for the dashboard.

## CLI

```bash
# Live run (network + API keys)
python scripts/update_data.py

# Deterministic offline run — no API calls, reproducible with a seed
python scripts/update_data.py --mock --seed 42

# Skip the throttling delay (CI / quick tests)
python scripts/update_data.py --no-delay --limit 3
```

| Flag            | Description                                            |
|-----------------|--------------------------------------------------------|
| `--mock`        | Offline run against seeded sample data (no API calls). |
| `--no-delay`    | Skip the throttling sleep between tickers.             |
| `--limit N`     | Only analyze the first N tickers per region.           |
| `--output PATH` | Output JSON path (default: `data/processed/latest_stocks.json`). |
| `--seed N`      | Seed for the sample-data RNG (reproducible `--mock`).  |

## Development

```bash
pip install -e ".[dev]"
python -m pytest            # offline test suite
ruff check scripts tests    # lint
```

*Note: This is for educational purposes only.*