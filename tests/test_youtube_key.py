from __future__ import annotations

import unittest

import requests

from sindrome_overlay.youtube_key import validate_youtube_api_key


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.call = None

    def get(self, url, **kwargs):
        self.call = (url, kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _error(reason: str) -> dict:
    return {"error": {"errors": [{"reason": reason}]}}


class YouTubeApiKeyValidationTests(unittest.TestCase):
    def test_valid_key_uses_minimal_request_and_result_contains_no_secret(self) -> None:
        secret = "AIza-secret-never-returned"
        session = FakeSession(FakeResponse(200, {"items": [{"id": "video"}]}))
        result = validate_youtube_api_key(secret, 7, session=session)
        self.assertEqual((result.request_id, result.status), (7, "valid"))
        self.assertNotIn(secret, repr(result))
        self.assertEqual(session.call[1]["params"]["part"], "id")
        self.assertEqual(session.call[1]["params"]["fields"], "items/id")
        self.assertEqual(session.call[1]["timeout"], (5, 10))

    def test_rejected_key_is_invalid(self) -> None:
        session = FakeSession(FakeResponse(400, _error("keyInvalid")))
        result = validate_youtube_api_key("bad-key", 1, session=session)
        self.assertEqual(result.status, "invalid")

    def test_key_restricted_away_from_youtube_is_invalid(self) -> None:
        session = FakeSession(FakeResponse(403, _error("accessNotConfigured")))
        result = validate_youtube_api_key("restricted-key", 2, session=session)
        self.assertEqual(result.status, "invalid")

    def test_quota_and_rate_limits_are_not_reported_as_invalid(self) -> None:
        for status_code, reason in ((403, "quotaExceeded"), (429, "rateLimitExceeded")):
            with self.subTest(reason=reason):
                session = FakeSession(FakeResponse(status_code, _error(reason)))
                result = validate_youtube_api_key("possibly-valid", 3, session=session)
                self.assertEqual(result.status, "unavailable")

    def test_network_and_server_errors_are_not_reported_as_invalid(self) -> None:
        offline = FakeSession(error=requests.ConnectionError("offline"))
        self.assertEqual(
            validate_youtube_api_key("possibly-valid", 4, session=offline).status,
            "unavailable",
        )
        server = FakeSession(FakeResponse(503, {}))
        self.assertEqual(
            validate_youtube_api_key("possibly-valid", 5, session=server).status,
            "unavailable",
        )


if __name__ == "__main__":
    unittest.main()
