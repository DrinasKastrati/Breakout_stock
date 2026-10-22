from datetime import date, timedelta
import unittest

from breakout_lab.models import Bar
from breakout_lab.reaction import day_reaction, reaction_day, symbol_reactions

SESSIONS = ["2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21"]


def history(last_close, last_volume, n=25):
    days = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(n)]
    bars = [Bar(d, 100, 100.5, 99.5, 100, 1000) for d in days[:-1]]
    bars.append(Bar(days[-1], 100, max(100, last_close) * 1.001, min(100, last_close) * .999, last_close, last_volume))
    return bars, {d: 50.0 for d in days}


class ReactionDay(unittest.TestCase):
    def test_before_close_is_same_session(self):
        self.assertEqual(reaction_day("2026-10-20T14:00:00Z", SESSIONS), "2026-10-20")   # 10:00 New York

    def test_after_close_is_next_session(self):
        self.assertEqual(reaction_day("2026-10-20T21:30:00Z", SESSIONS), "2026-10-21")   # 17:30 New York

    def test_weekend_goes_to_next_session(self):
        self.assertEqual(reaction_day("2026-10-17T15:00:00Z", SESSIONS), "2026-10-19")

    def test_after_last_session_is_unknown(self):
        self.assertIsNone(reaction_day("2026-10-21T21:30:00Z", SESSIONS))


class DayReaction(unittest.TestCase):
    def test_thresholds_are_inclusive(self):
        bars, index = history(102, 1500)
        r = day_reaction(bars, index, bars[-1].date)
        self.assertEqual(r["label"], "positive")
        self.assertAlmostEqual(r["excess"], .02)
        self.assertAlmostEqual(r["rvol"], 1.5)

    def test_big_move_without_volume_is_none(self):
        bars, index = history(105, 1200)
        self.assertEqual(day_reaction(bars, index, bars[-1].date)["label"], "none")

    def test_negative_reaction(self):
        bars, index = history(97, 2000)
        self.assertEqual(day_reaction(bars, index, bars[-1].date)["label"], "negative")

    def test_excess_is_relative_to_index(self):
        bars, index = history(103, 2000)
        index[bars[-1].date] = 51.0  # index +2 %, stock +3 % -> excess 1 %
        r = day_reaction(bars, index, bars[-1].date)
        self.assertAlmostEqual(r["excess"], .01)
        self.assertEqual(r["label"], "none")

    def test_missing_history_returns_none(self):
        bars, index = history(103, 2000, n=15)
        self.assertIsNone(day_reaction(bars, index, bars[-1].date))
        bars, index = history(103, 2000)
        del index[bars[-1].date]
        self.assertIsNone(day_reaction(bars, index, bars[-1].date))


class SymbolReactions(unittest.TestCase):
    def test_summary_uses_latest_clear_reaction(self):
        bars, index = history(103, 2000)
        last = bars[-1].date
        articles = [{"headline": "old", "created_at": f"{bars[-3].date}T14:00:00Z"},
                    {"headline": "new", "created_at": f"{last}T14:00:00Z"},
                    {"headline": "later", "created_at": f"{last}T22:00:00Z"}]
        r = symbol_reactions(articles, bars, index)
        self.assertEqual([a["reaction_day"] for a in r["articles"]], [bars[-3].date, last, None])
        self.assertEqual(r["articles"][0]["reaction"]["label"], "none")
        self.assertIsNone(r["articles"][2]["reaction"])
        self.assertEqual((r["summary"]["label"], r["summary"]["day"]), ("positive", last))

    def test_no_clear_reaction_summary(self):
        bars, index = history(100.5, 1000)
        r = symbol_reactions([{"headline": "x", "created_at": f"{bars[-1].date}T14:00:00Z"}], bars, index)
        self.assertEqual(r["summary"], {"label": "none"})


if __name__ == "__main__":
    unittest.main()
