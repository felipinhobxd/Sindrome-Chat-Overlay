package com.sindromegames.chatoverlay.util;

import java.net.URI;
import java.net.URISyntaxException;
import java.net.URLDecoder;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class UrlNormalizer {
    private static final Pattern TWITCH = Pattern.compile("^[A-Za-z0-9_]{3,25}$");
    private static final Pattern VIDEO_ID = Pattern.compile("^[A-Za-z0-9_-]{11}$");

    private UrlNormalizer() {}

    public static String twitchChannel(String value) {
        String raw = safe(value).replaceFirst("^@", "");
        if (raw.contains("://") || raw.toLowerCase(Locale.ROOT).startsWith("www.")) {
            try {
                URI uri = new URI(raw.contains("://") ? raw : "https://" + raw);
                String host = stripWww(uri.getHost());
                if (!("twitch.tv".equals(host) || "m.twitch.tv".equals(host))) return "";
                String[] parts = safe(uri.getPath()).replaceFirst("^/", "").split("/");
                raw = parts.length == 0 ? "" : parts[0];
            } catch (URISyntaxException ignored) { return ""; }
        }
        raw = raw.toLowerCase(Locale.ROOT);
        return TWITCH.matcher(raw).matches() ? raw : "";
    }

    public static String youtubeInput(String value) {
        String raw = safe(value);
        if (VIDEO_ID.matcher(raw).matches()) return "https://www.youtube.com/watch?v=" + raw;
        if (raw.startsWith("@")) return "https://www.youtube.com/" + raw + "/live";
        if (!raw.contains("://")) {
            if (raw.toLowerCase(Locale.ROOT).startsWith("youtube.com/")
                    || raw.toLowerCase(Locale.ROOT).startsWith("www.youtube.com/")
                    || raw.toLowerCase(Locale.ROOT).startsWith("youtu.be/")) {
                raw = "https://" + raw;
            } else {
                return "https://www.youtube.com/@" + raw.replaceFirst("^@", "") + "/live";
            }
        }
        try {
            URI uri = new URI(raw);
            String host = stripWww(uri.getHost());
            if ("youtu.be".equals(host)) {
                String id = safe(uri.getPath()).replaceFirst("^/", "").split("/")[0];
                return VIDEO_ID.matcher(id).matches()
                        ? "https://www.youtube.com/watch?v=" + id : "";
            }
            if (!("youtube.com".equals(host) || "m.youtube.com".equals(host))) return "";
            if ("/watch".equals(uri.getPath())) {
                String id = queryParameter(uri.getRawQuery(), "v");
                return VIDEO_ID.matcher(id).matches()
                        ? "https://www.youtube.com/watch?v=" + id : "";
            }
            if (safe(uri.getPath()).startsWith("/live/")) {
                String[] parts = uri.getPath().split("/");
                if (parts.length > 2 && VIDEO_ID.matcher(parts[2]).matches())
                    return "https://www.youtube.com/watch?v=" + parts[2];
            }
            String path = safe(uri.getPath()).replaceFirst("/$", "");
            if (path.isEmpty()) return "";
            return "https://www.youtube.com" + path + (path.endsWith("/live") ? "" : "/live");
        } catch (URISyntaxException ignored) { return ""; }
    }

    public static String youtubeVideoId(String normalized) {
        try {
            URI uri = new URI(normalized);
            String id = queryParameter(uri.getRawQuery(), "v");
            return VIDEO_ID.matcher(id).matches() ? id : "";
        } catch (URISyntaxException ignored) { return ""; }
    }

    private static String queryParameter(String query, String name) {
        if (query == null) return "";
        for (String item : query.split("&")) {
            String[] pair = item.split("=", 2);
            if (pair.length == 2 && name.equals(decode(pair[0]))) return decode(pair[1]);
        }
        return "";
    }

    private static String stripWww(String host) {
        if (host == null) return "";
        String value = host.toLowerCase(Locale.ROOT);
        return value.startsWith("www.") ? value.substring(4) : value;
    }

    private static String decode(String value) {
        try { return URLDecoder.decode(value, "UTF-8"); }
        catch (java.io.UnsupportedEncodingException ignored) { return value; }
    }

    private static String safe(String value) { return value == null ? "" : value.trim(); }
}
