"""Application service for mastered artifact persistence workflows."""

from __future__ import annotations

from dataclasses import dataclass

from audo_eq.application.mastered_artifact_repository import (
    ArtifactPersistenceError,
    MasteredArtifactRepository,
    PersistenceGuarantee,
    PersistenceMode,
    PersistencePolicy,
    PersistedArtifact,
)


@dataclass(frozen=True, slots=True)
class PersistMasteredArtifact:
    """Apply persistence policy through a repository port."""

    repository: MasteredArtifactRepository

    def run(
        self,
        *,
        object_name: str,
        audio_bytes: bytes,
        content_type: str,
        policy: PersistencePolicy,
    ) -> PersistedArtifact:
        result = self.repository.persist(object_name=object_name, audio_bytes=audio_bytes, content_type=content_type)

        if policy.guarantee is PersistenceGuarantee.GUARANTEED:
            if policy.mode is PersistenceMode.IMMEDIATE and result.status != "stored":
                raise ArtifactPersistenceError("guaranteed persistence requires immediate durable storage")
            if policy.mode is PersistenceMode.DEFERRED and result.status not in {"deferred", "stored"}:
                raise ArtifactPersistenceError("guaranteed persistence requires deferred persistence handoff")

        return result
