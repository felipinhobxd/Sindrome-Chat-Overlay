from __future__ import annotations

import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Qt paint regression runs on Windows CI")
class MessageDoubleRenderRegressionTests(unittest.TestCase):
    def test_delegate_stops_fallback_paint_when_message_card_is_open(self) -> None:
        from PySide6.QtCore import QRect, Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QApplication, QListView, QStyleOptionViewItem

        from sindrome_overlay.models import ChatMessage
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.message_list import MessageCardDelegate, MessageListModel

        app = QApplication.instance() or QApplication([])
        model = MessageListModel()
        view = QListView()
        view.setModel(model)
        delegate = MessageCardDelegate(Settings(font_size=16, card_opacity=78), None, view)
        view.setItemDelegate(delegate)
        view.resize(380, 140)
        view.show()

        model.append_message(
            ChatMessage(
                "youtube",
                "@SindromeGames",
                "hola seniores",
                author_id="regression-user",
                author_colour="#F4C542",
                message_id="double-render-regression",
            )
        )
        app.processEvents()
        index = model.index(0, 0)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 360, 100)

        def render_fallback() -> QImage:
            image = QImage(360, 100, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            delegate.paint(painter, option, index)
            painter.end()
            return image

        def has_visible_pixel(image: QImage) -> bool:
            for y in range(image.height()):
                for x in range(image.width()):
                    if image.pixelColor(x, y).alpha() != 0:
                        return True
            return False

        # The fallback is useful for the brief frame before virtualization opens
        # the real card, so prove the lightweight painter still works by itself.
        self.assertFalse(view.isPersistentEditorOpen(index))
        self.assertTrue(has_visible_pixel(render_fallback()))

        # Once the transparent MessageCard editor exists it becomes the sole renderer.
        # Any fallback pixels here would show through as the duplicated/ghosted text.
        view.openPersistentEditor(index)
        app.processEvents()
        self.assertTrue(view.isPersistentEditorOpen(index))
        self.assertFalse(has_visible_pixel(render_fallback()))

        view.closePersistentEditor(index)
        view.close()
        view.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
