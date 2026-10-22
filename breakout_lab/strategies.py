"""Strategy registry and the Metro section published next to the breakout scan."""
from .metro import METRO_STATUSES, scan_metro
from .metro_regime import breadth_by_date, regime_series

STRATEGIES = ({"id": "breakout", "name": "Breakout"}, {"id": "metro", "name": "Metro"})
METRO_CSV_COLUMNS = ["symbol", "date", "status", "close", "trend", "r1", "r2", "s1", "s2", "trigger",
                     "t1", "t2", "stop", "rr", "shares", "risk_usd"]


def metro_section(assets, histories, config, metadata, context_builder=None):
    as_of = metadata["as_of"]
    breadth = breadth_by_date(assets, histories, config, {}, historical=False, dates={as_of})
    regimes = regime_series(histories.get(metadata.get("benchmark_symbol", "SPY"), []), breadth, config.metro)
    regime = regimes.get(as_of) or {"date": as_of, "label": "neutral", "index_close": None, "index_sma200": None,
                                    "breadth": None, "eligible": 0, "notes": ["Indexhistorik saknas"]}
    rows = scan_metro(assets, histories, config, regimes, as_of)
    counts = {s: sum(r["status"] == s for r in rows) for s in METRO_STATUSES}
    context = None
    if context_builder:
        try:
            context = context_builder(rows, regime)
        except Exception:
            # News and narrative are optional context; they must never block the daily analysis.
            context = None
    return {"rows": rows, "counts": counts, "regime": regime, "context": context}
