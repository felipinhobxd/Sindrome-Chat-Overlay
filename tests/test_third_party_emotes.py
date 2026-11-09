from __future__ import annotations

import unittest

import requests
from unittest.mock import patch

from sindrome_overlay.models import ChatEmote, ChatMessage
from sindrome_overlay.providers.third_party_emotes import (
    ThirdPartyEmoteResolver,
    find_code_matches,
    parse_bttv_payload,
    parse_ffz_payload,
    parse_seventv_payload,
)


class ParserTests(unittest.TestCase):
    def test_bttv_global_and_channel_payloads(self) -> None:
        global_payload = [{"id": "abc", "code": "KappaPride"}, {"id": "x", "code": ""}]
        self.assertEqual(
            parse_bttv_payload(global_payload),
            {"KappaPride": "https://cdn.betterttv.net/emote/abc/2x"},
        )
        channel_payload = {
            "channelEmotes": [{"id": "ch1", "code": "ChannelEmote"}],
            "sharedEmotes": [{"id": "sh1", "code": "SharedEmote"}],
        }
        self.assertEqual(
            parse_bttv_payload(channel_payload),
            {
                "ChannelEmote": "https://cdn.betterttv.net/emote/ch1/2x",
                "SharedEmote": "https://cdn.betterttv.net/emote/sh1/2x",
            },
        )

    def test_seventv_payloads(self) -> None:
        global_payload = {"emotes": [{"name": "widepeepoHappy", "id": "7tv1"}]}
        self.assertEqual(
            parse_seventv_payload(global_payload),
            {"widepeepoHappy": "https://cdn.7tv.app/emote/7tv1/2x.webp"},
        )
        user_payload = {"emote_set": {"emotes": [{"name": "Sadge", "id": "7tv2"}]}}
        self.assertEqual(
            parse_seventv_payload(user_payload),
            {"Sadge": "https://cdn.7tv.app/emote/7tv2/2x.webp"},
        )

    def test_ffz_global_and_room_payloads(self) -> None:
        global_payload = {
            "default_sets": [1],
            "sets": {
                "1": {"emoticons": [{"name": "FeelsDankMan", "urls": {"1": "//cdn.frankerfacez.com/1", "2": "//cdn.frankerfacez.com/2"}}]}
            },
        }
        self.assertEqual(
            parse_ffz_payload(global_payload),
            {"FeelsDankMan": "https://cdn.frankerfacez.com/2"},
        )
        room_payload = {
            "room": {"set": 7},
            "sets": {"7": {"emoticons": [{"name": "RoomEmote", "urls": {"4": "//cdn.frankerfacez.com/room4"}}]}},
        }
        self.assertEqual(
            parse_ffz_payload(room_payload),
            {"RoomEmote": "https://cdn.frankerfacez.com/room4"},
        )

    def test_malformed_payloads_return_empty_maps(self) -> None:
        for parser in (parse_bttv_payload, parse_seventv_payload, parse_ffz_payload):
            self.assertEqual(parser(None), {})
            self.assertEqual(parser("nope"), {})
            self.assertEqual(parser({"unexpected": 1}), {})


class MatchTests(unittest.TestCase):
    def test_matches_tokens_with_positions(self) -> None:
        codes = {"Nice": "https://cdn.betterttv.net/emote/x/2x"}
        matches = find_code_matches("um Nice exemplo", codes)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].start, 3)
        self.assertEqual(matches[0].end, 7)
        self.assertEqual(matches[0].name, "Nice")

    def test_native_emote_range_is_not_replaced(self) -> None:
        codes = {"Kappa": "https://cdn.betterttv.net/emote/x/2x"}
        matches = find_code_matches("Kappa", codes, occupied=[(0, 5)])
        self.assertEqual(matches, [])

    def test_partial_suffix_is_not_matched(self) -> None:
        codes = {"Nice": "https://cdn.betterttv.net/emote/x/2x"}
        self.assertEqual(find_code_matches("Niceness", codes), [])
        # A standalone token after a non-matching prefix still matches.
        self.assertEqual(len(find_code_matches("Niceness Nice", codes)), 1)

    def test_match_cap_bounds_work(self) -> None:
        codes = {str(index): "https://cdn.betterttv.net/emote/x/2x" for index in range(60)}
        text = " ".join(str(index) for index in range(60))
        matches = find_code_matches(text, codes)
        self.assertEqual(len(matches), 30)


class ResolverTests(unittest.TestCase):
    def test_augment_appends_third_party_emotes_after_native(self) -> None:
        resolver = ThirdPartyEmoteResolver()
        with patch.object(resolver, "_lock"):
            pass
        resolver._codes = {"Nice": "https://cdn.betterttv.net/emote/x/2x"}
        native = ChatEmote(emote_id="25", start=0, end=5, name="Kappa")
        message = ChatMessage("twitch", "user", "Kappa Nice", message_id="m1", emotes=(native,))
        augmented = resolver.augment(message)
        self.assertEqual(augmented.emotes[0], native)
        self.assertEqual(augmented.emotes[1].name, "Nice")
        self.assertEqual(augmented.emotes[1].image_url, "https://cdn.betterttv.net/emote/x/2x")

    def test_augment_without_codes_returns_same_fields(self) -> None:
        resolver = ThirdPartyEmoteResolver()
        message = ChatMessage("twitch", "user", "texto simples", message_id="m1")
        augmented = resolver.augment(message)
        self.assertEqual(augmented, message)

    def test_load_rejects_non_https_urls(self) -> None:
        resolver = ThirdPartyEmoteResolver()
        fake_payloads = {
            "https://api.betterttv.net/3/cached/emotes/global": [{"id": "1", "code": "FromBttv"}],
            "https://7tv.io/v3/emote-sets/global": {"emotes": [{"name": "From7tv", "id": "2"}]},
            "https://api.frankerfacez.com/v1/set/global": {
                "default_sets": [1],
                "sets": {"1": {"emoticons": [{"name": "FromFfz", "urls": {"2": "//cdn.frankerfacez.com/ok"}}]}},
            },
        }

        def fake_fetch(url: str):
            return fake_payloads.get(url)

        with patch("sindrome_overlay.providers.third_party_emotes._fetch_json", side_effect=fake_fetch):
            resolver.load("")
        codes = resolver._codes
        self.assertIn("FromBttv", codes)
        self.assertIn("From7tv", codes)
        self.assertIn("FromFfz", codes)
        for url in codes.values():
            self.assertTrue(url.startswith("https://"))

    def test_catalog_timeout_does_not_block_other_providers(self) -> None:
        resolver = ThirdPartyEmoteResolver()

        def fake_fetch(url: str):
            if "betterttv.net" in url:
                raise requests.Timeout("BTTV is temporarily unavailable")
            if "7tv.io" in url:
                return {"emotes": [{"name": "Healthy7TV", "id": "ok-7"}]}
            if "frankerfacez.com" in url:
                return {
                    "default_sets": [1],
                    "sets": {"1": {"emoticons": [
                        {"name": "HealthyFFZ", "urls": {"2": "//cdn.frankerfacez.com/ok"}}
                    ]}},
                }
            return None

        with patch("sindrome_overlay.providers.third_party_emotes._fetch_json", side_effect=fake_fetch):
            resolver.load("123")
        self.assertNotIn("MissingBttv", resolver._codes)
        self.assertIn("Healthy7TV", resolver._codes)
        self.assertIn("HealthyFFZ", resolver._codes)

    def test_all_failed_catalogs_preserve_last_known_good_emotes(self) -> None:
        resolver = ThirdPartyEmoteResolver()
        existing = {"StillVisible": "https://cdn.betterttv.net/emote/old/2x"}
        resolver._codes = dict(existing)
        with patch(
            "sindrome_overlay.providers.third_party_emotes._fetch_json",
            side_effect=requests.ConnectionError("network unavailable"),
        ):
            resolver.load("123")
        self.assertEqual(resolver._codes, existing)

    def test_malformed_catalog_does_not_stop_other_providers(self) -> None:
        resolver = ThirdPartyEmoteResolver()

        def fake_fetch(url: str):
            if "betterttv.net" in url:
                return [{"id": "valid", "code": "ValidBttv"}]
            if "frankerfacez.com" in url:
                return {"default_sets": 5, "sets": {}}
            return None

        with patch("sindrome_overlay.providers.third_party_emotes._fetch_json", side_effect=fake_fetch):
            resolver.load("123")
        self.assertIn("ValidBttv", resolver._codes)

    def test_stop_during_load_cannot_replace_existing_catalog(self) -> None:
        resolver = ThirdPartyEmoteResolver()
        existing = {"Previous": "https://cdn.betterttv.net/emote/previous/2x"}
        resolver._codes = dict(existing)

        def stop_during_fetch(_url: str):
            resolver.stop()
            return [{"id": "new", "code": "ShouldNotPublish"}]

        with patch(
            "sindrome_overlay.providers.third_party_emotes._fetch_json",
            side_effect=stop_during_fetch,
        ):
            resolver.load("123")
        self.assertEqual(resolver._codes, existing)


if __name__ == "__main__":
    unittest.main()
