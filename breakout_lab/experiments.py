"""Nine controlled strategy experiments on one immutable free Alpaca dataset."""
from base64 import b64encode
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import argparse
import json
import math
import os
import struct

from .engine import evaluate
from .indicators import calculate, sma
from .models import Config
from .portfolio import benchmark, simulate_portfolio

# Known identity discontinuities are removed equally from every experiment.
QUARANTINE = {
    "WOLF": "Legacy shares cancelled and exchanged on 2025-09-29; no corporate-action ledger.",
    "RNA": "Ticker reused for Atrium in February 2026; no historical security-ID mapping.",
}
VARIANTS = (
    {"id": "reference", "label": "Referens: risk 0,5 %, max 15 %", "signals": "baseline", "allocation": "risk_budget", "exit": "initial"},
    {"id": "size10", "label": "10 % kapital per köp", "signals": "baseline", "allocation": "fixed_fraction", "fraction": .10, "exit": "initial"},
    {"id": "size25", "label": "25 % kapital per köp", "signals": "baseline", "allocation": "fixed_fraction", "fraction": .25, "exit": "initial"},
    {"id": "size100", "label": "100 % i en aktie", "signals": "baseline", "allocation": "all_in", "exit": "initial"},
    {"id": "golden_trend", "label": "Referens + SMA50 över SMA200", "signals": "golden_trend", "allocation": "risk_budget", "exit": "initial"},
    {"id": "golden_recent", "label": "Referens + golden cross senaste 20", "signals": "golden_recent", "allocation": "risk_budget", "exit": "initial"},
    {"id": "no_macd", "label": "Referens utan MACD-köpfilter", "signals": "no_macd", "allocation": "risk_budget", "exit": "initial"},
    {"id": "macd_exit", "label": "Referens + MACD-exit", "signals": "baseline", "allocation": "risk_budget", "exit": "macd"},
    {"id": "atr_trailing", "label": "Referens + flyttande 2 ATR-stop", "signals": "baseline", "allocation": "risk_budget", "exit": "atr_trailing"},
)


def golden_states(fast, slow, recent_bars=20):
    """Return persistent trend and recent actual cross; no future observations."""
    trend, recent, last_cross = [], [], None
    for i, (f, s) in enumerate(zip(fast, slow)):
        above = f is not None and s is not None and f > s
        if above and i and fast[i-1] is not None and slow[i-1] is not None:
            if fast[i-1] <= slow[i-1]:
                last_cross = i
        trend.append(above)
        recent.append(above and last_cross is not None and i - last_cross < recent_bars)
    return trend, recent


def experiment_signals(assets, histories, config, start, end):
    if config.earnings_blackout_days or config.min_market_cap or config.allowed_sectors:
        raise ValueError("Historical metadata is required for these filters")
    groups = {key: defaultdict(list) for key in ("baseline", "no_macd", "golden_trend", "golden_recent")}
    warm = 0
    broad_config = replace(config, require_macd=False)
    for asset in assets:
        bars = [b for b in histories.get(asset.symbol, []) if b.date <= end]
        warm += int(any(b.date <= start for b in bars[config.min_history-1:]))
        ind = calculate(bars)
        trend, recent = golden_states(ind["sma50"], sma([b.close for b in bars], 200))
        for i in range(config.min_history-1, len(bars)):
            if bars[i].date < start:
                continue
            c = evaluate(asset, bars, broad_config, i, ind, historical=True)
            if c["status"] != "breakout":
                continue
            day = bars[i].date
            groups["no_macd"][day].append(c)
            if not config.require_macd or c["checks"]["macd"]:
                groups["baseline"][day].append(c)
                if trend[i]:
                    groups["golden_trend"][day].append(c)
                if recent[i]:
                    groups["golden_recent"][day].append(c)
    return groups, warm


def dataset_fingerprint(assets, histories):
    digest = sha256()
    digest.update(json.dumps([(a.symbol, a.name, a.kind, a.exchange) for a in assets],
                             ensure_ascii=False).encode())
    for symbol in sorted(histories):
        digest.update(symbol.encode() + b"\0")
        for b in histories[symbol]:
            digest.update(b.date.encode())
            digest.update(struct.pack("!5d", b.open, b.high, b.low, b.close, b.volume))
    return digest.hexdigest()


def anniversary(day, years):
    try:
        return day.replace(year=day.year-years)
    except ValueError:
        return day.replace(year=day.year-years, day=28)


def run_suite(assets, histories, metadata, config, start, end):
    excluded = sorted(set(config.excluded_symbols) | set(QUARANTINE))
    config = replace(config, excluded_symbols=tuple(excluded),
                     require_macd=True, risk_fraction=.005, max_position_fraction=.15)
    selected = [a for a in assets if a.symbol not in excluded]
    spy = histories.get("SPY", [])
    if not spy or spy[-1].date != end:
        raise ValueError("Latest benchmark session is missing")
    coverage = sum(bool(histories.get(a.symbol)) and histories[a.symbol][-1].date == end for a in selected)
    if coverage < .9 * len(selected):
        raise ValueError("Latest session coverage below 90 percent")
    sessions = [b.date for b in spy]
    print("EXPERIMENT_STAGE=Building shared signal groups", flush=True)
    signals, warm = experiment_signals(selected, histories, config, start, end)
    midpoint = anniversary(date.fromisoformat(end), 1).isoformat()
    windows = [("full", start, end)]
    if start < midpoint < end:
        windows += [("year1", start, (date.fromisoformat(midpoint)-timedelta(days=1)).isoformat()),
                    ("year2", midpoint, end)]
    results = []
    for variant in VARIANTS:
        periods = {}
        for name, first, last in windows:
            periods[name] = simulate_portfolio(
                histories, signals[variant["signals"]], config, first, last, sessions,
                variant["allocation"], position_fraction=variant.get("fraction"), exit_rule=variant["exit"])
        full = periods["full"]
        results.append({"variant": variant, "periods": periods})
        print("EXPERIMENT_VARIANT=" + json.dumps({"id": variant["id"], "stats": full["stats"]}), flush=True)
    return {"schema": 1, "start": start, "end": end, "capital_usd": config.account_equity,
            "timeframe": "1Day", "metadata": metadata, "dataset_sha256": dataset_fingerprint(selected, histories),
            "assets": len(selected), "assets_with_warmup_at_start": warm,
            "excluded_symbols": excluded, "quarantine_reasons": QUARANTINE,
            "config": config.to_dict(), "benchmark": benchmark(spy, config, start, end),
            "period_benchmarks": {name: benchmark(spy, config, first, last) for name, first, last in windows},
            "variants": results,
            "limitations": [
                "Current active universe: survivorship bias; historical delisted securities are absent.",
                "WOLF and RNA excluded from every variant because security continuity is unresolved. Other corporate actions are not comprehensively audited.",
                "Daily split-adjusted bars; no dividends, taxes, interest, FX or settlement restrictions.",
                "All nine variants share the same fetched data, ranking, initial capital and costs.",
                "Experiments were chosen after inspecting this period: year2 is a separate robustness check, NOT an untouched out-of-sample test.",
                "Each yearly check starts with new cash and no positions; yearly returns do not compound into the full result.",
                "No best-variant selection is deployed automatically; results are exploratory.",
                "Fixed 10/25/100 percent allocation bypasses the reference 0.5 percent risk budget. Reference sizing is a cap, not a fixed 15 percent purchase.",
                "MACD bearish crossover observed at a close exits at the next available open. Opening stop/target gaps take priority.",
                "ATR stop ratchets after each completed close and applies only to later sessions. Original 2R target and 20-bar time exit remain active.",
            ]}


def public_summary(result):
    public = {k: v for k, v in result.items() if k != "variants"}
    public["variants"] = [{"variant": r["variant"], "periods": {
        name: {k: p[k] for k in ("start", "end", "stats", "equity_curve")}
        for name, p in r["periods"].items()}} for r in result["variants"]]
    return public


def markdown(result):
    pct = lambda x: "n/a" if x is None else f"{100*x:.2f}%"
    out = ["# Nio strategisimuleringar", "", f"Period: **{result['start']} – {result['end']}**. Startkapital: **{result['capital_usd']:,.0f} USD**. 1D-candles.", "",
           f"Gemensamt universum: {result['assets']} instrument, {result['assets_with_warmup_at_start']} med uppvärmning vid start. Exkluderade: {', '.join(result['excluded_symbols'])}.", "",
           "| Test | Slutvärde USD | Avkastning | Max nedgång | Stängda affärer | Träffandel | Profit factor | Genomsnittlig exponering |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["variants"]:
        s = row["periods"]["full"]["stats"]
        pf = "n/a" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}"
        out.append(f"| {row['variant']['label']} | {s['final_usd']:,.2f} | {pct(s['return'])} | {pct(s['max_drawdown'])} | {s['closed_trades']} | {pct(s['win_rate'])} | {pf} | {pct(s['average_exposure'])} |")
    out += ["", f"SPY kursavkastning utan utdelningar: **{pct(result['benchmark']['return'])}**. Max nedgång: **{pct(result['benchmark']['max_drawdown'])}**.", "",
            "## Separata konton för varje år", "", "Varje år startar från samma kapital utan ärvda innehav. Detta visar stabilitet mellan perioder, men är ingen oberoende validering eftersom perioden redan granskats.", "",
            "| Test | År 1 avkastning | År 1 max nedgång | År 1 affärer | År 2 avkastning | År 2 max nedgång | År 2 affärer |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["variants"]:
        if "year1" not in row["periods"]:
            continue
        a, b = (row["periods"][p]["stats"] for p in ("year1", "year2"))
        out.append(f"| {row['variant']['label']} | {pct(a['return'])} | {pct(a['max_drawdown'])} | {a['closed_trades']} | {pct(b['return'])} | {pct(b['max_drawdown'])} | {b['closed_trades']} |")
    out += ["", "## Exakta skillnader", "",
            "1. Referens: breakout + volym + MACD. Riskbudget 0,5 % av aktuellt kapital, max 15 % position.",
            "2–4. Samma köp och exits, men 10 %, 25 % respektive hela tillgängliga kapitalet per köp. Hela aktier, reserverat courtage, ingen belåning. 10/25 % kan hålla flera aktier; 100 % håller en.",
            "5. Referens plus SMA50 > SMA200 vid signalstängningen. Detta är ett trendläge, inte ett nytt kors varje dag.",
            "6. Referens plus ett faktiskt kors: SMA50 går från <= SMA200 till > SMA200 inom de senaste 20 candles, och ligger fortfarande över.",
            "7. Referens utan obligatorisk MACD-bekräftelse vid köp. MACD:s ursprungliga poängvikt behålls så rangordningen hålls konstant.",
            "8. Referens plus exit när MACD korsar signallinjen nedåt. Signal vid stängning, försäljning vid nästa öppning.",
            "9. Referens plus stop = max(tidigare stop, close − 2 × ATR14), uppdaterad efter stängning för nästa session.", "",
            "Samtliga behåller ursprungligt vinstmål 2R, tidsgräns 20 candles, stopprioritet vid tvetydig OHLC och samma entrygapfilter. Grundstrategin på hemsidan ändras inte av denna jämförelse.", "",
            "## Kostnader och datakontroll", "",
            f"Slippage: {result['config']['slippage_bps']:g} baspunkter per sida. Courtage: {result['config']['commission_per_share']:g} USD per aktie och sida.", "",
            f"Dataset SHA256: `{result['dataset_sha256']}`", "",
            "Detaljerade affärer är krypterade med befintlig dashboard-passphrase. Publik JSON innehåller endast inställningar och aggregerade kontoutfall.", "",
            "## Begränsningar", ""]
    out += [f"- {item}" for item in result["limitations"]]
    out += ["", "Källor för gemensam karantän: [WOLF SEC 8-K](https://www.sec.gov/Archives/edgar/data/895419/000119312525223057/d69265d8k.htm) och [Nasdaq RNA symbol reuse](https://nasdaqtrader.com/TraderNews.aspx?id=DTN2026-2).", ""]
    return "\n".join(out)


def save(result, output, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from .pages import derive_key, json_bytes, ITERATIONS
    salt, nonce = os.urandom(16), os.urandom(12)
    key = derive_key(passphrase, salt)
    aad = "strategy-experiments-v1"
    encrypted = AESGCM(key).encrypt(nonce, json_bytes(result), aad.encode())
    envelope = {"schema": 1, "aad": aad, "iterations": ITERATIONS, "salt": b64encode(salt).decode(),
                "nonce": b64encode(nonce).decode(), "ciphertext": b64encode(encrypted).decode()}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "personal-report.encrypted.json").write_bytes(json_bytes(envelope))
    (output / "summary.json").write_bytes(json_bytes(public_summary(result)))
    md = markdown(result)
    (output / "report.md").write_text(md, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    logged = public_summary(result)
    for row in logged["variants"]:
        for period in row["periods"].values():
            period.pop("equity_curve")
    print("EXPERIMENT_RESULT=" + json.dumps(logged, allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--output", default="dist/experiments")
    args = parser.parse_args()
    if not 2 <= args.years <= 3 or not math.isfinite(args.capital) or args.capital <= 0:
        parser.error("Use 2–3 years and positive finite capital")
    from .providers import Alpaca
    from .pages import derive_key
    passphrase = os.environ.get("DASHBOARD_PASSPHRASE", "")
    derive_key(passphrase, os.urandom(16))
    config = replace(Config.from_dict(json.loads(Path("config.json").read_text())), account_equity=args.capital)
    print("EXPERIMENT_STAGE=Downloading one shared dataset", flush=True)
    assets, histories, metadata = Alpaca("sip").dataset(years=args.years+1)
    end = date.fromisoformat(metadata["as_of"])
    result = run_suite(assets, histories, metadata, config, anniversary(end, args.years).isoformat(), end.isoformat())
    save(result, args.output, passphrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
