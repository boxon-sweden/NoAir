# Lokalt testresultat - Noair Codex-start

Kontrollerat 2026-10-24 i denna arbetsmiljö, inte i användarens Codex eller GitHub.

- 36 backendtester passerade (`python -m pytest tests -q`).
- 45 offlinekontroller i Chromium passerade, inklusive formulärflöde och mobilbredder
  (`NOAIR_OFFLINE_QA=1 python test_browser.py`).
- Den nya lokala demoservern startade och levererade demosidan; försök att läsa
  `.env`, `app.py`, `.git/config`, `static/index.html` och `../README.md` gav 404.
- Källfiler för sidan, designen, formuläret och servern jämfördes byte för byte
  med ursprungliga layout v2 och är oförändrade.

## Begränsningar

Det kompletta webbläsartestet mot den lokala backendservern kunde inte slutföras:
Chromium i denna miljö blockerade navigering till localhost med
`ERR_BLOCKED_BY_ADMINISTRATOR`. Backendtester utan webbläsare passerade enligt ovan.
Ingen säkerhetsinställning kringgicks; offline-delen kördes separat.

Inga inloggningar, uppladdningar eller testkörningar har gjorts i användarens GitHub
eller Codex. Ingen ren installation från externa paketkällor gjordes här;
redan installerade versioner användes. Detta är inte en produktions- eller
säkerhetscertifiering.

## Förändringar i startpaketet

- Tillagt README.md, AGENTS.md, FORSTA-PROMPTEN.txt och preview.py.
- Uppdaterat START-HAR.txt och .gitignore.
- Rättat en felaktig startkommentar i asgi.py (ingen körbeteendeändring).
- Gjort webbläsartestets Chromium-sökväg portabel.
- Ersatt gamla testresultat med denna redovisning och offline-testets JSON.

Skärmbilderna i screenshots/ är referensbilder från ursprungliga v2-paketet.
