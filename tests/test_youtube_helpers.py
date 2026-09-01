from __future__ import annotations

import threading
import unittest

from sindrome_overlay.providers.youtube import (
    YouTubeProvider,
    extract_json_object,
    find_continuation,
    find_live_video_id,
)


class YouTubeHelperTests(unittest.TestCase):
    def test_provider_does_not_override_thread_bootstrap(self) -> None:
        self.assertNotIn("_bootstrap", YouTubeProvider.__dict__)
        self.assertIs(YouTubeProvider._bootstrap, threading.Thread._bootstrap)

    def test_balanced_json_extraction_handles_braces_in_strings(self) -> None:
        html = 'prefix ytInitialData = {"text":"a } brace","nested":{"ok":true}}; suffix'
        self.assertEqual(
            extract_json_object(html, "ytInitialData ="),
            {"text": "a } brace", "nested": {"ok": True}},
        )

    def test_continuation_priority(self) -> None:
        node = {
            "continuations": [
                {"reloadContinuationData": {"continuation": "reload"}},
                {
                    "invalidationContinuationData": {
                        "continuation": "live",
                        "timeoutMs": 1234,
                    }
                },
            ]
        }
        self.assertEqual(find_continuation(node), ("live", 1234))

    def test_live_video_detection(self) -> None:
        node = {
            "items": [
                {"videoId": "aaaaaaaaaaa", "title": "gravado"},
                {
                    "videoId": "bbbbbbbbbbb",
                    "thumbnailOverlayTimeStatusRenderer": {"style": "LIVE"},
                },
            ]
        }
        self.assertEqual(find_live_video_id(node), "bbbbbbbbbbb")


if __name__ == "__main__":
    unittest.main()
