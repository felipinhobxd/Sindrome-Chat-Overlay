from __future__ import annotations

import unittest

from sindrome_overlay.url_utils import (
    is_youtube_channel_input,
    normalize_twitch_channel,
    normalize_youtube_input,
    twitch_channel_url,
    youtube_video_id,
)


class TwitchUrlTests(unittest.TestCase):
    def test_plain_channel(self) -> None:
        self.assertEqual(normalize_twitch_channel("@SindromeGames"), "sindromegames")

    def test_full_url(self) -> None:
        self.assertEqual(
            normalize_twitch_channel("https://www.twitch.tv/SindromeGames/videos"),
            "sindromegames",
        )
        self.assertEqual(
            twitch_channel_url("SindromeGames"),
            "https://www.twitch.tv/sindromegames",
        )

    def test_invalid_host(self) -> None:
        with self.assertRaises(ValueError):
            normalize_twitch_channel("https://example.com/channel")


class YouTubeUrlTests(unittest.TestCase):
    def test_handle(self) -> None:
        self.assertEqual(
            normalize_youtube_input("@SindromeGames"),
            "https://www.youtube.com/@SindromeGames/live",
        )

    def test_channel_url_gets_live_suffix(self) -> None:
        self.assertEqual(
            normalize_youtube_input("https://www.youtube.com/@SindromeGames"),
            "https://www.youtube.com/@SindromeGames/live",
        )

    def test_watch_and_short_urls(self) -> None:
        expected = "https://www.youtube.com/watch?v=abcdefghijk"
        self.assertEqual(
            normalize_youtube_input("https://youtu.be/abcdefghijk?t=1"),
            expected,
        )
        self.assertEqual(
            normalize_youtube_input("https://www.youtube.com/watch?v=abcdefghijk&feature=x"),
            expected,
        )
        self.assertEqual(youtube_video_id(expected), "abcdefghijk")
        self.assertFalse(is_youtube_channel_input(expected))
        self.assertTrue(is_youtube_channel_input("@SindromeGames"))

    def test_invalid_url(self) -> None:
        with self.assertRaises(ValueError):
            normalize_youtube_input("https://example.com/video")


if __name__ == "__main__":
    unittest.main()
