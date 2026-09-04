from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QStackedWidget

from .. import __version__
from ..diagnostics import export_diagnostics
from ..feature_i18n import feature_tr
from ..obs_source import ObsChatSourceServer, ObsSourceConfig
from ..profiles import (
    apply_overlay_profile,
    iter_profile_choices,
    normalize_profile_ref,
    resolve_profile,
)
from ..settings import Settings, SettingsStore
from .feature_settings_dialog import SettingsDialog
from .message_list import MessageCardDelegate, MessageListModel, VirtualMessageListView
from .overlay import OverlayWindow as _LegacyOverlayWindow
from .theme import build_stylesheet


class OverlayWindow(_LegacyOverlayWindow):
    """Desktop overlay with virtualized messages, OBS source, profiles and diagnostics."""

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        logger: logging.Logger,
    ) -> None:
        self.obs_source = ObsChatSourceServer(logger, self._obs_config(settings))
        super().__init__(settings, store, logger)
        self._sync_obs_source(seed_history=True)

    @staticmethod
    def _obs_config(settings: Settings) -> ObsSourceConfig:
        return ObsSourceConfig(
            port=settings.obs_port,
            max_messages=settings.obs_max_messages,
            font_size=settings.obs_font_size,
            show_platform_labels=settings.obs_show_platform_labels,
            show_badges=settings.obs_show_badges,
            show_timestamps=settings.obs_show_timestamps,
            message_background_opacity=settings.obs_message_background_opacity,
        )

    def _sync_obs_source(self, *, seed_history: bool = False) -> None:
        config = self._obs_config(self.settings).normalized()
        port_changed = self.obs_source.requested_port != config.port
        if port_changed and self.obs_source.running:
            self.obs_source.stop()
        self.obs_source.configure(config)

        if not self.settings.obs_enabled:
            self.obs_source.stop()
            return

        started = self.obs_source.running or self.obs_source.start()
        if not started:
            self.log.warning(
                "OBS browser source is enabled but unavailable on port %s: %s",
                config.port,
                self.obs_source.last_error,
            )
            return
        if seed_history or port_changed:
            self.obs_source.replace_messages(list(self.messages))

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
        self.message_view.setStyleSheet(
            "QListView#VirtualMessageList, QListView#VirtualMessageList::item {"
            "background: transparent; border: none; outline: none; }"
        )
        self.message_view.viewport().setAutoFillBackground(False)
        self.message_delegate = MessageCardDelegate(
            self.settings,
            self.twitch_assets,
            self.message_view,
        )
        self.message_view.setItemDelegate(self.message_delegate)
        self.message_view.viewport().installEventFilter(self)
        self.message_view.verticalScrollBar().rangeChanged.connect(self._on_scroll_range_changed)
        self._scroll_update_pending = False

        self.empty_state = QLabel()
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setWordWrap(True)

        self.message_stack = QStackedWidget(self)
        self.message_stack.setObjectName("MessageStack")
        self.message_stack.setStyleSheet(
            "QStackedWidget#MessageStack { background: transparent; border: none; }"
        )
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

    def _build_tray(self, icon) -> None:
        super()._build_tray(icon)
        self.profile_menu = None
        if self.tray is None:
            return
        menu = self.tray.contextMenu()
        if menu is None:
            return
        self.profile_menu = menu.addMenu("")
        menu.removeAction(self.profile_menu.menuAction())
        menu.insertMenu(self.settings_action, self.profile_menu)
        self._refresh_profile_menu()

    def _retranslate_ui(self, *, reset_statuses: bool = False) -> None:
        super()._retranslate_ui(reset_statuses=reset_statuses)
        if getattr(self, "profile_menu", None) is not None:
            self.profile_menu.setTitle(feature_tr(self.settings.language, "profiles_menu"))
            self._refresh_profile_menu()

    def _refresh_profile_menu(self) -> None:
        menu = getattr(self, "profile_menu", None)
        if menu is None:
            return
        menu.clear()
        custom_started = False
        active = normalize_profile_ref(
            self.settings.active_overlay_profile,
            self.settings.overlay_profiles,
        )
        for profile_ref, label, is_builtin in iter_profile_choices(
            self.settings.overlay_profiles,
            self.settings.language,
        ):
            if not is_builtin and not custom_started:
                menu.addSeparator()
                custom_started = True
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(profile_ref == active)
            action.triggered.connect(
                lambda _checked=False, ref=profile_ref: self._apply_overlay_profile_ref(ref)
            )
            menu.addAction(action)

    def _apply_overlay_profile_ref(self, profile_ref: str) -> None:
        values = resolve_profile(profile_ref, self.settings.overlay_profiles)
        if values is None:
            return
        self._remember_geometry()
        updated = apply_overlay_profile(self.settings, values)
        updated.active_overlay_profile = profile_ref
        self.settings = updated
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self.log.warning("Unable to save overlay profile selection: %s", exc)

        self._restore_geometry()
        self._apply_window_flags()
        self._apply_visual_settings()
        self._retranslate_ui()
        self._rebuild_cards()
        self._refresh_profile_menu()

    def open_settings(self) -> None:
        if self.settings.click_through:
            self.set_click_through(False)
        # Capture the actual current window geometry before a custom profile can be saved.
        self._remember_geometry()
        dialog = SettingsDialog(
            self.settings,
            self,
            youtube_connection_mode=self.youtube_connection_mode,
            obs_source_url=self.obs_source.url if self.obs_source.running else "",
        )
        dialog.diagnostics_requested.connect(lambda: self._export_diagnostics(dialog))
        dialog.setStyleSheet(build_stylesheet(self.settings))
        if dialog.exec() != SettingsDialog.Accepted:
            return

        updated = dialog.settings()
        self.settings = updated
        self.store.save(self.settings)
        self._sync_obs_source(seed_history=True)
        self.notification_sounds.reset_limit()
        if not self.settings.check_for_updates:
            self._stop_update_checker()
        else:
            self._start_update_check()
        self._restore_geometry()
        self._apply_window_flags()
        self._apply_visual_settings()
        self._retranslate_ui(reset_statuses=True)
        self._rebuild_cards()
        self._restart_providers()
        self.set_click_through(self.settings.click_through)
        self._refresh_profile_menu()

    def _export_diagnostics(self, parent=None) -> None:
        downloads = Path.home() / "Downloads"
        folder = downloads if downloads.is_dir() else Path.home()
        filename = f"SindromeChatOverlay-Diagnostic-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        destination, _selected_filter = QFileDialog.getSaveFileName(
            parent or self,
            feature_tr(self.settings.language, "diagnostic_save_title"),
            str(folder / filename),
            "ZIP (*.zip)",
        )
        if not destination:
            return
        try:
            saved = export_diagnostics(
                Path(destination),
                self.settings,
                self._diagnostic_runtime(),
                app_version=__version__,
            )
        except Exception as exc:  # noqa: BLE001 - support export UI boundary
            self.log.warning("Unable to export diagnostic package: %s", exc)
            QMessageBox.warning(
                parent or self,
                feature_tr(self.settings.language, "diagnostic_failed_title"),
                feature_tr(
                    self.settings.language,
                    "diagnostic_failed_message",
                    error=str(exc),
                ),
            )
            return
        QMessageBox.information(
            parent or self,
            feature_tr(self.settings.language, "diagnostic_saved_title"),
            feature_tr(
                self.settings.language,
                "diagnostic_saved_message",
                path=str(saved),
            ),
        )

    def _diagnostic_runtime(self) -> dict[str, object]:
        obs_snapshot = self.obs_source.snapshot()
        return {
            "youtube_connection_mode": self.youtube_connection_mode,
            "providers": [provider.platform for provider in self.providers],
            "message_count": len(self.messages),
            "active_message_cards": self.message_view.active_editor_count,
            "global_hotkey_registered": bool(self.global_hotkey.is_registered),
            "always_on_top": self.settings.always_on_top,
            "click_through": self.settings.click_through,
            "visible": self.isVisible(),
            "minimized": self.isMinimized(),
            "window_width": self.width(),
            "window_height": self.height(),
            "obs_source_enabled": self.settings.obs_enabled,
            "obs_source_running": self.obs_source.running,
            "obs_source_port": self.obs_source.bound_port or self.settings.obs_port,
            "obs_source_message_count": len(obs_snapshot.get("messages", [])),
            "statuses": {
                platform: label.text()
                for platform, label in self.status_labels.items()
            },
        }

    def _append_card(self, message) -> None:
        # OverlayWindow.add_message already appended to self.messages before this call.
        self.message_model.append_message(message)
        if self.settings.obs_enabled and self.obs_source.running:
            self.obs_source.publish_message(message)
        self._update_empty_state()
        self.message_view.schedule_editor_refresh()
        self._schedule_scroll_to_bottom()

    def _schedule_scroll_to_bottom(self) -> None:
        if not self.settings.auto_scroll or self._scroll_update_pending:
            return
        self._scroll_update_pending = True
        QTimer.singleShot(0, self._run_scheduled_scroll)

    def _run_scheduled_scroll(self) -> None:
        self._scroll_update_pending = False
        self._scroll_to_bottom()

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
            # OBS history is intentionally independent from desktop expiry.
            self._remove_at(0)

    def _remove_message_id(self, message_id: str) -> None:
        self.obs_source.remove_message(message_id)
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
        self.obs_source.clear_messages(platform)
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
        if filtered:
            self._schedule_scroll_to_bottom()

    def _update_empty_state(self) -> None:
        if self.messages:
            self.message_stack.setCurrentWidget(self.message_view)
        else:
            self.message_stack.setCurrentWidget(self.empty_state)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.obs_source.stop()
        super().closeEvent(event)
