# Metro-protokoll fastställt före körningen

Fastställt 2026-10-22, godkänt av ägaren innan Metro körts på riktig marknadsdata. Ingen Metro-statistik på riktig data har setts före detta datum; dashboardens rullande år hade ännu inte publicerats.

## Vad som testas

- **Regler:** Metro enligt [strategy-metro.md](strategy-metro.md), med förvalen i `config.json` → `metro` vid commit för detta protokoll. Breakoutens gemensamma värden (universum, likviditet, risk, kostnader, `max_holding_bars` = 20) från samma `config.json`.
- **Varianter (2):** Metro och Metro utan regimfilter.
- **Kostnadsfall (2):** `slippage_bps` = 10 (grund) och 30 (stress), courtage enligt `config.json`.
- Totalt 4 körningar. Inga andra varianter eller parametrar prövas inom detta protokoll.

## Data och period

- Alpaca, historisk SIP, splitjusterade dagscandles, alla aktiva handlingsbara amerikanska stamaktier som Alpaca listar på körningsdagen (samma urval som dashboarden), plus SPY som index.
- Hämtning: sex år bakåt från senaste avslutade session. Första året värmer upp indikatorer och nivåer.
- **Testperiod:** de fem senaste åren, `as_of − 5 × 365 dagar` till `as_of`. Signaler före testperioden räknas inte.
- **Årsblock:** fem på varandra följande block om 365 dagar från testperiodens start; en affär räknas till blocket där entry sker.

## Mått

Per variant och kostnadsfall: antal avslutade affärer, träffandel, genomsnitt R, profit factor i R, summa R, genomsnitt R per årsblock, de fem största vinsternas andel av positiv R, antal månader med minst en entry, och månadsklustrat medelvärde av R med standardfel (medel och spridning av månadsmedelvärden, delat med roten ur antalet månader). Affärer i olika aktier överlappar i tid och delar marknadsrörelse; antalet affärer är därför inte antalet oberoende observationer, och månadsmåttet redovisas bredvid.

## Kriterier, fastställda före körningen

Metro (med regimfilter, 10 bps) uppfyller protokollet först när **alla** gäller:

1. Minst 100 avslutade affärer.
2. Genomsnitt R > 0 och profit factor i R ≥ 1,15 efter kostnader.
3. Genomsnitt R > 0 i minst 4 av 5 årsblock.
4. Genomsnitt R > 0 även med 30 bps slippage.
5. De fem största vinsterna utgör högst 50 % av summan av positiva R.

**Marknadsläget** räknas som en förbättring endast om Metro med regimfilter har högre genomsnitt R än utan i minst 4 av 5 årsblock (10 bps).

Uppfylls kriterierna inte är det ett giltigt resultat. Parametrarna justeras inte för att få fram ett godkänt utfall; varje senare ändring kräver ett nytt protokoll och en ny, orörd period. Resultatet aktiverar ingenting automatiskt.

## Kända begränsningar

- Dagens universum ger överlevnadsbias: avnoterade bolag saknas, och bredden i marknadsläget räknas på samma universum.
- Separata affärer per aktie, en öppen affär per aktie åt gången; ingen gemensam kapitalbudget eller portföljdrawdown.
- Instrumenttyp uppskattas från namn där metadata saknas.
- Nyhetsreaktionen ingår inte; den styr inte signalen.
- Resultatfilen innehåller bara aggregerade mått, inga kurser eller enskilda affärer, eftersom Alpacas data inte får vidarepubliceras.
