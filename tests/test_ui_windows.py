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
        image_source = QUrl.fromLocalFile(str(Path("assets/icon.png").resolve())).toString()
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


if __name__ == "__main__":
    unittest.main()
