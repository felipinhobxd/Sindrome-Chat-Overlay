from __future__ import annotations

import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Qt UI smoke test runs on the Windows release job")
class WindowsUiSmokeTests(unittest.TestCase):
    def test_youtube_settings_are_simple_masked_translated_and_stateful(self) -> None:
        import tempfile
        from pathlib import Path

        from PySide6.QtWidgets import QApplication, QLineEdit

        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui.settings_dialog import SettingsDialog
        from sindrome_overlay.youtube_key import YouTubeKeyValidationResult

        app = QApplication.instance() or QApplication([])
        dialog = SettingsDialog(
            Settings(language="en", youtube_api_key=""),
            youtube_connection_mode="compatibility",
        )
        dialog.show()
        app.processEvents()
        self.assertIn("Compatibility mode", dialog.youtube_status_title.text())
        self.assertTrue(dialog.youtube_advanced_panel.isHidden())
        self.assertEqual(dialog.sound_volume.maximum(), 200)
        self.assertEqual(dialog.twitch_sound.count(), 6)
        self.assertEqual(dialog.youtube_sound.count(), 6)
        dialog.sound_volume.setValue(200)
        dialog.twitch_sound.setCurrentIndex(dialog.twitch_sound.findData("arcade"))
        dialog.youtube_sound.setCurrentIndex(dialog.youtube_sound.findData("bubble"))
        dialog.sound_min_interval.setValue(900)
        sound_settings = dialog.settings()
        self.assertEqual(sound_settings.sound_volume, 200)
        self.assertEqual(sound_settings.twitch_sound, "arcade")
        self.assertEqual(sound_settings.youtube_sound, "bubble")
        self.assertEqual(sound_settings.sound_min_interval_ms, 900)

        dialog.youtube_advanced_button.click()
        app.processEvents()
        self.assertFalse(dialog.youtube_advanced_panel.isHidden())
        self.assertEqual(dialog.youtube_api_key.echoMode(), QLineEdit.Password)

        secret = "AIza-test-secret"
        dialog.youtube_api_key.setText(secret)
        dialog._validation_debounce.stop()
        request_id = dialog._validation_request_id
        dialog._apply_validation_result(YouTubeKeyValidationResult(request_id, "valid"))
        self.assertIn("Valid API key", dialog.youtube_status_title.text())

        dialog.youtube_reveal_button.click()
        self.assertEqual(dialog.youtube_api_key.echoMode(), QLineEdit.Normal)
        dialog.youtube_reveal_button.click()
        self.assertEqual(dialog.youtube_api_key.echoMode(), QLineEdit.Password)

        dialog._apply_validation_result(YouTubeKeyValidationResult(request_id, "invalid"))
        self.assertIn("invalid", dialog.youtube_status_title.text().lower())
        dialog._apply_validation_result(YouTubeKeyValidationResult(request_id, "unavailable"))
        self.assertIn("not verified", dialog.youtube_status_title.text().lower())
        dialog.youtube_api_key.clear()
        self.assertIn("Compatibility mode", dialog.youtube_status_title.text())
        dialog.close()

        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            store.save(Settings(language="pt-BR", youtube_api_key=secret))
            reopened = SettingsDialog(
                store.load(),
                youtube_connection_mode="official_stream",
            )
            reopened.show()
            app.processEvents()
            self.assertIn("API oficial", reopened.youtube_status_title.text())
            self.assertIn("Configurações avançadas", reopened.youtube_advanced_button.text())
            self.assertEqual(reopened.youtube_api_key.text(), secret)
            self.assertEqual(reopened.youtube_api_key.echoMode(), QLineEdit.Password)
            self.assertTrue(reopened.youtube_advanced_panel.isHidden())
            self.assertEqual(reopened.sound_options.title(), "Sons de notificação")
            reopened.close()

    def test_message_card_renders_cached_emote_badge_and_coloured_author(self) -> None:
        from pathlib import Path

        from PySide6.QtCore import QObject, QUrl, Signal
        from PySide6.QtWidgets import QApplication, QLabel

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
        card.resize(500, 150)
        card.show()
        app.processEvents()

        emote_labels = card.findChildren(EmoteMessageLabel)
        badge_labels = card.findChildren(TwitchBadgeLabel)
        self.assertEqual(len(emote_labels), 1)
        self.assertIn("<img", emote_labels[0].text())
        self.assertEqual(len(badge_labels), 1)
        self.assertFalse(badge_labels[0].pixmap().isNull())
        author_labels = card.findChildren(QLabel, "AuthorName")
        self.assertEqual(len(author_labels), 1)
        self.assertIn("background: transparent", author_labels[0].styleSheet())
        self.assertNotIn("border-left", card.styleSheet())
        self.assertLess(card.message_bubble.width(), card.width())

        emote_only = MessageCard(
            ChatMessage(
                "twitch",
                "EmoteUser",
                "Kappa",
                author_id="emote-user",
                emotes=(ChatEmote("25", 0, 5, "Kappa"),),
            ),
            Settings(),
            cache,
        )
        emote_only.resize(500, 140)
        emote_only.show()
        app.processEvents()
        self.assertLess(emote_only.message_bubble.width(), 180)

        long_card = MessageCard(
            ChatMessage(
                "youtube",
                "Long Name Unicode 😀",
                "A long message " * 30,
                author_id="long-user",
            ),
            Settings(window_width=340),
            None,
        )
        long_card.resize(340, 300)
        long_card.show()
        app.processEvents()
        self.assertLessEqual(long_card.message_bubble.width(), long_card.width())
        self.assertGreater(long_card.message_bubble.height(), emote_only.message_bubble.height())
        long_card.deleteLater()
        emote_only.deleteLater()
        card.deleteLater()

    def test_overlay_integrates_mixed_messages_opacity_resize_and_lifecycle(self) -> None:
        import logging
        import tempfile
        from pathlib import Path

        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
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
                check_for_updates=False,
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
            self.assertIn("QFrame#ChatCard", window.styleSheet())
            self.assertIn("background-color: rgba(3, 5, 9, 199);", window.styleSheet())
            self.assertEqual(window.header.cursor().shape(), Qt.SizeAllCursor)
            self.assertEqual(window.settings_button.cursor().shape(), Qt.ArrowCursor)
            self.assertTrue(window.drag_indicator.isVisible())

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
            self.assertEqual(
                window.scroll.verticalScrollBar().value(),
                window.scroll.verticalScrollBar().maximum(),
            )

            for opacity in (100, 50, 0):
                window.settings.background_opacity = opacity
                window._apply_visual_settings()
                app.processEvents()
                start_position = window.pos()
                local_start = QPoint(25, 18)
                global_start = window.header.mapToGlobal(local_start)
                delta = QPoint(16, 11)
                window.header.mousePressEvent(
                    QMouseEvent(
                        QEvent.MouseButtonPress,
                        QPointF(local_start),
                        QPointF(global_start),
                        Qt.LeftButton,
                        Qt.LeftButton,
                        Qt.NoModifier,
                    )
                )
                window.header.mouseMoveEvent(
                    QMouseEvent(
                        QEvent.MouseMove,
                        QPointF(local_start + delta),
                        QPointF(global_start + delta),
                        Qt.NoButton,
                        Qt.LeftButton,
                        Qt.NoModifier,
                    )
                )
                window.header.mouseReleaseEvent(
                    QMouseEvent(
                        QEvent.MouseButtonRelease,
                        QPointF(local_start + delta),
                        QPointF(global_start + delta),
                        Qt.LeftButton,
                        Qt.NoButton,
                        Qt.NoModifier,
                    )
                )
                app.processEvents()
                self.assertEqual(window.pos(), start_position + delta)

            position_before_button = window.pos()
            window.clear_button.click()
            app.processEvents()
            self.assertEqual(window.pos(), position_before_button)
            self.assertEqual(window.messages, [])

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
