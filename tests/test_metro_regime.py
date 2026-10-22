from datetime import date, timedelta
import unittest

from breakout_lab.engine import eligibility
from breakout_lab.metro_regime import breadth_by_date, regime_series
from breakout_lab.models import Asset, Bar, Config, MetroConfig

CONFIG = Config()


def series(start, step, n, volume=1_000_000):
    bars = []
    for i in range(n):
        p = start + step * i
        bars.append(Bar((date(2023, 1, 2) + timedelta(days=i)).isoformat(), p, p * 1.01, p * .99, p, volume))
    return bars


def universe(rising, falling, n=60, illiquid=0):
    assets, histories = [], {}
    specs = [("U", .2)] * rising + [("D", -.2)] * falling + [("I", .2)] * illiquid
    for k, (kind, step) in enumerate(specs):
        symbol = f"{kind}{k}"
        assets.append(Asset(symbol, symbol))
        histories[symbol] = series(50 - (step * n if step < 0 else 0), step, n, 1_000 if kind == "I" else 1_000_000)
    return assets, histories


class Breadth(unittest.TestCase):
    def test_counts_above_sma50_among_eligible(self):
        assets, histories = universe(2, 2)
        last = histories["U0"][-1].date
        self.assertEqual(breadth_by_date(assets, histories, CONFIG, {}, historical=True, dates={last})[last], (2, 4))

    def test_illiquid_stock_not_in_denominator(self):
        assets, histories = universe(1, 1, illiquid=1)
        last = histories["U0"][-1].date
        self.assertEqual(breadth_by_date(assets, histories, CONFIG, {}, historical=True, dates={last})[last], (1, 2))

    def test_breadth_does_not_require_min_history(self):
        reasons, _ = eligibility(Asset("X", "X"), series(50, .1, 60), 59, CONFIG, historical=True, require_history=False)
        self.assertEqual(reasons, [])

    def test_short_series_reports_lookback(self):
        reasons, _ = eligibility(Asset("X", "X"), series(50, .1, 60), 10, CONFIG, require_history=False)
        self.assertEqual(reasons, ["Kräver 20 candles"])


class Regime(unittest.TestCase):
    def setUp(self):
        self.up = series(100, .5, 250)
        self.down = series(225, -.5, 250)
        self.day = self.up[-1].date

    def test_risk_on_needs_index_above_sma200_and_breadth_at_least_half(self):
        r = regime_series(self.up, {self.day: (2, 4)}, MetroConfig())[self.day]
        self.assertEqual(r["label"], "risk_on")
        self.assertAlmostEqual(r["breadth"], .5)
        self.assertEqual(r["eligible"], 4)

    def test_risk_off_needs_index_below_and_breadth_below_40(self):
        self.assertEqual(regime_series(self.down, {self.day: (1, 4)}, MetroConfig())[self.day]["label"], "risk_off")

    def test_mixed_is_neutral(self):
        self.assertEqual(regime_series(self.up, {self.day: (1, 4)}, MetroConfig())[self.day]["label"], "neutral")
        self.assertEqual(regime_series(self.down, {self.day: (2, 4)}, MetroConfig())[self.day]["label"], "neutral")

    def test_short_index_history_is_neutral_with_note(self):
        day = self.up[149].date
        r = regime_series(self.up[:150], {day: (4, 4)}, MetroConfig())[day]
        self.assertEqual(r["label"], "neutral")
        self.assertIn("Indexhistorik saknas", r["notes"])

    def test_no_eligible_stocks_is_neutral_with_note(self):
        r = regime_series(self.up, {}, MetroConfig())[self.day]
        self.assertEqual(r["label"], "neutral")
        self.assertIn("Inga behöriga aktier", r["notes"])


if __name__ == "__main__":
    unittest.main()
