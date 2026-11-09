from __future__ import annotations

import queue
import threading

from .events import ProviderEvent

MAX_PENDING_EVENTS = 500


class ProviderEventQueue(queue.Queue[ProviderEvent]):
    """Bounded FIFO shared by both providers, with lossless control events.

    Chat messages are best-effort during overload: the oldest queued message is
    evicted to admit the newest event. Status, deletion, author bans and clears
    never evict each other. If the queue contains only control events, writers
    wait for the UI to drain it rather than losing a moderation action.

    All capacity checks and evictions are protected by queue.Queue's mutex.
    close() releases producers if a provider session is being replaced.
    """

    def __init__(self, maxsize: int = MAX_PENDING_EVENTS) -> None:
        if maxsize <= 0:
            raise ValueError("Provider event queues must have a positive capacity")
        super().__init__(maxsize=maxsize)
        self._closed = False
        self.dropped_messages = 0

    def offer(
        self, event: ProviderEvent, *, stop_event: threading.Event | None = None
    ) -> bool:
        """Enqueue a new event without discarding queued control events."""
        with self.not_full:
            while self._qsize() >= self.maxsize:
                if self._closed or (stop_event is not None and stop_event.is_set()):
                    return False

                # Evict only a message, never a moderation or status event.
                for index, pending in enumerate(self.queue):
                    if pending.kind == "message":
                        del self.queue[index]
                        self.unfinished_tasks -= 1
                        self.dropped_messages += 1
                        break
                else:
                    if event.kind == "message":
                        self.dropped_messages += 1
                        return False
                    # The UI normally drains 100 items every 60 ms. Waiting
                    # here preserves a full backlog of moderation events and
                    # keeps memory bounded if the UI is temporarily stalled.
                    self.not_full.wait(timeout=0.1)
                    continue
                break

            if self._closed or (stop_event is not None and stop_event.is_set()):
                return False
            self._put(event)
            self.unfinished_tasks += 1
            self.not_empty.notify()
            return True

    def close(self) -> None:
        """Reject new events and wake producers blocked behind control events."""
        with self.not_full:
            self._closed = True
            self.not_full.notify_all()
