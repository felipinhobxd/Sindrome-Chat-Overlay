package com.sindromegames.chatoverlay;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.robolectric.Shadows.shadowOf;

import android.os.Looper;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.providers.YouTubeMode;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 35)
public final class ChatBusStressTest {
    private static final Duration DRAIN_TIMEOUT = Duration.ofSeconds(2);

    @Before
    public void setUp() {
        drainMainLooper();
        ChatBus.clearAll();
        ChatBus.setMaximumMessages(150);
        ChatBus.updateStopped();
        ChatBus.updateOverlay(false, false);
        ChatBus.updateStatus("twitch", "stopped", null);
        ChatBus.updateStatus("youtube", "stopped", YouTubeMode.STOPPED);
        drainMainLooper();
    }

    @After
    public void tearDown() {
        ChatBus.clearAll();
        ChatBus.setMaximumMessages(150);
        ChatBus.updateStopped();
        ChatBus.updateOverlay(false, false);
        drainMainLooper();
    }

    @Test
    public void burstOfTenThousandMessagesStaysBoundedAndResyncsLatestHistory() {
        ChatBus.setMaximumMessages(500);
        drainMainLooper();

        RecordingListener listener = new RecordingListener();
        ChatBus.register(listener);
        try {
            for (int index = 0; index < 10_000; index++) {
                ChatBus.publish(message(index));
            }

            List<ChatMessage> immediateSnapshot = ChatBus.snapshot();
            assertEquals(500, immediateSnapshot.size());
            assertEquals("message-9500", immediateSnapshot.get(0).messageId);
            assertEquals("message-9999", immediateSnapshot.get(499).messageId);

            drainMainLooper();

            assertNotNull(listener.lastHistory);
            assertEquals(500, listener.lastHistory.size());
            assertEquals("message-9500", listener.lastHistory.get(0).messageId);
            assertEquals("message-9999", listener.lastHistory.get(499).messageId);
            assertEquals(0, listener.totalIncrementalMessages());
        } finally {
            ChatBus.unregister(listener);
        }
    }

    @Test
    public void normalBurstIsDeliveredInFrameSizedBatches() {
        ChatBus.setMaximumMessages(150);
        drainMainLooper();

        RecordingListener listener = new RecordingListener();
        ChatBus.register(listener);
        try {
            for (int index = 0; index < 100; index++) {
                ChatBus.publish(message(index));
            }

            drainMainLooper();

            assertEquals(100, listener.totalIncrementalMessages());
            assertEquals(3, listener.batches.size());
            assertEquals(48, listener.batches.get(0).size());
            assertEquals(48, listener.batches.get(1).size());
            assertEquals(4, listener.batches.get(2).size());
            for (List<ChatMessage> batch : listener.batches) {
                assertTrue(batch.size() <= 48);
            }
        } finally {
            ChatBus.unregister(listener);
        }
    }

    @Test
    public void registeringDuringPendingDeliveryDoesNotDuplicateSnapshotMessages() {
        for (int index = 0; index < 10; index++) {
            ChatBus.publish(message(index));
        }

        RecordingListener listener = new RecordingListener();
        ChatBus.register(listener);
        try {
            assertNotNull(listener.initial);
            assertEquals(10, listener.initial.size());

            drainMainLooper();
            assertEquals(0, listener.totalIncrementalMessages());

            ChatBus.publish(message(10));
            drainMainLooper();

            assertEquals(1, listener.totalIncrementalMessages());
            assertEquals("message-10", listener.batches.get(0).get(0).messageId);
        } finally {
            ChatBus.unregister(listener);
        }
    }

    @Test
    public void concurrentIndependentStateMutationsDoNotLoseUpdates() throws Exception {
        for (int iteration = 0; iteration < 200; iteration++) {
            ChatBus.updateOverlay(false, false);
            ChatBus.updateStatus("twitch", "stopped", null);

            CountDownLatch start = new CountDownLatch(1);
            CountDownLatch finished = new CountDownLatch(2);

            Thread overlayThread = new Thread(() -> {
                await(start);
                ChatBus.updateOverlay(true, true);
                finished.countDown();
            }, "state-overlay-test");
            Thread twitchThread = new Thread(() -> {
                await(start);
                ChatBus.updateStatus("twitch", "connected", null);
                finished.countDown();
            }, "state-twitch-test");

            overlayThread.start();
            twitchThread.start();
            start.countDown();

            assertTrue("Concurrent state mutations timed out",
                    finished.await(5, TimeUnit.SECONDS));

            ChatBus.State state = ChatBus.state();
            assertTrue(state.overlayVisible());
            assertTrue(state.clickThrough());
            assertEquals("connected", state.twitchStatus());
        }
        drainMainLooper();
    }

    private static ChatMessage message(int index) {
        return ChatMessage.builder("twitch", "tester", "payload-" + index)
                .messageId("message-" + index)
                .build();
    }

    private static void drainMainLooper() {
        shadowOf(Looper.getMainLooper()).idleFor(DRAIN_TIMEOUT);
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new AssertionError(interrupted);
        }
    }

    private static final class RecordingListener implements ChatBus.Listener {
        private List<ChatMessage> initial;
        private List<ChatMessage> lastHistory;
        private final List<List<ChatMessage>> batches = new ArrayList<>();

        @Override
        public void onInitial(List<ChatMessage> messages, ChatBus.State state) {
            initial = List.copyOf(messages);
        }

        @Override
        public void onMessage(ChatMessage message) {
            batches.add(List.of(message));
        }

        @Override
        public void onMessages(List<ChatMessage> messages) {
            batches.add(List.copyOf(messages));
        }

        @Override
        public void onHistoryChanged(List<ChatMessage> messages) {
            lastHistory = List.copyOf(messages);
        }

        @Override
        public void onState(ChatBus.State state) {
        }

        int totalIncrementalMessages() {
            int total = 0;
            for (List<ChatMessage> batch : batches) total += batch.size();
            return total;
        }
    }
}
