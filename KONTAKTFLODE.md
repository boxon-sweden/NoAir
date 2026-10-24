# Boxons kontaktflöde

Tillägg till befintlig rapportvy. Rapporter, bildskydd, granskning, status,
CSV-export och radering finns kvar. Inga riktiga mejl skickas i denna leverans.
Anslutningen till eMarketeer är uttryckligen uppskjuten. Planerad avsändare:
Marcus.gustafsson@boxon.com.

## Använd flödet

1. Varje ny rapport får automatiskt ett privat kontaktutkast. Äldre rapporter
   får ett utkast vid serverstart; befintliga utkast skrivs inte över.
2. Granska bilder och beskrivning i rapportvyn och spara granskningsrutan.
   Öppna sedan **Meddelande & kontakt**, eller öppna utkastet i den nya kön.
3. Välj en offentlig kontakt eller fyll i egna verifierade uppgifter. Ändra namn,
   roll, adress, källänk, ämne och meddelande fritt. Tre alternativa formuleringar
   finns. Att välja en formulering ersätter ämne/text, men behåller kontakten.
4. Kontrollera mottagare och innehåll och välj **Lägg i utskickskön**.
   Från kön kan ett färdigt meddelande skickas utan ytterligare redigering när
   en mejltjänst har anslutits. Att spara som utkast tar bort det från klarkön.
5. I demon heter åtgärden **Simulera utskick**. Inget mejl eller nätverksanrop
   till ett företag görs. Allt ligger i webbläsarminnet och försvinner vid omladdning.

Utkasten är lokala säljpitchar med tre variationer: kundinsikt och konkret lösning,
kundupplevelsen i fokus samt en kort mötespitch. De använder företagsnamn,
upplevelsekategorier och identifierbara produktord i beskrivningen, till exempel
hörlurar, headset, laddare, mobilskal eller skor. Saknas en sådan uppgift används
produktkategorin eller en allmän leveransbeskrivning. Texten tillskriver upplevelsen
en kundrapport och utgår inte från att företaget handlar av en viss konkurrent.
Förslaget anpassas efter tomrum, fyllnadsmaterial eller skyddsbehov. Målet är ett
första möte på 15 minuter om en kundunik förpackningslösning från Boxon.
Kostnaden formuleras som något att jämföra, inte en garanterad besparing.

Kundens fria kommentar kopieras inte in. Bilder analyseras inte maskinellt:
medarbetaren ser dem i rapportvyn och kan lägga in en saklig sammanfattning i
mejltexten. Produktmatchningen är en begränsad ordlista, inte AI eller fullständig
språkförståelse. Kundens e-post och originalbilder bifogas aldrig automatiskt.

Befintliga sparade utkast skrivs inte över vid en uppdatering av mallarna. Öppna
utkastet och välj en ny formulering för att använda säljpitchen även där. Det
ursprungliga **Visa kontaktutkast** använder också den nya säljpitchen.

## Offentliga kontakter på servern

Sätt `CONTACT_LOOKUP_ENABLED=1` och starta om servern för automatisk sökning när
en rapport med företagswebbplats kommer in. Knappen i redigeraren kan göra en ny
sökning; för äldre rapporter används knappen. Funktionen är avstängd som standard.

Sökningen läser startsidan och upp till tre ytterligare HTTPS-sidor för kontakt,
team eller inköp på samma domän. Den hämtar publicerade e-postadresser, visar
källänk/datum/källtext och prioriterar träffar där källtexten nämner emballage,
förpackning eller inköp. Den uppfinner inte personnamn, titlar eller mejladresser.
En prioriterad träff bevisar inte att personen fattar inköpsbeslut. Verifiera
kontakten mot källan; ibland finns bara en allmän adress eller ingen träff.

Webbplatser som kräver JavaScript/inloggning, blockerar automatiska anrop eller
inte publicerar kontaktuppgifter kan ge tomt resultat. Egna verifierade
kontakter kan alltid matas in. Ingen extern sök-/kontaktleverantör är ansluten.

Servern behöver DNS och utgående HTTPS till företagens publika webbplatser.
Hämtaren använder direkt TLS, med verifierat servercertifikat och en låst,
kontrollerad publik IP-adress per anslutning; privata IP-adresser, osäkra
protokoll, andra portar och omdirigeringar till andra domäner följs inte.
Den använder inte maskinens HTTP_PROXY, skickar inga rapporter till webbplatsen
och loggar inte kundinnehåll. Miljöer som endast har proxybaserad utgående
trafik behöver en anpassad, lika skyddad transport innan kontaktsökningen fungerar.
Kontaktsökningen är testad med syntetiska webbplatssvar; åtkomst till riktiga
företagswebbplatser i er driftmiljö är ännu inte verifierad.

## eMarketeer: senare anslutning

API-dokumentation, kontoanslutning och riktiga utskick ingår inte i detta steg.
Det finns ingen påhittad eMarketeer-URL eller API-nyckel i koden.
Att sätta `OUTREACH_MAIL_ENABLED=1` räcker inte för att aktivera utskick.
En riktig serveradapter behöver först byggas mot eMarketeers bekräftade API
med autentisering och verifierad avsändare. Därefter registreras adaptern som
`config['delivery_adapter']` före `create_app(config)`. Hemligheter ska hanteras
av driftplattformen och får inte finnas i statiska filer, Git eller chatten.

Adaptern i `outreach.send_message` får endast avsändare, mottagaradress, ämne,
text och en stabil idempotensnyckel. Den ska ha en begränsad timeout, återvända
först när mejltjänsten bekräftat mottagandet och respektera idempotensnyckeln.
`DeliveryRejected` betyder att tjänsten uttryckligen inte accepterade mejlet.
`DeliveryUncertain` och alla oväntade fel ger okänd status, inte automatisk retry.
En lyckad överlämning betyder inte bekräftad leverans till mottagarens inkorg.

Kön använder versionskontroll och en atomisk övergång från klar till pågående
för att motverka dubbla klick och samtidiga utskick. Okänd status spärrar nya
utskick tills en operatör har kontrollerat mejltjänstens logg och angett utfallet.
Om processen avbryts kan statusen vara pågående. Vänta minst fem minuter före
manuell avstämning; eMarketeer-adaptern måste ha en timeout kortare än detta.
Det finns inga schemalagda eller automatiska mejlutskick.

## Lagring och verifiering

SQLite får en separat tabell kopplad till rapporten. Ämne, text, kontaktuppgifter,
källor, granskning och köstatus sparas privat. Rapportens befintliga radering och
gallring raderar även tillhörande utkast och kontakter. Kön och skrivoperationerna
kräver adminsession; skrivningar kräver även CSRF/Origin-kontroll. Publik
rapportering, dess frågor och obligatoriska fält har inte ändrats.

Verifiera från projektroten med Python 3.13:

```sh
.venv/bin/python build_preview.py
.venv/bin/python -m pytest tests -q
.venv/bin/python test_browser.py
.venv/bin/python test_outreach_browser.py
```

Webbläsartesterna använder Chromium och en tillfällig lokal backend med
syntetiska data. Utskickstesterna använder en testadapter som bara sparar
argument i minnet. Inga verkliga mejl skickas. `test_browser.py` skriver sin
resultatfil; återställ enbart den genererade resultatfilen efter körningen om
resultatfilen inte ska ingå i en kodändring.
