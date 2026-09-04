from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sindrome_overlay.profiles import (
    apply_overlay_profile,
    capture_overlay_profile,
    normalize_custom_profiles,
    normalize_profile_ref,
    resolve_profile,
)
from sindrome_overlay.settings import Settings, SettingsStore


class OverlayProfileTests(unittest.TestCase):
    def test_profile_values_are_allowlisted_and_clamped(self) -> None:
        profiles = normalize_custom_profiles(
            {
                "  My   Stream  ": {
                    "font_size": 999,
                    "window_width": 10,
                    "window_height": 99999,
                    "background_opacity": -4,
                    "show_timestamps": False,
                    "youtube_api_key": "must-never-be-stored",
                    "twitch_channel": "must-never-be-stored",
                    "click_through": True,
                },
                "": {"font_size": 12},
                "x" * 41: {"font_size": 12},
            }
        )
        self.assertEqual(list(profiles), ["My Stream"])
        stored = profiles["My Stream"]
        self.assertEqual(stored["font_size"], 30)
        self.assertEqual(stored["window_width"], 300)
        self.assertEqual(stored["window_height"], 1400)
        self.assertEqual(stored["background_opacity"], 0)
        self.assertFalse(stored["show_timestamps"])
        self.assertNotIn("youtube_api_key", stored)
        self.assertNotIn("twitch_channel", stored)
        self.assertNotIn("click_through", stored)

    def test_applying_profile_preserves_connections_secrets_and_sound(self) -> None:
        original = Settings(
            twitch_channel="sindromegames",
            youtube_input="https://www.youtube.com/@SindromeGames/live",
            youtube_api_key="AIza-test-secret-value-that-stays",
            click_through=True,
            sound_enabled=True,
            sound_volume=177,
            font_size=15,
            window_width=440,
        ).normalized()
        updated = apply_overlay_profile(
            original,
            {
                "font_size": 21,
                "window_width": 700,
                "background_opacity": 12,
                "youtube_api_key": "attacker-value",
                "click_through": False,
            },
        )
        self.assertEqual(updated.font_size, 21)
        self.assertEqual(updated.window_width, 700)
        self.assertEqual(updated.background_opacity, 12)
        self.assertEqual(updated.twitch_channel, original.twitch_channel)
        self.assertEqual(updated.youtube_input, original.youtube_input)
        self.assertEqual(updated.youtube_api_key, original.youtube_api_key)
        self.assertEqual(updated.click_through, original.click_through)
        self.assertEqual(updated.sound_enabled, original.sound_enabled)
        self.assertEqual(updated.sound_volume, original.sound_volume)

    def test_custom_profile_round_trips_through_settings_store(self) -> None:
        settings = Settings(font_size=18, window_x=321, window_y=222)
        settings.overlay_profiles = {
            "Live": capture_overlay_profile(settings),
        }
        settings.active_overlay_profile = "custom:Live"
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            store.save(settings)
            loaded = store.load()
        self.assertIn("Live", loaded.overlay_profiles)
        self.assertEqual(loaded.overlay_profiles["Live"]["font_size"], 18)
        self.assertEqual(loaded.overlay_profiles["Live"]["window_x"], 321)
        self.assertEqual(loaded.active_overlay_profile, "custom:Live")

    def test_builtin_and_custom_profile_references_are_resolved_safely(self) -> None:
        custom = {"Desk": {"font_size": 16}}
        self.assertIsNotNone(resolve_profile("builtin:compact_fps", custom))
        self.assertEqual(resolve_profile("custom:Desk", custom), {"font_size": 16})
        self.assertIsNone(resolve_profile("builtin:does-not-exist", custom))
        self.assertEqual(normalize_profile_ref("custom:Desk", custom), "custom:Desk")
        self.assertEqual(normalize_profile_ref("custom:Missing", custom), "")


if __name__ == "__main__":
    unittest.main()
