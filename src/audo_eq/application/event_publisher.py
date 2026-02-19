"""Application-level event publishing contracts."""

from __future__ import annotations

from typing import Protocol

from audo_eq.domain.events import DomainEvent


class EventPublisher(Protocol):
    """Port for publishing domain events."""

    def publish(self, event: DomainEvent) -> None:
        """Publish a single event."""


class NullEventPublisher:
    """No-op publisher used when event streaming is disabled."""

    def publish(self, event: DomainEvent) -> None:  # noqa: ARG002
        return
