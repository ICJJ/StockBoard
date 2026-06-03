"""Auth primitives: password hashing, signed-cookie sessions, user store."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from . import quiz_db

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _secret() -> bytes:
    s = os.environ.get("SESSION_SECRET", "")
    if not s:
        raise RuntimeError("SESSION_SECRET environment variable must be set")
    return s.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_session(username: str) -> str:
    payload = _b64(username.encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_session(token: str) -> str | None:
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return _unb64(payload).decode()
    except Exception:
        return None


def create_user(username: str, password: str, is_admin: bool = False) -> None:
    con = quiz_db.connect()
    try:
        con.execute(
            "INSERT INTO users(username, password_hash, is_admin) VALUES (?,?,?)",
            (username, hash_password(password), 1 if is_admin else 0),
        )
        con.commit()
    finally:
        con.close()


def get_user(username: str):
    con = quiz_db.connect()
    try:
        row = con.execute(
            "SELECT id, username, is_admin, disabled, created_at FROM users WHERE username=?",
            (username,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def check_login(username: str, password: str) -> bool:
    con = quiz_db.connect()
    try:
        row = con.execute(
            "SELECT password_hash, disabled FROM users WHERE username=?", (username,)).fetchone()
    finally:
        con.close()
    if not row or row["disabled"]:
        return False
    return verify_password(row["password_hash"], password)


def set_disabled(username: str, disabled: bool) -> None:
    con = quiz_db.connect()
    try:
        con.execute("UPDATE users SET disabled=? WHERE username=?", (1 if disabled else 0, username))
        con.commit()
    finally:
        con.close()


def set_password(username: str, password: str) -> None:
    con = quiz_db.connect()
    try:
        con.execute("UPDATE users SET password_hash=? WHERE username=?",
                    (hash_password(password), username))
        con.commit()
    finally:
        con.close()


def list_users() -> list[dict]:
    con = quiz_db.connect()
    try:
        return [dict(r) for r in con.execute(
            "SELECT username, is_admin, disabled, created_at FROM users ORDER BY username")]
    finally:
        con.close()
