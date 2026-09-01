from __future__ import annotations

import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Qt UI smoke test runs on the Windows release job")
class WindowsUiSmokeTests(unittest.TestCase):
    def test_message_card_renders_cached_emote_badge_and_coloured_author(self) -> None:
        from pathlib import Path

        from PySide6.QtCore import QObject, QUrl, Signal
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.models import ChatBadge, ChatEmote, ChatMessage
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.message_card import (
            EmoteMessageLabel,
            MessageCard,
            TwitchBadgeLabel,
        )

        class FakeAssetCache(QObject):
            emote_ready = Signal(str)
            badge_ready = Signal()

            def __init__(self, source: str) -> None:
                super().__init__()
                self.source = source

            def emote_source(self, _emote_id: str) -> str:
                return self.source

            def badge_source(self, _badge: ChatBadge) -> str:
                return self.source

        app = QApplication.instance() or QApplication([])
        image_source = QUrl.fromLocalFile(str(Path("assets/icon.svg").resolve())).toString()
        cache = FakeAssetCache(image_source)
        message = ChatMessage(
            "twitch",
            "Felipe",
            "Kappa hello",
            author_id="12345",
            author_colour="#FF69B4",
            badges=("MODERATOR",),
            emotes=(ChatEmote("25", 0, 5, "Kappa"),),
            badge_refs=(ChatBadge("moderator", "1", "444"),),
        )
        card = MessageCard(message, Settings(), cache)
        app.processEvents()

        emote_labels = card.findChildren(EmoteMessageLabel)
        badge_labels = card.findChildren(TwitchBadgeLabel)
        self.assertEqual(len(emote_labels), 1)
        self.assertIn("<img", emote_labels[0].text())
        self.assertEqual(len(badge_labels), 1)
        self.assertFalse(badge_labels[0].pixmap().isNull())
        card.deleteLater()

    def test_overlay_integrates_mixed_messages_opacity_resize_and_lifecycle(self) -> None:
        import logging
        import tempfile
        from pathlib import Path

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui.overlay import OverlayWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                twitch_enabled=False,
                youtube_enabled=False,
                always_on_top=True,
                background_opacity=0,
                max_messages=20,
                sound_enabled=False,
            )
            window = OverlayWindow(
                settings,
                SettingsStore(Path(directory) / "settings.json"),
                logging.getLogger("ui-integration"),
            )
            window.show()
            app.processEvents()

            self.assertTrue(window.windowFlags() & Qt.NoDropShadowWindowHint)
            self.assertIn("background-color: rgba(8, 11, 19, 0);", window.styleSheet())
            self.assertIn("border: 1px solid rgba(255, 255, 255, 0);", window.styleSheet())

            for index in range(40):
                platform = "twitch" if index % 2 == 0 else "youtube"
                window.add_message(
                    ChatMessage(
                        platform,
                        f"User {index % 7}",
                        f"Rapid message {index}",
                        author_id=f"stable-{index % 7}",
                        message_id=f"mixed-{index}",
                    )
                )
            window.add_message(
                ChatMessage(
                    "youtube",
                    "Duplicate",
                    "Must not appear twice",
                    message_id="mixed-39",
                )
            )
            app.processEvents()
            self.assertEqual(len(window.messages), 20)
            self.assertEqual(len(window.cards), 20)
            self.assertEqual(window.messages[-1].message_id, "mixed-39")
            self.assertEqual({message.platform for message in window.messages}, {"twitch", "youtube"})

            window.resize(620, 410)
            app.processEvents()
            self.assertEqual((window.width(), window.height()), (620, 410))
            self.assertTrue(window.size_grip.isVisible())

            initial_lock = window.settings.click_through
            if window.global_hotkey.is_registered:
                self.assertTrue(
                    window.global_hotkey.dispatch(
                        0x0312,
                        window.global_hotkey.hotkey_id,
                    )
                )
            else:
                window.toggle_click_through()
            self.assertNotEqual(window.settings.click_through, initial_lock)
            window.set_click_through(False)
            self.assertTrue(window.size_grip.isVisible())

            registered_handle = window.global_hotkey.registered_hwnd
            window.showMinimized()
            app.processEvents()
            window.showNormal()
            app.processEvents()
            window._restart_providers()
            window._restore_native_state()
            app.processEvents()
            if registered_handle is not None:
                self.assertEqual(window.global_hotkey.registered_hwnd, registered_handle)

            window.close()
            app.processEvents()
            self.assertFalse(window.global_hotkey.is_registered)
            self.assertFalse(window.event_timer.isActive())
            self.assertFalse(window.native_state_timer.isActive())
            self.assertEqual(window.providers, [])


if __name__ == "__main__":
    unittest.main()
