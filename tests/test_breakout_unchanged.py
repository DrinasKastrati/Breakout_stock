import json
import unittest

from golden_breakout import GOLDEN, snapshot


class BreakoutUnchanged(unittest.TestCase):
    def test_demo_scan_and_backtest_match_golden(self):
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(snapshot(), expected)


if __name__ == "__main__":
    unittest.main()
