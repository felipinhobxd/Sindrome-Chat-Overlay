$ErrorActionPreference = "Stop"

$keytool = (Get-Command keytool -ErrorAction Stop).Source
$output = Join-Path $PSScriptRoot "..\sindrome-android-release.jks"
if (Test-Path $output) {
    throw "The signing file already exists: $output"
}

$storePassword = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(24))
$keyPassword = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(24))
$alias = "sindrome-chat-overlay"

& $keytool -genkeypair -v -keystore $output -storetype JKS -keyalg RSA -keysize 4096 `
    -validity 10000 -alias $alias -storepass $storePassword -keypass $keyPassword `
    -dname "CN=Sindrome Chat Overlay, OU=Android, O=Sindrome Games, C=BR"
if ($LASTEXITCODE -ne 0) { throw "keytool failed with exit code $LASTEXITCODE" }

$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($output))
$instructions = @"
Keep sindrome-android-release.jks private and backed up. Losing it prevents in-place APK updates.

Create these repository Secrets under Settings -> Secrets and variables -> Actions:

ANDROID_KEYSTORE_BASE64
$base64

ANDROID_KEYSTORE_PASSWORD
$storePassword

ANDROID_KEY_ALIAS
$alias

ANDROID_KEY_PASSWORD
$keyPassword
"@
$instructions | Set-Content (Join-Path $PSScriptRoot "..\android-signing-secrets.txt") -Encoding utf8

Write-Host "Signing key created at: $output"
Write-Host "Secret values saved at: android-signing-secrets.txt"
Write-Host "Never commit either file. Back up the .jks file in a secure location."

