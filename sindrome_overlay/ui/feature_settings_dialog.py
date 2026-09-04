from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
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
    """Desktop settings dialog extended with overlay profiles and diagnostics."""

    diagnostics_requested = Signal()

    def __init__(self, *args, **kwargs) -> None:
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
        return settings.normalized()

    def _restore_defaults(self) -> None:
        super()._restore_defaults()
        self._active_profile_ref = ""
        if hasattr(self, "profile_combo"):
            self._reload_profile_combo()
