from __future__ import annotations

import unittest

from sindrome_overlay.models import ChatMessage, clean_text, text_from_runs


class ModelTests(unittest.TestCase):
    def test_clean_text(self) -> None:
        self.assertEqual(clean_text("  olá\n  mundo  "), "olá mundo")
        self.assertEqual(clean_text({"simpleText": "R$ 5,00"}), "R$ 5,00")

    def test_runs_with_emoji(self) -> None:
        runs = [
            {"text": "Olá "},
            {"emoji": {"shortcuts": [":wave:"]}},
            {"text": "!"},
        ]
        self.assertEqual(text_from_runs(runs), "Olá :wave:!")

    def test_colour_is_validated(self) -> None:
        self.assertEqual(
            ChatMessage("twitch", "A", "B", author_colour="#12ABEF").safe_author_colour,
            "#12ABEF",
        )
        self.assertRegex(
            ChatMessage("twitch", "A", "B", author_colour="red; bad").safe_author_colour,
            r"^#[0-9A-F]{6}$",
        )


if __name__ == "__main__":
    unittest.main()
