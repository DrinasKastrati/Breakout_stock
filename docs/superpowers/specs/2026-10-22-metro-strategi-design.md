# Metro-strategin och strategibyte — design

Datum: 2026-10-22. Status: utkast för godkännande.

## 1. Syfte och varför

Breakout Lab kör i dag en enda strategi (breakout, `docs/strategy.md`). Ägaren vill kunna köra
tre strategier och byta mellan dem utan att de krockar — särskilt inte i grafen — och utan att
sidan blir rörig. Den här designen täcker **strategi 2: Metro**, och den struktur som strategi 3
senare ska kopplas in i. Strategi 3 är ännu inte beskriven och ingår inte.

Metro bygger på en analysmall (Metro Finans metodik, ägarens prompt) i fem steg: makro & sentiment,
tekniska nyckelnivåer, scenarier (if/then), risk/reward, slutsats. Mallen är skriven för en
människa eller en AI-modell som analyserar en aktie i taget. Här översätts steg 2–5 till
mekaniska, backtestbara regler som körs på hela universumet (~6000 aktier, 1D), och steg 1 delas i
en mekanisk del (marknadsläge) och en visad men icke-styrande del (sentiment per aktie).

Ägaren gav fria händer för utförande och utseende. Allt som inte uttryckligen står som ägarens
beslut nedan är designerns val och får ifrågasättas.

## 2. Ägarens beslut

- Metro byggs först; strategi 3 tas efter att Metro är klart.
- Upplägg **B** för strategibyte (se §6): en strategi aktiv i taget i hela sidan, men listan och
  grafhuvudet visar vad de andra strategierna säger om samma aktie.
- Sentimentbedömning per aktie ska finnas om den gynnar oss. Delar av Vecko_agent får återanvändas.
- Inga API:er som kostar pengar. Sentiment = marknadens reaktion på nyheten + djupanalys på
  begäran via Vecko_agent (§5.6).
- Godkände spelplanen: marknadsläge mekaniskt; sentiment per aktie bara för kortlista och
  **påverkar inte signalen**; nivåer ur swing-pivåer; trigger vid stängning bortom nivå; R/R ≥ 2;
  "Sälj" = sälj om du äger / undvik, ingen blankning.

## 3. Mål, icke-mål, anti-mål

**Mål**
1. Metro som egen strategi med egna statusar, nivåer, plan, backtest och inställningar.
2. Strategibyte enligt upplägg B, där en tredje strategi kan läggas till utan att ändra sidans
   struktur.
3. Marknadsläge (Risk-on / Neutral / Risk-off) som mekanisk del av Metro. Backtestet visar
   variant med och utan regimfilter; själva bedömningen av filtret görs i protokolltestet (§5.5).
4. Kontextpanel per aktie i kortlistan: färska nyheter med marknadens reaktion, och knapp för
   djupanalys i Vecko_agent.

**Icke-mål**
- Strategi 3.
- Blankning, kortsidans backtest, orderläggning.
- Intradag/4H.
- Ändringar i Vecko_agent.
- Ändringar i forskningsmodulerna (`research.py`, `portfolio.py`, `concentrated.py`,
  `selection_study.py`, `experiments.py`) och deras workflows. De fortsätter köra breakout.
- Backtest av sentiment (se §5.6 varför).
- Protokollfört femårstest av Metro (eget steg efter detta bygge, §5.5).

**Anti-mål** — misslyckande även om det tekniskt fungerar:
- Grafen visar flera strategiers linjer samtidigt.
- Breakoutens resultat ändras av bygget. Breakoutrader, räkningar och backtest ska vara identiska
  före och efter för samma data och `config.json`.
- Sentiment presenteras som bevisat eller påverkar status utan mätning.
- Okrypterade Alpaca-data eller nyheter hamnar på Pages eller i det publika repot. Nycklar läcker.
- Metros regler justeras efter att backtestet visat resultat (se §5.5).

## 4. Begränsningar

- Gratis drift: GitHub Actions + Pages, Alpaca Basic. Publikt repo; allt riktigt innehåll
  krypteras som i dag (`pages.py`). Alpacas data — även nyheter — får inte vidarepubliceras.
- Sitebudget 180 MB (`pages.py`). Två strategiers rader för ~6000 aktier ska rymmas.
- Python 3.11–3.13, inga nya tunga beroenden. Frontend är vanilla JS + canvas (`app.js`).
- Kausalitet som i `docs/strategy.md`: signal vid `t` använder bara data känd vid `t`:s stängning.
- Användarens globala regel: trösklar sätts **innan** data finns; ett underlag som använts för att
  hitta ett mönster kan inte döma det.

## 5. Metro — regler

Alla parametrar nedan är förval som fastställs i och med denna design. Indikatorer (SMA, ATR 14,
`ATR_prev = ATR[t-1]`) följer `docs/strategy.md`. SMA 200 tillkommer.

### 5.1 Swing-pivåer och nivåer (steg 2)

- Swing high vid `j`: `high[j]` är strikt högsta inom `[j-k, j+k]`, `k = pivot_span = 5`.
  Swing low spegelvänt. En pivå vid `j` är **känd först vid `j+k`**; vid `t` används bara pivåer
  med `j + k ≤ t-1`. Signalcandlen får inte skapa sin egen nivå.
- Pivåer inom `level_lookback = 250` candles bakåt används.
- Kluster, **förankrat** (designerns val): sortera pivåerna (highs och lows tillsammans) efter pris
  stigande. Första pivån startar ett kluster; nästa pivå läggs till om dess pris ligger inom
  `cluster_atr = 0.5 × ATR_prev` från klustrets **första** pivå, annars startar den ett nytt.
  Nivå = medelpris; `touches` = antal pivåer. Kedjad sammanslagning används inte, eftersom den kan
  slå ihop ett helt sidledsintervall till en nivå.
- **Primärt motstånd R1** = närmaste nivå strikt över `close[t-1]`. **Sekundärt R2** = nästa över R1.
  **Primärt stöd S1** = närmaste nivå strikt under `close[t-1]`. **S2** = nästa under S1.
  Nivåerna bestäms av `close[t-1]` så att dagens candle bara kan bryta, inte flytta, dem.
- Saknas R1 eller S1 → status `avvakta` med orsak "Nivå saknas".

### 5.2 Trend

- **Bullish**: `close > SMA50 > SMA200` och de två senaste kända swing lows stigande.
- **Bearish**: `close < SMA50 < SMA200` och de två senaste kända swing highs fallande.
- **Sidledes**: allt annat.

### 5.3 Scenarier, mål och stop (steg 3–4)

- **Bullish trigger**: `close[t] > R1 + 0.1 × ATR_prev` och `close[t-1] ≤ R1` (färskt brott),
  trend ≠ bearish.
- **Target 1** = R2. Saknas R2: `R1 + (R1 − S1)` (uppmätt rörelse). **Target 2** = nivån efter R2,
  annars `R1 + 2 × (R1 − S1)`.
- **Stop (invalidering)** = `R1 − 1.0 × ATR_prev`: brottet är felaktigt om kursen faller tillbaka
  klart under nivån.
- **R/R** = `(T1 − close[t]) / (close[t] − stop)` vid utlöst bullish trigger. Krav: `≥ min_rr = 2.0`.
  **Rättelse 2026-10-22 (granskning):** utan utlöst trigger visas planerad R/R vid triggern,
  `(T1 − trigger) / (trigger − stop)`; räknat från dagens stängning blev värdet godtyckligt stort nära stop.
- **Bearish trigger**: `close[t] < S1 − 0.1 × ATR_prev` och `close[t-1] ≥ S1`. Nedsidesmål
  S2 respektive `S1 − (R1 − S1)` visas, men handlas inte.
- **Sidledes**: inget brott, kurs mellan S1 och R1.

Positionsstorlek: befintlig `position_plan` (`risk_fraction`, `max_position_fraction`,
`account_equity`), men med T1 som mål i stället för `reward_risk × risk`.

### 5.4 Marknadsläge (steg 1, mekaniskt) och statusar (steg 5)

- **Bredd** vid `t` = andel aktier med `close > SMA50`. Nämnaren (designerns val) = aktier som
  vid `t` klarar `universe_reasons`, prisgränsen och likviditetsfiltret (samma som breakout, räknat
  dag för dag även i backtestet) och har SMA50 definierad. `min_history` krävs inte för bredden.
  Aktier som saknar candle för dagen `t` räknas inte.
- Indexserie: `metadata["benchmark_symbol"]` (SPY för Alpaca, demons benchmark för demodata).
- **Risk-on**: SPY över SMA200 och bredd ≥ 50 %. **Risk-off**: SPY under SMA200 och bredd < 40 %.
  **Neutral**: övrigt. Ett läge per handelsdag, gemensamt för alla aktier.

Statusar, i prioritetsordning:

| Status | Villkor |
|---|---|
| `filtrerad` | Universum-, historik- eller likviditetsfilter (samma som breakout) |
| `köp` | Bullish trigger + R/R ≥ 2 + läge ≠ Risk-off |
| `bevaka` | Bullish trigger men R/R < 2 eller Risk-off; **eller** trend ≠ bearish, ingen bearish trigger och `close` inom 1 ATR under R1 (**rättelse 2026-10-22:** utan villkoret om bearish trigger visades ett stödbrott som bevaka när R1 låg nära) |
| `sälj` | Bearish trigger ("sälj om du äger / undvik") |
| `avvakta` | Övrigt |

Varje rad får mänskliga orsaker, som breakouten (`reasons`), t.ex. "R/R 1,6 under kravet 2",
"Risk-off: köpsignal nedgraderad".

### 5.5 Backtest

- Endast `köp`-signaler, long. Entry nästa öppning med slippage. Avstå om entry ≤ stop eller om
  entry ger R/R < 2 mot T1 (räknat om med faktiskt entrypris).
- Exit: hela positionen vid stop eller T1, konservativ OHLC-ordning och tidsgräns
  `max_holding_bars` som i `backtest.simulate_trade`. T2 visas men används inte i v1.
- Två varianter rapporteras: **Metro** och **Metro utan regimfilter**. Skillnaden mäter om
  marknadsläget tillför något. Fler varianter läggs inte till i efterhand utan att det redovisas
  som ett nytt test.
- Samma begränsningstexter som breakouten: separata affärer, överlevnadsbias, inga sannolikheter.
  Dessutom: affärer i olika aktier överlappar i tid och delar marknadsrörelse, så antalet affärer
  är inte antalet oberoende observationer. Bredden räknas på dagens universum och bär därför
  överlevnadsbias bakåt.
- **Ägarens beslut (2026-10-22):** dashboardens backtest är det rullande året som `pages.py`
  redan använder (`as_of − 365 dagar`). Det märks i gränssnittet som **"Visning, inte bevis"**:
  fönstret flyttas dagligen och ses löpande, så det kan inte avgöra om Metro eller regimfiltret
  fungerar. Ingen beslutsregel knyts till det.
- Bedömningen görs i ett **separat, senare steg**: ett protokoll med kriterier fastställda före
  körningen och ett femårstest i eget workflow, enligt mönstret i
  `docs/research-protocol-20261004.md`. Det ingår inte i detta bygge.
- Parametrarna i §5 fastställs i denna design och ska vara oförändrade när protokolltestet körs.

### 5.6 Sentiment per aktie (visas, styr inte)

- **Kortlista**: alla `köp` plus `bevaka` med bullish trigger, sorterade på R/R, högst
  `shortlist_size = 20`.
- **Nyheter**: Alpaca News API (`GET /v1beta1/news`, `symbols`, `start`, `limit`, Benzinga-källa),
  senaste 3 handelsdagarna, rubrik + sammanfattning. **Verifierat 2026-10-22** med ägarens nycklar.
  **Rättelse 2026-10-22:** "5 per aktie" visade bara senaste dygnet för stora bolag; nu ett anrop per
  aktie och högst 5 artiklar per reaktionsdag. Fungerar anropet inte visas
  "Nyheter ej tillgängliga" och resten av bygget påverkas inte.
- **Ägarens beslut (2026-10-22): inga betal-API:er** (ingen Anthropic eller annan LLM-tjänst).
  Sentiment per aktie = **marknadens reaktion på nyheten**, mekaniskt:
  - Reaktionsdag för en artikel: den session vars stängning först kommer efter `created_at`
    (New York-tid; publicerad före 16.00 en handelsdag → samma dag, annars nästa session). Ligger
    reaktionsdagen efter `as_of` → "Reaktion okänd än".
  - `excess` = aktiens dagsavkastning − indexets dagsavkastning samma dag. `rvol` = dagens volym /
    snittvolym de 20 föregående sessionerna.
  - **Positiv**: `excess ≥ +2 %` och `rvol ≥ 1.5`. **Negativ**: `excess ≤ −2 %` och `rvol ≥ 1.5`.
    Annars **ingen tydlig reaktion**. Flera artiklar samma dag delar reaktionsdag.
  - Sammanfattning per aktie: senaste reaktionsdag med tydlig reaktion, annars "ingen tydlig
    reaktion". Ingen "fälla"-flagga i v1.
  - Det mäter hur marknaden tog emot nyheten, inte textens ton. Det är gratis, körs i Actions och
    kan senare backtestas mot Alpacas nyhetsarkiv (från 2015) utan språkmodellens läckageproblem.
- **Djupanalys på begäran via Vecko_agent**: knapp "Djupanalys i Vecko_agent" per aktie som öppnar
  `https://github.com/DrinasKastrati/Vecko_agent/issues/new` med titel `analys: TICKER` och samma
  brödtext som Vecko_agents egen knapp ("Begäran om aktieanalys för TICKER. Skicka in ärendet så
  köas det automatiskt."), plus länk till Vecko_agents dashboard. Analysen körs i Vecko_agents
  befintliga, nyckellösa kö (Cowork). Breakout Lab läser inte tillbaka resultatet i v1.
  Overifierat: flödet är läst ur Vecko_agents `CLAUDE.md` och `assets/app.js`, inte provkört härifrån.
- **Varför reaktionen inte styr**: det finns inget mätt samband ännu. Varje dags reaktion per
  kortlisteaktie loggas (krypterat, i sitesnapshoten och vidare till nästa) så att mätning blir
  möjlig. Ingen tröskel för när den får börja styra sätts nu.
- **Vecko_agent**: dess `state/news_feed.json` saknar tickerfält och har ~90 rubriker/dag för alla
  bolag, så den används inte per aktie. Dess dagliga scout-rapport
  (`reports/scout/rapport-yymmdd.md`, publikt repo) visas som **marknadsberättelse** i
  Metro-vyn: senaste rapportens marknadsöversikt, med datum och länk. Den påverkar inte
  marknadsläget. Saknas eller är den äldre än 3 kalenderdagar visas inget.

## 6. Sidan — upplägg B

Ägaren valde B. Skissen ligger i `.superpowers/brainstorm/`.

- **Strategireglage** i toppfältet: `Breakout | Metro | Strategi 3 (kommer, inaktiv)`. Valet styr
  hela sidan: siffror, kandidatlista, graf, plan, backtest, inställningar, metodtext. Valet sparas
  i URL-hash (`#metro`) och, om möjligt, i `localStorage`.
- **Accentfärg per strategi** (breakout blå, Metro lila) i reglage, rubriker och grafens
  strategilinjer, så att det alltid syns vilken strategi som visas.
- **Siffror**: Breakout som i dag. Metro: Köp / Bevaka / Sälj / Avvakta / Filtrerad, plus
  marknadslägesbricka.
- **Kandidatlista**: aktiv strategis status och nyckeltal (Metro: R/R), plus en smal kolumn per
  övrig strategi med kort statusbricka. Filter och sökning gäller aktiv strategi.
- **Graf**: candles, volym och MACD som i dag. **Endast aktiv strategis nivåer ritas.** Metro: S1,
  S2, R1 (trigger), R2, T1, T2, stop, med etiketter; nivåer utanför synligt prisintervall ritas
  inte. Ovanför grafen: chips med övriga strategiers status för vald aktie; klick byter strategi.
- **Planpanel**: Metro visar de fem stegen i mallens ordning — Makro & sentiment (läge,
  marknadsberättelse, nyheter med marknadsreaktion för kortlisteaktier, knapp för djupanalys i
  Vecko_agent), Nivåer, Scenarier, R/R, Slutsats.
- **Backtest**: följer reglaget. Metro visar sina två varianter.
- **Inställningar**: gemensamma (universum, risk, kostnader) och strategispecifika separat.

## 7. Struktur (designerns val, byggaren förfinar)

- Ett strategiregister: varje strategi har id, namn, `evaluate(...)`, statusvokabulär, nivåer för
  grafen och backtestvarianter. Breakouten kopplas in genom att `engine.evaluate` omsluts, inte
  skrivs om.
- `backtest.simulate_trade` generaliseras så att stop, mål och högsta tillåtna entry kommer från
  kandidaten. För breakouten ska beteendet vara identiskt.
- Gemensamt radformat för grafen: `levels: [{kind, price, label}]`.
- Scan-payloaden får `strategies: {breakout: {rows, counts}, metro: {rows, counts, regime,
  narrative}}`. Befintliga fält för breakouten bör ligga kvar så länge något läser dem.
- `config.json`: befintliga fält oförändrade (forskningsmodulerna använder dem) och ett nytt
  `metro`-block för §5-parametrarna. Validering som `Config.from_dict`. Obs: `Config.from_dict`
  avvisar okända nycklar och alla forskningsmoduler läser `config.json` genom den. `models.py` måste
  därför ändras så att `metro`-blocket accepteras eller lyfts ut innan breakout-`Config` byggs.
  Forskningsmodulerna ska inte behöva ändras.
- Nya krypterade payloadsökvägar måste släppas igenom av sökvägskontrollerna i
  `pages.decrypt_file` och `data-client.js`.
- Lokala servern (`server.py`) och statiska klienten (`data-client.js`) ska båda stödja reglaget.
- `.superpowers/` läggs i `.gitignore`.

## 8. Vad som lämnas åt byggaren

- Exakt modulindelning, funktionsnamn och filnamn.
- Prestanda för pivåer och bredd över ~6000 aktier × flera år.
- Visuell detaljutformning inom §6, inklusive mobil.
- Hur reaktionsloggen förs vidare mellan snapshots, inom kravet att den är krypterad.

## 9. Verifiering

- Alla befintliga tester passerar oförändrade.
- Nytt test: breakoutrader, räkningar och backtest identiska före och efter för demodatan.
- Kausalitetstest för pivåer: att lägga till framtida candles ändrar inte nivåer eller status vid `t`.
- Enhetstester för nivåkluster, trend, varje status, R/R-grind, regimens nedgradering och backtestets
  entry/exit.
- Nyheter och reaktion: tester med mockade API-svar, inklusive fel; reaktionsdag före/efter 16.00
  och efter `as_of`; trösklarna ±2 % och 1,5× exakt på gränsen.
- Körning: `python -m breakout_lab demo` + `serve` visar båda strategierna; byte ändrar grafens
  linjer; `build-site --source demo` lyckas.
