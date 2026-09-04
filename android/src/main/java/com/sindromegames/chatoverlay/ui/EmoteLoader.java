package com.sindromegames.chatoverlay.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;

import com.sindromegames.chatoverlay.model.ChatEmote;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.HttpUrl;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public final class EmoteLoader {
    private static final long MAX_IMAGE_BYTES = 512_000L;
    private static volatile EmoteLoader instance;
    private final LruCache<String, Bitmap> memory = new LruCache<>(memoryCacheSizeKb()) {
        @Override protected int sizeOf(String key, Bitmap value) {
            return Math.max(1, value.getByteCount() / 1024);
        }
    };
    private final Map<String, List<Runnable>> pending = new ConcurrentHashMap<>();
    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "chat-emote");
        thread.setDaemon(true);
        return thread;
    });
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OkHttpClient http = new OkHttpClient();
    private final File cacheDirectory;

    private EmoteLoader(Context context) {
        cacheDirectory = new File(context.getApplicationContext().getCacheDir(), "chat-emotes");
        if (!cacheDirectory.exists()) cacheDirectory.mkdirs();
    }

    public static EmoteLoader get(Context context) {
        if (instance == null) synchronized (EmoteLoader.class) {
            if (instance == null) instance = new EmoteLoader(context);
        }
        return instance;
    }

    public Bitmap cached(String id) {
        return id == null ? null : memory.get(id);
    }

    public Bitmap cached(ChatEmote emote) {
        return emote == null ? null : memory.get(cacheKey(emote));
    }

    public void load(String id, Runnable callback) {
        if (id == null) return;
        load(new ChatEmote(id, 0, 1, ""), callback);
    }

    public void load(ChatEmote emote, Runnable callback) {
        if (emote == null || callback == null) return;
        String url = emoteUrl(emote);
        if (url.isEmpty()) return;
        String key = cacheKey(emote);
        if (key.isEmpty()) return;
        if (memory.get(key) != null) {
            main.post(callback);
            return;
        }
        boolean shouldStart;
        synchronized (pending) {
            List<Runnable> callbacks = pending.get(key);
            shouldStart = callbacks == null;
            if (callbacks == null) callbacks = new ArrayList<>();
            if (callbacks.size() < 64) callbacks.add(callback);
            pending.put(key, callbacks);
        }
        if (shouldStart) executor.execute(() -> loadNow(key, url));
    }

    private void loadNow(String key, String url) {
        Bitmap bitmap = null;
        File file = new File(cacheDirectory, safeFileName(key) + ".png");
        try {
            if (file.isFile() && file.length() > 0 && file.length() <= MAX_IMAGE_BYTES)
                bitmap = BitmapFactory.decodeFile(file.getAbsolutePath());
            if (bitmap == null) {
                try (Response response = http.newCall(new Request.Builder().url(url).build()).execute()) {
                    if (response.isSuccessful() && response.body() != null) {
                        long length = response.body().contentLength();
                        if (length < 0 || length <= MAX_IMAGE_BYTES) {
                            byte[] data = response.body().bytes();
                            if (data.length <= MAX_IMAGE_BYTES) {
                                bitmap = BitmapFactory.decodeByteArray(data, 0, data.length);
                                if (bitmap != null && bitmap.getWidth() <= 1024 && bitmap.getHeight() <= 1024
                                        && (long) bitmap.getWidth() * bitmap.getHeight() <= 1_048_576L) {
                                    try (FileOutputStream output = new FileOutputStream(file)) {
                                        output.write(data);
                                    }
                                } else {
                                    bitmap = null;
                                }
                            }
                        }
                    }
                }
            }
        } catch (IOException | RuntimeException ignored) {
            bitmap = null;
        }
        if (bitmap != null) memory.put(key, bitmap);
        pruneDiskCache();
        List<Runnable> callbacks;
        synchronized (pending) { callbacks = pending.remove(key); }
        if (callbacks != null) for (Runnable callback : callbacks) main.post(callback);
    }

    private static String emoteUrl(ChatEmote emote) {
        if (emote.imageUrl != null && !emote.imageUrl.isEmpty()) {
            String url = normalizeImageUrl(emote.imageUrl);
            return trustedImageUrl(url) ? url : "";
        }
        if (emote.id == null || !emote.id.matches("[A-Za-z0-9_-]{1,128}")) return "";
        return "https://static-cdn.jtvnw.net/emoticons/v2/" + emote.id + "/default/dark/2.0";
    }

    private static String cacheKey(ChatEmote emote) {
        if (emote.imageUrl == null || emote.imageUrl.isEmpty()) {
            return emote.id != null && emote.id.matches("[A-Za-z0-9_-]{1,128}") ? emote.id : "";
        }
        String url = normalizeImageUrl(emote.imageUrl);
        if (!trustedImageUrl(url)) return "";
        return "youtube-" + sha256(url);
    }

    private static String safeFileName(String key) {
        return key.replaceAll("[^A-Za-z0-9_-]", "_");
    }

    private static String normalizeImageUrl(String value) {
        String url = value == null ? "" : value.trim();
        if (url.startsWith("//")) return "https:" + url;
        return url;
    }

    static boolean trustedImageUrl(String value) {
        HttpUrl url = HttpUrl.parse(value == null ? "" : value);
        if (url == null || !url.isHttps()) return false;
        String host = url.host().toLowerCase(Locale.ROOT);
        return host.equals("static-cdn.jtvnw.net")
                || host.endsWith(".ggpht.com")
                || host.endsWith(".googleusercontent.com");
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte item : digest) result.append(String.format(Locale.ROOT, "%02x", item));
            return result.toString();
        } catch (NoSuchAlgorithmException impossible) {
            return Integer.toHexString(value.hashCode());
        }
    }

    private void pruneDiskCache() {
        File[] files = cacheDirectory.listFiles((directory, name) -> name.endsWith(".png"));
        if (files == null || files.length <= 128) return;
        java.util.Arrays.sort(files, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));
        for (int index = 128; index < files.length; index++) files[index].delete();
    }

    private static int memoryCacheSizeKb() {
        long maxMemoryKb = Runtime.getRuntime().maxMemory() / 1024L;
        long target = maxMemoryKb / 32L;
        return (int) Math.max(2_048L, Math.min(6_144L, target));
    }
}
