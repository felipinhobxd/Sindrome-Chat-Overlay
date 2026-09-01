from __future__ import annotations

import unittest

from sindrome_overlay.models import (
    ChatBadge,
    ChatEmote,
    ChatMessage,
    colour_contrast_ratio,
    resolve_author_colour,
    stable_user_identity,
)


class AuthorColourTests(unittest.TestCase):
    def setUp(self) -> None:
        resolve_author_colour.cache_clear()

    def test_twitch_uses_a_readable_official_colour(self) -> None:
        message = ChatMessage(
            "twitch",
            "Felipe",
            "Hello",
            author_id="12345",
            author_colour="#FF69B4",
        )
        self.assertEqual(message.safe_author_colour, "#FF69B4")
        self.assertGreaterEqual(colour_contrast_ratio(message.safe_author_colour), 4.5)

    def test_dark_official_twitch_colour_is_minimally_lightened(self) -> None:
        original = "#000080"
        adjusted = ChatMessage(
            "twitch",
            "DarkBlueUser",
            "Hello",
            author_id="20",
            author_colour=original,
        ).safe_author_colour
        self.assertNotEqual(adjusted, original)
        self.assertGreaterEqual(colour_contrast_ratio(adjusted), 4.5)
        self.assertGreater(int(adjusted[5:7], 16), int(original[5:7], 16))

    def test_twitch_fallback_is_stable_for_the_user_id(self) -> None:
        first = ChatMessage("twitch", "Joao123", "One", author_id="98765")
        second = ChatMessage("twitch", "JOAO RENAMED", "Two", author_id="98765")
        self.assertEqual(first.safe_author_colour, second.safe_author_colour)
        self.assertGreaterEqual(colour_contrast_ratio(first.safe_author_colour), 4.5)

    def test_youtube_colour_is_stable_for_the_channel_id(self) -> None:
        first = ChatMessage("youtube", "MariaLive", "One", author_id="UC-maria")
        second = ChatMessage("youtube", "Novo nome", "Two", author_id="UC-maria")
        self.assertEqual(first.safe_author_colour, second.safe_author_colour)
        self.assertGreaterEqual(colour_contrast_ratio(first.safe_author_colour), 4.5)

    def test_many_users_have_visually_individual_colours(self) -> None:
        twitch_colours = {
            ChatMessage("twitch", f"User {index}", "Hi", author_id=str(index)).safe_author_colour
            for index in range(40)
        }
        youtube_colours = {
            ChatMessage(
                "youtube",
                f"Viewer {index}",
                "Hi",
                author_id=f"UC-{index}",
            ).safe_author_colour
            for index in range(40)
        }
        self.assertGreaterEqual(len(twitch_colours), 38)
        self.assertGreaterEqual(len(youtube_colours), 38)

    def test_unicode_and_long_name_fallback_is_stable(self) -> None:
        name = "ジョアン_😀_" + ("NomeMuitoLongo" * 20)
        identity = stable_user_identity("", name)
        self.assertEqual(identity, stable_user_identity("", name))
        first = ChatMessage("youtube", name, "One").safe_author_colour
        second = ChatMessage("youtube", name, "Two").safe_author_colour
        self.assertEqual(first, second)

    def test_badges_emotes_and_owner_status_do_not_change_name_colour(self) -> None:
        plain = ChatMessage("youtube", "Owner", "Kappa", author_id="UC-owner")
        decorated = ChatMessage(
            "youtube",
            "Owner",
            "Kappa",
            author_id="UC-owner",
            badges=("OWNER", "MOD"),
            emotes=(ChatEmote("25", 0, 5, "Kappa"),),
            badge_refs=(ChatBadge("moderator", "1", "123"),),
        )
        self.assertEqual(plain.safe_author_colour, decorated.safe_author_colour)

    def test_cache_is_bounded(self) -> None:
        for index in range(2_100):
            resolve_author_colour("youtube", f"id:UC-{index}")
        info = resolve_author_colour.cache_info()
        self.assertEqual(info.maxsize, 2_048)
        self.assertLessEqual(info.currsize, 2_048)


if __name__ == "__main__":
    unittest.main()
