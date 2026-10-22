"""Swing pivots and price levels for the Metro strategy. A pivot at j is known only at j + span."""


def find_pivots(bars, span):
    pivots = []
    for j in range(span, len(bars) - span):
        window = range(j - span, j + span + 1)
        high, low = bars[j].high, bars[j].low
        # Strict extremes only: equal neighbours do not confirm a swing.
        if all(bars[k].high < high for k in window if k != j):
            pivots.append((j, "high", high))
        if all(bars[k].low > low for k in window if k != j):
            pivots.append((j, "low", low))
    return pivots


def known_pivots(pivots, t, span, lookback):
    return [p for p in pivots if p[0] + span <= t - 1 and p[0] >= t - 1 - lookback]


def cluster_levels(prices, width):
    levels = []
    for price in sorted(prices):
        # Anchored on the first member, so a sideways range cannot chain into one level.
        if levels and price - levels[-1]["first"] <= width:
            levels[-1]["members"].append(price)
        else:
            levels.append({"first": price, "members": [price]})
    return [{"price": sum(lv["members"]) / len(lv["members"]), "touches": len(lv["members"])} for lv in levels]


def nearest_levels(levels, reference):
    above = sorted(lv["price"] for lv in levels if lv["price"] > reference)
    below = sorted((lv["price"] for lv in levels if lv["price"] < reference), reverse=True)
    pick = lambda values, n: values[n] if len(values) > n else None
    return {"r1": pick(above, 0), "r2": pick(above, 1), "r3": pick(above, 2),
            "s1": pick(below, 0), "s2": pick(below, 1)}
