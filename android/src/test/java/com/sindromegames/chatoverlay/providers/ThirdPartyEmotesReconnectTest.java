package com.sindromegames.chatoverlay.providers;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.net.NetClient;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;

import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

@RunWith(RobolectricTestRunner.class)
public final class ThirdPartyEmotesReconnectTest {
    private static final String URL = "https://cdn.betterttv.net/emote/abc/2x";

    private static void await(Thread loader) throws InterruptedException {
        assertNotNull(loader);
        loader.join(3_000L);
        assertFalse("emote refresh thread should finish", loader.isAlive());
    }

    @Test public void failureOnFirstConnectionCanRetryOnNextConnection() throws Exception {
        AtomicInteger attempts = new AtomicInteger();
        ThirdPartyEmotes catalogs = new ThirdPartyEmotes((id, client) -> {
            assertEquals("12345", id);
            return attempts.incrementAndGet() == 1
                    ? Map.of()
                    : Map.of("Nice", URL);
        });
        NetClient client = new NetClient();
        await(catalogs.refreshForConnection("12345", client));
        ChatMessage original = ChatMessage.builder("twitch", "viewer", "Nice").build();
        assertTrue(catalogs.augment(original).emotes.isEmpty());

        await(catalogs.refreshForConnection("12345", client));
        assertEquals(2, attempts.get());
        assertEquals(1, catalogs.augment(original).emotes.size());
        assertEquals(URL, catalogs.augment(original).emotes.get(0).imageUrl);
    }

    @Test public void subsequentFailuresDoNotErasePreviouslyLoadedEmotes() throws Exception {
        AtomicInteger attempts = new AtomicInteger();
        ThirdPartyEmotes catalogs = new ThirdPartyEmotes((id, client) -> {
            return switch (attempts.incrementAndGet()) {
                case 1 -> Map.of("Nice", URL);
                case 2 -> Map.of();
                default -> throw new IllegalStateException("temporary API failure");
            };
        });
        NetClient client = new NetClient();
        ChatMessage message = ChatMessage.builder("twitch", "viewer", "Nice").build();

        await(catalogs.refreshForConnection("12345", client));
        await(catalogs.refreshForConnection("12345", client));
        await(catalogs.refreshForConnection("12345", client));
        assertEquals(3, attempts.get());
        assertEquals(1, catalogs.augment(message).emotes.size());
    }

    @Test public void overlappingReconnectsNeverStartParallelCatalogDownloads() throws Exception {
        CountDownLatch entered = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        AtomicInteger attempts = new AtomicInteger();
        ThirdPartyEmotes catalogs = new ThirdPartyEmotes((id, client) -> {
            attempts.incrementAndGet();
            entered.countDown();
            try {
                if (!release.await(3, TimeUnit.SECONDS))
                    throw new IllegalStateException("test gate timed out");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return Map.of();
            }
            return Map.of("Nice", URL);
        });
        NetClient client = new NetClient();
        Thread first = catalogs.refreshForConnection("12345", client);
        try {
            assertTrue(entered.await(2, TimeUnit.SECONDS));
            assertNull(catalogs.refreshForConnection("12345", client));
            assertNull(catalogs.refreshForConnection("", client));
            assertNull(catalogs.refreshForConnection("not-a-numeric-id", client));
            assertEquals(1, attempts.get());
        } finally {
            release.countDown();
            await(first);
        }
        await(catalogs.refreshForConnection("12345", client));
        assertEquals(2, attempts.get());
    }
}
