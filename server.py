#!/usr/bin/env python3
"""World Wide Bistro website and reservation request backend."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from datetime import date, datetime, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "requests.sqlite3"
BUSINESS_EMAIL = "fe.worldwidebistro.srl@gmail.com"
SESSION_COOKIE = "wwb_admin"
SESSION_SECONDS = 12 * 60 * 60
MAX_BODY_BYTES = 24_000
ALLOWED_TYPES = {
    "Rezervare masă",
    "Petrecere aniversară",
    "Seară tematică",
    "Atelier",
    "Altă întrebare",
}
ALLOWED_STATUSES = {"Nouă", "Contactată", "Confirmată", "Închisă"}
RATE_LIMITS: dict[str, list[float]] = {}


def load_local_env() -> None:
    """Load simple KEY=value settings from .env without an extra dependency."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


load_local_env()
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(32)
    print("Atenție: SESSION_SECRET temporar. Configurează .env înainte de folosirea panoului.")


def connect_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(DATA_DIR, 0o700)
    except OSError:
        pass
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            request_type TEXT NOT NULL,
            event_date TEXT NOT NULL DEFAULT '',
            event_time TEXT NOT NULL DEFAULT '',
            guests INTEGER,
            message TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Nouă',
            email_sent INTEGER NOT NULL DEFAULT 0
        )
    """)
    db.commit()
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError:
        pass
    return db


def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    recent = [stamp for stamp in RATE_LIMITS.get(key, []) if now - stamp < window_seconds]
    if len(recent) >= limit:
        RATE_LIMITS[key] = recent
        return False
    recent.append(now)
    RATE_LIMITS[key] = recent
    return True


def make_session(username: str) -> str:
    expires = int(time.time()) + SESSION_SECONDS
    payload = f"{username}:{expires}"
    signature = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def valid_session(token: str) -> bool:
    try:
        expires_text, signature = token.split(".", 1)
        expires = int(expires_text)
    except (ValueError, AttributeError):
        return False
    if expires < int(time.time()):
        return False
    payload = f"{ADMIN_USERNAME}:{expires}"
    expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def send_email_notification(record: dict) -> bool:
    host = os.environ.get("SMTP_HOST", "").strip()
    username = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", username).strip()
    if not all((host, username, password, sender)):
        print("Notificarea nu a fost trimisă: configurează SMTP_HOST, SMTP_USER, SMTP_PASSWORD și SMTP_FROM în .env.")
        return False

    message = EmailMessage()
    message["Subject"] = f"Solicitare World Wide Bistro — {record['request_type']}"
    message["From"] = sender
    message["To"] = BUSINESS_EMAIL
    if record["email"]:
        message["Reply-To"] = record["email"]
    details = [
        "Ai primit o solicitare nouă prin site-ul World Wide Bistro.",
        "",
        f"Nume: {record['full_name']}",
        f"E-mail: {record['email'] or '—'}",
        f"Telefon: {record['phone'] or '—'}",
        f"Tip solicitare: {record['request_type']}",
        f"Data: {record['event_date'] or '—'}",
        f"Ora: {record['event_time'] or '—'}",
        f"Număr de persoane: {record['guests'] if record['guests'] is not None else '—'}",
        "",
        "Mesaj:",
        record["message"] or "—",
        "",
        "Aceasta este o cerere, nu o rezervare confirmată.",
    ]
    message.set_content("\n".join(details))

    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException, ValueError) as error:
        print(f"Eroare la trimiterea notificării SMTP: {error}")
        return False


class BistroHandler(BaseHTTPRequestHandler):
    server_version = "WorldWideBistro/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {fmt % args}")

    def send_json(self, status: int, payload: dict, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Cerere invalidă.") from error
        if length < 1 or length > MAX_BODY_BYTES:
            raise ValueError("Cererea este goală sau prea mare.")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Datele trimise nu sunt valide.") from error
        if not isinstance(payload, dict):
            raise ValueError("Datele trimise nu sunt valide.")
        return payload

    def same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlsplit(origin).netloc.lower() == self.headers.get("Host", "").lower()

    def is_admin(self) -> bool:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie[SESSION_COOKIE].value
        except (KeyError, Exception):
            return False
        return valid_session(token)

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/api/admin/requests":
            if not self.is_admin():
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Autentificare necesară."})
                return
            with connect_db() as db:
                rows = db.execute("SELECT * FROM requests ORDER BY created_at DESC LIMIT 300").fetchall()
            self.send_json(HTTPStatus.OK, {"requests": [dict(row) for row in rows]})
            return

        if path == "/":
            path = "/index.html"
        elif path == "/admin":
            path = "/admin.html"
        target = (ROOT / path.lstrip("/")).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file() or target.name.startswith("."):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        relative_parts = target.relative_to(ROOT).parts
        if relative_parts[0] in {".git", "data", "__pycache__"} or target.suffix in {".py", ".pyc", ".sqlite3"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else None
        if content_type is None:
            import mimetypes
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        try:
            body = target.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {"/api/requests", "/api/admin/login", "/api/admin/logout"}:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Rută inexistentă."})
            return
        if not self.same_origin():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Origine nepermisă."})
            return

        if path == "/api/admin/login":
            if not ADMIN_PASSWORD:
                self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Configurează ADMIN_PASSWORD în fișierul .env."})
                return
            key = f"login:{self.client_address[0]}"
            if not check_rate_limit(key, 8, 15 * 60):
                self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Prea multe încercări. Încearcă din nou mai târziu."})
                return
            try:
                payload = self.read_json()
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            username = str(payload.get("username", ""))[:100]
            password = str(payload.get("password", ""))[:300]
            if not (hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD)):
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Numele de utilizator sau parola nu sunt corecte."})
                return
            secure = "; Secure" if os.environ.get("COOKIE_SECURE", "false").lower() == "true" else ""
            token = make_session(ADMIN_USERNAME)
            cookie = f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/api/admin; Max-Age={SESSION_SECONDS}{secure}"
            self.send_json(HTTPStatus.OK, {"success": True}, {"Set-Cookie": cookie})
            return

        if path == "/api/admin/logout":
            if not self.is_admin():
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Autentificare necesară."})
                return
            self.send_json(HTTPStatus.OK, {"success": True}, {"Set-Cookie": f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/api/admin; Max-Age=0"})
            return

        key = f"request:{self.client_address[0]}"
        if not check_rate_limit(key, 6, 15 * 60):
            self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Ai trimis mai multe cereri. Te rugăm să revii puțin mai târziu."})
            return
        try:
            payload = self.read_json()
            record = self.validate_request(payload)
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        # A filled honeypot is treated as accepted but is not stored or emailed.
        if str(payload.get("website", "")).strip():
            self.send_json(HTTPStatus.CREATED, {"success": True})
            return

        record["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with connect_db() as db:
                cursor = db.execute("""
                    INSERT INTO requests
                    (created_at, full_name, email, phone, request_type, event_date, event_time, guests, message)
                    VALUES (:created_at, :full_name, :email, :phone, :request_type, :event_date, :event_time, :guests, :message)
                """, record)
                record["id"] = cursor.lastrowid
                db.commit()
        except sqlite3.Error as error:
            print(f"Eroare la salvarea solicitării: {error}")
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Nu am putut salva solicitarea. Te rugăm să încerci din nou."})
            return

        email_sent = send_email_notification(record)
        try:
            with connect_db() as db:
                db.execute("UPDATE requests SET email_sent = ? WHERE id = ?", (int(email_sent), record["id"]))
                db.commit()
        except sqlite3.Error as error:
            print(f"Eroare la actualizarea stării e-mailului: {error}")

        self.send_json(HTTPStatus.CREATED, {
            "success": True,
            "message": (
                "Cererea a fost înregistrată. Este o solicitare, nu o rezervare confirmată."
                if email_sent else
                "Cererea a fost salvată, dar notificarea automată nu este activă. Pentru confirmare, sună-ne la 0230 520 462."
            ),
        })

    def validate_request(self, payload: dict) -> dict:
        def text(name: str, label: str, max_length: int, required: bool = False) -> str:
            value = payload.get(name, "")
            if not isinstance(value, str):
                raise ValueError(f"Câmpul {label} nu este valid.")
            value = value.strip()
            if required and not value:
                raise ValueError(f"Completează câmpul {label}.")
            if len(value) > max_length:
                raise ValueError(f"Câmpul {label} este prea lung.")
            return value

        full_name = text("fullName", "nume", 120, True)
        if payload.get("consent") != "on":
            raise ValueError("Bifează acordul pentru a putea trimite solicitarea.")
        email = text("email", "e-mail", 254)
        phone = text("phone", "telefon", 30)
        if not email and not phone:
            raise ValueError("Adaugă cel puțin o metodă de contact: telefon sau e-mail.")
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Adresa de e-mail nu pare validă.")
        if phone and (not re.fullmatch(r"[+0-9().\-\s]{7,30}", phone) or sum(char.isdigit() for char in phone) < 7):
            raise ValueError("Numărul de telefon nu pare valid.")

        request_type = text("requestType", "tipul solicitării", 50, True)
        if request_type not in ALLOWED_TYPES:
            raise ValueError("Alege un tip de solicitare din listă.")
        event_date = text("date", "data", 10)
        if event_date:
            try:
                date.fromisoformat(event_date)
            except ValueError as error:
                raise ValueError("Data nu este validă.") from error
        event_time = text("time", "ora", 5)
        if event_time and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", event_time):
            raise ValueError("Ora nu este validă.")
        guests_text = text("guests", "numărul de persoane", 4)
        guests = None
        if guests_text:
            try:
                guests = int(guests_text)
            except ValueError as error:
                raise ValueError("Numărul de persoane trebuie să fie un număr întreg.") from error
            if not 1 <= guests <= 1000:
                raise ValueError("Numărul de persoane trebuie să fie între 1 și 1000.")
        message = text("message", "mesaj", 2000)
        return {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "request_type": request_type,
            "event_date": event_date,
            "event_time": event_time,
            "guests": guests,
            "message": message,
        }

    def do_PATCH(self) -> None:
        if not self.same_origin():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Origine nepermisă."})
            return
        if not self.is_admin():
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Autentificare necesară."})
            return
        match = re.fullmatch(r"/api/admin/requests/(\d+)", urlsplit(self.path).path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Rută inexistentă."})
            return
        try:
            payload = self.read_json()
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        status = payload.get("status")
        if status not in ALLOWED_STATUSES:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Starea selectată nu este validă."})
            return
        with connect_db() as db:
            cursor = db.execute("UPDATE requests SET status = ? WHERE id = ?", (status, int(match.group(1))))
            db.commit()
        if cursor.rowcount == 0:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Solicitarea nu a fost găsită."})
            return
        self.send_json(HTTPStatus.OK, {"success": True})


def main() -> None:
    connect_db().close()
    host = os.environ.get("SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SERVER_PORT", "8000"))
    if not ADMIN_PASSWORD:
        print("Panoul admin este dezactivat până setezi ADMIN_PASSWORD în .env.")
    if not all(os.environ.get(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD")):
        print("Formularul salvează solicitările; notificările e-mail se activează după configurarea SMTP în .env.")
    server = ThreadingHTTPServer((host, port), BistroHandler)
    print(f"World Wide Bistro este disponibil la http://{host}:{port}")
    print(f"Panoul de administrare: http://{host}:{port}/admin")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer oprit.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
