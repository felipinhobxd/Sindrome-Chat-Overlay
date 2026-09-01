from __future__ import annotations

import queue
import unittest

import requests

from sindrome_overlay.updates import (
    LATEST_RELEASE_API,
    UpdateChecker,
    update_from_release,
    version_tuple,
)


def _release(version: str, **overrides):
    payload = {
        "tag_name": f"v{version}",
        "name": f"Sindrome Chat Overlay v{version}",
        "html_url": (
            "https://github.com/felipinhobxd/Sindrome-Chat-Overlay/releases/tag/"
            f"v{version}"
        ),
        "draft": False,
        "prerelease": False,
    }
    payload.update(overrides)
    return payload


class UpdateParsingTests(unittest.TestCase):
    def test_numeric_version_comparison_handles_double_digits(self) -> None:
        self.assertEqual(version_tuple("v1.10.2"), (1, 10, 2))
        update = update_from_release(_release("1.10.0"), "1.9.9")
        self.assertIsNotNone(update)
        self.assertEqual(update.version, "1.10.0")

    def test_same_or_older_release_does_not_prompt(self) -> None:
        self.assertIsNone(update_from_release(_release("1.5.0"), "1.5.0"))
        self.assertIsNone(update_from_release(_release("1.4.9"), "1.5.0"))

    def test_draft_prerelease_and_malformed_versions_are_ignored(self) -> None:
        self.assertIsNone(update_from_release(_release("1.6.0", draft=True), "1.5.0"))
        self.assertIsNone(update_from_release(_release("1.6.0", prerelease=True), "1.5.0"))
        self.assertIsNone(update_from_release(_release("1.6.0-beta"), "1.5.0"))

    def test_untrusted_release_url_is_rejected(self) -> None:
        payload = _release("1.6.0", html_url="https://example.com/update.exe")
        self.assertIsNone(update_from_release(payload, "1.5.0"))


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


class UpdateCheckerTests(unittest.TestCase):
    def test_checker_uses_public_versioned_api_and_reports_update(self) -> None:
        results = queue.Queue()
        session = FakeSession(FakeResponse(_release("1.6.0")))
        checker = UpdateChecker(results, "1.5.0", session=session)
        checker.start()
        checker.join(timeout=1)

        self.assertFalse(checker.is_alive())
        result = results.get_nowait()
        self.assertEqual(result.status, "update")
        self.assertEqual(result.update.version, "1.6.0")
        url, options = session.calls[0]
        self.assertEqual(url, LATEST_RELEASE_API)
        self.assertEqual(options["headers"]["Accept"], "application/vnd.github+json")
        self.assertEqual(options["headers"]["X-GitHub-Api-Version"], "2026-03-10")
        self.assertEqual(options["timeout"], (5, 10))

    def test_network_error_is_quietly_reported_to_the_ui_queue(self) -> None:
        results = queue.Queue()
        session = FakeSession(error=requests.ConnectionError("offline"))
        checker = UpdateChecker(results, "1.5.0", session=session)
        checker.run()
        result = results.get_nowait()
        self.assertEqual(result.status, "error")
        self.assertIn("offline", result.error)


if __name__ == "__main__":
    unittest.main()
