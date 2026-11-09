from __future__ import annotations

import unittest
from datetime import UTC, datetime

from sindrome_overlay.models import ChatMessage, clean_text, parse_timestamp_usec, text_from_runs


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

    def test_youtube_microsecond_timestamp_handles_out_of_range_values(self) -> None:
        valid = parse_timestamp_usec("1700000000000000")
        self.assertEqual(valid, datetime.fromtimestamp(1_700_000_000, UTC))

        # Numeric input can overflow either float conversion or datetime
        # construction; neither should interrupt the active chat connection.
        for value in (10**400, "9" * 400, 10**30, float("inf"), float("-inf"), None):
            with self.subTest(value=str(value)[:30]):
                before = datetime.now(UTC)
                fallback = parse_timestamp_usec(value)
                after = datetime.now(UTC)
                self.assertGreaterEqual(fallback, before)
                self.assertLessEqual(fallback, after)

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
