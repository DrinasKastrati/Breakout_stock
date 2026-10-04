"""Cash-limited daily portfolio research; no broker-order endpoints.

Signals use completed candles. Entries are next-session opens. Only opening
gap exits can fund that session's entries: intraday event order is unknown.
"""
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import argparse
import json
import math
import os

from .engine import evaluate
from .indicators import calculate
from .models import Config


def discover_signals(assets, histories, config, start, end):
    if config.earnings_blackout_days or config.min_market_cap or config.allowed_sectors:
        raise ValueError("Point-in-time metadata is required for these filters")
    signals = defaultdict(list)
    eligible = 0
    for asset in assets:
        bars = [b for b in histories.get(asset.symbol, []) if b.date <= end]
        if any(b.date <= start for b in bars[config.min_history - 1:]):
            eligible += 1
        indicators = calculate(bars)
        for i in range(config.min_history - 1, len(bars)):
            if bars[i].date < start:
                continue
            candidate = evaluate(asset, bars, config, i, indicators, historical=True)
            if candidate["status"] == "breakout":
                signals[bars[i].date].append(candidate)
    return signals, eligible


def drawdown(curve, initial):
    peak, worst = initial, 0.0
    for value in curve:
        peak = max(peak, value)
        worst = max(worst, 1 - value / peak)
    return worst


def simulate_portfolio(histories, signals, config, start, end, sessions):
    """Shared USD cash account, whole shares, one position per symbol.

    Ranking is based only on the prior close: score, relative volume,
    smallest extension, then symbol. Position sizing uses current opening
    equity; no leverage. Open positions are marked at the final close.
    """
    date.fromisoformat(start); date.fromisoformat(end)
    if start > end:
        raise ValueError("Start date must precede end date")
    days = sorted({d for d in sessions if start <= d <= end})
    if not days:
        raise ValueError("No benchmark sessions in the requested test period")
    symbols = {c["symbol"] for candidates in signals.values() for c in candidates}
    indexed = {s: {b.date: b for b in histories.get(s, [])} for s in symbols}
    initial, cash = config.account_equity, config.account_equity
    slip, commission = config.slippage_bps / 10_000, config.commission_per_share
    positions, trades, curve = {}, [], []
    skipped = Counter()
    costs = Counter(commission=0.0, slippage=0.0)
    max_positions, stale_marks = 0, 0
    pending = []

    def close(symbol, raw_price, day, reason):
        nonlocal cash
        p = positions.pop(symbol)
        fill = raw_price * (1 - slip)
        exit_fee = p["shares"] * commission
        cash += p["shares"] * fill - exit_fee
        costs["commission"] += exit_fee
        costs["slippage"] += p["shares"] * (raw_price - fill)
        pnl = p["shares"] * (fill - p["entry"]) - exit_fee - p["entry_fee"]
        trades.append({**p, "exit_date": day, "exit": fill,
                       "exit_reason": reason, "pnl_usd": pnl,
                       "r_multiple": pnl / (p["shares"] * (p["entry"] - p["stop"]))})

    def opening_equity(day):
        return cash + sum(p["shares"] * (indexed[s][day].open if day in indexed[s] else p["mark"])
                          for s, p in positions.items())

    for day in days:
        # Existing opening gap exits occur before new opening entries.
        for symbol in sorted(list(positions)):
            b = indexed[symbol].get(day)
            if not b:
                continue
            p = positions[symbol]
            p["holding_bars"] += 1
            if b.open <= p["stop"]:
                close(symbol, b.open, day, "stop_gap")
            elif b.open >= p["target"]:
                # Conservative: do not credit a better-than-target gap fill.
                close(symbol, p["target"], day, "target_gap")

        ranked = sorted(pending, key=lambda c: (-c["score"], -c["relative_volume"],
                                                c["extension_atr"], c["symbol"]))
        for c in ranked:
            symbol = c["symbol"]
            if symbol in positions:
                skipped["already_held"] += 1
                continue
            b = indexed[symbol].get(day)
            if b is None:
                # No carry-forward to an unobservable future resumption.
                skipped["missing_next_session"] += 1
                continue
            entry, stop = b.open * (1 + slip), c["stop"]
            if entry <= stop or entry > c["resistance"] + config.max_extension_atr * c["atr"]:
                skipped["entry_gap"] += 1
                continue
            equity = max(0.0, opening_equity(day))
            shares = min(math.floor(equity * config.risk_fraction / (entry - stop)),
                         math.floor(equity * config.max_position_fraction / entry),
                         math.floor(max(0.0, cash) / (entry + commission)))
            if shares < 1:
                skipped["cash_or_size"] += 1
                continue
            fee = shares * commission
            cash -= shares * entry + fee
            if cash < -1e-6:
                raise AssertionError("Portfolio borrowed cash")
            cash = max(0.0, cash)
            costs["commission"] += fee
            costs["slippage"] += shares * (entry - b.open)
            positions[symbol] = {"symbol": symbol, "signal_date": c["date"],
                                 "entry_date": day, "entry": entry, "shares": shares,
                                 "entry_fee": fee, "stop": stop,
                                 "target": entry + config.reward_risk * (entry - stop),
                                 "holding_bars": 1, "mark": b.open}
        max_positions = max(max_positions, len(positions))

        # Intraday proceeds cannot retroactively fund opening entries.
        for symbol in sorted(list(positions)):
            b = indexed[symbol].get(day)
            if not b:
                stale_marks += 1
                continue
            p = positions[symbol]
            if b.low <= p["stop"]:
                close(symbol, p["stop"], day, "stop")
            elif b.high >= p["target"]:
                close(symbol, p["target"], day, "target")
            elif p["holding_bars"] >= config.max_holding_bars:
                close(symbol, b.close, day, "time")
            else:
                p["mark"] = b.close
        invested = sum(p["shares"] * p["mark"] for p in positions.values())
        equity = cash + invested
        curve.append({"date": day, "equity_usd": equity, "cash_usd": cash,
                      "invested_usd": invested, "positions": len(positions)})
        # Signal day and next-session relationship is determined by this calendar.
        pending = signals.get(day, [])

    final = curve[-1]["equity_usd"]
    pnls = [t["pnl_usd"] for t in trades]
    wins, losses = sum(p for p in pnls if p > 0), -sum(p for p in pnls if p < 0)
    realized = sum(pnls)
    annual = {}
    previous = initial
    for year in sorted({r["date"][:4] for r in curve}):
        rows = [r for r in curve if r["date"].startswith(year)]
        ending = rows[-1]["equity_usd"]
        annual[year] = {"start": rows[0]["date"], "end": rows[-1]["date"],
                        "return": ending / previous - 1}
        previous = ending
    elapsed = (date.fromisoformat(end) - date.fromisoformat(start)).days
    stats = {"initial_usd": initial, "final_usd": final, "net_profit_usd": final - initial,
             "return": final / initial - 1,
             "cagr": (final / initial) ** (365.25 / elapsed) - 1 if elapsed and final > 0 else None,
             "max_drawdown": drawdown([r["equity_usd"] for r in curve], initial),
             "closed_trades": len(trades), "open_positions": len(positions),
             "win_rate": sum(p > 0 for p in pnls) / len(pnls) if pnls else None,
             "profit_factor": wins / losses if losses else None,
             "realized_pnl_usd": realized, "unrealized_pnl_usd": final - initial - realized,
             "cash_usd": cash, "max_positions": max_positions,
             "average_exposure": sum(r["invested_usd"] / r["equity_usd"] if r["equity_usd"] > 0 else 0 for r in curve) / len(curve),
             "commission_usd": costs["commission"], "slippage_usd": costs["slippage"],
             "exit_reasons": dict(Counter(t["exit_reason"] for t in trades)),
             "signals": sum(len(signals.get(d, [])) for d in days),
             "unfilled_final_session_signals": len(pending),
             "skipped": dict(skipped), "stale_position_sessions": stale_marks,
             "annual_returns": annual, "sessions": len(days)}
    return {"start": start, "end": end, "stats": stats, "equity_curve": curve,
            "trades": trades, "open_positions": list(positions.values())}


def benchmark(bars, config, start, end):
    selected = [b for b in bars if start <= b.date <= end]
    if not selected:
        raise ValueError("Missing SPY benchmark")
    entry = selected[0].open * (1 + config.slippage_bps / 10_000)
    shares = math.floor(config.account_equity / (entry + config.commission_per_share))
    cash = config.account_equity - shares * (entry + config.commission_per_share)
    values = [cash + shares * b.close for b in selected]
    return {"name": "SPY buy and hold, price return without dividends",
            "final_usd": values[-1], "return": values[-1] / config.account_equity - 1,
            "max_drawdown": drawdown(values, config.account_equity),
            "start": selected[0].date, "end": selected[-1].date}


def report(assets, histories, metadata, config, start, end):
    signals, warm = discover_signals(assets, histories, config, start, end)
    spy = histories.get("SPY", [])
    if not spy or spy[-1].date != end:
        raise ValueError("Latest benchmark session is missing")
    current = sum(bool(histories.get(a.symbol)) and histories[a.symbol][-1].date == end for a in assets)
    if current < len(assets) * .9:
        raise ValueError("Latest session coverage below 90 percent")
    result = simulate_portfolio(histories, signals, config, start, end, [b.date for b in spy])
    result.update({"benchmark": benchmark(spy, config, start, end),
                   "metadata": metadata, "config": config.to_dict(),
                   "scope": "shared_cash_portfolio", "assets": len(assets),
                   "assets_with_warmup_at_start": warm,
                   "limitations": ["Current active universe: survivorship bias and heuristic instrument classification.",
                                   "Split-adjusted 1Day bars; no dividends, interest, tax or FX effects.",
                                   "Daily close drawdown does not measure intraday drawdown.",
                                   "Missing position bars retain the last mark; stale sessions are counted.",
                                   "No MACD sell signal: exits are initial stop, 2R target and 20-bar time exit.",
                                   "Open positions marked at final close; no invented final liquidation.",
                                   "Same-day cash proceeds assumed immediately reusable; broker settlement is not modeled.",
                                   "Not an out-of-sample or optimized strategy result."]})
    return result


def markdown(result):
    s, b, c = result["stats"], result["benchmark"], result["config"]
    pct = lambda v: f"{100 * v:.2f}%" if v is not None else "n/a"
    rows = [("Startkapital (USD)", f"{s['initial_usd']:,.2f}"),
            ("Slutvärde inklusive öppna innehav (USD)", f"{s['final_usd']:,.2f}"),
            ("Nettoresultat (USD)", f"{s['net_profit_usd']:,.2f}"),
            ("Avkastning", pct(s["return"])), ("CAGR", pct(s["cagr"])),
            ("Största nedgång från topp, dagsstängningar", pct(s["max_drawdown"])),
            ("Stängda affärer", s["closed_trades"]), ("Öppna innehav", s["open_positions"]),
            ("Träffandel stängda affärer", pct(s["win_rate"])),
            ("Profit factor, netto-USD", f"{s['profit_factor']:.3f}" if s["profit_factor"] is not None else "n/a"),
            ("Realiserat resultat (USD)", f"{s['realized_pnl_usd']:,.2f}"),
            ("Orealiserat resultat efter entrykostnader (USD)", f"{s['unrealized_pnl_usd']:,.2f}"),
            ("Genomsnittlig kapitalexponering", pct(s["average_exposure"])),
            ("Courtage (USD)", f"{s['commission_usd']:,.2f}"),
            ("Modellerad slippage (USD)", f"{s['slippage_usd']:,.2f}"),
            ("SPY kursavkastning utan utdelningar", pct(b["return"])),
            ("SPY största nedgång, dagsstängningar", pct(b["max_drawdown"]))]
    out = ["# Portföljbacktest – breakout + volym + MACD", "",
           f"Period: **{result['start']} – {result['end']}**, {s['sessions']} sessioner.", "",
           "| Mått | Resultat |", "| --- | ---: |"]
    out += [f"| {k} | {v} |" for k, v in rows]
    out += ["", f"Universum: {result['assets']} nuvarande instrument; {result['assets_with_warmup_at_start']} hade minst {c['min_history']} candles vid periodstart.", "",
            f"Riskbudget {pct(c['risk_fraction'])} av aktuellt eget kapital per affär; högst {pct(c['max_position_fraction'])} per position. Ingen belåning. Hela aktier.", "",
            f"Entry vid nästa sessions öppning efter avslutad breakoutsignal. Slippage {c['slippage_bps']:g} baspunkter per sida; courtage ${c['commission_per_share']:g}/aktie per sida.", "",
            f"Exit vid stop under basen, mål {c['reward_risk']:g}R eller {c['max_holding_bars']} candles. Stop prioriteras om stop och mål träffas i samma candle. Ingen separat MACD-säljsignal.", "",
            "Rangordning: föregående stängnings poäng, relativ volym, lägst ATR-extension, sedan ticker. Intradagsförsäljningar kan inte finansiera samma dags öppningsköp.", "",
            f"Exitfördelning: `{json.dumps(s['exit_reasons'], sort_keys=True)}`.", "",
            f"Överhoppade entries: `{json.dumps(s['skipped'], sort_keys=True)}`. Innehavssessioner utan kurs: {s['stale_position_sessions']}.", "",
            "## Avkastning per kalenderår (första och sista är delår)", "",
            "| Period | Avkastning |", "| --- | ---: |"]
    out += [f"| {v['start']} – {v['end']} | {pct(v['return'])} |" for v in s["annual_returns"].values()]
    out += ["", "## Begränsningar", ""] + [f"- {v}" for v in result["limitations"]]
    out += ["", "Resultatet gäller denna regeluppsättning och datamängd. Överlevnadsbias innebär att det inte är ett historiskt komplett börstest.", ""]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--output", default="dist/portfolio")
    args = parser.parse_args()
    if not 1 <= args.years <= 5 or not math.isfinite(args.capital) or args.capital <= 0:
        parser.error("Use 1–5 test years and positive finite capital")
    from .providers import Alpaca
    from .pages import derive_key, json_bytes, ITERATIONS
    from base64 import b64encode
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    passphrase = os.environ.get("DASHBOARD_PASSPHRASE", "")
    salt = os.urandom(16)
    key = derive_key(passphrase, salt)  # Validate before downloading.
    config = replace(Config.from_dict(json.loads(Path("config.json").read_text())), account_equity=args.capital)
    assets, histories, metadata = Alpaca("sip").dataset(years=args.years + 1)
    end_day = date.fromisoformat(metadata["as_of"])
    try:
        start_day = end_day.replace(year=end_day.year - args.years)
    except ValueError:
        start_day = end_day.replace(year=end_day.year - args.years, day=28)
    result = report(assets, histories, metadata, config, start_day.isoformat(), end_day.isoformat())
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    # Only aggregated simulated-account statistics are public. Individual
    # fills, instruments and data remain in an authenticated encrypted file.
    nonce = os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, json_bytes(result), b"portfolio-report-v1")
    envelope = {"schema": 1, "aad": "portfolio-report-v1", "iterations": ITERATIONS,
                "salt": b64encode(salt).decode(), "nonce": b64encode(nonce).decode(),
                "ciphertext": b64encode(encrypted).decode()}
    (output / "personal-report.encrypted.json").write_bytes(json_bytes(envelope))
    public = {k: result[k] for k in ("start", "end", "stats", "benchmark", "assets",
                                      "assets_with_warmup_at_start", "scope", "config", "limitations", "equity_curve")}
    (output / "summary.json").write_bytes(json_bytes(public))
    md = markdown(result)
    (output / "report.md").write_text(md, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    print("PORTFOLIO_RESULT=" + json.dumps({k: public[k] for k in public if k != "equity_curve"}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
