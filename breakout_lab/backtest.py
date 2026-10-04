"""Per-symbol historical trade simulation, not a portfolio equity backtest."""
from dataclasses import replace

from .engine import evaluate, position_plan
from .indicators import calculate


def simulate_trade(bars, signal_index, candidate, config):
    entry_index = signal_index + 1
    if entry_index >= len(bars):
        return None
    entry_bar = bars[entry_index]
    slip = config.slippage_bps / 10_000
    entry = entry_bar.open * (1 + slip)
    stop = candidate["stop"]
    if entry <= stop or entry > candidate["resistance"] + config.max_extension_atr * candidate["atr"]:
        return None
    plan = position_plan(entry, stop, config)
    shares = plan["shares"]
    if shares < 1:
        return None
    target = plan["target"]
    last = min(entry_index + config.max_holding_bars - 1, len(bars) - 1)
    exit_price, exit_index, reason = None, last, "open"
    for j in range(entry_index, last + 1):
        b = bars[j]
        # Stop gaps fill at the opening price, not at the requested stop.
        if b.open <= stop:
            exit_price, exit_index, reason = b.open, j, "stop_gap"
            break
        if b.open >= target:
            exit_price, exit_index, reason = target, j, "target"
            break
        # OHLC cannot establish event order: stop wins if both prices were touched.
        if b.low <= stop:
            exit_price, exit_index, reason = stop, j, "stop"
            break
        if b.high >= target:
            exit_price, exit_index, reason = target, j, "target"
            break
    if exit_price is None:
        if last - entry_index + 1 < config.max_holding_bars:
            # Never invent a liquidation at the end of the available sample.
            return {"open": True, "entry_date": entry_bar.date, "entry_index": entry_index}
        exit_price, reason = bars[last].close, "time"
    exit_price *= 1 - slip
    fees = shares * config.commission_per_share * 2
    pnl = (exit_price - entry) * shares - fees
    return {"open": False, "signal_date": bars[signal_index].date,
            "entry_date": entry_bar.date, "exit_date": bars[exit_index].date,
            "entry": entry, "exit": exit_price, "stop": stop, "target": target,
            "shares": shares, "pnl_usd": pnl, "r_multiple": pnl / ((entry - stop) * shares),
            "holding_bars": exit_index - entry_index + 1, "exit_reason": reason,
            "exit_index": exit_index}


def summary(trades):
    rs = [t["r_multiple"] for t in trades]
    profits = sum(r for r in rs if r > 0)
    losses = -sum(r for r in rs if r < 0)
    return {"trades": len(rs), "win_rate": sum(r > 0 for r in rs) / len(rs) if rs else None,
            "expectancy_r": sum(rs) / len(rs) if rs else None,
            "profit_factor_r": profits / losses if losses else None,
            "total_r": sum(rs)}


def backtest(assets, histories, config, start=None, end=None):
    if config.earnings_blackout_days or config.min_market_cap or config.allowed_sectors:
        raise ValueError("Backtest requires point-in-time metadata for earnings, market cap and sectors. Disable these filters.")
    if start and end and start > end:
        raise ValueError("Start date must be before end date")
    all_trades, open_trades, signals = [], 0, 0
    for asset in assets:
        bars = [b for b in histories.get(asset.symbol, []) if not end or b.date <= end]
        ind = calculate(bars)
        i = config.min_history - 1
        while i < len(bars):
            if start and bars[i].date < start:
                i += 1
                continue
            c = evaluate(asset, bars, config, i, ind, historical=True)
            if c["status"] == "breakout":
                signals += 1
                trade = simulate_trade(bars, i, c, config)
                if trade and trade["open"]:
                    open_trades += 1
                    break
                if trade:
                    all_trades.append({"symbol": asset.symbol, **trade})
                    # Signal at exit day's close is available after the position exits.
                    i = max(i + 1, trade["exit_index"])
                    continue
            i += 1
    all_trades.sort(key=lambda t: (t["entry_date"], t["symbol"]))
    return {"summary": summary(all_trades), "signals": signals, "open_trades": open_trades,
            "trades": all_trades, "scope": "independent_trades",
            "limitations": ["Separata affärer per aktie; ingen portföljavkastning eller portföljdrawdown.",
                            "Nuvarande aktieuniversum kan ge överlevnadsbias.",
                            "Poäng och backtest är inte sannolikheter eller garantier."]}


def compare(assets, histories, config, start=None, end=None):
    variants = [("Pris", False, False), ("Pris + volym", True, False), ("Pris + volym + MACD", True, True)]
    return [{"name": name, **backtest(assets, histories, replace(config, require_volume=v, require_macd=m), start, end)}
            for name, v, m in variants]
