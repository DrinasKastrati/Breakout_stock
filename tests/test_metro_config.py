from dataclasses import asdict, replace
from pathlib import Path
import json
import unittest

from breakout_lab.models import Config, MetroConfig
from breakout_lab.server import Application

ROOT = Path(__file__).resolve().parents[1]


class MetroSettings(unittest.TestCase):
    def test_missing_metro_block_uses_defaults(self):
        c = Config.from_dict({"lookback": 20})
        self.assertEqual(c.metro, MetroConfig())
        self.assertEqual(c.metro.min_rr, 2.0)
        self.assertEqual(c.metro.pivot_span, 5)

    def test_repo_config_loads_and_roundtrips(self):
        c = Config.from_dict(json.loads((ROOT / "config.json").read_text(encoding="utf-8")))
        self.assertEqual(Config.from_dict(c.to_dict()), c)
        self.assertIsInstance(c.to_dict()["metro"], dict)
        self.assertEqual(c.metro, MetroConfig())

    def test_unknown_metro_key_rejected(self):
        with self.assertRaises(ValueError):
            Config.from_dict({"metro": {"bogus": 1}})

    def test_invalid_breadth_order_rejected(self):
        with self.assertRaises(ValueError):
            Config.from_dict({"metro": {"breadth_risk_on": 0.3, "breadth_risk_off": 0.4}})

    def test_invalid_types_rejected(self):
        for bad in ({"pivot_span": 0}, {"pivot_span": 2.5}, {"use_regime": 1}, {"min_rr": 0},
                    {"stop_atr": float("nan")}, {"level_lookback": 10}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Config.from_dict({"metro": bad})

    def test_replace_keeps_metro(self):
        c = Config.from_dict({"metro": {"min_rr": 3.0}})
        self.assertEqual(replace(c, account_equity=5).metro.min_rr, 3.0)

    def test_server_update_preserves_metro(self):
        app = Application(store=None, config=Config.from_dict({"metro": {"min_rr": 3.0}}))
        self.assertEqual(app.update_config({"min_price": 6}).metro.min_rr, 3.0)
        self.assertEqual(app.update_config({"metro": {**asdict(MetroConfig()), "min_rr": 2.5}}).metro.min_rr, 2.5)


if __name__ == "__main__":
    unittest.main()
