"""Two-person auth: a password for the web app, a bearer token for iOS Shortcuts.

Deliberately small. This is a household archive behind your own network or
tunnel, not a multi-tenant SaaS — but passwords are still salted+hashed and
sessions are HMAC-signed so a stolen cookie can't be forged or extended.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request

from . import db
from .config import settings

SESSION_COOKIE = "docbox_session"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


# ------------------------------------------------------------------ passwords


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), digest_hex)


# ------------------------------------------------------------------- sessions


def _sign(payload: str) -> str:
    return hmac.new(
        settings.resolve_secret().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def make_session(user_id: int) -> str:
    expires = int(time.time()) + settings.session_days * 86400
    payload = f"{user_id}:{expires}"
    return f"{base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')}.{_sign(payload)}"


def read_session(token: str) -> int | None:
    try:
        encoded, signature = token.split(".", 1)
        padding = "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(encoded + padding).decode()
        user_id_raw, expires_raw = payload.split(":")
    except (ValueError, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    if int(expires_raw) < time.time():
        return None
    return int(user_id_raw)


# ---------------------------------------------------------------------- users


def create_user(username: str, password: str) -> dict:
    username = username.strip().lower()
    if not username or len(password) < 6:
        raise ValueError("username required, password must be at least 6 characters")
    if db.query_one("SELECT id FROM users WHERE username = ?", (username,)):
        raise ValueError(f"user {username!r} already exists")
    token = secrets.token_urlsafe(32)
    user_id = db.insert("users", {
        "username": username,
        "password_hash": hash_password(password),
        "api_token": token,
        "created_at": time.time(),
    })
    return {"id": user_id, "username": username, "api_token": token}


def set_password(username: str, password: str) -> None:
    row = db.query_one("SELECT id FROM users WHERE username = ?", (username.strip().lower(),))
    if not row:
        raise ValueError("no such user")
    db.update("users", int(row["id"]), {"password_hash": hash_password(password)})


def rotate_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.update("users", user_id, {"api_token": token})
    return token


def authenticate(username: str, password: str) -> dict | None:
    row = db.query_one("SELECT * FROM users WHERE username = ?", (username.strip().lower(),))
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return {"id": int(row["id"]), "username": row["username"], "api_token": row["api_token"]}


def user_count() -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM users")
    return int(row["n"]) if row else 0


# ------------------------------------------------------------- request access


def current_user(request: Request) -> dict | None:
    """Session cookie, `Authorization: Bearer <token>`, or `?token=` for Shortcuts."""
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        user_id = read_session(cookie)
        if user_id:
            row = db.query_one("SELECT id, username FROM users WHERE id = ?", (user_id,))
            if row:
                return {"id": int(row["id"]), "username": row["username"]}

    token = ""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    token = token or request.headers.get("x-docbox-token", "").strip()
    token = token or (request.query_params.get("token") or "").strip()
    if token:
        row = db.query_one("SELECT id, username FROM users WHERE api_token = ?", (token,))
        if row:
            return {"id": int(row["id"]), "username": row["username"]}
    return None


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="authentication required")
    return user
