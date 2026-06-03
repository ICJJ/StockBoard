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
