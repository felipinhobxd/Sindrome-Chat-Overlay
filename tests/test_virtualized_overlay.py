from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "Desktop virtualization is validated on Windows")
class VirtualizedOverlayTests(unittest.TestCase):
    def _window(self, *, max_messages: int = 500, height: int = 300):
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui import OverlayWindow

        app = QApplication.instance() or QApplication([])
        directory = tempfile.TemporaryDirectory()
        settings = Settings(
            twitch_enabled=False,
            youtube_enabled=False,
            sound_enabled=False,
            check_for_updates=False,
            auto_scroll=True,
            max_messages=max_messages,
            window_width=440,
            window_height=height,
        )
        window = OverlayWindow(
            settings,
            SettingsStore(Path(directory.name) / "settings.json"),
            logging.getLogger("virtualized-overlay-test"),
        )
        window._test_temp_directory = directory
        window.show()
        app.processEvents()
        return app, window

    def test_large_history_keeps_only_viewport_message_cards_alive(self) -> None:
        from PySide6.QtWidgets import QListView

        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.ui.message_card import MessageCard

        app, window = self._window()
        try:
            for index in range(500):
                platform = "twitch" if index % 2 == 0 else "youtube"
                window.add_message(
                    ChatMessage(
                        platform,
                        f"User {index % 17}",
                        f"Virtualized message {index} with enough text to exercise wrapping.",
                        author_id=f"user-{index % 17}",
                        message_id=f"virtual-{index}",
                    )
                )

            for _ in range(5):
                app.processEvents()

            self.assertIsInstance(window.scroll, QListView)
            self.assertEqual(len(window.messages), 500)
            self.assertEqual(window.message_model.rowCount(), 500)
            self.assertEqual(window.cards, [])
            self.assertIsNone(window.message_host)
            self.assertGreater(window.message_view.active_editor_count, 0)
            self.assertLess(window.message_view.active_editor_count, 40)
            self.assertLess(len(window.findChildren(MessageCard)), 40)
            self.assertEqual(
                window.scroll.verticalScrollBar().value(),
                window.scroll.verticalScrollBar().maximum(),
            )

            window._remove_message_id("virtual-250")
            app.processEvents()
            self.assertEqual(window.message_model.rowCount(), 499)
            self.assertNotIn("virtual-250", {message.message_id for message in window.messages})

            window.clear_messages("twitch")
            app.processEvents()
            self.assertTrue(window.messages)
            self.assertTrue(all(message.platform == "youtube" for message in window.messages))
            self.assertEqual(window.message_model.rowCount(), len(window.messages))
        finally:
            window.close()
            app.processEvents()
            window._test_temp_directory.cleanup()

    def test_scrolling_recycles_editors_instead_of_growing_widget_count(self) -> None:
        from sindrome_overlay.models import ChatMessage

        app, window = self._window(max_messages=300, height=280)
        try:
            for index in range(300):
                window.add_message(
                    ChatMessage(
                        "youtube",
                        f"Scroller {index}",
                        ("Long scrolling message " * 4) + str(index),
                        author_id=f"scroll-{index}",
                        message_id=f"scroll-{index}",
                    )
                )
            for _ in range(4):
                app.processEvents()

            bar = window.message_view.verticalScrollBar()
            maximum = bar.maximum()
            observed_counts: list[int] = []
            for value in (0, maximum // 4, maximum // 2, (maximum * 3) // 4, maximum):
                window.settings.auto_scroll = False
                bar.setValue(value)
                for _ in range(3):
                    app.processEvents()
                observed_counts.append(window.message_view.active_editor_count)

            self.assertTrue(all(0 < count < 40 for count in observed_counts))
            self.assertLess(max(observed_counts), 40)

            window.clear_messages()
            for _ in range(3):
                app.processEvents()
            self.assertEqual(window.message_model.rowCount(), 0)
            self.assertEqual(window.messages, [])
            self.assertEqual(window.message_view.active_editor_count, 0)
            self.assertIs(window.message_stack.currentWidget(), window.empty_state)
        finally:
            window.close()
            app.processEvents()
            window._test_temp_directory.cleanup()


if __name__ == "__main__":
    unittest.main()
