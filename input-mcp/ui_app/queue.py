"""In-memory request queue + per-id response routing.

HTTP worker threads enqueue a Request object and wait on its `event`. The Tk
dispatcher pulls requests, shows the dialog, then sets `response` and `event`
when the dialog dismisses. The worker wakes, returns the response.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Request:
    type: str
    prompt: str
    spec: dict[str, Any]
    timeout_sec: int
    origin: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    submitted_at: float = field(default_factory=time.time)
    event: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None


class RequestQueue:
    """Thread-safe FIFO of pending Requests with id-based lookup.

    All operations grab `self._lock`. Dispatcher polls `pop()`; HTTP server
    calls `submit()`; cancel goes through `cancel()`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[Request] = deque()
        self._by_id: dict[str, Request] = {}
        self._showing: Request | None = None

    def submit(self, req: Request) -> None:
        with self._lock:
            self._queue.append(req)
            self._by_id[req.request_id] = req

    def pop(self) -> Request | None:
        with self._lock:
            if not self._queue:
                return None
            req = self._queue.popleft()
            self._showing = req
            return req

    def mark_done(self, request_id: str) -> None:
        with self._lock:
            self._by_id.pop(request_id, None)
            if self._showing and self._showing.request_id == request_id:
                self._showing = None

    def cancel(self, request_id: str) -> Request | None:
        with self._lock:
            req = self._by_id.get(request_id)
            if not req:
                return None
            try:
                self._queue.remove(req)
            except ValueError:
                pass
            return req

    def cancel_all(self) -> list[Request]:
        with self._lock:
            cancelled = list(self._queue)
            self._queue.clear()
            if self._showing:
                cancelled.append(self._showing)
            return cancelled

    def pending_count(self) -> int:
        with self._lock:
            n = len(self._queue)
            if self._showing:
                n += 1
            return n

    def pending_ids(self) -> list[dict[str, Any]]:
        with self._lock:
            ids: list[dict[str, Any]] = []
            if self._showing:
                ids.append({
                    "request_id": self._showing.request_id,
                    "type": self._showing.type,
                    "origin": self._showing.origin,
                    "state": "showing",
                })
            for r in self._queue:
                ids.append({
                    "request_id": r.request_id,
                    "type": r.type,
                    "origin": r.origin,
                    "state": "queued",
                })
            return ids

    def showing_request_id(self) -> str | None:
        with self._lock:
            return self._showing.request_id if self._showing else None
