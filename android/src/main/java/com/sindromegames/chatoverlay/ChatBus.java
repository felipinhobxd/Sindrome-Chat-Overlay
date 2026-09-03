package com.sindromegames.chatoverlay;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.providers.YouTubeMode;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

public final class ChatBus {
    private static final String TAG = "ChatBus";
    private static final int MAX_DELIVERY_BACKLOG = 256;
    private static final int MAX_BATCH_SIZE = 48;
    private static final long NEXT_BATCH_DELAY_MS = 16L;

    public interface Listener {
        void onInitial(List<ChatMessage> messages, State state);
        void onMessage(ChatMessage message);
        default void onMessages(List<ChatMessage> messages) {
            for (ChatMessage message : messages) onMessage(message);
        }
        void onHistoryChanged(List<ChatMessage> messages);
        void onState(State state);
    }

    public record State(boolean running, boolean overlayVisible, boolean clickThrough,
                        String twitchStatus, String youtubeStatus, YouTubeMode youtubeMode) {}

    private interface StateMutation {
        State apply(State current);
    }

    private static final Object LOCK = new Object();
    private static final Object STATE_LOCK = new Object();
    private static final ArrayDeque<ChatMessage> HISTORY = new ArrayDeque<>();
    private static final ArrayDeque<ChatMessage> PENDING_MESSAGES = new ArrayDeque<>();
    private static final CopyOnWriteArrayList<Listener> LISTENERS = new CopyOnWriteArrayList<>();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private static volatile State state = new State(false, false, false,
            "stopped", "stopped", YouTubeMode.STOPPED);
    private static volatile int maximumMessages = 150;
    private static boolean deliveryScheduled;
    private static boolean historyResyncPending;
    private static boolean stateDispatchScheduled;

    private ChatBus() {}

    public static void register(Listener listener) {
        if (listener == null || LISTENERS.contains(listener)) return;
        LISTENERS.add(listener);
        List<ChatMessage> snapshot = snapshot();
        State initialState = state();
        Runnable initial = () -> {
            if (!LISTENERS.contains(listener)) return;
            try {
                listener.onInitial(snapshot, initialState);
            } catch (RuntimeException failure) {
                Log.e(TAG, "Chat listener failed during initial delivery", failure);
            }
        };
        if (Looper.myLooper() == Looper.getMainLooper()) initial.run();
        else MAIN.post(initial);
    }

    public static void unregister(Listener listener) { LISTENERS.remove(listener); }

    public static void setMaximumMessages(int maximum) {
        boolean shouldSchedule;
        synchronized (LOCK) {
            maximumMessages = Math.max(20, Math.min(500, maximum));
            trimLocked();
            shouldSchedule = requestHistoryResyncLocked();
        }
        if (shouldSchedule) MAIN.post(ChatBus::drainMessages);
    }

    public static void publish(ChatMessage message) {
        if (message == null) return;
        boolean shouldSchedule = false;
        synchronized (LOCK) {
            HISTORY.addLast(message);
            trimLocked();

            if (!historyResyncPending) {
                int backlogLimit = Math.min(MAX_DELIVERY_BACKLOG, maximumMessages);
                if (PENDING_MESSAGES.size() >= backlogLimit) {
                    PENDING_MESSAGES.clear();
                    historyResyncPending = true;
                } else {
                    PENDING_MESSAGES.addLast(message);
                }
            }

            if (!deliveryScheduled) {
                deliveryScheduled = true;
                shouldSchedule = true;
            }
        }
        if (shouldSchedule) MAIN.post(ChatBus::drainMessages);
    }

    public static void delete(String platform, String messageId) {
        if (messageId == null || messageId.isEmpty()) return;
        boolean shouldSchedule = false;
        synchronized (LOCK) {
            boolean changed = HISTORY.removeIf(item -> item.platform.equals(platform)
                    && item.messageId.equals(messageId));
            if (changed) shouldSchedule = requestHistoryResyncLocked();
        }
        if (shouldSchedule) MAIN.post(ChatBus::drainMessages);
    }

    public static void clearPlatform(String platform) {
        boolean shouldSchedule = false;
        synchronized (LOCK) {
            if (HISTORY.removeIf(item -> item.platform.equals(platform))) {
                shouldSchedule = requestHistoryResyncLocked();
            }
        }
        if (shouldSchedule) MAIN.post(ChatBus::drainMessages);
    }

    public static void clearAll() {
        boolean shouldSchedule = false;
        synchronized (LOCK) {
            if (!HISTORY.isEmpty()) {
                HISTORY.clear();
                shouldSchedule = requestHistoryResyncLocked();
            }
        }
        if (shouldSchedule) MAIN.post(ChatBus::drainMessages);
    }

    public static List<ChatMessage> snapshot() {
        synchronized (LOCK) {
            return immutableHistorySnapshotLocked();
        }
    }

    public static State state() { return state; }

    public static void updateRunning(boolean running) {
        mutateState(current -> new State(running, current.overlayVisible, current.clickThrough,
                current.twitchStatus, current.youtubeStatus, current.youtubeMode));
    }

    public static void updateStopped() {
        mutateState(current -> new State(false, current.overlayVisible, current.clickThrough,
                "stopped", "stopped", YouTubeMode.STOPPED));
    }

    public static void updateOverlay(boolean visible, boolean clickThrough) {
        mutateState(current -> new State(current.running, visible, clickThrough,
                current.twitchStatus, current.youtubeStatus, current.youtubeMode));
    }

    public static void updateStatus(String platform, String status, YouTubeMode mode) {
        String safeStatus = status == null || status.isEmpty() ? "stopped" : status;
        mutateState(current -> {
            if ("twitch".equals(platform)) {
                return new State(current.running, current.overlayVisible, current.clickThrough,
                        safeStatus, current.youtubeStatus, current.youtubeMode);
            }
            if (!"youtube".equals(platform)) return current;
            return new State(current.running, current.overlayVisible, current.clickThrough,
                    current.twitchStatus, safeStatus,
                    mode == null ? current.youtubeMode : mode);
        });
    }

    private static void mutateState(StateMutation mutation) {
        boolean shouldSchedule = false;
        synchronized (STATE_LOCK) {
            State current = state;
            State next = mutation.apply(current);
            if (next == null || next.equals(current)) return;
            state = next;
            if (!stateDispatchScheduled) {
                stateDispatchScheduled = true;
                shouldSchedule = true;
            }
        }
        if (shouldSchedule) MAIN.post(ChatBus::dispatchLatestState);
    }

    private static void dispatchLatestState() {
        State snapshot;
        synchronized (STATE_LOCK) {
            snapshot = state;
            stateDispatchScheduled = false;
        }
        for (Listener listener : LISTENERS) {
            try {
                listener.onState(snapshot);
            } catch (RuntimeException failure) {
                Log.e(TAG, "Chat listener failed during state delivery", failure);
            }
        }
    }

    private static boolean requestHistoryResyncLocked() {
        PENDING_MESSAGES.clear();
        historyResyncPending = true;
        if (deliveryScheduled) return false;
        deliveryScheduled = true;
        return true;
    }

    private static void drainMessages() {
        List<ChatMessage> batch = null;
        List<ChatMessage> history = null;
        boolean scheduleNext = false;

        synchronized (LOCK) {
            if (historyResyncPending) {
                history = immutableHistorySnapshotLocked();
                historyResyncPending = false;
                PENDING_MESSAGES.clear();
                deliveryScheduled = false;
            } else if (!PENDING_MESSAGES.isEmpty()) {
                int count = Math.min(MAX_BATCH_SIZE, PENDING_MESSAGES.size());
                ArrayList<ChatMessage> next = new ArrayList<>(count);
                for (int index = 0; index < count; index++) {
                    ChatMessage message = PENDING_MESSAGES.pollFirst();
                    if (message != null) next.add(message);
                }
                batch = Collections.unmodifiableList(next);
                if (PENDING_MESSAGES.isEmpty()) {
                    deliveryScheduled = false;
                } else {
                    scheduleNext = true;
                }
            } else {
                deliveryScheduled = false;
            }
        }

        if (history != null) {
            for (Listener listener : LISTENERS) {
                try {
                    listener.onHistoryChanged(history);
                } catch (RuntimeException failure) {
                    Log.e(TAG, "Chat listener failed during history resync", failure);
                }
            }
        } else if (batch != null && !batch.isEmpty()) {
            for (Listener listener : LISTENERS) {
                try {
                    listener.onMessages(batch);
                } catch (RuntimeException failure) {
                    Log.e(TAG, "Chat listener failed during batched delivery", failure);
                }
            }
        }

        if (scheduleNext) MAIN.postDelayed(ChatBus::drainMessages, NEXT_BATCH_DELAY_MS);
    }

    private static List<ChatMessage> immutableHistorySnapshotLocked() {
        return Collections.unmodifiableList(new ArrayList<>(HISTORY));
    }

    private static void trimLocked() {
        while (HISTORY.size() > maximumMessages) HISTORY.removeFirst();
    }
}
