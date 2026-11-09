from __future__ import annotations

import json
import logging
import unittest
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sindrome_overlay.models import ChatEmote, ChatMessage
from sindrome_overlay.obs_source import ObsChatSourceServer, ObsSourceConfig, message_payload


class ObsSourcePayloadTests(unittest.TestCase):
    def test_twitch_and_youtube_emotes_are_serialized_without_html(self) -> None:
        twitch = ChatMessage(
            "twitch",
            "tester",
            "hi Kappa!",
            author_colour="#00FF00",
            emotes=(ChatEmote("25", 3, 8, "Kappa"),),
        )
        payload = message_payload(twitch)
        self.assertEqual(payload["segments"][0], {"type": "text", "text": "hi "})
        self.assertEqual(payload["segments"][1]["type"], "emote")
        self.assertIn("static-cdn.jtvnw.net/emoticons/v2/25/", payload["segments"][1]["url"])
        self.assertEqual(payload["segments"][2], {"type": "text", "text": "!"})

        youtube = ChatMessage(
            "youtube",
            "viewer",
            "hello :party:",
            emotes=(
                ChatEmote(
                    "UC123:party",
                    6,
                    13,
                    ":party:",
                    "https://yt3.ggpht.com/example=s48-c-k-c0x00ffffff-no-rj",
                ),
            ),
        )
        youtube_payload = message_payload(youtube)
        self.assertEqual(youtube_payload["segments"][1]["type"], "emote")
        self.assertTrue(youtube_payload["segments"][1]["url"].startswith("https://yt3.ggpht.com/"))

    def test_untrusted_youtube_emote_url_falls_back_to_text(self) -> None:
        message = ChatMessage(
            "youtube",
            "viewer",
            ":bad:",
            emotes=(
                ChatEmote(
                    "bad",
                    0,
                    5,
                    ":bad:",
                    "https://example.com/not-trusted.png",
                ),
            ),
        )
        self.assertEqual(
            message_payload(message)["segments"],
            [{"type": "text", "text": ":bad:"}],
        )


class ObsSourceServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ObsChatSourceServer(
            logging.getLogger("obs-source-test"),
            ObsSourceConfig(port=0, max_messages=20, font_size=22),
        )
        self.assertTrue(self.server.start())

    def tearDown(self) -> None:
        self.server.stop()

    def test_source_is_local_only_serves_transparent_chat_and_bounds_history(self) -> None:
        self.assertTrue(self.server.url.startswith("http://127.0.0.1:"))
        self.assertNotIn("0.0.0.0", self.server.url)

        with urlopen(self.server.url, timeout=3) as response:  # noqa: S310 - localhost test
            html = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
        self.assertIn("Sindrome OBS Chat Source", html)
        self.assertIn("background: transparent", html)
        self.assertNotIn("<audio", html.lower())

        for index in range(25):
            self.server.publish_message(
                ChatMessage(
                    "twitch",
                    f"user{index}",
                    f"message {index}",
                    message_id=f"m{index}",
                    timestamp=datetime(2026, 9, 4, 20, 0, tzinfo=UTC),
                )
            )

        api_url = self.server.url.replace("/obs-chat", "/api/state?revision=-1")
        with urlopen(api_url, timeout=3) as response:  # noqa: S310 - localhost test
            state = json.loads(response.read().decode("utf-8"))
        self.assertEqual(len(state["messages"]), 20)
        self.assertEqual(state["messages"][0]["message_id"], "m5")
        self.assertEqual(state["messages"][-1]["message_id"], "m24")
        self.assertEqual(state["config"]["font_size"], 22)

        unchanged = self.server.url.replace(
            "/obs-chat",
            f"/api/state?revision={state['revision']}",
        )
        with urlopen(unchanged, timeout=3) as response:  # noqa: S310 - localhost test
            self.assertEqual(response.status, 204)
            self.assertEqual(response.read(), b"")

    def test_provider_delete_and_clear_are_reflected(self) -> None:
        self.server.publish_message(
            ChatMessage("twitch", "one", "first", message_id="one")
        )
        self.server.publish_message(
            ChatMessage("youtube", "two", "second", message_id="two")
        )
        self.server.remove_message("one")
        snapshot = self.server.snapshot()
        self.assertEqual([item["message_id"] for item in snapshot["messages"]], ["two"])

        self.server.clear_messages("youtube")
        self.assertEqual(self.server.snapshot()["messages"], [])

    def test_config_update_does_not_expire_messages_by_time(self) -> None:
        self.server.publish_message(
            ChatMessage("twitch", "one", "persistent", message_id="persistent")
        )
        before = self.server.snapshot()["messages"]
        self.server.configure(
            ObsSourceConfig(port=0, max_messages=20, font_size=30, message_background_opacity=0)
        )
        after = self.server.snapshot()["messages"]
        self.assertEqual(before, after)
        self.assertEqual(after[0]["message_id"], "persistent")
        self.assertEqual(self.server.snapshot()["config"]["message_background_opacity"], 0)

    def test_requests_with_a_foreign_host_header_are_rejected(self) -> None:
        # DNS rebinding: an attacker page resolving its own domain to
        # 127.0.0.1 arrives with a non-loopback Host header and must not be
        # able to read the chat payload.
        bound_port = self.server.bound_port
        request = Request(
            f"http://127.0.0.1:{bound_port}/api/state?revision=-1",
            headers={"Host": "attacker.example:8080"},
        )
        try:
            with urlopen(request, timeout=3) as response:  # noqa: S310 - localhost test
                self.fail(f"expected rejection, got HTTP {response.status}")
        except HTTPError as error:
            self.assertEqual(error.code, 403)

        allowed = Request(
            f"http://127.0.0.1:{bound_port}/api/state?revision=-1",
            headers={"Host": f"127.0.0.1:{bound_port}"},
        )
        with urlopen(allowed, timeout=3) as response:  # noqa: S310 - localhost test
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main()
