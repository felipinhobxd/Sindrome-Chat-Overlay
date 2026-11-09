package com.sindromegames.chatoverlay.providers;

import com.sindromegames.chatoverlay.model.ChatMessage;

public interface ProviderCallback {
    void onMessage(ChatMessage message);
    void onDelete(String platform, String messageId);
    /** A user ban/timeout: every message from that account must be dropped. */
    void onDeleteUser(String platform, String userId);
    void onClear(String platform);
    void onStatus(String platform, String status, YouTubeMode youtubeMode);
}

