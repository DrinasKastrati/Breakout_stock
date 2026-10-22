from dataclasses import replace
from datetime import date, timedelta
import unittest

from breakout_lab.indicators import calculate
from breakout_lab.metro import METRO_STATUSES, evaluate_metro, scan_metro
from breakout_lab.models import Asset, Bar, Config

CONFIG = Config()
ASSET = Asset("AAA", "Alpha")
NEUTRAL = {"label": "neutral", "notes": []}
RISK_OFF = {"label": "risk_off", "notes": []}
# Rising zigzag: highs 60/70/80/90, rising lows 56/65/74/84, then a run toward the 90 high.
UPTREND = [(0, 50), (40, 60), (60, 56), (100, 70), (120, 65), (160, 80), (180, 74), (220, 90), (240, 84), (280, 89.5)]


def zigzag(points, length):
    closes = []
    for (i0, p0), (i1, p1) in zip(points, points[1:]):
        for i in range(i0, i1):
            closes.append(p0 + (p1 - p0) * (i - i0) / (i1 - i0))
    closes.append(points[-1][1])
    closes += [points[-1][1]] * (length - len(closes))
    return [Bar((date(2023, 1, 2) + timedelta(days=i)).isoformat(), c, c * 1.002, c * .998, c, 2_000_000)
            for i, c in enumerate(closes[:length])]


def scenario(last_close, extra=()):
    return zigzag(UPTREND + [(281, last_close), *extra], 282 + (extra[-1][0] - 281 if extra else 0))


class MetroStatus(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(METRO_STATUSES, ("buy", "watch", "sell", "wait", "excluded"))

    def test_buy_on_close_above_trigger_with_rr_at_least_two(self):
        r = evaluate_metro(ASSET, scenario(91.5), CONFIG, regime=NEUTRAL)
        self.assertEqual(r["status"], "buy", r["reasons"])
        self.assertEqual(r["reasons"], ["Samtliga Metro-villkor uppfyllda"])
        self.assertEqual(r["trend"], "bullish")
        self.assertFalse(r["checks"]["bearish_trigger"])
        self.assertTrue(r["checks"]["trigger"] and r["checks"]["rr_ok"] and r["checks"]["regime_ok"])
        self.assertGreaterEqual(r["rr"], 2)
        self.assertAlmostEqual(r["target"], r["t1"])

    def test_measured_move_target_when_r2_missing(self):
        r = evaluate_metro(ASSET, scenario(91.5), CONFIG, regime=NEUTRAL)
        self.assertIsNone(r["r2"])
        self.assertAlmostEqual(r["t1"], r["r1"] + (r["r1"] - r["s1"]))
        self.assertAlmostEqual(r["t2"], r["r1"] + 2 * (r["r1"] - r["s1"]))
        self.assertAlmostEqual(r["stop"], r["r1"] - r["atr"])

    def test_low_rr_becomes_watch_with_reason(self):
        r = evaluate_metro(ASSET, scenario(93), CONFIG, regime=NEUTRAL)
        self.assertEqual(r["status"], "watch")
        self.assertTrue(any(x.startswith("R/R ") and x.endswith("under kravet 2") for x in r["reasons"]), r["reasons"])

    def test_risk_off_downgrades_buy_to_watch(self):
        r = evaluate_metro(ASSET, scenario(91.5), CONFIG, regime=RISK_OFF)
        self.assertEqual(r["status"], "watch")
        self.assertIn("Risk-off: köpsignal nedgraderad", r["reasons"])

    def test_risk_off_ignored_when_use_regime_false(self):
        config = replace(CONFIG, metro=replace(CONFIG.metro, use_regime=False))
        self.assertEqual(evaluate_metro(ASSET, scenario(91.5), config, regime=RISK_OFF)["status"], "buy")

    def test_close_just_below_resistance_is_watch(self):
        self.assertEqual(evaluate_metro(ASSET, scenario(90.0), CONFIG, regime=NEUTRAL)["status"], "watch")

    def test_close_inside_range_is_wait(self):
        r = evaluate_metro(ASSET, scenario(88.5), CONFIG, regime=NEUTRAL)
        self.assertEqual(r["status"], "wait")
        self.assertIn("Inom intervallet: avvakta bekräftelse", r["reasons"])

    def test_close_below_support_is_sell(self):
        r = evaluate_metro(ASSET, scenario(83.0), CONFIG, regime=NEUTRAL)
        self.assertEqual(r["status"], "sell")
        self.assertIn("Stängning under stöd: sälj om du äger, undvik annars", r["reasons"])
        self.assertAlmostEqual(r["bear_t1"], r["s2"])

    def test_support_break_is_sell_even_when_resistance_is_near(self):
        bars = zigzag(UPTREND[:-2] + [(240, 88.5), (280, 89.5), (281, 88.0)], 282)
        config = replace(CONFIG, metro=replace(CONFIG.metro, watch_distance_atr=7.0))
        r = evaluate_metro(ASSET, bars, config, regime=NEUTRAL)
        self.assertTrue(r["checks"]["bearish_trigger"])
        self.assertGreaterEqual(r["close"], r["r1"] - 7.0 * r["atr"])
        self.assertEqual(r["status"], "sell")

    def test_untriggered_rr_is_planned_at_trigger(self):
        r = evaluate_metro(ASSET, scenario(90.0), CONFIG, regime=NEUTRAL)
        self.assertEqual(r["status"], "watch")
        self.assertAlmostEqual(r["rr"], (r["t1"] - r["trigger"]) / (r["trigger"] - r["stop"]))

    def test_all_time_high_without_resistance_is_wait(self):
        bars = zigzag(UPTREND[:-1] + [(280, 95), (281, 96)], 282)
        r = evaluate_metro(ASSET, bars, CONFIG, regime=NEUTRAL)
        self.assertEqual(r["status"], "wait")
        self.assertIn("Motståndsnivå saknas", r["reasons"])

    def test_missing_regime_is_neutral_with_warning(self):
        r = evaluate_metro(ASSET, scenario(91.5), CONFIG)
        self.assertEqual((r["status"], r["regime"]), ("buy", "neutral"))
        self.assertIn("Marknadsläge saknas", r["warnings"])

    def test_short_history_is_excluded(self):
        self.assertEqual(evaluate_metro(ASSET, scenario(91.5)[:200], CONFIG, regime=NEUTRAL)["status"], "excluded")

    def test_future_bars_do_not_change_result_at_t(self):
        bars = scenario(91.5, extra=[(300, 70), (320, 99)])
        a = evaluate_metro(ASSET, bars[:282], CONFIG, regime=NEUTRAL)
        b = evaluate_metro(ASSET, bars, CONFIG, index=281, indicators=calculate(bars), regime=NEUTRAL)
        for k in ("status", "r1", "s1", "t1", "stop", "rr", "trend"):
            self.assertEqual(a[k], b[k], k)

    def test_chart_levels_only_existing_levels(self):
        r = evaluate_metro(ASSET, scenario(91.5), CONFIG, regime=NEUTRAL)
        kinds = [lv["kind"] for lv in r["chart_levels"]]
        self.assertEqual(kinds, ["s2", "s1", "r1", "t1", "t2", "stop"])
        self.assertTrue(all(isinstance(lv["price"], float) and lv["label"] for lv in r["chart_levels"]))


class MetroScan(unittest.TestCase):
    def test_scan_sorting_and_missing_session(self):
        assets = [Asset("WAIT", "w"), Asset("BUY", "b"), Asset("OLD", "o"), Asset("SELL", "s")]
        histories = {"WAIT": scenario(88.5), "BUY": scenario(91.5), "OLD": scenario(91.5)[:-1], "SELL": scenario(83.0)}
        as_of = histories["BUY"][-1].date
        rows = scan_metro(assets, histories, CONFIG, {as_of: NEUTRAL}, as_of)
        self.assertEqual([r["symbol"] for r in rows], ["BUY", "SELL", "WAIT", "OLD"])
        self.assertEqual(rows[-1]["reasons"], ["Senaste avslutade handelssessionen saknas"])


if __name__ == "__main__":
    unittest.main()
