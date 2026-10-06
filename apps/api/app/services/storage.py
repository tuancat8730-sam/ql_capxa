"""Object storage behind a small interface: real S3/MinIO in production, memory in tests.

Files never pass through the API: clients PUT/GET presigned URLs directly (SPEC section 9).
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings

CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectInfo:
    size: int


class Storage(Protocol):
    async def ensure_bucket(self) -> None: ...

    async def presign_upload(
        self, key: str, content_type: str, expires_in: int
    ) -> PresignedUpload: ...

    async def presign_download(
        self, key: str, filename: str, content_type: str, expires_in: int, *, inline: bool
    ) -> str: ...

    async def head(self, key: str) -> ObjectInfo | None: ...

    def read_chunks(self, key: str) -> AsyncIterator[bytes]: ...

    async def read_bytes(self, key: str, max_bytes: int) -> bytes: ...


def content_disposition(filename: str, *, inline: bool) -> str:
    """RFC 6266 header that survives Vietnamese file names."""
    kind = "inline" if inline else "attachment"
    ascii_name = filename.encode("ascii", "ignore").decode() or "file"
    ascii_name = ascii_name.replace('"', "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


class S3Storage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        public_endpoint_url: str | None,
        access_key: str | None,
        secret_key: str | None,
    ) -> None:
        self.bucket = bucket
        config = Config(signature_version="s3v4", s3={"addressing_style": "path"})
        common: dict[str, Any] = {
            "region_name": region,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": config,
        }
        self._client: BaseClient = boto3.client("s3", endpoint_url=endpoint_url, **common)
        # Presigning is offline: use the address the *browser* can reach (MinIO sits behind
        # `minio:9000` inside Docker but `localhost:9000` outside).
        self._signer: BaseClient = boto3.client(
            "s3", endpoint_url=public_endpoint_url or endpoint_url, **common
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3Storage":
        return cls(
            bucket=settings.s3_bucket,
            region=settings.aws_region,
            endpoint_url=settings.s3_endpoint_url,
            public_endpoint_url=settings.s3_public_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )

    async def ensure_bucket(self) -> None:
        def _ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self.bucket)
            except ClientError:
                # Outside us-east-1 S3 insists on an explicit location constraint.
                region = self._client.meta.region_name
                if region == "us-east-1":
                    self._client.create_bucket(Bucket=self.bucket)
                else:
                    self._client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={"LocationConstraint": region},
                    )

        await asyncio.to_thread(_ensure)

    async def presign_upload(self, key: str, content_type: str, expires_in: int) -> PresignedUpload:
        url = await asyncio.to_thread(
            self._signer.generate_presigned_url,
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
        return PresignedUpload(url=url, headers={"Content-Type": content_type})

    async def presign_download(
        self, key: str, filename: str, content_type: str, expires_in: int, *, inline: bool
    ) -> str:
        url: str = await asyncio.to_thread(
            self._signer.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": content_disposition(filename, inline=inline),
            },
            ExpiresIn=expires_in,
        )
        return url

    async def head(self, key: str) -> ObjectInfo | None:
        def _head() -> ObjectInfo | None:
            try:
                meta = self._client.head_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise
            return ObjectInfo(size=int(meta["ContentLength"]))

        return await asyncio.to_thread(_head)

    async def read_chunks(self, key: str) -> AsyncIterator[bytes]:
        body = await asyncio.to_thread(
            lambda: self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
        )
        chunks: Iterator[bytes] = body.iter_chunks(CHUNK_SIZE)
        try:
            while True:
                chunk = await asyncio.to_thread(next, chunks, None)
                if chunk is None:
                    return
                yield chunk
        finally:
            body.close()

    async def read_bytes(self, key: str, max_bytes: int) -> bytes:
        data = bytearray()
        async for chunk in self.read_chunks(key):
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError("object larger than allowed")
        return bytes(data)


class MemoryStorage:
    """In-process stand-in used by tests; `put` simulates the browser's direct upload."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.downloads: list[tuple[str, str, bool]] = []

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def ensure_bucket(self) -> None:
        return None

    async def presign_upload(self, key: str, content_type: str, expires_in: int) -> PresignedUpload:
        return PresignedUpload(
            url=f"memory://upload/{quote(key)}?expires={expires_in}",
            headers={"Content-Type": content_type},
        )

    async def presign_download(
        self, key: str, filename: str, content_type: str, expires_in: int, *, inline: bool
    ) -> str:
        self.downloads.append((key, filename, inline))
        return f"memory://download/{quote(key)}?expires={expires_in}"

    async def head(self, key: str) -> ObjectInfo | None:
        data = self.objects.get(key)
        return None if data is None else ObjectInfo(size=len(data))

    async def read_chunks(self, key: str) -> AsyncIterator[bytes]:
        data = self.objects[key]
        for start in range(0, len(data), CHUNK_SIZE):
            yield data[start : start + CHUNK_SIZE]

    async def read_bytes(self, key: str, max_bytes: int) -> bytes:
        data = self.objects[key]
        if len(data) > max_bytes:
            raise ValueError("object larger than allowed")
        return data
