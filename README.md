# Sindrome Chat Overlay

A transparent Windows overlay that combines live **Twitch** and **YouTube** messages in one always-on-top window.

The app starts in English and also includes a complete **Português (Brasil)** interface. It is read-only: it never sends chat messages, asks for platform passwords, or writes chat content to log files.

## Download

Open the [latest release](https://github.com/felipinhobxd/Twitch-Youtube-ChatOverlay/releases/latest) and choose one of these files:

- **`SindromeChatOverlay-Setup-vX.Y.Z.exe` — recommended.** Installs the app for the current Windows user, creates Start Menu and optional desktop shortcuts, and adds a standard uninstaller.
- **`SindromeChatOverlay.exe`** — portable standalone executable; no installation required.
- **`SindromeChatOverlay-Windows-vX.Y.Z.zip`** — portable executable plus documentation and license files.
- **`SHA256SUMS.txt`** — SHA-256 checksums for verifying the downloads.

The downloadable executables are built automatically on a clean GitHub-hosted Windows runner from the source code in this repository.

## Default channels

- Twitch: `sindromegames`
- YouTube: `https://www.youtube.com/@SindromeGames/live`

You can replace either channel in the app settings.

## Features

- Combines Twitch and YouTube messages in arrival order.
- Automatically detects an active YouTube live stream from a channel URL.
- Visually identifies Twitch, YouTube, moderators, subscribers, members, Bits, Super Chats, and membership events.
- Automatically reconnects after temporary network or platform failures.
- Automatically scrolls to keep the newest message visible.
- Plays a short sound for each new Twitch or YouTube message.
- Removes a message when the platform reports that it was deleted.
- Transparent, borderless, resizable, and always-on-top window.
- Click-through mode prevents the overlay from capturing mouse input while gaming.
- Global `Ctrl + Shift + O` shortcut locks or unlocks mouse clicks.
- System tray menu for showing, hiding, configuring, locking, or closing the app.
- Configurable font size, opacity, message limit, and message lifetime.
- English and Brazilian Portuguese interface languages.
- Persistent user settings and a rotating technical log at `%APPDATA%\SindromeChatOverlay\overlay.log`.

> YouTube integration displays a live stream's **live chat**, not regular comments posted below recorded videos.

## Language

English is used on the first launch. To switch languages:

1. Open the gear button.
2. Select **Português (Brasil)** under **Language**.
3. Select **Save**.

The main window, settings, system tray, notifications, platform statuses, automatic event text, and known badge names are translated together. The preference is saved for future launches.

## How to use

- Drag the top bar to move the overlay.
- Drag the lower-right corner to resize it.
- Select the gear button to change channels, language, and appearance.
- Automatic scrolling and message sounds can be disabled independently.
- Select the lock button or press `Ctrl + Shift + O` to enable click-through mode.
- When locked, use the same shortcut or the system tray icon to unlock the overlay.
- The `⌫` button only clears the local overlay; it does not delete platform messages.

Borderless-windowed or windowed games provide the best compatibility. Windows may prevent overlays from appearing above some exclusive-fullscreen games.

## YouTube modes

No API key is required by default. Automatic mode reads public data used by YouTube's live chat page.

Each user may optionally enter their own **YouTube Data API v3** key. When a key is present, the app uses the official API endpoints. Never embed a personal key in source code or in an executable you intend to share.

Automatic mode follows a public but undocumented YouTube interface, so a future site change may require an application update. Official API mode is the more stable option when a key is available.

## Troubleshooting

### YouTube shows “Waiting for the next live stream”

- Confirm that the stream is currently live and public chat is enabled.
- For an unlisted live stream, paste the complete video URL into settings.
- Private or members-only streams require authentication and cannot be read by public mode.

### Twitch messages do not appear

- Confirm the channel name and verify that its chat is publicly available.
- Some corporate networks or antivirus products block TLS port `6697`, used by Twitch IRC.
- Inspect `%APPDATA%\SindromeChatOverlay\overlay.log` for the reconnect reason.

### Windows SmartScreen displays a warning

The generated files do not have a commercial code-signing certificate. SmartScreen may warn about new, unsigned applications. Only run builds from this repository or another source you trust.

### The overlay disappeared or does not receive clicks

- Look for the Sindrome Chat Overlay icon in the Windows system tray.
- Press `Ctrl + Shift + O`.
- To reset settings, close the app and remove `%APPDATA%\SindromeChatOverlay\settings.json`.

## Run from source

Install [64-bit Python 3.12](https://www.python.org/downloads/windows/) and enable **Add Python to PATH**, then double-click `RUN_APP.bat`.

Alternatively, use PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py
```

## Build the portable executable

Double-click `BUILD_EXE.bat`. It creates an isolated environment, installs the build dependencies, generates the icon and notification sound, and runs PyInstaller. The result is written to:

```text
dist\SindromeChatOverlay.exe
```

## Build the installer

The release workflow uses [Inno Setup](https://jrsoftware.org/isinfo.php) and `installer/SindromeChatOverlay.iss` to create the installer. After building the portable executable, a local installer can be compiled with:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=1.2.0 installer\SindromeChatOverlay.iss
```

The installer uses a stable application ID, supports in-place upgrades, installs per user without requiring administrator access, creates shortcuts, and includes an uninstaller.

## Automated Windows releases

`.github/workflows/build-windows.yml` runs the unit tests, builds the portable executable, compiles the installer on Windows, creates checksums, uploads a GitHub Actions artifact, and publishes all downloadable files under the version found in `pyproject.toml`.

The workflow runs after a push to `main` and can also be started manually from **Actions → Build Windows release → Run workflow**.

## Development notes

Network providers run in separate worker threads; only the main thread updates the Qt interface. Requests use HTTPS/TLS, timeouts, and exponential reconnect delays. API keys are never written to the technical log.

## References

The user experience was inspired by [Transparent Twitch Chat Overlay](https://github.com/baffler/Transparent-Twitch-Chat-Overlay) and [Ghost Chat](https://github.com/Enubia/ghost-chat). This project was implemented independently in Python. See `THIRD_PARTY_NOTICES.md` for dependency and reference notices.

## License

Original project code is available under the MIT License. Dependencies retain their respective licenses.
