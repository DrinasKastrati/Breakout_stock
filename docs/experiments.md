# Jämför nio strategier via GitHub

Öppna **Actions → Strategy experiments (9 variants) → Run workflow**, välj 2 år och 100000 USD och kör på main. Befintliga Alpaca-secrets och DASHBOARD_PASSPHRASE används. Inga nya konton, betaltjänster eller handelsorder behövs.

En enda hämtning från gratis Alpaca Basic ger dagscandles och ett gemensamt universum till alla nio tester. En SHA256-kontrollsumma identifierar datamängden. Resultaten visas i körningens sammanfattning. Artefakten `strategy-experiments-report` innehåller `report.md`, publik `summary.json` med kontokurvor och en krypterad detaljrapport; nedladdningslänken sparas en dag. GitHub-loggen och sammanfattningen visar också resultatet.

| Test | Förändring från referensen |
| --- | --- |
| Referens | Breakout + volym + MACD. Riskbudget 0,5 %, max 15 % av kapitalet per position. |
| 10 % | Fast 10 % av aktuellt kapital per köp, begränsat av tillgängliga kontanter. |
| 25 % | Fast 25 % per köp. |
| 100 % | Hela tillgängliga kapitalet i en aktie åt gången. |
| Golden trend | Referens plus SMA50 > SMA200. |
| Nylig golden cross | Referens plus ett faktiskt kors uppåt under de senaste 20 candles, fortfarande SMA50 > SMA200. |
| Utan MACD-filter | MACD är inte obligatoriskt vid köp. Den ursprungliga MACD-poängen finns kvar i rangordningen. |
| MACD-exit | Kors nedåt genom signallinjen vid stängning leder till försäljning vid nästa tillgängliga öppning. |
| ATR-stop | Stoppen höjs efter stängning till max(tidigare stop, close − 2 × ATR14), gäller från nästa session. |

Alla tester använder nästa öppning efter avslutad köp-signal, vinstmål 2R från initial risk, max 20 innehavscandles och samma kostnader. Riskbudgeten används inte i de fasta storlekstesterna. Hela aktier och courtage kan ge en mindre position än angiven procent. Ingen belåning används. Golden cross är ett extra breakoutfilter i testerna, inte en fristående köpregel.

Två separata årskonton startas också med samma kapital utan ärvda innehav. De används för att se om en regel fungerar i båda perioderna; årsresultaten ska inte multipliceras för att rekonstruera tvåårsresultatet. Eftersom perioden redan granskats är det ingen orörd valideringsperiod. Ingen vinnare aktiveras automatiskt i dashboarden.

## Gemensam datakontroll

WOLF och RNA utesluts lika ur alla tester tills historiska instrumentidentiteter och bolagshändelser kan hanteras korrekt. Detta är en konservativ korrigering vald efter granskning, och resultaten är inte direkt jämförbara med tidigare tester som innehöll dessa tickers.

- [WOLF SEC 8-K: gamla aktier annullerade och ersatta den 29 september 2025](https://www.sec.gov/Archives/edgar/data/895419/000119312525223057/d69265d8k.htm).
- [Nasdaq: RNA-symbolen återanvänds i februari 2026](https://nasdaqtrader.com/TraderNews.aspx?id=DTN2026-2).

Andra bolagshändelser är inte fullständigt granskade. Universum består fortfarande av nu aktiva instrument och saknar historiskt avnoterade bolag. Kurserna är splitjusterade, utdelningar och skatt ingår inte. Nedgång mäts vid dagsstängningar, vilket kan underskatta intradagsrisk.
