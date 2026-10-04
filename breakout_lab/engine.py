from datetime import date
import math

from .indicators import calculate
from .models import Config


def universe_reasons(asset, config, as_of, historical=False):
    reasons = []
    if asset.kind != "common":
        reasons.append("Instrumentet är inte en stamaktie")
    if asset.exchange not in ("NASDAQ", "NYSE", "AMEX", "NYSEAMERICAN", "ARCA", "BATS"):
        reasons.append("Börsen ingår inte i universumet")
    if asset.symbol in config.excluded_symbols:
        reasons.append("Finns i exkluderingslistan")
    if config.allowed_sectors and asset.sector not in config.allowed_sectors:
        reasons.append("Sektorn ingår inte eller saknas")
    if config.min_market_cap > 0 and (asset.market_cap is None or asset.market_cap < config.min_market_cap):
        reasons.append("Börsvärdet är för lågt eller saknas")
    if config.earnings_blackout_days:
        if historical:
            raise ValueError("Historical earnings metadata is not available; disable earnings filter for backtests")
        if not asset.earnings_date:
            reasons.append("Rapportdatum saknas när rapportfiltret är aktivt")
        elif asset.earnings_date < as_of:
            reasons.append("Rapportdatum är inaktuellt; nästa rapportdatum behövs")
        elif 0 <= (date.fromisoformat(asset.earnings_date) - date.fromisoformat(as_of)).days <= config.earnings_blackout_days:
            reasons.append("Rapport inom spärrperioden")
    return reasons


def position_plan(entry, stop, config):
    risk_per_share = entry - stop
    if risk_per_share <= 0 or entry <= 0:
        return {"shares": 0, "risk_usd": 0, "target": None}
    shares = min(math.floor(config.account_equity * config.risk_fraction / risk_per_share),
                 math.floor(config.account_equity * config.max_position_fraction / entry))
    return {"shares": shares, "risk_usd": shares * risk_per_share,
            "target": entry + config.reward_risk * risk_per_share}


def evaluate(asset, bars, config=Config(), index=None, indicators=None, benchmark=None, historical=False):
    i = len(bars) - 1 if index is None else index
    if i < 0:
        return {"symbol": asset.symbol, "name": asset.name, "status": "excluded", "reasons": ["Historik saknas"]}
    b = bars[i]
    result = {"symbol": asset.symbol, "name": asset.name, "sector": asset.sector,
              "date": b.date, "close": b.close, "status": "excluded", "score": 0,
              "reasons": [], "warnings": [], "checks": {}}
    reasons = universe_reasons(asset, config, b.date, historical)
    if i + 1 < config.min_history:
        reasons.append(f"Kräver {config.min_history} candles")
    if b.close < config.min_price:
        reasons.append("Kursen är under prisgränsen")
    if reasons:
        result["reasons"] = reasons
        return result
    window = bars[i-config.lookback:i]  # The signal bar MUST NOT define its own resistance.
    avg_dv = sum(x.close*x.volume for x in window) / len(window)
    if avg_dv < config.min_dollar_volume:
        result["reasons"] = ["För låg genomsnittlig dollaromsättning"]
        return result
    ind = indicators or calculate(bars[:i+1])
    atr = ind["atr"][i-1]
    if not atr or atr <= 0:
        result["reasons"] = ["ATR saknas eller är noll"]
        return result
    resistance = max(x.high for x in window)
    support = min(x.low for x in window)
    avg_volume = sum(x.volume for x in window) / len(window)
    rvol = b.volume / avg_volume if avg_volume else 0
    extension = (b.close - resistance) / atr
    ma = ind["sma50"][i]
    trend = b.close > ma and ma > ind["sma50"][i-5]
    momentum = ind["macd"][i] > ind["signal"][i] and ind["histogram"][i] > ind["histogram"][i-1]
    volume = rvol >= config.volume_multiplier
    breakout = b.close > resistance + config.breakout_atr_buffer * atr
    base = (resistance - support) / atr <= config.max_base_width_atr
    not_extended = extension <= config.max_extension_atr
    checks = {"trend": trend, "base": base, "breakout": breakout,
              "volume": volume, "macd": momentum, "not_extended": not_extended}
    result.update({"checks": checks, "resistance": resistance, "support": support,
                   "atr": atr, "relative_volume": rvol, "dollar_volume": avg_dv,
                   "extension_atr": extension, "macd": ind["macd"][i],
                   "histogram": ind["histogram"][i], "relative_strength": None})
    if asset.classification == "heuristic":
        result["warnings"].append("Instrumenttyp är uppskattad från namn; kontrollera stamaktie")
    if asset.market_cap is None:
        result["warnings"].append("Börsvärde saknas")
    if not asset.earnings_date:
        result["warnings"].append("Rapportdatum saknas")
    if benchmark and i >= 63:
        then = benchmark.get(bars[i-63].date)
        now = benchmark.get(b.date)
        if then and now:
            result["relative_strength"] = b.close/bars[i-63].close - now/then
    # Transparent ranking, NOT a probability or a prediction of profit.
    result["score"] = sum(weight for key, weight in (("trend", 25), ("base", 15), ("breakout", 20), ("volume", 15), ("macd", 15), ("not_extended", 10)) if checks[key])
    passed = trend and base and breakout and not_extended and (volume or not config.require_volume) and (momentum or not config.require_macd)
    labels = {"trend": "Stigande trend saknas", "base": "Konsolideringen är för bred", "breakout": "Stängning över breakoutnivån saknas", "volume": "Volymbekräftelse saknas", "macd": "MACD-bekräftelse saknas", "not_extended": "För långt över motståndet"}
    required = ["trend", "base", "breakout", "not_extended"] + (["volume"] if config.require_volume else []) + (["macd"] if config.require_macd else [])
    result["reasons"] = [labels[k] for k in required if not checks[k]]
    if passed:
        result["status"] = "breakout"
        result["reasons"] = ["Samtliga aktiva signalvillkor uppfyllda"]
    elif trend and base and -config.watch_distance_atr <= extension <= config.max_extension_atr:
        result["status"] = "watch"
    elif breakout and not not_extended:
        result["status"] = "extended"
    else:
        result["status"] = "inactive"
    stop = support - config.breakout_atr_buffer * atr
    result.update({"entry_reference": b.close, "stop": stop, **position_plan(b.close, stop, config)})
    return result


def scan(assets, histories, config, benchmark=None, as_of=None):
    results = []
    for asset in assets:
        bars = histories.get(asset.symbol, [])
        if as_of and (not bars or bars[-1].date != as_of):
            results.append({"symbol": asset.symbol, "name": asset.name, "status": "excluded", "score": 0,
                            "reasons": ["Senaste avslutade handelssessionen saknas"], "warnings": [], "checks": {}})
        else:
            results.append(evaluate(asset, bars, config, benchmark=benchmark))
    return sorted(results, key=lambda r: (-r.get("score", 0), r["symbol"]))
