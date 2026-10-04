from dataclasses import asdict
from pathlib import Path
import json
import sqlite3

from .models import Asset, Bar


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS assets(symbol TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bars(symbol TEXT NOT NULL, date TEXT NOT NULL,
                  open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,date));
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def replace_dataset(self, assets, histories, metadata):
        # All-or-nothing refresh avoids mixed vintages and stale split-adjusted bars.
        with self.connect() as db:
            db.execute("DELETE FROM assets")
            db.execute("DELETE FROM bars")
            db.execute("DELETE FROM metadata")
            for a in assets:
                db.execute("INSERT INTO assets VALUES (?,?)", (a.symbol, json.dumps(asdict(a))))
            for symbol, bars in histories.items():
                if len({b.date for b in bars}) != len(bars) or bars != sorted(bars, key=lambda b: b.date):
                    raise ValueError(f"Duplicate or unsorted history for {symbol}")
                db.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
                               [(symbol, b.date, b.open, b.high, b.low, b.close, b.volume) for b in bars])
            for key, value in metadata.items():
                db.execute("INSERT INTO metadata VALUES (?,?)", (key, json.dumps(value)))

    def load(self):
        with self.connect() as db:
            assets = [Asset(**json.loads(r[0])) for r in db.execute("SELECT payload FROM assets ORDER BY symbol")]
            histories = {}
            for row in db.execute("SELECT symbol,date,open,high,low,close,volume FROM bars ORDER BY symbol,date"):
                histories.setdefault(row[0], []).append(Bar(*row[1:]))
            meta = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata")}
        return assets, histories, meta
