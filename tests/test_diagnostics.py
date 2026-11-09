from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from sindrome_overlay.diagnostics import export_diagnostics
from sindrome_overlay.settings import Settings


class DiagnosticExportTests(unittest.TestCase):
    def test_export_is_sanitized_atomic_and_contains_support_state(self) -> None:
        api_key = "AIzaABCDEFGHIJKLMNOPQRSTUVWX123456"
        bearer = "super-private-bearer-token"
        twitch_channel = "privatechannel"
        youtube_input = "https://www.youtube.com/@PrivateChannel/live"
        settings = Settings(
            language="pt-BR",
            twitch_channel=twitch_channel,
            youtube_input=youtube_input,
            youtube_api_key=api_key,
            font_size=19,
        ).normalized()
        settings.overlay_profiles = {"Secret Name": {"font_size": 19}}
        settings.active_overlay_profile = "custom:Secret Name"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log_dir = root / "logs"
            cache_dir = root / "cache"
            log_dir.mkdir()
            cache_dir.mkdir()
            (cache_dir / "one.png").write_bytes(b"1234")
            (cache_dir / "two.png").write_bytes(b"56789")
            home_forward = str(Path.home()).replace("\\", "/")
            (log_dir / "overlay.log").write_text(
                "\n".join(
                    (
                        f"key={api_key}",
                        f"channel={twitch_channel.upper()}",
                        f"youtube={youtube_input}",
                        f'{{\"youtube_api_key\": \"{api_key}\"}}',
                        f"Authorization: Bearer {bearer}",
                        f"home={Path.home()}",
                        f"home-forward={home_forward}",
                    )
                ),
                encoding="utf-8",
            )
            destination = root / "support-package"
            saved = export_diagnostics(
                destination,
                settings,
                {
                    "global_hotkey_registered": True,
                    "message_count": 27,
                    "active_message_cards": 8,
                    "chat_messages": ["this chat text must not leave the app"],
                    "twitch_channel": twitch_channel,
                    "provider_access_token": bearer,
                },
                app_version="9.9.9-test",
                log_dir=log_dir,
                cache_dir=cache_dir,
            )

            self.assertEqual(saved.suffix, ".zip")
            self.assertTrue(saved.is_file())
            self.assertFalse(saved.with_name(saved.name + ".tmp").exists())

            with zipfile.ZipFile(saved) as archive:
                names = set(archive.namelist())
                self.assertIn("diagnostic.json", names)
                self.assertIn("README.txt", names)
                self.assertIn("logs/overlay.log.txt", names)
                self.assertFalse(any(name.endswith("settings.json") for name in names))
                report_text = archive.read("diagnostic.json").decode("utf-8")
                log_text = archive.read("logs/overlay.log.txt").decode("utf-8")

            for secret in (
                api_key,
                bearer,
                twitch_channel,
                twitch_channel.upper(),
                youtube_input,
                str(Path.home()),
                home_forward,
            ):
                self.assertNotIn(secret, report_text)
                self.assertNotIn(secret, log_text)
            self.assertNotIn("this chat text must not leave the app", report_text)

            report = json.loads(report_text)
            self.assertEqual(report["application"]["version"], "9.9.9-test")
            self.assertTrue(report["settings"]["youtube_api_key_configured"])
            self.assertNotIn("youtube_api_key", report["settings"])
            self.assertEqual(report["settings"]["active_overlay_profile"], "custom")
            self.assertEqual(report["runtime"]["global_hotkey_registered"], True)
            self.assertEqual(report["runtime"]["message_count"], 27)
            self.assertEqual(report["runtime"]["active_message_cards"], 8)
            self.assertEqual(report["runtime"]["chat_messages"], "[redacted]")
            self.assertEqual(report["runtime"]["twitch_channel"], "[redacted]")
            self.assertEqual(report["runtime"]["provider_access_token"], "[redacted]")
            self.assertEqual(report["cache"], {"bytes": 9, "file_count": 2})
            self.assertFalse(report["privacy"]["api_keys_included"])
            self.assertFalse(report["privacy"]["chat_messages_included"])


if __name__ == "__main__":
    unittest.main()
