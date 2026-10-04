# Strategispecifikation v0.1

## Tidsaxel

`t` är en avslutad dagscandle. Signalen använder bara information som är tillgänglig senast vid denna candles slut. Historiska signaler använder aldrig framtida candles. `ATR_prev = ATR(14)[t-1]`.

## Universum

- Tillåtna börslabels: NASDAQ, NYSE, AMEX, NYSEAMERICAN, ARCA, BATS.
- Instrumenttyp måste vara `common`. Alpaca-klienten uppskattar typen från namnet och varnar; CSV-import kräver explicit metadata.
- Kurs minst `min_price`.
- Minst `min_history` candles.
- Normal dollaromsättning är medelvärdet av `close * volume` för föregående `lookback` candles, exklusive signalcandlen.
- Eventuellt börsvärde, sektor, exkludering och kommande rapportdatum enligt konfigurationen.
- Aktier vars senaste candle inte motsvarar datasetets senaste session avvisas.

## Indikatorer

EMA för period N startas med SMA för de första N observationerna. Efter detta används `alpha = 2 / (N + 1)`. Värden före uppvärmning är null.

MACD = EMA 12 − EMA 26. Signallinjen är EMA 9 av giltiga MACD-värden. Histogrammet = MACD − signallinjen.

True range = max(high − low, abs(high − tidigare close), abs(low − tidigare close)). Första candles true range är high − low. ATR 14 startas med medelvärdet av de första 14 true ranges och fortsätter med Wilders utjämning `(13 * tidigare ATR + aktuell TR) / 14`.

## Signalen

| Del | Exakt regel |
|---|---|
| Motstånd | Högsta high under `[t-lookback, t)`. |
| Stöd | Lägsta low under samma period. |
| Trend | Close[t] > SMA50[t] och SMA50[t] > SMA50[t−5]. |
| Bas | (Motstånd − stöd) / ATR_prev ≤ max_base_width_atr. |
| Pris | Close[t] > motstånd + breakout_atr_buffer × ATR_prev. |
| Volym | Volume[t] / medelvolym under `[t-lookback, t)` ≥ volume_multiplier. |
| MACD | MACD[t] > signal[t] och histogram[t] > histogram[t−1]. |
| Avstånd | (Close[t] − motstånd) / ATR_prev ≤ max_extension_atr. |

En breakout kräver trend, bas, pris, avstånd samt de volym- och MACD-villkor som är aktiverade. Bevakning kräver trend och bas samt kurs inom `watch_distance_atr` under motstånd till `max_extension_atr` över motstånd. ”Översträckt” innebär att priset passerat breakoutgränsen men överstigit entryavståndet. Status är inte en köporder.

Regelpoängen räknar uppfyllda villkor: trend 25, bas 15, pris 20, volym 15, MACD 15, avstånd 10. Volym och MACD räknas i poängen även om de är avstängda som hårda filter. Poängen är varken kalibrerad sannolikhet eller rangordning efter förväntad avkastning.

Relativ styrka visas som aktiens avkastning under 63 observationer minus benchmarkens avkastning mellan samma datum, i procentenheter. Den ingår inte i urval eller poäng. Saknad benchmark visas som null.

## Entry och exit

Entryreferensen i screenern är signalcandlens stängning. Backtestets köppris är nästa candles öppning × (1 + slippage_bps / 10000). Om detta pris ligger under eller vid stop, eller mer än max_extension_atr över motstånd, avstår testet från köpet.

Stop = stöd − breakout_atr_buffer × ATR_prev. Stopnivån kommer från signalen. Storlek och mål räknas om med det faktiska simulerade entrypriset:

```text
risk_per_share = entry − stop
risk_budget = account_equity × risk_fraction
capital_cap = account_equity × max_position_fraction
shares = min(floor(risk_budget / risk_per_share), floor(capital_cap / entry))
target = entry + reward_risk × risk_per_share
```

Om minst en aktie inte ryms avstår testet från affären. Kostnader ingår i utfall men inte i den nominella riskbudgeten.

Daglig exitkontroll, inklusive entrydagen:

1. Öppning vid eller under stop → fyll vid öppning, med försäljningsslippage.
2. Öppning vid eller över mål → fyll konservativt vid målet, med försäljningsslippage.
3. Low vid eller under stop → stop. Om high också når målet väljs stop, eftersom ordningen är okänd.
4. High vid eller över mål → mål.
5. Efter max_holding_bars → stängningspris med försäljningsslippage.

Om datan slutar före tidsgränsen utan exit räknas affären som öppen och ingår inte i mått över avslutade affärer. Courtaget är `shares × commission_per_share × 2`.

R-multipel = netto-PnL / initial nominell risk. Detta kan bli mindre än −1 vid gap eller kostnader. Endast en affär per symbol är öppen samtidigt. En ny signal kan uppstå vid stängning på exitdagen och leder tidigast till entry nästa candle.

## Valideringsgräns

Kausal indikatorberäkning och konservativ OHLC-exekvering är verifierade av tester. Det undanröjer inte överlevnadsbias, prisjusteringsproblem, saknad instrumentmetadata eller verkliga fillproblem. Backtestets oberoende affärer bildar ingen kapitalbegränsad portfölj. Strategin är inte utvärderad mot riktig marknadsdata i denna miljö.
