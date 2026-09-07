package com.sindromegames.chatoverlay.providers;

import android.util.Log;

import androidx.annotation.Nullable;

import com.sindromegames.chatoverlay.model.ChatEmote;
import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.net.NetClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Third-party Twitch emote catalogs (BetterTTV, 7TV, FrankerFaceZ).
 *
 * The catalog is fetched once per connection on a background thread with
 * short timeouts; failures leave the map empty and messages keep rendering
 * plain text. Native Twitch emotes always win: tokens inside a native emote
 * range are never replaced.
 */
public final class ThirdPartyEmotes {
    private static final String TAG = "ThirdPartyEmotes";
    private static final int MAX_CODE_LENGTH = 40;
    private static final int MAX_MATCHES_PER_MESSAGE = 30;

    private volatile Map<String, String> codes = new LinkedHashMap<>();
    private final AtomicBoolean started = new AtomicBoolean(false);

    /** Fetches the catalogs on a background thread; only the first call runs. */
    public void loadOnce(final String channelId, final NetClient net) {
        if (!started.compareAndSet(false, true)) return;
        final Thread loader = new Thread(() -> {
            Map<String, String> loaded = new LinkedHashMap<>();
            fetchAll(channelId, net, loaded);
            if (!loaded.isEmpty()) {
                Log.i(TAG, "Loaded " + loaded.size() + " third-party emotes");
            }
            codes = loaded;
        }, "twitch-third-party-emotes");
        loader.setDaemon(true);
        loader.start();
    }

    private static void fetchAll(String channelId, NetClient net, Map<String, String> output) {
        safeMerge(output, parseBttvArray(getJsonArray(net, "https://api.betterttv.net/3/cached/emotes/global")));
        safeMerge(output, parseSeventv(getJsonObject(net, "https://7tv.io/v3/emote-sets/global")));
        safeMerge(output, parseFfz(getJsonObject(net, "https://api.frankerfacez.com/v1/set/global")));
        if (channelId != null && !channelId.isEmpty()) {
            safeMerge(output, parseBttv(getJsonObject(net,
                    "https://api.betterttv.net/3/cached/users/twitch/" + channelId)));
            safeMerge(output, parseSeventv(getJsonObject(net,
                    "https://7tv.io/v3/users/twitch/" + channelId)));
            safeMerge(output, parseFfz(getJsonObject(net,
                    "https://api.frankerfacez.com/v1/room/id/" + channelId)));
        }
        output.values().removeIf(url -> !url.startsWith("https://"));
    }

    @Nullable private static JSONObject getJsonObject(NetClient net, String url) {
        String body = getRaw(net, url);
        if (body == null) return null;
        try {
            return new JSONObject(body);
        } catch (Exception ignored) {
            return null;
        }
    }

    @Nullable private static JSONArray getJsonArray(NetClient net, String url) {
        String body = getRaw(net, url);
        if (body == null) return null;
        try {
            return new JSONArray(body);
        } catch (Exception ignored) {
            return null;
        }
    }

    @Nullable private static String getRaw(NetClient net, String url) {
        try {
            NetClient.ResponseData response = net.get(url);
            if (response.code() < 200 || response.code() >= 400) return null;
            return response.body();
        } catch (Exception ignored) {
            return null;
        }
    }

    private static void safeMerge(Map<String, String> output, Map<String, String> parsed) {
        for (Map.Entry<String, String> entry : parsed.entrySet()) {
            String code = entry.getKey();
            if (code.isEmpty() || code.length() > MAX_CODE_LENGTH) continue;
            String url = entry.getValue();
            if (url.startsWith("https://")) output.put(code, url);
        }
    }

    /** Parses a BTTV channel payload (channelEmotes + sharedEmotes). */
    public static Map<String, String> parseBttv(@Nullable JSONObject payload) {
        Map<String, String> output = new LinkedHashMap<>();
        if (payload == null) return output;
        List<Object> items = new ArrayList<>();
        addAll(items, payload.optJSONArray("channelEmotes"));
        addAll(items, payload.optJSONArray("sharedEmotes"));
        collectBttv(items, output);
        return output;
    }

    /** Parses a BTTV bare array payload (the global endpoint returns a list). */
    public static Map<String, String> parseBttvArray(@Nullable JSONArray payload) {
        Map<String, String> output = new LinkedHashMap<>();
        List<Object> items = new ArrayList<>();
        addAll(items, payload);
        collectBttv(items, output);
        return output;
    }

    private static void collectBttv(List<Object> items, Map<String, String> output) {
        for (Object raw : items) {
            if (!(raw instanceof JSONObject item)) continue;
            String code = item.optString("code", "").trim();
            String id = item.optString("id", "").trim();
            if (!code.isEmpty() && !id.isEmpty()) output.put(code, bttvUrl(id));
        }
    }

    private static String bttvUrl(String id) {
        return "https://cdn.betterttv.net/emote/" + id + "/2x";
    }

    private static String sevenTvUrl(String id) {
        return "https://cdn.7tv.app/emote/" + id + "/2x.webp";
    }

    public static Map<String, String> parseSeventv(@Nullable JSONObject payload) {
        Map<String, String> output = new LinkedHashMap<>();
        if (payload == null) return output;
        JSONObject emoteSet = payload.has("emote_set") ? payload.optJSONObject("emote_set") : payload;
        if (emoteSet == null) return output;
        JSONArray emotes = emoteSet.optJSONArray("emotes");
        if (emotes == null) return output;
        for (int index = 0; index < emotes.length(); index++) {
            JSONObject item = emotes.optJSONObject(index);
            if (item == null) continue;
            String code = item.optString("name", "").trim();
            String id = item.optString("id", "").trim();
            if (!code.isEmpty() && !id.isEmpty()) output.put(code, sevenTvUrl(id));
        }
        return output;
    }

    public static Map<String, String> parseFfz(@Nullable JSONObject payload) {
        Map<String, String> output = new LinkedHashMap<>();
        if (payload == null) return output;
        JSONObject sets = payload.optJSONObject("sets");
        if (sets == null) return output;
        List<JSONObject> selected = new ArrayList<>();
        if (payload.has("default_sets")) {
            JSONArray defaults = payload.optJSONArray("default_sets");
            if (defaults != null) {
                for (int index = 0; index < defaults.length(); index++) {
                    JSONObject chosen = sets.optJSONObject(String.valueOf(defaults.opt(index)));
                    if (chosen != null) selected.add(chosen);
                }
            }
        } else {
            JSONObject room = payload.optJSONObject("room");
            Object activeSet = room == null ? null : room.opt("set");
            if (activeSet != null) {
                JSONObject chosen = sets.optJSONObject(String.valueOf(activeSet));
                if (chosen != null) selected.add(chosen);
            }
        }
        for (JSONObject set : selected) {
            JSONArray emoticons = set.optJSONArray("emoticons");
            if (emoticons == null) continue;
            for (int index = 0; index < emoticons.length(); index++) {
                JSONObject item = emoticons.optJSONObject(index);
                if (item == null) continue;
                String code = item.optString("name", "").trim();
                JSONObject urls = item.optJSONObject("urls");
                String url = "";
                if (urls != null) {
                    url = normalizeFfzUrl(urls.optString("2", urls.optString("1",
                            urls.optString("4", ""))));
                }
                if (!code.isEmpty() && !url.isEmpty()) output.put(code, url);
            }
        }
        return output;
    }

    private static String normalizeFfzUrl(String value) {
        String url = value == null ? "" : value.trim();
        if (url.startsWith("//")) url = "https:" + url;
        return url;
    }

    private static void addAll(List<Object> target, @Nullable JSONArray array) {
        if (array == null) return;
        for (int index = 0; index < array.length(); index++) {
            Object value = array.opt(index);
            if (value != null) target.add(value);
        }
    }

    /**
     * Returns image emotes for message tokens that match a third-party code
     * and do not overlap a native Twitch emote range.
     */
    public static List<ChatEmote> findMatches(
            String text, Map<String, String> codeMap, List<ChatEmote> nativeEmotes) {
        List<ChatEmote> matches = new ArrayList<>();
        if (text == null || text.isEmpty() || codeMap.isEmpty()) return matches;
        int cursor = 0;
        for (String token : text.split("\\s+")) {
            if (matches.size() >= MAX_MATCHES_PER_MESSAGE) break;
            if (token.isEmpty()) continue;
            int start = text.indexOf(token, cursor);
            if (start < 0) continue;
            int end = start + token.length();
            cursor = end;
            String url = codeMap.get(token);
            if (url == null) continue;
            boolean occupied = false;
            for (ChatEmote nativeEmote : nativeEmotes) {
                if (start < nativeEmote.end && nativeEmote.start < end) {
                    occupied = true;
                    break;
                }
            }
            if (occupied) continue;
            matches.add(new ChatEmote(token, start, end, token, url));
        }
        return matches;
    }

    /** Test-only: injects a catalog without network access. */
    void forceCatalogForTest(Map<String, String> catalog) {
        codes = new LinkedHashMap<>(catalog);
    }

    /** Returns a copy of the message with third-party emotes appended. */
    public ChatMessage augment(ChatMessage message) {
        Map<String, String> current = codes;
        if (current.isEmpty() || message == null || message.text.isEmpty()) return message;
        List<ChatEmote> extra = findMatches(message.text, current, message.emotes);
        if (extra.isEmpty()) return message;
        List<ChatEmote> merged = new ArrayList<>(message.emotes);
        merged.addAll(extra);
        return ChatMessage.builder(message.platform, message.author, message.text)
                .authorId(message.authorId)
                .authorColor(message.authorColor)
                .messageId(message.messageId)
                .amount(message.amount)
                .kind(message.kind)
                .timestamp(message.timestamp)
                .badges(message.badges)
                .emotes(merged)
                .build();
    }
}
