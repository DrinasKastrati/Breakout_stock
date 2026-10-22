from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from breakout_lab.cli import main
from breakout_lab.demo import dataset
from breakout_lab.metro import METRO_STATUSES
from breakout_lab.models import Config
from breakout_lab.pages import export_site
from breakout_lab.server import Application
from breakout_lab.strategies import STRATEGIES, metro_section


class FakeStore:
    def __init__(self):
        self.data = dataset()

    def load(self):
        return self.data


class Section(unittest.TestCase):
    def test_strategy_registry(self):
        self.assertEqual([s["id"] for s in STRATEGIES], ["breakout", "metro"])

    def test_metro_section_has_rows_counts_regime(self):
        assets, histories, meta = dataset()
        section = metro_section(assets, histories, Config(), meta)
        self.assertEqual(set(section["counts"]), set(METRO_STATUSES))
        self.assertEqual(sum(section["counts"].values()), len(assets))
        self.assertEqual(section["regime"]["date"], meta["as_of"])
        self.assertIn(section["regime"]["label"], {"risk_on", "neutral", "risk_off"})
        self.assertIsNone(section["context"])

    def test_context_builder_receives_rows_and_regime(self):
        assets, histories, meta = dataset()
        seen = {}
        section = metro_section(assets, histories, Config(), meta,
                                lambda rows, regime: seen.update(n=len(rows), label=regime["label"]) or {"ok": True})
        self.assertEqual(section["context"], {"ok": True})
        self.assertEqual(seen["n"], len(assets))

    def test_context_builder_failure_does_not_raise(self):
        assets, histories, meta = dataset()
        def broken(rows, regime):
            raise RuntimeError("network down")
        self.assertIsNone(metro_section(assets, histories, Config(), meta, broken)["context"])


class Payload(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "site"
        self.assets, self.histories, self.meta = dataset()
        export_site(self.assets, self.histories, self.meta, Config(), self.output, repository="example/Breakout_stock")
        self.manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))

    def read(self, name):
        return json.loads((self.output / self.manifest[name]).read_text(encoding="utf-8"))

    def test_demo_payload_has_metro_section_and_keeps_breakout(self):
        scan = self.read("scan")
        metro = scan["strategies"]["metro"]
        self.assertEqual(set(metro["counts"]), set(METRO_STATUSES))
        self.assertEqual(len(metro["rows"]), len(scan["rows"]))
        self.assertIn("breakout", scan["counts"])

    def test_demo_backtest_payload_has_metro_variants(self):
        backtest = self.read("backtest")
        self.assertEqual(len(backtest["variants"]), 3)
        self.assertEqual([v["name"] for v in backtest["strategies"]["metro"]["variants"]], ["Metro", "Metro utan regimfilter"])


class LocalApp(unittest.TestCase):
    def setUp(self):
        self.app = Application(FakeStore(), Config())

    def test_scan_includes_metro(self):
        self.assertIn("metro", self.app.scan()["strategies"])

    def test_backtest_by_strategy(self):
        self.assertEqual(len(self.app.backtest("breakout")["variants"]), 3)
        self.assertEqual(len(self.app.backtest("metro")["variants"]), 2)
        with self.assertRaises(ValueError):
            self.app.backtest("nope")

    def test_export_rows_by_strategy(self):
        columns, rows, filename = self.app.export("metro")
        self.assertEqual(filename, "metro-scan.csv")
        self.assertIn("rr", columns)
        self.assertEqual(len(rows), len(FakeStore().data[0]))


class Cli(unittest.TestCase):
    def test_cli_scan_metro(self):
        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = str(Path(tmp) / "demo.sqlite")
            self.assertEqual(main(["--db", db, "demo"]), 0)
            self.assertEqual(main(["--db", db, "scan", "--strategy", "metro"]), 0)
            self.assertEqual(main(["--db", db, "backtest", "--strategy", "metro"]), 0)


if __name__ == "__main__":
    unittest.main()
