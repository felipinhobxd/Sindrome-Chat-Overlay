package com.sindromegames.chatoverlay.net;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Arrays;

import org.junit.Test;

public final class BoundedStreamsTest {
    @Test public void acceptsEmptyAndExactLimitBodies() throws Exception {
        assertArrayEquals(new byte[0],
                BoundedStreams.readBytes(new ByteArrayInputStream(new byte[0]), -1, 10));
        byte[] data = new byte[512];
        Arrays.fill(data, (byte) 7);
        assertArrayEquals(data,
                BoundedStreams.readBytes(new ByteArrayInputStream(data), -1, 512));
    }

    @Test public void rejectsOversizedBodyWhenLengthIsUnknown() {
        byte[] data = new byte[50_000];
        ByteArrayInputStream input = new ByteArrayInputStream(data);
        try {
            BoundedStreams.readBytes(input, -1, 512);
            fail("Oversized body was accepted");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("size limit"));
            assertEquals(data.length - 513, input.available());
        }
    }

    @Test public void rejectsAdvertisedOversizeBeforeReadingAnyData() {
        ByteArrayInputStream input = new ByteArrayInputStream(new byte[20]);
        try {
            BoundedStreams.readBytes(input, 21, 20);
            fail("Oversized body was accepted");
        } catch (IOException expected) {
            assertEquals(20, input.available());
        }
    }

    @Test public void rejectsBodyThatLiesAboutItsLength() {
        ByteArrayInputStream input = new ByteArrayInputStream(new byte[30]);
        try {
            BoundedStreams.readBytes(input, 4, 20);
            fail("Incorrect Content-Length was trusted");
        } catch (IOException expected) {
            assertEquals(9, input.available());
        }
    }

    @Test public void usesSmallReadsEvenWithHugeUntrustedStreams() throws Exception {
        final int[] consumed = {0};
        InputStream infinite = new InputStream() {
            @Override public int read() {
                consumed[0]++;
                return 0;
            }

            @Override public int read(byte[] target, int offset, int length) {
                Arrays.fill(target, offset, offset + length, (byte) 'x');
                consumed[0] += length;
                return length;
            }
        };
        try {
            BoundedStreams.readBytes(infinite, -1, 128);
            fail("Unbounded stream was accepted");
        } catch (IOException expected) {
            assertEquals(129, consumed[0]);
        }
    }
}
