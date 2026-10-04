"""Five-year comparison capped at 5, 6 or 10 positions; no orders."""
import argparse
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path

from .experiments import QUARANTINE, anniversary
from .models import Config
from .research import download_dataset, run_study, save

# New Biohaven began independent trading on 2022-10-04. The former parent
# was acquired for cash plus spinco shares, not a continuous price loss.
# Warmup must restart on the new security; never stitch the former parent.
IDENTITY_STARTS = {"BHVN": "2022-10-04"}
AUDIT_SYMBOLS = ("BHVN", "MDU", "PFG", "EXPE", "FRHC")


def variants():
    rows = []
    for cap in (5, 6, 10):
        common = {"family": "baseline", "max_positions_limit": cap}
        controls = {"position_cap": .10, "max_portfolio_risk": .02, "max_exposure": .80}
        for suffix, label, options in (
            ("base", "Grundregler", {}),
            ("market", "Marknadsfilter", {"market": True}),
            ("risk", "Gemensamt risktak", controls),
            ("market_risk", "Marknad + risktak", {"market": True, **controls}),
            ("golden_market", "Golden cross 20 + marknad", {"golden": 20, "market": True}),
            ("market_risk_exit", "Marknad + risktak + marknadsexit",
             {"market": True, **controls, "liquidate_when_market_off": True}),
        ):
            rows.append({"id": f"cap{cap}_{suffix}", "label": f"Max {cap}: {label}",
                         **common, **options})
    return rows


def apply_identity_starts(histories):
    clean = {symbol: list(bars) for symbol, bars in histories.items()}
    removed = {}
    for symbol, first in IDENTITY_STARTS.items():
        before = clean.get(symbol, [])
        clean[symbol] = [b for b in before if b.date >= first]
        removed[symbol] = len(before) - len(clean[symbol])
    return clean, removed


def audit_moves(histories, threshold=.40):
    # Flags are diagnostic only. Genuine collapses must remain in the test.
    events = []
    for symbol, bars in sorted(histories.items()):
        for previous, current in zip(bars, bars[1:]):
            gap = current.open / previous.close - 1
            move = current.close / previous.close - 1
            if max(abs(gap), abs(move)) >= threshold:
                events.append({"symbol": symbol, "date": current.date,
                               "overnight_return": gap, "close_return": move})
    return events


def validate_caps(result):
    for row in result["variants"]:
        cap = row["variant"]["max_positions_limit"]
        if type(cap) is not int or not 1 <= cap <= 10:
            raise AssertionError("Every new variant must have a cap of at most ten")
        for period in [*row["periods"].values(), row["stress"]]:
            if period["stats"]["max_positions"] > cap:
                raise AssertionError("Intraday position count exceeded the declared cap")
            for day in period["equity_curve"]:
                if day["positions"] > cap or day["cash_usd"] < -1e-6:
                    raise AssertionError("Position cap or cash budget violated")


def drawdown_details(period):
    peak = period["stats"]["initial_usd"]
    peak_day = period["start"]
    worst = 0.0
    previous = peak
    worst_day = {"date": None, "return": 0.0}
    decline = {}
    for day in period["equity_curve"]:
        value = day["equity_usd"]
        change = value / previous - 1 if previous else 0
        if change < worst_day["return"]:
            worst_day = {"date": day["date"], "return": change}
        if value > peak:
            peak, peak_day = value, day["date"]
        dd = 1 - value / peak if peak else 0
        if dd > worst:
            worst = dd
            decline = {"peak_date": peak_day, "trough_date": day["date"],
                       "peak_usd": peak, "trough_usd": value, "drawdown": dd}
        previous = value
    return {"decline": decline, "worst_day": worst_day}


def markdown(result):
    pct = lambda x: "n/a" if x is None else f"{100*x:.2f}%"
    out = ["# Portföljsimulering: högst 5, 6 och 10 innehav", "",
           f"Period: **{result['start']}–{result['end']}**. Startkapital: **{result['capital_usd']:,.0f} USD**.", "",
           "Alla 18 varianter är fastställda före körningen och använder samma justerade data. Inga order skickas och dashboardens signalregler ändras inte.", "",
           "## Data och metod", "",
           "Alpaca adjustment=split,spin-off normaliserar priser för splitar och avknoppningar. Det är en justerad forskningsserie, inte fullständig bokföring av historiska aktier och utdelade värdepapper. Ingen dubbelräkning genom att dessutom tillföra avknoppade aktier. Kontantutdelningar ingår inte; SPY jämförs utan utdelningar.", "",
           "BHVN-historik före 2022-10-04 används inte för nya Biohaven. Indikatorernas 250-dagars uppvärmning börjar om. Det äldre bolagets kontantuppköp simuleras inte. WOLF/RNA förblir gemensamt exkluderade. Detta är identitetskontroll, inte borttagning av en genuin förlust efter resultatgranskning.", "",
           f"Universum: {result['assets']} nu aktiva stamaktier; {result['assets_with_warmup_at_start']} med uppvärmning vid teststart. Instrumentkatalogen är aktuell, inte historisk.", "",
           "Grundregler: riskbudget 0,5 % per köp, max 15 % position. Risktak-varianterna: max 10 % position, max 2 % sammanlagd risk ned till stopparna och max 80 % exponering vid köp. 5/6/10-taket gäller i alla varianter. Gränser för risk/exponering gäller vid köpbeslut; gap och kursrörelser kan senare överskrida dem.", "",
           "Marknadsfilter: SPY över ett SMA200 som stiger över 20 sessioner. Det stoppar nya köp. Marknadsexit säljer dessutom vid öppningen efter en svag signalstängning. Golden cross: faktiskt SMA50/SMA200-kors senaste 20 sessioner och fortsatt SMA50 över SMA200. Ingen framtida information används vid signalbeslut.", "",
           "Entries nästa öppning; stop under basen, 2R-mål och max 20 candles. Slippage 10 bps per sida och 0,005 USD/aktie/sida; stress 30 bps. Ingen belåning. Kontanter från intradagsförsäljning finansierar inte tidigare öppningsköp.", "",
           "## Resultat", "",
           "| Variant | Avkastning | CAGR | Max nedgång | Högst innehav | Affärer | PF | Exponering | 30 bps/sida | Positiva år / 5 | Krav uppfyllda |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in result["variants"]:
        s = row["periods"]["full"]["stats"]
        pf = "n/a" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}"
        out.append(f"| {row['variant']['label']} | {pct(s['return'])} | {pct(s['cagr'])} | {pct(s['max_drawdown'])} | {s['max_positions']} | {s['closed_trades']} | {pf} | {pct(s['average_exposure'])} | {pct(row['stress']['stats']['return'])} | {row['assessment']['positive_years']} | {'Ja' if row['assessment']['passed'] else 'Nej'} |")
    out += ["", f"SPY utan utdelningar: **{pct(result['benchmark']['return'])}**, maximal nedgång **{pct(result['benchmark']['max_drawdown'])}**.", "",
            "Krav: positiv totalavkastning, högst 20 % nedgång, minst 100 avslutade affärer, PF minst 1,15, minst fyra positiva reset-år, positiv avkastning vid 30 bps/sida, fem största vinnare högst halva bruttovinsten. Uppfyllda krav är ingen garanti för lönsamhet.", "",
            "## Separata årskonton", "",
            "Varje år börjar med nytt kapital utan ärvda innehav; kolumnerna återskapar inte hela kontots avkastning.", "",
            "| Variant | År 1 | År 2 | År 3 | År 4 | År 5 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["variants"]:
        out.append("| " + row["variant"]["id"] + " | " + " | ".join(pct(row["periods"][f"year{i}"]["stats"]["return"]) for i in range(1,6)) + " |")
    out += ["", "## Nedgångar och kontroller", "",
            "| Variant | Topp → botten | Värsta kontodag | Dagens avkastning |", "| --- | --- | --- | ---: |"]
    for row in result["variants"]:
        d = row["drawdown_details"]
        a = d["decline"]
        span = f"{a['peak_date']} → {a['trough_date']}" if a else "Ingen nedgång"
        out.append(f"| {row['variant']['id']} | {span} | {d['worst_day']['date']} | {pct(d['worst_day']['return'])} |")
    out += ["", "Max antal innehav och icke-negativ kontantbudget kontrolleras både intradag och varje dagsstängning i alla perioder och kostnadsstress. Kontrollen av stora kursförändringar är diagnostisk; genuina kursras filtreras inte bort.", "",
            "Tidigare 48,92 % avsåg andra justeringar och obegränsat antal innehav. Skillnaden mot denna körning kan inte tillskrivas enbart innehavstaket.", "",
            "## Spårbarhet", "", f"Dataset SHA256: `{result['dataset_sha256']}`. Testmanifest SHA256: `{result['manifest_sha256']}`.", "",
            "Aggregat och kontokurvor finns i summary.json. Rå kurser, individuella affärer och jämförelser av äldre/justerade prisserier finns endast i personal-report.encrypted.json, krypterad med befintlig dashboard-lösenfras.", "",
            "Källor: [Alpaca bars](https://docs.alpaca.markets/us/reference/stockbars), [avknoppningsjustering](https://docs.alpaca.markets/us/changelog/optionally-adjust-bars-after-spin-offs), [nya Biohaven](https://ir.biohaven.com/news-releases/news-release-details/biohaven-sets-new-course-258-million-cash-proven-team-and-deep).", "",
            "## Begränsningar", ""]
    out += ["- " + text for text in result["limitations"]]
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--output", default="dist/concentrated")
    args = parser.parse_args()
    if not math.isfinite(args.capital) or args.capital <= 0:
        parser.error("Capital must be positive and finite")
    from .pages import derive_key
    from .providers import Alpaca
    passphrase = os.environ.get("DASHBOARD_PASSPHRASE", "")
    derive_key(passphrase, os.urandom(16))
    base = Config.from_dict(json.loads(Path("config.json").read_text()))
    config = replace(base, account_equity=args.capital,
                     excluded_symbols=tuple(sorted(set(base.excluded_symbols) | set(QUARANTINE))))
    manifest = variants()
    print("CAPPED_STAGE=Manifest fixed; variants=18; sha256=" + sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(), flush=True)
    assets, original, metadata = download_dataset(config, adjustment="split,spin-off")
    histories, removed = apply_identity_starts(original)
    metadata.update({"identity_starts": IDENTITY_STARTS, "identity_bars_removed": removed,
                     "position_cap_policy": "All variants have at most 10 holdings"})
    first = min(b.date for bars in original.values() for b in bars)
    # Audit the previous run's five largest decline contributors, using the
    # same end session. Raw/derived security data stays in the encrypted file.
    split_only = Alpaca("sip").bars(list(AUDIT_SYMBOLS), first, metadata["as_of"],
                                    datetime.now(timezone.utc), adjustment="split")
    private_audit = {"split_only": {s: [asdict(b) for b in bars] for s, bars in split_only.items()},
                     "split_spin_off": {s: [asdict(b) for b in original.get(s, [])] for s in AUDIT_SYMBOLS},
                     "large_moves_after_identity_control": audit_moves(histories)}
    metadata["large_move_audit_count"] = len(private_audit["large_moves_after_identity_control"])
    end = date.fromisoformat(metadata["as_of"])
    result = run_study(assets, histories, metadata, config, anniversary(end, 5).isoformat(), end.isoformat(), manifest)
    validate_caps(result)
    for row in result["variants"]:
        row["drawdown_details"] = drawdown_details(row["periods"]["full"])
    result["study"] = "concentrated-20261004"
    result["private_data_audit"] = private_audit
    result["limitations"] += [
        "Spin-off-adjusted prices are a normalized research series, not an exact historical cash/securities ledger; integer sizing and fees are approximate.",
        "BHVN identity begins 2022-10-04 with a new warmup. The acquired former parent and its cash payment are not simulated.",
        "Large moves are flagged, never removed based only on realized returns. A complete corporate-action and security-ID audit remains outstanding.",
        "Comparison with the previous uncapped split-only run changes both the data policy and holding limits; it does not isolate either effect.",
    ]
    save(result, args.output, passphrase, report_renderer=markdown)
    print("CAPPED_STAGE=All holding-cap and cash-budget checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
