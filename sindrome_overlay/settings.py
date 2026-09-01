from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .i18n import normalize_language
from .url_utils import normalize_twitch_channel, normalize_youtube_input

APP_DIR_NAME = "SindromeChatOverlay"


def app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_DIR_NAME


@dataclass(slots=True)
class Settings:
    language: str = "en"
    twitch_enabled: bool = True
    twitch_channel: str = "sindromegames"
    youtube_enabled: bool = True
    youtube_input: str = "https://www.youtube.com/@SindromeGames/live"
    youtube_api_key: str = ""
    always_on_top: bool = True
    click_through: bool = False
    background_opacity: int = 72
    card_opacity: int = 78
    font_size: int = 15
    max_messages: int = 150
    message_lifetime_seconds: int = 0
    auto_scroll: bool = True
    sound_enabled: bool = True
    show_timestamps: bool = True
    show_platform_labels: bool = True
    hide_commands: bool = False
    window_x: int = 40
    window_y: int = 80
    window_width: int = 440
    window_height: int = 720

    def normalized(self) -> Settings:
        self.language = normalize_language(self.language)
        if self.twitch_enabled or self.twitch_channel.strip():
            self.twitch_channel = normalize_twitch_channel(self.twitch_channel, self.language)
        else:
            self.twitch_channel = ""
        if self.youtube_enabled or self.youtube_input.strip():
            self.youtube_input = normalize_youtube_input(self.youtube_input, self.language)
        else:
            self.youtube_input = ""
        self.youtube_api_key = self.youtube_api_key.strip()
        self.background_opacity = _clamp(self.background_opacity, 0, 100)
        self.card_opacity = _clamp(self.card_opacity, 0, 100)
        self.font_size = _clamp(self.font_size, 11, 30)
        self.max_messages = _clamp(self.max_messages, 20, 500)
        self.message_lifetime_seconds = _clamp(self.message_lifetime_seconds, 0, 600)
        self.window_width = _clamp(self.window_width, 300, 2000)
        self.window_height = _clamp(self.window_height, 240, 1400)
        return self


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "settings.json"

    def load(self) -> Settings:
        defaults = Settings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return defaults
            allowed = {item.name for item in fields(Settings)}
            values = {key: value for key, value in payload.items() if key in allowed}
            return Settings(**values).normalized()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return defaults

    def save(self, settings: Settings) -> None:
        settings.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)


def _clamp(value: Any, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, numeric))
