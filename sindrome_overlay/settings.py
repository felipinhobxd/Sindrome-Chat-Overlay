from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .i18n import normalize_language
from .sounds import DEFAULT_TWITCH_SOUND, DEFAULT_YOUTUBE_SOUND, normalize_sound_id
from .url_utils import normalize_twitch_channel, normalize_youtube_input

APP_DIR_NAME = "SindromeChatOverlay"
_DPAPI_PREFIX = "dpapi:"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


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
    sound_volume: int = 100
    twitch_sound: str = DEFAULT_TWITCH_SOUND
    youtube_sound: str = DEFAULT_YOUTUBE_SOUND
    sound_min_interval_ms: int = 500
    check_for_updates: bool = True
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
        self.sound_volume = _clamp(self.sound_volume, 0, 200)
        self.twitch_sound = normalize_sound_id(self.twitch_sound, DEFAULT_TWITCH_SOUND)
        self.youtube_sound = normalize_sound_id(self.youtube_sound, DEFAULT_YOUTUBE_SOUND)
        self.sound_min_interval_ms = _clamp(self.sound_min_interval_ms, 0, 5_000)
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
            encrypted_key = values.get("youtube_api_key")
            if isinstance(encrypted_key, str):
                try:
                    values["youtube_api_key"] = _unprotect_secret(encrypted_key)
                except OSError:
                    values["youtube_api_key"] = ""
            return Settings(**values).normalized()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return defaults

    def save(self, settings: Settings) -> None:
        settings.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        payload = asdict(settings)
        payload["youtube_api_key"] = _protect_secret(settings.youtube_api_key)
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)


def _clamp(value: Any, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, numeric))


def _protect_secret(value: str) -> str:
    if not value or os.name != "nt":
        return value
    source, source_buffer = _blob(value.encode("utf-8"))
    output = _DataBlob()
    crypt32, kernel32 = _dpapi_libraries()
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "Sindrome Chat Overlay YouTube API key",
        None,
        None,
        None,
        0x01,
        ctypes.byref(output),
    ):
        raise OSError(ctypes.get_last_error(), "Windows could not protect the YouTube API key")
    try:
        protected = ctypes.string_at(output.pbData, output.cbData)
        return _DPAPI_PREFIX + base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer


def _unprotect_secret(value: str) -> str:
    if not value.startswith(_DPAPI_PREFIX):
        return value
    if os.name != "nt":
        return ""
    try:
        protected = base64.b64decode(value.removeprefix(_DPAPI_PREFIX), validate=True)
    except (ValueError, TypeError) as exc:
        raise OSError("The encrypted YouTube API key is invalid") from exc
    source, source_buffer = _blob(protected)
    output = _DataBlob()
    crypt32, kernel32 = _dpapi_libraries()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0x01,
        ctypes.byref(output),
    ):
        raise OSError(ctypes.get_last_error(), "Windows could not read the YouTube API key")
    try:
        return ctypes.string_at(output.pbData, output.cbData).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OSError("The encrypted YouTube API key is invalid") from exc
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    return _DataBlob(len(value), pointer), buffer


def _dpapi_libraries() -> tuple[Any, Any]:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32
