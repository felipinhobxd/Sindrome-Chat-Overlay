from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, tr
from ..settings import Settings


class SettingsDialog(QDialog):
    def __init__(self, current: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current = replace(current)
        self.setWindowTitle(self._text("settings_title"))
        self.resize(640, 610)

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
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText(self._text("save"))
        buttons.button(QDialogButtonBox.Cancel).setText(self._text("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

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
        self.youtube_enabled = QCheckBox(self._text("show_youtube_chat"))
        self.youtube_enabled.setChecked(self._current.youtube_enabled)
        self.youtube_input = QLineEdit(self._current.youtube_input)
        self.youtube_input.setPlaceholderText(self._text("youtube_placeholder"))
        self.youtube_input.setToolTip(self._text("youtube_source_note"))
        self.youtube_api_key = QLineEdit(self._current.youtube_api_key)
        self.youtube_api_key.setEchoMode(QLineEdit.Password)
        self.youtube_api_key.setPlaceholderText(self._text("optional"))
        show_key = QCheckBox(self._text("show_key"))
        show_key.toggled.connect(
            lambda checked: self.youtube_api_key.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        youtube_form.addRow(self.youtube_enabled)
        youtube_form.addRow(self._text("channel_or_live"), self.youtube_input)
        source_note = QLabel(self._text("youtube_source_note"))
        source_note.setWordWrap(True)
        source_note.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        youtube_form.addRow(source_note)
        youtube_form.addRow(self._text("youtube_data_api_key"), self.youtube_api_key)
        youtube_form.addRow("", show_key)
        youtube_note = QLabel(self._text("youtube_key_note"))
        youtube_note.setWordWrap(True)
        youtube_note.setStyleSheet("color: #AAB5CB; font-size: 12px;")
        youtube_form.addRow(youtube_note)
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
        try:
            self.settings().normalized()
        except ValueError as exc:
            QMessageBox.warning(self, tr(language, "invalid_settings_title"), str(exc))
            return
        super().accept()

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
        self.background_opacity.setValue(defaults.background_opacity)
        self.card_opacity.setValue(defaults.card_opacity)
        self.font_size.setValue(defaults.font_size)
        self.max_messages.setValue(defaults.max_messages)
        self.lifetime.setValue(defaults.message_lifetime_seconds)
        self.show_timestamps.setChecked(defaults.show_timestamps)
        self.show_platform.setChecked(defaults.show_platform_labels)
        self.hide_commands.setChecked(defaults.hide_commands)
