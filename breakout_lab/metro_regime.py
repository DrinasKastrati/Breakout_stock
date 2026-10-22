"""Mechanical market regime for Metro: index trend plus breadth over the eligible universe."""
from .engine import eligibility
from .indicators import calculate, sma


def breadth_by_date(assets, histories, config, indicators, historical, dates=None):
    counts = {}
    for asset in assets:
        bars = histories.get(asset.symbol, [])
        if not bars:
            continue
        ma = (indicators.get(asset.symbol) or calculate(bars))["sma50"]
        if dates is None:
            positions = range(len(bars))
        else:
            positions = [i for i, b in enumerate(bars) if b.date in dates]
        for i in positions:
            if ma[i] is None:
                continue
            reasons, _ = eligibility(asset, bars, i, config, historical, require_history=False)
            if reasons:
                continue
            above, eligible = counts.get(bars[i].date, (0, 0))
            counts[bars[i].date] = (above + (bars[i].close > ma[i]), eligible + 1)
    return counts


def regime_series(benchmark, breadth, metro):
    ma200 = sma([b.close for b in benchmark], 200)
    result = {}
    for i, b in enumerate(benchmark):
        above, eligible = breadth.get(b.date, (0, 0))
        share = above / eligible if eligible else None
        notes, label = [], "neutral"
        if ma200[i] is None:
            notes.append("Indexhistorik saknas")
        if not eligible:
            notes.append("Inga behöriga aktier")
        if not notes:
            if b.close > ma200[i] and share >= metro.breadth_risk_on:
                label = "risk_on"
            elif b.close < ma200[i] and share < metro.breadth_risk_off:
                label = "risk_off"
        result[b.date] = {"date": b.date, "label": label, "index_close": b.close, "index_sma200": ma200[i],
                          "breadth": share, "eligible": eligible, "notes": notes}
    return result
