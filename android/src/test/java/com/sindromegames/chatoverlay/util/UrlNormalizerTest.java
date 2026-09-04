package com.sindromegames.chatoverlay.util;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public final class UrlNormalizerTest {
    @Test public void normalizesTwitchNameAndUrl() {
        assertEquals("sindromegames", UrlNormalizer.twitchChannel("@SindromeGames"));
        assertEquals("sindromegames", UrlNormalizer.twitchChannel(
                "https://www.twitch.tv/SindromeGames/videos"));
        assertEquals("", UrlNormalizer.twitchChannel("https://example.com/not-twitch"));
    }

    @Test public void normalizesYouTubeHandleAndVideos() {
        assertEquals("https://www.youtube.com/@SindromeGames/live",
                UrlNormalizer.youtubeInput("@SindromeGames"));
        assertEquals("https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                UrlNormalizer.youtubeInput("https://youtu.be/dQw4w9WgXcQ"));
        assertEquals("https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                UrlNormalizer.youtubeInput("https://www.youtube.com/live/dQw4w9WgXcQ?si=share"));
        assertEquals("https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                UrlNormalizer.youtubeInput("https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=share"));
        assertEquals("dQw4w9WgXcQ", UrlNormalizer.youtubeVideoId(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"));
    }
}
