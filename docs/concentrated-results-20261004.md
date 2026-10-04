Källkörning: [GitHub Actions](https://github.com/DrinasKastrati/Breakout_stock/actions/runs/37220291620). Kodversion: `9ee3c8bf23112e7f12c765f241b859889135b856`. Alla 91 tester och samtliga kontant-/innehavskontroller passerade. Ingen av de 18 varianterna uppfyllde alla forskningskrav.

# Portföljsimulering: högst 5, 6 och 10 innehav

Period: **2021-10-02–2026-10-02**. Startkapital: **100,000 USD**.

Alla 18 varianter är fastställda före körningen och använder samma justerade data. Inga order skickas och dashboardens signalregler ändras inte.

## Data och metod

Alpaca adjustment=split,spin-off normaliserar priser för splitar och avknoppningar. Det är en justerad forskningsserie, inte fullständig bokföring av historiska aktier och utdelade värdepapper. Ingen dubbelräkning genom att dessutom tillföra avknoppade aktier. Kontantutdelningar ingår inte; SPY jämförs utan utdelningar.

BHVN-historik före 2022-10-04 används inte för nya Biohaven. Indikatorernas 250-dagars uppvärmning börjar om. Det äldre bolagets kontantuppköp simuleras inte. WOLF/RNA förblir gemensamt exkluderade. Detta är identitetskontroll, inte borttagning av en genuin förlust efter resultatgranskning.

Universum: 5131 nu aktiva stamaktier; 3266 med uppvärmning vid teststart. Instrumentkatalogen är aktuell, inte historisk.

Grundregler: riskbudget 0,5 % per köp, max 15 % position. Risktak-varianterna: max 10 % position, max 2 % sammanlagd risk ned till stopparna och max 80 % exponering vid köp. 5/6/10-taket gäller i alla varianter. Gränser för risk/exponering gäller vid köpbeslut; gap och kursrörelser kan senare överskrida dem.

Marknadsfilter: SPY över ett SMA200 som stiger över 20 sessioner. Det stoppar nya köp. Marknadsexit säljer dessutom vid öppningen efter en svag signalstängning. Golden cross: faktiskt SMA50/SMA200-kors senaste 20 sessioner och fortsatt SMA50 över SMA200. Ingen framtida information används vid signalbeslut.

Entries nästa öppning; stop under basen, 2R-mål och max 20 candles. Slippage 10 bps per sida och 0,005 USD/aktie/sida; stress 30 bps. Ingen belåning. Kontanter från intradagsförsäljning finansierar inte tidigare öppningsköp.

## Resultat

| Variant | Avkastning | CAGR | Max nedgång | Högst innehav | Affärer | PF | Exponering | 30 bps/sida | Positiva år / 5 | Krav uppfyllda |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Max 5: Grundregler | -5.71% | -1.17% | 7.46% | 5 | 330 | 0.88 | 14.77% | -13.61% | 3 | Nej |
| Max 5: Marknadsfilter | -6.06% | -1.24% | 7.71% | 5 | 255 | 0.84 | 11.78% | -10.14% | 1 | Nej |
| Max 5: Gemensamt risktak | -7.56% | -1.56% | 8.80% | 5 | 326 | 0.81 | 11.46% | -11.26% | 2 | Nej |
| Max 5: Marknad + risktak | 0.56% | 0.11% | 5.63% | 5 | 251 | 1.04 | 9.05% | -5.21% | 2 | Nej |
| Max 5: Golden cross 20 + marknad | -2.63% | -0.53% | 5.87% | 5 | 203 | 0.91 | 9.71% | -1.50% | 3 | Nej |
| Max 5: Marknad + risktak + marknadsexit | 3.01% | 0.59% | 4.62% | 5 | 262 | 1.13 | 9.08% | -6.78% | 2 | Nej |
| Max 6: Grundregler | -6.14% | -1.26% | 8.85% | 6 | 393 | 0.89 | 17.85% | -17.78% | 3 | Nej |
| Max 6: Marknadsfilter | -2.93% | -0.59% | 7.40% | 6 | 306 | 0.93 | 14.35% | -9.46% | 3 | Nej |
| Max 6: Gemensamt risktak | -8.61% | -1.78% | 11.90% | 6 | 380 | 0.76 | 12.14% | -10.68% | 2 | Nej |
| Max 6: Marknad + risktak | -4.85% | -0.99% | 6.33% | 6 | 303 | 0.83 | 9.27% | -9.30% | 1 | Nej |
| Max 6: Golden cross 20 + marknad | -0.15% | -0.03% | 5.91% | 6 | 239 | 1.00 | 11.81% | -1.40% | 4 | Nej |
| Max 6: Marknad + risktak + marknadsexit | -1.08% | -0.22% | 4.85% | 6 | 311 | 0.95 | 9.11% | -6.41% | 1 | Nej |
| Max 10: Grundregler | -9.77% | -2.04% | 14.02% | 10 | 657 | 0.89 | 30.42% | -17.51% | 2 | Nej |
| Max 10: Marknadsfilter | -3.92% | -0.80% | 10.80% | 10 | 506 | 0.95 | 24.42% | -11.08% | 2 | Nej |
| Max 10: Gemensamt risktak | -4.07% | -0.83% | 7.05% | 10 | 572 | 0.90 | 13.17% | -7.44% | 4 | Nej |
| Max 10: Marknad + risktak | -3.72% | -0.76% | 4.50% | 10 | 448 | 0.85 | 9.96% | -5.51% | 2 | Nej |
| Max 10: Golden cross 20 + marknad | 4.84% | 0.95% | 7.61% | 10 | 348 | 1.11 | 17.37% | 1.34% | 4 | Nej |
| Max 10: Marknad + risktak + marknadsexit | -5.91% | -1.21% | 7.10% | 10 | 464 | 0.80 | 9.46% | -3.61% | 2 | Nej |

SPY utan utdelningar: **77.33%**, maximal nedgång **25.29%**.

Krav: positiv totalavkastning, högst 20 % nedgång, minst 100 avslutade affärer, PF minst 1,15, minst fyra positiva reset-år, positiv avkastning vid 30 bps/sida, fem största vinnare högst halva bruttovinsten. Uppfyllda krav är ingen garanti för lönsamhet.

## Separata årskonton

Varje år börjar med nytt kapital utan ärvda innehav; kolumnerna återskapar inte hela kontots avkastning.

| Variant | År 1 | År 2 | År 3 | År 4 | År 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| cap5_base | -6.25% | 3.11% | 1.34% | -1.12% | 0.32% |
| cap5_market | -4.19% | -0.47% | 4.03% | -1.84% | -0.52% |
| cap5_risk | -5.66% | 1.04% | -0.31% | -2.00% | 1.24% |
| cap5_market_risk | -3.79% | 0.12% | 2.23% | -1.60% | -2.29% |
| cap5_golden_market | -5.10% | 1.30% | 0.00% | 1.32% | -0.35% |
| cap5_market_risk_exit | -2.62% | 0.12% | 1.88% | -1.21% | -1.20% |
| cap6_base | -6.86% | 2.05% | 2.77% | -2.49% | 0.70% |
| cap6_market | -3.50% | 0.90% | 6.36% | -2.90% | 0.44% |
| cap6_risk | -6.11% | 1.55% | 0.42% | -1.76% | -0.21% |
| cap6_market_risk | -3.67% | -0.24% | 2.16% | -0.70% | -0.36% |
| cap6_golden_market | -5.05% | 0.04% | 2.66% | 0.79% | 0.78% |
| cap6_market_risk_exit | -2.96% | -0.24% | 3.02% | -0.37% | -0.35% |
| cap10_base | -7.40% | 3.28% | 1.78% | -3.83% | -2.09% |
| cap10_market | -3.10% | -1.34% | 4.06% | -0.85% | 0.47% |
| cap10_risk | -6.33% | 2.35% | 4.57% | 0.10% | 2.48% |
| cap10_market_risk | -2.61% | -0.56% | 5.18% | 0.28% | -0.51% |
| cap10_golden_market | -4.91% | 0.47% | 4.08% | 2.37% | 4.73% |
| cap10_market_risk_exit | -2.80% | -0.56% | 4.32% | 0.92% | -1.16% |

## Nedgångar och kontroller

| Variant | Topp → botten | Värsta kontodag | Dagens avkastning |
| --- | --- | --- | ---: |
| cap5_base | 2024-07-16 → 2026-07-30 | 2025-04-04 | -1.14% |
| cap5_market | 2024-07-16 → 2026-09-15 | 2023-08-02 | -1.16% |
| cap5_risk | 2021-11-03 → 2025-04-08 | 2025-04-04 | -1.00% |
| cap5_market_risk | 2021-11-03 → 2023-10-27 | 2023-08-02 | -1.10% |
| cap5_golden_market | 2021-10-18 → 2023-06-23 | 2024-08-02 | -0.86% |
| cap5_market_risk_exit | 2021-11-03 → 2023-11-08 | 2023-08-02 | -1.15% |
| cap6_base | 2024-07-16 → 2026-07-30 | 2025-04-04 | -1.47% |
| cap6_market | 2024-12-06 → 2025-04-08 | 2023-08-02 | -1.35% |
| cap6_risk | 2021-11-03 → 2025-04-08 | 2022-05-18 | -0.83% |
| cap6_market_risk | 2021-11-03 → 2023-11-08 | 2023-08-02 | -1.06% |
| cap6_golden_market | 2021-10-18 → 2023-04-26 | 2024-08-02 | -0.89% |
| cap6_market_risk_exit | 2021-11-03 → 2023-11-08 | 2023-08-02 | -1.15% |
| cap10_base | 2024-07-16 → 2025-04-08 | 2025-04-04 | -2.29% |
| cap10_market | 2024-05-24 → 2025-04-08 | 2023-08-02 | -1.65% |
| cap10_risk | 2021-11-03 → 2024-01-24 | 2025-04-04 | -1.03% |
| cap10_market_risk | 2021-11-03 → 2026-09-25 | 2023-08-02 | -1.04% |
| cap10_golden_market | 2024-07-16 → 2025-06-13 | 2024-08-02 | -1.18% |
| cap10_market_risk_exit | 2024-07-16 → 2026-09-23 | 2023-08-02 | -1.05% |

Max antal innehav och icke-negativ kontantbudget kontrolleras både intradag och varje dagsstängning i alla perioder och kostnadsstress. Kontrollen av stora kursförändringar är diagnostisk; genuina kursras filtreras inte bort.

Tidigare 48,92 % avsåg andra justeringar och obegränsat antal innehav. Skillnaden mot denna körning kan inte tillskrivas enbart innehavstaket.

## Spårbarhet

Dataset SHA256: `7571707502169432ab97e64215ed32068ab3cc4ee6c5a5719c48401128d64aa3`. Testmanifest SHA256: `1eb8d039b1da0ab52d4a1184566a63a936dd72cd970859679d166ce213e32385`.

Aggregat och kontokurvor finns i summary.json. Rå kurser, individuella affärer och jämförelser av äldre/justerade prisserier finns endast i personal-report.encrypted.json, krypterad med befintlig dashboard-lösenfras.

Källor: [Alpaca bars](https://docs.alpaca.markets/us/reference/stockbars), [avknoppningsjustering](https://docs.alpaca.markets/us/changelog/optionally-adjust-bars-after-spin-offs), [nya Biohaven](https://ir.biohaven.com/news-releases/news-release-details/biohaven-sets-new-course-258-million-cash-proven-team-and-deep).

## Begränsningar

- Current active universe and current security-type directory: historical delisted securities absent; survivorship bias remains.
- WOLF and RNA quarantined; no complete corporate-action/security-identity ledger. Other discontinuities remain possible.
- Daily OHLC adjustment=split,spin-off; no cash dividends, tax, cash interest, FX or settlement restrictions.
- Study definitions fixed before this run, but prior exploration already inspected these dates. No genuinely untouched validation period.
- Reset-year/training/recent accounts start from 100k with no inherited holdings; their returns do not recreate the full continuous portfolio.
- Portfolio risk is a modeled distance to stops at entry checks, not a guaranteed loss cap; gaps can exceed it and risk can grow between entries.
- Daily-close drawdown and fixed slippage cannot capture intraday path, spread variation or market impact.
- No automatic promotion of a best variant to live strategy; this code submits no orders.
- Top-five-winner subtraction is concentration accounting on the same trade path, not a rerun without those trades.
- No sector/correlation cap because point-in-time sector metadata is unavailable from the current free pipeline.
- Spin-off-adjusted prices are a normalized research series, not an exact historical cash/securities ledger; integer sizing and fees are approximate.
- BHVN identity begins 2022-10-04 with a new warmup. The acquired former parent and its cash payment are not simulated.
- Large moves are flagged, never removed based only on realized returns. A complete corporate-action and security-ID audit remains outstanding.
- Comparison with the previous uncapped split-only run changes both the data policy and holding limits; it does not isolate either effect.
