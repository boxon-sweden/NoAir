"""Noair pilot: private packaging reports, a browser UI, and an admin API.

Single-instance deployment, persistent disk, HTTPS reverse proxy required.
No external AI, analytics, image publishing or CRM writes. Email is opt-in and manual.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import time
import uuid
import warnings
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.middleware.trustedhost import TrustedHostMiddleware

import outreach

ROOT = Path(__file__).resolve().parent
COOKIE = "noair_session"
SESSION_SECONDS = 4 * 60 * 60
MAX_FILE = 8 * 1024 * 1024
MAX_BODY = 25 * 1024 * 1024
ISSUES = {"air", "filler", "oversized", "protection", "other"}
STATUSES = {"new", "reviewed", "opportunity", "contacted", "meeting", "archived", "rejected"}
CATEGORIES = {"", "Elektronik", "Kl\u00e4der & skor", "Hem & inredning", "Sport & fritid", "Annat / vill inte ange"}
PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
LOG = logging.getLogger("noair")
Image.MAX_IMAGE_PIXELS = 25_000_000


def load_env() -> None:
    """Read a simple KEY=value .env without overwriting explicit environment values."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_from_env() -> dict:
    load_env()
    return {
        "secret": os.getenv("SECRET_KEY", ""),
        "admin_username": os.getenv("ADMIN_USERNAME", "admin"),
        "admin_password_hash": os.getenv("ADMIN_PASSWORD_HASH", ""),
        "data_dir": os.getenv("DATA_DIR", str(ROOT / "data")),
        "mode": os.getenv("APP_ENV", "development"),
        "public_origin": os.getenv("PUBLIC_ORIGIN", "http://127.0.0.1:8000"),
        "submissions_enabled": os.getenv("SUBMISSIONS_ENABLED", "0") == "1",
        "privacy_ready": os.getenv("PRIVACY_REVIEWED", "0") == "1",
        "controller_name": os.getenv("CONTROLLER_NAME", ""),
        "controller_email": os.getenv("CONTROLLER_EMAIL", ""),
        "legal_basis_description": os.getenv("LEGAL_BASIS_DESCRIPTION", ""),
        "processors_description": os.getenv("PROCESSORS_DESCRIPTION", ""),
        "backup_policy": os.getenv("BACKUP_POLICY", ""),
        "security_logs_description": os.getenv("SECURITY_LOGS_DESCRIPTION", ""),
        "privacy_version": os.getenv("PRIVACY_VERSION", "pilot-draft-1"),
        "retention_days": int(os.getenv("RETENTION_DAYS", "180")),
        "contact_lookup_enabled": os.getenv("CONTACT_LOOKUP_ENABLED", "0") == "1",
        "mail_enabled": os.getenv("OUTREACH_MAIL_ENABLED", "0") == "1",
        "mail_from": os.getenv("OUTREACH_FROM_EMAIL", "Marcus.gustafsson@boxon.com"),
        "mail_from_name": os.getenv("OUTREACH_FROM_NAME", "Boxon"),
    }


@contextmanager
def database(config: dict):
    connection = sqlite3.connect(Path(config["data_dir"]) / "noair.sqlite3", timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database(config: dict) -> None:
    data = Path(config["data_dir"])
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    (data / "images").mkdir(exist_ok=True, mode=0o700)
    with database(config) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, company TEXT NOT NULL, website TEXT NOT NULL,
          issues TEXT NOT NULL, category TEXT NOT NULL, comment TEXT NOT NULL,
          email TEXT NOT NULL, contact_permission INTEGER NOT NULL,
          created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
          notes TEXT NOT NULL DEFAULT '', review_checked INTEGER NOT NULL DEFAULT 0,
          deletion_hash TEXT NOT NULL, privacy_version TEXT NOT NULL,
          privacy_confirmed_at TEXT NOT NULL, contact_permission_at TEXT
        );
        CREATE INDEX IF NOT EXISTS reports_created_at ON reports(created_at);
        CREATE TABLE IF NOT EXISTS images (
          name TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS outreach (
          report_id TEXT PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
          recipient_name TEXT NOT NULL DEFAULT '', recipient_role TEXT NOT NULL DEFAULT '',
          recipient_email TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
          subject TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft',
          contact_checked INTEGER NOT NULL DEFAULT 0, content_checked INTEGER NOT NULL DEFAULT 0,
          contacts TEXT NOT NULL DEFAULT '[]', lookup_note TEXT NOT NULL DEFAULT '',
          lookup_state TEXT NOT NULL DEFAULT 'idle', lookup_started REAL NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL, sent_at TEXT, error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS pending_deletions (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL,
          admin INTEGER NOT NULL DEFAULT 0, expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rate_limits (
          bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL, report_id TEXT
        );
        """)
        for row in db.execute("SELECT id,company,category,issues,comment FROM reports WHERE id NOT IN (SELECT report_id FROM outreach)").fetchall():
            report = dict(row); report['issues'] = json.loads(report['issues'])
            draft = outreach.draft_for(report, int(hashlib.sha256(row['id'].encode()).hexdigest()[:2], 16) % 3)
            db.execute("INSERT INTO outreach(report_id,subject,body,updated_at) VALUES(?,?,?,?)",
                       (row['id'], draft['subject'], draft['body'], iso_now()))
    os.chmod(data / "noair.sqlite3", 0o600)


def audit(config: dict, action: str, report_id: str | None = None) -> None:
    with database(config) as db:
        db.execute("INSERT INTO audit(at, action, report_id) VALUES(?,?,?)", (iso_now(), action, report_id))


def image_path(config: dict, name: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", name):
        raise HTTPException(404, "Bilden finns inte.")
    return Path(config["data_dir"]) / "images" / name


def cleanup_files(config: dict) -> None:
    with database(config) as db:
        names = [row[0] for row in db.execute("SELECT name FROM pending_deletions")]
    for name in names:
        try:
            image_path(config, name).unlink(missing_ok=True)
            with database(config) as db:
                db.execute("DELETE FROM pending_deletions WHERE name=?", (name,))
        except OSError:
            LOG.error("A queued image deletion failed; it will be retried.")


def remove_reports(config: dict, ids: list[str]) -> None:
    with database(config) as db:
        for report_id in ids:
            db.execute("INSERT OR IGNORE INTO pending_deletions(name) SELECT name FROM images WHERE report_id=?", (report_id,))
            db.execute("DELETE FROM reports WHERE id=?", (report_id,))
    cleanup_files(config)


def purge(config: dict) -> int:
    """Runs on application start and hourly, and via `python manage.py purge`."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=config["retention_days"])).isoformat()
    with database(config) as db:
        ids = [r[0] for r in db.execute("SELECT id FROM reports WHERE created_at < ?", (cutoff,))]
    remove_reports(config, ids)
    with database(config) as db:
        db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        db.execute("DELETE FROM rate_limits WHERE expires < ?", (time.time(),))
        db.execute("DELETE FROM audit WHERE at < ?", (cutoff,))
        tracked = {r[0] for r in db.execute("SELECT name FROM images")}
    # Also recover image files left by a crash before the DB transaction committed.
    for path in (Path(config["data_dir"]) / "images").glob("*.jpg"):
        if path.name not in tracked and path.stat().st_mtime < time.time() - 86400:
            path.unlink(missing_ok=True)
    return len(ids)


class BodyLimitMiddleware:
    """Enforce limits on actual bytes, including chunked bodies without a length header."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH", "DELETE", "PUT"}:
            return await self.app(scope, receive, send)
        limit = MAX_BODY if scope["path"] == "/api/reports" else 65536
        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > limit:
                return await JSONResponse({"detail": "Uppladdningen \u00e4r f\u00f6r stor."}, status_code=413)(scope, receive, send)
        except ValueError:
            return await JSONResponse({"detail": "Ogiltig f\u00f6rfr\u00e5gan."}, status_code=400)(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                return await JSONResponse({"detail": "Uppladdningen \u00e4r f\u00f6r stor."}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def create_app(config: dict | None = None) -> FastAPI:
    c = config if config is not None else config_from_env()
    if len(c.get("secret", "")) < 32 or not c.get("admin_password_hash", ""):
        raise RuntimeError("Run `python manage.py setup` or set SECRET_KEY and ADMIN_PASSWORD_HASH.")
    if c["retention_days"] < 1:
        raise RuntimeError("RETENTION_DAYS must be positive.")
    if c["mode"] == "production":
        if not c["public_origin"].startswith("https://"):
            raise RuntimeError("Production requires HTTPS PUBLIC_ORIGIN.")
        if c["submissions_enabled"]:
            required = ["controller_name", "controller_email", "legal_basis_description", "processors_description", "backup_policy", "security_logs_description"]
            if not c["privacy_ready"] or any(not c.get(k) for k in required) or "draft" in c["privacy_version"]:
                raise RuntimeError("Public collection is blocked until the privacy and operating settings are reviewed and complete.")
    init_database(c)

    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(purge, c)
        async def housekeeping():
            while True:
                await asyncio.sleep(3600)
                try:
                    await run_in_threadpool(purge, c)
                except Exception:
                    LOG.exception("Scheduled retention cleanup failed. Operator action required.")
        task = asyncio.create_task(housekeeping())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="Noair private pilot API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.config = c
    image_gate = asyncio.Semaphore(2)
    app.add_middleware(BodyLimitMiddleware)
    if c["mode"] == "production":
        host = urlsplit(c["public_origin"]).hostname
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host, "www." + host] if not host.startswith("www.") else [host])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        })
        if request.url.path.startswith("/api") or request.url.path == "/admin":
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if c["mode"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        else:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    def get_session(request: Request) -> dict | None:
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 128:
            return None
        with database(c) as db:
            row = db.execute("SELECT * FROM sessions WHERE token_hash=? AND expires>?", (digest(token), time.time())).fetchone()
        return dict(row) if row else None

    def new_session(response: Response, admin: bool = False, old: dict | None = None) -> str:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with database(c) as db:
            if old:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (old["token_hash"],))
            db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), csrf, int(admin), time.time() + SESSION_SECONDS))
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=c["mode"] == "production", samesite="lax", path="/")
        return csrf

    def require_session(request: Request, write: bool = False, admin: bool = False) -> dict:
        session = get_session(request)
        if not session or (admin and not session["admin"]):
            raise HTTPException(401, "Sessionen har g\u00e5tt ut. Ladda om sidan och logga in igen vid behov.")
        if write:
            if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session["csrf"]):
                raise HTTPException(403, "S\u00e4kerhetskontrollen misslyckades. Ladda om sidan.")
            origin = request.headers.get("origin")
            expected = c["public_origin"].rstrip("/") if c["mode"] == "production" else str(request.base_url).rstrip("/")
            if origin and origin != expected:
                raise HTTPException(403, "F\u00f6rfr\u00e5gan kommer fr\u00e5n fel webbplats.")
        return session

    def rate_limit(request: Request, action: str, limit: int, window: int) -> None:
        # Raw IP addresses are not persisted by this application. Proxy logging is separate.
        ip = request.client.host if request.client else "unknown"
        window_id = str(int(time.time()) // window)
        bucket = hmac.new(c["secret"].encode(), f"{action}:{ip}:{window_id}".encode(), hashlib.sha256).hexdigest()
        with database(c) as db:
            db.execute("INSERT INTO rate_limits(bucket,count,expires) VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1", (bucket, time.time()+86400))
            count = db.execute("SELECT count FROM rate_limits WHERE bucket=?", (bucket,)).fetchone()[0]
        if count > limit:
            raise HTTPException(429, "F\u00f6r m\u00e5nga f\u00f6rs\u00f6k. F\u00f6rs\u00f6k igen senare.", headers={"Retry-After": str(window)})

    def active_report(report_id: str):
        cutoff = (datetime.now(timezone.utc)-timedelta(days=c["retention_days"])).isoformat()
        with database(c) as db:
            row = db.execute("SELECT * FROM reports WHERE id=? AND created_at>=?", (report_id, cutoff)).fetchone()
        if not row:
            raise HTTPException(404, "Rapporten finns inte.")
        return row

    def report_json(row, include_private: bool = False) -> dict:
        fields = ["id", "company", "website", "category", "created_at", "status", "review_checked"]
        if include_private:
            fields += ["comment", "email", "contact_permission", "notes", "privacy_version", "contact_permission_at"]
        result = {k: row[k] for k in fields}
        result["issues"] = json.loads(row["issues"])
        result["review_checked"] = bool(result["review_checked"])
        if include_private:
            result["contact_permission"] = bool(result["contact_permission"])
            with database(c) as db:
                names = [r[0] for r in db.execute("SELECT name FROM images WHERE report_id=?", (row["id"],))]
            result["images"] = ["/api/admin/images/" + name for name in names]
        return result

    @app.get("/api/session")
    def session_endpoint(request: Request):
        session = get_session(request)
        response = JSONResponse({})
        if not session:
            rate_limit(request, "session", 240, 3600)
        token = session["csrf"] if session else new_session(response)
        settings = {k: c.get(k) for k in ["mode", "submissions_enabled", "privacy_ready", "controller_name", "controller_email", "legal_basis_description", "processors_description", "backup_policy", "security_logs_description", "privacy_version", "retention_days"]}
        response.body = json.dumps({"csrf": token, "authenticated": bool(session and session["admin"]), "settings": settings}).encode()
        response.headers["content-length"] = str(len(response.body))
        return response

    async def json_body(request: Request) -> dict:
        try:
            value = await request.json()
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(400, "Ogiltig f\u00f6rfr\u00e5gan.")

    @app.post("/api/login")
    async def login(request: Request):
        session = require_session(request, write=True)
        rate_limit(request, "login", 8, 900)
        data = await json_body(request)
        username, password = data.get("username", ""), data.get("password", "")
        valid = False
        if isinstance(username, str) and isinstance(password, str) and len(password) <= 1024:
            try:
                valid_password = await run_in_threadpool(PH.verify, c["admin_password_hash"], password)
                valid = valid_password and hmac.compare_digest(username.encode(), c["admin_username"].encode())
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                pass
        if not valid:
            audit(c, "login_failed")
            raise HTTPException(401, "Fel anv\u00e4ndarnamn eller l\u00f6senord.")
        response = JSONResponse({})
        csrf = new_session(response, admin=True, old=session)
        response.body = json.dumps({"csrf": csrf}).encode()
        response.headers["content-length"] = str(len(response.body))
        audit(c, "login")
        return response

    @app.post("/api/logout")
    def logout(request: Request):
        old = require_session(request, write=True)
        response = JSONResponse({})
        csrf = new_session(response, old=old)
        response.body = json.dumps({"csrf": csrf}).encode()
        response.headers["content-length"] = str(len(response.body))
        audit(c, "logout")
        return response

    @app.post("/api/reports", status_code=201)
    async def submit_report(request: Request, background_tasks: BackgroundTasks):
        require_session(request, write=True)
        rate_limit(request, "report", 8, 3600)
        if not c["submissions_enabled"]:
            raise HTTPException(503, "Rapporteringen \u00e4r inte \u00f6ppen \u00e4nnu.")
        try:
            async with request.form(max_files=3, max_fields=20, max_part_size=8192) as form:
                values = validate_report(form)
                photos = form.getlist("photos")
                if not 1 <= len(photos) <= 3 or any(not isinstance(p, UploadFile) for p in photos):
                    raise HTTPException(400, "V\u00e4lj mellan en och tre bilder.")
                encoded = []
                for photo in photos:
                    raw = await photo.read(MAX_FILE + 1)
                    if len(raw) > MAX_FILE:
                        raise HTTPException(413, "En bild \u00e4r st\u00f6rre \u00e4n 8 MB.")
                    async with image_gate:
                        encoded.append(await run_in_threadpool(clean_image, raw))
        except HTTPException:
            raise
        except Exception as error:
            from starlette.exceptions import HTTPException as StarletteHTTPException
            if isinstance(error, StarletteHTTPException):
                raise HTTPException(400, "Kontrollera filerna. H\u00f6gst tre bilder \u00e4r till\u00e5tna.")
            raise
        report_id = "NA-" + secrets.token_hex(5).upper()
        deletion_token = secrets.token_urlsafe(24)
        now = iso_now()
        names = []
        try:
            for data in encoded:
                name = uuid.uuid4().hex + ".jpg"
                target = image_path(c, name)
                with target.open("xb") as file:
                    file.write(data)
                target.chmod(0o600)
                names.append(name)
            with database(c) as db:
                db.execute("""INSERT INTO reports(id,company,website,issues,category,comment,email,contact_permission,created_at,deletion_hash,privacy_version,privacy_confirmed_at,contact_permission_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (report_id, values["company"], values["website"], json.dumps(values["issues"]), values["category"], values["comment"], values["email"], int(values["contact_permission"]), now, digest(deletion_token), c["privacy_version"], now, now if values["contact_permission"] else None))
                db.executemany("INSERT INTO images(name,report_id) VALUES(?,?)", [(name, report_id) for name in names])
                draft = outreach.draft_for(values, int(report_id[-2:], 16) % 3)
                db.execute("INSERT INTO outreach(report_id,subject,body,updated_at) VALUES(?,?,?,?)",
                           (report_id, draft['subject'], draft['body'], now))
        except Exception:
            for name in names:
                image_path(c, name).unlink(missing_ok=True)
            raise
        if c.get('contact_lookup_enabled') and values['website']:
            background_tasks.add_task(find_contacts, report_id)
        return {"id": report_id, "deletion_token": deletion_token}

    @app.post("/api/reports/delete")
    async def public_delete(request: Request):
        require_session(request, write=True)
        rate_limit(request, "delete", 15, 3600)
        data = await json_body(request)
        report_id, token = data.get("id", ""), data.get("token", "")
        if not isinstance(report_id, str) or not isinstance(token, str) or len(token)>256 or len(report_id)>64:
            raise HTTPException(400, "Kontrollera rapportnummer och raderingskod.")
        with database(c) as db:
            row = db.execute("SELECT deletion_hash FROM reports WHERE id=?", (report_id,)).fetchone()
        if not row or not hmac.compare_digest(row["deletion_hash"], digest(token)):
            raise HTTPException(400, "Rapportnummer eller raderingskod st\u00e4mmer inte.")
        remove_reports(c, [report_id])
        audit(c, "public_delete", report_id)
        return {"deleted": True}

    @app.get("/api/admin/reports")
    def list_reports(request: Request):
        require_session(request, admin=True)
        cutoff = (datetime.now(timezone.utc)-timedelta(days=c["retention_days"])).isoformat()
        with database(c) as db:
            rows = db.execute("SELECT * FROM reports WHERE created_at>=? ORDER BY created_at DESC", (cutoff,)).fetchall()
        audit(c, "list_reports")
        return {"reports": [report_json(r) for r in rows]}

    @app.get("/api/admin/reports/{report_id}")
    def get_report(report_id: str, request: Request):
        require_session(request, admin=True)
        row = active_report(report_id)
        audit(c, "view_report", report_id)
        return report_json(row, include_private=True)

    @app.patch("/api/admin/reports/{report_id}")
    async def update_report(report_id: str, request: Request):
        require_session(request, write=True, admin=True)
        active_report(report_id)
        data = await json_body(request)
        status, notes, checked = data.get("status"), data.get("notes", ""), data.get("review_checked")
        if not isinstance(status, str) or status not in STATUSES or not isinstance(notes, str) or len(notes)>3000 or type(checked) is not bool:
            raise HTTPException(400, "Kontrollera status och anteckning.")
        if not checked and status not in {"new", "rejected", "archived"}:
            raise HTTPException(400, "Granska rapporten och markera kontrollrutan f\u00f6rst.")
        with database(c) as db:
            db.execute("UPDATE reports SET status=?,notes=?,review_checked=? WHERE id=?", (status, notes.strip(), int(checked), report_id))
            if not checked or status in {'new', 'rejected', 'archived'}:
                db.execute("UPDATE outreach SET state='draft',content_checked=0,version=version+1,updated_at=? WHERE report_id=? AND state IN ('draft','ready','failed')", (iso_now(), report_id))
        audit(c, "update_report", report_id)
        return {"saved": True}

    @app.delete("/api/admin/reports/{report_id}")
    def delete_report(report_id: str, request: Request):
        require_session(request, write=True, admin=True)
        active_report(report_id)
        remove_reports(c, [report_id])
        audit(c, "admin_delete", report_id)
        return {"deleted": True}

    @app.get("/api/admin/images/{name}")
    def get_image(name: str, request: Request):
        require_session(request, admin=True)
        path = image_path(c, name)
        with database(c) as db:
            row = db.execute("SELECT report_id FROM images WHERE name=?", (name,)).fetchone()
        if not row or not path.exists():
            raise HTTPException(404, "Bilden finns inte.")
        active_report(row["report_id"])
        audit(c, "view_image", row["report_id"])
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store, private"})

    @app.get("/api/admin/export")
    def export_csv(request: Request):
        require_session(request, admin=True)
        cutoff = (datetime.now(timezone.utc)-timedelta(days=c["retention_days"])).isoformat()
        with database(c) as db:
            rows = db.execute("SELECT * FROM reports WHERE created_at>=? ORDER BY created_at DESC", (cutoff,)).fetchall()
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Rapport", "F\u00f6retag", "Webbplats", "Datum", "Status", "Upplevelse"])
        for row in rows:
            writer.writerow([csv_safe(row[k]) for k in ["id", "company", "website", "created_at", "status"]]+[csv_safe(", ".join(json.loads(row["issues"])))])
        audit(c, "export")
        return Response("\ufeff"+output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="noair-oversikt.csv"'})

    def outreach_json(row):
        result = dict(row)
        result['contacts'] = json.loads(result['contacts'])
        result['contact_checked'] = bool(result['contact_checked'])
        result['content_checked'] = bool(result['content_checked'])
        return result

    def current_outreach(report_id):
        active_report(report_id)
        with database(c) as db:
            row = db.execute("SELECT * FROM outreach WHERE report_id=?", (report_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Utkastet finns inte.")
        return outreach_json(row)

    def find_contacts(report_id):
        started = time.time()
        try:
            report = active_report(report_id)
            with database(c) as db:
                changed = db.execute("UPDATE outreach SET lookup_state='searching',lookup_started=? WHERE report_id=? AND (lookup_state!='searching' OR lookup_started<?)", (started, report_id, started-120)).rowcount
            if not changed:
                return
            result = outreach.lookup_contacts(report['website'])
            state = 'done'
        except Exception:
            result = {'contacts': [], 'lookup_note': 'Kontaktsökningen kunde inte slutföras. Kontrollera webbplatsen eller lägg till kontakt manuellt.'}
            state = 'failed'
        with database(c) as db:
            db.execute("UPDATE outreach SET contacts=?,lookup_note=?,lookup_state=? WHERE report_id=? AND lookup_started=?",
                       (json.dumps(result['contacts']), result['lookup_note'], state, report_id, started))

    @app.get("/api/admin/outreach")
    def list_outreach(request: Request):
        require_session(request, admin=True)
        cutoff = (datetime.now(timezone.utc)-timedelta(days=c['retention_days'])).isoformat()
        with database(c) as db:
            rows = db.execute("SELECT o.*,r.company,r.status AS report_status,r.review_checked FROM outreach o JOIN reports r ON r.id=o.report_id WHERE r.created_at>=? ORDER BY o.updated_at DESC", (cutoff,)).fetchall()
        return {'messages': [outreach_json(row) for row in rows],
                'mail_configured': outreach.mail_configured(c), 'lookup_enabled': bool(c.get('contact_lookup_enabled'))}

    @app.get("/api/admin/reports/{report_id}/outreach")
    def get_outreach(report_id: str, request: Request):
        require_session(request, admin=True)
        result = current_outreach(report_id)
        report = report_json(active_report(report_id), include_private=True)
        result['variants'] = [outreach.draft_for(report, variant) for variant in range(3)]
        return result

    @app.put("/api/admin/reports/{report_id}/outreach")
    async def save_outreach(report_id: str, request: Request):
        require_session(request, write=True, admin=True)
        report = active_report(report_id)
        data = await json_body(request)
        fields = {'recipient_name':160, 'recipient_role':160, 'recipient_email':254,
                  'source_url':2048, 'subject':250, 'body':10000}
        values = {}
        for field, limit in fields.items():
            value = data.get(field, '')
            if not isinstance(value, str) or len(value)>limit or '\x00' in value:
                raise HTTPException(400, 'Kontrollera kontaktuppgifter och meddelande.')
            if field != 'body' and any(x in value for x in '\r\n'):
                raise HTTPException(400, 'Kontaktuppgifter och ämne får inte innehålla radbrytningar.')
            values[field] = value.strip()
        state = data.get('state', 'draft')
        version = data.get('version')
        contact_checked, content_checked = data.get('contact_checked', False), data.get('content_checked', False)
        if state not in {'draft', 'ready'} or type(version) is not int or type(contact_checked) is not bool or type(content_checked) is not bool:
            raise HTTPException(400, 'Kontrollera meddelandets status.')
        if values['recipient_email'] and not outreach.valid_email(values['recipient_email']):
            raise HTTPException(400, 'Ange en giltig mottagaradress.')
        if values['source_url']:
            try:
                values['source_url'] = outreach.public_url(values['source_url'])
            except ValueError as error:
                raise HTTPException(400, str(error))
        if state == 'ready':
            if not report['review_checked'] or report['status'] in {'new', 'rejected', 'archived'}:
                raise HTTPException(400, 'Granska och spara rapporten först.')
            if not (contact_checked and content_checked and values['recipient_email'] and values['subject'] and values['body']):
                raise HTTPException(400, 'Kontrollera mottagare och meddelande innan det läggs i utskickskön.')
        with database(c) as db:
            db.execute('BEGIN IMMEDIATE')
            current_report = db.execute('SELECT review_checked,status FROM reports WHERE id=?', (report_id,)).fetchone()
            if not current_report:
                raise HTTPException(404, 'Rapporten finns inte.')
            if state == 'ready' and (not current_report['review_checked'] or current_report['status'] in {'new','rejected','archived'}):
                raise HTTPException(400, 'Rapportens granskning har ändrats. Granska rapporten igen.')
            changed = db.execute("UPDATE outreach SET recipient_name=?,recipient_role=?,recipient_email=?,source_url=?,subject=?,body=?,state=?,contact_checked=?,content_checked=?,version=version+1,updated_at=?,error='' WHERE report_id=? AND version=? AND state IN ('draft','ready','failed')",
                                 (*values.values(), state, int(contact_checked), int(content_checked), iso_now(), report_id, version)).rowcount
        if not changed:
            raise HTTPException(409, 'Utkastet har ändrats eller kan inte redigeras. Öppna det igen.')
        audit(c, 'save_outreach', report_id)
        return current_outreach(report_id)

    @app.post("/api/admin/reports/{report_id}/contacts")
    def search_contacts(report_id: str, request: Request):
        require_session(request, write=True, admin=True)
        report = active_report(report_id)
        rate_limit(request, 'contact_lookup', 20, 3600)
        if not c.get('contact_lookup_enabled'):
            raise HTTPException(503, 'Kontaktsökning är inte aktiverad på servern.')
        if not report['website']:
            raise HTTPException(400, 'Rapporten saknar företagswebbplats. Lägg till en kontakt manuellt.')
        find_contacts(report_id)
        return {'completed': True}

    @app.post("/api/admin/reports/{report_id}/outreach/send")
    async def send_outreach(report_id: str, request: Request):
        require_session(request, write=True, admin=True)
        data = await json_body(request)
        if type(data.get('version')) is not int:
            raise HTTPException(400, 'Öppna meddelandet igen.')
        if not outreach.mail_configured(c):
            raise HTTPException(503, 'Mejltjänsten är inte ansluten. Meddelandet ligger kvar i kön.')
        rate_limit(request, 'send_outreach', 30, 3600)
        report = active_report(report_id)
        with database(c) as db:
            db.execute('BEGIN IMMEDIATE')
            # Re-read under the write lock: report review and queue state are authoritative.
            report = db.execute('SELECT * FROM reports WHERE id=?', (report_id,)).fetchone()
            row = db.execute('SELECT * FROM outreach WHERE report_id=?', (report_id,)).fetchone()
            if not report or not row:
                raise HTTPException(404, 'Rapporten finns inte.')
            if not report['review_checked'] or report['status'] in {'new', 'rejected', 'archived'}:
                raise HTTPException(400, 'Rapporten behöver vara granskad före utskick.')
            if row['state']!='ready' or row['version']!=data['version']:
                raise HTTPException(409, 'Meddelandet är inte klart, har ändrats eller har redan skickats.')
            if not row['contact_checked'] or not row['content_checked'] or not outreach.valid_email(row['recipient_email']):
                raise HTTPException(400, 'Kontrollera meddelandet och mottagaren först.')
            db.execute("UPDATE outreach SET state='sending',version=version+1,updated_at=? WHERE report_id=?", (iso_now(), report_id))
            draft = dict(row)
        try:
            await run_in_threadpool(outreach.send_message, c, draft)
        except outreach.DeliveryUncertain:
            state, error = 'uncertain', 'Leveransstatus är okänd. Kontrollera mejltjänstens logg innan fler försök.'
        except outreach.DeliveryRejected:
            state, error = 'failed', 'Mejltjänsten avvisade meddelandet. Kontrollera anslutning och mottagare innan ett nytt försök.'
        except Exception:
            state, error = 'uncertain', 'Leveransstatus är okänd. Kontrollera eMarketeers logg före fler försök.'
        else:
            state, error = 'sent', ''
        with database(c) as db:
            db.execute('UPDATE outreach SET state=?,error=?,sent_at=?,updated_at=?,version=version+1 WHERE report_id=?',
                       (state, error, iso_now() if state=='sent' else None, iso_now(), report_id))
            if state=='sent':
                db.execute("UPDATE reports SET status=CASE WHEN status='meeting' THEN status ELSE 'contacted' END WHERE id=?", (report_id,))
        audit(c, 'outreach_'+state, report_id)
        return current_outreach(report_id)

    @app.post("/api/admin/reports/{report_id}/outreach/resolve")
    async def resolve_outreach(report_id: str, request: Request):
        require_session(request, write=True, admin=True)
        active_report(report_id)
        data = await json_body(request)
        if data.get('checked_provider_log') is not True or data.get('state') not in {'sent', 'draft'} or type(data.get('version')) is not int:
            raise HTTPException(400, 'Kontrollera mejltjänstens logg och ange utfallet.')
        state = data['state']
        current = current_outreach(report_id)
        if current['state']=='sending' and (datetime.now(timezone.utc)-datetime.fromisoformat(current['updated_at'])).total_seconds()<300:
            raise HTTPException(409, 'Utskick pågår. Vänta minst fem minuter och kontrollera sedan mejltjänstens logg.')
        with database(c) as db:
            changed = db.execute("UPDATE outreach SET state=?,sent_at=?,error='',content_checked=0,version=version+1,updated_at=? WHERE report_id=? AND version=? AND state IN ('sending','uncertain')",
                                 (state, iso_now() if state=='sent' else None, iso_now(), report_id, data['version'])).rowcount
            if not changed:
                raise HTTPException(409, 'Meddelandets status har ändrats.')
            if state=='sent':
                db.execute("UPDATE reports SET status=CASE WHEN status='meeting' THEN status ELSE 'contacted' END WHERE id=?", (report_id,))
        audit(c, 'resolve_outreach_'+state, report_id)
        return current_outreach(report_id)

    @app.get("/healthz")
    def health():
        with database(c) as db:
            db.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/robots.txt")
    def robots():
        return Response("User-agent: *\nDisallow: /admin\nDisallow: /api/\n" if c["mode"]=="production" else "User-agent: *\nDisallow: /\n", media_type="text/plain")

    @app.get("/")
    def home():
        return FileResponse(ROOT / "static/index.html", media_type="text/html")

    @app.get("/admin")
    def admin_page():
        html = (ROOT / "static/index.html").read_text(encoding="utf-8").replace('data-page="public"', 'data-page="admin"')
        return HTMLResponse(html)

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


def csv_safe(value) -> str:
    value = str(value or "")
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    return value


def validate_report(form) -> dict:
    def field(name: str, maxlen: int, required: bool = False) -> str:
        value = form.get(name, "")
        if not isinstance(value, str):
            raise HTTPException(400, "Ogiltigt formul\u00e4rf\u00e4lt.")
        value = value.strip()
        if len(value)>maxlen or (required and not value) or any(ord(ch)<32 and ch not in "\n\t\r" for ch in value):
            raise HTTPException(400, "Kontrollera textf\u00e4lten i rapporten.")
        return value
    if field("company_fax", 200):
        raise HTTPException(400, "Rapporten kunde inte tas emot.")
    company = field("company", 160, True)
    website = normalize_website(field("website", 250))
    selected = form.getlist("issues")
    if not selected or len(selected)>5 or any(not isinstance(i,str) or i not in ISSUES for i in selected):
        raise HTTPException(400, "V\u00e4lj minst en upplevelse.")
    category = field("category", 80)
    if category not in CATEGORIES:
        raise HTTPException(400, "Ogiltig produktkategori.")
    if form.get("privacy_confirmed") != "true":
        raise HTTPException(400, "Bekr\u00e4fta att du kontrollerat bilderna och l\u00e4st informationen.")
    email = field("email", 254)
    permission = form.get("contact_permission") == "true"
    if email and (not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not permission):
        raise HTTPException(400, "E-post kr\u00e4ver ett giltigt format och separat godk\u00e4nnande.")
    if permission and not email:
        raise HTTPException(400, "Ange e-post eller avmarkera kontaktalternativet.")
    return {"company": company, "website": website, "issues": sorted(set(selected)), "category": category,
            "comment": field("comment", 1500), "email": email, "contact_permission": permission}


def normalize_website(value: str) -> str:
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://"+value
    try:
        url = urlsplit(value)
        host = (url.hostname or "").encode("idna").decode().lower()
        if url.scheme not in {"https", "http"} or "." not in host or url.username or url.password or url.port or not re.fullmatch(r"[a-z0-9.-]+", host):
            raise ValueError
        return "https://"+host
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Ange en giltig butiksadress, till exempel butik.se.")


def clean_image(raw: bytes) -> bytes:
    """Decode actual image data, limit dimensions, remove metadata, re-encode JPEG.

    Does NOT detect or remove shipping-label text, QR codes, faces or other PII.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or source.width*source.height>25_000_000:
                    raise ValueError
                source.load()
                image = ImageOps.exif_transpose(source)
                image.thumbnail((2048,2048), Image.Resampling.LANCZOS)
                clean = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    rgba = image.convert("RGBA")
                    clean.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    clean.paste(image.convert("RGB"))
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=88, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "En bild kunde inte l\u00e4sas. V\u00e4lj JPG, PNG eller WebP, h\u00f6gst 25 megapixel.")
