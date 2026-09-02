package com.sindromegames.chatoverlay.settings;

import android.os.Handler;
import android.os.Looper;

import com.sindromegames.chatoverlay.net.NetClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class YouTubeKeyValidator {
    public enum Result { VALID, INVALID, UNAVAILABLE }
    public interface Callback { void onResult(Result result); }

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    public void validate(String rawKey, Callback callback) {
        String key = rawKey == null ? "" : rawKey.trim();
        if (key.isEmpty()) { main.post(() -> callback.onResult(Result.VALID)); return; }
        executor.execute(() -> {
            Result result = check(key);
            main.post(() -> callback.onResult(result));
        });
    }

    public void close() { executor.shutdownNow(); }

    private static Result check(String key) {
        NetClient net = new NetClient();
        try {
            Map<String, String> parameters = new LinkedHashMap<>();
            parameters.put("part", "id");
            parameters.put("id", "dQw4w9WgXcQ");
            parameters.put("key", key);
            net.getJson("https://www.googleapis.com/youtube/v3/videos", parameters);
            return Result.VALID;
        } catch (NetClient.HttpFailure failure) {
            String reason = reason(failure.responseBody).toLowerCase(Locale.ROOT);
            if (reason.contains("keyinvalid") || reason.contains("accessnotconfigured")
                    || reason.contains("iprefererblocked") || failure.code == 401)
                return Result.INVALID;
            return Result.UNAVAILABLE;
        } catch (IOException | org.json.JSONException ignored) {
            return Result.UNAVAILABLE;
        } finally {
            net.cancelAll();
        }
    }

    private static String reason(String body) {
        try {
            JSONObject error = new JSONObject(body).optJSONObject("error");
            JSONArray errors = error == null ? null : error.optJSONArray("errors");
            JSONObject first = errors == null ? null : errors.optJSONObject(0);
            return first == null ? "" : first.optString("reason", "");
        } catch (Exception ignored) { return ""; }
    }
}

