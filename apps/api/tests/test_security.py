from datetime import timedelta

import pytest

from app.core.errors import AppError
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("abc12345!")
    assert h.startswith("$argon2")
    assert verify_password("abc12345!", h)
    assert not verify_password("wrong", h)


def test_verify_password_rejects_garbage_hash() -> None:
    assert not verify_password("x", "not-a-hash")


def test_needs_rehash_false_for_fresh_hash() -> None:
    assert not needs_rehash(hash_password("abc12345!"))


def test_access_token_roundtrip() -> None:
    tok = create_token("uid-1", "access", token_version=3)
    claims = decode_token(tok, "access")
    assert claims["sub"] == "uid-1"
    assert claims["tv"] == 3


def test_token_type_mismatch_rejected() -> None:
    tok = create_token("uid-1", "refresh", token_version=0)
    with pytest.raises(AppError) as e:
        decode_token(tok, "access")
    assert e.value.status == 401


def test_expired_token_rejected() -> None:
    tok = create_token("uid-1", "access", token_version=0, expires_in=timedelta(seconds=-1))
    with pytest.raises(AppError) as e:
        decode_token(tok, "access")
    assert e.value.status == 401


def test_tampered_token_rejected() -> None:
    tok = create_token("uid-1", "access", token_version=0)
    with pytest.raises(AppError):
        decode_token(tok[:-2] + "xx", "access")
