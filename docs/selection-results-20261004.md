# Börsvärde och månadsvis momentum: högst tio innehav

> Körning: [GitHub Actions 37222220762](https://github.com/DrinasKastrati/Breakout_stock/actions/runs/37222220762), kod `475f82fd77ffaac6e61603c5d83213999742554a`. Körningen lyckades 2026-10-04. Alla 99 tester passerade; separata CI-kontroller lyckades på Python 3.11, 3.12 och 3.13.

## Tolkning av denna körning

Två av sex tester kördes. Fyra storleksfilter blockerades eftersom historiska börsvärden saknas. Inget resultat visar ännu om >1 eller >5 miljarder USD förbättrar strategin.

Ofiltrerat momentum gav −41,62 % totalt, DD 64,29 % och −45,12 % vid 30 bps per sida. Breakout gav −9,77 %, DD 14,02 % och −17,51 % vid stress. Ingen variant klarade samtliga tidigare krav.

**Momentumresultatet är preliminärt på grund av dataluckor:** 827 innehavsdagar saknade kursbar, 40 försök att sälja vid månadsöppning saknade öppningsbar och 38 nya köp blockerades av låsta innehav. 827 är summan av saknade observationer för innehav, inte 827 distinkta börsdagar. Senaste kända markering behölls och innehaven upptog platser tills handel kunde simuleras. Det påverkar värdering, försäljning och kommande köp; resultatet ska inte behandlas som en fullt kvalitetssäkrad rekonstruktion av verklig handel. Breakout hade noll saknade innehavsdagar i denna körning.

Momentum hade 97,09 % genomsnittlig exponering mot 30,42 % för breakout, och saknade dagliga stoppar. Det är därför inte ett isolerat test av rankingregeln. 35,89 % av momentums avslutade affärer var vinnare; PF var 0,66. Dessa är modellens utfall, inte ett kausalt bevis för varför strategin förlorade.

Datasetets SHA256 är identiskt med föregående koncentrerade studie: jämförelsen med dess cap10_base återskapar samma −9,77 %. Skillnaderna här kommer därför inte från att olika prisdataset hämtats. Nästa giltiga steg är att lösa kurs-/instrumentluckorna och tillföra granskade historiska börsvärden, med framtida orörd validering. Inga parametrar ändrades efter att resultaten sågs och ingen variant infördes i dashboard eller handel.

Period **2021-10-02–2026-10-02**. Startkapital **100,000 USD**.

Sex fördefinierade tester: två strategier × tre börsvärdesgränser. Blockerade tester har inga simulerade resultat.

## Teststatus

| Test | Status | Orsak |
| --- | --- | --- |
| Breakout: utan börsvärdesfilter | Körd | Datakrav uppfyllda |
| Breakout: över 1 miljard USD | Blockerad | Historical market caps unavailable |
| Breakout: över 5 miljarder USD | Blockerad | Historical market caps unavailable |
| Månadsvis momentum: utan börsvärdesfilter | Körd | Datakrav uppfyllda |
| Månadsvis momentum: över 1 miljard USD | Blockerad | Historical market caps unavailable |
| Månadsvis momentum: över 5 miljarder USD | Blockerad | Historical market caps unavailable |

## Resultat

| Strategi | Totalavkastning | CAGR | Max nedgång | Högst innehav | Affärer | PF | Exponering | 30 bps/sida | Positiva år / 5 | Alla krav |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Breakout: utan börsvärdesfilter | -9.77% | -2.04% | 14.02% | 10 | 657 | 0.89 | 30.42% | -17.51% | 2 | Nej |
| Månadsvis momentum: utan börsvärdesfilter | -41.62% | -10.21% | 64.29% | 10 | 209 | 0.66 | 97.09% | -45.12% | 3 | Nej |

SPY utan utdelningar: **77.33%**, max nedgång **25.29%**.

## Regler fastställda före körningen

Breakout behåller grundreglerna: föregående 20 dagars motstånd, 0,1 ATR breakoutbuffert, 1,5× volym, stigande SMA50 och MACD; nästa öppning, stop under bas, 2R och högst 20 candles. Risk 0,5 % per köp, max 15 % position vid köp, högst tio innehav. Inget nytt marknadsfilter.

Momentum väljer vid varje avslutad börsmånad de tio högst rankade aktierna med positivt medelvärde av sex- och tolvmånaders avkastning. Den senaste månaden utelämnas: vid månad m används priser vid månadsslut m−1, m−7 och m−13. Minst 250 bars, kurs minst 5 USD och föregående 20 bars genomsnittliga dollaromsättning minst 20 MUSD. Lika poäng bryts alfabetiskt. Ingen information efter signalstängningen används i rangordningen.

Månadsurvalet handlas vid nästa sessions öppning. Aktier som lämnar topp tio säljs först; nya innehav får högst 10 % av kontots eget kapital vid öppningen. Befintliga innehav behålls utan omviktning. Färre än tio positiva kandidater lämnar kontanter. Inga dagliga stoppar, vinstmål eller 20-dagars exits. Saknad öppningsbar låser befintligt innehav och upptar en plats. Taket tio gäller varje dag även då.

Båda använder heltalsaktier, gemensam kassa utan belåning, 10 bps slippage per sida och 0,005 USD/aktie/sida; stress 30 bps. Slutliga innehav värderas vid stängning utan påhittad slutlikvidation. Risk och exponering skiljer sig mellan strategierna; en högre avkastning isolerar därför inte momentumregelns effekt.

Börsvärdesgränserna är strikt >1 respektive >5 miljarder USD vid signalstängningen. Filtret tillämpas före rangordning. Historiska USD-värden måste täcka alla relevanta kandidater och ha available_on ≤ signaldatum; annars blockeras hela filtervarianten. Inga aktuella börsvärden används bakåt i tiden.

Krav från tidigare studie bevaras som diagnostik: positiv totalavkastning, max 20 % nedgång, minst 100 affärer, PF ≥1,15, minst fyra positiva reset-år, positivt kostnadsstressresultat och fem största vinnare ≤50 % av bruttovinster. Gränsen 100 affärer kan missgynna långsammare strategier och är inte ett lönsamhetsbevis.

## Separata årskonton och senaste två år

Varje delkonto börjar i kontanter utan ärvda innehav; resultaten bildar inte hela kontots avkastning.

| Strategi | År 1 | År 2 | År 3 | År 4 | År 5 | Senaste 2 år |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| breakout_unfiltered | -7.40% | 3.28% | 1.78% | -3.83% | -2.09% | -7.28% |
| momentum_unfiltered | -42.64% | 6.41% | 65.91% | 2.98% | -8.27% | -7.69% |

## Nedgång och koncentration

| Strategi | Topp → botten | Värsta kontodag | Dagsavkastning | Fem största / bruttovinster | Saknade innehavsdagar |
| --- | --- | --- | ---: | ---: | ---: |
| breakout_unfiltered | 2024-07-16 → 2025-04-08 | 2025-04-04 | -2.29% | 6.24% | 0 |
| momentum_unfiltered | 2021-11-08 → 2026-07-29 | 2026-06-05 | -13.48% | 34.99% | 827 |

## Data och spårbarhet

5131 nu aktiva stamaktier; 3266 med uppvärmning vid start. Alpaca SIP adjustment=split,spin-off och samma identitetskontroller som den senaste koncentrerade studien. Genuina kursras behålls; stora rörelser flaggas endast i den krypterade granskningen.

Dataset SHA256: `7571707502169432ab97e64215ed32068ab3cc4ee6c5a5719c48401128d64aa3`. Sexdelat manifest SHA256: `85caec688eb2cf57da75110a74c369e56c03ec9ee11ead2fc44df636d920e884`.

Aggregerade kontokurvor och status finns i summary.json. Enskilda affärer, månadsrankning och eventuell börsvärdesdata finns endast i krypterad personal-report.encrypted.json.

Forskningsgrund: [Kenneth French momentum](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html). Den publicerade faktorn är ett annat portföljupplägg och bevisar inte denna strategis lönsamhet.

## Begränsningar

- Current active stock universe; delisted stocks are missing. Survivorship bias remains, especially important for long-term momentum.
- Historical dates were previously inspected; reset years/recent periods are not genuinely untouched validation.
- Split/spin-off-adjusted prices are normalized research data, not a full security and cash ledger. No cash dividends, tax, interest, FX or settlement constraints.
- BHVN starts as a new security on 2022-10-04 with fresh warmup. WOLF/RNA are excluded as in prior studies; complete corporate-action audit is outstanding.
- Breakout uses 0.5% modeled stop risk and max 15% per entry; momentum uses 10% of opening equity per new holding and no daily stop. Different exposure/risk policies prevent attributing return differences solely to stock ranking.
- Momentum retains existing holdings without resizing; weights can exceed 10% after price changes. Ten holdings is a count limit, not a loss limit.
- Missing holding bars carry the last mark; missing monthly opening bars freeze the holding and occupy a slot. Stale sessions are counted.
- Size filters require complete candidate coverage at each exact signal date and known availability dates. Current market caps and forward-filled approximations are not substitutes.
- Signals for the first buy must form within each test window. Reset accounts start in cash and do not inherit earlier monthly selections.
- Daily close drawdown and fixed slippage do not capture intraday risk or variable market impact. No live-strategy promotion or orders.
