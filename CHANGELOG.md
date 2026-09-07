# Changelog

Notable changes to Sindrome Chat Overlay. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each released
section below is copied verbatim into the matching GitHub Release by the
build workflow, so keep one `## [x.y.z] - YYYY-MM-DD` section per version
and add the section **before** publishing the version bump.

## [1.9.0] - 2026-09-07

### Desktop

- New virtualized chat feed as the single renderer: constant memory for any
  message history, editor recycling while scrolling, and a shared OverlayShell
  core that both the floating overlay and future surfaces build on.
- Third-party emotes from BTTV, 7TV and FFZ now render next to native Twitch
  emotes, with per-provider caching and OOM-safe bitmap containment.
- Smoother scrolling and coalesced emote/badge re-renders; row-height caching
  keyed by message id.
- Hash computation moved off the UI thread for large assets.

### Android

- Third-party emote support (BTTV/7TV/FFZ) matching the desktop experience.
- Locale filtering (en, pt-rBR) for a smaller APK; R8/minified release build.
- SoundPool-based notification audio and gRPC deadlines for streaming
  stability.
- Honest unit-test configuration and centralized chat filters.

### Security hardening

- TLS hostname verification for all outbound HTTPS.
- OBS source Host-header validation (DNS-rebinding defence) with regression
  tests.
- Emote bitmap OOM containment; reserved-keyword and lint fixes across the
  Android build.

### Quality

- mypy type checking in CI (progressive config, zero issues) with regression
  tests for the settings-dialog flow.

## [1.8.9] - 2026-09-07

- Simplified YouTube setup: the main screen takes only the channel/live link
  and shows the real connection mode; the optional Data API key lives in
  Advanced settings, stays masked, and is validated without blocking the UI.
- Cleaner game-HUD chat layout: metadata stays transparent, message content
  gets a compact dark bubble, tighter spacing, and a discreet drag handle on
  the header at 0% panel opacity.
- Hardened in-app updater: background download of the exact installer with
  release-URL, size and SHA-256 verification; it always asks before running
  and never installs silently.
- Richer notification audio: six built-in sounds, independent Twitch and
  YouTube choices, previews, 0-200% volume and a global anti-spam interval.
- First release shipping the native Android app (normal chat screen plus an
  optional draggable, resizable floating overlay).

## [1.8.0] - 2026-09-05

- First version pairing the Windows overlay with the native Android app.
