# Forskningsprotokoll fastställt före körningen

Mål: bedöma 36 breakoutstrategier och kombinationer över fem år med 100 000 USD, gemensamt striktare aktieurval och gratis historisk Alpaca SIP. Undersökningen ändrar inte grundstrategin på hemsidan och skickar inga order.

Kör `Deep strategy research (36 variants)` från GitHub Actions. Kapital är det enda körningsvalet; period och strategiuppsättning ligger i versionshanterad kod. Rapporten anger datasetets och testdefinitionernas SHA256 så att jämförelsen går att identifiera exakt.

## Bedömning innan resultatet är känt

En kandidat uppfyller undersökningskraven först när samtliga villkor gäller:

- Positiv avkastning under hela femårsperioden.
- Högst 20 % maximal nedgång mätt vid dagsstängningar.
- Minst 100 avslutade affärer och profit factor minst 1,15 efter modellerade kostnader.
- Minst fyra positiva årskonton av fem; varje år börjar med nytt kapital och inga positioner.
- Positiv femårsavkastning med 30 baspunkters slippage per sida, jämfört med 10 i grundtestet.
- De fem största vinnarna utgör högst hälften av sammanlagda vinster.

Rapporten visar också SPY utan utdelningar, kapitalexponering, rullande 252-dagarsresultat, förlust-/vinststorlekar, exitbidrag och vad som händer om de fem största vinnarnas resultat bokföringsmässigt tas bort. Den sista beräkningen ändrar inte affärsföljden och är ingen ny simulering.

Vi fortsätter inte att ändra parametrar tills ett positivt historiskt resultat råkar dyka upp. Hela den fastställda serien redovisas, inklusive misslyckade kombinationer. Om ingen uppfyller kraven är det ett giltigt resultat. Ingen vinnare aktiveras automatiskt.

## Testidéer

Grundstrategin, 100 %-kontroll, golden cross 10/20/40 dagar, SPY över stigande SMA200, relativ styrka mot SPY över 63 bars, högre likviditet, begränsad volatilitet och stopdistans, positions-/portföljriskgränser, misslyckad breakout-exit, marknads-exit, initial 2 ATR-stop, 40-dagars innehav, 3R-mål, trailing utan vinstmål, 55-dagars breakout med 10-dagars kanalexit, 2/3 ATR trailing och lägre risk. Exakta kombinationer finns i `breakout_lab/research.py:variants()` och återges i rapportartefakten.

Alla köp sker tidigast vid öppningen efter en avslutad signal. Close-baserade säljsignaler verkställs vid nästa öppning. Stop och mål som redan var kända används på samma sätt som tidigare; stop prioriteras om dagens OHLC inte avslöjar ordningen. Intradagslikvid kan inte finansiera tidigare öppningsköp. Ingen belåning.

Marknadsfiltret styr normalt endast nya entries. En separat variant säljer också när marknadsvillkoret blir falskt. Risk till stop är beräknad risk vid köpbeslutet och ingen garanterad förlustgräns; gap och förändrade kurser kan överstiga den.

## Perioder och tidigare granskad historik

Perioden slutar vid senaste kompletta sessionen. Ett extra år används för indikatorernas uppvärmning. Fem separata årsdagssnitt samt sammanhängande tidiga/sena fönster granskas.

Walk-forward väljer efter 2, 3 och 4 års träning högst tidigare CAGR/nedgång bland strategier med minst 20 affärer, positiv avkastning och högst 25 % nedgång. Nästa år utvärderas med nytt kapital. Om ingen kvalificerar ligger pengarna kontant. Valet använder ingen framtida periods resultat, men vi har redan granskat samma historiska datum i tidigare tester: detta är ingen orörd validering. En framtida papperstestperiod behövs före starkare slutsatser.

## Gratis datakällor och kvarvarande begränsningar

- [Nasdaq symbolkatalog](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs): ETF=N, Test Issue=N och uttrycklig common/ordinary/capital stock i namnet. Andra instrumentbenämningar utesluts. Katalogen är aktuell, inte historisk.
- Historiska splitjusterade 1D-bars via Alpaca Basic, med fördröjt SIP-slutdatum. Rå marknadsdata och affärer ligger endast i den krypterade rapporten.
- WOLF och RNA utesluts gemensamt på grund av olöst instrumentkontinuitet. Någon fullständig bolagshändelse-/instrument-ID-bok finns inte; övriga möjliga avbrott är inte helt granskade.
- Dagens aktiva aktier medför överlevnadsbias. Avnoterade historiska bolag saknas. Utdelningar, skatt, kontantränta, valutaförändringar och likviddagar ingår inte.
- Punkt-i-tid sektor- och fundamentalmetadata saknas, så sådana filter och sektorkorrelationstak införs inte som om de vore verifierade.

[AQR:s momentumforskning](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum) motiverar trend- och styrketester, men gäller andra instrument och bevisar inte denna aktiestrategi. [Bailey m.fl.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) beskriver risken med att välja strategier från många backtester; därför redovisas hela försöksserien och begränsningarna.
