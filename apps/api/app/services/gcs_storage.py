"""Cloud Storage backend (production on Google Cloud): same `Storage` interface as S3.

Files never pass through the API: the browser PUTs and GETs V4 signed URLs directly. On Cloud Run
there is no private key to sign with, so the service account signs through the IAM `signBlob`
API (it needs `roles/iam.serviceAccountTokenCreator` on itself); with a key file (local use)
the signature is made offline.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import timedelta
from typing import Any

import google.auth
import google.cloud.storage as storage
from google.auth.transport.requests import Request as AuthRequest
from google.cloud.exceptions import NotFound

from app.services.storage import (
    CHUNK_SIZE,
    ObjectInfo,
    PresignedUpload,
    content_disposition,
)


class GcsStorage:
    def __init__(
        self,
        *,
        bucket: str,
        project: str | None = None,
        signer_email: str | None = None,
        client: storage.Client | None = None,
    ) -> None:
        self.bucket_name = bucket
        if client is None:
            credentials, default_project = google.auth.default()
            client = storage.Client(project=project or default_project, credentials=credentials)
        self._client = client
        self._bucket = client.bucket(bucket)
        self._signer_email = signer_email

    def _signing_kwargs(self) -> dict[str, Any]:
        """Extra arguments for `generate_signed_url` when the credentials hold no private key."""
        credentials = self._client._credentials  # noqa: SLF001 - the client keeps what it signs with
        if getattr(credentials, "signer", None) is not None:
            return {}  # key file: signed offline
        if not getattr(credentials, "valid", False):
            credentials.refresh(AuthRequest())
        email = self._signer_email or getattr(credentials, "service_account_email", None)
        if not email or email == "default":
            raise RuntimeError("GCS_SIGNER_EMAIL is needed to sign URLs without a key file")
        return {"service_account_email": email, "access_token": credentials.token}

    async def ensure_bucket(self) -> None:
        """The bucket is created by Terraform; here we only check it is reachable."""

        def _check() -> None:
            if not self._bucket.exists():
                raise RuntimeError(f"bucket {self.bucket_name} does not exist")

        await asyncio.to_thread(_check)

    async def presign_upload(self, key: str, content_type: str, expires_in: int) -> PresignedUpload:
        def _sign() -> str:
            return str(
                self._bucket.blob(key).generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expires_in),
                    method="PUT",
                    content_type=content_type,
                    **self._signing_kwargs(),
                )
            )

        url = await asyncio.to_thread(_sign)
        return PresignedUpload(url=url, headers={"Content-Type": content_type})

    async def presign_download(
        self, key: str, filename: str, content_type: str, expires_in: int, *, inline: bool
    ) -> str:
        def _sign() -> str:
            return str(
                self._bucket.blob(key).generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expires_in),
                    method="GET",
                    response_type=content_type,
                    response_disposition=content_disposition(filename, inline=inline),
                    **self._signing_kwargs(),
                )
            )

        return await asyncio.to_thread(_sign)

    async def head(self, key: str) -> ObjectInfo | None:
        def _head() -> ObjectInfo | None:
            blob = self._bucket.get_blob(key)
            return None if blob is None else ObjectInfo(size=int(blob.size or 0))

        return await asyncio.to_thread(_head)

    async def read_chunks(self, key: str) -> AsyncGenerator[bytes]:
        blob = self._bucket.blob(key)
        try:
            reader = await asyncio.to_thread(blob.open, "rb", chunk_size=CHUNK_SIZE)
        except NotFound as exc:  # callers never see Google types
            raise KeyError(key) from exc
        try:
            while True:
                chunk: bytes = await asyncio.to_thread(reader.read, CHUNK_SIZE)
                if not chunk:
                    return
                yield chunk
        finally:
            await asyncio.to_thread(reader.close)

    async def read_bytes(self, key: str, max_bytes: int) -> bytes:
        data = bytearray()
        # aclosing: stopping early must free the connection now, not at garbage collection
        async with aclosing(self.read_chunks(key)) as chunks:
            async for chunk in chunks:
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise ValueError("object larger than allowed")
        return bytes(data)
