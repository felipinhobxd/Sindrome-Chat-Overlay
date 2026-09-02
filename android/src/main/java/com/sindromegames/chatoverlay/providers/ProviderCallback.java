package com.sindromegames.chatoverlay.providers;

import com.sindromegames.chatoverlay.model.ChatMessage;

public interface ProviderCallback {
    void onMessage(ChatMessage message);
    void onDelete(String platform, String messageId);
    void onClear(String platform);
    void onStatus(String platform, String status, YouTubeMode youtubeMode);
}

