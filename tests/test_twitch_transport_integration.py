from __future__ import annotations

import queue
import ssl
import threading
import unittest
from unittest.mock import Mock, patch

from sindrome_overlay.providers.twitch import TwitchProvider


class FakeTLSSocket:
    def __init__(self, *chunks: str) -> None:
        self.chunks = [part.encode("utf-8") for part in chunks]
        self.sent: list[str] = []
        self.closed = False
        self.timeout: float | None = None

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def sendall(self, payload: bytes) -> None:
        self.sent.append(payload.decode("utf-8"))

    def recv(self, _size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""

    def close(self) -> None:
        self.closed = True


class TwitchTransportIntegrationTests(unittest.TestCase):
    def _listen_script(self, provider: TwitchProvider, socket: FakeTLSSocket) -> None:
        raw = Mock()
        context = Mock()
        context.wrap_socket.return_value = socket
        with (
            patch("sindrome_overlay.providers.twitch.socket.create_connection", return_value=raw),
            patch("sindrome_overlay.providers.twitch.ssl.create_default_context", return_value=context),
        ):
            with self.assertRaisesRegex(ConnectionError, "closed the connection"):
                provider._listen()
        context.wrap_socket.assert_called_once_with(
            raw, server_hostname="irc.chat.twitch.tv"
        )
        self.assertEqual(socket.timeout, 1.0)
        self.assertTrue(socket.closed)
        self.assertIsNone(provider._socket)

    def test_welcome_before_roomstate_loads_channel_emotes_and_emits_moderation(self) -> None:
        events: queue.Queue = queue.Queue()
        provider = TwitchProvider(events, "sindromegames", third_party_emotes=True)
        assert provider._third_party is not None
        socket = FakeTLSSocket(
            ":tmi.twitch.tv 001 justinfan12345 :Welcome\r\n",
            "@room-id=123456 :tmi.twitch.tv ROOMSTATE #sindromegames\r\n"
            "@room-id=123456;display-name=Ana;user-id=55;id=tw-1 "
            ":ana!ana@ana.tmi.twitch.tv PRIVMSG #sindromegames :Ola Kappa\r\n"
            "@target-msg-id=tw-1 :tmi.twitch.tv CLEARMSG #sindromegames :Ola Kappa\r\n"
            "PING :tmi.twitch.tv\r\n",
        )
        with patch.object(provider._third_party, "load") as load:
            self._listen_script(provider, socket)
            thread = provider._emote_loader_thread
            self.assertIsNotNone(thread)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            load.assert_called_once_with("123456")
        emitted = []
        while not events.empty():
            emitted.append(events.get_nowait())
        self.assertEqual([item.kind for item in emitted], [
            "status", "status", "message", "delete"
        ])
        self.assertEqual([item.state for item in emitted if item.kind == "status"], [
            "connecting", "connected"
        ])
        self.assertEqual(emitted[2].message.message_id, "tw-1")
        self.assertEqual(emitted[2].message.author_id, "55")
        self.assertEqual(emitted[3].message_id, "tw-1")
        self.assertIn("PONG :tmi.twitch.tv\r\n", socket.sent)
        self.assertIn("JOIN #sindromegames\r\n", socket.sent)

    def test_first_message_room_tag_starts_emotes_before_roomstate(self) -> None:
        events: queue.Queue = queue.Queue()
        provider = TwitchProvider(events, "sindromegames", third_party_emotes=True)
        assert provider._third_party is not None
        socket = FakeTLSSocket(
            ":tmi.twitch.tv 001 guest :Welcome\r\n"
            "@room-id=765;display-name=Viewer;user-id=8;id=first "
            ":viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #sindromegames :Hi\r\n"
            "@room-id=765 :tmi.twitch.tv ROOMSTATE #sindromegames\r\n"
        )
        with patch.object(provider._third_party, "load") as load:
            self._listen_script(provider, socket)
            thread = provider._emote_loader_thread
            self.assertIsNotNone(thread)
            thread.join(timeout=2)
            load.assert_called_once_with("765")
        self.assertEqual(
            [e.state for e in list(events.queue) if e.kind == "status"],
            ["connecting", "connected"],
        )

    def test_unidentified_room_does_not_start_global_only_catalog(self) -> None:
        events: queue.Queue = queue.Queue()
        provider = TwitchProvider(events, "sindromegames", third_party_emotes=True)
        assert provider._third_party is not None
        socket = FakeTLSSocket(":tmi.twitch.tv 001 guest :Welcome\r\n")
        with patch.object(provider._third_party, "load") as load:
            self._listen_script(provider, socket)
            provider._ensure_third_party_emotes("")
            provider._ensure_third_party_emotes("not-a-room-id")
            self.assertIsNone(provider._emote_loader_thread)
            load.assert_not_called()

    def test_reconnect_refreshes_channel_emotes_in_each_irc_session(self) -> None:
        events: queue.Queue = queue.Queue()
        provider = TwitchProvider(events, "sindromegames", third_party_emotes=True)
        assert provider._third_party is not None
        greeting = "@room-id=123 :tmi.twitch.tv ROOMSTATE #sindromegames\r\n"
        with patch.object(provider._third_party, "load") as load:
            self._listen_script(provider, FakeTLSSocket(greeting))
            first_thread = provider._emote_loader_thread
            self.assertIsNotNone(first_thread)
            first_thread.join(timeout=2)
            self.assertFalse(first_thread.is_alive())

            self._listen_script(provider, FakeTLSSocket(greeting))
            second_thread = provider._emote_loader_thread
            self.assertIsNotNone(second_thread)
            second_thread.join(timeout=2)
            self.assertFalse(second_thread.is_alive())
            self.assertEqual(load.call_count, 2)
            load.assert_any_call("123")

    def test_reconnect_queues_refresh_without_overlapping_downloads(self) -> None:
        events: queue.Queue = queue.Queue()
        provider = TwitchProvider(events, "sindromegames", third_party_emotes=True)
        assert provider._third_party is not None
        first_started = threading.Event()
        release_first = threading.Event()
        loaded_rooms: list[str] = []

        def slow_first_load(room_id: str) -> None:
            loaded_rooms.append(room_id)
            if len(loaded_rooms) == 1:
                first_started.set()
                release_first.wait(timeout=5)

        greeting = "@room-id=456 :tmi.twitch.tv ROOMSTATE #sindromegames\r\n"
        with patch.object(provider._third_party, "load", side_effect=slow_first_load):
            try:
                self._listen_script(provider, FakeTLSSocket(greeting))
                first_thread = provider._emote_loader_thread
                self.assertIsNotNone(first_thread)
                self.assertTrue(first_started.wait(timeout=2))

                # A second IRC session must schedule a refresh, but not launch
                # another network download while the first one is blocked.
                self._listen_script(provider, FakeTLSSocket(greeting))
                self.assertIs(provider._emote_loader_thread, first_thread)
                self.assertEqual(loaded_rooms, ["456"])
            finally:
                release_first.set()
            first_thread.join(timeout=3)
            self.assertFalse(first_thread.is_alive())
            self.assertEqual(loaded_rooms, ["456", "456"])

    def test_tls_handshake_failure_closes_raw_socket(self) -> None:
        provider = TwitchProvider(queue.Queue(), "sindromegames", third_party_emotes=False)
        raw = Mock()
        context = Mock()
        context.wrap_socket.side_effect = ssl.SSLError("negotiation failed")
        with (
            patch("sindrome_overlay.providers.twitch.socket.create_connection", return_value=raw),
            patch("sindrome_overlay.providers.twitch.ssl.create_default_context", return_value=context),
            self.assertRaises(ssl.SSLError),
        ):
            provider._listen()
        raw.close.assert_called_once()
        self.assertIsNone(provider._socket)

    def test_failed_initial_irc_greeting_closes_wrapped_socket(self) -> None:
        provider = TwitchProvider(queue.Queue(), "sindromegames", third_party_emotes=False)
        raw = Mock()
        wrapped = Mock()
        wrapped.sendall.side_effect = BrokenPipeError("socket closed during greeting")
        context = Mock()
        context.wrap_socket.return_value = wrapped
        with (
            patch("sindrome_overlay.providers.twitch.socket.create_connection", return_value=raw),
            patch("sindrome_overlay.providers.twitch.ssl.create_default_context", return_value=context),
            self.assertRaises(BrokenPipeError),
        ):
            provider._listen()
        wrapped.close.assert_called_once()
        raw.close.assert_called_once()
        self.assertIsNone(provider._socket)


if __name__ == "__main__":
    unittest.main()
