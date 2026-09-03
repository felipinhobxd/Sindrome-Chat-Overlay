from __future__ import annotations

import logging
import queue
import threading

from ..events import ProviderEvent
from ..models import ChatMessage


_MAX_PENDING_EVENTS = 1_500


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

    def emit_clear(self) -> None:
        self._emit(ProviderEvent(kind="clear", platform=self.platform))

    def _emit(self, event: ProviderEvent) -> None:
        """Keep provider backlogs bounded if the UI cannot drain events fast enough."""
        try:
            while self.events.qsize() >= _MAX_PENDING_EVENTS:
                self.events.get_nowait()
            self.events.put_nowait(event)
        except queue.Empty:
            self.events.put_nowait(event)
        except queue.Full:
            # Also works if callers later replace the current unbounded queue with a bounded one.
            try:
                self.events.get_nowait()
                self.events.put_nowait(event)
            except (queue.Empty, queue.Full):
                self.log.warning("Dropping %s event because the UI event queue is full", event.kind)
