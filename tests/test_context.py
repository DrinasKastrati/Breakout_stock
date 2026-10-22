from datetime import date, timedelta
from unittest.mock import patch
from urllib.error import URLError
import io
import unittest

from breakout_lab.context import build_context, merge_log, scout_narrative, shortlist
from breakout_lab.models import Bar, MetroConfig
from breakout_lab.providers import Alpaca

AS_OF = "2026-10-21"
REPORT = "# Scout\n\nIntro\n\n## Marknadsöversikt\nS&P 500 steg.\nFed höll räntan.\n\n## Case\nNVDA\n"


def row(symbol, status, rr=None, trigger=False):
    return {"symbol": symbol, "status": status, "rr": rr, "checks": {"trigger": trigger}}


ROWS = [row("W1", "watch", 1.2, trigger=True), row("B1", "buy", 2.5, True), row("W2", "watch", 9.0, trigger=False),
        row("B2", "buy", 3.1, True), row("S1", "sell")]


def opener_for(files):
    calls = []

    def opener(url, timeout=None):
        calls.append(url)
        name = url.rsplit("/", 1)[-1]
        if name not in files:
            raise URLError("missing")
        return io.BytesIO(files[name].encode())
    opener.calls = calls
    return opener


def failing_opener(url, timeout=None):
    raise URLError("offline")


class StubNews:
    def __init__(self, articles=None, error=None):
        self.articles, self.error, self.requested = articles or {}, error, None

    def news(self, symbols, start, end):
        self.requested = (list(symbols), start, end)
        if self.error:
            raise self.error
        return self.articles


def histories():
    days = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(51)]
    bars = [Bar(d, 100, 101, 99, 100, 1000) for d in days]
    return {"B1": bars, "B2": bars, "IDX": bars}


class Shortlist(unittest.TestCase):
    def test_prefers_buy_then_triggered_watch_by_rr(self):
        self.assertEqual(shortlist(ROWS, 20), ["B2", "B1", "W1"])
        self.assertEqual(shortlist(ROWS, 2), ["B2", "B1"])


class Narrative(unittest.TestCase):
    def test_extracts_marknadsoversikt_section(self):
        n = scout_narrative(AS_OF, opener_for({"rapport-261021.md": REPORT}))
        self.assertEqual(n["date"], "2026-10-21")
        self.assertEqual(n["text"], "## Marknadsöversikt\nS&P 500 steg.\nFed höll räntan.")
        self.assertTrue(n["url"].startswith("https://"))

    def test_prefers_newest_report(self):
        n = scout_narrative(AS_OF, opener_for({"rapport-261022.md": REPORT, "rapport-261020.md": REPORT}))
        self.assertEqual(n["date"], "2026-10-22")

    def test_none_when_all_fetches_fail(self):
        self.assertIsNone(scout_narrative(AS_OF, failing_opener))

    def test_too_old_is_ignored(self):
        opener = opener_for({"rapport-261017.md": REPORT})
        self.assertIsNone(scout_narrative(AS_OF, opener))
        self.assertEqual(len(opener.calls), 5)

    def test_missing_section_is_none(self):
        self.assertIsNone(scout_narrative(AS_OF, opener_for({"rapport-261021.md": "# Only intro\n"})))


class Context(unittest.TestCase):
    def test_demo_has_no_news_and_no_network(self):
        ctx = build_context(ROWS, AS_OF, MetroConfig(), histories(), "IDX", news_client=None, opener=None)
        self.assertEqual(ctx["news"], {"available": False, "note": "Demodata har inga nyheter.", "by_symbol": {}})
        self.assertIsNone(ctx["narrative"])
        self.assertEqual(ctx["shortlist"], ["B2", "B1", "W1"])

    def test_news_error_marks_unavailable_and_does_not_raise(self):
        ctx = build_context(ROWS, AS_OF, MetroConfig(), histories(), "IDX",
                            news_client=StubNews(error=ValueError("Alpaca HTTP 403")), opener=None)
        self.assertFalse(ctx["news"]["available"])
        self.assertEqual(ctx["news"]["note"], "Nyheter ej tillgängliga")

    def test_only_shortlisted_symbols_are_requested(self):
        stub = StubNews()
        build_context(ROWS, AS_OF, MetroConfig(), histories(), "IDX", news_client=stub, opener=None)
        self.assertEqual(stub.requested[0], ["B2", "B1", "W1"])
        self.assertEqual(stub.requested[2], "2026-10-22")

    def test_news_keeps_markup_as_plain_string(self):
        markup = "<img src=x onerror=alert(1)>"
        stub = StubNews({"B1": [{"headline": markup, "summary": "", "created_at": "2026-10-20T14:00:00Z",
                                  "source": "benzinga", "url": "https://example.com"}]})
        ctx = build_context(ROWS, AS_OF, MetroConfig(), histories(), "IDX", news_client=stub, opener=None)
        self.assertEqual(ctx["news"]["by_symbol"]["B1"]["articles"][0]["headline"], markup)
        self.assertEqual(ctx["news"]["by_symbol"]["B2"]["articles"], [])

    def test_log_records_shortlist(self):
        ctx = build_context(ROWS, AS_OF, MetroConfig(), histories(), "IDX", news_client=None, opener=None,
                            previous_log=[{"date": "2026-10-20", "symbol": "B1", "status": "watch"}])
        self.assertEqual([(e["date"], e["symbol"]) for e in ctx["log"]],
                         [("2026-10-20", "B1"), (AS_OF, "B1"), (AS_OF, "B2"), (AS_OF, "W1")])
        self.assertIsNone(ctx["log"][1]["reaction"])


class Log(unittest.TestCase):
    def test_merge_log_dedupes_and_bounds(self):
        old = [{"date": "2026-10-20", "symbol": "A", "status": "watch"}, {"date": "2026-10-21", "symbol": "A", "status": "watch"}]
        new = [{"date": "2026-10-21", "symbol": "A", "status": "buy"}, {"date": "2026-10-21", "symbol": "B", "status": "buy"}]
        merged = merge_log(old, new, max_entries=2)
        self.assertEqual([(e["date"], e["symbol"], e["status"]) for e in merged],
                         [("2026-10-21", "A", "buy"), ("2026-10-21", "B", "buy")])


class AlpacaNews(unittest.TestCase):
    def test_paginates_maps_symbols_and_caps_per_symbol(self):
        with patch.dict("os.environ", {"ALPACA_API_KEY": "test", "ALPACA_API_SECRET": "test"}):
            client = Alpaca()
        article = lambda n, symbols: {"id": n, "headline": f"h{n}", "summary": "s", "created_at": "2026-10-20T14:00:00Z",
                                      "source": "benzinga", "url": None, "symbols": symbols, "content": "x"}
        pages = [{"news": [article(n, ["AAA", "ZZZ"]) for n in range(4)], "next_page_token": "p2"},
                 {"news": [article(n, ["AAA", "BBB"]) for n in range(4, 8)], "next_page_token": None}]
        calls = []

        def get(host, route, params):
            calls.append((route, dict(params)))
            return pages.pop(0)
        client.get = get
        news = client.news(["AAA", "BBB"], "2026-10-16", "2026-10-22")
        self.assertEqual(len(news["AAA"]), 5)
        self.assertEqual(len(news["BBB"]), 4)
        self.assertNotIn("ZZZ", news)
        self.assertEqual(set(news["AAA"][0]), {"headline", "summary", "created_at", "source", "url"})
        self.assertEqual(calls[0][0], "/v1beta1/news")
        self.assertEqual(calls[1][1]["page_token"], "p2")


if __name__ == "__main__":
    unittest.main()
