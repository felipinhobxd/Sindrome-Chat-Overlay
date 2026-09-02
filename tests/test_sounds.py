from __future__ import annotations

import struct
import tempfile
import unittest
import wave
from pathlib import Path

from sindrome_overlay.sounds import (
    NotificationSoundPlayer,
    normalize_sound_id,
    write_amplified_wave,
)


def _write_test_wave(path: Path, samples: tuple[int, ...] = (1_000, -1_000)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44_100)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))


class SoundTests(unittest.TestCase):
    def test_200_percent_gain_is_applied_and_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.wav"
            destination = Path(directory) / "amplified.wav"
            _write_test_wave(source, (1_000, -1_000, 20_000, -20_000))

            write_amplified_wave(source, destination, 200)

            with wave.open(str(destination), "rb") as audio:
                frames = audio.readframes(audio.getnframes())
            self.assertEqual(struct.unpack("<4h", frames), (2_000, -2_000, 32_767, -32_768))

    def test_platform_sounds_are_distinct_and_rate_limited_globally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory) / "assets"
            cache = Path(directory) / "cache"
            _write_test_wave(assets / "notification-pop.wav")
            _write_test_wave(assets / "notification-chime.wav")
            now = [10.0]
            played: list[Path] = []
            player = NotificationSoundPlayer(
                assets_dir=assets,
                cache_dir=cache,
                clock=lambda: now[0],
                play_file=played.append,
            )
            options = {
                "enabled": True,
                "volume": 100,
                "twitch_sound": "pop",
                "youtube_sound": "chime",
                "min_interval_ms": 500,
            }

            self.assertTrue(player.play("twitch", **options))
            now[0] += 0.1
            self.assertFalse(player.play("youtube", **options))
            now[0] += 0.41
            self.assertTrue(player.play("youtube", **options))

            self.assertEqual(
                [path.name for path in played],
                ["notification-pop.wav", "notification-chime.wav"],
            )

    def test_preview_bypasses_antispam_and_uses_amplified_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory) / "assets"
            cache = Path(directory) / "cache"
            _write_test_wave(assets / "notification-pop.wav")
            played: list[Path] = []
            player = NotificationSoundPlayer(
                assets_dir=assets,
                cache_dir=cache,
                clock=lambda: 5.0,
                play_file=played.append,
            )

            self.assertTrue(player.preview("pop", 200))
            self.assertTrue(player.preview("pop", 200))
            self.assertEqual(len(played), 2)
            self.assertEqual(played[0], played[1])
            self.assertEqual(played[0].name, "pop-200.wav")
            self.assertTrue(played[0].is_file())

    def test_disabled_zero_volume_and_unknown_presets_are_safe(self) -> None:
        played: list[Path] = []
        player = NotificationSoundPlayer(play_file=played.append)
        options = {
            "twitch_sound": "unknown",
            "youtube_sound": "unknown",
            "min_interval_ms": 0,
        }
        self.assertFalse(player.play("twitch", enabled=False, volume=100, **options))
        self.assertFalse(player.play("youtube", enabled=True, volume=0, **options))
        self.assertEqual(played, [])
        self.assertEqual(normalize_sound_id("unknown", "pop"), "pop")


if __name__ == "__main__":
    unittest.main()
