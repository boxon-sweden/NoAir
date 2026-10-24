# Noair: project instructions for Codex

## Context and scope
Noair is a Swedish consumer-facing packaging-feedback pilot for Boxon.
The user is a non-developer who wants to request small changes in Swedish.
Explain results in Swedish. Keep changes focused; do not rebuild the app in
another framework or introduce a CMS unless explicitly requested.
This repository is a test setup, not a live website or an approved production system.

## Source of truth
- `static/index.html`: public site, inline report form and admin markup.
- `static/layout-v2.css`: the requested v2 visual layout, loaded after `style.css`.
- `static/style.css`: shared/base and admin styles.
- `static/app.js`: client behaviour, validation and demo-mode reports.
- `static/parcel-hero.webp`: existing hero image.
- `app.py`: FastAPI server, SQLite database, private uploads and admin API.
- `asgi.py`: server entrypoint; `manage.py`: local server configuration.
- `noair-forhandsvisning.html`: GENERATED standalone demo, not the editing source.
- `build_preview.py`: rebuilds the demo from `static/` files.
- `preview.py`: dependency-free localhost DEMO server, not the backend.
- `LAS-MIG.md`: original detailed technical and deployment notes.

## Preserve unless explicitly requested
Keep the v2 warm-white/dark-green/lime design and responsive layout.
Do not change form questions, options, required/optional status, field IDs,
validation limits, privacy confirmation, optional contact permission, receipt,
deletion flow or private report handling for ordinary text/image/layout changes.
The upload limit is 1-3 JPG/PNG/WebP images, maximum 8 MB per image.
Never make report images publicly accessible or add email/CRM sends or tracking.
Do not change authentication, database schema or deployment settings during a
cosmetic change. Flag a request that crosses those boundaries before proceeding.

## Quick visual preview (no credentials needed)
Use Python 3.13 where available. From the repository root:

```sh
python preview.py --host 127.0.0.1 --port 8000
```
This serves only the generated self-contained demo at http://127.0.0.1:8000/.
Synthetic reports stay in browser memory and disappear on reload. The demo admin
is not authenticated and is NOT a production admin. No report collection occurs.
Restart the preview process after source edits. Inside an isolated preview
sandbox only, binding to 0.0.0.0 may be required by a browser tool. Do not expose
this demo or the repo publicly without explicit approval.
A screenshot is not the same as a running user-accessible preview; state which
one you actually produced. Do not invent a preview link.

## Setup and checks
For the existing backend and browser regression tests:

```sh
python -m pip install -r requirements-dev.txt
python build_preview.py
python -m pytest tests -q
```
For browser tests, use an installed Chromium (auto-detected) or install the
Playwright-managed browser during environment setup:

```sh
python -m playwright install --with-deps chromium
python test_browser.py
```
If OS package installation is not permitted, use `python -m playwright install
chromium` and report any remaining missing system libraries. CHROMIUM_PATH can
specify an existing executable. Do not hide a failed install, build or test.
Requirements are inherited exact pins, not a claim of current security approval.
If dependencies are unavailable, explain the issue rather than silently changing
runtime versions; the visual preview still works with the Python standard library.
Use `tests/` explicitly for pytest: `test_browser.py` is a separate executable test.

After UI edits rebuild `noair-forhandsvisning.html`, run available tests, inspect
mobile and desktop widths, and report exactly what passed and what was not run.
If making a pull request, include the source and rebuilt preview; report in plain
Swedish what changed and which checks were performed. A merge is not deployment.

## Secrets and publishing boundaries
Only synthetic test data belong in this repository. Do not add real report images,
customer details, personal data, passwords, API keys, tokens, filled `.env` files,
or databases. `.env.example` contains blank placeholders, not production secrets.
Check `.gitignore` is present, including after browser-based initial upload.
Do not connect AWS, change DNS, enable public collection, buy services, or publish
anything without an explicit separate request. Do not imply this setup has a
production pipeline. The original Dockerfile is reference code, not an active deploy.
AGENTS.md is guidance, not a technical security boundary; keep permissions narrow.
