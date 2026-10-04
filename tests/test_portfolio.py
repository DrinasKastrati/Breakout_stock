from dataclasses import replace
import unittest

from breakout_lab.models import Bar, Config
from breakout_lab.portfolio import simulate_portfolio, benchmark, discover_signals, phase_attribution, attribution_names


def signal(symbol, day="2024-01-01", stop=9, volume=2):
    return {"symbol": symbol, "date": day, "stop": stop,
            "resistance": 10, "atr": 2, "score": 100,
            "relative_volume": volume, "extension_atr": .2}


def bar(day, opening=10, high=10.5, low=9.5, close=10):
    return Bar(day, opening, high, low, close, 1_000_000)


class PortfolioExecution(unittest.TestCase):
    def setUp(self):
        self.days = ["2024-01-01", "2024-01-02", "2024-01-03"]
        self.config = replace(Config(), account_equity=1000, risk_fraction=.02,
                              max_position_fraction=1, max_holding_bars=3,
                              slippage_bps=0, commission_per_share=0)

    def run_sim(self, histories, signals, config=None, end=None):
        return simulate_portfolio(histories, signals, config or self.config,
                                  self.days[0], end or self.days[-1], self.days)

    def test_entry_next_session_and_terminal_mark_without_liquidation(self):
        r = self.run_sim({"A": [bar(self.days[1]), bar(self.days[2], close=10.2)]},
                         {self.days[0]: [signal("A")]})
        self.assertEqual(r["open_positions"][0]["entry_date"], self.days[1])
        self.assertEqual(r["stats"]["closed_trades"], 0)
        self.assertAlmostEqual(r["stats"]["final_usd"], 1004)
        self.assertEqual(r["stats"]["open_positions"], 1)

    def test_global_cash_cap_not_independent_accounts(self):
        names = [str(i) for i in range(7)]
        r = self.run_sim({s: [bar(d) for d in self.days] for s in names},
                         {self.days[0]: [signal(s) for s in names]})
        self.assertEqual(r["stats"]["max_positions"], 5)
        self.assertEqual(sum(p["shares"] for p in r["open_positions"]), 100)
        self.assertEqual(r["stats"]["skipped"]["cash_or_size"], 2)
        self.assertTrue(all(v["cash_usd"] >= 0 for v in r["equity_curve"]))

    def test_ranking_uses_signal_volume_not_future_profit(self):
        r = self.run_sim({s: [bar(d, high=10.005, low=9.995) for d in self.days] for s in ["A", "Z"]},
                         {self.days[0]: [signal("A", stop=9.99, volume=2), signal("Z", stop=9.99, volume=3)]})
        self.assertEqual([p["symbol"] for p in r["open_positions"]], ["Z"])

    def test_stop_wins_when_both_reached(self):
        r = self.run_sim({"A": [bar(self.days[1], high=13, low=8)]},
                         {self.days[0]: [signal("A")]})
        self.assertEqual(r["trades"][0]["exit_reason"], "stop")
        self.assertEqual(r["trades"][0]["exit"], 9)
        self.assertEqual(r["stats"]["net_profit_usd"], -20)

    def test_opening_gap_proceeds_can_fund_new_opening(self):
        h = {"A": [bar(self.days[1], high=10.005, low=9.995),
                    bar(self.days[2], opening=9, high=9.1, low=8.9, close=9)],
             "B": [bar(self.days[2], high=10.005, low=9.995)]}
        r = self.run_sim(h, {self.days[0]: [signal("A", stop=9.99)],
                             self.days[1]: [signal("B", self.days[1], stop=9.99)]})
        self.assertEqual(r["trades"][0]["exit_reason"], "stop_gap")
        self.assertEqual(r["open_positions"][0]["symbol"], "B")
        self.assertEqual(r["open_positions"][0]["shares"], 90)
        self.assertAlmostEqual(r["stats"]["final_usd"], 900)

    def test_intraday_proceeds_cannot_fund_earlier_opening(self):
        h = {"A": [bar(self.days[1], high=10.005, low=9.995),
                    bar(self.days[2], low=9)], "B": [bar(self.days[2])]}
        r = self.run_sim(h, {self.days[0]: [signal("A", stop=9.99)],
                             self.days[1]: [signal("B", self.days[1])]})
        self.assertEqual(len(r["open_positions"]), 0)
        self.assertEqual(r["stats"]["skipped"]["cash_or_size"], 1)

    def test_time_exit_counts_entry_bar(self):
        r = self.run_sim({"A": [bar(d) for d in self.days]},
                         {self.days[0]: [signal("A")]},
                         replace(self.config, max_holding_bars=2))
        self.assertEqual(r["trades"][0]["exit_date"], self.days[2])
        self.assertEqual(r["trades"][0]["exit_reason"], "time")

    def test_fees_and_slippage_are_in_cash_and_pnl(self):
        r = self.run_sim({"A": [bar(d) for d in self.days]},
                         {self.days[0]: [signal("A")]},
                         replace(self.config, max_holding_bars=2, slippage_bps=10, commission_per_share=.005))
        t = r["trades"][0]
        expected = t["shares"] * ((10 * .999) - (10 * 1.001) - .01)
        self.assertAlmostEqual(r["stats"]["net_profit_usd"], expected)
        self.assertAlmostEqual(t["pnl_usd"], expected)
        self.assertGreater(r["stats"]["commission_usd"], 0)
        self.assertGreater(r["stats"]["slippage_usd"], 0)

    def test_gap_above_extension_is_skipped(self):
        r = self.run_sim({"A": [bar(self.days[1], opening=15, high=16, low=14, close=15)]},
                         {self.days[0]: [signal("A")]})
        self.assertEqual(r["stats"]["skipped"]["entry_gap"], 1)
        self.assertEqual(r["stats"]["final_usd"], 1000)

    def test_missing_next_bar_not_deferred_until_resumption(self):
        r = self.run_sim({"A": [bar(self.days[2])]}, {self.days[0]: [signal("A")]})
        self.assertEqual(r["stats"]["skipped"]["missing_next_session"], 1)
        self.assertEqual(r["stats"]["open_positions"], 0)

    def test_same_symbol_cannot_be_held_twice(self):
        r = self.run_sim({"A": [bar(d) for d in self.days]},
                         {self.days[0]: [signal("A")], self.days[1]: [signal("A", self.days[1])]})
        self.assertEqual(r["stats"]["skipped"]["already_held"], 1)
        self.assertEqual(r["stats"]["max_positions"], 1)

    def test_future_cannot_change_historical_result(self):
        h = {"A": [bar(d) for d in self.days]}
        sig = {self.days[0]: [signal("A")]}
        original = self.run_sim(h, sig, end=self.days[1])
        h["A"][-1] = bar(self.days[2], opening=100, high=101, low=99, close=100)
        self.assertEqual(original, self.run_sim(h, sig, end=self.days[1]))

    def test_benchmark_costs_and_whole_shares(self):
        r = benchmark([bar(d) for d in self.days], replace(self.config, commission_per_share=.01),
                      self.days[0], self.days[-1])
        self.assertAlmostEqual(r["final_usd"], 999.01)

    def test_metadata_filters_not_allowed(self):
        with self.assertRaises(ValueError):
            discover_signals([], {}, replace(self.config, min_market_cap=1), *self.days[::2])

    def test_all_in_uses_full_cash_instead_of_risk_and_position_caps(self):
        config = replace(self.config, risk_fraction=.005, max_position_fraction=.15)
        r = simulate_portfolio({"A": [bar(d) for d in self.days]},
                               {self.days[0]: [signal("A")]}, config,
                               self.days[0], self.days[-1], self.days, "all_in")
        self.assertEqual(r["open_positions"][0]["shares"], 100)
        self.assertEqual(r["stats"]["cash_usd"], 0)
        self.assertEqual(r["stats"]["max_positions"], 1)

    def test_all_in_ranking_and_one_position_even_with_cash_left(self):
        histories = {"A": [bar(d, opening=600, high=601, low=599, close=600) for d in self.days],
                     "B": [bar(d) for d in self.days]}
        a = dict(signal("A", stop=590, volume=3), resistance=600, atr=20)
        r = simulate_portfolio(histories, {self.days[0]: [signal("B"), a]}, self.config,
                               self.days[0], self.days[-1], self.days, "all_in")
        self.assertEqual([p["symbol"] for p in r["open_positions"]], ["A"])
        self.assertEqual(r["stats"]["cash_usd"], 400)
        self.assertEqual(r["stats"]["skipped"]["portfolio_occupied"], 1)

    def test_all_in_reinvests_net_proceeds_after_exit(self):
        histories = {"A": [bar(self.days[1], high=11.5, close=11)],
                     "B": [bar(self.days[2])]}
        config = replace(self.config, max_holding_bars=1)
        signals = {self.days[0]: [signal("A")], self.days[1]: [signal("B", self.days[1])]}
        r = simulate_portfolio(histories, signals, config,
                               self.days[0], self.days[-1], self.days, "all_in")
        self.assertEqual([t["shares"] for t in r["trades"]], [100, 110])
        self.assertEqual(r["stats"]["final_usd"], 1100)

    def test_all_in_reserves_commission_and_accounts_for_slippage(self):
        config = replace(self.config, commission_per_share=.005, slippage_bps=10)
        r = simulate_portfolio({"A": [bar(d) for d in self.days]},
                               {self.days[0]: [signal("A")]}, config,
                               self.days[0], self.days[-1], self.days, "all_in")
        self.assertEqual(r["open_positions"][0]["shares"], 99)
        self.assertTrue(all(v["cash_usd"] >= 0 for v in r["equity_curve"]))
        self.assertAlmostEqual(r["stats"]["final_usd"], 1000 - 99 * .015)

    def test_all_in_skips_invalid_top_signal_then_buys_next(self):
        histories = {"A": [bar(self.days[1], opening=15, high=16, low=14, close=15)],
                     "B": [bar(self.days[1]), bar(self.days[2])]}
        r = simulate_portfolio(histories, {self.days[0]: [signal("A", volume=3), signal("B")]},
                               self.config, self.days[0], self.days[-1], self.days, "all_in")
        self.assertEqual(r["stats"]["skipped"]["entry_gap"], 1)
        self.assertEqual(r["open_positions"][0]["symbol"], "B")
        self.assertEqual(r["open_positions"][0]["shares"], 100)


class AttributionTests(unittest.TestCase):
    def test_trade_spanning_peak_and_trough_uses_endpoint_marks(self):
        histories = {"A": [bar("2024-01-01", high=15, close=15),
                           bar("2024-01-02", low=6, close=6),
                           bar("2024-01-03", high=12, close=12)]}
        result = {"stats": {"initial_usd": 100},
                  "equity_curve": [{"date": "2024-01-01", "equity_usd": 149},
                                   {"date": "2024-01-02", "equity_usd": 59},
                                   {"date": "2024-01-03", "equity_usd": 118}],
                  "trades": [{"symbol": "A", "entry_date": "2024-01-01", "entry": 10,
                              "shares": 10, "entry_fee": 1, "exit_date": "2024-01-03", "pnl_usd": 18}],
                  "open_positions": []}
        a = phase_attribution(result, histories)
        self.assertEqual(a["decline"]["contributors"], [{"symbol": "A", "change_usd": -90}])
        self.assertEqual(a["recovery"]["contributors"], [{"symbol": "A", "change_usd": 59}])
        public = attribution_names(a)
        self.assertEqual(public["decline"]["symbols_by_contribution"], ["A"])
        self.assertNotIn("contributors", public["decline"])

    def test_new_trade_costs_and_terminal_open_position_are_in_recovery(self):
        histories = {"A": [bar("2024-01-01", close=10), bar("2024-01-02", low=5, close=5)],
                     "B": [bar("2024-01-03", high=12, close=12)]}
        result = {"stats": {"initial_usd": 100},
                  "equity_curve": [{"date": "2024-01-01", "equity_usd": 100},
                                   {"date": "2024-01-02", "equity_usd": 50},
                                   {"date": "2024-01-03", "equity_usd": 59}],
                  "trades": [{"symbol": "A", "entry_date": "2024-01-01", "entry": 10,
                              "shares": 10, "entry_fee": 0, "exit_date": "2024-01-02", "pnl_usd": -50}],
                  "open_positions": [{"symbol": "B", "entry_date": "2024-01-03", "entry": 10,
                                      "shares": 5, "entry_fee": 1}]}
        a = phase_attribution(result, histories)
        self.assertEqual(a["recovery"]["contributors"], [{"symbol": "B", "change_usd": 9}])
        self.assertEqual(attribution_names(a)["recovery"]["symbols_by_contribution"], ["B"])


if __name__ == "__main__":
    unittest.main()
