package com.sindromegames.chatoverlay.providers;

import java.util.concurrent.atomic.AtomicBoolean;

public abstract class ChatProvider implements Runnable {
    protected final ProviderCallback callback;
    protected final AtomicBoolean stopped = new AtomicBoolean(false);

    protected ChatProvider(ProviderCallback callback) { this.callback = callback; }

    public void stop() { stopped.set(true); }

    protected boolean waitFor(long milliseconds) {
        long deadline = System.currentTimeMillis() + Math.max(0, milliseconds);
        while (!stopped.get()) {
            long remaining = deadline - System.currentTimeMillis();
            if (remaining <= 0) return false;
            try { Thread.sleep(Math.min(remaining, 250)); }
            catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                return true;
            }
        }
        return true;
    }
}

