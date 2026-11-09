from __future__ import annotations

import unittest

from sindrome_overlay.filters import should_display
from sindrome_overlay.models import ChatMessage
from sindrome_overlay.settings import Settings


def _message(text: str, author: str = "viewer", author_id: str = "uc-1") -> ChatMessage:
    return ChatMessage("twitch", author, text, author_id=author_id)


class ShouldDisplayTests(unittest.TestCase):
    def test_regular_message_passes_by_default(self) -> None:
        self.assertTrue(should_display(_message("hello there"), Settings()))

    def test_commands_hidden_only_when_enabled(self) -> None:
        settings = Settings()
        settings.hide_commands = True
        self.assertFalse(should_display(_message("!play song"), settings))
        self.assertTrue(should_display(_message("playing !song"), settings))
        settings.hide_commands = False
        self.assertTrue(should_display(_message("!play song"), settings))

    def test_hidden_users_match_case_insensitively_and_by_id(self) -> None:
        settings = Settings()
        settings.hidden_users = "SpamBot, other@user\nthird"
        self.assertFalse(should_display(_message("hi", author="spambot"), settings))
        self.assertFalse(should_display(_message("hi", author="Third"), settings))
        self.assertTrue(should_display(_message("hi", author="regular"), settings))

        by_id = Settings()
        by_id.hidden_users = "uc-999"
        self.assertFalse(
            should_display(_message("hi", author="anyone", author_id="uc-999"), by_id)
        )

    def test_hidden_words_are_substring_and_case_insensitive(self) -> None:
        settings = Settings()
        settings.hidden_words = "free nitro, SCAM"
        self.assertFalse(should_display(_message("Get FREE NitRO now"), settings))
        self.assertFalse(should_display(_message("total scam here"), settings))
        self.assertTrue(should_display(_message("nice game"), settings))

    def test_filters_combine(self) -> None:
        settings = Settings()
        settings.hide_commands = True
        settings.hidden_users = "spambot"
        self.assertFalse(should_display(_message("!play", author="spambot"), settings))


if __name__ == "__main__":
    unittest.main()
