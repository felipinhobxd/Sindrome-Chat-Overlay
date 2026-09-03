package com.sindromegames.chatoverlay.sound;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

public final class NotificationSoundPlayerTest {
    @Test public void generatedSoundIsValidPcmWav() {
        byte[] wav = NotificationSoundPlayer.buildWav(new double[][]{{880, 100}});

        assertEquals("RIFF", new String(wav, 0, 4, StandardCharsets.US_ASCII));
        assertEquals("WAVE", new String(wav, 8, 4, StandardCharsets.US_ASCII));
        assertEquals("fmt ", new String(wav, 12, 4, StandardCharsets.US_ASCII));
        assertEquals("data", new String(wav, 36, 4, StandardCharsets.US_ASCII));

        ByteBuffer header = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(44_100, header.getInt(24));
        assertEquals(16, header.getShort(34));
        assertEquals(wav.length - 44, header.getInt(40));

        boolean hasAudio = false;
        for (int index = 44; index < wav.length; index++) {
            if (wav[index] != 0) {
                hasAudio = true;
                break;
            }
        }
        assertTrue(hasAudio);
    }

    @Test public void malformedNotesDoNotBreakWavGeneration() {
        byte[] wav = NotificationSoundPlayer.buildWav(new double[][]{null, {}, {440}});
        assertEquals(44, wav.length);
        assertEquals("RIFF", new String(wav, 0, 4, StandardCharsets.US_ASCII));
        assertEquals("data", new String(wav, 36, 4, StandardCharsets.US_ASCII));
    }
}
