package com.sindromegames.chatoverlay.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public final class EmoteLoader {
    private static volatile EmoteLoader instance;
    private final LruCache<String, Bitmap> memory = new LruCache<>(memoryCacheSizeKb()) {
        @Override protected int sizeOf(String key, Bitmap value) {
            return Math.max(1, value.getByteCount() / 1024);
        }
    };
    private final Map<String, List<Runnable>> pending = new ConcurrentHashMap<>();
    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "twitch-emote");
        thread.setDaemon(true);
        return thread;
    });
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OkHttpClient http = new OkHttpClient();
    private final File cacheDirectory;

    private EmoteLoader(Context context) {
        cacheDirectory = new File(context.getApplicationContext().getCacheDir(), "twitch-emotes");
        if (!cacheDirectory.exists()) cacheDirectory.mkdirs();
    }

    public static EmoteLoader get(Context context) {
        if (instance == null) synchronized (EmoteLoader.class) {
            if (instance == null) instance = new EmoteLoader(context);
        }
        return instance;
    }

    public Bitmap cached(String id) { return id == null ? null : memory.get(id); }

    public void load(String id, Runnable callback) {
        if (id == null || callback == null || !id.matches("[A-Za-z0-9_-]{1,128}")) return;
        if (memory.get(id) != null) {
            main.post(callback);
            return;
        }
        boolean shouldStart;
        synchronized (pending) {
            List<Runnable> callbacks = pending.get(id);
            shouldStart = callbacks == null;
            if (callbacks == null) callbacks = new ArrayList<>();
            if (callbacks.size() < 64) callbacks.add(callback);
            pending.put(id, callbacks);
        }
        if (shouldStart) executor.execute(() -> loadNow(id));
    }

    private void loadNow(String id) {
        Bitmap bitmap = null;
        File file = new File(cacheDirectory, id + ".png");
        try {
            if (file.isFile() && file.length() > 0 && file.length() <= 512_000)
                bitmap = BitmapFactory.decodeFile(file.getAbsolutePath());
            if (bitmap == null) {
                String url = "https://static-cdn.jtvnw.net/emoticons/v2/" + id
                        + "/default/dark/2.0";
                try (Response response = http.newCall(new Request.Builder().url(url).build()).execute()) {
                    if (response.isSuccessful() && response.body() != null) {
                        long length = response.body().contentLength();
                        if (length < 0 || length <= 512_000) {
                            byte[] data = response.body().bytes();
                            if (data.length <= 512_000) {
                                bitmap = BitmapFactory.decodeByteArray(data, 0, data.length);
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
        if (bitmap != null) memory.put(id, bitmap);
        pruneDiskCache();
        List<Runnable> callbacks;
        synchronized (pending) { callbacks = pending.remove(id); }
        if (callbacks != null) for (Runnable callback : callbacks) main.post(callback);
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
