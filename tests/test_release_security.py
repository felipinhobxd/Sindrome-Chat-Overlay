from __future__ import annotations

import unittest
from pathlib import Path


class ReleaseSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path(".github/workflows/build-windows.yml").read_text(encoding="utf-8")

    def test_release_uses_oidc_and_no_long_lived_signing_secret(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("environment: production-signing", self.workflow)
        self.assertIn("uses: azure/login@v3", self.workflow)
        self.assertIn("if: github.event_name != 'pull_request'", self.workflow)
        self.assertNotIn("AZURE_CLIENT_SECRET", self.workflow)
        self.assertNotIn(".pfx", self.workflow.lower())

    def test_pull_requests_test_windows_build_without_signing_access(self) -> None:
        self.assertIn("pull_request:", self.workflow)
        test_job = self.workflow.split("  test-windows:", 1)[1].split("  build:", 1)[0]
        self.assertIn("if: github.event_name == 'pull_request'", test_job)
        self.assertIn("contents: read", test_job)
        self.assertNotIn("id-token: write", test_job)
        self.assertNotIn("artifact-signing-action", test_job)

    def test_portable_and_installer_are_both_signed(self) -> None:
        self.assertEqual(self.workflow.count("uses: azure/artifact-signing-action@v2"), 2)
        self.assertIn("dist\\SindromeChatOverlay.exe", self.workflow)
        self.assertIn("SindromeChatOverlay-Setup-v${{ env.VERSION }}.exe", self.workflow)
        self.assertIn("Get-AuthenticodeSignature", self.workflow)

    def test_signatures_are_verified_before_checksums_and_release(self) -> None:
        portable_sign = self.workflow.index("Sign portable executable with Azure Artifact Signing")
        archive = self.workflow.index("Build portable archive")
        installer_sign = self.workflow.index("Sign Windows installer with Azure Artifact Signing")
        verify = self.workflow.index("Verify Authenticode signatures")
        checksums = self.workflow.index("Generate SHA-256 checksums")
        publish = self.workflow.index("Publish GitHub release")
        self.assertLess(portable_sign, archive)
        self.assertLess(installer_sign, verify)
        self.assertLess(verify, checksums)
        self.assertLess(checksums, publish)


if __name__ == "__main__":
    unittest.main()
