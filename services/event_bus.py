"""
Simple Async Pub/Sub Event Bus

This module provides a lightweight publish/subscribe utility built on top of
asyncio queues. It allows background services to publish events and any number
of WebSocket handlers to subscribe and consume those events independently.
"""

import asyncio
from typing import Any, Dict, DefaultDict, Set
from collections import defaultdict

from core.logging import get_logger


class EventBus:
    """
    Async event bus with topic-based pub/sub.

    - Each subscriber gets its own asyncio.Queue and will not block publishers.
    - Unsubscribing is important to avoid queue leaks when clients disconnect.
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._topics: DefaultDict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._max_queue_size = max_queue_size
        self._lock = asyncio.Lock()
        self._logger = get_logger(__name__)

    async def subscribe(self, topic: str) -> asyncio.Queue:
        """
        Subscribe to a topic. Returns an asyncio.Queue for receiving events.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            self._topics[topic].add(queue)
        self._logger.debug(f"Subscriber added to topic '{topic}'. total={len(self._topics[topic])}")
        return queue

    async def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe a queue from a topic.
        """
        async with self._lock:
            if queue in self._topics.get(topic, set()):
                self._topics[topic].remove(queue)
                # Best-effort drain to allow GC
                try:
                    while not queue.empty():
                        queue.get_nowait()
                except Exception:
                    pass
        self._logger.debug(f"Subscriber removed from topic '{topic}'. total={len(self._topics[topic])}")

    async def publish(self, topic: str, event: Dict[str, Any]) -> None:
        """
        Publish an event to a topic. Drops events if subscriber queue is full.
        """
        subscribers = list(self._topics.get(topic, set()))
        if not subscribers:
            return

        for q in subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop event to avoid backpressure blocking
                self._logger.warning(f"Dropping event for topic '{topic}' due to full queue")


# Singleton event bus for the application
bus = EventBus()


