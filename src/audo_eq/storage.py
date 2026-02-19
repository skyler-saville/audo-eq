"""S3-compatible object storage helpers backed by MinIO client."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from minio import Minio


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Runtime configuration for S3-compatible object storage."""

    enabled: bool
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool
    region: str | None


@lru_cache(maxsize=1)
def load_storage_config() -> StorageConfig:
    """Load storage configuration from environment."""

    return StorageConfig(
        enabled=os.getenv("AUDO_EQ_STORAGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        endpoint=os.getenv("AUDO_EQ_S3_ENDPOINT", "minio:9000"),
        access_key=os.getenv("AUDO_EQ_S3_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("AUDO_EQ_S3_SECRET_KEY", "minioadmin"),
        bucket=os.getenv("AUDO_EQ_S3_BUCKET", "audo-eq-mastered"),
        secure=os.getenv("AUDO_EQ_S3_SECURE", "false").lower() in {"1", "true", "yes", "on"},
        region=os.getenv("AUDO_EQ_S3_REGION"),
    )


class StorageWriteError(RuntimeError):
    """Backward-compatible storage write exception type."""


@lru_cache(maxsize=1)
def get_storage_client() -> Any:
    """Build and cache a MinIO client for object storage."""

    from minio import Minio

    config = load_storage_config()
    return Minio(
        endpoint=config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        secure=config.secure,
        region=config.region,
    )


def store_mastered_audio(*, object_name: str, audio_bytes: bytes, content_type: str = "audio/wav") -> str | None:
    """Store mastered audio in object storage when storage is enabled."""

    config = load_storage_config()
    if not config.enabled:
        return None

    try:
        client = get_storage_client()
        if not client.bucket_exists(config.bucket):
            client.make_bucket(config.bucket)

        client.put_object(
            bucket_name=config.bucket,
            object_name=object_name,
            data=_bytes_to_stream(audio_bytes),
            length=len(audio_bytes),
            content_type=content_type,
        )

        return client.presigned_get_object(
            bucket_name=config.bucket,
            object_name=object_name,
            expires=timedelta(hours=1),
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("Mastered audio storage failed; returning no URL.", exc_info=error)
        return None


def _bytes_to_stream(payload: bytes):
    from io import BytesIO

    return BytesIO(payload)
