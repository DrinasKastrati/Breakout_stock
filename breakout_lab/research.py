"""Predeclared five-year breakout research; read-only APIs, no order endpoints."""
from base64 import b64encode
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from statistics import mean, median, stdev
from urllib.request import Request, urlopen
import argparse
import csv
import io
import json
import math
import os
import re
import time

from .engine import evaluate
from .experiments import QUARANTINE, anniversary, dataset_fingerprint, golden_states
from .indicators import calculate, sma
from .models import Config
from .portfolio import benchmark, simulate_portfolio, phase_attribution, attribution_names

DIRECTORIES = (
    ("nasdaqlisted.txt", "Symbol"), ("otherlisted.txt", "ACT Symbol"),
)
COMMON = re.compile(r"\b(common\s+(?:stock|shares?)|ordinary\s+shares?|capital\s+stock)\b", re.I)
OTHER = re.compile(r"\b(etfs?|etns?|funds?|warrants?|preferred|deposit[ao]ry|units?|rights?|notes?|bonds?|debentures?)\b", re.I)


def parse_directory(content, symbol_field):
    reader = csv.DictReader(io.StringIO(content), delimiter="|")
    required = {symbol_field, "Security Name", "ETF", "Test Issue"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Nasdaq directory schema is missing required fields")
    records = {}
    for row in reader:
        symbol = (row.get(symbol_field) or "").strip()
        if not symbol or symbol.startswith("File Creation Time"):
            continue
        records[symbol] = {"name": row["Security Name"], "etf": row["ETF"], "test": row["Test Issue"]}
    return records


def official_directory(opener=urlopen):
    records, stamps = {}, {}
    for filename, field in DIRECTORIES:
        url = "https://www.nasdaqtrader.com/dynamic/SymDir/" + filename
        content = None
        for attempt in range(3):
            try:
                with opener(Request(url, headers={"User-Agent": "BreakoutResearch/1.0"}), timeout=30) as response:
                    content = response.read().decode("utf-8-sig")
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise ValueError("Official symbol directory could not be downloaded") from None
                time.sleep(attempt + 1)
        parsed = parse_directory(content, field)
        if len(parsed) < 1000:
            raise ValueError("Official symbol directory is unexpectedly small")
        records.update(parsed)
        stamps[filename] = next((line.split('|')[0] for line in content.splitlines()
                                 if line.startswith("File Creation Time")), "timestamp unavailable")
    return records, stamps


def filter_universe(assets, records, exclusions=()):
    selected, reasons = [], Counter()
    for asset in assets:
        r = records.get(asset.symbol)
        if asset.symbol in exclusions:
            reasons["quarantine"] += 1
        elif r is None:
            reasons["missing_official_record"] += 1
        elif r["etf"] != "N" or r["test"] != "N":
            reasons["etf_test_or_unknown_flag"] += 1
        elif OTHER.search(r["name"]) or not COMMON.search(r["name"]):
            reasons["not_explicit_common_or_ordinary_stock"] += 1
        elif asset.exchange not in ("NASDAQ", "NYSE", "AMEX", "NYSEAMERICAN", "ARCA", "BATS"):
            reasons["unsupported_exchange"] += 1
        elif asset.symbol != "SPY":
            selected.append(replace(asset, name=r["name"], kind="common", classification="curated"))
    return sorted(selected, key=lambda a: a.symbol), dict(reasons)


def download_dataset(config, years=5):
    from .providers import Alpaca
    provider = Alpaca("sip")
    now = datetime.now(timezone.utc)
    end = provider.completed_session(now)
    records, stamps = official_directory()
    assets, reasons = filter_universe(provider.assets(), records, config.excluded_symbols)
    if len(assets) < 1000:
        raise ValueError("Strict equity universe is unexpectedly small")
    print(f"RESEARCH_STAGE=Universe approved; assets={len(assets)}; exclusions={json.dumps(reasons)}", flush=True)
    first = (date.fromisoformat(end) - timedelta(days=365 * (years + 1) + 30)).isoformat()
    # Fetch one chunk at a time to expose progress without publishing raw market data.
    histories = {}
    symbols = [a.symbol for a in assets] + ["SPY"]
    for offset in range(0, len(symbols), 100):
        histories.update(provider.bars(symbols[offset:offset+100], first, end, now))
        print(f"RESEARCH_STAGE=Downloaded {min(offset+100,len(symbols))}/{len(symbols)} histories", flush=True)
    metadata = {"source": "alpaca", "feed": "sip", "adjustment": "split", "as_of": end,
                "synced_at": now.isoformat(), "synthetic": False, "bar_definition": "provider_1Day",
                "official_directory_stamps": stamps, "universe_exclusion_counts": reasons,
                "universe_policy": "Current Nasdaq ETF=N and Test Issue=N, explicit common/ordinary/capital stock; excludes other instrument words."}
    return assets, histories, metadata


def variants():
    items = []
    def add(identifier, label, family="baseline", **options):
        items.append({"id": identifier, "label": label, "family": family, **options})
    controls = {"max_positions_limit": 10, "max_portfolio_risk": .02,
                "max_exposure": .80, "position_cap": .10}
    combo = {"golden": 20, "market": True, "rs": True, "quality": True,
             "rank": "rs", **controls}
    add("reference", "Grundstrategi")
    add("all_in", "Grundstrategi, 100 %", allocation="all_in")
    add("golden", "Golden cross 20", golden=20)
    add("market", "SPY över stigande SMA200", market=True)
    add("rs", "Relativ styrka 63 dagar", rs=True, rank="rs")
    add("golden_market", "Golden cross + marknad", golden=20, market=True)
    add("golden_rs", "Golden cross + relativ styrka", golden=20, rs=True, rank="rs")
    add("golden_market_rs", "Golden cross + marknad + RS", golden=20, market=True, rs=True, rank="rs")
    add("quality", "Likviditet och volatilitet", quality=True)
    add("risk_cap", "Begränsad portföljrisk", **controls)
    add("market_risk", "Marknad + portföljrisk", market=True, **controls)
    add("golden_market_risk", "Golden cross + marknad + risk", golden=20, market=True, **controls)
    add("combo", "Kombination: golden/marknad/RS/kvalitet/risk", **combo)
    add("combo_market_exit", "Kombination + exit vid svag marknad", **combo, liquidate_when_market_off=True)
    add("combo_failure", "Kombination + misslyckad breakout", **combo, failure_exit=True)
    add("combo_hold40", "Kombination, 40 dagars innehav", **combo, holding=40)
    add("combo_target3", "Kombination, mål 3R", **combo, reward=3)
    add("combo_tight", "Kombination, 2 ATR initial stop", **combo, entry_stop_atr=2)
    add("combo_half_risk", "Kombination, risk 0,25 %", **{**combo, "max_portfolio_risk": .01}, risk=.0025)
    add("combo_fixed10", "Kombination, 10 % kapital per köp", **combo, allocation="fixed_fraction", fraction=.10)
    add("combo_all_in", "Kombination, 100 % kontroll", **{k:v for k,v in combo.items() if k not in controls}, allocation="all_in")
    add("combo_golden10", "Kombination, golden cross 10", **{**combo, "golden":10})
    add("combo_golden40", "Kombination, golden cross 40", **{**combo, "golden":40})
    add("baseline_failure", "Grundstrategi + misslyckad breakout", failure_exit=True)
    add("golden_failure", "Golden cross + misslyckad breakout", golden=20, failure_exit=True)
    add("golden_market_failure", "Golden cross + marknad + snabb exit", golden=20, market=True, failure_exit=True, **controls)
    add("rs_market_failure", "RS + marknad + snabb exit", rs=True, rank="rs", market=True, failure_exit=True, **controls)
    add("combo_runner", "Kombination, låt vinnare löpa", **combo, holding=120, use_target=False, entry_stop_atr=2, exit_rule="atr_trailing", trailing_atr=3)
    add("no_macd_market", "Marknad + RS utan MACD", family="no_macd", market=True, rs=True, rank="rs", **controls)
    channel = {"holding":120, "use_target":False, "entry_stop_atr":2, "exit_rule":"channel10", **controls}
    add("channel55", "55-dagars breakout / 10-dagars exit", family="channel55", **channel)
    add("channel55_market", "55/10 + marknad", family="channel55", market=True, **channel)
    add("channel55_rs", "55/10 + relativ styrka", family="channel55", rs=True, rank="rs", **channel)
    add("channel55_combo", "55/10 + marknad + RS + kvalitet", family="channel55", market=True, rs=True, rank="rs", quality=True, **channel)
    add("channel55_trail2", "55-dagars breakout + 2 ATR trailing", family="channel55", market=True, rs=True, rank="rs", quality=True, **{**channel, "exit_rule":"atr_trailing", "trailing_atr":2})
    add("channel55_trail3", "55-dagars breakout + 3 ATR trailing", family="channel55", market=True, rs=True, rank="rs", quality=True, **{**channel, "exit_rule":"atr_trailing", "trailing_atr":3})
    add("channel55_half_risk", "55/10 kombination, halv risk", family="channel55", market=True, rs=True, rank="rs", quality=True, risk=.0025, **{**channel, "max_portfolio_risk":.01})
    return items


def market_states(bars):
    averages = sma([b.close for b in bars], 200)
    return {b.date: bool(i >= 219 and b.close > averages[i] and averages[i] > averages[i-20])
            for i,b in enumerate(bars)}


def build_signals(assets, histories, config, start, end):
    if config.earnings_blackout_days or config.min_market_cap or config.allowed_sectors:
        raise ValueError("Historical fundamental metadata is unavailable")
    groups = {f: defaultdict(list) for f in ("baseline", "no_macd", "channel55")}
    market = market_states(histories["SPY"])
    spy = {b.date: b.close for b in histories["SPY"]}
    configs = {"baseline": config, "channel55": replace(config, lookback=55, max_base_width_atr=15,
                 require_macd=False, require_volume=False, max_extension_atr=2)}
    warm = 0
    for number, asset in enumerate(assets):
        bars = histories.get(asset.symbol, [])
        warm += int(any(b.date <= start for b in bars[config.min_history-1:]))
        ind = calculate(bars)
        slow = sma([b.close for b in bars], 200)
        crosses = {n: golden_states(ind["sma50"], slow, n)[1] for n in (10,20,40)}
        broad = replace(config, require_macd=False)
        for i in range(config.min_history-1, len(bars)):
            b = bars[i]
            if not start <= b.date <= end:
                continue
            rs = None
            if i >= 63 and bars[i-63].date in spy and b.date in spy:
                rs = b.close/bars[i-63].close - spy[b.date]/spy[bars[i-63].date]
            extras = {"market_ok":market.get(b.date,False), "rs63":rs,
                      "golden_windows":[n for n in crosses if crosses[n][i]]}
            c = evaluate(asset, bars, broad, i, ind, historical=True)
            if c["status"] == "breakout":
                c.update(extras)
                c["atr_fraction"] = c["atr"]/b.close
                c["stop_fraction"] = (b.close-c["stop"])/b.close
                groups["no_macd"][b.date].append(c)
                if c["checks"]["macd"]:
                    groups["baseline"][b.date].append(c)
            c = evaluate(asset, bars, configs["channel55"], i, ind, historical=True)
            if c["status"] == "breakout" and slow[i] is not None and ind["sma50"][i] > slow[i]:
                c.update(extras)
                c["atr_fraction"] = c["atr"]/b.close
                c["stop_fraction"] = (b.close-c["stop"])/b.close
                groups["channel55"][b.date].append(c)
        if (number+1)%500 == 0:
            print(f"RESEARCH_STAGE=Built signals {number+1}/{len(assets)}",flush=True)
    return groups, warm


def choose_signals(groups, variant):
    signals = defaultdict(list)
    for day, candidates in groups[variant["family"]].items():
        for c in candidates:
            if variant.get("golden") and variant["golden"] not in c["golden_windows"]:
                continue
            if variant.get("market") and not c["market_ok"]:
                continue
            if variant.get("rs") and (c["rs63"] is None or c["rs63"] <= 0):
                continue
            if variant.get("quality") and (c["dollar_volume"] < 50_000_000 or c["atr_fraction"] > .06 or c["stop_fraction"] > .12):
                continue
            c = dict(c)
            if variant.get("rank") == "rs":
                c["score"] = c["rs63"] if c["rs63"] is not None else -1e9
            elif variant.get("rank") == "low_atr":
                c["score"] = -c["atr_fraction"]
            signals[day].append(c)
    return signals


def trade_diagnostics(result):
    trades, s = result["trades"], result["stats"]
    wins = sorted((t["pnl_usd"] for t in trades if t["pnl_usd"] > 0), reverse=True)
    losses = sorted((-t["pnl_usd"] for t in trades if t["pnl_usd"] < 0), reverse=True)
    grouped = defaultdict(list)
    for t in trades:
        grouped[t["exit_reason"]].append(t)
    normalized = [t["pnl_usd"]/(t["shares"]*t["entry"]+t["entry_fee"]) for t in trades]
    return {"average_win_usd":mean(wins) if wins else None,
            "average_loss_usd":mean(losses) if losses else None,
            "average_trade_return":mean(normalized) if normalized else None,
            "median_trade_return":median(normalized) if normalized else None,
            "average_holding_bars":mean(t["holding_bars"] for t in trades) if trades else None,
            "top5_share_of_gross_wins":sum(wins[:5])/sum(wins) if wins else None,
            "top5_share_of_gross_losses":sum(losses[:5])/sum(losses) if losses else None,
            "net_without_top5_winners_usd":s["net_profit_usd"]-sum(wins[:5]),
            "exit_pnl":{k:{"count":len(v),"net_pnl_usd":sum(t["pnl_usd"] for t in v)} for k,v in grouped.items()}}


def curve_diagnostics(result):
    curve, initial = result["equity_curve"], result["stats"]["initial_usd"]
    previous, daily = initial, []
    for row in curve:
        daily.append(row["equity_usd"]/previous-1)
        previous = row["equity_usd"]
    sd = stdev(daily) if len(daily)>1 else 0
    rolling = [curve[i+252]["equity_usd"]/curve[i]["equity_usd"]-1
               for i in range(0,len(curve)-252,21)]
    return {"sharpe_zero_cash_rate":mean(daily)/sd*math.sqrt(252) if sd else None,
            "annualized_volatility":sd*math.sqrt(252),
            "worst_rolling_252_sessions":min(rolling) if rolling else None,
            "best_rolling_252_sessions":max(rolling) if rolling else None,
            "positive_rolling_fraction":sum(v>0 for v in rolling)/len(rolling) if rolling else None,
            "rolling_windows":len(rolling),
            "worst_day":min(daily), "best_day":max(daily)}


def period_windows(start, end):
    last = date.fromisoformat(end)
    windows = {"full":(start,end)}
    for year in range(1,6):
        first = anniversary(last, 6-year)
        stop = last if year == 5 else anniversary(last, 5-year)-timedelta(days=1)
        windows[f"year{year}"] = (first.isoformat(),stop.isoformat())
    for length in (2,3,4):
        stop = anniversary(last,5-length)-timedelta(days=1)
        windows[f"train{length}"] = (start,stop.isoformat())
    windows["recent2"] = (anniversary(last,2).isoformat(),end)
    return windows


def assess(row):
    s = row["periods"]["full"]["stats"]
    yearly = [row["periods"][f"year{i}"]["stats"]["return"] for i in range(1,6)]
    checks = {"positive_full_return":s["return"]>0, "drawdown_at_most_20pct":s["max_drawdown"]<=.20,
              "at_least_100_closed_trades":s["closed_trades"]>=100,
              "profit_factor_at_least_1_15":s["profit_factor"] is not None and s["profit_factor"]>=1.15,
              "four_of_five_reset_years_positive":sum(v>0 for v in yearly)>=4,
              "positive_at_30bps_each_side":row["stress"]["stats"]["return"]>0,
              "top5_at_most_half_gross_wins":row["diagnostics"]["top5_share_of_gross_wins"] is not None and row["diagnostics"]["top5_share_of_gross_wins"]<=.5}
    return {"checks":checks, "passed":all(checks.values()),"positive_years":sum(v>0 for v in yearly),
            "calmar":s["cagr"]/s["max_drawdown"] if s["max_drawdown"] else None}


def walk_forward(rows):
    folds = []
    for length in (2,3,4):
        eligible = [r for r in rows if r["periods"][f"train{length}"]["stats"]["closed_trades"]>=20
                    and r["periods"][f"train{length}"]["stats"]["return"]>0
                    and r["periods"][f"train{length}"]["stats"]["max_drawdown"]<=.25]
        def score(row):
            s = row["periods"][f"train{length}"]["stats"]
            return s["cagr"]/max(.01,s["max_drawdown"])
        chosen = max(eligible,key=lambda r:(score(r),r["variant"]["id"])) if eligible else None
        year = length+1
        folds.append({"training":f"train{length}","evaluation":f"year{year}",
                      "selected":chosen["variant"]["id"] if chosen else "cash",
                      "training_score":score(chosen) if chosen else None,
                      "return":chosen["periods"][f"year{year}"]["stats"]["return"] if chosen else 0,
                      "drawdown":chosen["periods"][f"year{year}"]["stats"]["max_drawdown"] if chosen else 0})
    return {"folds":folds,"compounded_reset_fold_return":math.prod(1+f["return"] for f in folds)-1,
            "note":"Expanding training selects solely on past Calmar. Evaluation starts with fresh cash; all this historical data was previously inspected, so these folds are not genuinely untouched."}


def run_study(assets, histories, metadata, config, start, end, definitions=None):
    definitions = definitions or variants()
    spy = histories.get("SPY",[])
    if not spy or spy[-1].date != end:
        raise ValueError("Latest benchmark session is missing")
    if sum(bool(histories.get(a.symbol)) and histories[a.symbol][-1].date == end for a in assets)<.9*len(assets):
        raise ValueError("Latest equity coverage below 90 percent")
    groups,warm = build_signals(assets,histories,config,start,end)
    signal_symbols = {c["symbol"] for group in groups.values() for cs in group.values() for c in cs}
    indexed = {s:{b.date:b for b in histories[s]} for s in signal_symbols}
    cache, windows, results = {}, period_windows(start,end), []
    for v in definitions:
        signals = choose_signals(groups,v)
        settings = replace(config,risk_fraction=v.get("risk",.005),max_position_fraction=v.get("position_cap",.15),
                           max_holding_bars=v.get("holding",20),reward_risk=v.get("reward",2),
                           max_extension_atr=2 if v["family"]=="channel55" else config.max_extension_atr)
        options = {k:v[k] for k in ("failure_exit","max_positions_limit","max_portfolio_risk","max_exposure",
                                    "entry_stop_atr","trailing_atr","use_target","exit_rule") if k in v}
        if v.get("liquidate_when_market_off"):
            options["market_exit_dates"] = {day:not good for day,good in market_states(spy).items()}
        def simulate(first,last,cfg):
            return simulate_portfolio(histories,signals,cfg,first,last,[b.date for b in spy],
                v.get("allocation","risk_budget"),position_fraction=v.get("fraction"),
                bar_index=indexed,exit_event_cache=cache,**options)
        periods = {name:simulate(first,last,settings) for name,(first,last) in windows.items()}
        stressed = simulate(start,end,replace(settings,slippage_bps=30))
        row = {"variant":v,"config":settings.to_dict(),"periods":periods,"stress":stressed,
               "diagnostics":trade_diagnostics(periods["full"]),"curve_diagnostics":curve_diagnostics(periods["full"])}
        row["assessment"] = assess(row)
        row["attribution_names"] = attribution_names(phase_attribution(periods["full"],histories))
        results.append(row)
        print("RESEARCH_VARIANT="+json.dumps({"id":v["id"],"return":periods["full"]["stats"]["return"],
              "drawdown":periods["full"]["stats"]["max_drawdown"],"passed":row["assessment"]["passed"]}),flush=True)
    return {"schema":1,"start":start,"end":end,"capital_usd":config.account_equity,"timeframe":"1Day",
            "metadata":metadata,"assets":len(assets),"assets_with_warmup_at_start":warm,
            "config":config.to_dict(),"windows":windows,"dataset_sha256":dataset_fingerprint(assets,histories),
            "manifest_sha256":sha256(json.dumps(definitions,sort_keys=True).encode()).hexdigest(),
            "benchmark":benchmark(spy,config,start,end),
            "period_benchmarks":{name:benchmark(spy,config,*window) for name,window in windows.items()},
            "variants":results,"walk_forward":walk_forward(results),
            "limitations":["Current active universe and current security-type directory: historical delisted securities absent; survivorship bias remains.",
                "WOLF and RNA quarantined; no complete corporate-action/security-identity ledger. Other discontinuities remain possible.",
                "Split-adjusted daily OHLC; no dividends, tax, cash interest, FX or settlement restrictions.",
                "Study definitions fixed before this run, but prior exploration already inspected these dates. No genuinely untouched validation period.",
                "Reset-year/training/recent accounts start from 100k with no inherited holdings; their returns do not recreate the full continuous portfolio.",
                "Portfolio risk is a modeled distance to stops at entry checks, not a guaranteed loss cap; gaps can exceed it and risk can grow between entries.",
                "Daily-close drawdown and fixed slippage cannot capture intraday path, spread variation or market impact.",
                "No automatic promotion of a best variant to live strategy; this code submits no orders.",
                "Top-five-winner subtraction is concentration accounting on the same trade path, not a rerun without those trades.",
                "No sector/correlation cap because point-in-time sector metadata is unavailable from the current free pipeline."]}


def public_summary(result, include_curves=True):
    def aggregate(r):
        return {k:r[k] for k in ("start","end","allocation","stats","equity_curve") if include_curves or k!="equity_curve"}
    public = {k:v for k,v in result.items() if k!="variants"}
    public["variants"] = [{**{k:v for k,v in row.items() if k not in ("periods","stress")},
                          "periods":{n:aggregate(p) for n,p in row["periods"].items()},
                          "stress":aggregate(row["stress"])} for row in result["variants"]]
    return public


def markdown(result):
    pct = lambda x:"n/a" if x is None else f"{100*x:.2f}%"
    rows = sorted(result["variants"],key=lambda r:r["periods"]["full"]["stats"]["return"],reverse=True)
    out = ["# Fördjupad strategiforskning – fem år", "",
           f"Period **{result['start']}–{result['end']}**. Startkapital **{result['capital_usd']:,.0f} USD**. {len(rows)} fördefinierade kombinationer. 1D-candles.","",
           f"Universum: {result['assets']} instrument som uppfyller det striktare aktiefiltret; {result['assets_with_warmup_at_start']} med minst 250 candles vid start. Dagens noteringar och klassificering används; överlevnadsbias kvarstår.","",
           "## Hela perioden och kostnadsstress", "",
           "| ID | Strategi | Avkastning | CAGR | Max nedgång | Affärer | PF | Exponering | 30 bps/sida | Positiva år / 5 | Godkänd |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for r in rows:
        s=r["periods"]["full"]["stats"];a=r["assessment"]
        pf="n/a" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}"
        out.append(f"| {r['variant']['id']} | {r['variant']['label']} | {pct(s['return'])} | {pct(s['cagr'])} | {pct(s['max_drawdown'])} | {s['closed_trades']} | {pf} | {pct(s['average_exposure'])} | {pct(r['stress']['stats']['return'])} | {a['positive_years']} | {'Ja' if a['passed'] else 'Nej'} |")
    b=result["benchmark"]
    out += ["",f"SPY utan utdelningar: **{pct(b['return'])}**, största nedgång **{pct(b['max_drawdown'])}**.","",
            "## Separata årskonton", "", "Varje kolumn startar med nytt kapital utan ärvda innehav. År 1–5 definieras av fem successiva årsdagar fram till testslut.", "",
            "| ID | År 1 | År 2 | År 3 | År 4 | År 5 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        out.append("| "+r["variant"]["id"]+" | "+" | ".join(pct(r["periods"][f"year{i}"]["stats"]["return"]) for i in range(1,6))+" |")
    out += ["", "## Bedömningskrav fastställda före körningen", "",
            "Positiv femårsavkastning; högst 20 % maximal nedgång; minst 100 avslutade affärer; PF minst 1,15; minst fyra positiva årskonton; positiv avkastning vid 30 bps slippage per sida; fem största vinnarna högst hälften av sammanlagda vinster. Godkännande är ett undersökningskriterium, inte bevis för framtida lönsamhet.", "",
            "## Walk-forward med val baserat endast på föregående period", "",
            "Efter 2, 3 och 4 års träning väljs högst tidigare CAGR/nedgång, bland varianter med minst 20 affärer, positiv avkastning och högst 25 % nedgång. Om ingen kvalificerar väljs kontanter. Nästa års konto börjar med nytt kapital. Den tidigare granskningen av samma historik gör detta till en metodkontroll, inte orörd validering.", "",
            "| Träning | Utvärdering | Val | Nästa års avkastning | Nästa års nedgång |", "| --- | --- | --- | ---: | ---: |"]
    for f in result["walk_forward"]["folds"]:
        out.append(f"| {f['training']} | {f['evaluation']} | {f['selected']} | {pct(f['return'])} | {pct(f['drawdown'])} |")
    out += ["",f"Sammansatt avkastning för de tre reset-foldarna: {pct(result['walk_forward']['compounded_reset_fold_return'])}.","",
            "## Exakta regler och kombinationer", "",
            "Grund: föregående 20 dagars högsta kurs + 0,1 ATR, 1,5× volym, stigande SMA50, MACD över signallinjen med ökande histogram; stop under basen, 2R, max 20 dagar. Köp efter avslutad signal vid nästa öppning. Samma ranking och gapfilter som tidigare om ingen rankingändring anges.","",
            "Golden: faktiskt SMA50/SMA200-kors under senaste 10/20/40 dagar och SMA50 fortsatt över. Marknad: SPY close > SMA200 och SMA200 högre än för 20 sessioner sedan. RS: aktiens avkastning över 63 egna bars större än SPY:s över samma kalenderdatum; rangordning efter denna differens. Kvalitet: minst 50 MUSD tidigare genomsnittlig dollaromsättning, ATR/close ≤6 %, signalens avstånd till ursprunglig stop ≤12 %.","",
            "Portföljkontroll: max 10 innehav, max 10 % position, max 80 % investerat kapital vid köp, max 2 % sammanlagd kursrisk ned till stopparna. Halv risk: 0,25 % per affär och 1 % sammanlagd risk. En liten position är tillåten när bara en del av riskbudgeten återstår.","",
            "Marknadsfilter stoppar endast nya köp; combo_market_exit säljer dessutom vid nästa öppning när marknadsvillkoret blir falskt. Misslyckad breakout: close under signalens ursprungliga breakoutnivå utlöser försäljning vid nästa öppning. Initial 2 ATR-stop får endast strama åt ursprunglig stop. Trailing stop uppdateras efter stängning för senare sessioner. 55-dagarsfamiljen använder längre kanal, SMA50 > SMA200, inget obligatoriskt MACD/volymkrav, högst 2 ATR-extension, 2 ATR initial stop, inget vinstmål, max 120 dagar; 10-dagars exit är close under föregående tio dagars lägsta low och försäljning nästa öppning. Kombinerade regler visas exakt nedan.","",
            "```json",json.dumps([r['variant'] for r in result['variants']],ensure_ascii=False,indent=2),"```","",
            "## Diagnostik: exits, koncentration och rullande stabilitet", "",
            "| ID | Sharpe (kontantränta 0) | Sämsta rullande 252 dagar | Positiva rullande fönster | Fem största / alla vinster | Netto minus fem största vinnare USD |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        d,c=r['diagnostics'],r['curve_diagnostics'];sh="n/a" if c['sharpe_zero_cash_rate'] is None else f"{c['sharpe_zero_cash_rate']:.2f}"
        out.append(f"| {r['variant']['id']} | {sh} | {pct(c['worst_rolling_252_sessions'])} | {pct(c['positive_rolling_fraction'])} | {pct(d['top5_share_of_gross_wins'])} | {d['net_without_top5_winners_usd']:,.2f} |")
    out += ["", "Fullständiga kostnader, förlust-/vinststorlekar, exitbidrag och fasbidrag finns som aggregat i summary.json. Enskilda affärer och marknadsdata publiceras inte i klartext.","",
            "## Datakällor och spårbarhet", "",
            "Historisk SIP via gratis Alpaca Basic; officiell Nasdaq symbolkatalog med ETF- och testflaggor samt uttrycklig stamaktie/ordinary-share-benämning. WOLF/RNA utesluts lika för samtliga tester. Inga aktuella fundamentala filter används som om de vore historiska.","",
            f"Dataset SHA256 `{result['dataset_sha256']}`. Fördefinierade tester SHA256 `{result['manifest_sha256']}`.","",
            "Källor: [Nasdaq fältdefinitioner](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs), [AQR momentumforskning](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum), [Bailey m.fl. om backtestöveranpassning](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). Dessa motiverar testidéer och metodkontroll; de bevisar inte lönsamhet för denna aktiestrategi.","",
            "## Begränsningar",""]
    out += ["- "+v for v in result['limitations']]
    return "\n".join(out)+"\n"


def save(result, output, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from .pages import derive_key, json_bytes, ITERATIONS
    salt,nonce=os.urandom(16),os.urandom(12)
    key=derive_key(passphrase,salt)
    aad="breakout-research-v1"
    envelope={"schema":1,"aad":aad,"iterations":ITERATIONS,"salt":b64encode(salt).decode(),
              "nonce":b64encode(nonce).decode(),"ciphertext":b64encode(AESGCM(key).encrypt(nonce,json_bytes(result),aad.encode())).decode()}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/"personal-report.encrypted.json").write_bytes(json_bytes(envelope))
    (output/"summary.json").write_bytes(json_bytes(public_summary(result)))
    md=markdown(result)
    (output/"report.md").write_text(md,encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        # Keep the web summary concise; full exact manifest remains in the artifact.
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(md.split("## Exakta regler och kombinationer")[0])
    print("RESEARCH_RESULT="+json.dumps(public_summary(result,False),allow_nan=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital",type=float,default=100_000)
    parser.add_argument("--output",default="dist/research")
    args=parser.parse_args()
    if not math.isfinite(args.capital) or args.capital<=0:
        parser.error("Capital must be positive and finite")
    from .pages import derive_key
    passphrase=os.environ.get("DASHBOARD_PASSPHRASE","")
    derive_key(passphrase,os.urandom(16))
    excluded=tuple(sorted(set(Config.from_dict(json.loads(Path("config.json").read_text())).excluded_symbols)|set(QUARANTINE)))
    config=replace(Config.from_dict(json.loads(Path("config.json").read_text())),account_equity=args.capital,excluded_symbols=excluded)
    manifest=variants()
    print("RESEARCH_STAGE=Manifest fixed; variants="+str(len(manifest))+"; sha256="+sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),flush=True)
    assets,histories,metadata=download_dataset(config)
    end=date.fromisoformat(metadata["as_of"])
    result=run_study(assets,histories,metadata,config,anniversary(end,5).isoformat(),end.isoformat(),manifest)
    save(result,args.output,passphrase)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
