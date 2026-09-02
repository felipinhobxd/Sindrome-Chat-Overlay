from __future__ import annotations

import logging
import queue
import sys
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..events import ProviderEvent
from ..i18n import tr
from ..models import ChatMessage
from ..providers import TwitchProvider, YouTubeProvider
from ..providers.base import BaseProvider
from ..settings import Settings, SettingsStore
from ..updates import UpdateChecker, UpdateCheckResult, UpdateInfo
from ..win32 import WindowsGlobalHotkey, WindowsOverlayController, native_message_values
from .message_card import MessageCard
from .settings_dialog import SettingsDialog
from .theme import build_stylesheet
from .twitch_assets import TwitchAssetCache


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative


class DragHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            window = self.window()
            self._offset = event.globalPosition().toPoint() - window.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._offset = None
        super().mouseReleaseEvent(event)


class OverlayWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        logger: logging.Logger,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.log = logger
        self.twitch_assets = TwitchAssetCache(logger, self)
        self.events: queue.Queue[ProviderEvent] = queue.Queue()
        self.providers: list[BaseProvider] = []
        self.messages: list[ChatMessage] = []
        self.cards: list[MessageCard] = []
        self.cards_by_id: dict[str, MessageCard] = {}
        self.seen_ids: set[str] = set()
        self.seen_order: deque[str] = deque(maxlen=5_000)
        self.status_labels: dict[str, QLabel] = {}
        self.youtube_connection_mode = (
            "official_configured" if settings.youtube_api_key else "compatibility"
        )
        self._shutting_down = False
        self._first_lock_notice = True
        self.global_hotkey = WindowsGlobalHotkey(self.toggle_click_through, logger)
        self.native_window = WindowsOverlayController(logger)
        self._fallback_shortcut: QShortcut | None = None
        self._hotkey_warning_shown = False
        self.update_results: queue.Queue[UpdateCheckResult] = queue.Queue()
        self.update_checker: UpdateChecker | None = None
        self._update_check_started = False
        self._update_prompted = False

        flags = Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        if settings.always_on_top and sys.platform != "win32":
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(300, 240)
        self.setWindowTitle("Sindrome Chat Overlay")
        icon_path = resource_path("assets/icon.png")
        if not icon_path.exists():
            icon_path = resource_path("assets/icon.svg")
        icon = QIcon(str(icon_path))
        self.setWindowIcon(icon)

        self._build_ui()
        self._build_tray(icon)
        self._retranslate_ui(reset_statuses=True)
        self._restore_geometry()
        self._apply_visual_settings()

        self.event_timer = QTimer(self)
        self.event_timer.setInterval(60)
        self.event_timer.timeout.connect(self._drain_events)
        self.event_timer.start()

        self.expiry_timer = QTimer(self)
        self.expiry_timer.setInterval(1_000)
        self.expiry_timer.timeout.connect(self._expire_messages)
        self.expiry_timer.start()

        self.native_state_timer = QTimer(self)
        self.native_state_timer.setInterval(2_500)
        self.native_state_timer.timeout.connect(self._recover_topmost)
        self.native_state_timer.start()

        self.update_result_timer = QTimer(self)
        self.update_result_timer.setInterval(250)
        self.update_result_timer.timeout.connect(self._drain_update_results)

        QTimer.singleShot(0, self._restore_native_state)
        if self.settings.check_for_updates:
            QTimer.singleShot(2_500, self._start_update_check)

        self._restart_providers()
        QTimer.singleShot(150, lambda: self.set_click_through(self.settings.click_through))

    def _register_global_hotkey(self) -> None:
        if self._shutting_down:
            return
        if sys.platform == "win32" and self.global_hotkey.register(int(self.winId())):
            if self._fallback_shortcut is not None:
                self._fallback_shortcut.setEnabled(False)
                self._fallback_shortcut.deleteLater()
                self._fallback_shortcut = None
            self._hotkey_warning_shown = False
            return
        if self._fallback_shortcut is None:
            shortcut = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.activated.connect(self.toggle_click_through)
            self._fallback_shortcut = shortcut
        if (
            sys.platform == "win32"
            and self.tray is not None
            and not self._hotkey_warning_shown
        ):
            self.tray.showMessage(
                self._text("hotkey_unavailable_title"),
                self._text("hotkey_unavailable_message"),
                QSystemTrayIcon.Warning,
                6_000,
            )
            self._hotkey_warning_shown = True

    def _restore_native_state(self) -> None:
        if self._shutting_down:
            return
        self._register_global_hotkey()
        self._apply_native_window_state()

    def _apply_native_window_state(self) -> None:
        if sys.platform != "win32" or self._shutting_down:
            return
        self.native_window.apply(
            int(self.winId()),
            always_on_top=self.settings.always_on_top,
            click_through=self.settings.click_through,
        )

    def _recover_topmost(self) -> None:
        if (
            sys.platform == "win32"
            and self.settings.always_on_top
            and self.isVisible()
            and not self.isMinimized()
            and not self._shutting_down
        ):
            self._apply_native_window_state()

    def _start_update_check(self) -> None:
        if (
            self._shutting_down
            or not self.settings.check_for_updates
            or self._update_check_started
        ):
            return
        self._update_check_started = True
        self.update_results = queue.Queue()
        self.update_checker = UpdateChecker(self.update_results, __version__)
        self.update_checker.start()
        self.update_result_timer.start()

    def _drain_update_results(self) -> None:
        while True:
            try:
                result = self.update_results.get_nowait()
            except queue.Empty:
                break
            if result.status == "update" and result.update is not None:
                self._show_update_prompt(result.update)
            elif result.status == "error":
                self.log.debug("Automatic update check failed: %s", result.error)

        checker = self.update_checker
        if checker is None or not checker.is_alive():
            self.update_result_timer.stop()
            self.update_checker = None

    def _show_update_prompt(self, update: UpdateInfo) -> None:
        if self._shutting_down or self._update_prompted:
            return
        self._update_prompted = True
        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Information)
        prompt.setWindowTitle(self._text("update_available_title"))
        prompt.setText(
            self._text(
                "update_available_message",
                version=update.version,
                current=__version__,
            )
        )
        prompt.setInformativeText(self._text("update_available_details"))
        open_button = prompt.addButton(
            self._text("open_update_page"),
            QMessageBox.AcceptRole,
        )
        prompt.addButton(self._text("later"), QMessageBox.RejectRole)
        prompt.setDefaultButton(open_button)
        prompt.exec()
        if prompt.clickedButton() is open_button and not QDesktopServices.openUrl(
            QUrl(update.release_url)
        ):
            QMessageBox.warning(
                self,
                self._text("update_open_failed_title"),
                self._text("update_open_failed_message"),
            )

    def _stop_update_checker(self) -> None:
        self.update_result_timer.stop()
        checker = self.update_checker
        self.update_checker = None
        if checker is not None:
            checker.stop()
            if checker.is_alive():
                checker.join(timeout=0.5)

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            try:
                message_id, wparam = native_message_values(message)
                if self.global_hotkey.dispatch(message_id, wparam):
                    return True, 0
            except (TypeError, ValueError, OSError):
                pass
        return super().nativeEvent(event_type, message)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._restore_native_state)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and not self.isMinimized():
            QTimer.singleShot(0, self._restore_native_state)

    def _build_ui(self) -> None:
        root = QFrame()
        root.setObjectName("OverlayRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = DragHeader()
        self.header.setObjectName("Header")
        self.header.setCursor(Qt.SizeAllCursor)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 7, 7, 7)
        header_layout.setSpacing(6)

        title_area = QVBoxLayout()
        title_area.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self.title_label = QLabel("Sindrome Chat Overlay")
        self.title_label.setObjectName("AppTitle")
        title_row.addWidget(self.title_label)
        self.drag_indicator = QLabel("⋮⋮")
        self.drag_indicator.setObjectName("DragHandle")
        self.drag_indicator.setAlignment(Qt.AlignCenter)
        self.drag_indicator.setCursor(Qt.SizeAllCursor)
        title_row.addWidget(self.drag_indicator)
        title_row.addStretch(1)
        title_area.addLayout(title_row)

        statuses = QHBoxLayout()
        statuses.setSpacing(9)
        for platform, label in (("twitch", "Twitch"), ("youtube", "YouTube")):
            status = QLabel(f"● {label}")
            status.setObjectName("StatusLabel")
            self.status_labels[platform] = status
            statuses.addWidget(status)
        statuses.addStretch(1)
        title_area.addLayout(statuses)
        header_layout.addLayout(title_area, 1)

        self.clear_button = self._header_button("⌫", "")
        self.clear_button.clicked.connect(self.clear_messages)
        header_layout.addWidget(self.clear_button)

        self.settings_button = self._header_button("⚙", "")
        self.settings_button.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_button)

        self.lock_button = self._header_button("🔓", "")
        self.lock_button.clicked.connect(self.toggle_click_through)
        header_layout.addWidget(self.lock_button)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("CloseButton")
        self.close_button.setCursor(Qt.ArrowCursor)
        self.close_button.clicked.connect(self.close)
        header_layout.addWidget(self.close_button)
        layout.addWidget(self.header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().installEventFilter(self)
        self.message_host = QWidget()
        self.message_layout = QVBoxLayout(self.message_host)
        self.message_layout.setContentsMargins(5, 4, 5, 5)
        self.message_layout.setSpacing(3)

        self.empty_state = QLabel()
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setWordWrap(True)
        self.message_layout.addWidget(self.empty_state)
        self.message_layout.addStretch(1)
        self.scroll.setWidget(self.message_host)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._on_scroll_range_changed)
        layout.addWidget(self.scroll, 1)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 3, 3)
        grip_row.addStretch(1)
        self.size_grip = QSizeGrip(root)
        grip_row.addWidget(self.size_grip)
        layout.addLayout(grip_row)

    @staticmethod
    def _header_button(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("HeaderButton")
        button.setToolTip(tooltip)
        button.setCursor(Qt.ArrowCursor)
        return button

    def _build_tray(self, icon: QIcon) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Sindrome Chat Overlay")
        menu = QMenu()

        self.show_action = QAction(self)
        self.show_action.triggered.connect(self.toggle_visibility)
        menu.addAction(self.show_action)

        self.tray_lock_action = QAction(self)
        self.tray_lock_action.triggered.connect(self.toggle_click_through)
        menu.addAction(self.tray_lock_action)

        self.settings_action = QAction(self)
        self.settings_action.triggered.connect(self._settings_from_tray)
        menu.addAction(self.settings_action)
        menu.addSeparator()

        self.quit_action = QAction(self)
        self.quit_action.triggered.connect(self.close)
        menu.addAction(self.quit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: (
                self.toggle_visibility() if reason == QSystemTrayIcon.DoubleClick else None
            )
        )
        tray.show()
        self.tray = tray

    def _text(self, key: str, **values) -> str:
        return tr(self.settings.language, key, **values)

    def _retranslate_ui(self, *, reset_statuses: bool = False) -> None:
        self.clear_button.setToolTip(self._text("clear_messages"))
        self.settings_button.setToolTip(self._text("open_settings"))
        self.close_button.setToolTip(self._text("close"))
        self.header.setToolTip(self._text("drag_overlay_hint"))
        self.drag_indicator.setToolTip(self._text("drag_overlay_hint"))
        self.empty_state.setText(self._text("empty_state"))
        lock_key = "unlock_clicks" if self.settings.click_through else "lock_clicks"
        self.lock_button.setToolTip(self._text(lock_key))

        if reset_statuses:
            for platform in ("twitch", "youtube"):
                self._set_status(platform, "connecting", self._text("initializing"))

        if self.tray is not None:
            self.tray.setToolTip("Sindrome Chat Overlay")
            self.show_action.setText(self._text("show_hide"))
            self.settings_action.setText(self._text("settings"))
            self.quit_action.setText(self._text("quit"))
            self.tray_lock_action.setText(
                self._text("unlock_clicks")
                if self.settings.click_through
                else self._text("lock_clicks")
            )

    def _restore_geometry(self) -> None:
        self.resize(self.settings.window_width, self.settings.window_height)
        self.move(self.settings.window_x, self.settings.window_y)
        visible = any(
            screen.availableGeometry()
            .adjusted(-80, -80, 80, 80)
            .contains(self.frameGeometry().center())
            for screen in QApplication.screens()
        )
        if not visible:
            screen = QApplication.primaryScreen()
            if screen:
                area = screen.availableGeometry()
                self.move(area.left() + 30, area.top() + 60)

    def _remember_geometry(self) -> None:
        if self.isMaximized() or self.isMinimized():
            return
        self.settings.window_x = self.x()
        self.settings.window_y = self.y()
        self.settings.window_width = self.width()
        self.settings.window_height = self.height()

    def _restart_providers(self) -> None:
        self._stop_providers()
        # Old workers keep their old queue, so late shutdown events cannot overwrite new status.
        self.events = queue.Queue()

        if self.settings.twitch_enabled:
            provider = TwitchProvider(
                self.events,
                self.settings.twitch_channel,
                self.settings.language,
            )
            self.providers.append(provider)
            provider.start()
        else:
            self._set_status("twitch", "disabled", self._text("disabled"))

        if self.settings.youtube_enabled:
            self.youtube_connection_mode = (
                "official_configured"
                if self.settings.youtube_api_key
                else "compatibility"
            )
            provider = YouTubeProvider(
                self.events,
                self.settings.youtube_input,
                self.settings.youtube_api_key,
                self.settings.language,
            )
            self.providers.append(provider)
            provider.start()
        else:
            self.youtube_connection_mode = "disabled"
            self._set_status("youtube", "disabled", self._text("disabled"))

    def _stop_providers(self) -> None:
        old_providers = list(self.providers)
        self.providers.clear()
        for provider in old_providers:
            provider.stop()
        for provider in old_providers:
            if provider.is_alive():
                provider.join(timeout=1.0)
                if provider.is_alive():
                    self.log.warning("%s provider did not stop within one second.", provider.platform)

    def _drain_events(self) -> None:
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event.kind == "message" and event.message is not None:
                self.add_message(event.message)
            elif event.kind == "status":
                if event.platform == "youtube" and event.mode:
                    self.youtube_connection_mode = event.mode
                self._set_status(event.platform, event.state, event.text)
            elif event.kind == "delete" and event.message_id:
                self._remove_message_id(event.message_id)
            elif event.kind == "clear":
                self.clear_messages(event.platform)

    def add_message(self, message: ChatMessage) -> None:
        if self.settings.hide_commands and message.text.lstrip().startswith("!"):
            return
        if message.message_id and message.message_id in self.seen_ids:
            return
        if message.message_id:
            if len(self.seen_order) == self.seen_order.maxlen:
                oldest = self.seen_order.popleft()
                self.seen_ids.discard(oldest)
            self.seen_order.append(message.message_id)
            self.seen_ids.add(message.message_id)
        self.messages.append(message)
        self._append_card(message)
        self._trim_messages()
        self._play_message_sound()

    def _append_card(self, message: ChatMessage) -> None:
        self.empty_state.hide()
        card = MessageCard(
            message,
            self.settings,
            self.twitch_assets,
            self.message_host,
        )
        self.cards.append(card)
        if message.message_id:
            self.cards_by_id[message.message_id] = card
        self.message_layout.insertWidget(self.message_layout.count() - 1, card)
        if self.settings.auto_scroll:
            QTimer.singleShot(0, self._scroll_to_bottom)
            # Word wrapping may change the scroll range after the first layout pass.
            QTimer.singleShot(75, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        if not self.settings.auto_scroll:
            return
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_scroll_range_changed(self, _minimum: int, maximum: int) -> None:
        if self.settings.auto_scroll:
            self.scroll.verticalScrollBar().setValue(maximum)

    def _play_message_sound(self) -> None:
        if not self.settings.sound_enabled:
            return
        if sys.platform == "win32":
            try:
                import winsound

                sound_path = resource_path("assets/message.wav")
                if sound_path.exists():
                    winsound.PlaySound(
                        str(sound_path),
                        winsound.SND_ASYNC | winsound.SND_FILENAME | winsound.SND_NODEFAULT,
                    )
                else:
                    winsound.MessageBeep(winsound.MB_OK)
            except (OSError, RuntimeError) as exc:
                self.log.debug("Unable to play message sound: %s", exc)
        else:
            QApplication.beep()

    def _trim_messages(self) -> None:
        while len(self.messages) > self.settings.max_messages:
            self._remove_at(0)

    def _expire_messages(self) -> None:
        lifetime = self.settings.message_lifetime_seconds
        if lifetime <= 0:
            return
        now = time.monotonic()
        while self.cards and now - self.cards[0].created_monotonic >= lifetime:
            self._remove_at(0)

    def _remove_message_id(self, message_id: str) -> None:
        card = self.cards_by_id.get(message_id)
        if card is None:
            return
        try:
            index = self.cards.index(card)
        except ValueError:
            return
        self._remove_at(index)

    def _remove_at(self, index: int) -> None:
        if index < 0 or index >= len(self.cards):
            return
        card = self.cards.pop(index)
        message = self.messages.pop(index)
        if message.message_id:
            self.cards_by_id.pop(message.message_id, None)
        self.message_layout.removeWidget(card)
        card.deleteLater()
        self.empty_state.setVisible(not self.cards)

    def clear_messages(self, platform: str = "") -> None:
        if not platform:
            while self.cards:
                self._remove_at(len(self.cards) - 1)
            return
        for index in range(len(self.messages) - 1, -1, -1):
            if self.messages[index].platform == platform:
                self._remove_at(index)

    def _rebuild_cards(self) -> None:
        history = list(self.messages)
        while self.cards:
            card = self.cards.pop()
            self.message_layout.removeWidget(card)
            card.deleteLater()
        self.cards_by_id.clear()
        self.messages = []
        for message in history[-self.settings.max_messages :]:
            if self.settings.hide_commands and message.text.lstrip().startswith("!"):
                continue
            self.messages.append(message)
            self._append_card(message)
        self.empty_state.setVisible(not self.cards)

    def _set_status(self, platform: str, state: str, text: str) -> None:
        label = self.status_labels.get(platform)
        if label is None:
            return
        names = {"twitch": "Twitch", "youtube": "YouTube"}
        colours = {
            "connected": "#4BE09A",
            "connecting": "#F5C451",
            "waiting": "#F5C451",
            "error": "#FF6477",
            "stopped": "#7D899E",
            "disabled": "#7D899E",
        }
        colour = colours.get(state, "#AAB5CB")
        label.setText(f"● {names.get(platform, platform)}: {text}")
        label.setStyleSheet(f"color: {colour}; font-size: 11px;")

    def open_settings(self) -> None:
        if self.settings.click_through:
            self.set_click_through(False)
        dialog = SettingsDialog(
            self.settings,
            self,
            youtube_connection_mode=self.youtube_connection_mode,
        )
        dialog.setStyleSheet(build_stylesheet(self.settings))
        if dialog.exec() != SettingsDialog.Accepted:
            return
        self._remember_geometry()
        updated = dialog.settings()
        updated.window_x = self.settings.window_x
        updated.window_y = self.settings.window_y
        updated.window_width = self.settings.window_width
        updated.window_height = self.settings.window_height
        self.settings = updated
        self.store.save(self.settings)
        if not self.settings.check_for_updates:
            self._stop_update_checker()
        else:
            self._start_update_check()
        self._apply_window_flags()
        self._apply_visual_settings()
        self._retranslate_ui(reset_statuses=True)
        self._rebuild_cards()
        self._restart_providers()
        self.set_click_through(self.settings.click_through)

    def _settings_from_tray(self) -> None:
        if not self.isVisible():
            self.show()
        self.set_click_through(False)
        self.raise_()
        self.activateWindow()
        self.open_settings()

    def _apply_visual_settings(self) -> None:
        self.setStyleSheet(build_stylesheet(self.settings))

    def _apply_window_flags(self) -> None:
        if sys.platform == "win32":
            self._apply_native_window_state()
            return
        was_visible = self.isVisible()
        flags = self.windowFlags()
        if self.settings.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def toggle_click_through(self) -> None:
        self.set_click_through(not self.settings.click_through)

    def set_click_through(self, enabled: bool) -> None:
        self.settings.click_through = bool(enabled)
        self.header.setVisible(not enabled)
        self.size_grip.setVisible(not enabled)
        self.lock_button.setText("🔒" if enabled else "🔓")
        self.lock_button.setToolTip(
            self._text("unlock_clicks") if enabled else self._text("lock_clicks")
        )
        if hasattr(self, "tray_lock_action"):
            self.tray_lock_action.setText(
                self._text("unlock_clicks") if enabled else self._text("lock_clicks")
            )
        self._set_native_click_through(enabled)
        try:
            self._remember_geometry()
            self.store.save(self.settings)
        except OSError as exc:
            self.log.warning("Unable to save lock state: %s", exc)
        if enabled and self.tray and self._first_lock_notice:
            self.tray.showMessage(
                self._text("locked_title"),
                self._text("locked_message"),
                QSystemTrayIcon.Information,
                4_000,
            )
            self._first_lock_notice = False

    def _set_native_click_through(self, enabled: bool) -> None:
        if sys.platform != "win32":
            was_visible = self.isVisible()
            self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
            if was_visible:
                self.show()
            return
        self._apply_native_window_state()

    def toggle_visibility(self) -> None:
        if self.isMinimized():
            self.showNormal()
            self._restore_native_state()
            if not self.settings.click_through:
                self.raise_()
                self.activateWindow()
        elif self.isVisible():
            self.hide()
        else:
            self.show()
            self._restore_native_state()
            if not self.settings.click_through:
                self.raise_()
                self.activateWindow()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.scroll.viewport() and event.type() == QEvent.MouseButtonDblClick:
            self.toggle_click_through()
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._shutting_down:
            event.accept()
            return
        self._shutting_down = True
        self.event_timer.stop()
        self.expiry_timer.stop()
        self.native_state_timer.stop()
        self._stop_update_checker()
        self.global_hotkey.unregister()
        if self._fallback_shortcut is not None:
            self._fallback_shortcut.setEnabled(False)
        self._remember_geometry()
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self.log.warning("Unable to save settings on close: %s", exc)
        self._stop_providers()
        self.events = queue.Queue()
        if self.tray:
            self.tray.hide()
        event.accept()
        app = QApplication.instance()
        if app:
            QTimer.singleShot(0, app.quit)
