"""Metro strategy: levels, scenarios, risk/reward and status for one completed daily bar."""
from .engine import eligibility, position_plan
from .indicators import calculate
from .metro_levels import cluster_levels, find_pivots, known_pivots, nearest_levels

METRO_STATUSES = ("buy", "watch", "sell", "wait", "excluded")
LEVEL_FIELDS = ("trend", "r1", "r2", "s1", "s2", "trigger", "t1", "t2", "bear_trigger", "bear_t1", "bear_t2",
                "stop", "rr", "atr", "entry_reference", "shares", "risk_usd", "target", "regime")


def _trend(close, ma50, ma200, known):
    lows = [p for _, kind, p in known if kind == "low"]
    highs = [p for _, kind, p in known if kind == "high"]
    if ma50 is None or ma200 is None:
        return "sideways"
    if close > ma50 > ma200 and len(lows) >= 2 and lows[-1] > lows[-2]:
        return "bullish"
    if close < ma50 < ma200 and len(highs) >= 2 and highs[-1] < highs[-2]:
        return "bearish"
    return "sideways"


def evaluate_metro(asset, bars, config, index=None, indicators=None, pivots=None, regime=None, historical=False):
    m = config.metro
    i = len(bars) - 1 if index is None else index
    result = {"symbol": asset.symbol, "name": asset.name, "sector": asset.sector, "status": "excluded",
              "reasons": [], "warnings": [], "checks": {}, "chart_levels": [], **{k: None for k in LEVEL_FIELDS}}
    if i < 0:
        result["reasons"] = ["Historik saknas"]
        return result
    b = bars[i]
    result.update({"date": b.date, "close": b.close})
    reasons, _ = eligibility(asset, bars, i, config, historical)
    if reasons:
        result["reasons"] = reasons
        return result
    ind = indicators or calculate(bars[:i+1])
    atr = ind["atr"][i-1]
    if not atr or atr <= 0:
        result["reasons"] = ["ATR saknas eller är noll"]
        return result
    if regime is None:
        regime = {"label": "neutral", "notes": []}
        result["warnings"].append("Marknadsläge saknas")
    if asset.classification == "heuristic":
        result["warnings"].append("Instrumenttyp är uppskattad från namn; kontrollera stamaktie")
    # Pivots confirmed after t-1 are discarded, so only bars before the signal bar matter.
    known = known_pivots(find_pivots(bars[:i], m.pivot_span) if pivots is None else pivots,
                         i, m.pivot_span, m.level_lookback)
    levels = cluster_levels([p for _, _, p in known], m.cluster_atr * atr)
    near = nearest_levels(levels, bars[i-1].close)
    r1, r2, r3, s1, s2 = (near[k] for k in ("r1", "r2", "r3", "s1", "s2"))
    close, previous = b.close, bars[i-1].close
    trend = _trend(close, ind["sma50"][i], ind["sma200"][i], known)
    levels_ok = r1 is not None and s1 is not None
    trigger = r1 + m.trigger_atr_buffer * atr if r1 is not None else None
    bear_trigger = s1 - m.trigger_atr_buffer * atr if s1 is not None else None
    t1 = t2 = stop = rr = bear_t1 = bear_t2 = None
    if levels_ok:
        move = r1 - s1
        t1 = r2 if r2 is not None else r1 + move
        t2 = r3 if r3 is not None else r1 + 2 * move
        if t2 <= t1:
            t2 = None
        stop = r1 - m.stop_atr * atr
        if close > stop:
            rr = (t1 - close) / (close - stop)
        bear_t1 = s2 if s2 is not None else s1 - move
        bear_t2 = s1 - 2 * move
    bull = levels_ok and close > trigger and previous <= r1 and trend != "bearish"
    bear = levels_ok and close < bear_trigger and previous >= s1
    rr_ok = rr is not None and rr >= m.min_rr
    regime_ok = not m.use_regime or regime["label"] != "risk_off"
    near_r1 = levels_ok and trend != "bearish" and r1 - m.watch_distance_atr * atr <= close <= trigger
    if bull and rr_ok and regime_ok:
        status = "buy"
    elif bull or near_r1:
        status = "watch"
    elif bear:
        status = "sell"
    else:
        status = "wait"
    if status == "buy":
        reasons = ["Samtliga Metro-villkor uppfyllda"]
    else:
        reasons = []
        if r1 is None:
            reasons.append("Motståndsnivå saknas")
        if s1 is None:
            reasons.append("Stödnivå saknas")
        if trend == "bearish":
            reasons.append("Bearish trend")
        if levels_ok and not bull:
            reasons.append("Ingen stängning över triggern")
        if bull and not rr_ok:
            reasons.append(f"R/R {rr:.1f} under kravet {m.min_rr:g}" if rr is not None else "Mål saknas")
        if bull and rr_ok and not regime_ok:
            reasons.append("Risk-off: köpsignal nedgraderad")
        if status == "sell":
            reasons.append("Stängning under stöd: sälj om du äger, undvik annars")
        if status == "wait" and levels_ok and s1 < close < r1:
            reasons.append("Inom intervallet: avvakta bekräftelse")
    plan = position_plan(close, stop, config) if stop is not None else {"shares": 0, "risk_usd": 0}
    result.update({"status": status, "reasons": reasons, "trend": trend, "r1": r1, "r2": r2, "s1": s1, "s2": s2,
                   "trigger": trigger, "t1": t1, "t2": t2, "bear_trigger": bear_trigger, "bear_t1": bear_t1,
                   "bear_t2": bear_t2, "stop": stop, "rr": rr, "atr": atr, "entry_reference": close,
                   "shares": plan["shares"], "risk_usd": plan["risk_usd"], "target": t1, "regime": regime["label"],
                   "checks": {"trend_ok": trend != "bearish", "trigger": bull, "rr_ok": rr_ok,
                              "regime_ok": regime_ok, "bearish_trigger": bear}})
    result["chart_levels"] = [{"kind": kind, "price": float(price), "label": label} for kind, label, price in
                              (("s2", "S2", s2), ("s1", "S1", s1), ("r1", "R1 / trigger", r1), ("r2", "R2", r2),
                               ("t1", "T1", t1), ("t2", "T2", t2), ("stop", "Stop", stop)) if price is not None]
    return result


def scan_metro(assets, histories, config, regimes, as_of=None):
    rows = []
    for asset in assets:
        bars = histories.get(asset.symbol, [])
        if as_of and (not bars or bars[-1].date != as_of):
            rows.append({"symbol": asset.symbol, "name": asset.name, "sector": asset.sector, "status": "excluded",
                         "reasons": ["Senaste avslutade handelssessionen saknas"], "warnings": [], "checks": {},
                         "chart_levels": [], **{k: None for k in LEVEL_FIELDS}})
        else:
            rows.append(evaluate_metro(asset, bars, config, regime=regimes.get(bars[-1].date) if bars else None))
    order = {s: n for n, s in enumerate(METRO_STATUSES)}
    return sorted(rows, key=lambda r: (order[r["status"]], -(r["rr"] if r["rr"] is not None else float("-inf")), r["symbol"]))
