from __future__ import annotations

import importlib.util
import itertools
import math
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt is required for layout regressions")
class MessageLayoutRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.views = []
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        for view in self.views:
            view.close()
            view.deleteLater()
        self.settle()
        self.directory.cleanup()

    def settle(self) -> None:
        from PySide6.QtCore import QCoreApplication, QEvent

        for _ in range(20):
            self.app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def view(self, messages, *, width=356, height=450, font_size=16, cache=None):
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.message_list import (
            MessageCardDelegate, MessageListModel, VirtualMessageListView,
        )
        from sindrome_overlay.ui.theme import build_stylesheet

        settings = Settings(font_size=font_size, show_platform_labels=True, show_timestamps=True)
        model = MessageListModel()
        view = VirtualMessageListView(model)
        view.setItemDelegate(MessageCardDelegate(settings, cache, view))
        view.setStyleSheet(build_stylesheet(settings))
        view.resize(width, height)
        self.views.append(view)
        model.replace_messages(messages)
        view.show()
        self.settle()
        return view

    def card(self, view, row=0):
        from PySide6.QtWidgets import QAbstractItemView

        index = view.model().index(row, 0)
        view.scrollTo(index, QAbstractItemView.PositionAtTop)
        self.settle()
        self.assertTrue(view.isPersistentEditorOpen(index))
        return view.indexWidget(index)

    def assert_geometry(self, view, card) -> None:
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtWidgets import QLabel

        row = view.model().find_message_id(card.message.message_id)
        self.assertGreaterEqual(row, 0)
        row_rect = view.visualRect(view.model().index(row, 0))
        self.assertEqual(card.geometry(), row_rect)
        self.assertEqual(card.height(), card.required_height_for_width(card.width()))
        self.assertLessEqual(card.width(), view.viewport().width())
        metadata = card.findChildren(QLabel)
        self.assertGreater(len(metadata), 0)
        rectangles = [QRect(label.mapTo(card, QPoint()), label.size()) for label in metadata]
        rectangles.append(card.message_bubble.geometry())
        for rect in rectangles:
            self.assertTrue(card.rect().contains(rect), (card.rect(), rect))
        for left, right in itertools.combinations(rectangles, 2):
            self.assertFalse(left.intersects(right), (left, right))
        label = card.message_label
        self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
        self.assertTrue(card.message_bubble.rect().contains(label.geometry()))
        # Inspect the actual painted document, including every wrapped line and image.
        document = label.document()
        self.assertLessEqual(math.ceil(document.size().height()), label.height())
        self.assertEqual(label.verticalScrollBar().maximum(), 0)
        block = document.begin()
        while block.isValid():
            layout = block.layout()
            for number in range(layout.lineCount()):
                line = layout.lineAt(number)
                self.assertLessEqual(line.naturalTextWidth(), label.width() + 1)
                self.assertLessEqual(layout.position().y() + line.y() + line.height(), label.height() + 1)
            block = block.next()
        for child in (card, card.message_bubble, label):
            self.assertEqual(child.minimumHeight(), 0)
        for row in range(view.model().rowCount() - 1):
            first = view.visualRect(view.model().index(row, 0))
            following = view.visualRect(view.model().index(row + 1, 0))
            self.assertLess(first.bottom(), following.top())

    @staticmethod
    def message(number=0, *, text=None, author=None, **kwargs):
        from sindrome_overlay.models import ChatMessage

        return ChatMessage(
            "twitch", author or "Nome longo 😀 " * 30,
            text if text is not None else "Mensagem completa com várias palavras e quebras. " * 20,
            message_id=f"layout-{number}", **kwargs,
        )

    def test_extreme_name_three_badges_platform_timestamp_and_bits(self) -> None:
        from PySide6.QtWidgets import QLabel

        message = self.message(badges=("MODERATOR", "SUBSCRIBER", "OWNER"), amount="10000 Bits")
        view = self.view([message])
        card = self.card(view)
        self.assert_geometry(view, card)
        author = card.findChild(QLabel, "AuthorName")
        self.assertEqual(author.toolTip(), message.author)
        self.assertIn("…", author.text())
        self.assertNotIn("\n", author.text())

    def test_explicit_four_plus_lines_are_visible_in_full(self) -> None:
        message = self.message(text="\n".join(f"Linha {n}: texto completo" for n in range(6)))
        view = self.view([message], width=320)
        card = self.card(view)
        self.assert_geometry(view, card)
        self.assertEqual(card.message_label.toPlainText(), message.text)
        self.assertGreaterEqual(card.message_label.document().blockCount(), 6)

    def test_ten_consecutive_long_messages_never_overlap(self) -> None:
        view = self.view([self.message(n) for n in range(10)], width=320)
        for number in range(10):
            with self.subTest(row=number):
                card = self.card(view, number)
                self.assert_geometry(view, card)
                self.assertEqual(card.message_label.toPlainText(), card.message.text)

    def test_very_narrow_window_keeps_all_metadata_and_body_inside_rows(self) -> None:
        for width in (120, 180, 260):
            with self.subTest(width=width):
                view = self.view([
                    self.message(badges=("MODERATOR", "SUBSCRIBER", "OWNER"), amount="R$ 12345,67"),
                ], width=width)
                self.assert_geometry(view, self.card(view))
                self.assertEqual(view.horizontalScrollBar().maximum(), 0)

    def test_repeated_resize_shrinks_and_restores_all_ten_row_heights(self) -> None:
        view = self.view([self.message(n) for n in range(10)], width=200)
        heights = {}
        for width in (200, 720, 200, 480, 720, 200):
            view.resize(width, 450)
            self.settle()
            current = []
            for number in range(10):
                card = self.card(view, number)
                self.assert_geometry(view, card)
                current.append(card.height())
            if width in heights:
                self.assertEqual(current, heights[width])
            heights[width] = current
        self.assertTrue(all(wide < narrow for wide, narrow in zip(heights[720], heights[200])))

    def test_large_font_and_live_font_change_recompute_geometry(self) -> None:
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.theme import build_stylesheet

        view = self.view([self.message(badges=("MODERATOR", "SUBSCRIBER", "OWNER"), amount="500 Bits")])
        original_height = self.card(view).height()
        settings = Settings(font_size=30, show_platform_labels=True, show_timestamps=True)
        view.itemDelegate().set_settings(settings)
        view.setStyleSheet(build_stylesheet(settings))
        view.refresh_virtualization()
        self.settle()
        card = self.card(view)
        self.assert_geometry(view, card)
        self.assertGreater(card.height(), original_height)
        self.assertEqual(card.message_label.font().pixelSize(), 30)
        view.resize(150, 450)
        self.settle()
        self.assert_geometry(view, self.card(view))

    def asset_cache(self):
        from PySide6.QtCore import QObject, QUrl, Signal
        from PySide6.QtGui import QColor, QImage

        path = Path(self.directory.name) / "asset.png"
        image = QImage(64, 64, QImage.Format_ARGB32)
        image.fill(QColor("#9146FF"))
        self.assertTrue(image.save(str(path)))

        class Cache(QObject):
            emote_ready = Signal(str)
            badge_ready = Signal()

            def __init__(self):
                super().__init__()
                self.source = QUrl.fromLocalFile(str(path)).toString()
                self.emotes_loaded = False
                self.badges_loaded = False

            def emote_source(self, _emote_id, _image_url=""):
                return self.source if self.emotes_loaded else ""

            def badge_source(self, _badge):
                return self.source if self.badges_loaded else ""

        return Cache()

    def emote_message(self, number=0, *, prefix=""):
        from sindrome_overlay.models import ChatBadge, ChatEmote

        return self.message(
            number, text=prefix + " ".join(["K"] * 15),
            emotes=tuple(ChatEmote("25", len(prefix) + n * 2, len(prefix) + n * 2 + 1, "K") for n in range(15)),
            badges=("MODERATOR", "SUBSCRIBER", "OWNER"),
            badge_refs=tuple(ChatBadge(name, "1") for name in ("moderator", "subscriber", "broadcaster")),
        )

    def test_late_emotes_and_badges_relayout_visible_and_recycled_rows(self) -> None:
        from sindrome_overlay.ui.message_card import TwitchBadgeLabel

        cache = self.asset_cache()
        view = self.view([self.emote_message(n) for n in range(20)], width=220, cache=cache)
        before = self.card(view).message_label.height()
        cache.emotes_loaded = True
        for _ in range(4):
            cache.emote_ready.emit("25")
        self.settle()
        card = self.card(view)
        self.assert_geometry(view, card)
        self.assertGreater(card.message_label.height(), before)
        cache.badges_loaded = True
        cache.badge_ready.emit()
        self.settle()
        # Scroll through rows that had no editor when the assets arrived, then
        # return to the first row to exercise editor recycling with cached images.
        for row in (*range(20), 0):
            card = self.card(view, row)
            self.assert_geometry(view, card)
            self.assertEqual(card.message_label.text().count("<img"), 15)
            self.assertTrue(all(not badge.pixmap().isNull() for badge in card.findChildren(TwitchBadgeLabel)))
        height = card.height()
        self.settle()
        self.assertEqual(card.height(), height)

    def test_mixed_and_emote_only_messages_wrap_and_stay_compact(self) -> None:
        from sindrome_overlay.models import ChatEmote

        cache = self.asset_cache()
        cache.emotes_loaded = cache.badges_loaded = True
        messages = [self.emote_message(0, prefix="Texto antes dos emotes: "), self.emote_message(1)]
        messages.append(self.message(2, text="K", emotes=(ChatEmote("25", 0, 1, "K"),)))
        view = self.view(messages, width=220, cache=cache)
        for row in range(3):
            self.assert_geometry(view, self.card(view, row))
        self.assertLess(self.card(view, 2).message_bubble.width(), 80)

    def test_unbroken_words_links_and_html_like_text_wrap_without_data_loss(self) -> None:
        text = "<b>literal</b> " + "x" * 250 + "\nhttps://example.test/" + "abcdef" * 70
        message = self.message(text=text)
        view = self.view([message], width=180)
        card = self.card(view)
        self.assert_geometry(view, card)
        self.assertEqual(card.message_label.toPlainText(), text)

    def test_virtualization_and_height_cache_remain_bounded_after_resize_and_clear(self) -> None:
        from sindrome_overlay.ui.message_card import MessageCard

        view = self.view([self.message(n) for n in range(100)])
        for width, row in ((180, 0), (700, 40), (220, 99), (356, 0)):
            view.resize(width, 450)
            # Resize schedules a Qt layout pass. Resolve that pass before asking
            # scrollTo to locate a row using its new width-dependent geometry.
            self.settle()
            self.assert_geometry(view, self.card(view, row))
            self.assertLess(view.active_editor_count, 20)
            self.assertLess(len(view.findChildren(MessageCard)), 20)
            self.assertLessEqual(len(view.itemDelegate()._height_cache), 2 * view.model().rowCount())
        view.model().clear()
        self.settle()
        self.assertEqual(view.active_editor_count, 0)
        self.assertEqual(len(view.itemDelegate()._height_cache), 0)

    def test_delegate_never_paints_under_cards_after_resize_or_late_assets(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QStyleOptionViewItem

        cache = self.asset_cache()
        view = self.view([self.emote_message()], cache=cache)
        for width in (180, 700, 180):
            view.resize(width, 450)
            cache.emotes_loaded = cache.badges_loaded = True
            cache.emote_ready.emit("25")
            cache.badge_ready.emit()
            self.settle()
            self.card(view)
            index = view.model().index(0, 0)
            option = QStyleOptionViewItem()
            option.rect = view.visualRect(index)
            image = QImage(view.size(), QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            view.itemDelegate().paint(painter, option, index)
            painter.end()
            self.assertFalse(any(bytes(image.constBits())))


if __name__ == "__main__":
    unittest.main()
