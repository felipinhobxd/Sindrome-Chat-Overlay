package com.sindromegames.chatoverlay.net;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class JsonTools {
    private static final Pattern VIDEO_ID = Pattern.compile("^[A-Za-z0-9_-]{11}$");
    // ytInitialData paths stay well below this; the cap only exists so that a
    // hostile deep-nested payload can never recurse deep enough to overflow
    // the Java call stack (StackOverflowError would escape every catch and
    // kill the process).
    private static final int MAX_TRAVERSAL_DEPTH = 128;

    private JsonTools() {}

    private record Frame(Object node, int depth) {}

    private static void pushChildren(Frame frame, Deque<Frame> stack) {
        if (frame.depth() >= MAX_TRAVERSAL_DEPTH) return;
        List<Object> children = new ArrayList<>();
        if (frame.node() instanceof JSONObject object) {
            Iterator<String> keys = object.keys();
            while (keys.hasNext()) children.add(object.opt(keys.next()));
        } else if (frame.node() instanceof JSONArray array) {
            for (int index = 0; index < array.length(); index++) children.add(array.opt(index));
        } else {
            return;
        }
        // Push reversed so the stack pops children in the original DFS order.
        for (int index = children.size() - 1; index >= 0; index--) {
            Object child = children.get(index);
            if (child instanceof JSONObject || child instanceof JSONArray)
                stack.push(new Frame(child, frame.depth() + 1));
        }
    }

    public static JSONObject extractObject(String text, String marker) {
        if (text == null || marker == null) return null;
        int markerIndex = text.indexOf(marker);
        if (markerIndex < 0) return null;
        int start = text.indexOf('{', markerIndex + marker.length());
        if (start < 0) return null;
        int depth = 0;
        boolean string = false;
        boolean escaped = false;
        for (int index = start; index < text.length(); index++) {
            char c = text.charAt(index);
            if (string) {
                if (escaped) escaped = false;
                else if (c == '\\') escaped = true;
                else if (c == '"') string = false;
                continue;
            }
            if (c == '"') string = true;
            else if (c == '{') depth++;
            else if (c == '}' && --depth == 0) {
                try { return new JSONObject(text.substring(start, index + 1)); }
                catch (JSONException ignored) { return null; }
            }
        }
        return null;
    }

    public static Object findFirst(Object node, String key) {
        if (!(node instanceof JSONObject || node instanceof JSONArray)) return null;
        Deque<Frame> stack = new ArrayDeque<>();
        stack.push(new Frame(node, 0));
        while (!stack.isEmpty()) {
            Frame frame = stack.pop();
            if (frame.node() instanceof JSONObject object) {
                if (object.has(key) && !object.isNull(key)) return object.opt(key);
            }
            pushChildren(frame, stack);
        }
        return null;
    }

    public static String findLiveVideoId(Object node) {
        if (!(node instanceof JSONObject || node instanceof JSONArray)) return "";
        Deque<Frame> stack = new ArrayDeque<>();
        stack.push(new Frame(node, 0));
        while (!stack.isEmpty()) {
            Frame frame = stack.pop();
            if (frame.node() instanceof JSONObject object) {
                String candidate = object.optString("videoId", "");
                if (VIDEO_ID.matcher(candidate).matches()) {
                    String snapshot = object.toString();
                    if (snapshot.contains("\"isLiveNow\":true")
                            || snapshot.contains("BADGE_STYLE_TYPE_LIVE_NOW")
                            || snapshot.contains("\"style\":\"LIVE\"")
                            || snapshot.toUpperCase(Locale.ROOT).contains("LIVE NOW")
                            || snapshot.toUpperCase(Locale.ROOT).contains("AO VIVO")) return candidate;
                }
            }
            pushChildren(frame, stack);
        }
        return "";
    }

    public static Continuation findContinuation(Object node) {
        String[] priorities = {"invalidationContinuationData", "timedContinuationData",
                "reloadContinuationData"};
        for (String key : priorities) {
            Object raw = findFirst(node, key);
            if (raw instanceof JSONObject value) {
                String token = value.optString("continuation", "");
                if (!token.isEmpty()) return new Continuation(token,
                        Math.max(1000, value.optLong("timeoutMs", 2000)));
            }
        }
        return new Continuation("", 2000);
    }

    public static String cleanText(Object value) {
        if (value == null || value == JSONObject.NULL) return "";
        if (value instanceof String string) return cleanWhitespace(string);
        if (value instanceof Number) return value.toString();
        if (value instanceof JSONObject object) {
            if (object.has("simpleText")) return cleanText(object.opt("simpleText"));
            if (object.has("runs")) return cleanText(object.opt("runs"));
            if (object.has("text")) return cleanText(object.opt("text"));
        }
        if (value instanceof JSONArray runs) {
            StringBuilder output = new StringBuilder();
            for (int index = 0; index < runs.length(); index++) {
                Object raw = runs.opt(index);
                if (raw instanceof String string) output.append(string);
                else if (raw instanceof JSONObject run) {
                    if (run.has("text")) output.append(run.optString("text"));
                    else if (run.opt("emoji") instanceof JSONObject emoji) {
                        JSONArray shortcuts = emoji.optJSONArray("shortcuts");
                        if (shortcuts != null && shortcuts.length() > 0)
                            output.append(shortcuts.optString(0));
                        else output.append(emoji.optString("emojiId", ""));
                    }
                }
            }
            return cleanWhitespace(output.toString());
        }
        return cleanWhitespace(value.toString());
    }

    public static String extractConfigString(String html, String key) {
        Pattern pattern = Pattern.compile("[\\\"']" + Pattern.quote(key)
                + "[\\\"']\\s*:\\s*[\\\"']([^\\\"']+)[\\\"']");
        Matcher match = pattern.matcher(html == null ? "" : html);
        return match.find() ? unescape(match.group(1)) : "";
    }

    public static String extractConfigNumber(String html, String key) {
        Pattern pattern = Pattern.compile("[\\\"']" + Pattern.quote(key)
                + "[\\\"']\\s*:\\s*(?:[\\\"'])?(\\d+)");
        Matcher match = pattern.matcher(html == null ? "" : html);
        return match.find() ? match.group(1) : "";
    }

    public static Instant parseInstant(String value) {
        try { return Instant.parse(value); }
        catch (Exception ignored) { return Instant.now(); }
    }

    public static Instant parseTimestampUsec(Object value) {
        try { return Instant.ofEpochMilli(Long.parseLong(String.valueOf(value)) / 1000L); }
        catch (Exception ignored) { return Instant.now(); }
    }

    private static String cleanWhitespace(String value) {
        return value.replace("\u0000", "").trim().replaceAll("\\s+", " ");
    }

    private static String unescape(String value) {
        return value.replace("\\u0026", "&").replace("\\/", "/");
    }

    public record Continuation(String token, long timeoutMs) {}
}

