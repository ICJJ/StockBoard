"""Auth primitives: password hashing, signed-cookie sessions, user store."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


import base64
import hashlib
import hmac
import os


def _secret() -> bytes:
    return os.environ.get("SESSION_SECRET", "").encode()


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
