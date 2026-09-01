from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sindrome_overlay.settings import Settings, SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_round_trip_and_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            settings = Settings(
                twitch_channel="@SindromeGames",
                youtube_input="@SindromeGames",
                font_size=99,
                max_messages=1,
            )
            store.save(settings)
            loaded = store.load()
            self.assertEqual(loaded.twitch_channel, "sindromegames")
            self.assertEqual(
                loaded.youtube_input,
                "https://www.youtube.com/@SindromeGames/live",
            )
            self.assertEqual(loaded.font_size, 30)
            self.assertEqual(loaded.max_messages, 20)

    def test_unknown_fields_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"twitch_channel": "sindromegames", "future": 123}),
                encoding="utf-8",
            )
            loaded = SettingsStore(path).load()
            self.assertEqual(loaded.twitch_channel, "sindromegames")

    def test_invalid_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            loaded = SettingsStore(path).load()
            self.assertEqual(loaded, Settings())

    def test_disabled_channels_may_be_blank(self) -> None:
        settings = Settings(
            twitch_enabled=False,
            twitch_channel="",
            youtube_enabled=False,
            youtube_input="",
        ).normalized()
        self.assertEqual(settings.twitch_channel, "")
        self.assertEqual(settings.youtube_input, "")

    def test_notifications_are_enabled_by_default(self) -> None:
        settings = Settings()
        self.assertTrue(settings.auto_scroll)
        self.assertTrue(settings.sound_enabled)


if __name__ == "__main__":
    unittest.main()
