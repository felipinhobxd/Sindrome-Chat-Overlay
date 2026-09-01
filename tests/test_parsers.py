from __future__ import annotations

import unittest

from sindrome_overlay.providers.twitch import parse_irc_tags, parse_twitch_line
from sindrome_overlay.providers.youtube import (
    official_message_from_item,
    youtube_messages_from_actions,
)


class TwitchParserTests(unittest.TestCase):
    def test_tag_escapes(self) -> None:
        tags = parse_irc_tags(r"display-name=Sindrome\sGames;system-msg=Ola\smundo\:")
        self.assertEqual(tags["display-name"], "Sindrome Games")
        self.assertEqual(tags["system-msg"], "Ola mundo;")

    def test_privmsg(self) -> None:
        line = (
            "@badges=moderator/1,subscriber/12;color=#9146FF;display-name=Felipe;"
            "id=msg-1;tmi-sent-ts=1700000000000 :felipe!felipe@felipe.tmi.twitch.tv "
            "PRIVMSG #sindromegames :Olá chat!"
        )
        kind, payload = parse_twitch_line(line)
        self.assertEqual(kind, "message")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.author, "Felipe")
        self.assertEqual(payload.text, "Olá chat!")
        self.assertIn("MODERATOR", payload.badges)

    def test_deletion(self) -> None:
        kind, payload = parse_twitch_line(
            "@target-msg-id=abc :tmi.twitch.tv CLEARMSG #canal :texto"
        )
        self.assertEqual((kind, payload), ("delete", "abc"))

    def test_clear_chat_only_clears_on_full_room_clear(self) -> None:
        self.assertEqual(
            parse_twitch_line(":tmi.twitch.tv CLEARCHAT #canal"),
            ("clear", None),
        )
        self.assertEqual(
            parse_twitch_line(":tmi.twitch.tv CLEARCHAT #canal :usuario"),
            ("other", None),
        )


class YouTubeParserTests(unittest.TestCase):
    def test_innertube_text_message(self) -> None:
        actions = [
            {
                "addChatItemAction": {
                    "item": {
                        "liveChatTextMessageRenderer": {
                            "id": "yt-1",
                            "timestampUsec": "1700000000000000",
                            "authorName": {"simpleText": "Visitante"},
                            "message": {"runs": [{"text": "Boa live!"}]},
                            "authorBadges": [
                                {"liveChatAuthorBadgeRenderer": {"tooltip": "Moderator"}}
                            ],
                        }
                    }
                }
            }
        ]
        messages, deletions = youtube_messages_from_actions(actions)
        self.assertEqual(deletions, [])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].author, "Visitante")
        self.assertEqual(messages[0].text, "Boa live!")
        self.assertEqual(messages[0].badges, ("MODERATOR",))

    def test_paid_message_and_deletion(self) -> None:
        actions = [
            {
                "addChatItemAction": {
                    "item": {
                        "liveChatPaidMessageRenderer": {
                            "id": "paid-1",
                            "authorName": {"simpleText": "Apoiador"},
                            "message": {"runs": [{"text": "Parabéns!"}]},
                            "purchaseAmountText": {"simpleText": "R$ 10,00"},
                        }
                    }
                }
            },
            {"markChatItemAsDeletedAction": {"targetItemId": "paid-1"}},
        ]
        messages, deletions = youtube_messages_from_actions(actions)
        self.assertEqual(messages[0].amount, "R$ 10,00")
        self.assertEqual(messages[0].kind, "paid")
        self.assertEqual(deletions, ["paid-1"])

    def test_official_api_message(self) -> None:
        item = {
            "id": "official-1",
            "snippet": {
                "type": "textMessageEvent",
                "displayMessage": "Olá pelo modo oficial",
                "publishedAt": "2026-01-02T03:04:05Z",
            },
            "authorDetails": {
                "displayName": "Canal",
                "isChatOwner": True,
                "isChatModerator": False,
                "isChatSponsor": True,
            },
        }
        message = official_message_from_item(item)
        self.assertIsNotNone(message)
        self.assertEqual(message.message_id, "official-1")
        self.assertEqual(message.badges, ("DONO", "MEMBRO"))


if __name__ == "__main__":
    unittest.main()
