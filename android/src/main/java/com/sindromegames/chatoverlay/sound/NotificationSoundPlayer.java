package com.sindromegames.chatoverlay.sound;

import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaDataSource;
import android.media.MediaPlayer;
import android.media.ToneGenerator;
import android.util.Log;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicLong;

public final class NotificationSoundPlayer {
    private static final String TAG = "ChatSound";
    private static final int SAMPLE_RATE = 44_100;
    private static final int CHANNELS = 1;
    private static final int BITS_PER_SAMPLE = 16;
    private static final AudioAttributes AUDIO_ATTRIBUTES = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build();
    private static final Map<String, double[][]> PRESETS;

    static {
        LinkedHashMap<String, double[][]> presets = new LinkedHashMap<>();
        presets.put("soft", new double[][]{{620, 55}, {780, 70}});
        presets.put("pop", new double[][]{{920, 45}, {1240, 55}});
        presets.put("chime", new double[][]{{660, 80}, {990, 100}, {1320, 130}});
        presets.put("arcade", new double[][]{{420, 45}, {840, 45}, {1260, 65}});
        presets.put("bubble", new double[][]{{480, 45}, {720, 45}, {1040, 70}});
        presets.put("bell", new double[][]{{1046, 140}, {1318, 190}});
        PRESETS = Collections.unmodifiableMap(presets);
    }

    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "chat-sound");
        thread.setDaemon(true);
        return thread;
    });
    private final AtomicLong lastPlayed = new AtomicLong(0);
    private final Object playbackLock = new Object();
    private volatile MediaPlayer activePlayer;

    public boolean play(String preset, int volume, int minimumIntervalMs, boolean bypassLimit) {
        int safeVolume = Math.max(0, Math.min(200, volume));
        if (safeVolume == 0 || executor.isShutdown()) return false;
        long now = android.os.SystemClock.elapsedRealtime();
        if (!bypassLimit) {
            long previous = lastPlayed.get();
            if (previous > 0 && now - previous < Math.max(0, minimumIntervalMs)) return false;
            if (!lastPlayed.compareAndSet(previous, now)) return false;
        } else {
            lastPlayed.set(now);
        }

        String safePreset = PRESETS.containsKey(preset) ? preset : "pop";
        try {
            executor.execute(() -> playWithMediaPlayer(safePreset, safeVolume));
            return true;
        } catch (RejectedExecutionException ignored) {
            return false;
        }
    }

    public void stop() {
        executor.shutdownNow();
        MediaPlayer player;
        synchronized (playbackLock) {
            player = activePlayer;
            activePlayer = null;
        }
        releasePlayer(player, true);
    }

    private void playWithMediaPlayer(String preset, int volume) {
        double[][] pattern = PRESETS.getOrDefault(preset, PRESETS.get("pop"));
        byte[] wav = buildWav(pattern);
        long durationMs = patternDurationMs(pattern);
        MediaPlayer player = null;
        try {
            player = new MediaPlayer();
            player.setAudioAttributes(AUDIO_ATTRIBUTES);
            player.setDataSource(new ByteArrayMediaDataSource(wav));
            float gain = Math.max(0f, Math.min(1f, volume / 200f));
            player.setVolume(gain, gain);
            player.setLooping(false);
            player.prepare();

            MediaPlayer previous;
            synchronized (playbackLock) {
                previous = activePlayer;
                activePlayer = player;
            }
            if (previous != null && previous != player) releasePlayer(previous, true);

            player.start();
            Thread.sleep(Math.max(140L, durationMs + 120L));
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        } catch (IOException | RuntimeException failure) {
            Log.w(TAG, "MediaPlayer could not play chat sound; using media-stream fallback", failure);
            playFallbackTone(volume, durationMs);
        } finally {
            synchronized (playbackLock) {
                if (activePlayer == player) activePlayer = null;
            }
            releasePlayer(player, false);
        }
    }

    private static void playFallbackTone(int volume, long durationMs) {
        ToneGenerator tone = null;
        try {
            int toneVolume = Math.max(1, Math.min(100, Math.round(volume / 2f)));
            tone = new ToneGenerator(AudioManager.STREAM_MUSIC, toneVolume);
            tone.startTone(ToneGenerator.TONE_PROP_BEEP2,
                    (int) Math.max(100L, Math.min(1_000L, durationMs)));
            Thread.sleep(Math.max(120L, durationMs + 80L));
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        } catch (RuntimeException fallbackFailure) {
            Log.w(TAG, "Fallback media tone could not play", fallbackFailure);
        } finally {
            if (tone != null) tone.release();
        }
    }

    private static void releasePlayer(MediaPlayer player, boolean stopFirst) {
        if (player == null) return;
        if (stopFirst) {
            try {
                player.stop();
            } catch (IllegalStateException ignored) {
                // The player may still be preparing or may already be stopped.
            }
        }
        try {
            player.reset();
        } catch (IllegalStateException ignored) {
            // Release remains safe even if reset is rejected by the current state.
        }
        player.release();
    }

    static byte[] buildWav(double[][] pattern) {
        int totalSamples = 0;
        for (double[] note : pattern) {
            if (note == null || note.length < 2) continue;
            totalSamples += Math.max(0, (int) (SAMPLE_RATE * note[1] / 1000.0));
        }
        int dataSize = totalSamples * 2;
        ByteBuffer output = ByteBuffer.allocate(44 + dataSize).order(ByteOrder.LITTLE_ENDIAN);
        output.put("RIFF".getBytes(StandardCharsets.US_ASCII));
        output.putInt(36 + dataSize);
        output.put("WAVE".getBytes(StandardCharsets.US_ASCII));
        output.put("fmt ".getBytes(StandardCharsets.US_ASCII));
        output.putInt(16);
        output.putShort((short) 1);
        output.putShort((short) CHANNELS);
        output.putInt(SAMPLE_RATE);
        output.putInt(SAMPLE_RATE * CHANNELS * BITS_PER_SAMPLE / 8);
        output.putShort((short) (CHANNELS * BITS_PER_SAMPLE / 8));
        output.putShort((short) BITS_PER_SAMPLE);
        output.put("data".getBytes(StandardCharsets.US_ASCII));
        output.putInt(dataSize);

        double amplitude = 0.90 * Short.MAX_VALUE;
        for (double[] note : pattern) {
            if (note == null || note.length < 2) continue;
            int samples = Math.max(0, (int) (SAMPLE_RATE * note[1] / 1000.0));
            for (int index = 0; index < samples; index++) {
                double attack = Math.min(1.0, index / (SAMPLE_RATE * 0.008));
                double release = Math.max(0.0, 1.0 - index / (double) Math.max(1, samples));
                double envelope = attack * release;
                double sample = Math.sin(2 * Math.PI * note[0] * index / SAMPLE_RATE)
                        * amplitude * envelope;
                output.putShort((short) Math.max(Short.MIN_VALUE,
                        Math.min(Short.MAX_VALUE, Math.round(sample))));
            }
        }
        return output.array();
    }

    private static long patternDurationMs(double[][] pattern) {
        long total = 0;
        for (double[] note : pattern) {
            if (note != null && note.length >= 2) total += Math.max(0L, Math.round(note[1]));
        }
        return total;
    }

    private static final class ByteArrayMediaDataSource extends MediaDataSource {
        private final byte[] data;

        ByteArrayMediaDataSource(byte[] data) {
            this.data = data == null ? new byte[0] : data;
        }

        @Override public int readAt(long position, byte[] buffer, int offset, int size) {
            if (position < 0 || position >= data.length || size <= 0) return -1;
            int start = (int) position;
            int count = Math.min(size, data.length - start);
            System.arraycopy(data, start, buffer, offset, count);
            return count;
        }

        @Override public long getSize() {
            return data.length;
        }

        @Override public void close() {
            // The byte array is owned by this short-lived playback request.
        }
    }
}
