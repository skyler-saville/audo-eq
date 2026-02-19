"""Infrastructure adapters for mastered artifact persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from audo_eq.application.mastered_artifact_repository import MasteredArtifactRepository, PersistedArtifact
from audo_eq.storage import store_mastered_audio

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MinIOMasteredArtifactRepository(MasteredArtifactRepository):
    """Adapter that persists mastered artifacts to S3-compatible object storage."""

    def persist(self, *, object_name: str, audio_bytes: bytes, content_type: str = "audio/wav") -> PersistedArtifact:
        object_url = store_mastered_audio(object_name=object_name, audio_bytes=audio_bytes, content_type=content_type)
        if object_url:
            return PersistedArtifact(status="stored", object_url=object_url, destination=object_url)
        return PersistedArtifact(status="skipped")


@dataclass(frozen=True, slots=True)
class DeferredMasteredArtifactRepository(MasteredArtifactRepository):
    """Adapter that enqueues persistence work and returns immediately."""

    queue_name: str = "mastered-artifacts"

    def persist(self, *, object_name: str, audio_bytes: bytes, content_type: str = "audio/wav") -> PersistedArtifact:
        # Placeholder queue adapter: in production this would push to SQS/Kafka/Rabbit/etc.
        logger.info(
            "Queued mastered artifact persistence task",
            extra={
                "queue_name": self.queue_name,
                "object_name": object_name,
                "content_type": content_type,
                "payload_size": len(audio_bytes),
            },
        )
        return PersistedArtifact(status="deferred", destination=f"queue://{self.queue_name}/{object_name}")
