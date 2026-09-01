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
                language="pt-BR",
                twitch_channel="@SindromeGames",
                youtube_input="@SindromeGames",
                youtube_api_key="secret-data-api-key",
                font_size=99,
                max_messages=1,
            )
            store.save(settings)
            loaded = store.load()
            self.assertEqual(loaded.twitch_channel, "sindromegames")
            self.assertEqual(loaded.language, "pt-BR")
            self.assertEqual(
                loaded.youtube_input,
                "https://www.youtube.com/@SindromeGames/live",
            )
            self.assertEqual(loaded.font_size, 30)
            self.assertEqual(loaded.max_messages, 20)
            self.assertEqual(loaded.youtube_api_key, "secret-data-api-key")
            saved_payload = json.loads(path.read_text(encoding="utf-8"))
            if __import__("os").name == "nt":
                self.assertTrue(saved_payload["youtube_api_key"].startswith("dpapi:"))
                self.assertNotIn("secret-data-api-key", path.read_text(encoding="utf-8"))

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
        self.assertEqual(settings.language, "en")
        self.assertTrue(settings.auto_scroll)
        self.assertTrue(settings.sound_enabled)

    def test_unknown_language_falls_back_to_english(self) -> None:
        settings = Settings(language="invalid").normalized()
        self.assertEqual(settings.language, "en")


if __name__ == "__main__":
    unittest.main()
