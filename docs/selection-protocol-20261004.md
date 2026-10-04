# Börsvärde och månadsvis momentum – fastställt protokoll

Fastställt 2026-10-04 före resultat från denna serie. Sex kombinationer:

| Strategi | Börsvärdesgräns | Tak |
| --- | --- | --- |
| Ursprunglig breakout | Ingen | 10 innehav |
| Ursprunglig breakout | >1 miljard USD | 10 innehav |
| Ursprunglig breakout | >5 miljarder USD | 10 innehav |
| Månadsvis momentum | Ingen | 10 innehav |
| Månadsvis momentum | >1 miljard USD | 10 innehav |
| Månadsvis momentum | >5 miljarder USD | 10 innehav |

Nuvarande Alpaca-pipeline saknar historiska börsvärden. De fyra varianterna med filter markeras **blockerade**, utan resultat. Två ofiltrerade tester körs. Inga aktuella börsvärden eller dagens stora bolag används som historiskt urval. Ingen datatjänst köps eller nya nycklar krävs för den ofiltrerade körningen.

## Regler

Samma femårsperiod som föregående koncentrerade studie, 100 000 USD startkapital, samma aktuella universum av stamaktier, WOLF/RNA-exkludering, BHVN-identitetsstart 2022-10-04 och Alpaca SIP `adjustment=split,spin-off`. Överlevnadsbias och ofullständig bolagshändelsebokföring kvarstår. Genuina kursras filtreras inte bort.

Breakout använder befintliga signaler, stop under basen, 2R och max 20 candles. Riskbudget 0,5 % vid köp, max 15 % position vid köp, max tio innehav. Inget nytt marknadsfilter.

Momentum väljer vid varje avslutad börsmånad de tio högsta positiva poängen: medelvärdet av sex- och tolvmånaders avkastning med senaste månaden utelämnad. Vid månad m används stängningspriser från m−1, m−7 och m−13. Alla tre måste finnas på samma månadsslutsdatum som SPY; ingen ersättning med kortare historik. Minst 250 egna bars, pris ≥5 USD, föregående 20 bars genomsnittlig dollaromsättning ≥20 MUSD. Rangordning endast med information känd vid signalstängningen; alfabetisk brytning av lika poäng.

Nästa sessions öppning: sälj innehav som lämnat topp tio, köp nytillkomna för högst 10 % av öppningens eget kapital per innehav. Behåll kvarvarande innehav utan omviktning; deras vikt kan växa. Inga dagliga stoppar, vinstmål eller tidsgränser. Färre än tio positiva kandidater lämnar kontanter. Saknad öppningsbar låser ett innehav och upptar en av de tio platserna. Köp som saknar öppningsbar hoppas över utan ersättning baserad på framtida data.

Båda använder heltalsaktier, gemensam kassa utan belåning, 10 bps per sida och 0,005 USD/aktie/sida; stress 30 bps per sida. Innehavstak och kassa kontrolleras intradag och dagligen i samtliga delperioder. Momentum-P/L stäms även av mot kontovärdet. Avkastningen kan inte tillskrivas enbart ranking eftersom exitregler, riskbudget och exponering också skiljer sig.

## Utvärdering

Fem år kontinuerligt, fem reset-år, träningsperioder 2/3/4 år och senaste två år samt kostnadsstress. Alla reset-konton börjar i kassa; deras första signal måste uppstå inom fönstret. Ingen automatisk ändring av live-/dashboardregler och inga order. Tidigare granskning av samma historik innebär att detta inte är orörd validering.

Tidigare bedömningskrav bevaras som diagnostik: positivt totalt resultat; DD ≤20 %; ≥100 avslutade affärer; PF ≥1,15; ≥4 positiva reset-år; positivt vid stress; fem största vinnare ≤halva bruttovinsten. Kravet 100 affärer är inte särskilt anpassat till långsamt momentum; resultaten redovisas även när det inte uppfylls. Ingen parameter ändras efter resultatgranskning i denna serie.

## Historiska börsvärden

Lokal körning: `python -m breakout_lab.selection_study --market-caps data/historical-market-caps.json` med befintliga Alpaca- och dashboardmiljövariabler. Filen ska hållas utanför publikt git och har följande JSON-form:

```json
{
  "schema": 1,
  "currency": "USD",
  "point_in_time": true,
  "source": "Namngiven datakälla och dokumenterad historisk vintage-policy",
  "records": [
    {
      "symbol": "EXAMPLE",
      "date": "2024-01-31",
      "available_on": "2024-01-31",
      "market_cap_usd": 2000000000
    }
  ]
}
```

Dataleverantörens vintage-policy och aktieklass-/identitetsmappning måste granskas separat; fältet `point_in_time` är en deklaration, inte ett självständigt bevis. Värdet avser börsvärdet på `date`, inte en nyare uppskattning bakåtskriven. `available_on` anger när värdet var tillgängligt. Det måste vara ≤signaldatum. Exakt observationsdatum krävs; ingen framåtfyllning. Aktuellt aktieantal × historisk justerad kurs accepteras inte som korrekt historiskt börsvärde.

Storleksfiltret tillämpas före ranking. Saknat eller ännu inte tillgängligt värde för någon pris-/likviditetskvalificerad positiv momentumkandidat eller breakoutsignal blockerar hela filtervarianten. Täckning, datakällans namn och filens SHA256 redovisas. Numeriska observationer och månadsurval sparas bara krypterat. JSON-data måste först valideras; dubbletter, fel valuta och ogiltiga tal avvisas.

Forskningsgrund: [Kenneth Frenchs momentumfaktor](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html) använder tidigare 2–12-månaders avkastning i ett annat, long/short-portföljupplägg. Den motiverar hypotesen men bevisar inte lönsamhet för detta topp-tio-test.
