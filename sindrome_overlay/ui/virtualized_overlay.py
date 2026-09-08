from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QStackedWidget

from .. import __version__
from ..diagnostics import export_diagnostics
from ..feature_i18n import feature_tr
from ..game_profiles import WindowsGameDetector
from ..obs_source import ObsChatSourceServer, ObsSourceConfig
from ..profiles import (
    apply_overlay_profile,
    capture_overlay_profile,
    iter_profile_choices,
    normalize_profile_ref,
    resolve_profile,
)
from ..settings import Settings, SettingsStore
from .settings_dialog import SettingsDialog as _BaseSettingsDialog
from .feature_settings_dialog import SettingsDialog
from .message_list import MessageCardDelegate, MessageListModel, VirtualMessageListView
from .overlay import OverlayShell


class OverlayWindow(OverlayShell):
    """Desktop overlay with virtualized messages, OBS source, profiles and diagnostics."""

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        logger: logging.Logger,
    ) -> None:
        self._game_detector = WindowsGameDetector()
        self._automatic_baseline: tuple[dict[str, Any], str] | None = None
        self._automatic_ref = ""
        self.obs_source = ObsChatSourceServer(logger, self._obs_config(settings))
        super().__init__(settings, store, logger)
        self._sync_obs_source(seed_history=True)
        self._automatic_timer = QTimer(self)
        self._automatic_timer.setInterval(1000)
        self._automatic_timer.timeout.connect(self._poll_game_profile)
        self.destroyed.connect(self._game_detector.close)
        self._configure_automatic_profiles()

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

    def _build_message_area(self, layout) -> None:
        """Build the virtualized feed; the shell only provides the frame around it."""
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
        # Register the scroll area before any event filter can fire: on Windows
        # synchronous layout events reach eventFilter() during addWidget/show,
        # while the legacy `self.scroll` alias is only assigned below.
        self._message_scroll = self.message_view
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
        layout.addWidget(self.message_stack, 1)

    def _settings_dialog_class(self) -> type[_BaseSettingsDialog]:
        return SettingsDialog

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
        profile_menu = getattr(self, "profile_menu", None)
        if profile_menu is not None:
            profile_menu.setTitle(feature_tr(self.settings.language, "profiles_menu"))
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
        menu.addSeparator()
        automatic = QAction(feature_tr(self.settings.language, "automatic_profiles_enable"), menu)
        automatic.setCheckable(True)
        automatic.setChecked(self.settings.automatic_profiles_enabled)
        automatic.setEnabled(self._game_detector.available and bool(self.settings.game_profiles))
        automatic.triggered.connect(self._set_automatic_profiles_enabled)
        menu.addAction(automatic)

    def _apply_overlay_profile_ref(self, profile_ref: str) -> None:
        values = resolve_profile(profile_ref, self.settings.overlay_profiles)
        if values is None:
            return
        # An explicit manual selection wins until automation is enabled again.
        self.settings.automatic_profiles_enabled = False
        self._configure_automatic_profiles()
        self._remember_geometry()
        updated = apply_overlay_profile(self.settings, values)
        updated.active_overlay_profile = profile_ref
        self.settings = updated
        try:
            self.store.save(self._settings_for_save())
        except OSError as exc:
            self.log.warning("Unable to save overlay profile selection: %s", exc)

        self._present_profile()

    def _present_profile(self) -> None:
        self._restore_geometry()
        self._apply_window_flags()
        self._apply_visual_settings()
        self._retranslate_ui()
        self._rebuild_cards()
        self._refresh_profile_menu()

    def _settings_for_save(self) -> Settings:
        # Hotkeys and click-through also save settings. Never persist the
        # temporary game layout, even through those paths or after a crash.
        if self._automatic_baseline is None:
            return self.settings
        values, ref = self._automatic_baseline
        saved = apply_overlay_profile(self.settings, values)
        saved.active_overlay_profile = ref
        return saved

    def _restore_automatic_profile(self) -> None:
        if self._automatic_baseline is None:
            return
        self.settings = self._settings_for_save()
        self._automatic_baseline = None
        self._automatic_ref = ""
        self._present_profile()

    def _configure_automatic_profiles(self) -> None:
        enabled = (
            self.settings.automatic_profiles_enabled
            and self._game_detector.available
            and bool(self.settings.game_profiles)
        )
        if enabled:
            self._automatic_timer.start()
        else:
            self._automatic_timer.stop()
            self._game_detector.close()
            self._restore_automatic_profile()

    def _set_automatic_profiles_enabled(self, enabled: bool) -> None:
        self.settings.automatic_profiles_enabled = enabled
        self._configure_automatic_profiles()
        try:
            self.store.save(self._settings_for_save())
        except OSError as exc:
            self.log.warning("Unable to save automatic profile preference: %s", exc)
        self._refresh_profile_menu()

    def _poll_game_profile(self) -> None:
        if self._shutting_down or not self.settings.automatic_profiles_enabled:
            return
        ref = self._game_detector.profile(self.settings.game_profiles)
        if ref == self._automatic_ref:
            return
        values = resolve_profile(ref, self.settings.overlay_profiles)
        if values is None:
            self._restore_automatic_profile()
            return
        if self._automatic_baseline is None:
            self._remember_geometry()
            self._automatic_baseline = (
                capture_overlay_profile(self.settings), self.settings.active_overlay_profile,
            )
        # Every game starts from the original layout, so partial profiles do
        # not inherit the previous game's position or appearance.
        self.settings = apply_overlay_profile(self._settings_for_save(), values)
        self.settings.active_overlay_profile = ref
        self._automatic_ref = ref
        self._present_profile()

    def open_settings(self) -> None:
        self._automatic_timer.stop()
        self._restore_automatic_profile()
        try:
            super().open_settings()
        finally:
            if not self._shutting_down:
                self._configure_automatic_profiles()

    def _before_settings_dialog(self) -> None:
        # Capture the actual current window geometry before a custom profile can be saved.
        self._remember_geometry()

    def _settings_dialog_extras(self) -> dict:
        return {"obs_source_url": self.obs_source.url if self.obs_source.running else ""}

    def _connect_settings_dialog(self, dialog: _BaseSettingsDialog) -> None:
        dialog.diagnostics_requested.connect(lambda: self._export_diagnostics(dialog))

    def _settings_applied(self) -> None:
        # Runs after _rebuild_cards, so the OBS history is seeded from the
        # already-filtered message list instead of publishing rows the desktop
        # filtered away.
        self._sync_obs_source(seed_history=True)
        self._restore_geometry()
        self._refresh_profile_menu()

        self._configure_automatic_profiles()

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

    # --- Feed hook implementations -----------------------------------------

    def _append_card(self, message) -> None:
        # OverlayShell.add_message already appended to self.messages before this call.
        self.message_model.append_message(message)
        if self.settings.obs_enabled and self.obs_source.running:
            self.obs_source.publish_message(message)
        self._update_empty_state()
        self.message_view.schedule_editor_refresh()
        self._schedule_scroll_to_bottom()

    def _detach_message(self, index: int) -> None:
        self.message_model.remove_at(index)
        self.message_view.schedule_editor_refresh()

    def _replace_feed(self, messages) -> None:
        self.message_delegate.set_settings(self.settings)
        self.message_model.replace_messages(messages)
        self.message_view.refresh_virtualization()
        if messages:
            self._schedule_scroll_to_bottom()

    def _clear_feed(self, platform: str) -> None:
        self.obs_source.clear_messages(platform)
        if not platform:
            self.message_model.clear()

    def _update_empty_state(self) -> None:
        if self.messages:
            self.message_stack.setCurrentWidget(self.message_view)
        else:
            self.message_stack.setCurrentWidget(self.empty_state)

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

    def _remove_message_id(self, message_id: str) -> None:
        self.obs_source.remove_message(message_id)
        super()._remove_message_id(message_id)

    def _remove_author_id(self, author_id: str) -> None:
        # Ban/timeout: drop the banned account's history here and in the OBS
        # browser source.
        self.obs_source.remove_by_author(author_id)
        super()._remove_author_id(author_id)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._automatic_timer.stop()
        self._game_detector.close()
        self._restore_automatic_profile()
        self.obs_source.stop()
        super().closeEvent(event)
