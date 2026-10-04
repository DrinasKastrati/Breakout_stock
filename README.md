# Breakout Lab

En körbar första version av en daglig breakoutscreener för amerikanska aktier. Systemet hittar kandidater, visar varför de kvalificerar sig och jämför strategier med och utan volym/MACD. Gränssnittet är på svenska.

**Status: v0.1, lokalt forskningsverktyg.** Demoläget fungerar utan konton eller installation av extra Python-paket. En läsande Alpaca-klient är implementerad; riktig synkronisering kräver egna API-nycklar och rätt dataabonnemang. Inga köp- eller säljorder skickas.

## Kom igång

Kräver Python 3.11 eller senare och operativsystemets tidszonsdata. Kör från projektmappen:

```bash
python -m breakout_lab demo
python -m breakout_lab serve
```

Öppna **http://127.0.0.1:8000**. Avsluta med Ctrl+C.

Demoläget skapar åtta **fiktiva** aktier och 650 syntetiska dagscandles per aktie. Kalendern består av vardagar och representerar inte börsens verkliga helgdagar. Demodata ska endast användas för att undersöka funktioner; dess resultat säger ingenting om strategins förmåga på marknaden.

På system utan IANA-tidszonsdatabas, till exempel vissa Windows-installationer, installera `tzdata` med `python -m pip install tzdata`.

## Det som finns i v0.1

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
- 30 automatiska tester och GitHub Actions för Python 3.11, 3.12 och 3.13.

## Riktiga marknadsdata

### 1. Ange nycklar i miljön

```bash
export ALPACA_API_KEY='din-api-nyckel'
export ALPACA_API_SECRET='din-hemliga-nyckel'
export ALPACA_DATA_FEED='sip'
```

`.env.example` visar variabelnamnen. Applikationen laddar **inte** `.env` automatiskt. Nycklar ska vara servervariabler och får aldrig läggas i frontend eller Git. Applikationen använder enbart GET-anrop till tillgångs-, kalender- och marknadsdataendpoints.

SIP kräver rätt dataåtkomst och används som standard eftersom volymfiltret ska ha bred börstäckning. `iex` kan användas uttryckligen, men representerar en enskild börs. Resultat från de två flödena är inte direkt jämförbara.

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

**”Uppdatera analys” räknar om den lagrade datan.** Kör `sync` igen för att hämta nya kurser. Datasetets session visas alltid i gränssnittet och aktier med saknad senaste session filtreras bort. Kontrollera att sessionen är aktuell innan analysen används.

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

```bash
python -m unittest discover -s tests -v
```

Inga runtimeberoenden utöver Python-standardbiblioteket. Frontend använder vanlig HTML/CSS/JavaScript och canvas. SQLite lagrar data. Python-servern lyssnar endast på `127.0.0.1` och accepterar endast lokala Host-headers och samma Origin. Den är byggd för lokal användning, inte offentlig hosting.

```text
breakout_lab/
  models.py       Datamodeller och inställningsvalidering
  indicators.py   SMA, EMA, MACD och ATR
  engine.py       Universum, signalregler och riskplan
  backtest.py     Affärssimulering och jämförelse
  providers.py    Alpaca och CSV-import
  storage.py      SQLite och atomisk uppdatering
  server.py       Lokalt API och webbgränssnitt
  cli.py          Kommandon
  static/         Dashboard
tests/            Beräkning, kausalitet, data och API
```

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
- [Fidelity: MACD](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd)
- [Fidelity: ATR](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr)

Kodens regler är projektets egna definitioner. Källorna används för indikator- och API-konventioner och utgör inte belägg för strategins lönsamhet.
