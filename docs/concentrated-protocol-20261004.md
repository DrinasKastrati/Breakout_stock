# Ny simulering med högst 10 innehav

Fastställd 2026-10-04 efter användarens önskemål. Fem års test med 100 000 USD, samma gemensamma dataset och alla kombinationer redovisade. Det är ny forskning på redan granskad historik, inte orörd validering.

## Testmanifest

För vart och ett av taken 5, 6 och 10 innehav jämförs:

1. Grundregler med endast innehavstaket tillagt.
2. Grundregler plus marknadsfilter vid köp.
3. Grundregler plus gemensamt risktak.
4. Marknadsfilter plus gemensamt risktak.
5. Golden cross under senaste 20 sessioner plus marknadsfilter.
6. Marknadsfilter, risktak och exit vid nästa öppning efter svag marknadssignal.

Alla 18 varianter har ett absolut tak på högst 10 samtidiga innehav. Taket kontrolleras intradag, vid dagsstängning och i alla reset-/träningsperioder samt kostnadsstress. Grundrisk 0,5 % per köp och max 15 % position. Risktak: max 2 % risk till stoppar, 80 % exponering och 10 % per position vid nya köp. Kursrörelser och gap kan senare överskrida risk-/exponeringsgränserna. Ingen belåning.

Marknadsfilter: SPY stänger över SMA200 och SMA200 är högre än för 20 sessioner sedan. Marknadsexit säljer vid nästa öppning, inte vid signalens stängning. Golden cross kräver ett verkligt SMA50/SMA200-kors under senaste 20 sessioner och fortsatt SMA50 över SMA200.

## Datakontroll

- Alpaca `adjustment=split,spin-off`, dokumenterat i [Historical bars](https://docs.alpaca.markets/us/reference/stockbars) och [avknoppningsjustering](https://docs.alpaca.markets/us/changelog/optionally-adjust-bars-after-spin-offs). Ingen tyst återgång till enbart splitar vid API-fel.
- Detta normaliserar avknoppningar i prisserien; det är inte fullständig bokföring av utdelade aktier. Kontantutdelningar ingår inte och SPY jämförs också utan utdelningar. Justerade historiska priser och hela aktier ger approximativ positionsstorlek/courtage.
- BHVN börjar 2022-10-04 med ny indikatoruppvärmning. Det gamla bolaget köptes för kontanter och aktier i ett nytt bolag; det är inte samma ekonomiska instrument. Se [Biohaven 2022-10-04](https://ir.biohaven.com/news-releases/news-release-details/biohaven-sets-new-course-258-million-cash-proven-team-and-deep) och [Pfizers uppköpsvillkor](https://www.pfizer.com/news/press-release/press-release-detail/pfizer-acquire-biohaven-pharmaceuticals). Gamla Biohaven simuleras inte.
- WOLF och RNA förblir gemensamt exkluderade; nuvarande Nasdaq-katalog används för positiv identifiering av stamaktier.
- Dagsgap/kursrörelser på minst 40 % flaggas för granskning, men genuina prisras tas aldrig automatiskt bort. Datagranskningen inkluderar de tidigare största negativa bidragarna BHVN, MDU, PFG, EXPE och FRHC med både split- och avknoppningsjusterade serier, endast i den krypterade rapporten.
- Rå kurser och individuella affärer krypteras med befintlig dashboard-lösenfras. Publikt visas aggregerad kontostatistik, kontokurvor, datum för nedgångar och högsta innehavsantal.

Överlevnadsbias, ofullständig instrument-/bolagshändelsehistorik, punkt-i-tid sektorinformation, likviddagar, ränta, skatt och valuta återstår. Dessa problem löses inte av ett innehavstak. Ingen strategi väljs eller aktiveras automatiskt.

## Körning

GitHub Actions: **Capped portfolio research (5, 6, 10 holdings)**. Första körningen startar vid push av det nya manifestet till main. Senare körningar startas manuellt via Run workflow. Lokalt:

```bash
python -m breakout_lab.concentrated --capital 100000
```

Rapportartefakten `capped-portfolio-report` innehåller `report.md`, `summary.json` och `personal-report.encrypted.json`. Ingen orderintegration används och dashboardens konfiguration ändras inte.

Resultat ska granskas även efter kostnadsstress 30 bps per sida och separata årskonton. Tidigare 48,92 % och denna körning ändrar både datajustering och portföljregler; skillnaden kan inte tillskrivas bara taket. Den gamla 36-variantserien bevaras för spårbarhet.
