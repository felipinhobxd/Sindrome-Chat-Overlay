package com.sindromegames.chatoverlay.overlay;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;
import static org.junit.Assume.assumeTrue;

import android.content.Context;
import android.os.ParcelFileDescriptor;
import android.provider.Settings;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;
import java.io.InputStream;

/**
 * Exercises the floating overlay window against the real WindowManager.
 * SYSTEM_ALERT_WINDOW is granted by the instrumentation itself (UiAutomation
 * runs with shell privileges); the test is skipped rather than failed when the
 * environment refuses the grant.
 */
@RunWith(AndroidJUnit4.class)
public class OverlayWindowInstrumentedTest {

    private final Context context = ApplicationProvider.getApplicationContext();

    @Before
    public void grantOverlayPermission() {
        try (ParcelFileDescriptor descriptor = InstrumentationRegistry.getInstrumentation()
                .getUiAutomation()
                .executeShellCommand(
                        "appops set " + context.getPackageName() + " SYSTEM_ALERT_WINDOW allow")) {
            // Drain the stream so the shell command runs to completion.
            InputStream stream = new ParcelFileDescriptor.AutoCloseInputStream(descriptor);
            // noinspection ResultOfMethodCallIgnored - reading to EOF is the point
            while (stream.read() != -1) {
                // keep reading
            }
        } catch (IOException ignored) {
            // The assume below reports the missing permission clearly.
        }
        assumeTrue(
                "SYSTEM_ALERT_WINDOW not granted; skipping overlay window test",
                Settings.canDrawOverlays(context));
    }

    @Test
    public void showMakesWindowVisibleAndHideDestroysIt() {
        OverlayWindow window = new OverlayWindow(context, () -> { });
        try {
            assertFalse(window.isVisible());
            window.show();
            assertTrue(window.isVisible());
        } catch (RuntimeException failure) {
            fail("OverlayWindow.show() failed on a real WindowManager: " + failure);
        } finally {
            if (window.isVisible()) {
                window.hide();
            }
        }
        assertFalse(window.isVisible());
    }

    @Test
    public void toggleClickThroughKeepsWindowUsable() {
        OverlayWindow window = new OverlayWindow(context, () -> { });
        try {
            window.show();
            window.toggleClickThrough();
            assertTrue(window.isVisible());
            window.toggleClickThrough();
            assertTrue(window.isVisible());
        } finally {
            if (window.isVisible()) {
                window.hide();
            }
        }
        assertFalse(window.isVisible());
    }

    @Test
    public void repeatedShowHideCyclesAreStable() {
        OverlayWindow window = new OverlayWindow(context, () -> { });
        for (int cycle = 0; cycle < 3; cycle++) {
            window.show();
            assertTrue("cycle " + cycle + " should be visible", window.isVisible());
            window.hide();
            assertFalse("cycle " + cycle + " should be hidden", window.isVisible());
        }
        assertFalse(window.isVisible());
    }
}
