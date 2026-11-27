"""Thread-safe in-process event bus backing the server-sent events stream."""
from __future__ import annotations

import threading
from collections import deque
from typing import Any

from app.core.utils import iso, now


class EventBus:
    def __init__(self, capacity: int = 2000) -> None:
        self._events: deque[dict] = deque(maxlen=capacity)
        self._seq = 0
        self._lock = threading.Lock()

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> dict:
        with self._lock:
            self._seq += 1
            event = {"id": self._seq, "type": event_type, "ts": iso(now()), "data": data or {}}
            self._events.append(event)
            return event

    def since(self, last_id: int) -> list[dict]:
        with self._lock:
            if last_id >= self._seq:
                return []
            return [e for e in self._events if e["id"] > last_id]

    @property
    def last_id(self) -> int:
        with self._lock:
            return self._seq


bus = EventBus()
