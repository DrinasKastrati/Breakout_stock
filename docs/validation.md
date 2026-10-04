# Verifiering av v0.2

## Genomförda kontroller

- `python -m unittest discover -s tests -v`: 43 tester passerar lokalt på Python 3.12.
- Samma 43 tester, JavaScript-kontroller och statiskt demobygge passerar också i GitHub Actions på Python 3.11, 3.12 och 3.13: [verifierad körning](https://github.com/DrinasKastrati/Breakout_stock/actions/runs/37166677704). Testad kodcommit: `7b6f937a6e7818371a871fc19ad9ebaa0ca59074`.
- Kommandon för demoinläsning, scanning och backtest har körts.
- `node --check` kontrollerar både `app.js` och `data-client.js`.
- API-tester verifierar scanning, diagramdata, tre backtestvarianter, CSV-export och settingsvalidering.
- Tester verifierar EMA-uppvärmning, MACD/ATR-serier, tidigare motstånd och volymbaslinje, framtidsoberoende signaler, positionsgränser, gap, stop/mål-ordning, kostnader och öppna affärer.
- Datatester verifierar paginering, bortsortering av nyare candles, tidszonsberoende sessionsgräns, metadata för CSV och rollback vid felaktig uppdatering.
- Host- och Origin-skydd testas med nekade främmande requests.
- Statisk export ger samma signaler som Python-motorn. Diagram- och backtestlänkar verifieras och resurser använder relativa sökvägar för Pages repoundermapp.
- WebCrypto-testet kör frontendens riktiga dekrypteringsfunktion i Node mot Python-exporterade AES-GCM-filer. Fel lösenfras och ändrad ciphertext avvisas.
- Riktiga dataset får inte exporteras i klartext. Lösenfrasbyte, pathsäkerhet och avvisad automatisk fallback till demo testas.
- Misslyckad och ofullständig datainhämtning behåller föregående bygge. Oförändrad analys publiceras inte igen; tvingad hämtning kontrollerar data på nytt.
- Fria SIP-anrop får uttryckligt `end` minst 16 minuter gammalt. Request pacing verifieras under Basics 200/minut.
- Demowebbplatsen har byggts två gånger: första körningen skapar ett snapshot, andra rapporterar `changed: false`.
- Arbetsflödesfilerna har parsats som YAML.
- 2026-10-04: repot gjordes publikt, Pages-källan sattes till GitHub Actions och `ENABLE_PAGES=true` sparades via GitHub-hemsidan. Inga datahemligheter finns ännu; automatisk marknadsuppdatering är avstängd.
- Första demopubliceringen lyckades, inklusive 43 tester och keepalive-jobbet: [Pages-körning](https://github.com/DrinasKastrati/Breakout_stock/actions/runs/37167782403). [Publicerad dashboard](https://drinaskastrati.github.io/Breakout_stock/).
- Desktopkontroll i Chrome på den publicerade sidan: kandidatlistan laddas, sökning filtrerar på bolagsnamn, aktiebyte uppdaterar candles/volym/MACD och signalvillkor, och de tre förberäknade backtestvarianterna visas. Skärmbild har granskats; inga konsolfel rapporterades.

## Ej verifierat

- Riktiga Alpaca-anrop: användarens Basic-nycklar saknas i miljön. HTTP-paginering och datakontrakt testas med stubbar.
- Det återkommande schemat och publicering med riktiga Alpaca-data: kräver användarens datahemligheter och `ENABLE_AUTO_UPDATE=true`.
- Mobil rendering, upplåsning av riktiga data i Chrome och CSV-nedladdning på den publicerade sidan. Ett försök att observera CSV-nedladdningen gav timeout i webbläsarverktyget; ingen lyckad nedladdning har bekräftats.
- Fullt amerikanskt universum, verklig likviditet, historiskt instrumentregister och strategins marknadsresultat.

Gränssnittets primära manuella kontroll är desktop + mobil: läs scanning, välj kandidat, granska OHLC/MACD, filtrera listan och kontrollera provenance. På Pages: lås upp, exportera CSV, öppna GitHub-inställningslänken och visa senaste jämförelse. Lokalt: spara risknivå och kör ett eget testintervall. Tester av API är inte ett substitut för visuell kontroll.
