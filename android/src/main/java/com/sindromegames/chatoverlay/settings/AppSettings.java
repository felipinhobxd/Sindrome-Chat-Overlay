package com.sindromegames.chatoverlay.settings;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.appcompat.app.AppCompatDelegate;
import androidx.core.os.LocaleListCompat;

public final class AppSettings {
    private static final String PREFS = "settings";

    public String language = "en";
    public boolean twitchEnabled = true;
    public String twitchChannel = "sindromegames";
    public boolean youtubeEnabled = true;
    public String youtubeInput = "https://www.youtube.com/@SindromeGames/live";
    public boolean autoScroll = true;
    public boolean showTimestamps = true;
    public boolean showPlatform = true;
    public boolean hideCommands = false;
    public boolean soundEnabled = true;
    public int soundVolume = 100;
    public String twitchSound = "pop";
    public String youtubeSound = "chime";
    public int soundMinIntervalMs = 500;
    public int backgroundOpacity = 0;
    public int fontSize = 15;
    public int maxMessages = 150;
    public int overlayX = 24;
    public int overlayY = 120;
    public int overlayWidth = 420;
    public int overlayHeight = 640;
    public boolean overlayClickThrough = false;

    public static AppSettings load(Context context) {
        SharedPreferences p = context.getApplicationContext()
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        AppSettings value = new AppSettings();
        value.language = normalizeLanguage(p.getString("language", value.language));
        value.twitchEnabled = p.getBoolean("twitch_enabled", value.twitchEnabled);
        value.twitchChannel = p.getString("twitch_channel", value.twitchChannel);
        value.youtubeEnabled = p.getBoolean("youtube_enabled", value.youtubeEnabled);
        value.youtubeInput = p.getString("youtube_input", value.youtubeInput);
        value.autoScroll = p.getBoolean("auto_scroll", value.autoScroll);
        value.showTimestamps = p.getBoolean("show_timestamps", value.showTimestamps);
        value.showPlatform = p.getBoolean("show_platform", value.showPlatform);
        value.hideCommands = p.getBoolean("hide_commands", value.hideCommands);
        value.soundEnabled = p.getBoolean("sound_enabled", value.soundEnabled);
        value.soundVolume = clamp(p.getInt("sound_volume", value.soundVolume), 0, 200);
        value.twitchSound = normalizeSound(p.getString("twitch_sound", value.twitchSound), "pop");
        value.youtubeSound = normalizeSound(p.getString("youtube_sound", value.youtubeSound), "chime");
        value.soundMinIntervalMs = clamp(p.getInt("sound_interval", value.soundMinIntervalMs), 0, 5000);
        value.backgroundOpacity = clamp(p.getInt("background_opacity", value.backgroundOpacity), 0, 100);
        value.fontSize = clamp(p.getInt("font_size", value.fontSize), 11, 30);
        value.maxMessages = clamp(p.getInt("max_messages", value.maxMessages), 20, 500);
        value.overlayX = p.getInt("overlay_x", value.overlayX);
        value.overlayY = p.getInt("overlay_y", value.overlayY);
        value.overlayWidth = clamp(p.getInt("overlay_width", value.overlayWidth), 280, 1600);
        value.overlayHeight = clamp(p.getInt("overlay_height", value.overlayHeight), 240, 1800);
        value.overlayClickThrough = p.getBoolean("overlay_click_through", false);
        return value;
    }

    public void save(Context context) {
        context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString("language", normalizeLanguage(language))
                .putBoolean("twitch_enabled", twitchEnabled)
                .putString("twitch_channel", safe(twitchChannel))
                .putBoolean("youtube_enabled", youtubeEnabled)
                .putString("youtube_input", safe(youtubeInput))
                .putBoolean("auto_scroll", autoScroll)
                .putBoolean("show_timestamps", showTimestamps)
                .putBoolean("show_platform", showPlatform)
                .putBoolean("hide_commands", hideCommands)
                .putBoolean("sound_enabled", soundEnabled)
                .putInt("sound_volume", clamp(soundVolume, 0, 200))
                .putString("twitch_sound", normalizeSound(twitchSound, "pop"))
                .putString("youtube_sound", normalizeSound(youtubeSound, "chime"))
                .putInt("sound_interval", clamp(soundMinIntervalMs, 0, 5000))
                .putInt("background_opacity", clamp(backgroundOpacity, 0, 100))
                .putInt("font_size", clamp(fontSize, 11, 30))
                .putInt("max_messages", clamp(maxMessages, 20, 500))
                .putInt("overlay_x", overlayX)
                .putInt("overlay_y", overlayY)
                .putInt("overlay_width", clamp(overlayWidth, 280, 1600))
                .putInt("overlay_height", clamp(overlayHeight, 240, 1800))
                .putBoolean("overlay_click_through", overlayClickThrough)
                .apply();
    }

    public static void applyLocale(Context context) {
        String language = load(context).language;
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(language));
    }

    public static String normalizeLanguage(String value) {
        return value != null && value.toLowerCase().startsWith("pt") ? "pt-BR" : "en";
    }

    public static int clamp(int value, int minimum, int maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    private static String safe(String value) { return value == null ? "" : value.trim(); }

    private static String normalizeSound(String value, String fallback) {
        if (value == null) return fallback;
        return switch (value) {
            case "soft", "pop", "chime", "arcade", "bubble", "bell" -> value;
            default -> fallback;
        };
    }
}

