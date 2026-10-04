from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import shutil
import subprocess
import unittest

from breakout_lab.demo import dataset
from breakout_lab.engine import scan
from breakout_lab.models import Config
from breakout_lab.pages import build_site, decrypt_file, export_site
from breakout_lab.providers import Alpaca, NY

PHRASE = "test-only-random-long-passphrase-493891"


class Pages(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "site"
        self.assets, self.histories, self.meta = dataset()

    def export(self, **kwargs):
        return export_site(self.assets, self.histories, self.meta, Config(), self.output,
                           repository="example/Breakout_stock", **kwargs)

    def test_demo_snapshot_matches_engine_and_all_links_exist(self):
        result = self.export()
        manifest = json.loads((self.output / "manifest.json").read_text())
        data = json.loads((self.output / manifest["scan"]).read_text())
        benchmark = {b.date:b.close for b in self.histories[self.meta["benchmark_symbol"]]}
        self.assertEqual(data["rows"], scan(self.assets, self.histories, Config(), benchmark, self.meta["as_of"]))
        for name in data["chart_ids"].values():
            chart = json.loads((self.output / (manifest["prefix"] + name + manifest["suffix"])).read_text())
            self.assertEqual(len(chart["bars"]), 100)
            self.assertEqual(len(chart["indicators"]["macd"]), 100)
        backtest = json.loads((self.output / manifest["backtest"]).read_text())
        self.assertEqual(len(backtest["variants"]), 3)
        self.assertTrue(result["changed"])
        html = (self.output / "index.html").read_text()
        self.assertIn('name="breakout-mode" content="static"', html)
        self.assertIn('href="./style.css"', html)
        self.assertIn('src="./data-client.js"', html)
        self.assertNotIn('src="/app.js"', html)

    def test_unchanged_snapshot_does_not_redeploy(self):
        self.export()
        before = (self.output / "manifest.json").read_bytes()
        result = self.export()
        self.assertFalse(result["changed"])
        self.assertEqual((self.output / "manifest.json").read_bytes(), before)

    def test_real_data_never_exports_without_encryption(self):
        self.meta = {**self.meta, "source":"alpaca", "synthetic":False}
        for phrase in (None, "short"):
            with self.assertRaises(ValueError):
                self.export(passphrase=phrase)
        self.assertFalse(self.output.exists())

    def test_real_snapshot_has_only_encrypted_market_payloads(self):
        self.meta = {**self.meta, "source":"alpaca", "synthetic":False}
        self.export(passphrase=PHRASE)
        manifest = json.loads((self.output / "manifest.json").read_text())
        scan_data = decrypt_file(self.output, manifest, manifest["scan"], PHRASE)
        self.assertEqual(len(scan_data["rows"]), 8)
        self.assertEqual(manifest["mode"], "encrypted")
        for path in (self.output / "data").rglob("*"):
            if path.is_file():
                self.assertEqual(path.suffix, ".bin")
                self.assertNotIn(b'"close":', path.read_bytes())
                self.assertNotIn(PHRASE.encode(), path.read_bytes())
        from cryptography.exceptions import InvalidTag
        with self.assertRaises(InvalidTag):
            decrypt_file(self.output, manifest, manifest["scan"], PHRASE + "wrong")
        chart_path = manifest["prefix"] + next(iter(scan_data["chart_ids"].values())) + ".bin"
        with self.assertRaises(InvalidTag):
            # A file cannot be substituted for another path: AAD binds its identity.
            raw = (self.output / manifest["scan"]).read_bytes()
            (self.output / chart_path).write_bytes(raw)
            decrypt_file(self.output, manifest, chart_path, PHRASE)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for Python/WebCrypto interoperability")
    def test_browser_webcrypto_decrypts_python_snapshot(self):
        self.meta = {**self.meta, "synthetic":False}
        self.export(passphrase=PHRASE)
        script = Path(__file__).with_name("webcrypto.cjs")
        result = subprocess.run(["node", str(script), str(self.output), PHRASE], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), {"rows":8, "wrong_passphrase_rejected":True, "tamper_rejected":True})

    def test_failed_build_keeps_last_good_site(self):
        self.export()
        before = (self.output / "manifest.json").read_bytes()
        self.meta = {**self.meta, "synthetic":False}
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual((self.output / "manifest.json").read_bytes(), before)

    def test_real_to_demo_fallback_is_rejected(self):
        self.meta = {**self.meta, "source":"alpaca", "synthetic":False}
        self.export(passphrase=PHRASE)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            build_site(Config(), self.output, "auto")
        self.assertEqual(json.loads((self.output / "manifest.json").read_text())["mode"], "encrypted")

    def test_passphrase_rotation_changes_version(self):
        self.meta = {**self.meta, "synthetic":False}
        first = self.export(passphrase=PHRASE)
        second = self.export(passphrase=PHRASE + "rotated")
        self.assertTrue(second["changed"])
        self.assertNotEqual(first["version"], second["version"])
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(len(decrypt_file(self.output, manifest, manifest["scan"], PHRASE + "rotated")["rows"]), 8)

    def test_incomplete_real_session_does_not_replace_demo(self):
        self.export()
        before = (self.output / "manifest.json").read_bytes()
        real = {**self.meta, "source":"alpaca", "synthetic":False, "as_of":"2026-06-30"}
        env = {"ALPACA_API_KEY":"test", "ALPACA_API_SECRET":"test", "DASHBOARD_PASSPHRASE":PHRASE}
        with patch.dict(os.environ, env), patch.object(Alpaca, "dataset", return_value=(self.assets, self.histories, real)):
            with self.assertRaises(ValueError):
                build_site(Config(), self.output, "alpaca")
        self.assertEqual((self.output / "manifest.json").read_bytes(), before)

    def test_bars_end_is_old_enough_for_free_sip_even_before_midnight(self):
        with patch.dict(os.environ, {"ALPACA_API_KEY":"test", "ALPACA_API_SECRET":"test"}):
            client = Alpaca()
        calls = []
        client.get = lambda host,route,params: calls.append(params) or {"bars":{}}
        now = datetime(2026,7,2,20,37,tzinfo=NY)
        client.bars(["AAA"], "2026-01-01", "2026-07-02", now)
        end = datetime.fromisoformat(calls[0]["end"])
        self.assertLessEqual(end, now - timedelta(minutes=16))
        self.assertEqual(end.astimezone(NY).date().isoformat(), "2026-07-02")
        self.assertEqual(calls[0]["feed"], "sip")
        client.bars(["AAA"], "2026-01-01", "2026-07-01", now)
        self.assertEqual(datetime.fromisoformat(calls[-1]["end"]).astimezone(NY).hour, 21)

    def test_successful_real_build_reuses_session_and_force_checks_again(self):
        self.histories["SPY"] = self.histories[self.meta["benchmark_symbol"]]
        real = {**self.meta, "source":"alpaca", "synthetic":False, "benchmark_symbol":"SPY"}
        env = {"ALPACA_API_KEY":"test", "ALPACA_API_SECRET":"test", "DASHBOARD_PASSPHRASE":PHRASE}
        with patch.dict(os.environ, env), patch.object(Alpaca, "dataset", return_value=(self.assets,self.histories,real)) as provider:
            with patch.object(Alpaca, "completed_session", return_value=real["as_of"]):
                first = build_site(Config(), self.output, "alpaca")
                second = build_site(Config(), self.output, "alpaca")
                self.assertTrue(first["changed"])
                self.assertFalse(second["changed"])
                self.assertEqual(provider.call_count, 1)
                forced = build_site(Config(), self.output, "alpaca", force=True)
                self.assertFalse(forced["changed"])
                self.assertEqual(provider.call_count, 2)

    def test_snapshot_path_cannot_escape_output_directory(self):
        with self.assertRaises(ValueError):
            decrypt_file(self.output, {}, "../../config.json", PHRASE)

    def test_authenticated_retry_remains_within_basic_request_rate(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{}'
        waits = []
        with patch.dict(os.environ, {"ALPACA_API_KEY":"test", "ALPACA_API_SECRET":"test"}):
            client = Alpaca(opener=lambda *a,**k: Response(), sleeper=waits.append)
            client.get("https://data.alpaca.markets", "/v2/stocks/bars", {})
        self.assertEqual(waits, [0.35])


if __name__ == "__main__":
    unittest.main()
