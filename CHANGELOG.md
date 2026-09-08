# Changelog

Notable changes to Sindrome Chat Overlay. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each released
section below is copied verbatim into the matching GitHub Release by the
build workflow, so keep one `## [x.y.z] - YYYY-MM-DD` section per version
and add the section **before** publishing the version bump.

## [Unreleased]

## [1.9.1] - 2026-09-08

### Desktop

- Fixed the settings dialog failing to open on the published Windows build:
  the overlay injected the OBS browser-source URL into the stock settings
  dialog, which does not accept that keyword, so clicking the settings button
  or the tray entry silently did nothing whenever the OBS source was running.
  The concrete overlay now supplies its extended dialog (profiles, OBS source
  and diagnostics tabs) through a shell hook, and regression tests lock the
  dialog-constructor contract so this mismatch cannot ship again.
- Settings dialogs opened from the overlay now consistently expose the
  profiles, OBS source and diagnostics tabs regardless of how the flow was
  triggered.

### Android

- Fixed the first notification sound after app start being silent: SoundPool
  decodes samples asynchronously and play requests issued before decoding
  finished were dropped; the player now bridges that window with the same
  ToneGenerator fallback used when sample preparation fails.

### Internal

- CI: the instrumented-test job grants the runner user KVM access (udev rule
  for `/dev/kvm`), boots a `google_apis` API 30 emulator with animations
  disabled, a 10-minute boot timeout and test-report upload on failure; the
  previous setup silently fell back to software emulation and never reached
  the test phase.
- Overlay window instrumented tests proxy window mutations to the main thread
  (`runOnMainSync`), because `WindowManager.addView` requires a Looper that
  the instrumentation thread does not have.

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
