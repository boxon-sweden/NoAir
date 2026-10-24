# Noair - startpaket för Codex + GitHub

**Testprojekt. Ingen livesajt, domän eller AWS-miljö är ansluten.**

Detta är Noair layout v2 med samma formulär och serverkod som tidigare,
plus startinstruktioner för promptbaserad redigering. Målet är att du ska
kunna beskriva en ändring, granska resultatet och spara den i projektet utan
att skicka nya filer till IT. Den första uppladdningen är en engångsåtgärd.

## 1. Skapa ett privat GitHub-projekt

Använd GitHub Free. Skapa ett repository (kodprojekt) med namnet `noair` och
välj **Private**. En Boxon-kontrollerad ägare är lämplig för ett arbetsprojekt;
följ er interna policy. Lägg inte in kunduppgifter eller servernycklar.
Du behöver inte aktivera Copilot, GitHub Pages, Actions eller betald drift för
detta första test. Codex-åtkomst och användningsgränser är separata från GitHub.

## 2. Ladda upp koden en gång

Packa upp ZIP-filen. Ladda upp **innehållet** i mappen `noair-codex-start`
med GitHubs `Add file > Upload files` (eller länken för befintliga filer i ett
tomt projekt). Ladda INTE upp själva ZIP-filen. Bekräfta med `Commit changes`.

`README.md`, `AGENTS.md`, `app.py`, `preview.py` och mappen `static` ska ligga
direkt i projektets rot, inte inuti ytterligare en `noair-codex-start`-mapp.
Ta med `.gitignore`, `.dockerignore` och `.env.example`. På Mac kan dolda filer
visas med Cmd+Shift+punkt. Ladda aldrig upp en riktig `.env` eller någon databas.
Paketet innehåller endast koden, fiktiva exempel och instruktioner.

## 3. Koppla Codex till projektet

Logga in i Codex med ditt ChatGPT-konto och välj molnmiljö / GitHub-projekt.
Skapa en miljö för `noair` och godkänn GitHub-anslutningen. Begränsa åtkomsten
till detta projekt när det är möjligt. I arbetsytor kan en administratör
behöva godkänna användningen. Ge inte åtkomst till andra Boxon-projekt.

Codex kan förbereda miljön. Vid manuell konfiguration: välj Python 3.13 och
använd installationskommandot i `AGENTS.md`. Installera Chromium bara när det
behövs för webbläsartester. Det behövs inga produktionshemligheter för testet.

**En eventuell knapp `Publish` i Codex-miljöns uppsättning publicerar
arbetsmiljön för användning i Codex, inte webbplatsen på noair.se.**

## 4. Gör första teständringen

Kopiera innehållet i `FORSTA-PROMPTEN.txt` till Codex. Det ber om en liten
rubrikändring och att formuläret ska lämnas oförändrat.
Granska det faktiska resultatet och testutfallet. Granska ett pull request
(ändringsförslag) innan du väljer att slå ihop det med huvudversionen.
En sparad kodändring på GitHub är INTE en uppdatering av en livesajt.

Tillgången till interaktiv förhandsvisning beror på Codex-gränssnittet och
miljöns verktyg. En skärmbild kan användas för granskning när en delad
interaktiv länk saknas. Paketet lovar inte en automatiskt skapad publik testadress.

## Vad som finns och vad som inte finns

- Finns: Noairs befintliga källkod, formulär, bild och design v2; en lokal demo;
  backend- och webbläsartester; instruktioner för Codex.
- Inte gjort: GitHub-uppladdning, Codex-anslutning, körning i ditt Codex-konto,
  driftgranskning, publik testserver, AWS-koppling eller DNS-ändring.
- Ingen automatisk GitHub Actions- eller publiceringsprocess är tillagd.

## Kör en lokal demo utan att konfigurera servern

```sh
python preview.py
```

Öppna `http://127.0.0.1:8000/`. Endast demosidan exponeras, aldrig
projektfilerna. Rapporter stannar i webbläsarens minne. Ingen databas eller
inloggning behövs. Starta om processen efter ändringar i källfilerna.
Även `noair-forhandsvisning.html` kan öppnas direkt som en fristående fil.

## Server och tester

Backend: Python/FastAPI + SQLite + privata bildfiler. `asgi.py` är startpunkt.
Se `LAS-MIG.md` för lokal serverinstallation och genomgång före riktig drift.

```sh
python -m pip install -r requirements-dev.txt
python build_preview.py
python -m pytest tests -q
# Separata browser-tester, kräver Chromium:
python -m playwright install --with-deps chromium
python test_browser.py
```

Installationen kräver tillgång till paketkällor. Originalets versionslåsningar
är bevarade; installerbarhet i ditt Codex-konto och aktuell säkerhetsstatus
måste kontrolleras där. Gör inga tysta uppgraderingar av produktionen.

## Senare: publicering utan att skicka filer

Nästa separat beslut är drift och kopplingen från godkänd kod till en
webbserver. Ett framtida publiceringsflöde kan byggas kring samma projekt.
Det finns INTE i detta startpaket. Behåll privata rapporter och bilder utanför
kodprojektet och låt aldrig en layoutuppdatering ersätta insamlade data.

## Dokumentation att kontrollera vid uppsättningen

Kontrollerad 2026-10-24. Gränssnitt och abonnemang kan ändras.

- GitHub Free: https://docs.github.com/en/get-started/learning-about-github/githubs-plans
- Skapa projekt: https://docs.github.com/en/repositories/creating-and-managing-repositories/quickstart-for-repositories
- Filuppladdning: https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- Codex och abonnemang: https://help.openai.com/en/articles/11369540
- Codex Cloud: https://developers.openai.com/codex/cloud
- Projektinstruktioner: https://developers.openai.com/codex/guides/agents-md

## Kontaktutkast och utskickskö

Boxons rapportvy har ett tillägg med redigerbara kontaktutkast, alternativa
formuleringar, offentliga kontaktförslag och en kö för granskade meddelanden.
GitHub Pages visar en simulering. eMarketeer-anslutningen görs senare och
verkliga utskick är avstängda. Se [KONTAKTFLODE.md](KONTAKTFLODE.md) för
serverinställningar, begränsningar och testkommandon.
