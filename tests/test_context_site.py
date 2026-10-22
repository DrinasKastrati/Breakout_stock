from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from breakout_lab.demo import dataset
from breakout_lab.models import Config
from breakout_lab.pages import export_site, previous_log

PHRASE = "test-only-random-long-passphrase-493891"
LOG = [{"date": "2026-06-26", "symbol": "DEMO-A", "status": "buy"}]


class PreviousLog(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "site"
        self.assets, self.histories, meta = dataset()
        self.meta = {**meta, "synthetic": False}

    def test_reads_log_from_encrypted_snapshot(self):
        export_site(self.assets, self.histories, self.meta, Config(), self.output, PHRASE,
                    context_builder=lambda rows, regime: {"log": LOG})
        self.assertEqual(previous_log(self.output, PHRASE), (LOG, None))

    def test_no_previous_snapshot_is_silent(self):
        self.assertEqual(previous_log(self.output, PHRASE), ([], None))

    def test_unreadable_snapshot_restarts_with_note(self):
        export_site(self.assets, self.histories, self.meta, Config(), self.output, PHRASE)
        log, note = previous_log(self.output, "another-long-random-passphrase-12345")
        self.assertEqual(log, [])
        self.assertIn("Reaktionsloggen startade om", note)

    def test_demo_build_publishes_context_without_network(self):
        export_site(self.assets, self.histories, dict(self.meta, synthetic=True), Config(), self.output,
                    context_builder=lambda rows, regime: {"log": []})
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        scan = json.loads((self.output / manifest["scan"]).read_text(encoding="utf-8"))
        self.assertEqual(scan["strategies"]["metro"]["context"], {"log": []})


if __name__ == "__main__":
    unittest.main()
