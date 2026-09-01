# Sindrome Chat Overlay

A transparent Windows overlay that combines live **Twitch** and **YouTube** messages in one always-on-top window.

The app starts in English and also includes a complete **Português (Brasil)** interface. It is read-only: it never sends chat messages, asks for platform passwords, or writes chat content to log files.

## Download

Open the [latest release](https://github.com/felipinhobxd/Sindrome-Chat-Overlay/releases/latest) and choose one of these files:

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
- Renders native Twitch emotes as images inside messages.
- Renders official Twitch badge images next to usernames, including event and recap badges.
- Gives each username an individual, stable, readable colour without changing platform labels or badges.
- Uses the user's official Twitch chat colour when available and a deterministic account-ID colour for YouTube and Twitch fallbacks.
- Automatically detects an active YouTube live stream from a channel URL.
- Uses YouTube's official low-latency `liveChatMessages.streamList` connection when a Data API key is configured.
- Visually identifies Twitch, YouTube, moderators, subscribers, members, Bits, Super Chats, and membership events.
- Automatically reconnects after temporary network or platform failures.
- Automatically scrolls to keep the newest message visible.
- Plays a short sound for each new Twitch or YouTube message.
- Removes a message when the platform reports that it was deleted.
- Transparent, borderless, resizable, and always-on-top window.
- Click-through mode prevents the overlay from capturing mouse input while gaming.
- Native Windows global `Ctrl + Shift + O` shortcut locks or unlocks mouse clicks with one press, even when another application has focus.
- System tray menu for showing, hiding, configuring, locking, or closing the app.
- Configurable font size, opacity, message limit, and message lifetime.
- English and Brazilian Portuguese interface languages.
- Checks the official GitHub Releases page in the background at startup and asks before opening a newer stable version's download page.
- Persistent user settings and a rotating technical log at `%APPDATA%\SindromeChatOverlay\overlay.log`.
- Asynchronous Twitch image downloads with a bounded local cache under `%APPDATA%\SindromeChatOverlay\twitch-assets`.

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
- Automatic update checks can be disabled under Appearance. No GitHub account or token is required.
- Select the lock button or press `Ctrl + Shift + O` to enable click-through mode.
- When locked, use the same shortcut or the system tray icon to unlock the overlay.
- The `⌫` button only clears the local overlay; it does not delete platform messages.

Windowed and borderless-fullscreen games provide the best compatibility. The app uses the native Windows TOPMOST Z-order, reapplies it after restore, and does not activate the overlay while click-through is enabled.

Exclusive fullscreen is different: a game that owns the display surface can bypass normal desktop composition, so Windows may not be able to place any ordinary top-level window above it. This project intentionally does not inject DLLs, hook DirectX, modify game processes, or use anti-cheat-sensitive techniques. Use borderless fullscreen when an exclusive-fullscreen game hides the overlay.

## YouTube connection

The settings intentionally contain only two YouTube inputs:

- **Channel or live stream:** a channel handle/URL or a specific live video URL. The app resolves this to the active Video ID automatically.
- **YouTube Data API key (optional):** enables the official low-latency API path. The field is masked. On Windows, the saved value is encrypted for the current Windows account with DPAPI and is never written to the technical log.

When a Data API key is present, the app:

1. resolves the channel/live URL to a Video ID;
2. calls `videos.list(part=liveStreamingDetails)` to discover `activeLiveChatId`;
3. opens `liveChatMessages.streamList` over a background gRPC/HTTP/2 connection;
4. preserves `nextPageToken` when reconnecting, keeps response order, and ignores duplicate message IDs;
5. falls back to `liveChatMessages.list` only if the streaming transport repeatedly cannot be established. The fallback waits for the exact `pollingIntervalMillis` returned by YouTube.

Without a key, automatic mode reads the public live-chat data used by YouTube's web page. This mode requires no account, but it uses an undocumented public interface that YouTube may change. OAuth is not used because the overlay only reads public chat.

| Item | Purpose |
| --- | --- |
| Channel/live URL | Finds the current Video ID or identifies a specific live video. |
| Video ID | Identifies the live video; discovered automatically. |
| Live Chat ID | Identifies that video's live chat; discovered automatically in official API mode. |
| Data API key | Authorizes public YouTube Data API requests and the official streaming connection. |
| OAuth | Not used; no YouTube account access is requested. |
| Stream Key | Broadcast credential for an encoder. It is never requested, stored, or used to read chat. |

Never embed a personal Data API key in source code or an executable you intend to share.

## Troubleshooting

### YouTube shows “Waiting for the next live stream”

- Confirm that the stream is currently live and public chat is enabled.
- For an unlisted live stream, paste the complete video URL into settings.
- Private or members-only streams require authentication and cannot be read by public mode.

### Twitch messages do not appear

- Confirm the channel name and verify that its chat is publicly available.
- Some corporate networks or antivirus products block TLS port `6697`, used by Twitch IRC.
- Inspect `%APPDATA%\SindromeChatOverlay\overlay.log` for the reconnect reason.

### A Twitch emote or badge briefly appears as text

Images are downloaded asynchronously so the chat never waits for the Twitch CDN. The name is used as a safe fallback during the first download or if the image service is temporarily unavailable. Successfully downloaded images are cached for later messages and future launches.

### Windows SmartScreen displays a warning

The generated files do not have a commercial code-signing certificate. SmartScreen may warn about new, unsigned applications. Only run builds from this repository or another source you trust.

### The overlay disappeared or does not receive clicks

- Look for the Sindrome Chat Overlay icon in the Windows system tray.
- Press `Ctrl + Shift + O`.
- To reset settings, close the app and remove `%APPDATA%\SindromeChatOverlay\settings.json`.

If Windows reports that the global shortcut is unavailable, another program has already registered `Ctrl + Shift + O`. Close or reconfigure that program. Until the conflict is removed, the app provides a focused-window fallback and shows a tray warning.

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
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=1.5.0 installer\SindromeChatOverlay.iss
```

The installer uses a stable application ID, supports in-place upgrades, installs per user without requiring administrator access, creates shortcuts, and includes an uninstaller.

## Automated Windows releases

`.github/workflows/build-windows.yml` runs the unit tests, builds the portable executable, compiles the installer on Windows, creates checksums, uploads a GitHub Actions artifact, and publishes all downloadable files under the version found in `pyproject.toml`.

The workflow runs after a push to `main` and can also be started manually from **Actions → Build Windows release → Run workflow**.

## Development notes

Network providers and the startup update check run in separate worker threads; only the main thread updates the Qt interface. Requests use HTTPS/TLS, timeouts, bounded reconnect delays, message-ID deduplication, and bounded UI/image caches. Provider shutdown cancels the active Twitch socket or YouTube stream before reconnection. API keys are never written to the technical log.

The updater performs one unauthenticated request to GitHub's public `releases/latest` endpoint at startup. It accepts only newer stable `X.Y.Z` releases and only opens a validated `https://github.com/felipinhobxd/Sindrome-Chat-Overlay/releases/tag/...` URL after the user confirms. It never downloads or runs an executable silently.

## References

The user experience was inspired by [Transparent Twitch Chat Overlay](https://github.com/baffler/Transparent-Twitch-Chat-Overlay) and [Ghost Chat](https://github.com/Enubia/ghost-chat). This project was implemented independently in Python. See `THIRD_PARTY_NOTICES.md` for dependency and reference notices.

## License

Original project code is available under the MIT License. Dependencies retain their respective licenses.
