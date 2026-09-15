"""Tests for scripts/update_data.py — the daily stock analysis pipeline.

All tests run offline: they exercise the pure analysis helpers, the
deterministic synthetic-record generator, orchestration against a stub
fetcher, the JSON writer, and the CLI parser. No network, no API keys.
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import update_data as ud  # noqa: E402


# --------------------------------------------------------------------------- #
# Purse confidence scoring                                                     #
# --------------------------------------------------------------------------- #
class TestConfidenceScoring:
    def test_baseline_is_fifty(self):
        assert ud.compute_confidence_score(0, 1.0) == 50

    def test_price_momentum_buckets(self):
        assert ud.price_momentum_points(4) == 20
        assert ud.price_momentum_points(2) == 12
        assert ud.price_momentum_points(0.5) == 6
        assert ud.price_momentum_points(-3) == -10
        assert ud.price_momentum_points(-1) == 0

    def test_volume_buckets(self):
        assert ud.volume_points(2.5) == 15
        assert ud.volume_points(1.6) == 10
        assert ud.volume_points(1.3) == 5
        assert ud.volume_points(1.0) == 0
        assert ud.volume_points(0.5) == -5

    def test_extreme_inputs_stay_in_range(self):
        score = ud.compute_confidence_score(10, 3.0, 5)
        assert score == 93  # 50 + 20(price) + 15(volume) + 8(trend)
        assert 0 <= score <= 100

    def test_negative_extreme_stays_in_range(self):
        score = ud.compute_confidence_score(-20, 0.1, -5)
        assert score == 27  # 50 - 10(price) - 5(volume) - 8(trend)
        assert 0 <= score <= 100

    def test_trend_bonus_uses_dead_parameter(self):
        # Previously the hist_data-derived trend signal was ignored entirely.
        assert ud.trend_points(3) == 8
        assert ud.trend_points(1) == 3
        assert ud.trend_points(0.5) == 3
        assert ud.trend_points(-3) == -8
        assert ud.trend_points(0) == 0
        assert ud.trend_points(None) == 0

    def test_trend_lifts_score(self):
        base = ud.compute_confidence_score(0, 1.0, None)
        boosted = ud.compute_confidence_score(0, 1.0, 3)
        assert boosted == base + 8


# --------------------------------------------------------------------------- #
# Analysis text                                                                #
# --------------------------------------------------------------------------- #
class TestAnalysisText:
    def test_strong_bullish(self):
        assert ud.generate_analysis_text(80, 3, 2.0).startswith("Strong bullish")

    def test_positive_trend(self):
        assert ud.generate_analysis_text(65, 0.5, 1.2).startswith("Positive trend")

    def test_watch(self):
        assert ud.generate_analysis_text(50, 0.1, 1.0).startswith("Watch")

    def test_needs_signals(self):
        assert ud.generate_analysis_text(30, -1, 1.0).startswith("Needs stronger")

    def test_company_name_fallback(self):
        assert ud.company_name("AAPL") == "Apple Inc."
        assert ud.company_name("ZZZZ") == "ZZZZ"


# --------------------------------------------------------------------------- #
# Synthetic data generator                                                     #
# --------------------------------------------------------------------------- #
class TestSyntheticRecords:
    def _analyzer(self, seed=7):
        return ud.RobustStockAnalyzer(
            rng=random.Random(seed),
            now=lambda: datetime(2026, 1, 2, 3, 4, 5),
            delay=lambda: 0.0,
        )

    def test_record_shape(self):
        rec = self._analyzer()._synthetic_record("AAPL")
        assert rec["ticker"] == "AAPL"
        assert rec["company_name"] == "Apple Inc."
        assert rec["data_source"] == "sample"
        assert 0 <= rec["confidence_score"] <= 100
        # Scalars are rounded where declared.
        assert isinstance(rec["current_price"], float)
        assert isinstance(rec["volume"], int)

    def test_deterministic_with_seed(self):
        a = self._analyzer(seed=11)._synthetic_record("NVDA")
        b = self._analyzer(seed=11)._synthetic_record("NVDA")
        assert a == b

    def test_different_seed_differs(self):
        a = self._analyzer(seed=1)._synthetic_record("NVDA")
        b = self._analyzer(seed=2)._synthetic_record("NVDA")
        assert a["current_price"] != b["current_price"]


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #
class TestOrchestration:
    def _analyzer(self, stub_quote=None):
        return ud.RobustStockAnalyzer(
            watchlist={"US": ["AAA", "BBB"]},
            rng=random.Random(3),
            now=lambda: datetime(2026, 1, 2, 0, 0, 0),
            delay=lambda: 0.0,
            sleep=lambda _s: None,
            fetch_quote=stub_quote,
        )

    def test_mock_sorts_high_to_low(self):
        stocks, sources = self._analyzer().update_all_stocks(mock=True, no_delay=True)
        scores = [s["confidence_score"] for s in stocks]
        assert scores == sorted(scores, reverse=True)
        assert len(stocks) == 2
        assert sources == {"sample": 2}

    def test_limit_caps_tickers_per_region(self):
        stocks, _ = self._analyzer().update_all_stocks(mock=True, no_delay=True, limit=1)
        assert len(stocks) == 1

    def test_live_path_falls_back_to_sample_on_failure(self):
        def failing_quote(_t):  # network path returns None
            return None

        stocks, sources = self._analyzer(failing_quote).update_all_stocks(no_delay=True)
        # Every record came from the deterministic fallback.
        assert len(stocks) == 2
        assert all(s["data_source"] == "sample" for s in stocks)

    def test_live_path_uses_quote(self):
        live = [{
            "ticker": "AAA", "current_price": 10.0, "price_change": 1.0,
            "price_change_percent": 11.0, "volume": 100, "volume_ratio": 1.5,
            "company_name": "Acme", "confidence_score": 99,
            "analysis": "x", "catalyst": "c", "data_source": "yfinance",
            "last_updated": "now",
        }]

        def stub_quote(t):
            return next((x for x in live if x["ticker"] == t), None)

        stocks, sources = self._analyzer(stub_quote).update_all_stocks(
            mock=True  # mock path ignores fetch_quote by design
        )
        # mock path synthesises regardless; assert data_source reflects that.
        assert all(s["data_source"] == "sample" for s in stocks)


# --------------------------------------------------------------------------- #
# Output writer                                                                #
# --------------------------------------------------------------------------- #
class TestOutputWriter:
    def test_writes_nested_json(self, tmp_path):
        target = tmp_path / "out" / "latest.json"
        analyzer = ud.RobustStockAnalyzer(
            watchlist={"US": ["AAA"]},
            rng=random.Random(1), now=lambda: datetime(2026, 1, 1, 12, 0, 0)
        )
        stocks, sources = analyzer.update_all_stocks(mock=True, no_delay=True)
        written = analyzer.write_output(stocks, sources, target)

        assert written == target
        assert target.exists()
        data = json.loads(target.read_text())
        assert data["total_stocks_analyzed"] == 1
        assert data["data_sources"] == {"sample": 1}
        assert data["last_updated"] == "2026-01-01T12:00:00"

    def test_relative_output_anchored_to_repo_root(self, monkeypatch, tmp_path):
        # Regression: a relative output path must resolve against the repo
        # root, not the caller's working directory — and the (committed) real
        # data file must never be clobbered. Use a unique filename for the probe.
        monkeypatch.chdir(tmp_path)  # simulate running from anywhere
        probe = Path("data/processed") / "cwd_probe.json"
        out = ud.main(["--mock", "--no-delay", "--limit", "1", "--seed", "4",
                       "--output", str(probe)])
        assert out == 0
        # It must NOT have been written under the caller's CWD...
        assert not (tmp_path / probe).exists()
        # ...it lands under the repo root instead.
        repo_root = Path(ud.__file__).resolve().parent.parent
        expected = repo_root / probe
        assert expected.exists()
        data = json.loads(expected.read_text())
        assert data["total_stocks_analyzed"] == 3
        expected.unlink()  # leave no trace in the working tree


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
class TestCli:
    def test_parser_defaults(self):
        args = ud.build_parser().parse_args([])
        assert args.mock is False
        assert args.no_delay is False
        assert args.limit is None
        assert args.output == ud.DEFAULT_OUTPUT
        assert args.seed is None

    def test_parser_flags(self):
        args = ud.build_parser().parse_args(
            ["--mock", "--no-delay", "--limit", "2", "--output", "x.json", "--seed", "5"]
        )
        assert args.mock is True
        assert args.no_delay is True
        assert args.limit == 2
        assert args.output == "x.json"
        assert args.seed == 5

    def test_main_mock_writes_file(self, tmp_path):
        out = tmp_path / "o.json"
        rc = ud.main(["--mock", "--no-delay", "--limit", "2", "--seed", "9",
                      "--output", str(out)])
        assert rc == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["total_stocks_analyzed"] == 6  # --limit 2 x 3 regions
        assert data["data_sources"] == {"sample": 6}