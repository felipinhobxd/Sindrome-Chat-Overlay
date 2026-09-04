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

            # Desktop expiry/trim uses _remove_at; OBS intentionally retains its own history.
            window._remove_at(0)
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
