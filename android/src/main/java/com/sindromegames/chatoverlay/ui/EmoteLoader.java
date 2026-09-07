package com.sindromegames.chatoverlay.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;

import com.sindromegames.chatoverlay.model.ChatEmote;
import com.sindromegames.chatoverlay.net.NetClient;

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
    // Emotes are rendered at ~28-56 px; anything decoded above this is a waste
    // of memory. Natural (compressed) bounds above MAX_NATURAL_* are rejected.
    private static final int MAX_DECODED_DIMENSION = 256;
    private static final int MAX_NATURAL_DIMENSION = 1024;
    private static final int PRUNE_EVERY_DOWNLOADS = 32;
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
    private final OkHttpClient http = NetClient.sharedClient();
    private final File cacheDirectory;
    // Only touched from the single-threaded executor.
    private int downloadsSincePrune;

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
                bitmap = decodeSafely(readFile(file));
            if (bitmap == null) {
                try (Response response = http.newCall(new Request.Builder().url(url).build()).execute()) {
                    if (response.isSuccessful() && response.body() != null) {
                        long length = response.body().contentLength();
                        if (length < 0 || length <= MAX_IMAGE_BYTES) {
                            byte[] data = response.body().bytes();
                            if (data.length <= MAX_IMAGE_BYTES) {
                                bitmap = decodeSafely(data);
                                if (bitmap != null) {
                                    try (FileOutputStream output = new FileOutputStream(file)) {
                                        output.write(data);
                                    }
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
        if (++downloadsSincePrune >= PRUNE_EVERY_DOWNLOADS) {
            downloadsSincePrune = 0;
            pruneDiskCache();
        }
        List<Runnable> callbacks;
        synchronized (pending) { callbacks = pending.remove(key); }
        if (callbacks != null) for (Runnable callback : callbacks) main.post(callback);
    }

    private static byte[] readFile(File file) {
        byte[] data = new byte[(int) Math.min(file.length(), MAX_IMAGE_BYTES)];
        try (java.io.FileInputStream input = new java.io.FileInputStream(file)) {
            int read = 0;
            while (read < data.length) {
                int chunk = input.read(data, read, data.length - read);
                if (chunk < 0) break;
                read += chunk;
            }
            return read == data.length ? data : java.util.Arrays.copyOf(data, read);
        } catch (IOException | RuntimeException ignored) {
            return null;
        }
    }

    /**
     * Decodes image data without ever allocating an unbounded bitmap. A 512 KB
     * PNG can legitimately decode to 4096x4096 (~64 MB); bounds are checked
     * first, the bitmap is downsampled with inSampleSize, and OutOfMemoryError
     * (an Error, not an Exception) is contained so a hostile image can never
     * crash the overlay process.
     */
    private static Bitmap decodeSafely(byte[] data) {
        if (data == null || data.length == 0) return null;
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null;
        if (bounds.outWidth > MAX_NATURAL_DIMENSION || bounds.outHeight > MAX_NATURAL_DIMENSION
                || (long) bounds.outWidth * bounds.outHeight > 1_048_576L) return null;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight);
        try {
            return BitmapFactory.decodeByteArray(data, 0, data.length, options);
        } catch (OutOfMemoryError ignored) {
            BitmapFactory.Options reduced = new BitmapFactory.Options();
            reduced.inSampleSize = options.inSampleSize * 4;
            try {
                return BitmapFactory.decodeByteArray(data, 0, data.length, reduced);
            } catch (OutOfMemoryError again) {
                return null;
            }
        }
    }

    private static int sampleSize(int width, int height) {
        int sample = 1;
        while (width / (sample * 2) >= MAX_DECODED_DIMENSION
                && height / (sample * 2) >= MAX_DECODED_DIMENSION) sample *= 2;
        return sample;
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
                || host.equals("cdn.betterttv.net")
                || host.equals("cdn.7tv.app")
                || host.equals("cdn.frankerfacez.com")
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
