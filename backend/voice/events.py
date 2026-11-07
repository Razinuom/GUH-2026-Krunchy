"""In-process pub/sub so the dashboard (English) updates while the voice agent talks (any language).

Voice tool calls publish events; the dashboard listens on GET /voice/events?family_id=... (Server-Sent Events).
Single-process only, which is fine for a hackathon demo (run uvicorn with one worker).
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import AsyncIterator

HEARTBEAT_SECS = 15


class EventBus:
    def __init__(self, history: int = 50):
        self._subs: dict[asyncio.Queue, str | None] = {}
        self.recent: deque[dict] = deque(maxlen=history)

    def publish(self, type_: str, family_id: str | None, data: dict) -> dict:
        event = {"type": type_, "family_id": family_id, "ts": time.time(), "data": data}
        self.recent.append(event)
        for q, fam in list(self._subs.items()):
            if fam is None or family_id is None or fam == family_id:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass
        return event

    async def stream(self, family_id: str | None) -> AsyncIterator[str]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[q] = family_id
        try:
            yield ": connected\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECS)
                    yield f"event: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            self._subs.pop(q, None)


bus = EventBus()
