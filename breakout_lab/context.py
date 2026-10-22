"""Display-only Metro context: scout narrative, news with market reaction, and a reaction log."""
from datetime import date, timedelta
from urllib.request import urlopen

from .reaction import symbol_reactions

SCOUT_URL = "https://raw.githubusercontent.com/DrinasKastrati/Vecko_agent/main/reports/scout/rapport-{}.md"
SECTION = "## Marknadsöversikt"


def shortlist(rows, size):
    picks = [r for r in rows if r["status"] == "buy" or (r["status"] == "watch" and r["checks"].get("trigger"))]
    picks.sort(key=lambda r: (r["status"] != "buy", -(r["rr"] if r["rr"] is not None else float("-inf")), r["symbol"]))
    return [r["symbol"] for r in picks[:size]]


def scout_narrative(as_of, opener=urlopen):
    day = date.fromisoformat(as_of)
    # The report is written in Stockholm the morning after the US session; older than 3 days is stale.
    for offset in (1, 0, -1, -2, -3):
        current = day + timedelta(days=offset)
        url = SCOUT_URL.format(current.strftime("%y%m%d"))
        try:
            with opener(url, timeout=10) as response:
                text = response.read().decode("utf-8")
        except Exception:
            continue
        lines, section = text.splitlines(), None
        for line in lines:
            if section is None and line.startswith(SECTION):
                section = [line]
            elif section is not None and line.startswith("## "):
                break
            elif section is not None:
                section.append(line)
        if section is None:
            return None
        return {"date": current.isoformat(), "text": "\n".join(section).strip()[:4000], "url": url}
    return None


def merge_log(previous, entries, max_entries=10000):
    merged = {(e["date"], e["symbol"]): e for e in previous}
    merged.update({(e["date"], e["symbol"]): e for e in entries})
    return [merged[k] for k in sorted(merged)][-max_entries:]


def build_context(rows, as_of, metro, histories, benchmark_symbol, news_client=None, opener=urlopen, previous_log=None):
    symbols = shortlist(rows, metro.shortlist_size)
    narrative = scout_narrative(as_of, opener) if opener else None
    news = {"available": False, "note": "Demodata har inga nyheter.", "by_symbol": {}}
    if news_client is not None:
        start = (date.fromisoformat(as_of) - timedelta(days=metro.news_days + 2)).isoformat()
        # A date-only end would stop at midnight and drop the session's own articles.
        end = (date.fromisoformat(as_of) + timedelta(days=1)).isoformat()
        try:
            raw = news_client.news(symbols, start, end) if symbols else {}
            index_bars = {b.date: b.close for b in histories.get(benchmark_symbol, [])}
            news = {"available": True, "note": "" if symbols else "Inga aktier i kortlistan.",
                    "by_symbol": {s: symbol_reactions(raw.get(s, []), histories.get(s, []), index_bars) for s in symbols}}
        except Exception:
            news = {"available": False, "note": "Nyheter ej tillgängliga", "by_symbol": {}}
    by_row = {r["symbol"]: r for r in rows}
    entries = []
    for s in symbols:
        summary = news["by_symbol"].get(s, {}).get("summary") if news["available"] else None
        entries.append({"date": as_of, "symbol": s, "status": by_row[s]["status"], "rr": by_row[s]["rr"],
                        "reaction": summary["label"] if summary else None,
                        "excess": summary.get("excess") if summary else None,
                        "rvol": summary.get("rvol") if summary else None})
    return {"shortlist": symbols, "narrative": narrative, "news": news, "log": merge_log(previous_log or [], entries)}
