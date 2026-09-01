from __future__ import annotations

import unittest

from sindrome_overlay.emotes import build_message_html, twitch_emote_url
from sindrome_overlay.models import ChatEmote


class EmoteRenderingTests(unittest.TestCase):
    def test_official_twitch_cdn_url(self) -> None:
        self.assertEqual(
            twitch_emote_url("emotesv2_abc-123"),
            "https://static-cdn.jtvnw.net/emoticons/v2/emotesv2_abc-123/static/dark/3.0",
        )

    def test_invalid_emote_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            twitch_emote_url("../not-safe")

    def test_html_replaces_only_the_tagged_range_and_escapes_text(self) -> None:
        rendered = build_message_html(
            "<hello> Kappa & bye",
            (ChatEmote("25", 8, 13, "Kappa"),),
            {"25": "file:///tmp/Kappa.png"},
            28,
        )
        self.assertIn("&lt;hello&gt;", rendered)
        self.assertIn('src="file:///tmp/Kappa.png"', rendered)
        self.assertIn('height="28"', rendered)
        self.assertIn('alt="Kappa"', rendered)
        self.assertIn("&amp; bye", rendered)
        self.assertNotIn(">Kappa<", rendered)

    def test_missing_image_keeps_text_as_fallback(self) -> None:
        rendered = build_message_html(
            "Hello Kappa",
            (ChatEmote("25", 6, 11, "Kappa"),),
            {},
            28,
        )
        self.assertEqual(rendered, "Hello Kappa")

    def test_only_repeated_and_different_emotes_render_in_place(self) -> None:
        text = "Kappa hello Kappa PogChamp"
        rendered = build_message_html(
            text,
            (
                ChatEmote("25", 0, 5, "Kappa"),
                ChatEmote("25", 12, 17, "Kappa"),
                ChatEmote("88", 18, 26, "PogChamp"),
            ),
            {"25": "file:///Kappa.png", "88": "file:///PogChamp.png"},
            30,
        )
        self.assertEqual(rendered.count('src="file:///Kappa.png"'), 2)
        self.assertEqual(rendered.count('src="file:///PogChamp.png"'), 1)
        self.assertIn(" hello ", rendered)

    def test_unicode_before_an_emote_is_preserved(self) -> None:
        rendered = build_message_html(
            "😀 olá Kappa!",
            (ChatEmote("25", 6, 11, "Kappa"),),
            {"25": "file:///Kappa.png"},
            28,
        )
        self.assertTrue(rendered.startswith("😀 olá "))
        self.assertTrue(rendered.endswith("!"))

    def test_normal_message_does_not_become_rich_content(self) -> None:
        self.assertEqual(build_message_html("Normal 😀 text", (), {}, 28), "Normal 😀 text")


if __name__ == "__main__":
    unittest.main()
