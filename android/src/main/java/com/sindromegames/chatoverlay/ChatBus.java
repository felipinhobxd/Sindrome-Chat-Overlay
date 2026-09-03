package com.sindromegames.chatoverlay;

import android.os.Handler;
import android.os.Looper;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.providers.YouTubeMode;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

public final class ChatBus {
    public interface Listener {
        void onInitial(List<ChatMessage> messages, State state);
        void onMessage(ChatMessage message);
        void onHistoryChanged(List<ChatMessage> messages);
        void onState(State state);
    }

    public record State(boolean running, boolean overlayVisible, boolean clickThrough,
                        String twitchStatus, String youtubeStatus, YouTubeMode youtubeMode) {}

    private static final Object LOCK = new Object();
    private static final ArrayDeque<ChatMessage> HISTORY = new ArrayDeque<>();
    private static final CopyOnWriteArrayList<Listener> LISTENERS = new CopyOnWriteArrayList<>();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static volatile State state = new State(false, false, false,
            "stopped", "stopped", YouTubeMode.STOPPED);
    private static volatile int maximumMessages = 150;

    private ChatBus() {}

    public static void register(Listener listener) {
        if (listener == null || LISTENERS.contains(listener)) return;
        LISTENERS.add(listener);
        List<ChatMessage> snapshot = snapshot();
        MAIN.post(() -> {
            if (LISTENERS.contains(listener)) listener.onInitial(snapshot, state);
        });
    }

    public static void unregister(Listener listener) { LISTENERS.remove(listener); }

    public static void setMaximumMessages(int maximum) {
        maximumMessages = Math.max(20, Math.min(500, maximum));
        trimAndPublish();
    }

    public static void publish(ChatMessage message) {
        if (message == null) return;
        synchronized (LOCK) {
            HISTORY.addLast(message);
            trimLocked();
        }
        MAIN.post(() -> {
            for (Listener listener : LISTENERS) listener.onMessage(message);
        });
    }

    public static void delete(String platform, String messageId) {
        if (messageId == null || messageId.isEmpty()) return;
        boolean changed;
        synchronized (LOCK) {
            changed = HISTORY.removeIf(item -> item.platform.equals(platform)
                    && item.messageId.equals(messageId));
        }
        if (changed) publishHistory();
    }

    public static void clearPlatform(String platform) {
        synchronized (LOCK) { HISTORY.removeIf(item -> item.platform.equals(platform)); }
        publishHistory();
    }

    public static void clearAll() {
        synchronized (LOCK) { HISTORY.clear(); }
        publishHistory();
    }

    public static List<ChatMessage> snapshot() {
        synchronized (LOCK) {
            return Collections.unmodifiableList(new ArrayList<>(HISTORY));
        }
    }

    public static State state() { return state; }

    public static void updateRunning(boolean running) {
        State old = state;
        updateState(new State(running, old.overlayVisible, old.clickThrough,
                old.twitchStatus, old.youtubeStatus, old.youtubeMode));
    }

    public static void updateOverlay(boolean visible, boolean clickThrough) {
        State old = state;
        updateState(new State(old.running, visible, clickThrough,
                old.twitchStatus, old.youtubeStatus, old.youtubeMode));
    }

    public static void updateStatus(String platform, String status, YouTubeMode mode) {
        State old = state;
        if ("twitch".equals(platform)) {
            updateState(new State(old.running, old.overlayVisible, old.clickThrough,
                    status, old.youtubeStatus, old.youtubeMode));
        } else {
            updateState(new State(old.running, old.overlayVisible, old.clickThrough,
                    old.twitchStatus, status, mode == null ? old.youtubeMode : mode));
        }
    }

    private static void updateState(State next) {
        state = next;
        MAIN.post(() -> {
            for (Listener listener : LISTENERS) listener.onState(next);
        });
    }

    private static void trimAndPublish() {
        synchronized (LOCK) { trimLocked(); }
        publishHistory();
    }

    private static void trimLocked() {
        while (HISTORY.size() > maximumMessages) HISTORY.removeFirst();
    }

    private static void publishHistory() {
        List<ChatMessage> snapshot = snapshot();
        MAIN.post(() -> {
            for (Listener listener : LISTENERS) listener.onHistoryChanged(snapshot);
        });
    }
}
