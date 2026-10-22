# Metro-strategin v0.1

Metro översätter en analysmall i fem steg (makro & sentiment, nivåer, scenarier, risk/reward, slutsats) till mekaniska regler för dagliga candles. Design och skäl: [superpowers/specs/2026-10-22-metro-strategi-design.md](superpowers/specs/2026-10-22-metro-strategi-design.md). Alla värden nedan är förval i `config.json` → `metro` och fastställdes innan några resultat sågs.

## Tidsaxel och universum

Samma som breakouten ([strategy.md](strategy.md)): signal vid `t` använder bara data känd vid `t`:s stängning, `ATR_prev = ATR(14)[t-1]`, samma universum-, historik-, pris- och likviditetsfilter. SMA 200 tillkommer.

## 1. Marknadsläge (makro, mekaniskt)

- Bredd vid `t`: andel aktier med `close > SMA50` bland aktier som klarar universum, prisgräns och likviditet den dagen och har SMA 50. `min_history` krävs inte.
- **Risk-on**: index (SPY) över SMA 200 och bredd ≥ `breadth_risk_on` = 50 %.
- **Risk-off**: index under SMA 200 och bredd < `breadth_risk_off` = 40 %.
- **Neutral**: allt annat, även när indexhistorik eller behöriga aktier saknas.

Risk-off gör Köp till Bevaka när `use_regime` = true.

## 2. Nivåer

- Swing high vid `j`: `high[j]` strikt högre än alla andra highs i `[j−5, j+5]` (`pivot_span` = 5). Swing low spegelvänt. Pivån är känd först vid `j + 5`; vid `t` används bara pivåer med `j + 5 ≤ t − 1`, högst `level_lookback` = 250 candles bakåt.
- Highs och lows sorteras på pris och slås ihop förankrat: en pivå ansluter till ett kluster om den ligger inom `cluster_atr` = 0,5 × ATR_prev från klustrets första pivå. Nivån är klustrets medelpris.
- R1/R2/R3 är de närmaste nivåerna strikt över `close[t−1]`, S1/S2 de närmaste strikt under.
- Trend: **bullish** om `close > SMA50 > SMA200` och de två senaste kända swing lows stiger; **bearish** om `close < SMA50 < SMA200` och de två senaste swing highs faller; annars sidledes.

## 3. Scenarier

| Scenario | Regel |
|---|---|
| Bullish | `close[t] > R1 + 0,1 × ATR_prev` (`trigger_atr_buffer`), `close[t−1] ≤ R1`, trend inte bearish |
| Bearish | `close[t] < S1 − 0,1 × ATR_prev`, `close[t−1] ≥ S1` |
| Sidledes | Inget brott: avvakta |

T1 = R2, annars `R1 + (R1 − S1)`. T2 = R3, annars `R1 + 2 × (R1 − S1)`, och bara om T2 > T1. Nedsidesmål (visas, handlas inte): S2, annars `S1 − (R1 − S1)`.

## 4. Risk/reward

Stop = `R1 − stop_atr × ATR_prev` (1,0). Vid utlöst köpsignal: `R/R = (T1 − close) / (close − stop)`. Utan utlöst signal visas planerad R/R vid triggern: `(T1 − trigger) / (trigger − stop)`. Köp kräver `R/R ≥ min_rr` = 2. Positionsstorlek som breakouten (`risk_fraction`, `max_position_fraction`, `account_equity`), med T1 som mål.

## 5. Status

| Status | Villkor, i prioritetsordning |
|---|---|
| Filtrerad | Universum-, historik-, pris- eller likviditetsfilter, eller ATR saknas |
| Köp | Bullish + R/R ≥ 2 + marknadsläge inte Risk-off |
| Bevaka | Bullish men R/R < 2 eller Risk-off; eller trend inte bearish, inget brott under stöd och close inom `watch_distance_atr` = 1 ATR under R1 |
| Sälj | Bearish: sälj om du äger, undvik annars. Ingen blankning |
| Avvakta | Övrigt, och alltid när R1 eller S1 saknas |

Rättelse efter granskning 2026-10-22: tidigare kunde ett brott under stöd visas som Bevaka när R1 låg nära, och R/R för ej utlösta rader räknades från dagens stängning (upp till flera hundra nära stop). Båda är rättade enligt ovan.

## Nyheter och marknadsreaktion (visas, styr inte)

För kortlistan (Köp och utlösta Bevaka, högst `shortlist_size` = 20, sorterade på R/R) hämtas Alpaca-nyheter för cirka `news_days` = 3 handelsdagar. Varje artikels reaktionsdag är sessionen vars stängning först kommer efter publiceringen (före 16.00 New York-tid samma dag, annars nästa session). Positivt mottagen: aktien minst +2 % mot index och minst 1,5 × snittvolymen för 20 sessioner; negativt mottagen spegelvänt; annars ingen tydlig reaktion. Trösklarna ligger i koden (`breakout_lab/reaction.py`) och är inga inställningar.

Det mäter marknadens reaktion, inte textens ton, och används inte i statusen. Varje dags reaktion per kortlisteaktie loggas krypterat så att sambandet kan mätas framåt. Nyheter hämtas med ett anrop per aktie (högst 4 sidor à 50) och högst 5 artiklar sparas per reaktionsdag, så att många artiklar efter stängning inte döljer tidigare sessioner. Nyhets-API:t fungerar med ägarens Alpaca-nycklar (provkört 2026-10-22). Fallerar anropet visas "Nyheter ej tillgängliga".

Marknadsberättelsen är avsnittet "Marknadsöversikt" ur Vecko_agents senaste scout-rapport (högst 3 kalenderdagar gammal). Knappen "Djupanalys i Vecko_agent" öppnar ett förifyllt issue `analys: TICKER` i Vecko_agents nyckellösa kö. Inga betal-API:er används.

## Backtest

Bara Köp, long. Entry nästa öppning med slippage; avstå om entry ≤ stop eller om R/R mot T1 räknat från det faktiska entrypriset blir < 2. Exit vid stop eller T1 (hela positionen), konservativ OHLC-ordning och tidsgräns som breakouten. Två varianter: Metro och Metro utan regimfilter.

Dashboardens rullande år ses löpande och är en **visning, inte ett bevis**. Affärer i olika aktier överlappar i tid, så antalet affärer är inte antalet oberoende observationer, och bredden bär överlevnadsbias bakåt. En bedömning kräver ett separat protokoll med kriterier fastställda före körningen.
