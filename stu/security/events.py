"""Bounded in-memory security event store."""

from __future__ import annotations

from collections import deque
from threading import Lock

from ..constants import SecurityDecision
from ..models import SecurityEvent


class SecurityEventStore:
    def __init__(self, retention: int):
        self._events: deque[SecurityEvent] = deque(maxlen=retention)
        self._lock = Lock()

    def record(self, event: SecurityEvent) -> None:
        with self._lock:
            self._events.append(event)

    def list(self, project_id: str | None = None, limit: int = 100) -> list[SecurityEvent]:
        with self._lock:
            events = list(self._events)

        if project_id:
            events = [event for event in events if event.project_id == project_id]

        events.sort(key=lambda event: event.timestamp, reverse=True)
        return events[:limit]

    def counts(self) -> dict[str, int]:
        with self._lock:
            total = len(self._events)
            deny_count = sum(1 for event in self._events if event.decision == SecurityDecision.DENY)
            review_count = sum(1 for event in self._events if event.decision == SecurityDecision.REVIEW)

        return {
            "total": total,
            "deny": deny_count,
            "review": review_count,
        }
