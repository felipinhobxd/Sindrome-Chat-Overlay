package com.sindromegames.chatoverlay.net;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

/** Reads HTTP bodies with a hard cap, even when Content-Length is absent or incorrect. */
public final class BoundedStreams {
    private BoundedStreams() {}

    public static byte[] readBytes(InputStream input, long declaredLength, int maxBytes)
            throws IOException {
        if (maxBytes < 0) throw new IllegalArgumentException("Negative response limit");
        if (declaredLength > maxBytes)
            throw new IOException("HTTP response exceeds the size limit");

        ByteArrayOutputStream output = new ByteArrayOutputStream(
                declaredLength >= 0 ? (int) declaredLength : Math.min(maxBytes, 8192));
        byte[] chunk = new byte[8192];
        int total = 0;
        while (true) {
            // At most one byte past the cap is consumed to detect oversize bodies.
            int amount = Math.min(chunk.length, maxBytes - total + 1);
            int received = input.read(chunk, 0, amount);
            if (received < 0) break;
            if (received == 0) continue;
            total += received;
            if (total > maxBytes)
                throw new IOException("HTTP response exceeds the size limit");
            output.write(chunk, 0, received);
        }
        return output.toByteArray();
    }
}
