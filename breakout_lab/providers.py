"""Read-only data clients. This module contains no broker-order endpoints."""
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import csv
import json
import math
import os
import re
import time as clock

from .models import Asset, Bar

NY = ZoneInfo("America/New_York")


def read_metadata(path):
    if not path:
        return {}
    result = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            symbol = row["symbol"].strip().upper()
            if not symbol or symbol in result:
                raise ValueError("Empty or duplicate metadata symbol")
            cap = float(row["market_cap"]) if row.get("market_cap") else None
            if cap is not None and (not math.isfinite(cap) or cap < 0):
                raise ValueError("Invalid market cap")
            earnings = row.get("earnings_date") or None
            if earnings:
                date.fromisoformat(earnings)
            result[symbol] = {"sector": row.get("sector") or None, "market_cap": cap,
                              "earnings_date": earnings}
            for key in ("name", "kind", "exchange"):
                if row.get(key):
                    result[symbol][key] = row[key]
            if row.get("kind"):
                result[symbol]["classification"] = "curated"
    return result


def import_csv(path, metadata_path=None):
    """Required: symbol,date,open,high,low,close,volume; 1D finalized bars only."""
    histories = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"symbol", "date", "open", "high", "low", "close", "volume"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV requires {', '.join(sorted(required))}")
        for row in reader:
            symbol = row["symbol"].strip().upper()
            if not symbol:
                raise ValueError("Missing symbol")
            bar = Bar(row["date"], *(float(row[k]) for k in ("open", "high", "low", "close", "volume")))
            histories.setdefault(symbol, []).append(bar)
    if not histories:
        raise ValueError("CSV has no bars")
    meta = read_metadata(metadata_path)
    assets = [Asset(symbol=s, **{"name": s, "kind": "unknown", "classification": "unknown", **meta.get(s, {})})
              for s in sorted(histories) if s != "SPY"]
    for bars in histories.values():
        bars.sort(key=lambda b: b.date)
    latest = max(bars[-1].date for bars in histories.values())
    return assets, histories, {"source": "csv", "feed": "user-supplied", "as_of": latest,
                                "benchmark_symbol": "SPY", "synthetic": False,
                                "notes": ["Importerade 1D-candles; du ansvarar för avslutade candles och konsekvent splitjustering.",
                                          "Instrumenttyp kräver metadata med kind=common."]}


def latest_complete_session(calendar, now):
    local = now.astimezone(NY)
    available = []
    for session in calendar:
        session_day = date.fromisoformat(session["date"])
        # Wait through the end of extended hours + 15 min to avoid a changing daily aggregate.
        closing = time.fromisoformat(session["close"])
        cutoff = datetime.combine(session_day, max(closing, time(20)), NY) + timedelta(minutes=15)
        if cutoff <= local:
            available.append(session["date"])
    if not available:
        raise ValueError("No completed session in calendar response")
    return max(available)


class Alpaca:
    def __init__(self, feed=None, opener=urlopen, sleeper=clock.sleep):
        key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_API_SECRET")
        if not key or not secret:
            raise ValueError("Set ALPACA_API_KEY and ALPACA_API_SECRET in your environment")
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.feed = feed or os.environ.get("ALPACA_DATA_FEED", "sip")
        if self.feed not in ("sip", "iex"):
            raise ValueError("Only sip and iex feeds are supported")
        self.opener, self.sleeper = opener, sleeper

    def get(self, host, route, params):
        url = host + route + "?" + urlencode(params)
        for attempt in range(4):
            try:
                with self.opener(Request(url, headers=self.headers), timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if (error.code == 429 or error.code >= 500) and attempt < 3:
                    self.sleeper(min(2**attempt, 8))
                    continue
                # Deliberately omit request headers and provider response bodies.
                raise ValueError(f"Alpaca HTTP {error.code}: check credentials, entitlement or rate limit") from None
            except (URLError, TimeoutError):
                if attempt < 3:
                    self.sleeper(2**attempt)
                    continue
                raise ValueError("Alpaca network request failed") from None

    def assets(self):
        rows = self.get("https://paper-api.alpaca.markets", "/v2/assets", {"status": "active", "asset_class": "us_equity"})
        assets = []
        excluded = re.compile(r"\b(etf|etn|fund|warrants?|preferred|depositary|units|portfolio)\b", re.I)
        for row in rows:
            if not row.get("tradable") or row.get("exchange") == "OTC":
                continue
            name = row.get("name", row["symbol"])
            kind = "other" if excluded.search(name) or any(c in row["symbol"] for c in ("/", "^")) else "common"
            assets.append(Asset(row["symbol"], name, row["exchange"], kind, classification="heuristic"))
        return assets

    def bars(self, symbols, start, as_of):
        histories = {s: [] for s in symbols}
        for offset in range(0, len(symbols), 100):
            chunk = symbols[offset:offset+100]
            token, seen = None, set()
            while True:
                params = {"symbols": ",".join(chunk), "timeframe": "1Day", "start": start,
                          "end": (date.fromisoformat(as_of)+timedelta(days=1)).isoformat(),
                          "adjustment": "split", "feed": self.feed, "limit": 10000, "sort": "asc"}
                if token:
                    params["page_token"] = token
                page = self.get("https://data.alpaca.markets", "/v2/stocks/bars", params)
                for symbol, rows in (page.get("bars") or {}).items():
                    if symbol not in histories:
                        raise ValueError("Unexpected symbol in provider response")
                    for row in rows:
                        day = datetime.fromisoformat(row["t"].replace("Z", "+00:00")).astimezone(NY).date().isoformat()
                        if start <= day <= as_of:
                            histories[symbol].append(Bar(day, row["o"], row["h"], row["l"], row["c"], row["v"]))
                token = page.get("next_page_token")
                if not token:
                    break
                if token in seen:
                    raise ValueError("Provider repeated pagination token")
                seen.add(token)
        for symbol, history in histories.items():
            histories[symbol] = sorted(history, key=lambda b: b.date)
        return histories

    def dataset(self, metadata_path=None, limit=None, years=3):
        now = datetime.now(timezone.utc)
        local_day = now.astimezone(NY).date()
        calendar = self.get("https://paper-api.alpaca.markets", "/v2/calendar",
                            {"start": (local_day-timedelta(days=30)).isoformat(), "end": local_day.isoformat()})
        as_of = latest_complete_session(calendar, now)
        metadata = read_metadata(metadata_path)
        assets = [replace(a, **metadata.get(a.symbol, {})) for a in self.assets()]
        assets = sorted([a for a in assets if a.kind == "common" and a.symbol != "SPY"], key=lambda a: a.symbol)
        total = len(assets)
        if not assets:
            raise ValueError("No eligible assets returned by Alpaca")
        if limit is not None:
            assets = assets[:limit]
        start = (date.fromisoformat(as_of)-timedelta(days=365*years+30)).isoformat()
        histories = self.bars([a.symbol for a in assets]+["SPY"], start, as_of)
        return assets, histories, {"source": "alpaca", "feed": self.feed, "as_of": as_of,
                                    "synced_at": now.isoformat(), "synthetic": False,
                                    "benchmark_symbol": "SPY", "discovered_assets": total,
                                    "sample_limit": limit, "adjustment": "split", "bar_definition": "provider_1Day",
                                    "notes": ["Aktiva handlingsbara instrument hos Alpaca; ej ett historiskt komplett börsuniversum.",
                                              "Instrumenttyp uppskattas från namn om kuraterad metadata saknas.",
                                              "IEX omfattar en börs; SIP kräver rätt abonnemang." if self.feed == "iex" else "SIP används för bred volymtäckning."]}
