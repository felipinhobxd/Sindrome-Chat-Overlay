package com.sindromegames.chatoverlay.providers;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.sindromegames.chatoverlay.model.ChatEmote;
import com.sindromegames.chatoverlay.model.ChatMessage;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;
import java.util.Map;

/**
 * Runs the third-party emote matching (BTTV/7TV/FFZ) on the real ART runtime
 * so regex tokenisation and index arithmetic match production behaviour.
 */
@RunWith(AndroidJUnit4.class)
public class ThirdPartyEmotesInstrumentedTest {

    @Test
    public void matchesThirdPartyCodesOutsideNativeRanges() {
        Map<String, String> codes = Map.of(
                "S geilO", "https://example.com/sgeilo.png",
                "KEKW", "https://example.com/kekw.png");
        List<ChatEmote> nativeEmotes = List.of(new ChatEmote("25", 0, 5, "Kappa"));
        List<ChatEmote> matches = ThirdPartyEmotes.findMatches(
                "Kappa KEKW S geilO", codes, nativeEmotes);
        assertEquals(2, matches.size());
        assertEquals("KEKW", matches.get(0).name);
        assertTrue(matches.get(1).start > matches.get(0).end);
    }

    @Test
    public void buildRoundTripsMessageMetadata() {
        ChatMessage message = ChatMessage.builder("twitch", "viewer", "hello KEKW")
                .authorId("u-1")
                .authorColor("#FF8800")
                .messageId("m-1")
                .build();
        assertEquals("twitch", message.platform);
        assertEquals("viewer", message.author);
        assertEquals("u-1", message.authorId);
        assertEquals("#FF8800", message.authorColor);
        assertEquals("hello KEKW", message.text);
        assertEquals("m-1", message.messageId);
    }
}
