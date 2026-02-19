"""Simple logging-backed implementation of the event publisher."""

from __future__ import annotations

import logging

from audo_eq.domain.events import DomainEvent

LOGGER = logging.getLogger("audo_eq.events")


class LoggingEventPublisher:
    """Emit event payload summaries to structured logs."""

    def publish(self, event: DomainEvent) -> None:
        LOGGER.info(
            "domain_event_emitted",
            extra={
                "event_name": type(event).__name__,
                "correlation_id": event.correlation_id,
                "payload_summary": event.payload_summary,
                "occurred_at": event.occurred_at.isoformat(),
            },
        )
