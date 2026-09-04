from __future__ import annotations

import unittest

from sindrome_overlay.providers.twitch import (
    parse_irc_tags,
    parse_twitch_badges,
    parse_twitch_emotes,
    parse_twitch_line,
)
from sindrome_overlay.providers.youtube import (
    extract_video_id_from_url,
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
            "id=msg-1;room-id=444;user-id=12345;tmi-sent-ts=1700000000000 "
            ":felipe!felipe@felipe.tmi.twitch.tv "
            "PRIVMSG #sindromegames :Olá chat!"
        )
        kind, payload = parse_twitch_line(line)
        self.assertEqual(kind, "message")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.author, "Felipe")
        self.assertEqual(payload.author_id, "12345")
        self.assertEqual(payload.text, "Olá chat!")
        self.assertIn("MODERATOR", payload.badges)
        self.assertEqual(payload.badge_refs[0].room_id, "444")

    def test_privmsg_includes_emote_positions(self) -> None:
        line = (
            "@badges=;color=#9146FF;display-name=Felipe;emotes=25:0-4/88:12-19;"
            "id=msg-emotes :felipe!felipe@felipe.tmi.twitch.tv "
            "PRIVMSG #sindromegames :Kappa hello PogChamp"
        )
        kind, payload = parse_twitch_line(line)
        self.assertEqual(kind, "message")
        self.assertIsNotNone(payload)
        self.assertEqual(
            [(item.emote_id, item.start, item.end, item.name) for item in payload.emotes],
            [("25", 0, 5, "Kappa"), ("88", 12, 20, "PogChamp")],
        )

    def test_emote_positions_handle_repeats_and_utf16_offsets(self) -> None:
        repeated = parse_twitch_emotes("25:0-4,6-10", "Kappa Kappa")
        self.assertEqual([item.name for item in repeated], ["Kappa", "Kappa"])

        with_emoji = parse_twitch_emotes("25:3-7", "😀 Kappa")
        self.assertEqual(len(with_emoji), 1)
        self.assertEqual((with_emoji[0].start, with_emoji[0].end), (2, 7))
        self.assertEqual(with_emoji[0].name, "Kappa")

    def test_action_message_uses_positions_after_action_prefix(self) -> None:
        line = (
            "@display-name=Felipe;emotes=25:0-4;id=action-1 "
            ":felipe!felipe@felipe.tmi.twitch.tv "
            "PRIVMSG #sindromegames :\x01ACTION Kappa waves\x01"
        )
        kind, payload = parse_twitch_line(line)
        self.assertEqual(kind, "message")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.text, "Kappa waves")
        self.assertEqual(payload.emotes[0].name, "Kappa")

    def test_twitch_badges_keep_set_version_and_room(self) -> None:
        badges = parse_twitch_badges(
            "moderator/1,twitch-recap-2023/1,invalid",
            "123456",
        )
        self.assertEqual(
            [(item.set_id, item.version, item.room_id) for item in badges],
            [
                ("moderator", "1", "123456"),
                ("twitch-recap-2023", "1", "123456"),
            ],
        )
        self.assertEqual(badges[1].key, "123456:twitch-recap-2023/1")

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
                            "authorExternalChannelId": "UC-visitor",
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
        self.assertEqual(messages[0].author_id, "UC-visitor")
        self.assertEqual(messages[0].text, "Boa live!")
        self.assertEqual(messages[0].badges, ("MODERATOR",))

    def test_innertube_custom_emote_preserves_image_and_span(self) -> None:
        actions = [
            {
                "addChatItemAction": {
                    "item": {
                        "liveChatTextMessageRenderer": {
                            "id": "yt-emote",
                            "authorName": {"simpleText": "Visitante"},
                            "message": {
                                "runs": [
                                    {"text": "Oi "},
                                    {
                                        "emoji": {
                                            "emojiId": "UC-custom-1",
                                            "shortcuts": [":sindrome:"],
                                            "isCustomEmoji": True,
                                            "image": {
                                                "thumbnails": [
                                                    {"url": "https://yt3.ggpht.com/small"},
                                                    {"url": "https://yt3.ggpht.com/large"},
                                                ]
                                            },
                                        }
                                    },
                                    {"text": "!"},
                                ]
                            },
                        }
                    }
                }
            }
        ]
        messages, _ = youtube_messages_from_actions(actions)
        self.assertEqual(messages[0].text, "Oi :sindrome:!")
        self.assertEqual(len(messages[0].emotes), 1)
        emote = messages[0].emotes[0]
        self.assertEqual((emote.start, emote.end, emote.name), (3, 13, ":sindrome:"))
        self.assertEqual(emote.image_url, "https://yt3.ggpht.com/large")

    def test_direct_live_url_extracts_video_id(self) -> None:
        self.assertEqual(
            extract_video_id_from_url("https://www.youtube.com/live/dQw4w9WgXcQ?si=share"),
            "dQw4w9WgXcQ",
        )

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

    def test_innertube_uses_browse_id_when_external_id_is_missing(self) -> None:
        actions = [
            {
                "addChatItemAction": {
                    "item": {
                        "liveChatTextMessageRenderer": {
                            "id": "yt-browse",
                            "authorName": {
                                "runs": [
                                    {
                                        "text": "Unicode 😀",
                                        "navigationEndpoint": {
                                            "browseEndpoint": {"browseId": "UC-browse-id"}
                                        },
                                    }
                                ]
                            },
                            "message": {"runs": [{"text": "Hello"}]},
                        }
                    }
                }
            }
        ]
        messages, _ = youtube_messages_from_actions(actions)
        self.assertEqual(messages[0].author_id, "UC-browse-id")

    def test_official_api_message(self) -> None:
        item = {
            "id": "official-1",
            "snippet": {
                "type": "textMessageEvent",
                "displayMessage": "Olá pelo modo oficial",
                "publishedAt": "2026-01-02T03:04:05Z",
            },
            "authorDetails": {
                "channelId": "UC-owner-id",
                "displayName": "Canal",
                "isChatOwner": True,
                "isChatModerator": False,
                "isChatSponsor": True,
            },
        }
        message = official_message_from_item(item)
        self.assertIsNotNone(message)
        self.assertEqual(message.message_id, "official-1")
        self.assertEqual(message.author_id, "UC-owner-id")
        self.assertEqual(message.badges, ("OWNER", "MEMBER"))

    def test_generated_event_text_uses_the_selected_language(self) -> None:
        actions = [
            {
                "addChatItemAction": {
                    "item": {
                        "liveChatMembershipItemRenderer": {
                            "id": "member-1",
                            "authorName": {"simpleText": "Supporter"},
                        }
                    }
                }
            }
        ]
        english, _ = youtube_messages_from_actions(actions, "en")
        portuguese, _ = youtube_messages_from_actions(actions, "pt-BR")
        self.assertEqual(english[0].text, "Became a channel member")
        self.assertEqual(portuguese[0].text, "Tornou-se membro do canal")


if __name__ == "__main__":
    unittest.main()
