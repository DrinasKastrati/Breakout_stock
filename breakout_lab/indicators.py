"""Causal indicator series. Every result at i uses bars at or before i."""


def sma(values, period):
    output, total = [], 0.0
    for i, v in enumerate(values):
        total += v
        if i >= period:
            total -= values[i - period]
        output.append(total / period if i >= period - 1 else None)
    return output


def ema(values, period):
    # SMA seed, then alpha=2/(period+1); explicit warm-up rather than zero fill.
    result = [None] * len(values)
    if len(values) < period:
        return result
    previous = sum(values[:period]) / period
    result[period - 1] = previous
    alpha = 2 / (period + 1)
    for i in range(period, len(values)):
        previous += alpha * (values[i] - previous)
        result[i] = previous
    return result


def calculate(bars):
    closes = [b.close for b in bars]
    ma50 = sma(closes, 50)
    fast, slow = ema(closes, 12), ema(closes, 26)
    macd = [f - s if f is not None and s is not None else None for f, s in zip(fast, slow)]
    valid = [m for m in macd if m is not None]
    signal = [None] * min(25, len(bars)) + ema(valid, 9)
    histogram = [m - s if m is not None and s is not None else None for m, s in zip(macd, signal)]
    true_range = [b.high - b.low if i == 0 else max(b.high - b.low, abs(b.high - bars[i-1].close), abs(b.low - bars[i-1].close)) for i, b in enumerate(bars)]
    atr = [None] * len(bars)
    if len(bars) >= 14:
        atr[13] = sum(true_range[:14]) / 14
        for i in range(14, len(bars)):
            atr[i] = (atr[i-1] * 13 + true_range[i]) / 14
    return {"sma50": ma50, "atr": atr, "macd": macd, "signal": signal, "histogram": histogram}
