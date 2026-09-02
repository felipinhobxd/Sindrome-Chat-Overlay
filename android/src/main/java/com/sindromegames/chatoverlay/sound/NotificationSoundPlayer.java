package com.sindromegames.chatoverlay.sound;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

public final class NotificationSoundPlayer {
    private static final int SAMPLE_RATE = 44_100;
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

    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "chat-sound");
        thread.setDaemon(true);
        return thread;
    });
    private final AtomicLong lastPlayed = new AtomicLong(0);

    public boolean play(String preset, int volume, int minimumIntervalMs, boolean bypassLimit) {
        int safeVolume = Math.max(0, Math.min(200, volume));
        if (safeVolume == 0) return false;
        long now = android.os.SystemClock.elapsedRealtime();
        if (!bypassLimit) {
            long previous = lastPlayed.get();
            if (previous > 0 && now - previous < Math.max(0, minimumIntervalMs)) return false;
            if (!lastPlayed.compareAndSet(previous, now)) return false;
        } else lastPlayed.set(now);
        double[][] pattern = PRESETS.getOrDefault(preset, PRESETS.get("pop"));
        executor.execute(() -> synthesize(pattern, safeVolume));
        return true;
    }

    public void stop() { executor.shutdownNow(); }

    private static void synthesize(double[][] pattern, int volume) {
        int totalSamples = 0;
        for (double[] note : pattern) totalSamples += (int) (SAMPLE_RATE * note[1] / 1000.0);
        short[] pcm = new short[totalSamples];
        double amplitude = Math.min(0.95, 0.30 * volume / 100.0) * Short.MAX_VALUE;
        int offset = 0;
        for (double[] note : pattern) {
            int samples = (int) (SAMPLE_RATE * note[1] / 1000.0);
            for (int index = 0; index < samples; index++) {
                double envelope = Math.min(1.0, index / (SAMPLE_RATE * 0.008))
                        * Math.max(0.0, 1.0 - index / (double) samples);
                pcm[offset++] = (short) Math.max(Short.MIN_VALUE, Math.min(Short.MAX_VALUE,
                        Math.sin(2 * Math.PI * note[0] * index / SAMPLE_RATE) * amplitude * envelope));
            }
        }
        AudioTrack track = null;
        try {
            track = new AudioTrack.Builder()
                    .setAudioAttributes(new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                    .setAudioFormat(new AudioFormat.Builder().setSampleRate(SAMPLE_RATE)
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                    .setBufferSizeInBytes(pcm.length * 2)
                    .setTransferMode(AudioTrack.MODE_STATIC).build();
            track.write(pcm, 0, pcm.length);
            track.play();
            Thread.sleep(Math.max(100, totalSamples * 1000L / SAMPLE_RATE + 40));
        } catch (Exception ignored) {
            Thread.currentThread().interrupt();
        } finally {
            if (track != null) {
                try { track.stop(); } catch (IllegalStateException ignored) {}
                track.release();
            }
        }
    }
}
