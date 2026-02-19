"""Domain event contracts for mastering workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base domain event emitted by application services."""

    correlation_id: str
    payload_summary: dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass(frozen=True, slots=True)
class IngestValidated(DomainEvent):
    """Input assets were validated and accepted for mastering."""


@dataclass(frozen=True, slots=True)
class TrackAnalyzed(DomainEvent):
    """Target/reference tracks were analyzed for mastering metrics."""


@dataclass(frozen=True, slots=True)
class MasteringDecided(DomainEvent):
    """Mastering decision payload was computed from analysis metrics."""


@dataclass(frozen=True, slots=True)
class MasteringRendered(DomainEvent):
    """Mastered audio was rendered (not persisted) for the request."""


@dataclass(frozen=True, slots=True)
class ArtifactStored(DomainEvent):
    """A rendered mastering artifact was persisted to storage."""


@dataclass(frozen=True, slots=True)
class MasteringFailed(DomainEvent):
    """Pipeline execution failed for a correlation id."""
