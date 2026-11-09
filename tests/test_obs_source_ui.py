from __future__ import annotations

import logging
import socket
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "OBS desktop integration is validated on Windows CI")
class ObsSourceUiTests(unittest.TestCase):
    def test_settings_dialog_exposes_obs_browser_source_controls(self) -> None:
        from PySide6.QtWidgets import QApplication, QTabWidget

        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.feature_settings_dialog import SettingsDialog

        app = QApplication.instance() or QApplication([])
        current = Settings(
            language="pt-BR",
            obs_enabled=True,
            obs_port=9876,
            obs_max_messages=120,
            obs_font_size=21,
            obs_show_platform_labels=True,
            obs_show_badges=True,
            obs_show_timestamps=False,
            obs_message_background_opacity=66,
        )
        dialog = SettingsDialog(
            current,
            youtube_connection_mode="compatibility",
            obs_source_url="http://127.0.0.1:9876/obs-chat",
        )
        dialog.show()
        app.processEvents()

        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        titles = [tabs.tabText(index) for index in range(tabs.count())]
        self.assertIn("Fonte OBS", titles)
        self.assertEqual(dialog.obs_url.text(), "http://127.0.0.1:9876/obs-chat")

        dialog.obs_copy_button.click()
        app.processEvents()
        self.assertEqual(
            QApplication.clipboard().text(),
            "http://127.0.0.1:9876/obs-chat",
        )

        dialog.obs_max_messages.setValue(200)
        dialog.obs_font_size.setValue(24)
        dialog.obs_background.setValue(45)
        saved = dialog.settings()
        self.assertTrue(saved.obs_enabled)
        self.assertEqual(saved.obs_port, 9876)
        self.assertEqual(saved.obs_max_messages, 200)
        self.assertEqual(saved.obs_font_size, 24)
        self.assertEqual(saved.obs_message_background_opacity, 45)
        dialog.close()

    def test_mixed_provider_events_reach_real_obs_http_and_moderation(self) -> None:
        import json
        from unittest.mock import patch
        from urllib.request import urlopen

        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.events import ProviderEvent
        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.obs_source import ObsChatSourceServer
        from sindrome_overlay.provider_event_queue import ProviderEventQueue
        from sindrome_overlay.providers.twitch import TwitchProvider, parse_twitch_line
        from sindrome_overlay.providers.youtube import YouTubeProvider, official_message_from_stream
        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui.virtualized_overlay import OverlayWindow
        from sindrome_overlay.youtube_grpc import stream_list_pb2

        app = QApplication.instance() or QApplication([])
        port = _free_local_port()
        settings = Settings(
            twitch_enabled=False,
            youtube_enabled=False,
            sound_enabled=False,
            check_for_updates=False,
            obs_enabled=True,
            obs_port=port,
            obs_max_messages=30,
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(
            ObsChatSourceServer, "_load_badge_images_async"
        ):
            window = OverlayWindow(
                settings,
                SettingsStore(Path(directory) / "settings.json"),
                logging.getLogger("chat-to-obs-integration"),
            )
            try:
                window.show()
                app.processEvents()
                self.assertTrue(window.obs_source.running)
                self.assertIsInstance(window.events, ProviderEventQueue)

                twitch = TwitchProvider(
                    window.events, "sindromegames", third_party_emotes=False
                )
                youtube = YouTubeProvider(
                    window.events, "https://youtu.be/abcdefghijk", "fake-key"
                )
                raw = (
                    "@room-id=444;display-name=Ana;user-id=55;emotes=25:3-7;id=tw-one "
                    ":ana!ana@ana.tmi.twitch.tv PRIVMSG #sindromegames :Oi Kappa"
                )
                kind, twitch_message = parse_twitch_line(raw)
                self.assertEqual(kind, "message")
                self.assertIsInstance(twitch_message, ChatMessage)
                twitch.emit_message(twitch_message)

                item = stream_list_pb2.LiveChatMessage(id="yt-one")
                item.snippet.type = stream_list_pb2.LiveChatMessageSnippet.TEXT_MESSAGE_EVENT
                item.snippet.text_message_details.message_text = "Olá YouTube 😀"
                item.author_details.display_name = "Visitante"
                youtube_message = official_message_from_stream(item, "pt-BR")
                self.assertIsNotNone(youtube_message)
                youtube._emit_once(youtube_message)
                youtube._emit_once(youtube_message)  # Replay after reconnect.

                window._drain_events()
                api_url = window.obs_source.url.replace(
                    "/obs-chat", "/api/state?revision=-1"
                )

                def read_messages() -> list[dict]:
                    with urlopen(api_url, timeout=3) as response:  # noqa: S310
                        self.assertEqual(response.status, 200)
                        return json.loads(response.read().decode("utf-8"))["messages"]

                messages = read_messages()
                self.assertEqual(
                    [m["message_id"] for m in messages], ["tw-one", "yt-one"]
                )
                self.assertEqual(messages[0]["segments"][1]["type"], "emote")
                self.assertEqual(messages[1]["segments"][0]["text"], "Olá YouTube 😀")

                twitch.emit_delete("tw-one")
                window._drain_events()
                self.assertEqual(
                    [m["message_id"] for m in read_messages()], ["yt-one"]
                )

                twitch.emit_message(
                    ChatMessage(
                        "twitch", "Ana", "second", author_id="55", message_id="tw-two"
                    )
                )
                window._drain_events()
                twitch.emit_delete_author("55")
                window._drain_events()
                self.assertEqual(
                    [m["message_id"] for m in read_messages()], ["yt-one"]
                )

                twitch.emit_clear()
                window._drain_events()
                self.assertEqual(
                    [m["message_id"] for m in read_messages()], ["yt-one"]
                )

                old_queue = window.events
                window._restart_providers()
                self.assertFalse(
                    old_queue.offer(
                        # Old provider events must not re-enter a new connection.
                        ProviderEvent(kind="clear", platform="youtube")
                    )
                )
                window._drain_events()
                self.assertEqual(
                    [m["message_id"] for m in read_messages()], ["yt-one"]
                )
            finally:
                window.close()
                app.processEvents()

    def test_moderation_keeps_same_ids_on_other_platform_in_ui_and_obs(self) -> None:
        from unittest.mock import patch

        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.events import ProviderEvent
        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.obs_source import ObsChatSourceServer
        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui.virtualized_overlay import OverlayWindow

        app = QApplication.instance() or QApplication([])
        settings = Settings(
            twitch_enabled=False,
            youtube_enabled=False,
            sound_enabled=False,
            check_for_updates=False,
            obs_enabled=True,
            obs_port=_free_local_port(),
            max_messages=300,
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(
            ObsChatSourceServer, "_load_badge_images_async"
        ):
            window = OverlayWindow(
                settings,
                SettingsStore(Path(directory) / "settings.json"),
                logging.getLogger("stage11-moderation"),
            )
            try:
                window.show()
                app.processEvents()
                self.assertTrue(window.obs_source.running)

                window.add_message(
                    ChatMessage("twitch", "T", "Twitch " * 30,
                                author_id="same-author", message_id="same-id")
                )
                window.add_message(
                    ChatMessage("youtube", "Y", "YouTube " * 5,
                                author_id="same-author", message_id="same-id")
                )
                window.add_message(
                    ChatMessage("twitch", "T", "duplicate",
                                author_id="same-author", message_id="same-id")
                )
                self.assertEqual(
                    [m.platform for m in window.messages], ["twitch", "youtube"]
                )
                self.assertEqual(window.message_model.rowCount(), 2)
                self.assertEqual(
                    [m["platform"] for m in window.obs_source.snapshot()["messages"]],
                    ["twitch", "youtube"],
                )

                window.events.offer(
                    ProviderEvent(kind="delete", platform="twitch", message_id="same-id")
                )
                window._drain_events()
                self.assertEqual([m.platform for m in window.messages], ["youtube"])
                self.assertEqual(
                    [m["platform"] for m in window.obs_source.snapshot()["messages"]],
                    ["youtube"],
                )

                window.add_message(
                    ChatMessage("twitch", "T", "timeout me",
                                author_id="same-author", message_id="new-id")
                )
                window.events.offer(
                    ProviderEvent(
                        kind="delete_author", platform="twitch",
                        author_id="same-author"
                    )
                )
                window._drain_events()
                self.assertEqual([m.platform for m in window.messages], ["youtube"])
                self.assertEqual(
                    [m["platform"] for m in window.obs_source.snapshot()["messages"]],
                    ["youtube"],
                )
                self.assertEqual(window.message_model.rowCount(), 1)

                window.events.offer(
                    ProviderEvent(kind="delete", platform="youtube", message_id="same-id")
                )
                window._drain_events()
                self.assertEqual(window.messages, [])
                self.assertEqual(window.obs_source.snapshot()["messages"], [])
            finally:
                window.close()
                app.processEvents()

    def test_overlay_feeds_obs_history_independently_from_desktop_expiry(self) -> None:
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui.virtualized_overlay import OverlayWindow

        app = QApplication.instance() or QApplication([])
        port = _free_local_port()
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                twitch_enabled=False,
                youtube_enabled=False,
                sound_enabled=False,
                check_for_updates=False,
                message_lifetime_seconds=1,
                obs_enabled=True,
                obs_port=port,
                obs_max_messages=100,
            )
            store = SettingsStore(Path(directory) / "settings.json")
            window = OverlayWindow(settings, store, logging.getLogger("obs-ui"))
            window.show()
            app.processEvents()

            self.assertTrue(window.obs_source.running)
            self.assertEqual(window.obs_source.bound_port, port)

            first = ChatMessage(
                "twitch",
                "raimundoce_",
                "tem o meccha chameleon e o machine party no roblox, vi esses dias",
                message_id="obs-first",
            )
            window.add_message(first)
            app.processEvents()
            self.assertEqual(
                [item["message_id"] for item in window.obs_source.snapshot()["messages"]],
                ["obs-first"],
            )

            # Desktop expiry/trim uses remove_at; OBS intentionally retains its own history.
            window.remove_at(0)
            app.processEvents()
            self.assertEqual(window.messages, [])
            self.assertEqual(
                [item["message_id"] for item in window.obs_source.snapshot()["messages"]],
                ["obs-first"],
            )

            second = ChatMessage("youtube", "viewer", "hello", message_id="obs-second")
            window.add_message(second)
            window._remove_message_id("obs-second")
            app.processEvents()
            self.assertNotIn(
                "obs-second",
                [item["message_id"] for item in window.obs_source.snapshot()["messages"]],
            )

            window.clear_messages()
            self.assertEqual(window.obs_source.snapshot()["messages"], [])
            window.close()
            app.processEvents()
            self.assertFalse(window.obs_source.running)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    unittest.main()
