package com.sindromegames.chatoverlay.util;

import android.graphics.Color;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;

public final class UserColor {
    private static final ConcurrentHashMap<String, Integer> CACHE = new ConcurrentHashMap<>();

    private UserColor() {}

    public static int resolve(String platform, String userId, String name, String supplied) {
        String identity = !safe(userId).isEmpty() ? "id:" + safe(userId)
                : "name:" + safe(name).toLowerCase(Locale.ROOT);
        String key = safe(platform).toLowerCase(Locale.ROOT) + ":" + identity + ":" + safe(supplied);
        return CACHE.computeIfAbsent(key, ignored -> compute(platform, identity, supplied));
    }

    private static int compute(String platform, String identity, String supplied) {
        if ("twitch".equalsIgnoreCase(platform) && safe(supplied).matches("#[0-9a-fA-F]{6}")) {
            return makeReadable(Color.parseColor(supplied));
        }
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest((safe(platform) + ":" + identity).getBytes(StandardCharsets.UTF_8));
            float hue = (((digest[0] & 0xff) << 8) | (digest[1] & 0xff)) * 360f / 65536f;
            float saturation = 0.70f + (digest[2] & 0xff) / 255f * 0.12f;
            float value = 0.85f + (digest[3] & 0xff) / 255f * 0.12f;
            return makeReadable(Color.HSVToColor(new float[]{hue, saturation, value}));
        } catch (Exception ignored) {
            return Color.rgb(183, 194, 216);
        }
    }

    private static int makeReadable(int color) {
        float[] hsv = new float[3];
        Color.colorToHSV(color, hsv);
        double contrast = contrast(color, Color.rgb(11, 16, 27));
        while (contrast < 4.5 && hsv[2] < 1f) {
            hsv[2] = Math.min(1f, hsv[2] + 0.025f);
            color = Color.HSVToColor(hsv);
            contrast = contrast(color, Color.rgb(11, 16, 27));
        }
        return color;
    }

    static double contrast(int a, int b) {
        double la = luminance(a), lb = luminance(b);
        return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
    }

    private static double luminance(int color) {
        double r = linear(Color.red(color) / 255.0);
        double g = linear(Color.green(color) / 255.0);
        double b = linear(Color.blue(color) / 255.0);
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }

    private static double linear(double value) {
        return value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
    }

    private static String safe(String value) { return value == null ? "" : value.trim(); }
}

