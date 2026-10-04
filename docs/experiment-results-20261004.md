# Nio strategisimuleringar – resultat 4 oktober 2026

## Bedömning av denna körning

Det nyliga golden cross-filtret gav bäst resultat bland de nio varianterna: +17,12 % efter modellerade kostnader, maximal nedgång 12,34 %, 366 stängda affärer och profit factor 1,40. Separata årskonton gav +7,86 % respektive +7,21 %. Detta är ett lovande undersökningsresultat, inte bevis för framtida överavkastning.

Filtret kräver både den vanliga breakoutsignalen och att SMA50 faktiskt korsat upp över SMA200 under de senaste 20 handelsdagarna och fortfarande ligger över. Att endast kräva SMA50 över SMA200 gav −11,78 % och förbättrade inte referensen.

Golden cross-varianten hade bara 39,78 % genomsnittlig kapitalexponering, jämfört med referensens 92,12 %. Den lägre nedgången ska därför bedömas tillsammans med att mer kapital låg kontant. SPY gav +35,24 % med 18,90 % maximal nedgång och slog samtliga strategier i total avkastning.

Fasta köp på 10 %, 25 % och 100 % förbättrade inte resultatet över hela perioden. Referensens max 15 % är en gräns: riskbudgeten på 0,5 % gör ofta köpet mindre. 25 %-varianten gav nästan samma totalavkastning som referensen men betydligt större maximal nedgång, 54,70 %. 100 %-varianten slutade på 48 502,97 USD, med −51,50 % avkastning och 74,33 % maximal nedgång.

MACD-exit och flyttande 2 ATR-stop gav fler affärer och sämre nettoresultat än referensen. Avstängt obligatoriskt MACD-köpfilter gav +1,08 %, men profit factor för stängda affärer var cirka 1,00 och det andra fristående årskontot gick svagt negativt. Ingen av dessa skillnader motiverar att automatiskt ändra grundstrategin.

WOLF och RNA har tagits bort lika ur samtliga nio tester. Tidigare rapporter innehöll dem och är därför inte direkt jämförbara med detta resultat; tidigare positiv 100 %-avkastning ska inte betraktas som verifierad innan bolagshändelser och instrumentidentiteter har hanterats. Den nya jämförelsen är fortfarande begränsad av överlevnadsbias och ofullständig granskning av andra bolagshändelser.

År 1 avser 2024-10-02–2025-10-01. År 2 avser 2025-10-02–2026-10-02. Varje år startar med 100 000 USD och utan ärvda positioner. Perioden har redan granskats; årstesterna är robusthetskontroller och ingen orörd validering.

[Källkörning i GitHub Actions](https://github.com/DrinasKastrati/Breakout_stock/actions/runs/37193908983). Kod vid körningen: `0d49cf7b4bcd2cb80e71d8466add1e4238dd293d`. Samtliga 72 tester passerade även i GitHub. Rapporten ändrar ingen live-strategi och skickar inga order.

Period: **2024-10-02 – 2026-10-02**. Startkapital: **100,000 USD**. 1D-candles.

Gemensamt universum: 6013 instrument, 4657 med uppvärmning vid start. Exkluderade: RNA, WOLF.

| Test | Slutvärde USD | Avkastning | Max nedgång | Stängda affärer | Träffandel | Profit factor | Genomsnittlig exponering |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Referens: risk 0,5 %, max 15 % | 97,722.09 | -2.28% | 22.05% | 1276 | 48.20% | 0.98 | 92.12% |
| 10 % kapital per köp | 80,283.42 | -19.72% | 33.11% | 635 | 49.29% | 0.86 | 93.65% |
| 25 % kapital per köp | 97,638.14 | -2.36% | 54.70% | 430 | 50.23% | 1.00 | 94.04% |
| 100 % i en aktie | 48,502.97 | -51.50% | 74.33% | 26 | 50.00% | 0.58 | 94.57% |
| Referens + SMA50 över SMA200 | 88,219.59 | -11.78% | 25.27% | 1118 | 48.93% | 0.88 | 89.93% |
| Referens + golden cross senaste 20 | 117,124.67 | 17.12% | 12.34% | 366 | 53.01% | 1.40 | 39.78% |
| Referens utan MACD-köpfilter | 101,076.46 | 1.08% | 22.67% | 1312 | 48.86% | 1.00 | 92.58% |
| Referens + MACD-exit | 89,737.25 | -10.26% | 24.90% | 1825 | 38.30% | 0.92 | 90.53% |
| Referens + flyttande 2 ATR-stop | 85,861.71 | -14.14% | 21.18% | 1667 | 39.53% | 0.87 | 86.29% |

SPY kursavkastning utan utdelningar: **35.24%**. Max nedgång: **18.90%**.

## Separata konton för varje år

Varje år startar från samma kapital utan ärvda innehav. Detta visar stabilitet mellan perioder, men är ingen oberoende validering eftersom perioden redan granskats.

| Test | År 1 avkastning | År 1 max nedgång | År 1 affärer | År 2 avkastning | År 2 max nedgång | År 2 affärer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Referens: risk 0,5 %, max 15 % | 1.26% | 22.05% | 554 | -5.85% | 14.91% | 674 |
| 10 % kapital per köp | -11.05% | 32.90% | 277 | -7.23% | 21.86% | 330 |
| 25 % kapital per köp | -10.44% | 54.70% | 166 | 15.02% | 20.66% | 191 |
| 100 % i en aktie | -49.98% | 74.33% | 13 | -34.66% | 58.30% | 13 |
| Referens + SMA50 över SMA200 | -9.60% | 25.27% | 466 | 3.84% | 15.63% | 603 |
| Referens + golden cross senaste 20 | 7.86% | 12.34% | 169 | 7.21% | 4.44% | 172 |
| Referens utan MACD-köpfilter | 0.77% | 22.67% | 563 | -0.52% | 11.04% | 666 |
| Referens + MACD-exit | -10.95% | 24.90% | 822 | -6.35% | 14.93% | 973 |
| Referens + flyttande 2 ATR-stop | -10.28% | 21.18% | 745 | -5.18% | 14.03% | 889 |

## Exakta skillnader

1. Referens: breakout + volym + MACD. Riskbudget 0,5 % av aktuellt kapital, max 15 % position.
2–4. Samma köp och exits, men 10 %, 25 % respektive hela tillgängliga kapitalet per köp. Hela aktier, reserverat courtage, ingen belåning. 10/25 % kan hålla flera aktier; 100 % håller en.
5. Referens plus SMA50 > SMA200 vid signalstängningen. Detta är ett trendläge, inte ett nytt kors varje dag.
6. Referens plus ett faktiskt kors: SMA50 går från <= SMA200 till > SMA200 inom de senaste 20 candles, och ligger fortfarande över.
7. Referens utan obligatorisk MACD-bekräftelse vid köp. MACD:s ursprungliga poängvikt behålls så rangordningen hålls konstant.
8. Referens plus exit när MACD korsar signallinjen nedåt. Signal vid stängning, försäljning vid nästa öppning.
9. Referens plus stop = max(tidigare stop, close − 2 × ATR14), uppdaterad efter stängning för nästa session.

Samtliga behåller ursprungligt vinstmål 2R, tidsgräns 20 candles, stopprioritet vid tvetydig OHLC och samma entrygapfilter. Grundstrategin på hemsidan ändras inte av denna jämförelse.

## Kostnader och datakontroll

Slippage: 10 baspunkter per sida. Courtage: 0.005 USD per aktie och sida.

Dataset SHA256: `158ce0e5a1d68159a662cbe83d7a6989194250f6e3786543d08df6ed92eb881d`

Detaljerade affärer är krypterade med befintlig dashboard-passphrase. Publik JSON innehåller endast inställningar och aggregerade kontoutfall.

## Begränsningar

- Current active universe: survivorship bias; historical delisted securities are absent.
- WOLF and RNA excluded from every variant because security continuity is unresolved. Other corporate actions are not comprehensively audited.
- Daily split-adjusted bars; no dividends, taxes, interest, FX or settlement restrictions.
- All nine variants share the same fetched data, ranking, initial capital and costs.
- Experiments were chosen after inspecting this period: year2 is a separate robustness check, NOT an untouched out-of-sample test.
- Each yearly check starts with new cash and no positions; yearly returns do not compound into the full result.
- No best-variant selection is deployed automatically; results are exploratory.
- Fixed 10/25/100 percent allocation bypasses the reference 0.5 percent risk budget. Reference sizing is a cap, not a fixed 15 percent purchase.
- MACD bearish crossover observed at a close exits at the next available open. Opening stop/target gaps take priority.
- ATR stop ratchets after each completed close and applies only to later sessions. Original 2R target and 20-bar time exit remain active.

Källor för gemensam karantän: [WOLF SEC 8-K](https://www.sec.gov/Archives/edgar/data/895419/000119312525223057/d69265d8k.htm) och [Nasdaq RNA symbol reuse](https://nasdaqtrader.com/TraderNews.aspx?id=DTN2026-2).
