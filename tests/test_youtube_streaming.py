from __future__ import annotations

import queue
import unittest
from unittest.mock import patch

import grpc

from sindrome_overlay.providers.youtube import (
    ApiKeyRejected,
    ChatDisabled,
    LiveChatEnded,
    StreamingTransportUnavailable,
    YouTubeProvider,
    official_message_from_stream,
)
from sindrome_overlay.youtube_grpc import stream_list_pb2


def _stream_item(message_id: str, text: str, author: str = "Viewer"):
    item = stream_list_pb2.LiveChatMessage(id=message_id)
    item.snippet.type = stream_list_pb2.LiveChatMessageSnippet.TEXT_MESSAGE_EVENT
    item.snippet.published_at = "2026-09-01T12:34:56Z"
    item.snippet.text_message_details.message_text = text
    item.author_details.channel_id = f"UC-{author}"
    item.author_details.display_name = author
    return item


class YouTubeStreamingParserTests(unittest.TestCase):
    def test_stream_message_preserves_identity_badges_and_unicode(self) -> None:
        item = _stream_item("stream-1", "Olá 😀", "Canal Unicode")
        item.author_details.is_chat_owner = True
        item.author_details.is_chat_moderator = True
        message = official_message_from_stream(item, "pt-BR")
        self.assertIsNotNone(message)
        self.assertEqual(message.message_id, "stream-1")
        self.assertEqual(message.author_id, "UC-Canal Unicode")
        self.assertEqual(message.text, "Olá 😀")
        self.assertEqual(message.badges, ("OWNER", "MOD"))

    def test_stream_super_chat_and_membership(self) -> None:
        paid = stream_list_pb2.LiveChatMessage(id="paid")
        paid.snippet.type = stream_list_pb2.LiveChatMessageSnippet.SUPER_CHAT_EVENT
        paid.snippet.super_chat_details.user_comment = "Great stream"
        paid.snippet.super_chat_details.amount_display_string = "R$ 10,00"
        paid.author_details.display_name = "Supporter"
        paid_message = official_message_from_stream(paid)
        self.assertEqual((paid_message.kind, paid_message.amount), ("paid", "R$ 10,00"))

        member = stream_list_pb2.LiveChatMessage(id="member")
        member.snippet.type = stream_list_pb2.LiveChatMessageSnippet.NEW_SPONSOR_EVENT
        member.author_details.display_name = "Member"
        member_message = official_message_from_stream(member, "en")
        self.assertEqual(member_message.kind, "membership")
        self.assertEqual(member_message.text, "Channel membership event")

    def test_generated_schema_round_trips_next_page_token_and_order(self) -> None:
        response = stream_list_pb2.LiveChatMessageListResponse(next_page_token="resume-token")
        response.items.extend([_stream_item("one", "First"), _stream_item("two", "Second")])
        decoded = stream_list_pb2.LiveChatMessageListResponse.FromString(
            response.SerializeToString()
        )
        self.assertEqual(decoded.next_page_token, "resume-token")
        self.assertEqual([item.id for item in decoded.items], ["one", "two"])


class YouTubeStreamingProviderTests(unittest.TestCase):
    def test_official_api_discovers_live_chat_id_from_video(self) -> None:
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        with patch.object(
            provider,
            "_get_json",
            return_value={
                "items": [
                    {
                        "liveStreamingDetails": {
                            "actualStartTime": "2026-09-01T12:00:00Z",
                            "activeLiveChatId": "live-chat-id",
                        }
                    }
                ]
            },
        ) as request:
            self.assertEqual(
                provider._official_live_chat_id_for_video("abcdefghijk"),
                "live-chat-id",
            )
        self.assertEqual(request.call_args.kwargs["params"]["part"], "liveStreamingDetails")
        self.assertEqual(request.call_args.kwargs["params"]["key"], "data-key")

    def test_started_video_without_live_chat_is_reported_as_disabled(self) -> None:
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        with patch.object(
            provider,
            "_get_json",
            return_value={
                "items": [
                    {"liveStreamingDetails": {"actualStartTime": "2026-09-01T12:00:00Z"}}
                ]
            },
        ):
            with self.assertRaises(ChatDisabled):
                provider._official_live_chat_id_for_video("abcdefghijk")

    def test_streaming_transport_failure_uses_polling_fallback(self) -> None:
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        with (
            patch.object(
                provider,
                "_official_live_chat_id_for_video",
                return_value="live-chat-id",
            ),
            patch.object(
                provider,
                "_run_official_stream",
                side_effect=StreamingTransportUnavailable("HTTP/2 unavailable"),
            ) as streaming,
            patch.object(provider, "_run_official_polling") as polling,
        ):
            provider._run_official_api("abcdefghijk")
        streaming.assert_called_once_with("abcdefghijk", "live-chat-id")
        polling.assert_called_once_with("live-chat-id")
        modes = []
        while not provider.events.empty():
            event = provider.events.get_nowait()
            if event.kind == "status":
                modes.append(event.mode)
        self.assertEqual(modes, ["official_stream", "official_polling"])

    def test_rejected_key_emits_structured_invalid_mode(self) -> None:
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "bad-key")
        with (
            patch.object(provider, "_resolve_video_id", return_value="abcdefghijk"),
            patch.object(provider, "_run_official_api", side_effect=ApiKeyRejected()),
            patch.object(provider, "wait", return_value=True),
        ):
            provider.run()
        statuses = []
        while not provider.events.empty():
            event = provider.events.get_nowait()
            if event.kind == "status":
                statuses.append((event.state, event.mode))
        self.assertIn(("connecting", "official_configured"), statuses)
        self.assertIn(("error", "invalid_key"), statuses)

    def test_stream_connection_attempts_are_bounded_before_fallback(self) -> None:
        channels = []
        waits: list[float] = []

        class FakeChannel:
            def close(self) -> None:
                return None

        class UnavailableFuture:
            def result(self, timeout: float) -> None:
                raise grpc.FutureTimeoutError()

        def channel_factory(*args, **kwargs):
            channel = FakeChannel()
            channels.append(channel)
            return channel

        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        with (
            patch(
                "sindrome_overlay.providers.youtube.grpc.secure_channel",
                side_effect=channel_factory,
            ),
            patch("sindrome_overlay.providers.youtube.grpc.ssl_channel_credentials"),
            patch(
                "sindrome_overlay.providers.youtube.grpc.channel_ready_future",
                return_value=UnavailableFuture(),
            ),
            patch.object(
                provider,
                "wait",
                side_effect=lambda seconds: waits.append(seconds) or False,
            ),
        ):
            with self.assertRaises(StreamingTransportUnavailable):
                provider._run_official_stream("abcdefghijk", "live-chat-id")
        self.assertEqual(len(channels), 3)
        self.assertEqual(waits, [2, 4])

    def test_ended_chat_causes_channel_url_to_be_resolved_again(self) -> None:
        provider = YouTubeProvider(queue.Queue(), "https://youtube.com/@channel/live", "key")

        def run_live(video_id: str) -> None:
            if video_id == "old-live-id":
                raise LiveChatEnded("ended")
            provider.stop_event.set()

        with (
            patch.object(
                provider,
                "_resolve_video_id",
                side_effect=["old-live-id", "new-live-id"],
            ) as resolve,
            patch.object(provider, "_run_official_api", side_effect=run_live),
            patch.object(provider, "wait", return_value=False),
        ):
            provider.run()
        self.assertEqual(resolve.call_count, 2)

    def test_chat_ended_event_stops_the_current_stream(self) -> None:
        response = stream_list_pb2.LiveChatMessageListResponse(next_page_token="last-token")
        ended = stream_list_pb2.LiveChatMessage(id="ended")
        ended.snippet.type = stream_list_pb2.LiveChatMessageSnippet.CHAT_ENDED_EVENT
        response.items.append(ended)

        class FakeChannel:
            def close(self) -> None:
                return None

        class ReadyFuture:
            def result(self, timeout: float) -> None:
                return None

        class FakeCall:
            def __iter__(self):
                return iter([response])

            def cancel(self) -> None:
                return None

        class FakeStub:
            def __init__(self, _channel) -> None:
                pass

            def StreamList(self, request, metadata):
                return FakeCall()

        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        with (
            patch(
                "sindrome_overlay.providers.youtube.grpc.secure_channel",
                return_value=FakeChannel(),
            ),
            patch("sindrome_overlay.providers.youtube.grpc.ssl_channel_credentials"),
            patch(
                "sindrome_overlay.providers.youtube.grpc.channel_ready_future",
                return_value=ReadyFuture(),
            ),
            patch(
                "sindrome_overlay.providers.youtube.stream_list_pb2_grpc."
                "V3DataLiveChatMessageServiceStub",
                FakeStub,
            ),
        ):
            with self.assertRaises(LiveChatEnded):
                provider._run_official_stream("abcdefghijk", "live-chat-id")

    def test_stream_reconnects_with_last_token_and_deduplicates(self) -> None:
        responses = []
        first = stream_list_pb2.LiveChatMessageListResponse(next_page_token="token-1")
        first.items.extend([_stream_item("one", "First"), _stream_item("duplicate", "Once")])
        second = stream_list_pb2.LiveChatMessageListResponse(next_page_token="token-2")
        second.items.extend([_stream_item("duplicate", "Once"), _stream_item("two", "Second")])
        responses.extend([[first], [second]])
        requested_tokens: list[str] = []

        class FakeChannel:
            def close(self) -> None:
                return None

        class ReadyFuture:
            def result(self, timeout: float) -> None:
                self.timeout = timeout

        class FakeCall:
            def __init__(self, values) -> None:
                self.values = values

            def __iter__(self):
                return iter(self.values)

            def cancel(self) -> None:
                return None

        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        original_emit_once = provider._emit_once

        def emit_and_stop(message) -> None:
            original_emit_once(message)
            if message.message_id == "two":
                provider.stop_event.set()

        provider._emit_once = emit_and_stop

        class FakeStub:
            def __init__(self, _channel) -> None:
                pass

            def StreamList(self, request, metadata):
                requested_tokens.append(request.page_token)
                self.metadata = metadata
                return FakeCall(responses.pop(0))

        with (
            patch(
                "sindrome_overlay.providers.youtube.grpc.secure_channel", return_value=FakeChannel()
            ),
            patch("sindrome_overlay.providers.youtube.grpc.ssl_channel_credentials"),
            patch(
                "sindrome_overlay.providers.youtube.grpc.channel_ready_future",
                return_value=ReadyFuture(),
            ),
            patch(
                "sindrome_overlay.providers.youtube.stream_list_pb2_grpc."
                "V3DataLiveChatMessageServiceStub",
                FakeStub,
            ),
            patch.object(provider, "wait", return_value=False),
        ):
            provider._run_official_stream("abcdefghijk", "live-chat-id")

        self.assertEqual(requested_tokens, ["", "token-1"])
        self.assertEqual(provider._official_page_token, "token-2")
        emitted = []
        while not provider.events.empty():
            emitted.append(provider.events.get_nowait().message.message_id)
        self.assertEqual(emitted, ["one", "duplicate", "two"])

    def test_polling_fallback_obeys_youtube_interval_exactly(self) -> None:
        provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk", "data-key")
        waits: list[float] = []
        payload = {
            "nextPageToken": "next",
            "pollingIntervalMillis": 2_375,
            "items": [],
        }

        def record_wait(seconds: float) -> bool:
            waits.append(seconds)
            return True

        with (
            patch.object(provider, "_get_json", return_value=payload),
            patch.object(provider, "wait", side_effect=record_wait),
        ):
            provider._run_official_polling("live-chat-id")

        self.assertEqual(waits, [2.375])
        self.assertEqual(provider._official_page_token, "next")


if __name__ == "__main__":
    unittest.main()
