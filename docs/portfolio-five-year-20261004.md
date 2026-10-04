# Femårsresultat – breakout med 100 % i en position

Körning: [Portfolio backtest #4](https://github.com/DrinasKastrati/Breakout_stock/actions/runs/37195721487), 2026-10-04. Kodversion `a957c65252393746b63ea1cb670f441096f9519a`. Alla 72 kodtester passerade.

**100 000 USD blev 53 158,86 USD: −46,84 % på fem år.** Största nedgången från tidigare topp var **75,82 %**. Standardkontot gav −34,37 % och SPY +77,33 % utan utdelningar.

Det gamla tvåårsresultatet +137,33 % inkluderade WOLF och RNA, vars bolagshändelser och tickeridentitet inte är verifierade i simulatorn. I den senare tvåårsjämförelsen med båda uteslutna gav samma 100 %-variant −51,50 %; nyligt golden cross var bästa strategivarianten med +17,12 %. Detta femårstest förlänger **100 %-varianten**, utan golden cross, med samma exkluderingar som den senaste jämförelsen. Startdatum påverkar hela följden av affärer; femårsresultatet är inte tvåårsresultatet plus tre års fristående affärer.

**Kvarstående datakvalitetsbegränsning:** instrumenttyp uppskattas från namn. Rapportens återhämtningsbidrag inkluderar UCO, som enligt [ProShares](https://www.proshares.com/our-etfs/leveraged-and-inverse/uco) är en börshandlad produkt med mål om 2× daglig indexavkastning. Det visar att instrumentfiltret släpper igenom andra instrument än stamaktier. Resultatet gäller därför det befintliga prototypuniversumet och är inte ett verifierat test av enbart aktier. Att utesluta WOLF/RNA löser inte andra möjliga problem med bolagshändelser eller återanvända tickers.

Verifiering: båda kontona har 1 255 dagsobservationer; kontanter + innehav stämmer med kontovärdet varje dag; slutvärde, avkastning, årets avkastningar och största nedgång är avstämda mot rapportfilen. Inga innehavssessioner saknade kurs. Rå marknadsdata och enskilda affärer ligger endast i den krypterade Actions-rapporten.

---

# Portföljbacktest – 100 % i en aktie åt gången

Period: **2021-10-02 – 2026-10-02**, 1255 sessioner.

| Mått | Resultat |
| --- | ---: |
| Startkapital (USD) | 100,000.00 |
| Slutvärde inklusive öppna innehav (USD) | 53,158.86 |
| Nettoresultat (USD) | -46,841.14 |
| Avkastning | -46.84% |
| CAGR | -11.87% |
| Största nedgång från topp, dagsstängningar | 75.82% |
| Stängda affärer | 68 |
| Öppna innehav | 1 |
| Träffandel stängda affärer | 45.59% |
| Profit factor, netto-USD | 0.851 |
| Realiserat resultat (USD) | -46,852.61 |
| Orealiserat resultat efter entrykostnader (USD) | 11.48 |
| Genomsnittlig kapitalexponering | 94.05% |
| Courtage (USD) | 1,736.77 |
| Modellerad slippage (USD) | 9,462.24 |
| SPY kursavkastning utan utdelningar | 77.33% |
| SPY största nedgång, dagsstängningar | 25.29% |

Universum: 6013 nuvarande instrument; 3716 hade minst 250 candles vid periodstart.

Exkluderade tickers: RNA, WOLF. Samma exkludering gäller jämförelsekontot.

100 % av tillgängligt kapital i en enda position åt gången. Antalet hela aktier avrundas nedåt och courtage reserveras; en liten kontantrest kan därför bli kvar. Riskbudget och 15 %-gränsen från standardläget används inte. Ingen belåning.

Entry vid nästa sessions öppning efter avslutad breakoutsignal. Slippage 10 baspunkter per sida; courtage $0.005/aktie per sida.

Exit vid stop under basen, mål 2R eller 20 candles. Stop prioriteras om stop och mål träffas i samma candle. Ingen separat MACD-säljsignal.

Rangordning: föregående stängnings poäng, relativ volym, lägst ATR-extension, sedan ticker. Intradagsförsäljningar kan inte finansiera samma dags öppningsköp.

Exitfördelning: `{"stop": 8, "stop_gap": 1, "target": 4, "target_gap": 1, "time": 54}`.

Överhoppade entries: `{"entry_gap": 20, "portfolio_occupied": 11738}`. Innehavssessioner utan kurs: 0.

## Avkastning per kalenderår (första och sista är delår)

| Period | Avkastning |
| --- | ---: |
| 2021-10-04 – 2021-12-31 | 14.36% |
| 2022-01-03 – 2022-12-30 | -41.44% |
| 2023-01-03 – 2023-12-29 | -10.72% |
| 2024-01-02 – 2024-12-31 | 62.44% |
| 2025-01-02 – 2025-12-31 | -60.28% |
| 2026-01-02 – 2026-10-02 | 37.78% |

## Jämförelse på exakt samma hämtade data

| Mått | Riskbudget och högst 15 % per position | 100 % i en position |
| --- | ---: | ---: |
| Slutvärde USD | 65,631.32 | 53,158.86 |
| Avkastning | -34.37% | -46.84% |
| Största nedgång | 44.87% | 75.82% |
| Stängda affärer | 2825 | 68 |

## Aktier bakom nedgång och återhämtning

Namnen nedan är rangordnade efter respektive akties bidrag till det simulerade kontots förändring. Öppna innehav markeras vid periodgränserna. Enskilda kurser, affärer och belopp per aktie finns endast i den krypterade rapporten.

| Fas | Period | Kontovärde USD | Största negativa/positiva bidrag, ticker |
| --- | --- | ---: | --- |
| Största nedgång | 2024-07-12 – 2025-04-08 | 140,680.86 → 34,012.34 | GRRR, SOUN, YETI, BRKR, SYNA |
| Efter botten till testslut | 2025-04-08 – 2026-10-02 | 34,012.34 → 53,158.86 | BE, UCO, ODD, VCTR, CGON |

## Begränsningar

- Current active universe: survivorship bias and heuristic instrument classification.
- Split-adjusted 1Day bars; no dividends, interest, tax or FX effects.
- Daily close drawdown does not measure intraday drawdown.
- Missing position bars retain the last mark; stale sessions are counted.
- No MACD sell signal: exits are initial stop, 2R target and 20-bar time exit.
- Open positions marked at final close; no invented final liquidation.
- Same-day cash proceeds assumed immediately reusable; broker settlement is not modeled.
- Not an out-of-sample or optimized strategy result.

Resultatet gäller denna regeluppsättning och datamängd. Överlevnadsbias innebär att det inte är ett historiskt komplett börstest.
