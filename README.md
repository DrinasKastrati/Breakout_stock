# Breakout Lab

En körbar första version av en daglig breakoutscreener för amerikanska aktier. Systemet hittar kandidater, visar varför de kvalificerar sig och jämför strategier med och utan volym/MACD. Gränssnittet är på svenska.

**Status: v0.2, statisk dashboard för GitHub Pages + lokalt forskningsverktyg.** Gratis GitHub Actions hämtar avslutade dagsdata, beräknar signaler och uppdaterar sidan. Alpaca Basic räcker för historisk SIP-data; inga betalabonnemang behövs för det implementerade upplägget. Inga köp- eller säljorder skickas.

## Starta via GitHub-hemsidan

Alla steg för drift kan göras i webbläsaren. Ingen egen server, terminal eller betalt webbhotell krävs.

1. **Gratis Pages kräver ett publikt repo.** Projektet är förberett, men synlighet ändras inte automatiskt. Läs och följ [installationsguiden](docs/github-setup.md).
2. Välj **Settings → Pages → Source: GitHub Actions**.
3. Lägg dina gratis Alpaca Basic/paper-nycklar och en egen slumpmässig lösenfras i **Settings → Secrets and variables → Actions → Secrets**: `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `DASHBOARD_PASSPHRASE`.
4. Lägg till **Variables**: `ENABLE_PAGES=true`, `ENABLE_AUTO_UPDATE=true`.
5. Välj **Actions → Update dashboard → Run workflow → source: alpaca**. Länken till sidan visas efter första lyckade publiceringen.

För en första titt kan du välja `source: demo` utan API-nycklar; då visas tydligt fiktiva aktier. Aktivera automatisk uppdatering först när de tre hemligheterna är klara.

Koden och webbgränssnittet kan vara publika, medan riktiga analys- och diagramfiler alltid krypteras innan uppladdning. Du låser upp dem i webbläsaren med din egen lösenfras. API-nycklarna skickas aldrig till sidan. Detta är en dashboard för kontoinnehavarens **personliga bruk**: Alpaca tillåter inte vidarepublicering av sina API-data. Kryptering skyddar innehållet men ger inga ytterligare datarättigheter.

Dagliga körningar sker **01.37 och 02.37 UTC, tisdag–lördag**, efter föregående New York-handelsdag. Andra körningen kontrollerar också sena datakorrigeringar. Oförändrad analys publiceras inte igen. Om datahämtning, tester eller publicering misslyckas ligger föregående lyckade sida kvar, med sitt sessionsdatum. En öppen flik kontrollerar ny analys var femte minut.

Strategiinställningar ändras genom att redigera `config.json` på GitHub och välja **Commit changes**. Sidan länkar till redigeraren. Push till `main` startar en ny analys och publicering. Backtestet på Pages beräknas automatiskt för senaste året; fria datumval och direkt ändring av inställningar finns i den lokala versionen. 4H ingår inte ännu.

## Kör lokalt (valfritt)

Kräver Python 3.11 eller senare och operativsystemets tidszonsdata. Kör från projektmappen:

```bash
python -m breakout_lab demo
python -m breakout_lab serve
```

Öppna **http://127.0.0.1:8000**. Avsluta med Ctrl+C.

Demoläget skapar åtta **fiktiva** aktier och 650 syntetiska dagscandles per aktie. Kalendern består av vardagar och representerar inte börsens verkliga helgdagar. Demodata ska endast användas för att undersöka funktioner; dess resultat säger ingenting om strategins förmåga på marknaden.

På system utan IANA-tidszonsdatabas, till exempel vissa Windows-installationer, installera `tzdata` med `python -m pip install tzdata`.

## Funktioner i v0.2

- Screener med breakout, bevakning, översträckt, ingen setup och filtrerad.
- Sökning, statusfilter och CSV-export.
- Candlestickdiagram med SMA 50, motstånd, volym och MACD.
- Förklaring av varje signal, filtreringsorsak och saknad metadata.
- Riskplan med entryreferens, stop, mål och kapitalbegränsad positionsstorlek.
- Inställningar som valideras och sparas i `config.json`.
- SQLite-lagring med atomiska databyten.
- Alpaca-integration med symbolbatcher, paginering, begränsade omförsök och splitjustering.
- Import av dagliga OHLCV-data och kuraterad bolagsmetadata från CSV.
- Backtest av oberoende affärer och jämförelse av tre strategivarianter.
- Automatisk Pages-publicering, uppdateringsschema, krypterade personliga snapshotfiler och testning på Python 3.11, 3.12 och 3.13.

## Riktiga marknadsdata

### 1. Ange nycklar i miljön

```bash
export ALPACA_API_KEY='din-api-nyckel'
export ALPACA_API_SECRET='din-hemliga-nyckel'
export ALPACA_DATA_FEED='sip'
```

`.env.example` visar variabelnamnen. Applikationen laddar **inte** `.env` automatiskt. Nycklar ska vara servervariabler och får aldrig läggas i frontend eller Git. Applikationen använder enbart GET-anrop till tillgångs-, kalender- och marknadsdataendpoints.

Alpaca Basic tillåter **historisk SIP utan betalabonnemang när `end` är minst 15 minuter gammalt**. Klienten skickar ett uttryckligt slutvärde minst 16 minuter bakåt och använder inga SIP-endpoints för realtid, latest eller snapshot. Anrop begränsas till högst cirka 171/minut, under Basics gräns på 200/minut. SIP används som standard för bred volymtäckning. `iex` representerar en enskild börs och är inte direkt jämförbart med SIP.

### 2. Kör först ett mindre anslutningstest

```bash
python -m breakout_lab --db data/alpaca-sample.sqlite sync --limit 50
python -m breakout_lab --db data/alpaca-sample.sqlite serve
```

### 3. Hämta hela det upptäckta universumet

```bash
python -m breakout_lab --db data/alpaca.sqlite sync --years 3
python -m breakout_lab --db data/alpaca.sqlite serve
```

Utan `--limit` hämtas alla upptäckta, aktiva och handlingsbara kandidater hos Alpaca. Detta är **inte** en garanti om exakt samtliga amerikanska stamaktier. Tillgångslistan inkluderar inte ett komplett historiskt universum med avnoterade bolag. Instrumenttypen uppskattas från namn om explicit metadata saknas; gränssnittet varnar om detta.

Synkroniseringen hämtar om hela det valda historikintervallet för att undvika att äldre priser och volymer behåller fel justering efter en split. Den kan därför ta tid vid ett stort universum. Vid fel behålls det tidigare datasetet. Den kräver också att processen har minne för det valda historikintervallet; strömmande ingestion är ett framtida utvecklingssteg.

Den senaste handelsdagen används först efter **20.15 New York-tid**. Kalendern hämtas från Alpaca för helgdagar och förkortade sessioner. Pris- och volymaggregering följer leverantörens `1Day`-definition; den ska inte antas vara identisk med egna candles som byggs enbart från ordinarie handel.

**I den lokala versionen räknar ”Uppdatera analys” om den lagrade datan.** Kör `sync` igen för att hämta nya kurser. På GitHub Pages hämtar Actions nya kurser enligt schemat; knappen läser senaste publicerade analysen. Datasetets session visas alltid i gränssnittet och aktier med saknad senaste session filtreras bort. Kontrollera att sessionen är aktuell innan analysen används.

### Bolagsmetadata

Alpacas tillgångsendpoint ger inte alla uppgifter som behövs för börsvärde, sektor och rapportdatum. Komplettera med en egen, daterad och kontrollerad CSV:

```csv
symbol,name,exchange,kind,sector,market_cap,earnings_date
EXAMPLE,Example Company,NASDAQ,common,Technology,1500000000,2026-12-01
```

`market_cap` anges i USD. `earnings_date` ska vara nästa kända rapportdatum. `kind=common` innebär att du har kontrollerat att instrumentet är en stamaktie. Exempelradens ticker är fiktiv.

```bash
python -m breakout_lab --db data/alpaca.sqlite sync --metadata metadata.csv
```

Minsta börsvärde och rapportspärr är avstängda som standard eftersom metadata kan saknas. När ett sådant filter är aktivt utesluts instrument med saknade uppgifter. Rapportspärren använder **kalenderdagar**. Ett passerat rapportdatum kräver ny metadata. Sektorfilter kräver exakta sektornamn från metadatafilen.

## Importera egna data

```csv
symbol,date,open,high,low,close,volume
EXAMPLE,2026-01-02,100,102,99,101,1500000
```

CSV-import kräver separat instrumentmetadata med `kind=common`. Annars klassificeras instrumentet som okänt och filtreras bort. Varje aktie behöver minst 250 dagscandles med standardinställningarna.

```bash
python -m breakout_lab --db data/csv.sqlite import bars.csv --metadata metadata.csv
python -m breakout_lab --db data/csv.sqlite serve
```

Använd färdiga 1D-candles, konsekvent splitjustering och datum i New York-sessionens kalender. Dubbletter, ogiltiga OHLC-priser och icke-finita tal avvisas. SPY används som frivillig benchmark och blir ingen handelskandidat. Relativ styrka är informationsvärde, inte signalvillkor.

## Strategi och risk

Detaljer och konventioner finns i [docs/strategy.md](docs/strategy.md). Alla trösklar är hypoteser att pröva, inte optimerade eller bevisat lönsamma regler.

Standardstrategin kräver kurs över ett stigande SMA 50, en avgränsad bas och stängning över föregående 20 candles högsta high plus 0,1 ATR. Den kräver också 1,5 gånger normalvolym samt MACD över signallinjen med stigande histogram. Entry får inte ligga mer än 1 ATR över motståndet.

Stop läggs under basens botten. Positionsstorleken är det lägre av riskbudgeten och kapitalgränsen. Referenskontot är 100 000 USD, planerad risk 0,5 % och högst 15 % av kontot per position. Dessa värden är exempel och behöver anpassas i `config.json`. Gap, likviditet och kostnader kan ge större förlust än den planerade risken.

## Backtest

```bash
python -m breakout_lab backtest
python -m breakout_lab --db data/alpaca.sqlite backtest --start 2025-01-01 --end 2025-12-31
python -m breakout_lab --db data/alpaca.sqlite scan
```

Globala argument som `--db` och `--config` anges **före** underkommandot.

Tre varianter jämförs: pris, pris + volym och pris + volym + MACD. Övriga regler och kostnader är identiska. Backtestet använder nästa öppning för entry, modellerar slippage och courtage, hanterar gap genom stop och väljer stop om både stop och mål nås i samma candle. Affärer som fortfarande är öppna i slutet av intervallet stängs inte artificiellt.

Resultatet är oberoende affärer per aktie med fast referenskapital, **inte** en gemensam portfölj. Kapital kan vara upptaget i flera samtidiga positioner utan global budgetkontroll. Därför visas inte CAGR, portföljavkastning eller portföljdrawdown. Måtten är antal affärer, träffandel, nettoresultat i initiala riskenheter R och profit factor baserat på R.

Nuvarande bolagsmetadata får inte användas i historiska tester som om den varit känd då. Backtestet avvisar därför aktiva börsvärdes-, sektor- och rapportfilter. Ett seriöst strategiutvärderingssteg behöver avnoterade bolag, historiskt korrekt universum och metadata, hantering av bolagshändelser samt orörda testperioder. Splitjusterade priser är här en normaliserad forskningsserie och återskapar inte exakt historisk positionsstorlek.

## Utveckling

### Ny jämförelse med högst 10 innehav

Kör **Actions → Capped portfolio research (5, 6, 10 holdings)** för 18 fördefinierade femårsjämförelser med tak på 5, 6 eller 10 samtidiga innehav, marknadsfilter och gemensamma riskgränser. Denna serie använder split- och avknoppningsjusterade forskningspriser samt separat instrumenthistorik för nya Biohaven. Se [protokollet](docs/concentrated-protocol-20261004.md) för exakta regler och kvarvarande begränsningar. Alla varianter begränsas till högst 10 innehav; gamla rapporter och den tidigare 36-variantserien bevaras. Körningen skickar inga order och ändrar inte dashboardens strategi.

### Portföljtest med gemensamt kapital

Workflowens val `allocation=all_in` investerar hela tillgängliga kapitalet i en aktie åt gången, utan belåning. Hela aktier avrundas nedåt och courtage reserveras. Nya signaler ignoreras medan positionen är öppen. Breakoutregler, rangordning och exits är desamma, medan riskbudgeten på 0,5 % och positionsgränsen på 15 % inte används för storleken. Samma körning räknar om standardläget på exakt samma hämtade data för jämförelse. Lokalt: `python -m breakout_lab.portfolio --years 2 --capital 100000 --allocation all_in`.

Välj **Actions → Portfolio backtest → Run workflow** på GitHub. Standardvalen är två års test och 100 000 USD. Samma tre Secrets som för dashboarden används. Körningen hämtar ett extra år före testperioden för indikatorernas uppvärmning och använder hela det upptäckta nuvarande universumet.

Detta separata test har en gemensam kontantbudget, hela aktier, återinvestering, 0,5 % riskbudget och högst 15 % av aktuellt eget kapital per position. Ingen belåning används. Köp sker vid nästa sessions öppning efter breakout + volym + MACD. Befintliga exits används: stop under basen, 2R-mål eller efter 20 candles. **En separat MACD-säljsignal finns inte.** När flera signaler konkurrerar rangordnas de med föregående stängnings poäng, relativ volym, lägst ATR-extension och ticker.

Öppningsgap kan frigöra kapital före nya öppningsköp. Intradagsförsäljningar kan inte finansiera samma dags tidigare öppningsköp. Likviddagar modelleras inte; återanvändning av försäljningslikvid samma dag förutsätts. Öppna slutpositioner markeras till senaste stängning. Resultatet inkluderar 10 baspunkters slippage per sida och 0,005 USD per aktie i courtage per sida. Utdelningar, ränta, skatt och växelkurs ingår inte. SPY jämförs som kursavkastning utan utdelningar.

Rapporten visas i körningens sammanfattning. Artefakten `portfolio-report` innehåller aggregerad rapport och kontokurva, samt en fil med individuella affärer krypterad med din `DASHBOARD_PASSPHRASE`. Artefakten sparas en dag; körningens sammanfattning finns kvar. Pages-flikens tidigare test visar fortfarande oberoende affärer för senaste året.

Testet använder nu aktiva bolag och namnheuristik för instrumenttyp, vilket ger överlevnadsbias. Det är därför inte ett historiskt komplett börsuniversum eller ett orört test av en på förhand bevisad strategi.

Lokalt med samma miljövariabler och fria krypteringspaket:

```bash
python -m breakout_lab.portfolio --years 2 --capital 100000
```

```bash
python -m unittest discover -s tests -v
```

Lokal analys och demo behöver bara Python-standardbiblioteket. Krypterade Pages-byggen använder också det fria paketet `cryptography` från `requirements-pages.txt`. Frontend använder vanlig HTML/CSS/JavaScript och canvas. SQLite lagrar data. Python-servern lyssnar endast på `127.0.0.1` och accepterar endast lokala Host-headers och samma Origin. Den är byggd för lokal användning, inte offentlig hosting.

```text
breakout_lab/
  models.py       Datamodeller och inställningsvalidering
  indicators.py   SMA, EMA, MACD och ATR
  engine.py       Universum, signalregler och riskplan
  backtest.py     Affärssimulering och jämförelse
  providers.py    Alpaca och CSV-import
  storage.py      SQLite och atomisk uppdatering
  server.py       Lokalt API och webbgränssnitt
  pages.py        Statisk export och krypterade snapshotfiler
  cli.py          Kommandon
  static/         Dashboard
tests/            Beräkning, kausalitet, data och API
```

## Bygg statiska filer lokalt (valfritt)

```bash
python -m breakout_lab build-site --source demo --repository DrinasKastrati/Breakout_stock
python -m http.server --directory dist/site 8080
```

Öppna http://localhost:8080. Filer fungerar även under GitHub Pages repoundermapp. För personliga marknadsdata: installera `requirements-pages.txt`, sätt de tre hemligheterna i miljön och välj `--source alpaca`. Exporten avvisar okrypterade riktiga data. `--force` hämtar om korrigerad historik eller gör ett uttryckligt byte till demo. Sidan publiceras av workflowen; genererade filer checkas inte in i kodrepot.

Schemat är polling efter dagsstängning, inte en realtidsström eller garanterad exakt leveranstid. GitHub kan fördröja schemalagda körningar. Workflowen underhåller en enkel aktivitetsfil en gång per månad så att GitHub inte stänger av schemat efter 60 dagars inaktivitet. Den använder standard Ubuntu-runners, kortlivade artefakter och en begränsad snapshotcache.

## Nästa utvecklingssteg

1. Validera Alpaca-integrationen med egna nycklar och kuraterad instrumentmetadata.
2. Strömma ingestion och läsa en akties historik i taget för stora universum.
3. Lägg till historiskt korrekt universum och portföljbudget med sektorgränser.
4. Bygg 4H från lägre tidsupplösning med uttrycklig sessionsankring, helgdagskalender och separat volymnormalisering för sista, kortare blocket.
5. Kör nya signaler i simulerad handel och granska resultat före eventuell orderintegration.

## Källor för datakontrakt

- [Alpaca: Historical bars](https://docs.alpaca.markets/us/reference/stockbars)
- [Alpaca: Assets](https://docs.alpaca.markets/us/reference/get-v2-assets-1)
- [Alpaca: Calendar](https://docs.alpaca.markets/us/reference/legacycalendar)
- [Alpaca: Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
- [GitHub Pages och kostnadsfria publika repos](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [GitHub Actions schemalagda körningar](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Alpaca: begränsning av vidarepublicering](https://alpaca.markets/support/redistribute-alpaca-api)
- [Fidelity: MACD](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd)
- [Fidelity: ATR](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr)

Kodens regler är projektets egna definitioner. Källorna används för indikator- och API-konventioner och utgör inte belägg för strategins lönsamhet.
