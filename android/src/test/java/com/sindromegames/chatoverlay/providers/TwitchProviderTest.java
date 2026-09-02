package com.sindromegames.chatoverlay.providers;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.sindromegames.chatoverlay.model.ChatEmote;

import org.junit.Test;

import java.util.List;

public final class TwitchProviderTest {
    @Test public void parsesMetadataColourBadgesAndRepeatedEmotes() {
        String line = "@badges=moderator/1,subscriber/12;color=#12ABEF;display-name=Félipinho;"
                + "emotes=25:0-4,6-10;id=message-1;tmi-sent-ts=1710000000000;user-id=123 "
                + ":felipinho!x@y PRIVMSG #channel :Kappa Kappa";
        TwitchProvider.ParsedLine parsed = TwitchProvider.parseLine(line);
        assertNotNull(parsed.message);
        assertEquals("Félipinho", parsed.message.author);
        assertEquals("#12ABEF", parsed.message.authorColor);
        assertEquals(2, parsed.message.emotes.size());
        assertEquals(List.of("MODERATOR", "SUBSCRIBER"), parsed.message.badges);
    }

    @Test public void convertsCodePointOffsetsWithoutBreakingUnicode() {
        String text = "😀 Kappa";
        List<ChatEmote> emotes = TwitchProvider.parseEmotes("25:2-6", text);
        assertEquals(1, emotes.size());
        assertEquals("Kappa", text.substring(emotes.get(0).start, emotes.get(0).end));
    }

    @Test public void handlesPingAndDeletion() {
        assertEquals(":tmi.twitch.tv", TwitchProvider.parseLine(
                "PING :tmi.twitch.tv").ping);
        assertEquals("gone", TwitchProvider.parseLine(
                "@target-msg-id=gone :tmi.twitch.tv CLEARMSG #channel :removed").deleteId);
        assertTrue(TwitchProvider.parseLine(":tmi.twitch.tv RECONNECT").reconnect);
    }
}

