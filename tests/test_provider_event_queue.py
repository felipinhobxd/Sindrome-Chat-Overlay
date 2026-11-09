from __future__ import annotations

import queue
import threading
import time
import unittest

from sindrome_overlay.events import ProviderEvent
from sindrome_overlay.models import ChatMessage
from sindrome_overlay.provider_event_queue import MAX_PENDING_EVENTS, ProviderEventQueue
from sindrome_overlay.providers.base import BaseProvider


def _message(number: int, platform: str = "twitch") -> ProviderEvent:
    return ProviderEvent(
        kind="message",
        platform=platform,
        message=ChatMessage(platform, "viewer", f"message {number}", message_id=str(number)),
    )


def _control(kind: str, number: int, platform: str = "twitch") -> ProviderEvent:
    if kind == "delete":
        return ProviderEvent(kind="delete", platform=platform, message_id=str(number))
    if kind == "delete_author":
        return ProviderEvent(kind="delete_author", platform=platform, author_id=str(number))
    if kind == "clear":
        return ProviderEvent(kind="clear", platform=platform)
    if kind == "status":
        return ProviderEvent(kind="status", platform=platform, state=f"state-{number}")
    raise AssertionError(kind)


class DummyProvider(BaseProvider):
    platform = "twitch"

    def run(self) -> None:
        pass


class ProviderEventQueueTests(unittest.TestCase):
    def test_bounded_chat_flood_evicts_oldest_messages(self) -> None:
        events = ProviderEventQueue(maxsize=3)
        for number in range(100):
            self.assertTrue(events.offer(_message(number)))
            self.assertLessEqual(events.qsize(), 3)
        self.assertEqual(events.dropped_messages, 97)
        self.assertEqual(
            [events.get_nowait().message.message_id for _ in range(3)],
            ["97", "98", "99"],
        )

    def test_full_queue_keeps_mod_actions_and_status_in_fifo_order(self) -> None:
        events = ProviderEventQueue(maxsize=5)
        for number in range(5):
            events.offer(_message(number))
        controls = [
            _control("delete", 10),
            _control("delete_author", 11),
            _control("clear", 12),
            _control("status", 13),
        ]
        for control in controls:
            self.assertTrue(events.offer(control))
            self.assertEqual(events.qsize(), 5)
        actual = [events.get_nowait() for _ in range(5)]
        self.assertEqual(actual[1:], controls)
        self.assertEqual(actual[0].message.message_id, "4")
        self.assertEqual(events.dropped_messages, 4)

    def test_messages_do_not_evict_a_queue_full_of_controls(self) -> None:
        events = ProviderEventQueue(maxsize=2)
        first = _control("delete", 1)
        second = _control("clear", 2)
        self.assertTrue(events.offer(first))
        self.assertTrue(events.offer(second))
        self.assertFalse(events.offer(_message(3)))
        self.assertEqual([events.get_nowait(), events.get_nowait()], [first, second])
        self.assertEqual(events.dropped_messages, 1)

    def test_control_waits_for_ui_instead_of_overwriting_another_control(self) -> None:
        events = ProviderEventQueue(maxsize=2)
        first = _control("delete", 1)
        second = _control("delete_author", 2)
        last = _control("clear", 3)
        events.offer(first)
        events.offer(second)
        done = threading.Event()
        result: list[bool] = []

        def send() -> None:
            result.append(events.offer(last))
            done.set()

        thread = threading.Thread(target=send)
        thread.start()
        try:
            self.assertFalse(done.wait(0.03))
            self.assertEqual(events.get_nowait(), first)
            self.assertTrue(done.wait(1))
            self.assertEqual(result, [True])
            self.assertEqual([events.get_nowait(), events.get_nowait()], [second, last])
        finally:
            events.close()
            thread.join(timeout=1)

    def test_close_wakes_a_blocked_provider_on_restart(self) -> None:
        events = ProviderEventQueue(maxsize=1)
        events.offer(_control("delete", 1))
        done = threading.Event()
        result: list[bool] = []

        def send() -> None:
            result.append(events.offer(_control("clear", 2)))
            done.set()

        thread = threading.Thread(target=send)
        thread.start()
        self.assertFalse(done.wait(0.03))
        events.close()
        self.assertTrue(done.wait(1))
        thread.join(timeout=1)
        self.assertEqual(result, [False])
        self.assertEqual(events.qsize(), 1)
        self.assertFalse(events.offer(_message(5)))

    def test_evictions_preserve_queue_task_accounting(self) -> None:
        events = ProviderEventQueue(maxsize=2)
        events.offer(_message(1))
        events.offer(_message(2))
        events.offer(_control("delete", 3))
        events.offer(_message(4))
        self.assertEqual(events.unfinished_tasks, 2)
        while not events.empty():
            events.get_nowait()
            events.task_done()
        events.join()
        self.assertEqual(events.unfinished_tasks, 0)

    def test_two_providers_concurrently_preserve_all_moderation_events(self) -> None:
        events = ProviderEventQueue(maxsize=64)
        done = threading.Event()
        errors: list[BaseException] = []
        expected: dict[str, list[ProviderEvent]] = {"twitch": [], "youtube": []}
        actual: dict[str, list[ProviderEvent]] = {"twitch": [], "youtube": []}

        providers = [DummyProvider(events), DummyProvider(events)]
        providers[1].platform = "youtube"

        def produce(provider: DummyProvider) -> None:
            try:
                for number in range(700):
                    provider.emit_message(
                        ChatMessage(provider.platform, "viewer", "hi", message_id=str(number))
                    )
                    if number % 14 == 0:
                        event = _control(
                            ("delete", "delete_author", "clear", "status")[
                                (number // 14) % 4
                            ],
                            number,
                            provider.platform,
                        )
                        expected[provider.platform].append(event)
                        provider._emit(event)
            except BaseException as exc:
                errors.append(exc)

        def consume() -> None:
            while not done.is_set() or not events.empty():
                try:
                    event = events.get(timeout=0.05)
                except queue.Empty:
                    continue
                if event.kind != "message":
                    actual[event.platform].append(event)
                events.task_done()

        reader = threading.Thread(target=consume)
        writers = [threading.Thread(target=produce, args=(p,)) for p in providers]
        reader.start()
        try:
            for writer in writers:
                writer.start()
            for writer in writers:
                writer.join(timeout=5)
            self.assertFalse(any(writer.is_alive() for writer in writers))
            done.set()
            reader.join(timeout=5)
            self.assertFalse(reader.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(actual, expected)
            self.assertLessEqual(events.qsize(), events.maxsize)
        finally:
            done.set()
            events.close()
            for writer in writers:
                writer.join(timeout=1)
            reader.join(timeout=1)

    def test_default_capacity_matches_desktop_backlog_limit(self) -> None:
        self.assertEqual(ProviderEventQueue().maxsize, MAX_PENDING_EVENTS)
        self.assertEqual(MAX_PENDING_EVENTS, 500)


if __name__ == "__main__":
    unittest.main()
