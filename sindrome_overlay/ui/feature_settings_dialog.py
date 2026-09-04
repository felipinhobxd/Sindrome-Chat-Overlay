from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..feature_i18n import feature_tr
from ..profiles import (
    MAX_CUSTOM_PROFILES,
    capture_overlay_profile,
    iter_profile_choices,
    normalize_custom_profiles,
    normalize_profile_name,
    normalize_profile_ref,
    resolve_profile,
)
from .settings_dialog import SettingsDialog as _BaseSettingsDialog


class SettingsDialog(_BaseSettingsDialog):
    """Desktop settings dialog extended with profiles, OBS source and diagnostics."""

    diagnostics_requested = Signal()

    def __init__(self, *args, **kwargs) -> None:
        self._obs_source_url = str(kwargs.pop("obs_source_url", "") or "")
        super().__init__(*args, **kwargs)
        self._profiles = normalize_custom_profiles(deepcopy(self._current.overlay_profiles))
        self._active_profile_ref = normalize_profile_ref(
            self._current.active_overlay_profile,
            self._profiles,
        )
        self._applying_profile = False

        tabs = self.findChild(QTabWidget)
        if tabs is not None:
            tabs.addTab(self._profiles_tab(), self._feature_text("profiles"))
            tabs.addTab(self._obs_tab(), self._feature_text("obs_source"))
            tabs.addTab(self._diagnostics_tab(), self._feature_text("diagnostics"))

    def _feature_text(self, key: str, **values) -> str:
        return feature_tr(self._current.language, key, **values)

    def _profiles_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        help_label = QLabel(self._feature_text("profiles_help"))
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        layout.addWidget(help_label)

        group = QGroupBox(self._feature_text("profiles"))
        group_layout = QVBoxLayout(group)
        row = QHBoxLayout()
        row.addWidget(QLabel(self._feature_text("profile")))
        self.profile_combo = QComboBox()
        row.addWidget(self.profile_combo, 1)
        self.profile_apply_button = QPushButton(self._feature_text("profile_apply"))
        self.profile_apply_button.setObjectName("ActionButton")
        self.profile_apply_button.clicked.connect(self._apply_selected_profile)
        row.addWidget(self.profile_apply_button)
        group_layout.addLayout(row)

        actions = QHBoxLayout()
        self.profile_save_button = QPushButton(self._feature_text("profile_save_current"))
        self.profile_save_button.setObjectName("ActionButton")
        self.profile_save_button.clicked.connect(self._prompt_save_profile)
        actions.addWidget(self.profile_save_button)
        self.profile_delete_button = QPushButton(self._feature_text("profile_delete"))
        self.profile_delete_button.clicked.connect(self._delete_selected_profile)
        actions.addWidget(self.profile_delete_button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group)
        layout.addStretch(1)

        self.profile_combo.currentIndexChanged.connect(self._update_profile_buttons)
        self._reload_profile_combo(self._active_profile_ref)
        self._connect_profile_change_tracking()
        return tab

    def _obs_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        help_label = QLabel(self._feature_text("obs_source_help"))
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        layout.addWidget(help_label)

        self.obs_enabled = QCheckBox(self._feature_text("obs_enable"))
        self.obs_enabled.setChecked(self._current.obs_enabled)
        layout.addWidget(self.obs_enabled)

        url_group = QGroupBox(self._feature_text("obs_source"))
        url_layout = QVBoxLayout(url_group)
        url_layout.addWidget(QLabel(self._feature_text("obs_url")))
        url_row = QHBoxLayout()
        self.obs_url = QLineEdit()
        self.obs_url.setObjectName("ObsBrowserSourceUrl")
        self.obs_url.setReadOnly(True)
        url_row.addWidget(self.obs_url, 1)
        self.obs_copy_button = QPushButton(self._feature_text("obs_copy_url"))
        self.obs_copy_button.setObjectName("ActionButton")
        self.obs_copy_button.clicked.connect(self._copy_obs_url)
        url_row.addWidget(self.obs_copy_button)
        self.obs_open_button = QPushButton(self._feature_text("obs_open_test"))
        self.obs_open_button.clicked.connect(self._open_obs_test)
        url_row.addWidget(self.obs_open_button)
        url_layout.addLayout(url_row)
        layout.addWidget(url_group)

        options = QGroupBox(self._feature_text("obs_source"))
        options_layout = QVBoxLayout(options)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel(self._feature_text("obs_port")))
        self.obs_port = QSpinBox()
        self.obs_port.setRange(1024, 65535)
        self.obs_port.setValue(self._current.obs_port)
        port_row.addWidget(self.obs_port)
        port_row.addStretch(1)
        options_layout.addLayout(port_row)

        history_row = QHBoxLayout()
        history_row.addWidget(QLabel(self._feature_text("obs_max_messages")))
        self.obs_max_messages = QSpinBox()
        self.obs_max_messages.setRange(20, 500)
        self.obs_max_messages.setValue(self._current.obs_max_messages)
        history_row.addWidget(self.obs_max_messages)
        history_row.addStretch(1)
        options_layout.addLayout(history_row)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel(self._feature_text("obs_font_size")))
        self.obs_font_size = QSpinBox()
        self.obs_font_size.setRange(11, 40)
        self.obs_font_size.setSuffix(" px")
        self.obs_font_size.setValue(self._current.obs_font_size)
        font_row.addWidget(self.obs_font_size)
        font_row.addStretch(1)
        options_layout.addLayout(font_row)

        background_row = QHBoxLayout()
        background_row.addWidget(QLabel(self._feature_text("obs_background")))
        self.obs_background = QSpinBox()
        self.obs_background.setRange(0, 100)
        self.obs_background.setSuffix(" %")
        self.obs_background.setValue(self._current.obs_message_background_opacity)
        background_row.addWidget(self.obs_background)
        background_row.addStretch(1)
        options_layout.addLayout(background_row)

        self.obs_show_platform = QCheckBox(self._feature_text("obs_show_platform"))
        self.obs_show_platform.setChecked(self._current.obs_show_platform_labels)
        options_layout.addWidget(self.obs_show_platform)
        self.obs_show_badges = QCheckBox(self._feature_text("obs_show_badges"))
        self.obs_show_badges.setChecked(self._current.obs_show_badges)
        options_layout.addWidget(self.obs_show_badges)
        self.obs_show_timestamps = QCheckBox(self._feature_text("obs_show_timestamps"))
        self.obs_show_timestamps.setChecked(self._current.obs_show_timestamps)
        options_layout.addWidget(self.obs_show_timestamps)

        restart_note = QLabel(self._feature_text("obs_restart_note"))
        restart_note.setWordWrap(True)
        restart_note.setStyleSheet("color: #AAB5CB; font-size: 11px;")
        options_layout.addWidget(restart_note)
        layout.addWidget(options)
        layout.addStretch(1)

        self.obs_port.valueChanged.connect(self._update_obs_url_preview)
        self._update_obs_url_preview()
        return tab

    def _obs_url_from_controls(self) -> str:
        port = int(self.obs_port.value()) if hasattr(self, "obs_port") else self._current.obs_port
        if self._obs_source_url:
            try:
                current_port = QUrl(self._obs_source_url).port()
            except (TypeError, ValueError):
                current_port = -1
            if current_port == port:
                return self._obs_source_url
        return f"http://127.0.0.1:{port}/obs-chat"

    def _update_obs_url_preview(self, *_args) -> None:
        if hasattr(self, "obs_url"):
            self.obs_url.setText(self._obs_url_from_controls())

    def _copy_obs_url(self) -> None:
        QApplication.clipboard().setText(self._obs_url_from_controls())

    def _open_obs_test(self) -> None:
        QDesktopServices.openUrl(QUrl(self._obs_url_from_controls()))

    def _diagnostics_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        help_label = QLabel(self._feature_text("diagnostics_help"))
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        layout.addWidget(help_label)
        export_button = QPushButton(self._feature_text("export_diagnostics"))
        export_button.setObjectName("ActionButton")
        export_button.clicked.connect(self.diagnostics_requested.emit)
        layout.addWidget(export_button)
        layout.addStretch(1)
        self.export_diagnostics_button = export_button
        return tab

    def _reload_profile_combo(self, selected_ref: str = "") -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        choices = iter_profile_choices(self._profiles, self._current.language)
        custom_started = False
        for profile_ref, label, is_builtin in choices:
            if not is_builtin and not custom_started:
                self.profile_combo.insertSeparator(self.profile_combo.count())
                custom_started = True
            self.profile_combo.addItem(label, profile_ref)
        target = selected_ref or self._active_profile_ref
        index = self.profile_combo.findData(target)
        if index < 0:
            index = 0 if self.profile_combo.count() else -1
        self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self._update_profile_buttons()

    def _selected_profile_ref(self) -> str:
        return str(self.profile_combo.currentData() or "")

    def _update_profile_buttons(self, *_args) -> None:
        ref = self._selected_profile_ref()
        self.profile_delete_button.setEnabled(ref.startswith("custom:"))
        self.profile_apply_button.setEnabled(bool(resolve_profile(ref, self._profiles)))

    def _apply_selected_profile(self) -> None:
        profile_ref = self._selected_profile_ref()
        values = resolve_profile(profile_ref, self._profiles)
        if values is None:
            return
        self._applying_profile = True
        try:
            setters = {
                "always_on_top": self.always_on_top.setChecked,
                "background_opacity": self.background_opacity.setValue,
                "card_opacity": self.card_opacity.setValue,
                "font_size": self.font_size.setValue,
                "max_messages": self.max_messages.setValue,
                "message_lifetime_seconds": self.lifetime.setValue,
                "auto_scroll": self.auto_scroll.setChecked,
                "show_timestamps": self.show_timestamps.setChecked,
                "show_platform_labels": self.show_platform.setChecked,
                "hide_commands": self.hide_commands.setChecked,
            }
            for field_name, setter in setters.items():
                if field_name in values:
                    setter(values[field_name])
            for field_name in ("window_x", "window_y", "window_width", "window_height"):
                if field_name in values:
                    setattr(self._current, field_name, int(values[field_name]))
            self._active_profile_ref = profile_ref
        finally:
            self._applying_profile = False
        self._reload_profile_combo(profile_ref)

    def _connect_profile_change_tracking(self) -> None:
        for checkbox in (
            self.always_on_top,
            self.auto_scroll,
            self.show_timestamps,
            self.show_platform,
            self.hide_commands,
        ):
            checkbox.toggled.connect(self._profile_controls_changed)
        for spin_or_slider in (
            self.background_opacity,
            self.card_opacity,
            self.font_size,
            self.max_messages,
            self.lifetime,
        ):
            spin_or_slider.valueChanged.connect(self._profile_controls_changed)

    def _profile_controls_changed(self, *_args) -> None:
        if self._applying_profile:
            return
        self._active_profile_ref = ""

    def _prompt_save_profile(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            self._feature_text("profile_name_title"),
            self._feature_text("profile_name_prompt"),
        )
        if not accepted:
            return
        normalized = normalize_profile_name(name)
        if not normalized:
            QMessageBox.warning(
                self,
                self._feature_text("profile_name_title"),
                self._feature_text("profile_invalid_name"),
            )
            return
        if normalized not in self._profiles and len(self._profiles) >= MAX_CUSTOM_PROFILES:
            QMessageBox.warning(
                self,
                self._feature_text("profile_name_title"),
                self._feature_text("profile_limit", count=MAX_CUSTOM_PROFILES),
            )
            return
        if normalized in self._profiles:
            choice = QMessageBox.question(
                self,
                self._feature_text("profile_exists_title"),
                self._feature_text("profile_exists_message", name=normalized),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                return
        self._save_profile_named(normalized)

    def _save_profile_named(self, name: str) -> bool:
        normalized = normalize_profile_name(name)
        if not normalized:
            return False
        if normalized not in self._profiles and len(self._profiles) >= MAX_CUSTOM_PROFILES:
            return False
        current = replace(self._current)
        current.always_on_top = self.always_on_top.isChecked()
        current.background_opacity = self.background_opacity.value()
        current.card_opacity = self.card_opacity.value()
        current.font_size = self.font_size.value()
        current.max_messages = self.max_messages.value()
        current.message_lifetime_seconds = self.lifetime.value()
        current.auto_scroll = self.auto_scroll.isChecked()
        current.show_timestamps = self.show_timestamps.isChecked()
        current.show_platform_labels = self.show_platform.isChecked()
        current.hide_commands = self.hide_commands.isChecked()
        self._profiles[normalized] = capture_overlay_profile(current)
        self._profiles = normalize_custom_profiles(self._profiles)
        self._active_profile_ref = f"custom:{normalized}"
        self._reload_profile_combo(self._active_profile_ref)
        return normalized in self._profiles

    def _delete_selected_profile(self) -> None:
        profile_ref = self._selected_profile_ref()
        if not profile_ref.startswith("custom:"):
            return
        name = profile_ref.removeprefix("custom:")
        choice = QMessageBox.question(
            self,
            self._feature_text("profile_delete_title"),
            self._feature_text("profile_delete_message", name=name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if choice != QMessageBox.Yes:
            return
        self._profiles.pop(name, None)
        if self._active_profile_ref == profile_ref:
            self._active_profile_ref = ""
        self._reload_profile_combo()

    def settings(self):
        settings = super().settings()
        settings.overlay_profiles = deepcopy(self._profiles)
        settings.active_overlay_profile = self._active_profile_ref
        settings.obs_enabled = self.obs_enabled.isChecked()
        settings.obs_port = self.obs_port.value()
        settings.obs_max_messages = self.obs_max_messages.value()
        settings.obs_font_size = self.obs_font_size.value()
        settings.obs_show_platform_labels = self.obs_show_platform.isChecked()
        settings.obs_show_badges = self.obs_show_badges.isChecked()
        settings.obs_show_timestamps = self.obs_show_timestamps.isChecked()
        settings.obs_message_background_opacity = self.obs_background.value()
        return settings.normalized()

    def _restore_defaults(self) -> None:
        super()._restore_defaults()
        self._active_profile_ref = ""
        if hasattr(self, "profile_combo"):
            self._reload_profile_combo()
        if hasattr(self, "obs_enabled"):
            from ..settings import Settings

            defaults = Settings()
            self.obs_enabled.setChecked(defaults.obs_enabled)
            self.obs_port.setValue(defaults.obs_port)
            self.obs_max_messages.setValue(defaults.obs_max_messages)
            self.obs_font_size.setValue(defaults.obs_font_size)
            self.obs_show_platform.setChecked(defaults.obs_show_platform_labels)
            self.obs_show_badges.setChecked(defaults.obs_show_badges)
            self.obs_show_timestamps.setChecked(defaults.obs_show_timestamps)
            self.obs_background.setValue(defaults.obs_message_background_opacity)
            self._update_obs_url_preview()
