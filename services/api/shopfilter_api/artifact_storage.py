from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.error import MinioException, S3Error


class ArtifactStorageError(RuntimeError):
    """Raised when immutable artifact bytes cannot be stored or verified."""


@dataclass(frozen=True)
class StoredArtifact:
    uri: str
    sha256: str
    size_bytes: int


class ReadableStream(Protocol):
    def read(self, size: int = -1) -> bytes: ...


class ArtifactStorage(Protocol):
    def put_verified(
        self,
        source: Path,
        *,
        object_key: str,
        expected_sha256: str,
    ) -> StoredArtifact: ...


def content_addressed_run_key(
    *, organization_id: str, project_id: str, sha256: str
) -> str:
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("sha256 must be a lowercase hexadecimal digest")
    return f"organizations/{organization_id}/projects/{project_id}/runs/{sha256}.json"


def _stream_hash(stream: ReadableStream) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


class MinioArtifactStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        client: Minio | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def _verify_object(self, object_key: str, expected_sha256: str) -> StoredArtifact:
        response = self._client.get_object(self._bucket, object_key)
        try:
            actual_hash, size = _stream_hash(response)
        finally:
            response.close()
            response.release_conn()
        if actual_hash != expected_sha256:
            raise ArtifactStorageError(
                "Stored artifact SHA-256 does not match the local immutable artifact"
            )
        return StoredArtifact(
            uri=f"s3://{self._bucket}/{object_key}",
            sha256=actual_hash,
            size_bytes=size,
        )

    def put_verified(
        self,
        source: Path,
        *,
        object_key: str,
        expected_sha256: str,
    ) -> StoredArtifact:
        try:
            self._ensure_bucket()
            try:
                self._client.stat_object(self._bucket, object_key)
            except S3Error as exc:
                if exc.code not in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                    raise
                self._client.fput_object(
                    self._bucket,
                    object_key,
                    str(source),
                    content_type="application/json",
                    metadata={"sha256": expected_sha256},
                )
            return self._verify_object(object_key, expected_sha256)
        except ArtifactStorageError:
            raise
        except (OSError, MinioException) as exc:
            raise ArtifactStorageError("Unable to store evaluation artifact in MinIO") from exc
