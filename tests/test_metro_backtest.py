import unittest

from breakout_lab import demo
from breakout_lab.backtest import compare_metro, metro_plan, simulate_trade
from breakout_lab.metro import evaluate_metro
from breakout_lab.models import Config

from test_metro import ASSET, NEUTRAL, scenario

CONFIG = Config()


class MetroPlan(unittest.TestCase):
    def test_rejects_entry_with_low_rr(self):
        self.assertIsNone(metro_plan(10.5, {"stop": 9.0, "t1": 11.0}, CONFIG))   # 0.5 / 1.5

    def test_accepts_entry_and_targets_t1(self):
        plan = metro_plan(9.5, {"stop": 9.0, "t1": 11.0}, CONFIG)                # 1.5 / 0.5
        self.assertEqual(plan["target"], 11.0)
        self.assertGreater(plan["shares"], 0)

    def test_rejects_entry_at_or_below_stop_and_missing_target(self):
        self.assertIsNone(metro_plan(9.0, {"stop": 9.0, "t1": 11.0}, CONFIG))
        self.assertIsNone(metro_plan(9.5, {"stop": 9.0, "t1": None}, CONFIG))


class MetroTrades(unittest.TestCase):
    def test_metro_trade_exits_at_t1(self):
        bars = scenario(91.5, extra=[(290, 92), (310, 100)])
        candidate = evaluate_metro(ASSET, bars[:282], CONFIG, regime=NEUTRAL)
        self.assertEqual(candidate["status"], "buy")
        trade = simulate_trade(bars, 281, candidate, CONFIG, plan=metro_plan)
        self.assertEqual(trade["exit_reason"], "target")
        self.assertAlmostEqual(trade["exit"], candidate["t1"] * (1 - CONFIG.slippage_bps / 10_000))

    def test_compare_metro_has_two_named_variants_and_says_not_evidence(self):
        assets, histories, meta = demo.dataset()
        variants = compare_metro(assets, histories, CONFIG, benchmark_symbol=meta["benchmark_symbol"])
        self.assertEqual([v["name"] for v in variants], ["Metro", "Metro utan regimfilter"])
        for v in variants:
            self.assertTrue(any(t.startswith("Visning, inte bevis") for t in v["limitations"]))
            self.assertEqual(set(v["summary"]), {"trades", "win_rate", "expectancy_r", "profit_factor_r", "total_r"})


if __name__ == "__main__":
    unittest.main()
