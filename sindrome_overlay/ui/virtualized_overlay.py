from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QStackedWidget

from .message_list import MessageCardDelegate, MessageListModel, VirtualMessageListView
from .overlay import OverlayWindow as _LegacyOverlayWindow


class OverlayWindow(_LegacyOverlayWindow):
    """Desktop overlay using a QListView-backed, viewport-virtualized message feed."""

    def _build_ui(self) -> None:
        # Reuse the mature header/tray/window implementation and replace only the
        # old QScrollArea + one-QWidget-per-message feed.
        super()._build_ui()

        old_scroll = self.scroll
        root_layout = self.centralWidget().layout()
        insert_at = root_layout.indexOf(old_scroll)
        old_scroll.viewport().removeEventFilter(self)
        root_layout.removeWidget(old_scroll)
        old_scroll.hide()
        old_scroll.setParent(None)
        old_scroll.deleteLater()

        self.message_model = MessageListModel(self)
        self.message_view = VirtualMessageListView(self.message_model, self)
        self.message_view.setObjectName("VirtualMessageList")
        self.message_delegate = MessageCardDelegate(
            self.settings,
            self.twitch_assets,
            self.message_view,
        )
        self.message_view.setItemDelegate(self.message_delegate)
        self.message_view.viewport().installEventFilter(self)
        self.message_view.verticalScrollBar().rangeChanged.connect(self._on_scroll_range_changed)

        self.empty_state = QLabel()
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setWordWrap(True)

        self.message_stack = QStackedWidget(self)
        self.message_stack.setObjectName("MessageStack")
        self.message_stack.addWidget(self.empty_state)
        self.message_stack.addWidget(self.message_view)
        self.message_stack.setCurrentWidget(self.empty_state)
        root_layout.insertWidget(insert_at, self.message_stack, 1)

        # Keep the public/legacy scroll attribute used by eventFilter and smoke tests.
        self.scroll = self.message_view
        # These belonged to the retired QScrollArea feed. They intentionally no
        # longer own message widgets; visible MessageCards are controlled by the delegate.
        self.message_host = None
        self.message_layout = None
        self.cards.clear()
        self.cards_by_id.clear()

    def _append_card(self, message) -> None:
        # OverlayWindow.add_message already appended to self.messages before this call.
        self.message_model.append_message(message)
        self._update_empty_state()
        self.message_view.schedule_editor_refresh()
        if self.settings.auto_scroll:
            QTimer.singleShot(0, self._scroll_to_bottom)
            # Exact row heights are learned lazily from visible MessageCards.
            QTimer.singleShot(75, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        if not self.settings.auto_scroll:
            return
        self.message_view.scrollToBottom()
        bar = self.message_view.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.message_view.schedule_editor_refresh()

    def _on_scroll_range_changed(self, _minimum: int, maximum: int) -> None:
        if self.settings.auto_scroll:
            self.message_view.verticalScrollBar().setValue(maximum)

    def _expire_messages(self) -> None:
        lifetime = self.settings.message_lifetime_seconds
        if lifetime <= 0:
            return
        now = time.monotonic()
        while self.messages:
            created = self.message_model.created_at(0)
            if created is None or now - created < lifetime:
                break
            self._remove_at(0)

    def _remove_message_id(self, message_id: str) -> None:
        index = self.message_model.find_message_id(message_id)
        if index >= 0:
            self._remove_at(index)

    def _remove_at(self, index: int) -> None:
        if index < 0 or index >= len(self.messages):
            return
        self.messages.pop(index)
        self.message_model.remove_at(index)
        self._update_empty_state()
        self.message_view.schedule_editor_refresh()

    def clear_messages(self, platform: str = "") -> None:
        if not platform:
            self.messages.clear()
            self.message_model.clear()
            self._update_empty_state()
            return
        for index in range(len(self.messages) - 1, -1, -1):
            if self.messages[index].platform == platform:
                self._remove_at(index)

    def _rebuild_cards(self) -> None:
        history = list(self.messages)
        filtered = []
        for message in history[-self.settings.max_messages :]:
            if self.settings.hide_commands and message.text.lstrip().startswith("!"):
                continue
            filtered.append(message)

        self.messages[:] = filtered
        self.cards.clear()
        self.cards_by_id.clear()
        self.message_delegate.set_settings(self.settings)
        self.message_model.replace_messages(filtered)
        self.message_view.refresh_virtualization()
        self._update_empty_state()
        if self.settings.auto_scroll and filtered:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _update_empty_state(self) -> None:
        if self.messages:
            self.message_stack.setCurrentWidget(self.message_view)
        else:
            self.message_stack.setCurrentWidget(self.empty_state)
