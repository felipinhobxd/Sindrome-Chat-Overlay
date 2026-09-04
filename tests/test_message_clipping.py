from __future__ import annotations

import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Qt layout regression runs on Windows CI")
class MessageClippingRegressionTests(unittest.TestCase):
    def test_virtualized_wrapped_twitch_message_gets_full_height(self) -> None:
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.message_card import MessageCard
        from sindrome_overlay.ui.message_list import (
            MessageCardDelegate,
            MessageListModel,
            VirtualMessageListView,
        )

        app = QApplication.instance() or QApplication([])
        settings = Settings(
            font_size=16,
            window_width=356,
            show_platform_labels=False,
            show_timestamps=False,
        )
        model = MessageListModel()
        view = VirtualMessageListView(model)
        delegate = MessageCardDelegate(settings, None, view)
        view.setItemDelegate(delegate)
        view.resize(356, 300)
        view.show()

        text = "tem o meccha chameleon e o machine party no roblox, vi esses dias"
        model.append_message(
            ChatMessage(
                "twitch",
                "raimundoce_",
                text,
                author_id="wrapped-message-regression",
                author_colour="#F4C542",
                badges=("MODERATOR",),
                message_id="wrapped-message-regression",
            )
        )

        # Virtualization opens the persistent editor and then asynchronously applies
        # the exact height measured from the wrapped QLabel. Run enough event turns
        # to exercise both phases just like the real overlay.
        for _ in range(8):
            app.processEvents()

        index = model.index(0, 0)
        self.assertTrue(view.isPersistentEditorOpen(index))
        cards = view.findChildren(MessageCard)
        self.assertEqual(len(cards), 1)
        card = cards[0]
        label = card.message_label

        required_label_height = label.heightForWidth(max(1, label.width()))
        self.assertGreater(required_label_height, 0)
        self.assertGreaterEqual(label.height() + 1, required_label_height)

        required_card_height = card.required_height_for_width(card.width())
        self.assertGreaterEqual(card.height() + 1, required_card_height)
        self.assertGreaterEqual(view.visualRect(index).height() + 1, required_card_height)
        self.assertEqual(label.text(), text)

        view.close()
        view.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
