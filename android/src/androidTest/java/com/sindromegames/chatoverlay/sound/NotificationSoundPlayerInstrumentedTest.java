package com.sindromegames.chatoverlay.sound;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

/**
 * Validates the SoundPool pipeline against the real audio stack: sample
 * synthesis to cache, decode-on-load, anti-spam timing and release semantics.
 */
@RunWith(AndroidJUnit4.class)
public class NotificationSoundPlayerInstrumentedTest {

    @Test
    public void playReturnsTrueForEveryBuiltinPreset() {
        Context context = ApplicationProvider.getApplicationContext();
        for (String preset : new String[]{"soft", "pop", "chime", "arcade", "bubble", "bell"}) {
            NotificationSoundPlayer player = new NotificationSoundPlayer(context);
            try {
                boolean played = player.play(preset, 100, 0, true);
                assertTrue("preset " + preset + " should play", played);
            } finally {
                player.stop();
            }
        }
    }

    @Test
    public void unknownPresetFallsBackInsteadOfThrowing() {
        Context context = ApplicationProvider.getApplicationContext();
        NotificationSoundPlayer player = new NotificationSoundPlayer(context);
        try {
            assertTrue(player.play("does-not-exist", 100, 0, true));
        } finally {
            player.stop();
        }
    }

    @Test
    public void antiSpamIntervalBlocksImmediateSecondPlay() {
        Context context = ApplicationProvider.getApplicationContext();
        NotificationSoundPlayer player = new NotificationSoundPlayer(context);
        try {
            assertTrue(player.play("pop", 100, 10_000, true));
            // Without bypass the 10 s anti-spam window rejects the next play.
            assertFalse(player.play("pop", 100, 10_000, false));
            // With bypass the play goes through immediately.
            assertTrue(player.play("pop", 100, 10_000, true));
            // Zero volume is always rejected.
            assertFalse(player.play("pop", 0, 0, true));
        } finally {
            player.stop();
        }
    }

    @Test
    public void playAfterStopReturnsFalseWithoutThrowing() {
        Context context = ApplicationProvider.getApplicationContext();
        NotificationSoundPlayer player = new NotificationSoundPlayer(context);
        player.stop();
        assertFalse(player.play("pop", 100, 0, true));
        // stop() must stay idempotent.
        player.stop();
    }
}
