# Noair v2 - layout efter referensbilderna

## Ny visuell utformning

Varmvit bakgrund, mörkgröna ytor, limegröna accenter, stora rubriker,
ljusa stegkort, formulär direkt på sidan, om-sektion, frågor och mörk sidfot.
Illustrationen i hero-sektionen är ett utsnitt ur den tillhandahållna
referensbilden. Den är inbäddad i den fristående HTML-filen.
Inga externa typsnitt eller bildtjänster laddas.

## Bevarat från originalet

Alla formulärkontroller, frågor och svarsalternativ är bevarade:
bilder, butiksnamn, valfri webbplats, flera problemval, valfri kommentar,
valfri produktkategori, integritetsbekräftelse och frivillig e-post
med separat tillåtelse att kontakta personen om rapporten.
Obligatoriska och valfria uppgifter har inte bytt status.
Bildkraven är 1-3 JPG/PNG/WebP, max 8 MB per bild, precis som i v1.

Frågorna visas samtidigt i ett sammanhängande formulär i stället
för att delas upp i tre steg i en dialog. Felen visas vid rätt fält.
Kvitto, raderingskod, rapportvy, filtrering, manuell granskning,
statusuppdatering och kontaktutkast är kvar. Serverkoden app.py
är oförändrad byte för byte jämfört med v1.

## Filer att börja med

- `noair-forhandsvisning.html`: komplett fristående demo.
- `static/index.html`: sidstruktur för serverversionen.
- `static/layout-v2.css`: ny layout och responsiva brytpunkter.
- `static/style.css`: befintliga grundstilar, dialoger och administration.
- `static/app.js`: formulärflöde och administration.
- `static/parcel-hero.webp`: illustration från referensbilden.
- `screenshots/`: faktiska webbläsarskärmbilder från v2.

Efter ändringar skapas en ny fristående demo med:

```bash
python build_preview.py
```

## Kontroll den 24 oktober 2026

36 API-/servertester passerar. 45 webbläsarkontroller passerar i
Chromium mot den fristående demon. Bland annat testas bildval,
bildgränser, validering, e-postgodkännande, inskickning, kvitto,
radering och rapportöversikten. Ingen horisontell överströmning
upptäcktes vid bredderna 320, 375, 390, 768, 820, 1024, 1440 och 1920 pixlar.
Formulärets fält, attribut och svarsalternativ har också jämförts
maskinellt med v1.

Den tillgängliga webbläsarmiljön blockerar navigation till lokala
filer och localhost. Därför laddades demon direkt i webbläsarens
minne; API-testerna kördes separat mot den riktiga serverkoden.
Ett komplett webbläsartest mot servern samt tester på verkliga
Safari/iPhone- och Androidenheter återstår. Detta är inte en
säkerhetsrevision, tillgänglighetscertifiering eller publik lansering.

```bash
python -m pytest -q tests
NOAIR_OFFLINE_QA=1 python test_browser.py
# I en miljö som tillåter localhost:
python test_browser.py
```

Befintliga krav inför publik drift i LAS-MIG.md gäller fortfarande.
Ingen domän, driftmiljö, e-posttjänst eller CRM-koppling har anslutits.
