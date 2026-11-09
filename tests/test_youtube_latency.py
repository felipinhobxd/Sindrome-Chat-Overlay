from __future__ import annotations

import queue
import unittest
from unittest.mock import Mock, patch

from sindrome_overlay.providers.youtube import (
    RateLimited,
    YouTubeBootstrap,
    YouTubeProvider,
    find_continuation,
)


def continuation(timeout):
    return [{"timedContinuationData": {"continuation": "next", "timeoutMs": timeout}}]


class YouTubeLatencyTests(unittest.TestCase):
    def test_zero_and_short_server_timeouts_are_not_replaced_by_two_seconds(self):
        for timeout in (0, 125, 750, 2375):
            with self.subTest(timeout=timeout):
                self.assertEqual(find_continuation(continuation(timeout)), ("next", timeout))
        for invalid in (None, "invalid", -1):
            with self.subTest(invalid=invalid):
                self.assertEqual(find_continuation(continuation(invalid)), ("next", 2000))

    def test_continuation_rejects_overflow_and_caps_excessive_waits(self):
        for timeout in (300_000, 10**18, "9" * 400):
            with self.subTest(timeout=str(timeout)[:30]):
                self.assertEqual(find_continuation(continuation(timeout)), ("next", 300_000))
        for timeout in (float("inf"), float("-inf")):
            with self.subTest(timeout=timeout):
                self.assertEqual(find_continuation(continuation(timeout)), ("next", 2_000))

    def test_official_polling_bounds_remote_intervals_and_recovers_from_overflow(self):
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        self.addCleanup(provider.stop)
        for supplied, expected in (
            (250, 0.25),
            (5_000, 5.0),
            (300_000, 300.0),
            (10**18, 300.0),
            (float("inf"), 5.0),
            (-5, 5.0),
        ):
            with self.subTest(interval=supplied):
                payload = {
                    "items": [],
                    "nextPageToken": "next",
                    "pollingIntervalMillis": supplied,
                }
                with (
                    patch.object(provider, "_get_json", return_value=payload),
                    patch.object(provider, "wait", return_value=True) as wait,
                ):
                    provider._run_official_polling("live-chat-id")
                wait.assert_called_once_with(expected)

    def _provider(self):
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk")
        self.addCleanup(provider.stop)
        bootstrap = YouTubeBootstrap(
            "abcdefghijk", "https://youtu.be/abcdefghijk", "first", "test-key",
            "WEB", "1", "test-version", {"client": {}},
        )
        bootstrap_patch = patch.object(provider, "_bootstrap_chat", return_value=bootstrap)
        bootstrap_patch.start()
        self.addCleanup(bootstrap_patch.stop)
        return provider

    def test_compatibility_delivers_before_waiting_and_resumes_without_duplicates(self):
        provider = self._provider()
        payload = {"continuationContents": {"liveChatContinuation": {
            "actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {
                "id": "one", "authorName": {"simpleText": "Viewer"},
                "message": {"runs": [{"text": "Hello"}]},
            }}}}],
            "continuations": continuation(250),
        }}}
        response = Mock(status_code=200)
        response.json.return_value = payload
        waits = []
        messages = []

        def wait(seconds):
            while not provider.events.empty():
                event = provider.events.get_nowait()
                if event.kind == "message":
                    messages.append(event.message.message_id)
            self.assertEqual(messages, ["one"])
            waits.append(seconds)
            return len(waits) == 2

        with patch.object(provider.session, "post", return_value=response) as post, \
                patch.object(provider, "wait", side_effect=wait):
            provider._run_innertube("abcdefghijk")
        self.assertEqual(waits, [0.25, 0.25])
        self.assertEqual([call.kwargs["json"]["continuation"] for call in post.call_args_list],
                         ["first", "next"])

    def test_innertube_author_ban_emits_scoped_moderation_event(self):
        provider = self._provider()
        actions = [
            {"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {
                "id": "bad-message",
                "authorExternalChannelId": "UC-bad",
                "authorName": {"simpleText": "Bad"},
                "message": {"runs": [{"text": "Remove me"}]},
            }}}},
            {"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {
                "id": "good-message",
                "authorExternalChannelId": "UC-good",
                "authorName": {"simpleText": "Good"},
                "message": {"runs": [{"text": "Keep me"}]},
            }}}},
            {"markChatItemsByAuthorAsDeletedAction": {
                "externalChannelId": "UC-bad",
            }},
            {"markChatItemAsDeletedAction": {"targetItemId": "one-message"}},
        ]
        response = Mock(status_code=200)
        response.json.return_value = {
            "continuationContents": {"liveChatContinuation": {
                "actions": actions,
                "continuations": continuation(500),
            }}
        }
        with (
            patch.object(provider.session, "post", return_value=response),
            patch.object(provider, "wait", return_value=True),
        ):
            provider._run_innertube("abcdefghijk")

        events = []
        while not provider.events.empty():
            event = provider.events.get_nowait()
            if event.kind != "status":
                events.append(event)
        self.assertEqual(
            [(event.kind, event.platform) for event in events],
            [
                ("message", "youtube"),
                ("message", "youtube"),
                ("delete", "youtube"),
                ("delete_author", "youtube"),
            ],
        )
        self.assertEqual([event.message.message_id for event in events[:2]],
                         ["bad-message", "good-message"])
        self.assertEqual(events[2].message_id, "one-message")
        self.assertEqual(events[3].author_id, "UC-bad")

    def test_zero_guard_and_long_server_intervals_are_respected(self):
        for timeout, expected in ((0, 0.1), (125, 0.125), (2375, 2.375), (5000, 5.0)):
            with self.subTest(timeout=timeout):
                provider = self._provider()
                response = Mock(status_code=200)
                response.json.return_value = {"continuationContents": {"liveChatContinuation": {
                    "actions": [], "continuations": continuation(timeout),
                }}}
                with patch.object(provider.session, "post", return_value=response), \
                        patch.object(provider, "wait", return_value=True) as wait:
                    provider._run_innertube("abcdefghijk")
                wait.assert_called_once_with(expected)

    def test_rate_limit_still_stops_fast_polling(self):
        provider = self._provider()
        with patch.object(provider.session, "post", return_value=Mock(status_code=429)) as post:
            with self.assertRaises(RateLimited):
                provider._run_innertube("abcdefghijk")
        self.assertEqual(post.call_count, 1)
