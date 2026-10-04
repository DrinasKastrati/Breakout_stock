from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from breakout_lab.experiments import golden_states, experiment_signals, public_summary, run_suite, save
from breakout_lab.models import Asset, Bar, Config
from breakout_lab.portfolio import discover_signals, simulate_portfolio
from test_core import history
from test_portfolio import bar, signal


class ExperimentTests(unittest.TestCase):
    def test_golden_cross_needs_actual_cross_and_expires_after_twenty_bars(self):
        fast = [9] + [11] * 25
        trend, recent = golden_states(fast, [10] * len(fast))
        self.assertFalse(recent[0])
        self.assertTrue(recent[1])
        self.assertTrue(recent[20])
        self.assertFalse(recent[21])
        self.assertTrue(trend[21])
        self.assertFalse(golden_states([11]*30, [10]*30)[1][-1])

    def test_golden_cross_warmup_death_cross_and_causality(self):
        fast, slow = [None, 9, 11, 9, 11], [None, 10, 10, 10, 10]
        expected = golden_states(fast[:4], slow[:4])
        extended = golden_states(fast, slow)
        self.assertEqual(expected, tuple(x[:4] for x in extended))
        self.assertFalse(extended[1][3])
        self.assertTrue(extended[1][4])

    def test_shared_baseline_signals_equal_original_discovery(self):
        assets, bars, config = [Asset("TEST", "Test")], history(), Config()
        histories = {"TEST": bars}
        original, warm = discover_signals(assets, histories, config, bars[250].date, bars[-1].date)
        groups, got_warm = experiment_signals(assets, histories, config, bars[250].date, bars[-1].date)
        self.assertEqual(original, groups["baseline"])
        self.assertEqual(warm, got_warm)
        self.assertTrue(all(c["checks"]["macd"] for row in groups["baseline"].values() for c in row))
        self.assertTrue(set(groups["baseline"]) <= set(groups["no_macd"]))

    def test_fixed_fraction_uses_equity_reserves_fees_and_never_borrows(self):
        days = ["2024-01-01", "2024-01-02"]
        config = replace(Config(), account_equity=1000, commission_per_share=1, slippage_bps=0)
        histories = {s: [bar(d) for d in days] for s in ("A", "B", "C", "D", "E", "F")}
        result = simulate_portfolio(histories, {days[0]: [signal(s) for s in histories]}, config,
                                    days[0], days[-1], days, "fixed_fraction", position_fraction=.25)
        holdings = result["open_positions"]
        self.assertEqual(holdings[0]["shares"], 22)
        self.assertEqual(result["stats"]["cash_usd"], 10)
        self.assertEqual(sum(p["shares"] for p in holdings), 90)
        self.assertTrue(all(p["shares"] * 11 <= 250 for p in holdings))
        self.assertTrue(all(r["cash_usd"] >= 0 for r in result["equity_curve"]))
        for invalid in (None, 0, -1, 2, float("nan")):
            with self.assertRaises(ValueError):
                simulate_portfolio(histories, {}, config, days[0], days[-1], days,
                                   "fixed_fraction", position_fraction=invalid)

    def test_macd_exit_is_next_open_not_signal_close(self):
        days = ["2024-01-01", "2024-01-02", "2024-01-03"]
        h = {"A": [bar(days[0]), bar(days[1], high=11, close=11),
                    bar(days[2], opening=10.5, high=11, close=10.5)]}
        config = replace(Config(), account_equity=1000, commission_per_share=0, slippage_bps=0)
        with patch("breakout_lab.portfolio.calculate", return_value={"macd": [1, -1, -1], "signal": [0, 0, 0]}):
            result = simulate_portfolio(h, {days[0]: [signal("A")]}, config,
                                        days[0], days[-1], days, "all_in", exit_rule="macd")
        trade = result["trades"][0]
        self.assertEqual(trade["exit_date"], days[2])
        self.assertEqual(trade["exit_reason"], "macd_next_open")
        self.assertEqual(trade["exit"], 10.5)
        self.assertEqual(result["stats"]["final_usd"], 1050)

    def test_trailing_stop_cannot_use_current_close_to_stop_current_low(self):
        days = ["2024-01-01", "2024-01-02", "2024-01-03"]
        h = {"A": [bar(days[0]), bar(days[1], high=11.5, low=9.5, close=11.5),
                    bar(days[2], opening=11, high=11.5, low=10, close=11)]}
        config = replace(Config(), account_equity=1000, commission_per_share=0, slippage_bps=0)
        with patch("breakout_lab.portfolio.calculate", return_value={"atr": [.5, .5, .5]}):
            result = simulate_portfolio(h, {days[0]: [signal("A")]}, config,
                                        days[0], days[-1], days, "all_in", exit_rule="atr_trailing")
        trade = result["trades"][0]
        self.assertEqual(trade["exit_date"], days[2])
        self.assertEqual(trade["exit"], 10.5)
        self.assertEqual(trade["initial_stop"], 9)
        self.assertAlmostEqual(trade["r_multiple"], .5)

    def test_trailing_stop_never_moves_down_and_future_cannot_change_past(self):
        days = ["2024-01-01", "2024-01-02", "2024-01-03"]
        h = {"A": [bar(days[0]), bar(days[1], high=11.5, low=9.5, close=11.5),
                    bar(days[2], opening=11, high=11, low=10.6, close=10.7)]}
        config = replace(Config(), account_equity=1000, commission_per_share=0, slippage_bps=0)
        with patch("breakout_lab.portfolio.calculate", return_value={"atr": [.5, .5, .5]}):
            result = simulate_portfolio(h, {days[0]: [signal("A")]}, config,
                                        days[0], days[-1], days, "all_in", exit_rule="atr_trailing")
        self.assertEqual(result["open_positions"][0]["stop"], 10.5)

    def test_suite_has_nine_shared_variants_yearly_resets_and_no_public_fills(self):
        bars = history()
        # Two years are needed for independent yearly account windows.
        bars = [Bar((date(2023, 1, 1)+timedelta(days=i)).isoformat(),
                    b.open, b.high, b.low, b.close, b.volume) for i, b in enumerate(bars)]
        extra = [Bar((date(2023, 1, 1)+timedelta(days=300+i)).isoformat(),
                     79, 79.2, 78.8, 79, 2_000_000) for i in range(450)]
        bars += extra
        assets = [Asset("TEST", "Test"), Asset("WOLF", "Wolf"), Asset("RNA", "Rna")]
        h = {s: bars for s in ("TEST", "WOLF", "RNA", "SPY")}
        with patch("builtins.print"):
            result = run_suite(assets, h, {"as_of": bars[-1].date}, Config(), "2023-10-01", bars[-1].date)
        self.assertEqual(len(result["variants"]), 9)
        self.assertEqual(result["assets"], 1)
        public = public_summary(result)
        for row in public["variants"]:
            self.assertEqual(set(row["periods"]), {"full", "year1", "year2"})
            for period in row["periods"].values():
                self.assertEqual(period["stats"]["initial_usd"], 100_000)
                self.assertNotIn("trades", period)
                self.assertNotIn("open_positions", period)
        self.assertTrue(all("WOLF" not in str(p["trades"]) for r in result["variants"] for p in r["periods"].values()))
        with tempfile.TemporaryDirectory() as directory:
            with patch("builtins.print"):
                save(result, directory, "test-passphrase-12345")
            summary = json.loads((Path(directory)/"summary.json").read_text())
            self.assertEqual(summary, json.loads(json.dumps(public)))
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from breakout_lab.pages import derive_key
            from base64 import b64decode
            envelope = json.loads((Path(directory)/"personal-report.encrypted.json").read_text())
            key = derive_key("test-passphrase-12345", b64decode(envelope["salt"]))
            private = json.loads(AESGCM(key).decrypt(b64decode(envelope["nonce"]), b64decode(envelope["ciphertext"]), envelope["aad"].encode()))
            self.assertEqual(private, json.loads(json.dumps(result)))


if __name__ == "__main__":
    unittest.main()
