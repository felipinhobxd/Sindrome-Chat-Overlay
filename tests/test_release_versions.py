from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

from sindrome_overlay import __version__

ROOT = Path(__file__).resolve().parents[1]


class ReleaseVersionTests(unittest.TestCase):
    def test_windows_android_and_changelog_versions_match(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        desktop_version = pyproject["project"]["version"]
        gradle = (ROOT / "android" / "build.gradle").read_text(encoding="utf-8")
        android_name = re.search(r'(?m)^\s*versionName\s+"([^"]+)"', gradle)
        android_code = re.search(r"(?m)^\s*versionCode\s+(\d+)", gradle)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertRegex(desktop_version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(__version__, desktop_version)
        self.assertIsNotNone(android_name)
        self.assertEqual(android_name.group(1), desktop_version)
        self.assertIsNotNone(android_code)
        self.assertGreater(int(android_code.group(1)), 0)
        self.assertEqual(
            len(re.findall(r"(?m)^## \[" + re.escape(desktop_version) + r"\] - ", changelog)),
            1,
            "Release needs exactly one versioned changelog section",
        )


if __name__ == "__main__":
    unittest.main()
