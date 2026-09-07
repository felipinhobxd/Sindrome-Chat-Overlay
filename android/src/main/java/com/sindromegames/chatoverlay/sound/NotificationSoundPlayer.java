package com.sindromegames.chatoverlay.sound;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.SoundPool;
import android.media.ToneGenerator;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Plays the synthesized notification presets through a SoundPool.
 *
 * SoundPool keeps short samples decoded in memory and mixes up to four
 * streams, so bursts of chat overlap naturally instead of queueing behind a
 * serial MediaPlayer executor (which used to delay sounds by seconds and
 * allocate a new player plus a fresh PCM buffer for every message).
 *
 * Because SoundPool decodes asynchronously, a play request for a freshly
 * loaded sample would otherwise be dropped; play() bridges that window with
 * the ToneGenerator fallback so the first notification after app start is
 * always audible.
 */
public final class NotificationSoundPlayer {
    private static final String TAG = "ChatSound";
    private static final int SAMPLE_RATE = 44_100;
    private static final int CHANNELS = 1;
    private static final int BITS_PER_SAMPLE = 16;
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

    private final Context context;
    private final SoundPool soundPool;
    private final Map<String, Integer> soundIds = new ConcurrentHashMap<>();
    /** SoundPool sample ids whose PCM data finished decoding and can play. */
    private final Set<Integer> loadedSoundIds = ConcurrentHashMap.newKeySet();
    private final AtomicLong lastPlayed = new AtomicLong(0);
    private volatile boolean released;

    public NotificationSoundPlayer(Context context) {
        this.context = context.getApplicationContext();
        soundPool = new SoundPool.Builder()
                .setMaxStreams(4)
                .setAudioAttributes(mediaAudioAttributes())
                .build();
        soundPool.setOnLoadCompleteListener((pool, sampleId, status) -> {
            if (status == 0) loadedSoundIds.add(sampleId);
        });
    }

    public boolean play(String preset, int volume, int minimumIntervalMs, boolean bypassLimit) {
        if (released) return false;
        int safeVolume = Math.max(0, Math.min(200, volume));
        if (safeVolume == 0) return false;
        long now = android.os.SystemClock.elapsedRealtime();
        if (!bypassLimit) {
            long previous = lastPlayed.get();
            if (previous > 0 && now - previous < Math.max(0, minimumIntervalMs)) return false;
            if (!lastPlayed.compareAndSet(previous, now)) return false;
        } else {
            lastPlayed.set(now);
        }

        String safePreset = PRESETS.containsKey(preset) ? preset : "pop";
        int soundId = ensureLoaded(safePreset);
        if (soundId == 0) {
            playFallbackTone(safeVolume, patternDurationMs(PRESETS.get(safePreset)));
            return true;
        }
        try {
            // SoundPool gain tops out at 1.0; the 100-200% range plays at full
            // sample amplitude instead of digitally clipping further.
            float gain = Math.max(0f, Math.min(1f, safeVolume / 100f));
            if (!loadedSoundIds.contains(soundId)) {
                // SoundPool decodes asynchronously: soundPool.play() with an
                // id whose PCM data is not decoded yet is silently dropped
                // (it returns stream 0), which used to make the very first
                // chat sound after app start silent. A sample whose decode
                // failed never enters loadedSoundIds either, so the same
                // bridge covers it.
                playFallbackTone(safeVolume, patternDurationMs(PRESETS.get(safePreset)));
                return true;
            }
            return soundPool.play(soundId, gain, gain, 1, 0, 1f) != 0;
        } catch (RuntimeException failure) {
            Log.w(TAG, "SoundPool could not play chat sound; using fallback tone", failure);
            playFallbackTone(safeVolume, patternDurationMs(PRESETS.get(safePreset)));
            return true;
        }
    }

    public void stop() {
        if (released) return;
        released = true;
        try {
            soundPool.autoPause();
        } catch (RuntimeException ignored) {
            // Release below is the authoritative cleanup.
        }
        soundIds.clear();
        soundPool.release();
    }

    private int ensureLoaded(String preset) {
        Integer existing = soundIds.get(preset);
        if (existing != null) return existing;
        File file = presetFile(preset);
        try {
            if (!file.isFile()) writePresetFile(preset, file);
            int id = soundPool.load(file.getAbsolutePath(), 1);
            soundIds.put(preset, id);
            return id;
        } catch (IOException | RuntimeException failure) {
            Log.w(TAG, "Unable to prepare chat sound sample", failure);
            return 0;
        }
    }

    private File presetFile(String preset) {
        File directory = new File(context.getCacheDir(), "chat-sounds");
        if (!directory.exists()) directory.mkdirs();
        return new File(directory, preset + ".wav");
    }

    private void writePresetFile(String preset, File file) throws IOException {
        byte[] wav = buildWav(PRESETS.getOrDefault(preset, PRESETS.get("pop")));
        File partial = new File(file.getParentFile(), preset + ".partial");
        try (FileOutputStream output = new FileOutputStream(partial)) {
            output.write(wav);
        }
        if (!partial.renameTo(file)) {
            throw new IOException("Unable to finalize chat sound sample file");
        }
    }

    private static AudioAttributes mediaAudioAttributes() {
        return new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build();
    }

    private static void playFallbackTone(int volume, long durationMs) {
        ToneGenerator tone = null;
        try {
            int toneVolume = Math.max(1, Math.min(100, Math.round(volume / 2f)));
            tone = new ToneGenerator(AudioManager.STREAM_MUSIC, toneVolume);
            tone.startTone(ToneGenerator.TONE_PROP_BEEP2,
                    (int) Math.max(100L, Math.min(1_000L, durationMs)));
        } catch (RuntimeException fallbackFailure) {
            Log.w(TAG, "Fallback media tone could not play", fallbackFailure);
        } finally {
            if (tone != null) tone.release();
        }
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
}
