from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QWidget,
)

from ..models import ChatMessage
from ..settings import Settings
from .message_card import MessageCard
from .twitch_assets import TwitchAssetCache

_MESSAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_CREATED_ROLE = _MESSAGE_ROLE + 1


@dataclass(slots=True)
class _MessageRow:
    message: ChatMessage
    created_monotonic: float


class MessageListModel(QAbstractListModel):
    """Small data-only model backing the virtualized desktop chat list."""

    MessageRole = _MESSAGE_ROLE
    CreatedMonotonicRole = _CREATED_ROLE

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[_MessageRow] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return row.message.text
        if role == self.MessageRole:
            return row.message
        if role == self.CreatedMonotonicRole:
            return row.created_monotonic
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # Persistent editors are opened only for visible rows. The editable flag is
        # required by QAbstractItemView, while user-triggered editing stays disabled.
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    @property
    def messages(self) -> list[ChatMessage]:
        return [row.message for row in self._rows]

    def message_at(self, index: int) -> ChatMessage | None:
        if 0 <= index < len(self._rows):
            return self._rows[index].message
        return None

    def created_at(self, index: int) -> float | None:
        if 0 <= index < len(self._rows):
            return self._rows[index].created_monotonic
        return None

    def append_message(self, message: ChatMessage, *, created_monotonic: float | None = None) -> None:
        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append(
            _MessageRow(
                message=message,
                created_monotonic=(
                    time.monotonic() if created_monotonic is None else created_monotonic
                ),
            )
        )
        self.endInsertRows()

    def remove_at(self, index: int) -> ChatMessage | None:
        if not 0 <= index < len(self._rows):
            return None
        self.beginRemoveRows(QModelIndex(), index, index)
        row = self._rows.pop(index)
        self.endRemoveRows()
        return row.message

    def clear(self) -> None:
        if not self._rows:
            return
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def replace_messages(self, messages: list[ChatMessage]) -> None:
        now = time.monotonic()
        self.beginResetModel()
        self._rows[:] = [_MessageRow(message, now) for message in messages]
        self.endResetModel()

    def find_message_id(self, message_id: str) -> int:
        if not message_id:
            return -1
        for index, row in enumerate(self._rows):
            if row.message.message_id == message_id:
                return index
        return -1


class MessageCardDelegate(QStyledItemDelegate):
    """Creates real MessageCard widgets only for rows near the viewport."""

    def __init__(
        self,
        settings: Settings,
        asset_cache: TwitchAssetCache | None,
        parent: QListView,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.asset_cache = asset_cache
        self._height_cache: dict[tuple[int, int, tuple[object, ...]], int] = {}
        if asset_cache is not None:
            asset_cache.emote_ready.connect(self._asset_layout_changed)
            asset_cache.badge_ready.connect(self._asset_layout_changed)

    def set_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.invalidate_height_cache()

    def invalidate_height_cache(self) -> None:
        self._height_cache.clear()

    def createEditor(  # noqa: N802 - Qt API
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QWidget | None:
        message = index.data(MessageListModel.MessageRole)
        if not isinstance(message, ChatMessage):
            return None
        card = MessageCard(message, self.settings, self.asset_cache, parent)
        card.setAutoFillBackground(False)
        return card

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        # MessageCard is immutable for the lifetime of one row; a new editor is
        # created when an index is recycled into the visible window.
        return

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:  # noqa: N802
        return

    def updateEditorGeometry(  # noqa: N802 - Qt API
        self,
        editor: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        editor.setGeometry(option.rect)
        if not isinstance(editor, MessageCard):
            return
        editor.ensurePolished()
        layout = editor.layout()
        if layout is not None:
            layout.activate()
        actual_height = max(1, editor.sizeHint().height())
        width = max(80, option.rect.width())
        key = self._cache_key(index, width)
        previous = self._height_cache.get(key)
        if previous is None or abs(previous - actual_height) > 1:
            self._height_cache[key] = actual_height
            persistent = QPersistentModelIndex(index)
            QTimer.singleShot(0, lambda: self._emit_size_hint_changed(persistent))

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        view = self.parent()
        width = option.rect.width()
        if isinstance(view, QListView):
            width = max(width, view.viewport().width() - 2)
        width = max(120, width)
        key = self._cache_key(index, width)
        cached = self._height_cache.get(key)
        if cached is not None:
            return QSize(width, cached)
        message = index.data(MessageListModel.MessageRole)
        if not isinstance(message, ChatMessage):
            return QSize(width, max(40, self.settings.font_size * 3))
        return QSize(width, self._estimate_height(message, width))

    def paint(  # noqa: N802 - Qt API
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Lightweight fallback for the one frame before a visible editor opens."""
        message = index.data(MessageListModel.MessageRole)
        if not isinstance(message, ChatMessage):
            return
        painter.save()
        rect = option.rect.adjusted(7, 4, -7, -4)
        base_font = QFont("Segoe UI")
        base_font.setPixelSize(self.settings.font_size)
        author_font = QFont(base_font)
        author_font.setBold(True)
        painter.setFont(author_font)
        painter.setPen(QColor(message.safe_author_colour))
        metrics = QFontMetrics(author_font)
        author_height = metrics.lineSpacing()
        painter.drawText(
            QRect(rect.left(), rect.top(), rect.width(), author_height),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            message.author,
        )
        body_top = rect.top() + author_height + 3
        body_rect = QRect(rect.left(), body_top, rect.width(), max(1, rect.bottom() - body_top + 1))
        alpha = round(max(0, min(100, self.settings.card_opacity)) * 2.55)
        painter.setBrush(QColor(3, 5, 9, alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(body_rect, 6, 6)
        painter.setFont(base_font)
        painter.setPen(QColor("#F5F7FB"))
        painter.drawText(
            body_rect.adjusted(7, 3, -7, -4),
            int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            message.text,
        )
        painter.restore()

    def _estimate_height(self, message: ChatMessage, width: int) -> int:
        base_font = QFont("Segoe UI")
        base_font.setPixelSize(self.settings.font_size)
        metrics = QFontMetrics(base_font)
        meta_height = metrics.lineSpacing()
        if message.badge_refs:
            meta_height = max(
                meta_height,
                max(18, min(32, round(self.settings.font_size * 1.25))),
            )

        available_text_width = max(80, width - 34)
        text_rect = metrics.boundingRect(
            QRect(0, 0, available_text_width, 100_000),
            int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft),
            message.text or " ",
        )
        body_height = max(metrics.lineSpacing(), text_rect.height())
        if message.emotes:
            image_size = max(24, min(48, round(self.settings.font_size * 1.8)))
            body_height = max(body_height, image_size)
        # Mirrors MessageCard's outer/meta/bubble margins closely. Once a row is
        # visible, updateEditorGeometry records the exact widget size for that width.
        return max(42, 2 + meta_height + 2 + 3 + body_height + 4 + 3 + 4)

    def _cache_key(self, index: QModelIndex, width: int) -> tuple[int, int, tuple[object, ...]]:
        message = index.data(MessageListModel.MessageRole)
        return (id(message), width, self._settings_signature())

    def _settings_signature(self) -> tuple[object, ...]:
        return (
            self.settings.font_size,
            self.settings.language,
            self.settings.show_platform_labels,
            self.settings.show_timestamps,
            self.settings.card_opacity,
        )

    def _emit_size_hint_changed(self, persistent: QPersistentModelIndex) -> None:
        if not persistent.isValid():
            return
        model = persistent.model()
        if model is None:
            return
        self.sizeHintChanged.emit(model.index(persistent.row(), persistent.column()))

    def _asset_layout_changed(self, *_args) -> None:
        self.invalidate_height_cache()
        view = self.parent()
        if isinstance(view, VirtualMessageListView):
            view.relayout_visible_items()


class VirtualMessageListView(QListView):
    """QListView that keeps persistent MessageCard editors only near the viewport."""

    def __init__(self, model: MessageListModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._open_editors: list[QPersistentModelIndex] = []
        self._refresh_pending = False
        self._buffer_pixels = 120
        self.setModel(model)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(False)
        self.setWordWrap(True)
        self.setSpacing(3)

        self.verticalScrollBar().valueChanged.connect(self.schedule_editor_refresh)
        self.verticalScrollBar().rangeChanged.connect(self.schedule_editor_refresh)
        model.rowsInserted.connect(self.schedule_editor_refresh)
        model.rowsRemoved.connect(self.schedule_editor_refresh)
        model.modelReset.connect(self._model_reset)
        QTimer.singleShot(0, self.schedule_editor_refresh)

    @property
    def active_editor_count(self) -> int:
        return sum(1 for index in self._open_editors if index.isValid())

    def schedule_editor_refresh(self, *_args) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._refresh_virtual_editors)

    def refresh_virtualization(self) -> None:
        self._close_all_editors()
        delegate = self.itemDelegate()
        if isinstance(delegate, MessageCardDelegate):
            delegate.invalidate_height_cache()
        self.doItemsLayout()
        self.schedule_editor_refresh()

    def relayout_visible_items(self) -> None:
        delegate = self.itemDelegate()
        if isinstance(delegate, MessageCardDelegate):
            delegate.invalidate_height_cache()
        self.doItemsLayout()
        self.schedule_editor_refresh()
        self.viewport().update()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        delegate = self.itemDelegate()
        if isinstance(delegate, MessageCardDelegate):
            delegate.invalidate_height_cache()
        super().resizeEvent(event)
        QTimer.singleShot(0, self.doItemsLayout)
        self.schedule_editor_refresh()

    def _model_reset(self) -> None:
        self._open_editors.clear()
        self.schedule_editor_refresh()

    def _refresh_virtual_editors(self) -> None:
        self._refresh_pending = False
        model = self.model()
        if model is None or model.rowCount() == 0:
            self._close_all_editors()
            return

        visible = self.viewport().rect().adjusted(0, -self._buffer_pixels, 0, self._buffer_pixels)
        desired: list[QPersistentModelIndex] = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            rect = self.visualRect(index)
            if rect.isValid() and rect.intersects(visible):
                desired.append(QPersistentModelIndex(index))

        for current in list(self._open_editors):
            if not current.isValid() or not any(current == wanted for wanted in desired):
                if current.isValid():
                    self.closePersistentEditor(model.index(current.row(), current.column()))
                self._open_editors.remove(current)

        for wanted in desired:
            if any(wanted == current for current in self._open_editors):
                continue
            index = model.index(wanted.row(), wanted.column())
            self.openPersistentEditor(index)
            self._open_editors.append(wanted)

    def _close_all_editors(self) -> None:
        model = self.model()
        if model is not None:
            for persistent in list(self._open_editors):
                if persistent.isValid():
                    self.closePersistentEditor(
                        model.index(persistent.row(), persistent.column())
                    )
        self._open_editors.clear()
