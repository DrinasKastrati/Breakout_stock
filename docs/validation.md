# Verifiering av v0.1

## Genomförda kontroller

- `python -m unittest discover -s tests -v`: 30 tester passerar på Python 3.12.
- Kommandon för demoinläsning, scanning och backtest har körts.
- `node --check breakout_lab/static/app.js`: JavaScript-syntax kontrollerad.
- API-tester verifierar scanning, diagramdata, tre backtestvarianter, CSV-export och settingsvalidering.
- Tester verifierar EMA-uppvärmning, MACD/ATR-serier, tidigare motstånd och volymbaslinje, framtidsoberoende signaler, positionsgränser, gap, stop/mål-ordning, kostnader och öppna affärer.
- Datatester verifierar paginering, bortsortering av nyare candles, tidszonsberoende sessionsgräns, metadata för CSV och rollback vid felaktig uppdatering.
- Host- och Origin-skydd testas med nekade främmande requests.

## Ej verifierat

- Riktiga Alpaca-anrop: nycklar och SIP-behörighet saknas i miljön. HTTP-paginering och datakontrakt testas med stubbar.
- Visuell rendering i webbläsare: Playwright finns, men browser-binären saknas. Ingen skärmbild eller visuell QA har därför genomförts.
- Python 3.11/3.13: konfigurerade i GitHub Actions, men har inte körts lokalt här.
- Fullt amerikanskt universum, verklig likviditet, historiskt instrumentregister och strategins marknadsresultat.

Gränssnittets primära manuella kontroll är desktop + mobil: läs scanning, välj kandidat, granska OHLC/MACD, filtrera listan, spara risknivå, kör ett testintervall och kontrollera provenance. Tester av API är inte ett substitut för visuell kontroll.
