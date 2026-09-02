from __future__ import annotations

import queue
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, tr
from ..settings import Settings
from ..youtube_key import YouTubeKeyValidationResult, YouTubeKeyValidator


class SettingsDialog(QDialog):
    def __init__(
        self,
        current: Settings,
        parent: QWidget | None = None,
        *,
        youtube_connection_mode: str = "",
    ) -> None:
        super().__init__(parent)
        self._current = replace(current)
        self._initial_youtube_api_key = self._current.youtube_api_key.strip()
        self._youtube_connection_mode = youtube_connection_mode
        self._key_validation_state = ""
        self._validation_request_id = 0
        self._validation_results: queue.Queue[YouTubeKeyValidationResult] = queue.Queue()
        self._validator: YouTubeKeyValidator | None = None

        self._validation_debounce = QTimer(self)
        self._validation_debounce.setSingleShot(True)
        self._validation_debounce.setInterval(700)
        self._validation_debounce.timeout.connect(self._start_youtube_key_validation)
        self._validation_result_timer = QTimer(self)
        self._validation_result_timer.setInterval(80)
        self._validation_result_timer.timeout.connect(self._drain_validation_results)

        self.setWindowTitle(self._text("settings_title"))
        self.resize(660, 630)

        root = QVBoxLayout(self)

        language_form = QFormLayout()
        self.language_combo = QComboBox()
        for code in SUPPORTED_LANGUAGES:
            self.language_combo.addItem(LANGUAGE_LABELS[code], code)
        current_index = self.language_combo.findData(self._current.language)
        self.language_combo.setCurrentIndex(max(0, current_index))
        language_form.addRow(self._text("language"), self.language_combo)
        root.addLayout(language_form)

        language_hint = QLabel(self._text("language_hint"))
        language_hint.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        root.addWidget(language_hint)

        tabs = QTabWidget()
        tabs.addTab(self._channels_tab(), self._text("channels"))
        tabs.addTab(self._appearance_tab(), self._text("appearance"))
        root.addWidget(tabs)

        hint = QLabel(self._text("global_shortcut_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        root.addWidget(hint)

        actions = QHBoxLayout()
        defaults = QPushButton(self._text("restore_defaults"))
        defaults.setObjectName("ActionButton")
        defaults.clicked.connect(self._restore_defaults)
        actions.addWidget(defaults)
        actions.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        self.buttons.button(QDialogButtonBox.Save).setText(self._text("save"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(self._text("cancel"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        actions.addWidget(self.buttons)
        root.addLayout(actions)

        QTimer.singleShot(0, self._sync_initial_youtube_status)

    def _text(self, key: str) -> str:
        return tr(self._current.language, key)

    def _channels_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        twitch_box = QGroupBox("Twitch")
        twitch_form = QFormLayout(twitch_box)
        self.twitch_enabled = QCheckBox(self._text("show_twitch_messages"))
        self.twitch_enabled.setChecked(self._current.twitch_enabled)
        self.twitch_channel = QLineEdit(self._current.twitch_channel)
        self.twitch_channel.setPlaceholderText(self._text("twitch_placeholder"))
        twitch_form.addRow(self.twitch_enabled)
        twitch_form.addRow(self._text("channel"), self.twitch_channel)
        twitch_note = QLabel(self._text("twitch_readonly_note"))
        twitch_note.setWordWrap(True)
        twitch_note.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        twitch_form.addRow(twitch_note)
        layout.addWidget(twitch_box)

        youtube_box = QGroupBox("YouTube")
        youtube_form = QFormLayout(youtube_box)
        youtube_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.youtube_enabled = QCheckBox(self._text("show_youtube_chat"))
        self.youtube_enabled.setChecked(self._current.youtube_enabled)
        self.youtube_input = QLineEdit(self._current.youtube_input)
        self.youtube_input.setPlaceholderText(self._text("youtube_placeholder"))

        self.youtube_status_card = QFrame()
        self.youtube_status_card.setObjectName("YouTubeStatusCard")
        status_layout = QVBoxLayout(self.youtube_status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(3)
        self.youtube_status_title = QLabel()
        self.youtube_status_title.setObjectName("YouTubeStatusTitle")
        self.youtube_status_detail = QLabel()
        self.youtube_status_detail.setObjectName("YouTubeStatusDetail")
        self.youtube_status_detail.setWordWrap(True)
        status_layout.addWidget(self.youtube_status_title)
        status_layout.addWidget(self.youtube_status_detail)

        self.youtube_advanced_button = QPushButton()
        self.youtube_advanced_button.setObjectName("AdvancedSettingsButton")
        self.youtube_advanced_button.setCheckable(True)
        self.youtube_advanced_button.setChecked(False)
        self.youtube_advanced_button.toggled.connect(self._toggle_youtube_advanced)

        self.youtube_advanced_panel = QFrame()
        self.youtube_advanced_panel.setObjectName("YouTubeAdvancedPanel")
        advanced_layout = QVBoxLayout(self.youtube_advanced_panel)
        advanced_layout.setContentsMargins(12, 11, 12, 11)
        advanced_layout.setSpacing(7)
        api_key_label = QLabel(self._text("youtube_data_api_key_optional"))
        api_key_label.setObjectName("AdvancedFieldTitle")

        key_row = QWidget()
        key_row_layout = QHBoxLayout(key_row)
        key_row_layout.setContentsMargins(0, 0, 0, 0)
        key_row_layout.setSpacing(6)
        self.youtube_api_key = QLineEdit(self._current.youtube_api_key)
        self.youtube_api_key.setEchoMode(QLineEdit.Password)
        self.youtube_api_key.setPlaceholderText(self._text("optional"))
        self.youtube_reveal_button = QToolButton()
        self.youtube_reveal_button.setObjectName("RevealKeyButton")
        self.youtube_reveal_button.setText("👁")
        self.youtube_reveal_button.setCheckable(True)
        self.youtube_reveal_button.setToolTip(self._text("show_api_key"))
        self.youtube_reveal_button.toggled.connect(self._toggle_api_key_visibility)
        key_row_layout.addWidget(self.youtube_api_key, 1)
        key_row_layout.addWidget(self.youtube_reveal_button)

        key_description = QLabel(self._text("youtube_key_description"))
        key_description.setObjectName("AdvancedHelpText")
        key_description.setWordWrap(True)
        key_clarification = QLabel(self._text("youtube_key_clarification"))
        key_clarification.setObjectName("AdvancedHelpText")
        key_clarification.setWordWrap(True)
        advanced_layout.addWidget(api_key_label)
        advanced_layout.addWidget(key_row)
        advanced_layout.addWidget(key_description)
        advanced_layout.addWidget(key_clarification)
        self.youtube_advanced_panel.hide()

        youtube_form.addRow(self.youtube_enabled)
        youtube_form.addRow(self._text("channel_or_live"), self.youtube_input)
        youtube_form.addRow(self.youtube_status_card)
        youtube_form.addRow(self.youtube_advanced_button)
        youtube_form.addRow(self.youtube_advanced_panel)
        self.youtube_api_key.textChanged.connect(self._on_youtube_api_key_changed)
        self._update_advanced_button_text(False)
        layout.addWidget(youtube_box)
        layout.addStretch(1)
        return tab

    def _appearance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.always_on_top = QCheckBox(self._text("always_on_top"))
        self.always_on_top.setChecked(self._current.always_on_top)
        self.click_through = QCheckBox(self._text("start_click_through"))
        self.click_through.setChecked(self._current.click_through)
        self.auto_scroll = QCheckBox(self._text("auto_scroll"))
        self.auto_scroll.setChecked(self._current.auto_scroll)
        self.sound_enabled = QCheckBox(self._text("sound_enabled"))
        self.sound_enabled.setChecked(self._current.sound_enabled)
        self.check_for_updates = QCheckBox(self._text("check_for_updates"))
        self.check_for_updates.setChecked(self._current.check_for_updates)
        self.show_timestamps = QCheckBox(self._text("show_timestamps"))
        self.show_timestamps.setChecked(self._current.show_timestamps)
        self.show_platform = QCheckBox(self._text("show_platform"))
        self.show_platform.setChecked(self._current.show_platform_labels)
        self.hide_commands = QCheckBox(self._text("hide_commands"))
        self.hide_commands.setChecked(self._current.hide_commands)

        self.background_opacity, background_row = self._slider_row(self._current.background_opacity)
        self.card_opacity, card_row = self._slider_row(self._current.card_opacity)

        self.font_size = QSpinBox()
        self.font_size.setRange(11, 30)
        self.font_size.setSuffix(" px")
        self.font_size.setValue(self._current.font_size)

        self.max_messages = QSpinBox()
        self.max_messages.setRange(20, 500)
        self.max_messages.setValue(self._current.max_messages)

        self.lifetime = QSpinBox()
        self.lifetime.setRange(0, 600)
        self.lifetime.setSuffix(" s")
        self.lifetime.setSpecialValueText(self._text("never_remove"))
        self.lifetime.setValue(self._current.message_lifetime_seconds)

        form.addRow(self.always_on_top)
        form.addRow(self.click_through)
        form.addRow(self.auto_scroll)
        form.addRow(self.sound_enabled)
        form.addRow(self.check_for_updates)
        form.addRow(self._text("panel_opacity"), background_row)
        form.addRow(self._text("message_opacity"), card_row)
        form.addRow(self._text("font_size"), self.font_size)
        form.addRow(self._text("max_messages"), self.max_messages)
        form.addRow(self._text("remove_after"), self.lifetime)
        form.addRow(self.show_timestamps)
        form.addRow(self.show_platform)
        form.addRow(self.hide_commands)
        return tab

    @staticmethod
    def _slider_row(value: int) -> tuple[QSlider, QWidget]:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(value)
        label = QLabel(f"{value}%")
        label.setMinimumWidth(42)
        slider.valueChanged.connect(lambda number: label.setText(f"{number}%"))
        layout.addWidget(slider)
        layout.addWidget(label)
        return slider, row

    def accept(self) -> None:
        language = str(self.language_combo.currentData() or "en")
        if not self.twitch_enabled.isChecked() and not self.youtube_enabled.isChecked():
            QMessageBox.warning(
                self,
                tr(language, "no_channel_title"),
                tr(language, "no_channel_message"),
            )
            return
        if self.youtube_api_key.text().strip() and self._key_validation_state == "invalid":
            QMessageBox.warning(
                self,
                tr(language, "youtube_invalid_key_title"),
                tr(language, "youtube_invalid_key_save_message"),
            )
            return
        try:
            self.settings().normalized()
        except ValueError as exc:
            QMessageBox.warning(self, tr(language, "invalid_settings_title"), str(exc))
            return
        super().accept()

    def done(self, result: int) -> None:
        self._validation_debounce.stop()
        self._validation_result_timer.stop()
        self._stop_validator()
        self.youtube_reveal_button.setChecked(False)
        self.youtube_api_key.setEchoMode(QLineEdit.Password)
        super().done(result)

    def settings(self) -> Settings:
        return Settings(
            language=str(self.language_combo.currentData() or "en"),
            twitch_enabled=self.twitch_enabled.isChecked(),
            twitch_channel=self.twitch_channel.text(),
            youtube_enabled=self.youtube_enabled.isChecked(),
            youtube_input=self.youtube_input.text(),
            youtube_api_key=self.youtube_api_key.text(),
            always_on_top=self.always_on_top.isChecked(),
            click_through=self.click_through.isChecked(),
            background_opacity=self.background_opacity.value(),
            card_opacity=self.card_opacity.value(),
            font_size=self.font_size.value(),
            max_messages=self.max_messages.value(),
            message_lifetime_seconds=self.lifetime.value(),
            auto_scroll=self.auto_scroll.isChecked(),
            sound_enabled=self.sound_enabled.isChecked(),
            check_for_updates=self.check_for_updates.isChecked(),
            show_timestamps=self.show_timestamps.isChecked(),
            show_platform_labels=self.show_platform.isChecked(),
            hide_commands=self.hide_commands.isChecked(),
            window_x=self._current.window_x,
            window_y=self._current.window_y,
            window_width=self._current.window_width,
            window_height=self._current.window_height,
        ).normalized()

    def _restore_defaults(self) -> None:
        defaults = Settings()
        self.language_combo.setCurrentIndex(self.language_combo.findData(defaults.language))
        self.twitch_enabled.setChecked(defaults.twitch_enabled)
        self.twitch_channel.setText(defaults.twitch_channel)
        self.youtube_enabled.setChecked(defaults.youtube_enabled)
        self.youtube_input.setText(defaults.youtube_input)
        self.youtube_api_key.clear()
        self.always_on_top.setChecked(defaults.always_on_top)
        self.click_through.setChecked(defaults.click_through)
        self.auto_scroll.setChecked(defaults.auto_scroll)
        self.sound_enabled.setChecked(defaults.sound_enabled)
        self.check_for_updates.setChecked(defaults.check_for_updates)
        self.background_opacity.setValue(defaults.background_opacity)
        self.card_opacity.setValue(defaults.card_opacity)
        self.font_size.setValue(defaults.font_size)
        self.max_messages.setValue(defaults.max_messages)
        self.lifetime.setValue(defaults.message_lifetime_seconds)
        self.show_timestamps.setChecked(defaults.show_timestamps)
        self.show_platform.setChecked(defaults.show_platform_labels)
        self.hide_commands.setChecked(defaults.hide_commands)

    def _toggle_youtube_advanced(self, expanded: bool) -> None:
        self.youtube_advanced_panel.setVisible(expanded)
        self._update_advanced_button_text(expanded)

    def _update_advanced_button_text(self, expanded: bool) -> None:
        arrow = "▴" if expanded else "▾"
        self.youtube_advanced_button.setText(
            f"{self._text('advanced_settings')} {arrow}"
        )

    def _toggle_api_key_visibility(self, visible: bool) -> None:
        self.youtube_api_key.setEchoMode(
            QLineEdit.Normal if visible else QLineEdit.Password
        )
        self.youtube_reveal_button.setToolTip(
            self._text("hide_api_key" if visible else "show_api_key")
        )

    def _sync_initial_youtube_status(self) -> None:
        key = self.youtube_api_key.text().strip()
        if not key:
            self._set_youtube_status("compatibility")
            return
        if self._youtube_connection_mode == "official_stream":
            self._set_youtube_status("official")
            return
        if self._youtube_connection_mode == "official_polling":
            self._set_youtube_status("official_fallback")
            return
        if self._youtube_connection_mode == "invalid_key":
            self._set_youtube_status("invalid")
            return
        if self._youtube_connection_mode == "compatibility_fallback":
            self._set_youtube_status("compatibility_fallback")
            return
        self._on_youtube_api_key_changed()

    def _on_youtube_api_key_changed(self, _value: str = "") -> None:
        self._validation_request_id += 1
        self._validation_debounce.stop()
        self._stop_validator()
        key = self.youtube_api_key.text().strip()
        if not key:
            self._set_youtube_status("compatibility")
            return
        if (
            key == self._initial_youtube_api_key
            and self._youtube_connection_mode == "official_stream"
        ):
            self._set_youtube_status("official")
            return
        if (
            key == self._initial_youtube_api_key
            and self._youtube_connection_mode == "official_polling"
        ):
            self._set_youtube_status("official_fallback")
            return
        if (
            key == self._initial_youtube_api_key
            and self._youtube_connection_mode == "invalid_key"
        ):
            self._set_youtube_status("invalid")
            return
        self._set_youtube_status("checking")
        self._validation_debounce.start()

    def _start_youtube_key_validation(self) -> None:
        key = self.youtube_api_key.text().strip()
        if not key:
            return
        self._stop_validator()
        self._validator = YouTubeKeyValidator(
            self._validation_results,
            key,
            self._validation_request_id,
        )
        self._validator.start()
        self._validation_result_timer.start()

    def _drain_validation_results(self) -> None:
        while True:
            try:
                result = self._validation_results.get_nowait()
            except queue.Empty:
                break
            self._apply_validation_result(result)
        validator = self._validator
        if validator is None or not validator.is_alive():
            self._validation_result_timer.stop()
            self._validator = None

    def _apply_validation_result(self, result: YouTubeKeyValidationResult) -> None:
        if result.request_id != self._validation_request_id:
            return
        if not self.youtube_api_key.text().strip():
            self._set_youtube_status("compatibility")
        elif result.status == "valid":
            self._set_youtube_status("valid")
        elif result.status == "invalid":
            self._set_youtube_status("invalid")
        else:
            self._set_youtube_status("unavailable")

    def _stop_validator(self) -> None:
        validator = self._validator
        self._validator = None
        if validator is not None:
            validator.stop()

    def _set_youtube_status(self, status: str) -> None:
        keys = {
            "compatibility": (
                "youtube_mode_compatibility_title",
                "youtube_mode_compatibility_detail",
                "info",
            ),
            "official": (
                "youtube_mode_official_title",
                "youtube_mode_official_detail",
                "official",
            ),
            "official_fallback": (
                "youtube_mode_official_fallback_title",
                "youtube_mode_official_fallback_detail",
                "warning",
            ),
            "valid": (
                "youtube_key_valid_title",
                "youtube_key_valid_detail",
                "official",
            ),
            "invalid": (
                "youtube_key_invalid_title",
                "youtube_key_invalid_detail",
                "warning",
            ),
            "unavailable": (
                "youtube_key_unavailable_title",
                "youtube_key_unavailable_detail",
                "warning",
            ),
            "checking": (
                "youtube_key_checking_title",
                "youtube_key_checking_detail",
                "info",
            ),
            "compatibility_fallback": (
                "youtube_mode_fallback_title",
                "youtube_mode_fallback_detail",
                "warning",
            ),
        }
        title_key, detail_key, kind = keys.get(status, keys["checking"])
        self._key_validation_state = status
        self.youtube_status_title.setText(self._text(title_key))
        self.youtube_status_detail.setText(self._text(detail_key))
        self.youtube_status_card.setProperty("statusKind", kind)
        style = self.youtube_status_card.style()
        style.unpolish(self.youtube_status_card)
        style.polish(self.youtube_status_card)
