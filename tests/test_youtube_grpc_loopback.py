from __future__ import annotations

import queue
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import grpc

from sindrome_overlay.providers.youtube import ApiKeyRejected, YouTubeProvider
from sindrome_overlay.youtube_grpc import stream_list_pb2, stream_list_pb2_grpc


def _item(message_id: str, text: str) -> stream_list_pb2.LiveChatMessage:
    item = stream_list_pb2.LiveChatMessage(id=message_id)
    item.snippet.type = stream_list_pb2.LiveChatMessageSnippet.TEXT_MESSAGE_EVENT
    item.snippet.published_at = "2026-11-09T12:00:00Z"
    item.snippet.text_message_details.message_text = text
    item.author_details.channel_id = "UC-integration"
    item.author_details.display_name = "Test viewer"
    return item


class LoopbackYouTubeService(
    stream_list_pb2_grpc.V3DataLiveChatMessageServiceServicer
):
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.tokens: list[str] = []
        self.keys: list[str] = []

    def StreamList(self, request, context):
        self.tokens.append(request.page_token)
        self.keys.append(dict(context.invocation_metadata()).get("x-goog-api-key", ""))
        if self.reject:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid API key")
        if request.page_token == "":
            response = stream_list_pb2.LiveChatMessageListResponse(next_page_token="token-1")
            response.items.extend([_item("yt-one", "Olá 😀"), _item("yt-dup", "Once")])
        elif request.page_token == "token-1":
            response = stream_list_pb2.LiveChatMessageListResponse(next_page_token="token-2")
            response.items.extend([_item("yt-dup", "Once"), _item("yt-two", "Last")])
        else:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Unexpected page token")
        yield response


class YouTubeGrpcLoopbackTests(unittest.TestCase):
    def _start_service(self, service: LoopbackYouTubeService):
        server = grpc.server(ThreadPoolExecutor(max_workers=2))
        stream_list_pb2_grpc.add_V3DataLiveChatMessageServiceServicer_to_server(
            service, server
        )
        port = server.add_insecure_port("127.0.0.1:0")
        self.assertGreater(port, 0)
        server.start()
        return server, port

    def test_real_grpc_roundtrip_recovers_page_token_without_duplicate_messages(self) -> None:
        service = LoopbackYouTubeService()
        server, port = self._start_service(service)
        events: queue.Queue = queue.Queue()
        provider = YouTubeProvider(
            events, "https://youtu.be/abcdefghijk", "fake-development-key"
        )
        emit_once = provider._emit_once

        def capture_and_stop(message) -> None:
            emit_once(message)
            if message.message_id == "yt-two":
                provider.stop_event.set()

        provider._emit_once = capture_and_stop
        try:
            with (
                patch.object(
                    provider,
                    "_open_stream_channel",
                    side_effect=lambda: grpc.insecure_channel(f"127.0.0.1:{port}"),
                ),
                patch.object(provider, "wait", return_value=False),
            ):
                provider._run_official_stream("abcdefghijk", "live-chat-test")
        finally:
            server.stop(0).wait(timeout=3)

        self.assertEqual(service.tokens, ["", "token-1"])
        self.assertEqual(service.keys, ["fake-development-key", "fake-development-key"])
        self.assertEqual(provider._official_page_token, "token-2")
        messages = []
        while not events.empty():
            event = events.get_nowait()
            self.assertEqual(event.kind, "message")
            messages.append(event.message)
        self.assertEqual([m.message_id for m in messages], ["yt-one", "yt-dup", "yt-two"])
        self.assertEqual(messages[0].text, "Olá 😀")
        self.assertIsNone(provider._grpc_channel)

    def test_real_grpc_permission_denied_maps_to_invalid_api_key(self) -> None:
        service = LoopbackYouTubeService(reject=True)
        server, port = self._start_service(service)
        provider = YouTubeProvider(
            queue.Queue(), "https://youtu.be/abcdefghijk", "fake-rejected-key"
        )
        try:
            with (
                patch.object(
                    provider,
                    "_open_stream_channel",
                    side_effect=lambda: grpc.insecure_channel(f"127.0.0.1:{port}"),
                ),
                self.assertRaises(ApiKeyRejected),
            ):
                provider._run_official_stream("abcdefghijk", "live-chat-test")
        finally:
            server.stop(0).wait(timeout=3)
        self.assertEqual(service.tokens, [""])
        self.assertIsNone(provider._grpc_channel)


if __name__ == "__main__":
    unittest.main()
