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
