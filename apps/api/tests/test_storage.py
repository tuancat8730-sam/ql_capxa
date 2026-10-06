"""S3Storage against a real S3 HTTP server (moto), so presigned URLs are exercised end to end."""

import hashlib
import os
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from moto.server import ThreadedMotoServer

from app.services.storage import MemoryStorage, S3Storage, content_disposition

BUCKET = "qlda-test"


@pytest.fixture(scope="module")
def s3_server() -> Iterator[str]:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    server = ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.stop()


@pytest.fixture
async def s3(s3_server: str) -> S3Storage:
    storage = S3Storage(
        bucket=BUCKET,
        region="ap-southeast-1",
        endpoint_url=s3_server,
        public_endpoint_url=s3_server,
        access_key="test",
        secret_key="test",
    )
    await storage.ensure_bucket()
    return storage


async def test_presigned_upload_head_and_chunked_read(s3: S3Storage) -> None:
    key = "projects/p/packages/1/doc/v1/bao-lanh.pdf"
    presigned = await s3.presign_upload(key, "application/pdf", 600)
    assert presigned.method == "PUT" and presigned.headers == {"Content-Type": "application/pdf"}
    payload = b"%PDF-1.4 " + os.urandom(3 * 1024 * 1024 + 17)
    async with httpx.AsyncClient() as client:
        resp = await client.put(presigned.url, content=payload, headers=presigned.headers)
    assert resp.status_code == 200
    info = await s3.head(key)
    assert info is not None and info.size == len(payload)
    digest = hashlib.sha256()
    async for chunk in s3.read_chunks(key):
        digest.update(chunk)
    assert digest.hexdigest() == hashlib.sha256(payload).hexdigest()


async def test_head_of_missing_object_is_none(s3: S3Storage) -> None:
    assert await s3.head("does/not/exist.pdf") is None


async def test_upload_signature_binds_the_content_type(s3: S3Storage) -> None:
    # moto does not verify signatures, so assert the signed header list: real S3 then refuses
    # an upload whose Content-Type differs from what was presigned.
    presigned = await s3.presign_upload("signed/type.pdf", "application/pdf", 600)
    query = parse_qs(urlparse(presigned.url).query)
    assert "content-type" in query["X-Amz-SignedHeaders"][0].split(";")
    assert query["X-Amz-Expires"] == ["600"]


async def test_presigned_download_sets_disposition_and_content(s3: S3Storage) -> None:
    key = "projects/p/dl/v1/hop-dong.pdf"
    up = await s3.presign_upload(key, "application/pdf", 600)
    async with httpx.AsyncClient() as client:
        await client.put(up.url, content=b"hello", headers=up.headers)
        inline = await client.get(
            await s3.presign_download(
                key, "Hợp đồng số 71.pdf", "application/pdf", 300, inline=True
            )
        )
        attach = await client.get(
            await s3.presign_download(
                key, "Hợp đồng số 71.pdf", "application/pdf", 300, inline=False
            )
        )
    assert inline.content == b"hello"
    assert inline.headers["content-disposition"].startswith("inline")
    assert attach.headers["content-disposition"].startswith("attachment")
    assert "UTF-8''H%E1%BB%A3p%20%C4%91%E1%BB%93ng" in attach.headers["content-disposition"]


async def test_fifty_megabyte_upload_via_presigned_url(s3: S3Storage) -> None:
    """SPEC M4 acceptance: a 50 MB file uploads and is read back intact."""
    key = "projects/p/big/v1/scan.zip"
    payload = os.urandom(50 * 1024 * 1024)
    up = await s3.presign_upload(key, "application/zip", 600)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.put(up.url, content=payload, headers=up.headers)
    assert resp.status_code == 200
    info = await s3.head(key)
    assert info is not None and info.size == 50 * 1024 * 1024
    digest = hashlib.sha256()
    async for chunk in s3.read_chunks(key):
        digest.update(chunk)
    assert digest.hexdigest() == hashlib.sha256(payload).hexdigest()


async def test_read_bytes_enforces_a_cap(s3: S3Storage) -> None:
    key = "projects/p/cap/v1/a.txt"
    up = await s3.presign_upload(key, "text/plain", 600)
    async with httpx.AsyncClient() as client:
        await client.put(up.url, content=b"x" * 2048, headers=up.headers)
    assert await s3.read_bytes(key, 4096) == b"x" * 2048
    with pytest.raises(ValueError):
        await s3.read_bytes(key, 1024)


def test_content_disposition_survives_vietnamese_and_quotes() -> None:
    header = content_disposition('Bảo lãnh "tạm ứng".pdf', inline=False)
    assert header.startswith('attachment; filename="')
    assert header.isascii()
    assert "filename*=UTF-8''" in header


async def test_memory_storage_mirrors_the_interface() -> None:
    mem = MemoryStorage()
    mem.put("k", b"abc")
    assert (await mem.head("k")).size == 3  # type: ignore[union-attr]
    assert await mem.head("nope") is None
    assert b"".join([c async for c in mem.read_chunks("k")]) == b"abc"
    assert await mem.read_bytes("k", 10) == b"abc"
    with pytest.raises(ValueError):
        await mem.read_bytes("k", 1)
    url = await mem.presign_download("k", "a.pdf", "application/pdf", 300, inline=True)
    assert url.startswith("memory://download/") and mem.downloads == [("k", "a.pdf", True)]
