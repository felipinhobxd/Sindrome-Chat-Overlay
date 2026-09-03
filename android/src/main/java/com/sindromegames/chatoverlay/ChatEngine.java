package com.sindromegames.chatoverlay;

import android.content.Context;
import android.util.Log;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.providers.ChatProvider;
import com.sindromegames.chatoverlay.providers.ProviderCallback;
import com.sindromegames.chatoverlay.providers.TwitchProvider;
import com.sindromegames.chatoverlay.providers.YouTubeMode;
import com.sindromegames.chatoverlay.providers.YouTubeProvider;
import com.sindromegames.chatoverlay.settings.AppSettings;
import com.sindromegames.chatoverlay.settings.SecureStore;
import com.sindromegames.chatoverlay.sound.NotificationSoundPlayer;
import com.sindromegames.chatoverlay.util.UrlNormalizer;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

public final class ChatEngine {
    private static final String TAG = "ChatEngine";

    private final Context context;
    private final NotificationSoundPlayer sounds = new NotificationSoundPlayer();
    private final Object lock = new Object();
    private final AtomicLong generation = new AtomicLong();
    private ExecutorService executor;
    private List<ChatProvider> providers = Collections.emptyList();
    private volatile AppSettings settings;

    public ChatEngine(Context context) {
        this.context = context.getApplicationContext();
        this.settings = AppSettings.load(this.context);
    }

    public void start() {
        synchronized (lock) {
            long currentGeneration = generation.incrementAndGet();
            try {
                stopLocked();
                ChatBus.updateStopped();
                settings = AppSettings.load(context);
                ChatBus.setMaximumMessages(settings.maxMessages);
                ProviderCallback callback = new GenerationCallback(currentGeneration);
                ArrayList<ChatProvider> next = new ArrayList<>(2);
                if (settings.twitchEnabled) {
                    String channel = UrlNormalizer.twitchChannel(settings.twitchChannel);
                    if (!channel.isEmpty()) next.add(new TwitchProvider(callback, channel));
                }
                if (settings.youtubeEnabled) {
                    String input = UrlNormalizer.youtubeInput(settings.youtubeInput);
                    if (!input.isEmpty()) {
                        next.add(new YouTubeProvider(callback, input,
                                new SecureStore(context).readApiKey(), settings.language));
                    }
                }
                providers = next;
                if (next.isEmpty()) return;

                executor = Executors.newFixedThreadPool(next.size(), runnable -> {
                    Thread thread = new Thread(runnable, "chat-provider");
                    thread.setDaemon(true);
                    thread.setUncaughtExceptionHandler((failedThread, failure) ->
                            Log.e(TAG, "Chat provider thread crashed", failure));
                    return thread;
                });
                ChatBus.updateRunning(true);
                for (ChatProvider provider : next) executor.execute(provider);
            } catch (RuntimeException failure) {
                generation.incrementAndGet();
                Log.e(TAG, "Unable to start chat providers", failure);
                stopLocked();
                ChatBus.updateStopped();
            }
        }
    }

    public void restart() { start(); }

    public void stop() {
        generation.incrementAndGet();
        synchronized (lock) { stopLocked(); }
        ChatBus.updateStopped();
    }

    public void destroy() {
        stop();
        sounds.stop();
    }

    private void stopLocked() {
        for (ChatProvider provider : providers) {
            try {
                provider.stop();
            } catch (RuntimeException failure) {
                Log.w(TAG, "Unable to stop chat provider cleanly", failure);
            }
        }
        providers = Collections.emptyList();
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
    }

    private final class GenerationCallback implements ProviderCallback {
        private final long expectedGeneration;

        GenerationCallback(long expectedGeneration) {
            this.expectedGeneration = expectedGeneration;
        }

        private boolean active() {
            return generation.get() == expectedGeneration;
        }

        @Override public void onMessage(ChatMessage message) {
            if (!active() || message == null) return;
            AppSettings current = settings;
            if (current.hideCommands && message.text.startsWith("!")) return;
            if (!active()) return;
            ChatBus.publish(message);
            if (current.soundEnabled && active()) {
                String preset = message.platform.equals("twitch")
                        ? current.twitchSound : current.youtubeSound;
                sounds.play(preset, current.soundVolume, current.soundMinIntervalMs, false);
            }
        }

        @Override public void onDelete(String platform, String messageId) {
            if (active()) ChatBus.delete(platform, messageId);
        }

        @Override public void onClear(String platform) {
            if (active()) ChatBus.clearPlatform(platform);
        }

        @Override public void onStatus(String platform, String status, YouTubeMode youtubeMode) {
            if (active()) ChatBus.updateStatus(platform, status, youtubeMode);
        }
    }
}
