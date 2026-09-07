package com.sindromegames.chatoverlay.providers;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.sindromegames.chatoverlay.model.ChatEmote;
import com.sindromegames.chatoverlay.model.ChatMessage;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class ThirdPartyEmotesTest {
    @Test public void parsesBttvChannelAndSharedEmotes() throws Exception {
        JSONObject payload = new JSONObject()
                .put("channelEmotes", new JSONArray()
                        .put(new JSONObject().put("code", "ChannelEmote").put("id", "ch1")))
                .put("sharedEmotes", new JSONArray()
                        .put(new JSONObject().put("code", "SharedEmote").put("id", "sh1")));
        Map<String, String> parsed = ThirdPartyEmotes.parseBttv(payload);
        assertEquals("https://cdn.betterttv.net/emote/ch1/2x", parsed.get("ChannelEmote"));
        assertEquals("https://cdn.betterttv.net/emote/sh1/2x", parsed.get("SharedEmote"));
    }

    @Test public void parsesBttvGlobalArray() throws Exception {
        JSONArray payload = new JSONArray()
                .put(new JSONObject().put("code", "KappaPride").put("id", "abc"));
        Map<String, String> parsed = ThirdPartyEmotes.parseBttvArray(payload);
        assertEquals("https://cdn.betterttv.net/emote/abc/2x", parsed.get("KappaPride"));
    }

    @Test public void parsesSeventvSetAndUserPayloads() throws Exception {
        JSONObject set = new JSONObject()
                .put("emotes", new JSONArray()
                        .put(new JSONObject().put("name", "widepeepoHappy").put("id", "7tv1")));
        Map<String, String> parsed = ThirdPartyEmotes.parseSeventv(set);
        assertEquals("https://cdn.7tv.app/emote/7tv1/2x.webp", parsed.get("widepeepoHappy"));

        JSONObject user = new JSONObject().put("emote_set", new JSONObject()
                .put("emotes", new JSONArray()
                        .put(new JSONObject().put("name", "Sadge").put("id", "7tv2"))));
        assertEquals("https://cdn.7tv.app/emote/7tv2/2x.webp",
                ThirdPartyEmotes.parseSeventv(user).get("Sadge"));
    }

    @Test public void parsesFfzRoomActiveSetOnly() throws Exception {
        JSONObject payload = new JSONObject()
                .put("room", new JSONObject().put("set", 7))
                .put("sets", new JSONObject()
                        .put("7", new JSONObject().put("emoticons", new JSONArray()
                                .put(new JSONObject().put("name", "RoomEmote").put(
                                        "urls", new JSONObject().put("2", "//cdn.frankerfacez.com/room2")))))
                        .put("9", new JSONObject().put("emoticons", new JSONArray()
                                .put(new JSONObject().put("name", "Ignored").put(
                                        "urls", new JSONObject().put("2", "//cdn.frankerfacez.com/x"))))));
        Map<String, String> parsed = ThirdPartyEmotes.parseFfz(payload);
        assertEquals("https://cdn.frankerfacez.com/room2", parsed.get("RoomEmote"));
        assertEquals(1, parsed.size());
    }

    @Test public void malformedPayloadsYieldEmptyMaps() {
        assertTrue(ThirdPartyEmotes.parseBttv(null).isEmpty());
        assertTrue(ThirdPartyEmotes.parseBttvArray(null).isEmpty());
        assertTrue(ThirdPartyEmotes.parseSeventv(null).isEmpty());
        assertTrue(ThirdPartyEmotes.parseFfz(null).isEmpty());
    }

    @Test public void matchesStandaloneTokensWithPositions() {
        Map<String, String> codes = new HashMap<>();
        codes.put("Nice", "https://cdn.betterttv.net/emote/x/2x");
        List<ChatEmote> matches = ThirdPartyEmotes.findMatches("um Nice exemplo", codes, List.of());
        assertEquals(1, matches.size());
        assertEquals(3, matches.get(0).start);
        assertEquals(7, matches.get(0).end);
        assertEquals("Nice", matches.get(0).name);
    }

    @Test public void nativeEmoteRangeIsNotReplaced() {
        Map<String, String> codes = new HashMap<>();
        codes.put("Kappa", "https://cdn.betterttv.net/emote/x/2x");
        List<ChatEmote> native = List.of(new ChatEmote("25", 0, 5, "Kappa"));
        assertTrue(ThirdPartyEmotes.findMatches("Kappa", codes, native).isEmpty());
    }

    @Test public void augmentAppendsThirdPartyAfterNative() {
        ThirdPartyEmotes loader = new ThirdPartyEmotes();
        Map<String, String> codes = new HashMap<>();
        codes.put("Nice", "https://cdn.betterttv.net/emote/x/2x");
        loader.forceCatalogForTest(codes);
        ChatMessage message = ChatMessage.builder("twitch", "user", "Kappa Nice")
                .messageId("m1")
                .emotes(List.of(new ChatEmote("25", 0, 5, "Kappa")))
                .build();
        ChatMessage augmented = loader.augment(message);
        assertEquals(2, augmented.emotes.size());
        assertEquals("Kappa", augmented.emotes.get(0).name);
        assertEquals("Nice", augmented.emotes.get(1).name);
        assertEquals("https://cdn.betterttv.net/emote/x/2x", augmented.emotes.get(1).imageUrl);
    }

    @Test public void augmentWithoutCatalogReturnsSameMessage() {
        ThirdPartyEmotes loader = new ThirdPartyEmotes();
        ChatMessage message = ChatMessage.builder("twitch", "user", "texto").messageId("m1").build();
        assertEquals(message, loader.augment(message));
    }
}
