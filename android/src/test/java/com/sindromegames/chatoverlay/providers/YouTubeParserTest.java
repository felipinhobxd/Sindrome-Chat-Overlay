package com.sindromegames.chatoverlay.providers;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.net.JsonTools;

import org.json.JSONObject;
import org.junit.Test;

import java.util.List;

public final class YouTubeParserTest {
    @Test public void extractsBalancedInitialJson() {
        String html = "before var ytInitialData = {\"nested\":{\"text\":\"} still text\"},"
                + "\"videoId\":\"dQw4w9WgXcQ\"}; after";
        JSONObject object = JsonTools.extractObject(html, "var ytInitialData");
        assertNotNull(object);
        assertEquals("dQw4w9WgXcQ", object.optString("videoId"));
    }

    @Test public void parsesCompatibilityMessageIdentityAndBadges() throws Exception {
        JSONObject item = new JSONObject("{\"liveChatTextMessageRenderer\":{"
                + "\"id\":\"yt-1\",\"authorExternalChannelId\":\"UC123\","
                + "\"authorName\":{\"simpleText\":\"MariaLive\"},"
                + "\"message\":{\"runs\":[{\"text\":\"Olá 😀\"}]},"
                + "\"timestampUsec\":\"1710000000000000\","
                + "\"authorBadges\":[{\"liveChatAuthorBadgeRenderer\":{"
                + "\"tooltip\":\"Owner\"}}]}}}");
        ChatMessage message = YouTubeProvider.compatibilityMessage(item);
        assertNotNull(message);
        assertEquals("MariaLive", message.author);
        assertEquals("UC123", message.authorId);
        assertEquals("Olá 😀", message.text);
        assertEquals(List.of("OWNER"), message.badges);
    }
}
