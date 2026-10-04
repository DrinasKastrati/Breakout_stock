"""Predeclared size/momentum research, ten holdings maximum, no orders."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from statistics import mean

from .concentrated import apply_identity_starts, audit_moves, drawdown_details, validate_caps
from .experiments import QUARANTINE, anniversary, dataset_fingerprint
from .models import Config
from .portfolio import benchmark, discover_signals, drawdown, simulate_portfolio
from .research import assess, curve_diagnostics, download_dataset, period_windows, save, trade_diagnostics


def variants():
    return [{"id": f"{family}_{suffix}", "label": f"{label}: {size_label}",
             "family": family, "min_market_cap_usd": threshold,
             "max_positions_limit": 10,
             "allocation": "risk_budget" if family == "breakout" else "fixed_fraction",
             "position_fraction": None if family == "breakout" else .10}
            for family, label in (("breakout", "Breakout"), ("momentum", "Månadsvis momentum"))
            for suffix, size_label, threshold in (("unfiltered", "utan börsvärdesfilter", 0),
                ("gt1b", "över 1 miljard USD", 1_000_000_000),
                ("gt5b", "över 5 miljarder USD", 5_000_000_000))]


def month_ends(sessions):
    # The next calendar session establishes whether a month is complete;
    # no future price enters a signal. The final partial month is excluded.
    days = sorted(set(sessions))
    return [a for a, b in zip(days, days[1:]) if a[:7] != b[:7]]


def momentum_signals(assets, histories, config, start, end):
    months = month_ends(b.date for b in histories["SPY"])
    decisions = {day: (months[j-1], months[j-7], months[j-13])
                 for j, day in enumerate(months) if j >= 13 and start <= day <= end}
    groups = {day: [] for day in decisions}  # Empty month means move to cash.
    for asset in assets:
        if asset.symbol in config.excluded_symbols:
            continue
        bars = histories.get(asset.symbol, [])
        indexed = {b.date: (i, b) for i, b in enumerate(bars)}
        for day, anchors in decisions.items():
            if day not in indexed or any(a not in indexed for a in anchors):
                continue
            i, current = indexed[day]
            if i + 1 < config.min_history or current.close < config.min_price:
                continue
            previous = bars[i-config.lookback:i]
            volume = mean(b.close * b.volume for b in previous)
            if volume < config.min_dollar_volume:
                continue
            recent, six, twelve = [indexed[a][1].close for a in anchors]
            score = .5 * (recent / six - 1 + recent / twelve - 1)
            if score > 0:
                groups[day].append({"symbol": asset.symbol, "date": day,
                                    "score": score, "dollar_volume": volume})
    return {day: sorted(rows, key=lambda c: (-c["score"], c["symbol"]))
            for day, rows in groups.items()}


def load_market_caps(path):
    if not path:
        return None, {"status": "unavailable", "reason": "No point-in-time historical market-cap dataset supplied"}
    content = Path(path).read_bytes()
    data = json.loads(content)
    if (data.get("schema") != 1 or data.get("currency") != "USD" or
            data.get("point_in_time") is not True or not isinstance(data.get("source"), str) or
            not data["source"].strip() or not isinstance(data.get("records"), list)):
        raise ValueError("Market-cap data needs schema=1, USD, source, point_in_time=true and records")
    records = {}
    for row in data["records"]:
        day, available = row["date"], row["available_on"]
        date.fromisoformat(day); date.fromisoformat(available)
        cap = row["market_cap_usd"]
        symbol = row["symbol"]
        if (not isinstance(symbol, str) or not symbol or isinstance(cap, bool) or
                not isinstance(cap, (int, float)) or not math.isfinite(cap) or cap <= 0):
            raise ValueError("Invalid historical market-cap record")
        key = (symbol, day)
        if key in records:
            raise ValueError("Duplicate historical market-cap observation; resolve data vintages first")
        records[key] = {"available_on": available, "value": cap}
    return records, {"status": "supplied", "source": data["source"], "records": len(records),
                     "sha256": sha256(content).hexdigest(), "currency": "USD",
                     "policy": "Exact signal date; available_on <= signal date; no forward fill"}


def filter_size(signals, threshold, records):
    if not threshold:
        return signals, {"required": False, "status": "not_required"}
    if records is None:
        return None, {"required": True, "status": "blocked", "reason": "Historical market caps unavailable"}
    output, missing, candidates, eligible = {}, 0, 0, 0
    for day, rows in signals.items():
        output[day] = []
        for candidate in rows:
            candidates += 1
            observation = records.get((candidate["symbol"], day))
            if observation is None or observation["available_on"] > day:
                missing += 1
            elif observation["value"] > threshold:
                output[day].append(candidate)
                eligible += 1
    coverage = {"required": True, "candidate_observations": candidates,
                "missing_or_not_yet_available": missing, "eligible_observations": eligible}
    if missing:
        return None, {**coverage, "status": "blocked", "reason": "Incomplete point-in-time coverage; no restricted-universe substitute"}
    return output, {**coverage, "status": "complete"}


def simulate_momentum(histories, signals, config, start, end, sessions):
    """Monthly top-ten membership; 10% opening equity for each new holding.

    Existing holdings are retained without resizing until they leave the
    top ten. No daily stop, target or time exit. Missing opening bars freeze
    existing positions and occupy slots; replacements never exceed ten.
    """
    days = sorted({d for d in sessions if start <= d <= end})
    if not days:
        raise ValueError("No benchmark sessions in the requested test period")
    symbols = {c["symbol"] for rows in signals.values() for c in rows[:10]}
    indexed = {s: {b.date: b for b in histories.get(s, [])} for s in symbols}
    initial = cash = config.account_equity
    slip, commission = config.slippage_bps / 10_000, config.commission_per_share
    positions, trades, curve = {}, [], []
    costs, skipped = Counter(), Counter()
    max_positions = stale = rebalances = 0
    pending = None
    for day in days:
        for symbol, p in positions.items():
            b = indexed[symbol].get(day)
            p["holding_bars"] += 1
            if b:
                p["mark"] = b.open
        if pending is not None:
            rebalances += 1
            desired = pending[:10]
            names = {c["symbol"] for c in desired}
            # All sales occur at this open before opening purchases.
            for symbol in sorted(set(positions) - names):
                b = indexed[symbol].get(day)
                if not b:
                    skipped["missing_exit_open"] += 1
                    continue
                p = positions.pop(symbol)
                fill, fee = b.open * (1-slip), p["shares"] * commission
                cash += p["shares"] * fill - fee
                costs["commission"] += fee
                costs["slippage"] += p["shares"] * (b.open-fill)
                trades.append({**p, "exit_date": day, "exit": fill, "exit_reason": "monthly_rank",
                    "pnl_usd": p["shares"] * (fill-p["entry"]) - p["entry_fee"] - fee,
                    "r_multiple": None})
            equity = cash + sum(p["shares"]*p["mark"] for p in positions.values())
            budget = .10 * equity
            for c in desired:
                symbol = c["symbol"]
                if symbol in positions:
                    continue
                if len(positions) >= 10:
                    skipped["position_limit"] += 1
                    continue
                b = indexed[symbol].get(day)
                if not b:
                    skipped["missing_entry_open"] += 1
                    continue
                fill = b.open * (1+slip)
                shares = min(math.floor(budget/fill), math.floor(max(0, cash)/(fill+commission)))
                if shares < 1:
                    skipped["cash_or_size"] += 1
                    continue
                fee = shares * commission
                cash -= shares*fill + fee
                costs["commission"] += fee
                costs["slippage"] += shares*(fill-b.open)
                positions[symbol] = {"symbol": symbol, "signal_date": c["date"], "entry_date": day,
                    "entry": fill, "entry_fee": fee, "shares": shares, "mark": b.open,
                    "holding_bars": 1}
        max_positions = max(max_positions, len(positions))
        for symbol, p in positions.items():
            b = indexed[symbol].get(day)
            if b:
                p["mark"] = b.close
            else:
                stale += 1
        if cash < -1e-6 or len(positions) > 10:
            raise AssertionError("Momentum holding/cash limit violated")
        cash = max(0, cash)
        invested = sum(p["shares"]*p["mark"] for p in positions.values())
        curve.append({"date": day, "equity_usd": cash+invested, "cash_usd": cash,
                      "invested_usd": invested, "positions": len(positions)})
        pending = signals.get(day)  # [] is a deliberate next-open liquidation.
    final = curve[-1]["equity_usd"]
    pnls = [t["pnl_usd"] for t in trades]
    wins, losses = sum(p for p in pnls if p > 0), -sum(p for p in pnls if p < 0)
    annual, previous = {}, initial
    for year in sorted({r["date"][:4] for r in curve}):
        rows = [r for r in curve if r["date"].startswith(year)]
        ending = rows[-1]["equity_usd"]
        annual[year] = {"start": rows[0]["date"], "end": rows[-1]["date"], "return": ending/previous-1}
        previous = ending
    elapsed = (date.fromisoformat(end)-date.fromisoformat(start)).days
    stats = {"initial_usd": initial, "final_usd": final, "net_profit_usd": final-initial,
        "return": final/initial-1, "cagr": (final/initial)**(365.25/elapsed)-1 if elapsed and final > 0 else None,
        "max_drawdown": drawdown([r["equity_usd"] for r in curve], initial),
        "closed_trades": len(trades), "open_positions": len(positions),
        "win_rate": sum(p > 0 for p in pnls)/len(pnls) if pnls else None,
        "profit_factor": wins/losses if losses else None,
        "realized_pnl_usd": sum(pnls), "unrealized_pnl_usd": final-initial-sum(pnls),
        "cash_usd": cash, "max_positions": max_positions,
        "average_exposure": mean(r["invested_usd"]/r["equity_usd"] if r["equity_usd"] > 0 else 0 for r in curve),
        "commission_usd": costs["commission"], "slippage_usd": costs["slippage"],
        "exit_reasons": dict(Counter(t["exit_reason"] for t in trades)),
        "signals": sum(len(signals.get(d, [])) for d in days),
        "unfilled_final_session_signals": len(pending) if pending is not None else 0,
        "skipped": dict(skipped), "stale_position_sessions": stale, "annual_returns": annual,
        "sessions": len(days), "monthly_rebalances": rebalances}
    result = {"start": start, "end": end, "allocation": "fixed_fraction", "stats": stats,
              "equity_curve": curve, "trades": trades, "open_positions": list(positions.values())}
    # Independent accounting check includes entry fees on still-open holdings.
    open_pnl = sum(p["shares"]*(p["mark"]-p["entry"])-p["entry_fee"] for p in positions.values())
    if not math.isclose(sum(pnls)+open_pnl, final-initial, abs_tol=1e-5):
        raise AssertionError("Momentum P/L does not reconcile to equity")
    return result


def run_study(assets, histories, metadata, config, start, end, records=None, cap_metadata=None):
    if config.min_market_cap or config.allowed_sectors or config.earnings_blackout_days:
        raise ValueError("This study uses its explicit historical filters, not current asset metadata")
    spy = histories.get("SPY", [])
    if not spy or spy[-1].date != end:
        raise ValueError("Latest benchmark session is missing")
    if sum(bool(histories.get(a.symbol)) and histories[a.symbol][-1].date == end for a in assets) < .9*len(assets):
        raise ValueError("Latest equity coverage below 90 percent")
    manifest = variants()
    breakout, warm = discover_signals(assets, histories, config, start, end)
    momentum = momentum_signals(assets, histories, config, start, end)
    groups, results, matrix = {"breakout": breakout, "momentum": momentum}, [], []
    windows, sessions = period_windows(start, end), [b.date for b in spy]
    for v in manifest:
        signals, coverage = filter_size(groups[v["family"]], v["min_market_cap_usd"], records)
        if signals is None:
            matrix.append({"variant": v, "status": "blocked", "coverage": coverage})
            print("SELECTION_BLOCKED="+json.dumps({"id": v["id"], **coverage}), flush=True)
            continue
        def simulate(first, last, cfg):
            if v["family"] == "momentum":
                return simulate_momentum(histories, signals, cfg, first, last, sessions)
            return simulate_portfolio(histories, signals, cfg, first, last, sessions, max_positions_limit=10)
        periods = {name: simulate(first, last, config) for name, (first, last) in windows.items()}
        stress = simulate(start, end, replace(config, slippage_bps=30))
        row = {"variant": v, "config": config.to_dict(), "periods": periods, "stress": stress,
               "diagnostics": trade_diagnostics(periods["full"]),
               "curve_diagnostics": curve_diagnostics(periods["full"]),
               "drawdown_details": drawdown_details(periods["full"]), "market_cap_coverage": coverage}
        row["assessment"] = assess(row)
        results.append(row)
        matrix.append({"variant": v, "status": "completed", "coverage": coverage})
        print("SELECTION_VARIANT="+json.dumps({"id": v["id"], "return": periods["full"]["stats"]["return"],
              "drawdown": periods["full"]["stats"]["max_drawdown"], "passed": row["assessment"]["passed"]}), flush=True)
    result = {"schema": 1, "study": "selection-20261004", "start": start, "end": end,
        "capital_usd": config.account_equity, "timeframe": "1Day", "metadata": metadata,
        "assets": len(assets), "assets_with_warmup_at_start": warm, "config": config.to_dict(),
        "windows": windows, "dataset_sha256": dataset_fingerprint(assets, histories),
        "manifest_sha256": sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "planned_variants": manifest, "execution_matrix": matrix, "market_cap_data": cap_metadata or {},
        "benchmark": benchmark(spy, config, start, end), "variants": results,
        "limitations": [
            "Current active stock universe; delisted stocks are missing. Survivorship bias remains, especially important for long-term momentum.",
            "Historical dates were previously inspected; reset years/recent periods are not genuinely untouched validation.",
            "Split/spin-off-adjusted prices are normalized research data, not a full security and cash ledger. No cash dividends, tax, interest, FX or settlement constraints.",
            "BHVN starts as a new security on 2022-10-04 with fresh warmup. WOLF/RNA are excluded as in prior studies; complete corporate-action audit is outstanding.",
            "Breakout uses 0.5% modeled stop risk and max 15% per entry; momentum uses 10% of opening equity per new holding and no daily stop. Different exposure/risk policies prevent attributing return differences solely to stock ranking.",
            "Momentum retains existing holdings without resizing; weights can exceed 10% after price changes. Ten holdings is a count limit, not a loss limit.",
            "Missing holding bars carry the last mark; missing monthly opening bars freeze the holding and occupy a slot. Stale sessions are counted.",
            "Size filters require complete candidate coverage at each exact signal date and known availability dates. Current market caps and forward-filled approximations are not substitutes.",
            "Signals for the first buy must form within each test window. Reset accounts start in cash and do not inherit earlier monthly selections.",
            "Daily close drawdown and fixed slippage do not capture intraday risk or variable market impact. No live-strategy promotion or orders."]}
    validate_caps(result)
    return result


def markdown(result):
    pct = lambda x: "n/a" if x is None else f"{100*x:.2f}%"
    lines = ["# Börsvärde och månadsvis momentum: högst tio innehav", "",
        f"Period **{result['start']}–{result['end']}**. Startkapital **{result['capital_usd']:,.0f} USD**.", "",
        "Sex fördefinierade tester: två strategier × tre börsvärdesgränser. Blockerade tester har inga simulerade resultat.", "",
        "## Teststatus", "", "| Test | Status | Orsak |", "| --- | --- | --- |"]
    for cell in result["execution_matrix"]:
        lines.append(f"| {cell['variant']['label']} | {'Körd' if cell['status']=='completed' else 'Blockerad'} | {cell['coverage'].get('reason', 'Datakrav uppfyllda')} |")
    lines += ["", "## Resultat", "",
        "| Strategi | Totalavkastning | CAGR | Max nedgång | Högst innehav | Affärer | PF | Exponering | 30 bps/sida | Positiva år / 5 | Alla krav |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in result["variants"]:
        s = row["periods"]["full"]["stats"]
        pf = "n/a" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}"
        lines.append(f"| {row['variant']['label']} | {pct(s['return'])} | {pct(s['cagr'])} | {pct(s['max_drawdown'])} | {s['max_positions']} | {s['closed_trades']} | {pf} | {pct(s['average_exposure'])} | {pct(row['stress']['stats']['return'])} | {row['assessment']['positive_years']} | {'Ja' if row['assessment']['passed'] else 'Nej'} |")
    lines += ["", f"SPY utan utdelningar: **{pct(result['benchmark']['return'])}**, max nedgång **{pct(result['benchmark']['max_drawdown'])}**.", "",
        "## Regler fastställda före körningen", "",
        "Breakout behåller grundreglerna: föregående 20 dagars motstånd, 0,1 ATR breakoutbuffert, 1,5× volym, stigande SMA50 och MACD; nästa öppning, stop under bas, 2R och högst 20 candles. Risk 0,5 % per köp, max 15 % position vid köp, högst tio innehav. Inget nytt marknadsfilter.", "",
        "Momentum väljer vid varje avslutad börsmånad de tio högst rankade aktierna med positivt medelvärde av sex- och tolvmånaders avkastning. Den senaste månaden utelämnas: vid månad m används priser vid månadsslut m−1, m−7 och m−13. Minst 250 bars, kurs minst 5 USD och föregående 20 bars genomsnittliga dollaromsättning minst 20 MUSD. Lika poäng bryts alfabetiskt. Ingen information efter signalstängningen används i rangordningen.", "",
        "Månadsurvalet handlas vid nästa sessions öppning. Aktier som lämnar topp tio säljs först; nya innehav får högst 10 % av kontots eget kapital vid öppningen. Befintliga innehav behålls utan omviktning. Färre än tio positiva kandidater lämnar kontanter. Inga dagliga stoppar, vinstmål eller 20-dagars exits. Saknad öppningsbar låser befintligt innehav och upptar en plats. Taket tio gäller varje dag även då.", "",
        "Båda använder heltalsaktier, gemensam kassa utan belåning, 10 bps slippage per sida och 0,005 USD/aktie/sida; stress 30 bps. Slutliga innehav värderas vid stängning utan påhittad slutlikvidation. Risk och exponering skiljer sig mellan strategierna; en högre avkastning isolerar därför inte momentumregelns effekt.", "",
        "Börsvärdesgränserna är strikt >1 respektive >5 miljarder USD vid signalstängningen. Filtret tillämpas före rangordning. Historiska USD-värden måste täcka alla relevanta kandidater och ha available_on ≤ signaldatum; annars blockeras hela filtervarianten. Inga aktuella börsvärden används bakåt i tiden.", "",
        "Krav från tidigare studie bevaras som diagnostik: positiv totalavkastning, max 20 % nedgång, minst 100 affärer, PF ≥1,15, minst fyra positiva reset-år, positivt kostnadsstressresultat och fem största vinnare ≤50 % av bruttovinster. Gränsen 100 affärer kan missgynna långsammare strategier och är inte ett lönsamhetsbevis.", "",
        "## Separata årskonton och senaste två år", "",
        "Varje delkonto börjar i kontanter utan ärvda innehav; resultaten bildar inte hela kontots avkastning.", "",
        "| Strategi | År 1 | År 2 | År 3 | År 4 | År 5 | Senaste 2 år |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["variants"]:
        lines.append("| "+row["variant"]["id"]+" | "+" | ".join(pct(row["periods"][key]["stats"]["return"]) for key in ["year1","year2","year3","year4","year5","recent2"])+" |")
    lines += ["", "## Nedgång och koncentration", "",
        "| Strategi | Topp → botten | Värsta kontodag | Dagsavkastning | Fem största / bruttovinster | Saknade innehavsdagar |",
        "| --- | --- | --- | ---: | ---: | ---: |"]
    for row in result["variants"]:
        d, a = row["drawdown_details"], row["drawdown_details"]["decline"]
        span = f"{a['peak_date']} → {a['trough_date']}" if a else "Ingen nedgång"
        lines.append(f"| {row['variant']['id']} | {span} | {d['worst_day']['date']} | {pct(d['worst_day']['return'])} | {pct(row['diagnostics']['top5_share_of_gross_wins'])} | {row['periods']['full']['stats']['stale_position_sessions']} |")
    lines += ["", "## Data och spårbarhet", "",
        f"{result['assets']} nu aktiva stamaktier; {result['assets_with_warmup_at_start']} med uppvärmning vid start. Alpaca SIP adjustment=split,spin-off och samma identitetskontroller som den senaste koncentrerade studien. Genuina kursras behålls; stora rörelser flaggas endast i den krypterade granskningen.", "",
        f"Dataset SHA256: `{result['dataset_sha256']}`. Sexdelat manifest SHA256: `{result['manifest_sha256']}`.", "",
        "Aggregerade kontokurvor och status finns i summary.json. Enskilda affärer, månadsrankning och eventuell börsvärdesdata finns endast i krypterad personal-report.encrypted.json.", "",
        "Forskningsgrund: [Kenneth French momentum](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html). Den publicerade faktorn är ett annat portföljupplägg och bevisar inte denna strategis lönsamhet.", "",
        "## Begränsningar", ""]
    lines += ["- "+s for s in result["limitations"]]
    return "\n".join(lines)+"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--output", default="dist/selection")
    parser.add_argument("--market-caps", help="Point-in-time USD market caps in the documented JSON schema")
    args = parser.parse_args()
    if not math.isfinite(args.capital) or args.capital <= 0:
        parser.error("Capital must be positive and finite")
    from .pages import derive_key
    passphrase = os.environ.get("DASHBOARD_PASSPHRASE", "")
    derive_key(passphrase, os.urandom(16))
    base = Config.from_dict(json.loads(Path("config.json").read_text()))
    config = replace(base, account_equity=args.capital,
        excluded_symbols=tuple(sorted(set(base.excluded_symbols)|set(QUARANTINE))))
    records, cap_metadata = load_market_caps(args.market_caps)
    print("SELECTION_STAGE=Six variants fixed; max holdings=10", flush=True)
    assets, original, metadata = download_dataset(config, adjustment="split,spin-off")
    histories, removed = apply_identity_starts(original)
    metadata["identity_bars_removed"] = removed
    end = date.fromisoformat(metadata["as_of"])
    result = run_study(assets, histories, metadata, config, anniversary(end, 5).isoformat(),
                       end.isoformat(), records, cap_metadata)
    result["private_data_audit"] = {"large_moves": audit_moves(histories),
        "momentum_signals": momentum_signals(assets, histories, config, result["start"], result["end"]),
        "market_caps": json.loads(Path(args.market_caps).read_text()) if args.market_caps else None}
    save(result, args.output, passphrase, report_renderer=markdown)
    print(f"SELECTION_STAGE=Completed={len(result['variants'])}; blocked={6-len(result['variants'])}; all holding/cash checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
