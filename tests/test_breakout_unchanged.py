import json
import unittest

from golden_breakout import GOLDEN, snapshot


def normalize(value):
    # Python 3.12 changed float sum() to compensated summation, so the last bits differ
    # from 3.11. Ten significant digits keep every real behaviour change visible.
    if isinstance(value, float):
        return float(f"{value:.10g}")
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


class BreakoutUnchanged(unittest.TestCase):
    def test_demo_scan_and_backtest_match_golden(self):
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(normalize(snapshot()), normalize(expected))

    def test_normalize_ignores_float_noise_only(self):
        self.assertEqual(normalize({"r": [0.1 + 0.2]}), normalize({"r": [0.3]}))
        self.assertNotEqual(normalize(1.0000001), normalize(1.0))


if __name__ == "__main__":
    unittest.main()
