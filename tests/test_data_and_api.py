from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import threading
import unittest

from breakout_lab.demo import dataset
from breakout_lab.models import Config
from breakout_lab.providers import Alpaca, NY, import_csv, latest_complete_session
from breakout_lab.server import Application, handler
from breakout_lab.storage import Store


class Data(unittest.TestCase):
    def test_complete_session_excludes_changing_daily_bar(self):
        calendar=[{"date":"2026-07-01","close":"16:00"},{"date":"2026-07-02","close":"13:00"}]
        now=datetime(2026,7,2,20,14,tzinfo=NY)
        self.assertEqual(latest_complete_session(calendar,now),"2026-07-01")
        self.assertEqual(latest_complete_session(calendar,now.replace(minute=15)),"2026-07-02")

    def test_pagination_collects_all_symbols(self):
        with patch.dict("os.environ",{"ALPACA_API_KEY":"test","ALPACA_API_SECRET":"test"}):
            client=Alpaca()
        def bar(day):
            return {"t":f"2024-01-{day:02}T05:00:00Z","o":100,"h":101,"l":99,"c":100,"v":1000}
        pages=[{"bars":{"AAA":[bar(1),bar(2)]},"next_page_token":"page-2"},{"bars":{"BBB":[bar(1)]},"next_page_token":None}]
        calls=[]
        def get(host,route,params):
            calls.append(params.copy())
            return pages.pop(0)
        client.get=get
        rows=client.bars(["AAA","BBB"],"2024-01-01","2024-01-02")
        self.assertEqual(len(rows["AAA"]),2)
        self.assertEqual(len(rows["BBB"]),1)
        self.assertEqual(calls[1]["page_token"],"page-2")
        self.assertEqual(calls[0]["adjustment"],"split")

    def test_future_and_partial_bars_are_removed(self):
        with patch.dict("os.environ",{"ALPACA_API_KEY":"test","ALPACA_API_SECRET":"test"}):
            client=Alpaca()
        client.get=lambda *args:{"bars":{"AAA":[{"t":"2024-01-03T05:00:00Z","o":100,"h":101,"l":99,"c":100,"v":1000}]}}
        self.assertEqual(client.bars(["AAA"],"2024-01-01","2024-01-02")["AAA"],[])

    def test_refresh_rolls_back_invalid_dataset(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/"data.sqlite")
            assets,histories,meta=dataset()
            store.replace_dataset(assets,histories,meta)
            histories[assets[0].symbol].append(histories[assets[0].symbol][-1])
            with self.assertRaises(ValueError):
                store.replace_dataset(assets,histories,{"source":"bad"})
            self.assertEqual(store.load()[2]["source"],"demo")

    def test_csv_requires_explicit_security_metadata(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"bars.csv"
            path.write_text("symbol,date,open,high,low,close,volume\nAAA,2024-01-01,100,101,99,100,1000\n")
            self.assertEqual(import_csv(path)[0][0].kind,"unknown")
            metadata=Path(tmp)/"metadata.csv"
            metadata.write_text("symbol,kind,sector\nAAA,common,Technology\n")
            self.assertEqual(import_csv(path,metadata)[0][0].kind,"common")


class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=TemporaryDirectory()
        cls.store=Store(Path(cls.tmp.name)/"demo.sqlite")
        cls.store.replace_dataset(*dataset())
        cls.app=Application(cls.store,Config())
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),handler(cls.app))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def test_scan_and_bars(self):
        with urlopen(self.base+"/api/scan") as response:
            data=json.load(response)
        self.assertEqual(data["metadata"]["source"],"demo")
        self.assertEqual(len(data["rows"]),8)
        self.assertGreater(data["counts"]["breakout"],0)
        with urlopen(self.base+"/api/bars?symbol=DEMO-A") as response:
            bars=json.load(response)
        self.assertEqual(len(bars["bars"]),100)

    def test_backtest_variants(self):
        with urlopen(self.base+"/api/backtest") as response:
            result=json.load(response)
        self.assertEqual(len(result["variants"]),3)
        self.assertGreater(result["variants"][0]["summary"]["trades"],0)

    def test_config_validation(self):
        request=Request(self.base+"/api/config",data=b'{"risk_fraction":1}',headers={"Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code,400)

    def test_host_and_origin_protection(self):
        for headers in ({"Host":"attacker.example"},{"Origin":"https://attacker.example"}):
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base+"/api/scan",headers=headers))
            self.assertEqual(error.exception.code,403)

    def test_static_and_csv(self):
        with urlopen(self.base+"/") as response:
            self.assertIn("Breakout Lab",response.read().decode())
            self.assertIn("frame-ancestors 'none'",response.headers["Content-Security-Policy"])
        with urlopen(self.base+"/api/export") as response:
            self.assertIn("symbol,date,status",response.read().decode("utf-8-sig"))


if __name__=="__main__":
    unittest.main()
