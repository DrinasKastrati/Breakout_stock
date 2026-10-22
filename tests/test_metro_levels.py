from datetime import date, timedelta
import random
import unittest

from breakout_lab.indicators import calculate
from breakout_lab.metro_levels import cluster_levels, find_pivots, known_pivots, nearest_levels
from breakout_lab.models import Bar


def bars_from_highs(highs):
    return [Bar((date(2024, 1, 1) + timedelta(days=i)).isoformat(), h, h, h - .5, h - .25, 1000)
            for i, h in enumerate(highs)]


def random_walk(n, seed=7):
    rng, p, bars = random.Random(seed), 50.0, []
    for i in range(n):
        o = p
        p *= 1 + rng.gauss(0, .02)
        bars.append(Bar((date(2024, 1, 1) + timedelta(days=i)).isoformat(), o, max(o, p) * 1.01, min(o, p) * .99, p, 1000))
    return bars


class Pivots(unittest.TestCase):
    def test_pivot_is_known_only_after_span(self):
        p = find_pivots(bars_from_highs([1, 2, 3, 9, 3, 2, 1, 1]), 2)
        self.assertIn((3, "high", 9), p)
        self.assertEqual([x for x in known_pivots(p, t=5, span=2, lookback=250) if x[0] == 3], [])
        self.assertIn((3, "high", 9), known_pivots(p, t=6, span=2, lookback=250))

    def test_equal_highs_are_not_pivots(self):
        p = find_pivots(bars_from_highs([1, 2, 9, 3, 9, 2, 1]), 2)
        self.assertEqual([x for x in p if x[1] == "high"], [])

    def test_lookback_drops_old_pivots(self):
        p = [(10, "high", 5.0), (100, "low", 4.0)]
        self.assertEqual(known_pivots(p, t=120, span=5, lookback=50), [(100, "low", 4.0)])

    def test_future_bars_do_not_change_known_pivots(self):
        bars = random_walk(260)
        self.assertEqual(known_pivots(find_pivots(bars[:200], 5), 199, 5, 250),
                         known_pivots(find_pivots(bars, 5), 199, 5, 250))


class Levels(unittest.TestCase):
    def test_cluster_is_anchored_not_chained(self):
        levels = cluster_levels([10.0, 10.3, 10.6, 12.0], 0.5)
        self.assertEqual([lv["touches"] for lv in levels], [2, 1, 1])
        for got, want in zip([lv["price"] for lv in levels], [10.15, 10.6, 12.0]):
            self.assertAlmostEqual(got, want)

    def test_cluster_sorts_input(self):
        self.assertEqual([lv["touches"] for lv in cluster_levels([12.0, 10.3, 10.0], 0.5)], [2, 1])

    def test_nearest_levels(self):
        lv = [{"price": p, "touches": 1} for p in (8, 9, 11, 12, 13)]
        self.assertEqual(nearest_levels(lv, 10), {"r1": 11, "r2": 12, "r3": 13, "s1": 9, "s2": 8})
        self.assertEqual(nearest_levels(lv, 14), {"r1": None, "r2": None, "r3": None, "s1": 13, "s2": 12})
        self.assertEqual(nearest_levels(lv, 11)["r1"], 12)  # strictly above


class Sma200(unittest.TestCase):
    def test_sma200_causal(self):
        bars = random_walk(260)
        self.assertIsNone(calculate(bars)["sma200"][198])
        self.assertEqual(calculate(bars[:220])["sma200"], calculate(bars)["sma200"][:220])


if __name__ == "__main__":
    unittest.main()
