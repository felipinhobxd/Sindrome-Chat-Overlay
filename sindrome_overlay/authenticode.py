from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthenticodeResult:
    valid: bool
    status: str
    signer_subject: str = ""
    error_code: str = ""


_SIGNATURE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$signature = Get-AuthenticodeSignature -LiteralPath $env:SINDROME_VERIFY_FILE
$subject = ''
if ($null -ne $signature.SignerCertificate) {
    $subject = [string]$signature.SignerCertificate.Subject
}
[ordered]@{
    status = [string]$signature.Status
    subject = $subject
} | ConvertTo-Json -Compress
""".strip()


def verify_authenticode(
    path: Path,
    expected_signer_subject: str = "",
) -> AuthenticodeResult:
    """Validate a Windows Authenticode signature and optional signer continuity.

    PowerShell's Get-AuthenticodeSignature delegates trust evaluation to Windows. The
    file path is passed through an environment variable so downloaded filenames never
    become executable PowerShell source.
    """

    if os.name != "nt":
        return AuthenticodeResult(False, "Unsupported", error_code="unsupported")
    try:
        resolved = Path(path).resolve(strict=True)
    except OSError:
        return AuthenticodeResult(False, "NotFound", error_code="not_found")
    if not resolved.is_file():
        return AuthenticodeResult(False, "NotFile", error_code="not_found")

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return AuthenticodeResult(False, "Unavailable", error_code="verifier_unavailable")

    environment = os.environ.copy()
    environment["SINDROME_VERIFY_FILE"] = str(resolved)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _SIGNATURE_SCRIPT,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            env=environment,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError):
        return AuthenticodeResult(False, "VerifierError", error_code="verifier_failed")

    if completed.returncode != 0 or len(completed.stdout) > 8_192:
        return AuthenticodeResult(False, "VerifierError", error_code="verifier_failed")
    try:
        payload = json.loads(completed.stdout.strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return AuthenticodeResult(False, "VerifierError", error_code="verifier_failed")
    return authenticode_result_from_payload(payload, expected_signer_subject)


def authenticode_result_from_payload(
    payload: Any,
    expected_signer_subject: str = "",
) -> AuthenticodeResult:
    """Convert the deliberately small PowerShell result into a strict trust decision."""

    if not isinstance(payload, dict):
        return AuthenticodeResult(False, "VerifierError", error_code="verifier_failed")
    status = str(payload.get("status") or "").strip()[:80]
    subject = str(payload.get("subject") or "").strip()[:1_000]
    if status != "Valid" or not subject:
        return AuthenticodeResult(False, status or "NotSigned", subject, "signature_invalid")
    if expected_signer_subject and _normalise_subject(subject) != _normalise_subject(
        expected_signer_subject
    ):
        return AuthenticodeResult(False, "SignerMismatch", subject, "signer_mismatch")
    return AuthenticodeResult(True, status, subject)


def _normalise_subject(value: str) -> str:
    return " ".join(value.split()).casefold()
