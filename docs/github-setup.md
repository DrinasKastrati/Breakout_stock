# Aktivera Breakout Lab via GitHub

Guiden gäller `DrinasKastrati/Breakout_stock`. All drift kan skötas på GitHub-hemsidan. Koden är förberedd; sidan är inte publicerad förrän följande inställningar och första körningen är klara.

## 1. Välj gratis hosting

GitHub Free ger Pages för publika repos. Ett privat repo kräver en betald GitHub-plan för Pages. Behåll repot privat tills du uttryckligen vill publicera dess kod och hela dess versionshistorik.

Om du godkänner publik kod: öppna [repo-inställningar](https://github.com/DrinasKastrati/Breakout_stock/settings), gå till **Danger Zone → Change repository visibility → Public** och följ GitHubs kontrollsteg. Genererade riktiga marknadsdata och API-nycklar finns inte i koden eller dess historik.

Öppna sedan [Pages-inställningar](https://github.com/DrinasKastrati/Breakout_stock/settings/pages). Välj **Build and deployment → Source → GitHub Actions**. Ingen egen domän behövs.

## 2. Skapa gratis dataåtkomst

Skapa ett gratis Alpaca Basic/paperkonto på [Alpaca](https://app.alpaca.markets/). Använd paper-nycklar som ger tillgång till assets, calendar och historiska marknadsdata. Projektet skickar bara läsande GET-anrop; det finns ingen orderfunktion.

Ingen betalplan för realtids-SIP behövs. Vi använder historisk SIP och ett `end` minst 16 minuter bakåt. Basic begränsar nya historiska data med 15 minuter och tillåter 200 anrop/minut; klienten håller sig under detta. Data sedan 2016 finns enligt Alpacas dokumentation. Workflowen hämtar två års historik, tillräckligt för standardstrategins 250 candles och ett års jämförelse.

## 3. Lägg hemligheterna i GitHub

Öppna [Actions secrets](https://github.com/DrinasKastrati/Breakout_stock/settings/secrets/actions) → **New repository secret** och lägg till:

| Namn | Värde |
|---|---|
| `ALPACA_API_KEY` | Din paper-API-nyckel |
| `ALPACA_API_SECRET` | Din paper-API-hemlighet |
| `DASHBOARD_PASSPHRASE` | En egen slumpmässig lösenfras, helst minst 32 slumpmässiga tecken; minimum 20 |

Spara lösenfrasen i din lösenordshanterare. Den används för att låsa upp analysen på sidan och ska skilja sig från dina API-hemligheter. Lägg aldrig dessa värden i `config.json`, arbetsflödesfilen, commitmeddelanden eller chatten. `.env.example` är endast en namnguide och laddas inte automatiskt.

Alpaca förbjuder vidarepublicering av API-data. Därför publiceras riktiga analys-, diagram- och backtestfiler bara krypterade, avsedda för kontoinnehavarens personliga användning. Lösenfrasen används lokalt i webbläsaren och skickas inte till en server. Dela inte lösenfras eller dekrypterade data. Kryptering skyddar innehåll; den ersätter inte leverantörens användningsvillkor.

## 4. Aktivera sidan och schemat

Öppna [Actions variables](https://github.com/DrinasKastrati/Breakout_stock/settings/variables/actions) och välj **New repository variable**:

| Namn | Värde |
|---|---|
| `ENABLE_PAGES` | `true` |
| `ENABLE_AUTO_UPDATE` | `true` |

Workflowen publicerar endast när repot är publikt och `ENABLE_PAGES=true`. Automatiska körningar kräver även `ENABLE_AUTO_UPDATE=true`. Schemalagda körningar kräver riktiga datahemligheter; de ersätter aldrig marknadsanalysen med demo när en nyckel saknas.

## 5. Kör första uppdateringen

Öppna [Actions](https://github.com/DrinasKastrati/Breakout_stock/actions) → **Update dashboard → Run workflow**:

- Branch: `main`
- Source: `alpaca`
- Force: avstängd

Efter lyckad körning visas sidlänken under GitHub Pages och i deployment-steget. Öppna den och ange din lösenfras. Du ser senast analyserade handelssession, källa och signalregler.

För demo utan konto: skapa bara variabeln `ENABLE_PAGES=true` och kör med Source `demo`. Låt `ENABLE_AUTO_UPDATE` vara avstängd tills Alpaca och lösenfras är klara. Demo är tydligt markerad och innehåller enbart fiktiva aktier.

## Så fungerar den själv

- **01.37 UTC tisdag–lördag:** analys efter måndag–fredag i New York. Helgdagar hanteras via börskalendern.
- **02.37 UTC:** nytt försök och kontroll av sena datakorrigeringar. Samma analys ger ingen ny publicering.
- Historik hämtas om när ett nytt dataset behövs, så äldre splitjusteringar blir konsekventa.
- SPY och minst 90 % av upptäckta aktier måste ha aktuell session för att ett nytt dataset ska godtas. Saknade sessioner på enskilda aktier filtreras ur analysen.
- Alla upptäckta aktiva och handlingsbara stamaktiekandidater hos Alpaca hämtas, utan ett dolt 50/100-aktietak. Listan är leverantörens täckning, inte en garanti om varje amerikansk notering eller avnoterad aktie.
- Sidan söker ny publicerad analys var femte minut medan fliken är synlig och data har låsts upp.
- Ett fel lämnar tidigare publicerad sida kvar. Se sessionsdatumet och felet under Actions.
- En månatlig botcommit till `.github/heartbeat.txt` håller schemat aktivt. GitHub kan ändå fördröja eller tappa cron-körningar; de har ingen exakt tids-SLA.

## Ändra strategin

Öppna [config.json](https://github.com/DrinasKastrati/Breakout_stock/blob/main/config.json), välj pennan och sedan **Commit changes** till `main`. Detta startar nästa bygge direkt. Sidan länkar också till redigeraren.

Pris-, likviditets-, breakout-, volym- och MACD-filter fungerar utan betalda metadata. Sektor, börsvärde och rapportdatum saknas i denna gratis källa och är avstängda som standard; om du aktiverar sådana filter utan metadata utesluts aktierna. Backtestet avvisar dessa aktuella bolagsfilter eftersom historiskt korrekt metadata saknas.

`account_equity` är ett exempelvärde för riskplaner. Inställningar i det publika kodrepot är synliga. Senaste årets tre backtestvarianter räknas om vid publicering; sidan gör inga nya servertester när du klickar **Visa senaste jämförelse**. 4H har ännu inte implementerats.

## Stoppa eller felsök

Sätt `ENABLE_AUTO_UPDATE=false` för att stoppa schemat. **Actions → Update dashboard → Disable workflow** stoppar även manuella/push-körningar. GitHub Pages kan avpubliceras i Pages-inställningarna.

Om lösenfrasen ändras: uppdatera hemligheten, kör workflowen med Source `alpaca` och Force på, och lås upp med den nya frasen. Tidigare publicerade krypterade kopior kan finnas kvar i cache eller besökarens nedladdningar; rotation ger inte tillbaka redan delade data.

Vid HTTP 401/403: kontrollera paper-nycklar och Basic-åtkomst; ett konto som återställts kan behöva nya nycklar. Vid 429 försöker klienten igen under rate limit; misslyckad körning behåller tidigare sida. Vid utebliven Pages-publicering: kontrollera publik repo-synlighet, Pages-källan och variablerna.

## Kostnader och verifiering

Utformningen använder Alpaca Basic, GitHub Pages för publikt repo och standard Ubuntu-runners. Den innehåller inga betal-API:er, större betalrunners eller automatisk uppgradering. Actions-artefakter behålls en dag; snapshotfiler hålls under 180 MB och inga riktiga rådata checkas in. Lämna GitHubs betalda överanvändning avstängd om du använder andra arbetsflöden på kontot.

Verklig datainhämtning och Pages-publicering kan verifieras först när ditt konto, hemligheter och Pages är aktiverade. Tester med syntetiska data verifierar signaler, exporter och att Python-krypteringen kan dekrypteras med webbläsarens WebCrypto.

Källor: [GitHub Pages tillgänglighet](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Actions kostnader](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [schemaläggning](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Alpaca Basic](https://docs.alpaca.markets/us/docs/about-market-data-api), [gratis historisk SIP](https://docs.alpaca.markets/us/docs/market-data-faq), [Alpacas vidarepubliceringsregel](https://alpaca.markets/support/redistribute-alpaca-api).
