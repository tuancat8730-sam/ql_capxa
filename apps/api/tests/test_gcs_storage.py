"""GcsStorage: signed URLs are made with a real key, the rest runs on a fake client."""

from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import credentials as auth_credentials
from google.cloud import storage as gcs
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account

from app.core.config import Settings
from app.services import gcs_storage
from app.services.gcs_storage import GcsStorage
from app.services.storage import CHUNK_SIZE, S3Storage, build_storage, content_disposition

BUCKET = "qlda-dev-documents"
EMAIL = "api@qlda-dev.iam.gserviceaccount.com"


@pytest.fixture(scope="module")
def key_credentials() -> service_account.Credentials:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "client_email": EMAIL,
            "private_key": pem,
            "token_uri": "https://oauth2.googleapis.com/token",
            "project_id": "qlda-dev",
        }
    )


@pytest.fixture
def signed(key_credentials: service_account.Credentials) -> GcsStorage:
    client = gcs.Client(project="qlda-dev", credentials=key_credentials)
    return GcsStorage(bucket=BUCKET, client=client)


# --- signed URLs (offline, with a key) ---------------------------------------------------------


async def test_upload_url_is_a_v4_put_that_pins_the_content_type(signed: GcsStorage) -> None:
    key = "projects/p/packages/1/doc/v1/bảo-lãnh.pdf"
    presigned = await signed.presign_upload(key, "application/pdf", 600)
    url = urlparse(presigned.url)
    query = parse_qs(url.query)
    assert url.netloc == "storage.googleapis.com"
    assert unquote(url.path) == f"/{BUCKET}/{key}"
    assert query["X-Goog-Algorithm"] == ["GOOG4-RSA-SHA256"]
    assert query["X-Goog-Expires"] == ["600"]
    assert "content-type" in query["X-Goog-SignedHeaders"][0]
    assert presigned.method == "PUT" and presigned.headers == {"Content-Type": "application/pdf"}
    assert query["X-Goog-Credential"][0].startswith(EMAIL)
    assert len(query["X-Goog-Signature"][0]) > 100


async def test_download_url_carries_the_vietnamese_file_name_and_expiry(signed: GcsStorage) -> None:
    url = await signed.presign_download(
        "k/a.pdf", "Bảo lãnh tạm ứng.pdf", "application/pdf", 300, inline=False
    )
    query = parse_qs(urlparse(url).query)
    assert query["X-Goog-Expires"] == ["300"]
    assert query["response-content-type"] == ["application/pdf"]
    assert query["response-content-disposition"] == [
        content_disposition("Bảo lãnh tạm ứng.pdf", inline=False)
    ]
    inline = await signed.presign_download("k/a.pdf", "a.pdf", "application/pdf", 300, inline=True)
    assert "inline" in parse_qs(urlparse(inline).query)["response-content-disposition"][0]


# --- signing through IAM when there is no key (Cloud Run) --------------------------------------


class _TokenOnlyCredentials(auth_credentials.Credentials):
    """What Cloud Run gives: a token and the account e-mail, but no private key."""

    def __init__(self, email: str | None) -> None:
        super().__init__()
        self.token = "ya29.test-token"
        self.service_account_email = email
        self.refreshed = 0

    @property
    def valid(self) -> bool:  # type: ignore[override]
        return True

    def refresh(self, request: Any) -> None:  # pragma: no cover - valid is always true
        self.refreshed += 1


def _iam_storage(email: str | None, signer_email: str | None = None) -> GcsStorage:
    client = gcs.Client(project="qlda-dev", credentials=_TokenOnlyCredentials(email))
    return GcsStorage(bucket=BUCKET, signer_email=signer_email, client=client)


async def test_without_a_key_the_url_is_signed_through_iam(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_sign(self: Any, **kwargs: Any) -> str:
        seen.update(kwargs)
        return "https://storage.googleapis.com/signed"

    monkeypatch.setattr(gcs.Blob, "generate_signed_url", fake_sign)
    storage = _iam_storage("default", signer_email=EMAIL)
    await storage.presign_upload("k", "application/pdf", 600)
    assert seen["service_account_email"] == EMAIL  # the configured account wins over "default"
    assert seen["access_token"] == "ya29.test-token"
    assert seen["version"] == "v4" and seen["method"] == "PUT"


async def test_the_account_e_mail_comes_from_the_credentials_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        gcs.Blob, "generate_signed_url", lambda self, **kw: seen.update(kw) or "https://x"
    )
    await _iam_storage(EMAIL).presign_download("k", "a.pdf", "application/pdf", 300, inline=False)
    assert seen["service_account_email"] == EMAIL


async def test_without_any_signer_identity_it_fails_loudly() -> None:
    with pytest.raises(RuntimeError, match="GCS_SIGNER_EMAIL"):
        await _iam_storage("default").presign_upload("k", "application/pdf", 600)
    with pytest.raises(RuntimeError, match="GCS_SIGNER_EMAIL"):
        await _iam_storage(None).presign_upload("k", "application/pdf", 600)


# --- reading objects (fake client) -------------------------------------------------------------


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0
        self.closed = False

    def read(self, size: int) -> bytes:
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


class _Blob:
    def __init__(self, store: dict[str, bytes], key: str) -> None:
        self._store = store
        self._key = key
        self.size = len(store[key]) if key in store else None
        self.readers: list[_Reader] = []

    def open(self, mode: str, chunk_size: int) -> _Reader:
        assert mode == "rb" and chunk_size == CHUNK_SIZE
        if self._key not in self._store:
            raise NotFound("no such object")
        reader = _Reader(self._store[self._key])
        self.readers.append(reader)
        return reader


class _Bucket:
    def __init__(self, store: dict[str, bytes], exists: bool = True) -> None:
        self.store = store
        self._exists = exists
        self.blobs: list[_Blob] = []

    def exists(self) -> bool:
        return self._exists

    def blob(self, key: str) -> _Blob:
        blob = _Blob(self.store, key)
        self.blobs.append(blob)
        return blob

    def get_blob(self, key: str) -> _Blob | None:
        return _Blob(self.store, key) if key in self.store else None


class _Client:
    def __init__(self, bucket: _Bucket) -> None:
        self._bucket = bucket
        self._credentials = None

    def bucket(self, name: str) -> _Bucket:
        return self._bucket


@pytest.fixture
def fake() -> Iterator[tuple[GcsStorage, _Bucket]]:
    bucket = _Bucket({"a/b.pdf": b"%PDF-1.4 " + bytes(range(256)) * 12000})  # about 3 MB
    yield GcsStorage(bucket=BUCKET, client=_Client(bucket)), bucket  # type: ignore[arg-type]


async def test_head_returns_the_size_or_none(fake: tuple[GcsStorage, _Bucket]) -> None:
    storage, bucket = fake
    info = await storage.head("a/b.pdf")
    assert info is not None and info.size == len(bucket.store["a/b.pdf"])
    assert await storage.head("missing.pdf") is None


async def test_chunked_read_returns_every_byte_in_bounded_chunks(
    fake: tuple[GcsStorage, _Bucket],
) -> None:
    storage, bucket = fake
    chunks = [c async for c in storage.read_chunks("a/b.pdf")]
    assert b"".join(chunks) == bucket.store["a/b.pdf"]
    assert all(len(c) <= CHUNK_SIZE for c in chunks) and len(chunks) > 1
    assert bucket.blobs[-1].readers[0].closed  # the reader is released


async def test_reading_stops_early_and_still_closes_the_reader(
    fake: tuple[GcsStorage, _Bucket],
) -> None:
    storage, bucket = fake
    with pytest.raises(ValueError, match="larger"):
        await storage.read_bytes("a/b.pdf", 1000)
    assert bucket.blobs[-1].readers[0].closed
    assert len(await storage.read_bytes("a/b.pdf", 10_000_000)) == len(bucket.store["a/b.pdf"])


async def test_reading_a_missing_object_is_a_key_error_not_a_google_error(
    fake: tuple[GcsStorage, _Bucket],
) -> None:
    storage, _ = fake
    with pytest.raises(KeyError):
        _ = [c async for c in storage.read_chunks("nope")]


async def test_ensure_bucket_checks_but_never_creates() -> None:
    present = GcsStorage(bucket=BUCKET, client=_Client(_Bucket({})))  # type: ignore[arg-type]
    await present.ensure_bucket()
    absent = GcsStorage(bucket=BUCKET, client=_Client(_Bucket({}, exists=False)))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="does not exist"):
        await absent.ensure_bucket()


# --- choosing the backend ----------------------------------------------------------------------


def test_the_default_backend_is_s3_compatible() -> None:
    assert isinstance(build_storage(Settings(s3_bucket="b", _env_file=None)), S3Storage)  # type: ignore[call-arg]


def test_gcs_backend_gets_bucket_project_and_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Recorder:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

    monkeypatch.setattr(gcs_storage, "GcsStorage", Recorder)
    settings = Settings(  # type: ignore[call-arg]
        storage_backend="gcs",
        gcs_bucket="qlda-prod-documents",
        gcp_project="qlda-prod",
        gcs_signer_email=EMAIL,
        _env_file=None,
    )
    build_storage(settings)
    assert seen == {"bucket": "qlda-prod-documents", "project": "qlda-prod", "signer_email": EMAIL}


def test_gcs_bucket_falls_back_to_the_s3_bucket_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(gcs_storage, "GcsStorage", lambda **kw: seen.update(kw))
    build_storage(Settings(storage_backend="gcs", s3_bucket="named", _env_file=None))  # type: ignore[call-arg]
    assert seen["bucket"] == "named"
