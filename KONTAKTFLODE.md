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

## Kontaktpersoner och flerval

Kontaktförslag har kryssrutor. Välj enskilda personer eller **Välj alla hittade**.
**Avmarkera hittade** lämnar manuellt tillagda kontakter kvar. Alla valda personer
kan redigeras separat: namn, roll, e-post och källänk. Lägg till fler med
**Lägg till kontaktperson manuellt**. Högst 30 kontakter kan väljas per utkast;
samma e-postadress räknas bara en gång, även med olika stora/små bokstäver.

Personer utan offentlig e-post kan väljas och kompletteras, men hela utskicket
kan inte läggas i klarkön förrän alla valda mottagare har giltiga adresser och
medarbetaren har verifierat kontakterna. Varje mottagare får ett eget mejl när
eMarketeer anslutits; adresser delas inte via gemensam To/CC. Status och
idempotensnyckel hålls separat per adress. Ett redan bekräftat skickat mejl
skickas inte om ifall en annan mottagare behöver ett nytt försök. Okänd status
stäms av per mottagare efter kontroll i mejltjänstens logg.

## Vad som fungerar i GitHub Pages-testet

GitHub Pages kör bara statiska filer. Omladdning raderar demots arbetsminne,
men det ger inte sidan möjlighet att köra Python eller kringgå andra
webbplatsers CORS-regler. Automatisk kontakthämtning kan därför inte aktiveras
på Pages genom enbart en kodpush. Rapportvyn visar detta uttryckligen vid sökknappen.

Testversionen har riktiga länkar till sökningar efter företagets kontaktpersoner,
inköpsansvariga, kundcase och nyhetsartiklar. Du kan öppna källorna själv, lägga
till personer manuellt eller klistra in offentlig kontakttext och låta
webbläsaren hitta e-postadresser lokalt. Det är en import av den text du klistrar
in, inte automatisk hämtning. Namn/roller kan fyllas i manuellt. Knappen
**Visa fiktiva testkontakter** är en separat, tydligt märkt simulering.

Inga verkliga kontakter sparas i projektfiler eller skickas till söktjänsten i
demon. De ligger i sidans minne och försvinner vid omladdning. Lägg aldrig en
söktjänsts API-nyckel i Pages eller i webbläsarens JavaScript.

## Automatisk sökning på servern

Serverkoden börjar med angiven företagswebbplats. Kontaktsökningen är aktiverad
som standard (`CONTACT_LOOKUP_ENABLED=1`); sätt 0 för att stänga av den.
Nya rapporter med webbplats söker automatiskt i bakgrunden. Finns ingen webbplats
kan en ansluten söktjänst söka utifrån företagsnamnet. För äldre rapporter,
eller för att försöka igen, används sökknappen. En medarbetare kan också ange
en företagswebbplats i redigeraren när rapporten saknar den; rapportens ursprungliga
uppgifter ändras inte av detta.

Sökningen läser startsidan och upp till tre ytterligare sidor för kontakt/team/
inköp på samma domän. Vid anslutet Brave Search-API fortsätter den med öppna
webbträffar, exempelvis leverantörers kundcase och nyhetsartiklar. Sökfrågan
innehåller företagsnamn och yrkes-/ämnesord, aldrig kundens bilder, kommentar
eller kontaktuppgifter. Sökresultatens källsidor hämtas och granskas; externa
kontaktuppgifter kräver lokal källtext eller strukturerad persondata med koppling
till målföretaget. En tidnings eller leverantörs allmänna redaktions-/pressadress
ska inte väljas enbart för att företaget nämns någon annanstans på sidan.

Resultaten visar källänk, datum, källtext, eventuellt namn/roll och publicerad
adress. Personnamn från löptext är förslag som måste verifieras. Strukturerade
Person/worksFor-uppgifter läses där de finns. Personer kan hittas utan publicerad
mejladress; ingen adress gissas. Prioritet ges åt emballage, förpackning, inköp
och logistik. Yrkesroll bevisar inte att personen fattar inköpsbeslut.

Om extern sökning inte är ansluten fungerar webbplatsdelen ändå och gränssnittet
visar att nätet inte har sökts igenom. Resultatlösa sökningar, saknad anslutning,
misslyckad API-anslutning och sidor som inte kan läsas visas med status i vyn.
JavaScript-/inloggningskrävande eller blockerande sidor kan sakna resultat.

För extern sökning behövs `BRAVE_SEARCH_API_KEY` säkert i serverns inställningar.
Tjänstekonto, betalning och nyckel har inte skapats. Adaptern använder Brave
Searchs HTTPS-webbendpoint och skickar inte nyckeln vid omdirigeringar. Den har
verifierats med syntetiska API-svar; ingen autentiserad liveförfrågan har kunnat
verifieras utan nyckel. Ingen extern kontakt-/söktjänst finns i den nuvarande driften.

Servern behöver DNS och utgående HTTPS till företagens/källornas publika
webbplatser, samt `api.search.brave.com` för webbsökning. Webbplatshämtaren
använder verifierad TLS och en låst publik IP-adress per anslutning. Privata IP,
osäkra protokoll och särskilda portar tillåts inte. Externa omdirigeringar
valideras före hämtning. Antal sidor, lästid och svarsstorlek begränsas.
Hämtaren använder direkt trafik, inte HTTP_PROXY; proxybaserad serverdrift
behöver motsvarande skyddad transport. Kontaktsökning mot riktiga webbplatser
måste verifieras i den valda driftmiljön innan funktionen kallas aktiverad där.

För livefunktion återstår alltså att välja och ansluta serverdrift för den
privata FastAPI-rapportvyn och, för bred webbsökning, ansluta söktjänsten.
Detta har inte gjorts genom en GitHub Pages-push.

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
