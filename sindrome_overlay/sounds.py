from __future__ import annotations

import logging
import os
import struct
import sys
import threading
import time
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class SoundPreset:
    identifier: str
    asset_name: str
    translation_key: str


SOUND_PRESETS = (
    SoundPreset("soft", "notification-soft.wav", "sound_preset_soft"),
    SoundPreset("pop", "notification-pop.wav", "sound_preset_pop"),
    SoundPreset("chime", "notification-chime.wav", "sound_preset_chime"),
    SoundPreset("arcade", "notification-arcade.wav", "sound_preset_arcade"),
    SoundPreset("bubble", "notification-bubble.wav", "sound_preset_bubble"),
    SoundPreset("bell", "notification-bell.wav", "sound_preset_bell"),
)
SOUND_PRESET_IDS = frozenset(item.identifier for item in SOUND_PRESETS)
DEFAULT_TWITCH_SOUND = "pop"
DEFAULT_YOUTUBE_SOUND = "chime"

_PRESETS_BY_ID = {item.identifier: item for item in SOUND_PRESETS}
_MAX_CACHED_FILES = 24


def normalize_sound_id(value: object, default: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in SOUND_PRESET_IDS else default


def bundled_assets_dir() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / "assets"


def sound_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "SindromeChatOverlay" / "sound-cache"


def write_amplified_wave(source: Path, destination: Path, volume: int) -> None:
    """Copy a small 16-bit PCM WAV while applying 0–200% digital gain."""

    gain = max(0, min(200, int(volume))) / 100.0
    with wave.open(str(source), "rb") as audio:
        if audio.getcomptype() != "NONE" or audio.getsampwidth() != 2:
            raise ValueError("Notification sounds must be uncompressed 16-bit PCM WAV files")
        params = audio.getparams()
        frames = audio.readframes(audio.getnframes())

    sample_count = len(frames) // 2
    if sample_count == 0 or len(frames) % 2:
        raise ValueError("Notification sound contains invalid PCM data")
    samples = struct.unpack(f"<{sample_count}h", frames)
    amplified = (
        max(-32_768, min(32_767, round(sample * gain)))
        for sample in samples
    )
    output_frames = struct.pack(f"<{sample_count}h", *amplified)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setparams(params)
        output.writeframes(output_frames)


class NotificationSoundPlayer:
    """Select, rate-limit, amplify, cache, and play platform notification sounds."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        *,
        assets_dir: Path | None = None,
        cache_dir: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        play_file: Callable[[Path], None] | None = None,
        fallback_beep: Callable[[], None] | None = None,
    ) -> None:
        self.log = logger or logging.getLogger(__name__)
        self.assets_dir = Path(assets_dir) if assets_dir else bundled_assets_dir()
        self.cache_dir = Path(cache_dir) if cache_dir else sound_cache_dir()
        self._clock = clock
        self._play_file = play_file or self._play_file_default
        self._fallback_beep = fallback_beep
        self._last_played_at: float | None = None
        self._prepared: dict[tuple[str, int], Path] = {}
        self._cache_lock = threading.Lock()

    def play(
        self,
        platform: str,
        *,
        enabled: bool,
        volume: int,
        twitch_sound: str,
        youtube_sound: str,
        min_interval_ms: int,
        bypass_limit: bool = False,
    ) -> bool:
        volume = max(0, min(200, int(volume)))
        if not enabled or volume == 0:
            return False

        now = self._clock()
        interval = max(0, min(5_000, int(min_interval_ms))) / 1_000.0
        if (
            not bypass_limit
            and self._last_played_at is not None
            and now - self._last_played_at < interval
        ):
            return False

        default = DEFAULT_TWITCH_SOUND if platform.lower() == "twitch" else DEFAULT_YOUTUBE_SOUND
        selected = twitch_sound if platform.lower() == "twitch" else youtube_sound
        preset_id = normalize_sound_id(selected, default)
        try:
            sound_path = self._prepared_sound(preset_id, volume)
            self._play_file(sound_path)
        except (OSError, RuntimeError, ValueError, wave.Error) as exc:
            self.log.debug("Unable to play notification sound: %s", exc)
            if self._fallback_beep is None:
                return False
            try:
                self._fallback_beep()
            except (OSError, RuntimeError):
                return False

        self._last_played_at = now
        return True

    def preview(self, preset_id: str, volume: int) -> bool:
        return self.play(
            "twitch",
            enabled=True,
            volume=volume,
            twitch_sound=preset_id,
            youtube_sound=preset_id,
            min_interval_ms=0,
            bypass_limit=True,
        )

    def reset_limit(self) -> None:
        self._last_played_at = None

    def _prepared_sound(self, preset_id: str, volume: int) -> Path:
        preset = _PRESETS_BY_ID[preset_id]
        source = self.assets_dir / preset.asset_name
        if not source.is_file():
            raise OSError(f"Bundled notification sound is missing: {preset.asset_name}")
        if volume == 100:
            return source

        key = (preset_id, volume)
        cached = self._prepared.get(key)
        if cached is not None and cached.is_file():
            return cached

        with self._cache_lock:
            destination = self.cache_dir / f"{preset_id}-{volume}.wav"
            try:
                source_mtime = source.stat().st_mtime_ns
                destination_mtime = destination.stat().st_mtime_ns
            except OSError:
                source_mtime = 1
                destination_mtime = 0
            if destination_mtime < source_mtime:
                self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                temporary = self.cache_dir / f".{uuid.uuid4().hex}.wav"
                try:
                    write_amplified_wave(source, temporary, volume)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                self._prune_cache(destination)
            self._prepared[key] = destination
            return destination

    def _prune_cache(self, preserve: Path) -> None:
        try:
            candidates = sorted(
                (
                    path
                    for path in self.cache_dir.glob("*.wav")
                    if path.is_file() and path != preserve
                ),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return
        for candidate in candidates[_MAX_CACHED_FILES - 1 :]:
            try:
                candidate.unlink()
            except OSError:
                continue

    @staticmethod
    def _play_file_default(path: Path) -> None:
        if sys.platform != "win32":
            raise OSError("WAV notification playback is only available on Windows")
        import winsound

        winsound.PlaySound(
            str(path),
            winsound.SND_ASYNC | winsound.SND_FILENAME | winsound.SND_NODEFAULT,
        )
