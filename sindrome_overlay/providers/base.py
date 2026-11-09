from __future__ import annotations

import logging
import queue
import threading

from ..events import ProviderEvent
from ..models import ChatMessage
from ..provider_event_queue import ProviderEventQueue


class BaseProvider(threading.Thread):
    platform = "unknown"

    def __init__(self, events: queue.Queue[ProviderEvent]) -> None:
        super().__init__(name=f"{self.platform}-chat", daemon=True)
        self.events = events
        self.stop_event = threading.Event()
        self.log = logging.getLogger(f"sindrome_overlay.{self.platform}")

    def stop(self) -> None:
        self.stop_event.set()

    def wait(self, seconds: float) -> bool:
        return self.stop_event.wait(seconds)

    def emit_message(self, message: ChatMessage) -> None:
        self._emit(ProviderEvent(kind="message", platform=self.platform, message=message))

    def emit_status(self, state: str, text: str, *, mode: str = "") -> None:
        self._emit(
            ProviderEvent(
                kind="status",
                platform=self.platform,
                state=state,
                text=text,
                mode=mode,
            )
        )

    def emit_delete(self, message_id: str) -> None:
        self._emit(
            ProviderEvent(
                kind="delete",
                platform=self.platform,
                message_id=message_id,
            )
        )

    def emit_delete_author(self, author_id: str) -> None:
        self._emit(
            ProviderEvent(
                kind="delete_author",
                platform=self.platform,
                author_id=author_id,
            )
        )

    def emit_clear(self) -> None:
        self._emit(ProviderEvent(kind="clear", platform=self.platform))

    def _emit(self, event: ProviderEvent) -> None:
        """Publish events without allowing chat floods to erase moderation."""
        if isinstance(self.events, ProviderEventQueue):
            accepted = self.events.offer(event, stop_event=self.stop_event)
            if not accepted and event.kind != "message" and not self.stop_event.is_set():
                self.log.warning("Could not enqueue %s event (queue closed)", event.kind)
            return

        # Compatibility with callers that provide a regular Queue. The desktop
        # overlay always supplies ProviderEventQueue for coordinated admission.
        try:
            self.events.put_nowait(event)
        except queue.Full:
            self.log.warning("Dropping %s event because the queue is full", event.kind)
