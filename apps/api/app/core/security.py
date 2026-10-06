"""Password hashing (argon2) and JWT helpers."""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.errors import AppError

TokenType = Literal["access", "refresh"]
_ALGORITHM = "HS256"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_token(
    subject: str,
    token_type: TokenType,
    *,
    token_version: int,
    expires_in: timedelta | None = None,
) -> str:
    settings = get_settings()
    if expires_in is None:
        expires_in = (
            timedelta(minutes=settings.jwt_access_minutes)
            if token_type == "access"
            else timedelta(days=settings.jwt_refresh_days)
        )
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "typ": token_type,
        "tv": token_version,
        "iat": now,
        "exp": now + expires_in,
    }
    token: str = jwt.encode(claims, settings.jwt_secret, algorithm=_ALGORITHM)
    return token


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token, get_settings().jwt_secret, algorithms=[_ALGORITHM]
        )
    except JWTError as exc:
        raise AppError(401, "unauthorized", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn") from exc
    if claims.get("typ") != expected_type or "sub" not in claims:
        raise AppError(401, "unauthorized", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return claims


def generate_temporary_password(length: int = 14) -> str:
    """Random password guaranteed to contain a letter and a digit (passes strength policy)."""
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in pw) and any(c.isdigit() for c in pw):
            return pw
