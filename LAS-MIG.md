> **Layout v2:** sidan följer de nya referensbilderna och formuläret ligger direkt på sidan. Se LAYOUT-V2.md. Frågor, val och serverfunktioner är bevarade.

# Noair - första fungerande pilotversionen

Byggd 24 oktober 2026. Ett separat konsumentgränssnitt för Noair med
föreslagen avsändare **Ett initiativ av Boxon**. Inte publicerad.

## Två versioner ingår

**noair-forhandsvisning.html:** en fristående interaktiv demonstration.
Öppna filen i webbläsaren. Bilder, kommentarer och exempelrapporter finns
endast i den öppna sidans arbetsminne; ingen nätverksuppladdning sker.
Inga cookies, localStorage eller externa typsnitt används i demon. Den enda
externa länken går till Boxon och öppnas bara när besökaren klickar.
Tre exempelbutiker är tydligt märkta som fiktiva. Demons rapportvy har ingen
inloggning och får inte användas för verklig insamling.

**Serverversionen:** FastAPI, SQLite och privata bildfiler, med administratörsinloggning.
Riktiga rapporter kan sparas när servern körs och insamling uttryckligen aktiverats.
Koden saknar koppling till SuperOffice, e-postleverantör och analysplattform.

## Funktioner

Besökaren skickar 1-3 JPG-, PNG- eller WebP-bilder, butiksnamn och minst en
upplevelsekategori. Kommentar, webbplats och produktkategori är frivilliga.
E-post är separat frivillig och kräver godkännande för kontakt om rapporten.
Det behövs inget konto. Ett kvitto innehåller rapportnummer och en privat
raderingskod som kan användas utan konto. Koden skickas inte via e-post;
besökaren måste spara kvittot.

Administratören kan söka, filtrera, granska bilder och kommentarer, skriva
interna anteckningar, ändra status, radera rapporter och exportera en CSV-översikt.
Exporten innehåller inte bilder, fritextkommentarer eller kontaktuppgifter.
Företagsräknaren grupperar på webbplatsdomän eller, om den saknas, normaliserat
namn. Det är inte en företagsregistermatchning och kan behöva manuell korrigering.

Kontaktutkast låses upp efter manuell granskning och sparad status.
Det är en text att kopiera, inte en e-postintegration. Inga bilder delas med
butiken och inga mejl skickas automatiskt.

## Lokal installation för utvecklare / IT

Testat med Python 3.13. Exakta biblioteksversioner i requirements.txt kommer
från testmiljön; kontrollera versionernas tillgänglighet, säkerhetsuppdateringar
samt kompatibilitet i den valda driftmiljön före publicering.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py setup
python manage.py run
```

På Windows ersätts aktiveringen med `.venv\Scripts\activate`.
`setup` ber om ett eget administratörslösenord, minst 14 tecken, och skapar en
lokal `.env` med ett slumpmässigt säkerhetsvärde. Inga riktiga lösenord
eller hemligheter följer med paketet. Använd endast testuppgifter lokalt.

Öppna `http://127.0.0.1:8000` och `http://127.0.0.1:8000/admin`.
Användarnamn: `admin`. Lösenord: det du valde vid setup.
Servern lyssnar endast lokalt och har inget debugläge.

För nytt lösenordshash: `python manage.py password-hash`.
Uppdatera ADMIN_PASSWORD_HASH och töm sessions-tabellen vid misstänkt intrång.
En lösenordsändring ensam återkallar inte redan aktiva sessioner.

## Dataskydd och säkerhetsfunktioner

- Bildfiler ligger utanför den publika statiska katalogen. Bild-API, rapporter och
  export kräver inloggning. Bilder svarar med Cache-Control: no-store.
- Bilder avkodas som faktiska bilder, begränsas till 8 MB per bild / 25 megapixel
  och sparas på nytt som JPEG, högst 2048 px per sida. Filnamn genereras av servern.
  EXIF och annan ursprunglig metadata följer inte med. HEIC och SVG accepteras inte.
- **Text i bilder, fraktsedlar, QR-koder och ansikten maskeras inte automatiskt.**
  Användaren uppmanas att täcka över eller beskära dem. Boxon ska radera
  olämpligt underlag och få ett maskningsverktyg i en senare version vid behov.
- Lösenord verifieras med Argon2. Sessionsnycklar och raderingskoder lagras hashade.
  Sessioner roteras vid inloggning och återkallas vid utloggning, max fyra timmar.
  Cookies är HttpOnly och SameSite=Lax, samt Secure i produktion.
- CSRF-kontroll och kontroll av Origin på skrivoperationer; inga CORS-undantag.
  Inbyggd begränsning av faktiska requeststorlekar även utan Content-Length.
- Inloggning, rapporter och raderingsförsök har grundläggande frekvensbegränsning.
  IP-adresser sparas inte i klartext av applikationen, men driftleverantörens
  loggar måste hanteras separat. Frekvensidentifierare är pseudonymiserade,
  inte anonyma. Ingen CAPTCHA eller avancerad botdetektion är ansluten.
- Gränssnittet kodar användartext innan HTML-rendering; SQL använder parametrar.
  CSV-utmatning skyddas mot formelstartande fält.
- Enkel revisionslogg sparar händelsetyp, tid och rapport-ID, inte bildinnehåll,
  kommentarer, e-post eller raderingskod. Loggen har samma gallringshorisont.
- Automatisk gallring körs vid serverstart och varje timme. Föreslagen gräns
  är 180 dagar, inte ett lagkrav. Utgångna rapporter spärras omedelbart i läs-API.
  Misslyckad filradering köas för nytt försök; filer blir direkt otillgängliga
  via tjänsten. Driftteamet måste övervaka gallringsfel och säkerhetskopior.

```sh
python manage.py purge
```

## Innan offentlig lansering - obligatorisk genomgång

1. Förankra namnet Noair, kommunikationen och Boxons roll internt.
2. Fastställ personuppgiftsansvarigt juridiskt bolag, kontaktväg och dokumenterad
   rättslig grund för varje ändamål. Formulärets obligatoriska ruta är en
   läs-/kontrollbekräftelse, inte automatiskt ett giltigt GDPR-samtycke.
   Om samtycke väljs som rättslig grund ska formuläret anpassas och granskas.
3. Färdigställ integritetsinformation, databehandlingsregister, lagringstid,
   biträdesavtal, geografisk lagring, eventuella tredjelandsöverföringar,
   backupgallring och process för de registrerades rättigheter.
4. Fastställ regler för felaktiga uppgifter, känsliga bilder, barns uppgifter,
   interna åtkomster, företagskontakter och eventuell vidareanvändning i CRM.
5. Granska serverkod, uppdatera och sårbarhetsskanna beroenden, testa tillgänglighet,
   kör verkliga Safari/iPhone- och Androidtester samt penetrationstest vid behov.
6. Ordna SSO/MFA eller skyddande autentiseringsproxy och individuella konton innan
   flera medarbetare får tillgång. Denna pilot har ett administratörskonto.
7. Sätt HTTPS, domän/DNS, driftövervakning, bot-/trafikskydd, krypterad beständig
   disk och säkerhetskopior med återläsningstest. Applikationen krypterar inte
   själv SQLite eller bilder på disk. Testa radering även efter backupåterläsning.
8. Fyll i konfigurationen nedan och öppna sedan insamlingen.

Koden är en testad pilot, **inte en oberoende säkerhetsrevision eller ett
GDPR-godkännande**. Publik insamling är avstängd i .env.example.

## Produktionskonfiguration

Använd `.env.example` som referens, men lägg hemligheter i driftplattformens
hemlighetshantering. Sätt `APP_ENV=production` och `PUBLIC_ORIGIN=https://noair.se`.
Ingen domänändring eller driftkostnad har beställts.

`SUBMISSIONS_ENABLED=1` kräver i produktion `PRIVACY_REVIEWED=1`, en fastställd
`PRIVACY_VERSION` utan ordet `draft`, samt ifyllda värden för:

- CONTROLLER_NAME, CONTROLLER_EMAIL
- LEGAL_BASIS_DESCRIPTION, PROCESSORS_DESCRIPTION
- BACKUP_POLICY, SECURITY_LOGS_DESCRIPTION

De sista textfälten visas i integritetsinformationen. Använd sakliga,
fullständiga formuleringar som stämmer med faktisk drift; systemet kan inte
juridiskt verifiera dem. Inkludera även information om revisionsloggar och
frekvensidentifierare, återkallelse/invändningar, supportväg samt backuphantering.

## Driftmodell

En Dockerfile och en compose-fil ingår. Dockerbilden har inte byggts i denna
miljö, eftersom externa paket inte kunde hämtas här.
Exakta krav på plan, region och disk beror på vald driftleverantör och ska verifieras.

- En serverinstans, en ASGI-worker och beständig lokal disk på DATA_DIR.
- SQLite-databasen och bilderna ska säkerhetskopieras som en konsistent enhet.
  Kopiera inte bara SQLite-huvudfilen under aktiv drift i WAL-läge; använd
  SQLite backup API eller stoppa skrivningar och ta en kontrollerad snapshot.
- Kör inte flera instanser med separata diskar eller delad SQLite över nätverksdisk.
  Gå över till PostgreSQL och privat objektlagring om tjänsten växer.
- HTTPS avslutas i en kontrollerad reverse proxy. Tillåt endast faktiska proxy-IP
  i FORWARDED_ALLOW_IPS och se till att spoofade forwarded-headers tas bort.
  Annars kan frekvensbegränsning bli fel eller missbrukas.
- Proxygräns: högst 25 MiB för uppladdning, rimliga timeouts och trafikbegränsning.
  Belastnings- och lagringstester ska göras med verklig driftkonfiguration.
- PUBLIC_ORIGIN ska vara den kanoniska domänen; dirigera www till samma domän
  vid proxyn. Produktionsvärd ska vara korrekt också i Host-headern.
- Hälsokontroll: `/healthz`. Övervaka tillgänglighet, disk, gallringsfel och 5xx-fel.

```sh
docker compose up --build -d
```

Compose exponerar bara localhost. En publik tjänst kräver separat HTTPS-ingress.
Render kan vara ett alternativ för publicering men inget Render-konto är
anslutet och ingen tjänst är skapad.

## Tester och granskning

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python build_preview.py
python test_browser.py
```

36 automatiska API-/servertester har passerat i leveransmiljön. De täcker
inlämning, inloggning, åtkomstskydd, CSRF, Origin, bildvalidering,
metadataborttagning, e-postval, CSV, radering, frekvensbegränsning,
gallring och produktionsspärrar.

Demon har körts i Chromium med dator- och mobilbredder: bildval, validering,
inlämning i minnet, rapportvy, granskningsspärr och kontaktutkast.
Skärmbilderna är från den faktiskt renderade sidan.

Webbläsarmiljön blockerade navigation till lokala filer och localhost.
Demon verifierades därför genom att samma fristående HTML lästes in direkt
i webbläsaren. API-testerna kördes separat mot den riktiga serverkoden.
Ett fullständigt webbläsartest mot en driftsatt server, Safari/iPhone,
Android, DNS, TLS, Docker och verkliga driftleverantörer återstår.

För att köra enbart den verifierade demotestdelen:
`NOAIR_OFFLINE_QA=1 python test_browser.py`.
Skriptets Chromium-sökväg kan behöva ändras till din lokala installation.

## Fortsatt produktutveckling

Prioritera maskning/beskärning före uppladdning, individuella konton med SSO,
bättre spamhantering och kontrollerad företagsmatchning. Därefter kan en
begränsad SuperOffice-integration skapa en granskningsuppgift eller ett lead
med källa Noair. Skicka inte med originalbilder eller privatpersonens kontaktuppgifter
utan en separat, uttryckligt beslutad process och rättslig bedömning.

Mät rapporter, granskade möjligheter, kontaktade företag, möten och affärer.
Beräkna inte exakta luftandelar eller klimatbesparingar från en bild i denna version.
Varken AI-analys, klimatberäkning eller representativ företagsranking ingår.

## Referensunderlag

- IMY, Grundläggande principer: https://www.imy.se/verksamhet/dataskydd/det-har-galler-enligt-gdpr/grundlaggande-principer/
- FastAPI, Request Files: https://fastapi.tiangolo.com/tutorial/request-files/
- Flask, Security Considerations (principer om CSRF, headers och resursgränser): https://flask.palletsprojects.com/en/stable/web-security/

Länkarna har använts som referens, inte som en garanti för att den här
implementationen uppfyller alla juridiska eller säkerhetsmässiga krav.
