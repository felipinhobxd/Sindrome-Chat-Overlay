package com.sindromegames.chatoverlay;

import android.content.Context;

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

public final class ChatEngine implements ProviderCallback {
    private final Context context;
    private final NotificationSoundPlayer sounds = new NotificationSoundPlayer();
    private final Object lock = new Object();
    private ExecutorService executor;
    private List<ChatProvider> providers = Collections.emptyList();
    private volatile AppSettings settings;

    public ChatEngine(Context context) {
        this.context = context.getApplicationContext();
        this.settings = AppSettings.load(context);
    }

    public void start() {
        synchronized (lock) {
            stopLocked();
            settings = AppSettings.load(context);
            ChatBus.setMaximumMessages(settings.maxMessages);
            ArrayList<ChatProvider> next = new ArrayList<>();
            if (settings.twitchEnabled) {
                String channel = UrlNormalizer.twitchChannel(settings.twitchChannel);
                if (!channel.isEmpty()) next.add(new TwitchProvider(this, channel));
            }
            if (settings.youtubeEnabled) {
                String input = UrlNormalizer.youtubeInput(settings.youtubeInput);
                if (!input.isEmpty()) next.add(new YouTubeProvider(this, input,
                        new SecureStore(context).readApiKey(), settings.language));
            }
            providers = next;
            if (next.isEmpty()) {
                ChatBus.updateRunning(false);
                return;
            }
            executor = Executors.newFixedThreadPool(next.size(), runnable -> {
                Thread thread = new Thread(runnable, "chat-provider");
                thread.setDaemon(true);
                return thread;
            });
            ChatBus.updateRunning(true);
            for (ChatProvider provider : next) executor.submit(provider);
        }
    }

    public void restart() { start(); }

    public void stop() {
        synchronized (lock) { stopLocked(); }
        ChatBus.updateRunning(false);
    }

    public void destroy() {
        stop();
        sounds.stop();
    }

    private void stopLocked() {
        for (ChatProvider provider : providers) provider.stop();
        providers = Collections.emptyList();
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
    }

    @Override public void onMessage(ChatMessage message) {
        AppSettings current = settings;
        if (current.hideCommands && message.text.startsWith("!")) return;
        ChatBus.publish(message);
        if (current.soundEnabled) {
            String preset = message.platform.equals("twitch")
                    ? current.twitchSound : current.youtubeSound;
            sounds.play(preset, current.soundVolume, current.soundMinIntervalMs, false);
        }
    }

    @Override public void onDelete(String platform, String messageId) {
        ChatBus.delete(platform, messageId);
    }

    @Override public void onClear(String platform) { ChatBus.clearPlatform(platform); }

    @Override public void onStatus(String platform, String status, YouTubeMode youtubeMode) {
        ChatBus.updateStatus(platform, status, youtubeMode);
    }
}
