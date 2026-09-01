from __future__ import annotations

import logging
import queue
import threading

from ..events import ProviderEvent
from ..models import ChatMessage


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
        self.events.put(ProviderEvent(kind="message", platform=self.platform, message=message))

    def emit_status(self, state: str, text: str) -> None:
        self.events.put(
            ProviderEvent(
                kind="status",
                platform=self.platform,
                state=state,
                text=text,
            )
        )

    def emit_delete(self, message_id: str) -> None:
        self.events.put(
            ProviderEvent(
                kind="delete",
                platform=self.platform,
                message_id=message_id,
            )
        )

    def emit_clear(self) -> None:
        self.events.put(ProviderEvent(kind="clear", platform=self.platform))
