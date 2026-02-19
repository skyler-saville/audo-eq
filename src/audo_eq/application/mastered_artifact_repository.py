"""Application port for persisting mastered artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class PersistenceMode(str, Enum):
    """Persistence execution mode."""

    IMMEDIATE = "immediate"
    DEFERRED = "deferred"


class PersistenceGuarantee(str, Enum):
    """Application-level persistence guarantees."""

    BEST_EFFORT = "best-effort"
    GUARANTEED = "guaranteed"


@dataclass(frozen=True, slots=True)
class PersistencePolicy:
    """Policy controlling persistence behavior independently of infrastructure."""

    mode: PersistenceMode = PersistenceMode.IMMEDIATE
    guarantee: PersistenceGuarantee = PersistenceGuarantee.BEST_EFFORT


@dataclass(frozen=True, slots=True)
class PersistedArtifact:
    """Result of an artifact persistence request."""

    status: str
    object_url: str | None = None
    destination: str | None = None


class MasteredArtifactRepository(Protocol):
    """Port implemented by infrastructure adapters for mastered-artifact persistence."""

    def persist(self, *, object_name: str, audio_bytes: bytes, content_type: str = "audio/wav") -> PersistedArtifact:
        """Persist mastered bytes and return persistence metadata."""


class ArtifactPersistenceError(RuntimeError):
    """Raised when application-level persistence guarantees cannot be met."""
