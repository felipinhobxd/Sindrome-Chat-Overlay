from __future__ import annotations

import hashlib
import queue
import tempfile
import unittest
from pathlib import Path

import requests

from sindrome_overlay.authenticode import AuthenticodeResult
from sindrome_overlay.updates import (
    LATEST_RELEASE_API,
    UpdateChecker,
    UpdateDownloader,
    parse_checksum_manifest,
    sha256_matches,
    update_from_release,
    version_tuple,
)


def _asset(version: str, name: str, size: int) -> dict[str, object]:
    return {
        "name": name,
        "size": size,
        "state": "uploaded",
        "browser_download_url": (
            "https://github.com/felipinhobxd/Sindrome-Chat-Overlay/releases/download/"
            f"v{version}/{name}"
        ),
    }


def _release(
    version: str,
    *,
    installer_size: int = 1_024,
    checksums_size: int = 96,
    **overrides,
):
    installer_name = f"SindromeChatOverlay-Setup-v{version}.exe"
    payload = {
        "tag_name": f"v{version}",
        "name": f"Sindrome Chat Overlay v{version}",
        "html_url": (
            "https://github.com/felipinhobxd/Sindrome-Chat-Overlay/releases/tag/"
            f"v{version}"
        ),
        "draft": False,
        "prerelease": False,
        "assets": [
            _asset(version, installer_name, installer_size),
            _asset(version, "SHA256SUMS.txt", checksums_size),
        ],
    }
    payload.update(overrides)
    return payload


class UpdateParsingTests(unittest.TestCase):
    def test_numeric_version_comparison_handles_double_digits(self) -> None:
        self.assertEqual(version_tuple("v1.10.2"), (1, 10, 2))
        update = update_from_release(_release("1.10.0"), "1.9.9")
        self.assertIsNotNone(update)
        self.assertEqual(update.version, "1.10.0")
        self.assertEqual(update.installer_name, "SindromeChatOverlay-Setup-v1.10.0.exe")

    def test_same_or_older_release_does_not_prompt(self) -> None:
        self.assertIsNone(update_from_release(_release("1.5.0"), "1.5.0"))
        self.assertIsNone(update_from_release(_release("1.4.9"), "1.5.0"))

    def test_draft_prerelease_and_malformed_versions_are_ignored(self) -> None:
        self.assertIsNone(update_from_release(_release("1.6.0", draft=True), "1.5.0"))
        self.assertIsNone(update_from_release(_release("1.6.0", prerelease=True), "1.5.0"))
        self.assertIsNone(update_from_release(_release("1.6.0-beta"), "1.5.0"))

    def test_release_and_asset_urls_must_be_exact_trusted_urls(self) -> None:
        payload = _release("1.6.0", html_url="https://example.com/update.exe")
        self.assertIsNone(update_from_release(payload, "1.5.0"))

        payload = _release("1.6.0")
        payload["assets"][0]["browser_download_url"] = "https://example.com/setup.exe"
        self.assertIsNone(update_from_release(payload, "1.5.0"))

    def test_missing_duplicate_or_oversized_security_asset_is_rejected(self) -> None:
        missing = _release("1.6.0")
        missing["assets"] = missing["assets"][:1]
        self.assertIsNone(update_from_release(missing, "1.5.0"))

        duplicate = _release("1.6.0")
        duplicate["assets"].append(dict(duplicate["assets"][0]))
        self.assertIsNone(update_from_release(duplicate, "1.5.0"))

        oversized = _release("1.6.0", installer_size=300 * 1024 * 1024)
        self.assertIsNone(update_from_release(oversized, "1.5.0"))

    def test_checksum_manifest_requires_one_exact_filename(self) -> None:
        name = "SindromeChatOverlay-Setup-v1.7.0.exe"
        digest = "a" * 64
        self.assertEqual(
            parse_checksum_manifest(f"{digest}  {name}\n".encode("ascii"), name),
            digest,
        )
        self.assertIsNone(
            parse_checksum_manifest(f"{digest}  ../{name}\n".encode("ascii"), name)
        )
        duplicate = f"{digest}  {name}\n{digest}  {name}\n".encode("ascii")
        self.assertIsNone(parse_checksum_manifest(duplicate, name))


class FakeResponse:
    def __init__(
        self,
        *,
        payload=None,
        data: bytes = b"{}",
        status_code: int = 200,
        url: str = "",
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.content = data
        self.url = url
        self.headers = {"Content-Length": str(len(data))}
        self.closed = False

    def json(self):
        return self.payload

    def iter_content(self, chunk_size: int):
        for start in range(0, len(self.content), max(1, chunk_size)):
            yield self.content[start : start + chunk_size]

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses=None, error: Exception | None = None) -> None:
        self.responses = responses or {}
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        if isinstance(self.responses, FakeResponse):
            return self.responses
        return self.responses[url]


class UpdateCheckerTests(unittest.TestCase):
    def test_checker_uses_public_versioned_api_and_reports_update(self) -> None:
        results = queue.Queue()
        response = FakeResponse(payload=_release("1.6.0"))
        session = FakeSession(response)
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


def _download_fixture(installer: bytes, manifest_hash: str | None = None):
    version = "1.7.0"
    name = f"SindromeChatOverlay-Setup-v{version}.exe"
    digest = manifest_hash or hashlib.sha256(installer).hexdigest()
    manifest = f"{digest}  {name}\n".encode("ascii")
    payload = _release(
        version,
        installer_size=len(installer),
        checksums_size=len(manifest),
    )
    update = update_from_release(payload, "1.6.0")
    assert update is not None
    responses = {
        update.checksums_url: FakeResponse(data=manifest, url=update.checksums_url),
        update.installer_url: FakeResponse(data=installer, url=update.installer_url),
    }
    return update, FakeSession(responses)


def _terminal_result(results: queue.Queue):
    terminal = None
    while not results.empty():
        result = results.get_nowait()
        if result.status != "progress":
            terminal = result
    return terminal


class UpdateDownloaderTests(unittest.TestCase):
    def test_download_verifies_hash_signature_and_saves_atomically(self) -> None:
        installer = b"MZ signed installer payload"
        update, session = _download_fixture(installer)
        results = queue.Queue()
        signature_calls = []

        def verify(path: Path, expected_subject: str) -> AuthenticodeResult:
            signature_calls.append((path, expected_subject))
            return AuthenticodeResult(True, "Valid", "CN=Sindrome Games")

        with tempfile.TemporaryDirectory() as directory:
            downloader = UpdateDownloader(
                results,
                update,
                download_dir=Path(directory),
                session=session,
                signature_verifier=verify,
            )
            downloader.run()
            result = _terminal_result(results)

            self.assertEqual(result.status, "ready")
            self.assertEqual(result.installer_path.read_bytes(), installer)
            self.assertTrue(sha256_matches(result.installer_path, result.sha256))
            self.assertEqual(len(signature_calls), 1)
            self.assertEqual(signature_calls[0][1], "")
            self.assertFalse(any(path.name.startswith(".") for path in Path(directory).iterdir()))

        for _url, options in session.calls:
            self.assertTrue(options["stream"])
            self.assertTrue(options["allow_redirects"])
            self.assertIn("timeout", options)

    def test_checksum_mismatch_blocks_before_signature_check(self) -> None:
        update, session = _download_fixture(b"installer", manifest_hash="0" * 64)
        results = queue.Queue()
        signature_calls = []

        def verify(path: Path, expected_subject: str) -> AuthenticodeResult:
            signature_calls.append((path, expected_subject))
            return AuthenticodeResult(True, "Valid", "CN=Sindrome Games")

        with tempfile.TemporaryDirectory() as directory:
            UpdateDownloader(
                results,
                update,
                download_dir=Path(directory),
                session=session,
                signature_verifier=verify,
            ).run()
            result = _terminal_result(results)
            self.assertEqual(result.error_code, "checksum_mismatch")
            self.assertEqual(signature_calls, [])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_signature_blocks_and_removes_partial_file(self) -> None:
        update, session = _download_fixture(b"installer")
        results = queue.Queue()

        def reject(_path: Path, _expected: str) -> AuthenticodeResult:
            return AuthenticodeResult(False, "NotSigned", error_code="signature_invalid")

        with tempfile.TemporaryDirectory() as directory:
            UpdateDownloader(
                results,
                update,
                download_dir=Path(directory),
                session=session,
                signature_verifier=reject,
            ).run()
            result = _terminal_result(results)
            self.assertEqual(result.error_code, "signature")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_packaged_app_requires_same_signer_as_current_executable(self) -> None:
        update, session = _download_fixture(b"installer")
        results = queue.Queue()
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / "current.exe"
            current.write_bytes(b"current")

            def verify(path: Path, expected: str) -> AuthenticodeResult:
                calls.append((path, expected))
                if path == current:
                    return AuthenticodeResult(True, "Valid", "CN=Sindrome Games")
                self.assertEqual(expected, "CN=Sindrome Games")
                return AuthenticodeResult(True, "Valid", "CN=Sindrome Games")

            UpdateDownloader(
                results,
                update,
                download_dir=Path(directory) / "updates",
                session=session,
                signature_verifier=verify,
                current_executable=current,
            ).run()
            self.assertEqual(_terminal_result(results).status, "ready")
            self.assertEqual(len(calls), 2)

    def test_untrusted_redirect_is_blocked(self) -> None:
        update, session = _download_fixture(b"installer")
        installer_response = session.responses[update.installer_url]
        installer_response.url = "https://example.com/installer.exe"
        results = queue.Queue()
        with tempfile.TemporaryDirectory() as directory:
            UpdateDownloader(
                results,
                update,
                download_dir=Path(directory),
                session=session,
                signature_verifier=lambda path, expected: AuthenticodeResult(
                    True, "Valid", "CN=Sindrome Games"
                ),
            ).run()
            self.assertEqual(_terminal_result(results).error_code, "untrusted_download")
            self.assertTrue(installer_response.closed)

    def test_cancel_during_signature_check_never_publishes_download(self) -> None:
        update, session = _download_fixture(b"installer")
        results = queue.Queue()
        with tempfile.TemporaryDirectory() as directory:
            downloader = None

            def verify(_path: Path, _expected: str) -> AuthenticodeResult:
                assert downloader is not None
                downloader.stop()
                return AuthenticodeResult(True, "Valid", "CN=Sindrome Games")

            downloader = UpdateDownloader(
                results,
                update,
                download_dir=Path(directory),
                session=session,
                signature_verifier=verify,
            )
            downloader.run()
            self.assertEqual(_terminal_result(results).status, "cancelled")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
