import json
import asyncio
from typing import AsyncGenerator, Dict, Set
from datetime import datetime
import structlog

logger = structlog.get_logger()


class EventEmitter:
    """
    In-process pub/sub for real-time WebSocket streaming.
    In production, back this with Redis pub/sub for multi-process scaling.
    """
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    async def emit(self, submission_id: str, event: dict):
        event["timestamp"] = datetime.utcnow().isoformat()
        queues = self._subscribers.get(submission_id, set())
        dead = set()
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.add(q)
        # Remove dead queues
        if dead:
            self._subscribers[submission_id] -= dead

    def subscribe(self, submission_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(submission_id, set()).add(q)
        return q

    def unsubscribe(self, submission_id: str, queue: asyncio.Queue):
        subs = self._subscribers.get(submission_id, set())
        subs.discard(queue)

    async def stream_events(
        self,
        submission_id: str,
        timeout: float = 30.0,
    ) -> AsyncGenerator[dict, None]:
        queue = self.subscribe(submission_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    yield event
                    if event.get("type") == "completed":
                        break
                except asyncio.TimeoutError:
                    yield {"type": "timeout", "submission_id": submission_id}
                    break
        finally:
            self.unsubscribe(submission_id, queue)
