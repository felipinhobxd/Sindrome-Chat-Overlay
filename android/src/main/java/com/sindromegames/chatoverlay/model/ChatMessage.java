package com.sindromegames.chatoverlay.model;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class ChatMessage {
    public final String platform;
    public final String author;
    public final String authorId;
    public final String authorColor;
    public final String text;
    public final String messageId;
    public final String amount;
    public final String kind;
    public final Instant timestamp;
    public final List<String> badges;
    public final List<ChatEmote> emotes;

    private ChatMessage(Builder builder) {
        platform = clean(builder.platform);
        author = clean(builder.author);
        authorId = clean(builder.authorId);
        authorColor = clean(builder.authorColor);
        text = clean(builder.text);
        messageId = clean(builder.messageId);
        amount = clean(builder.amount);
        kind = clean(builder.kind).isEmpty() ? "message" : clean(builder.kind);
        timestamp = builder.timestamp == null ? Instant.now() : builder.timestamp;
        badges = Collections.unmodifiableList(new ArrayList<>(builder.badges));
        emotes = Collections.unmodifiableList(new ArrayList<>(builder.emotes));
    }

    private static String clean(String value) {
        return (value == null ? "" : value).replace("\u0000", "").trim();
    }

    public static Builder builder(String platform, String author, String text) {
        return new Builder(platform, author, text);
    }

    public static final class Builder {
        private final String platform;
        private final String author;
        private final String text;
        private String authorId = "";
        private String authorColor = "";
        private String messageId = "";
        private String amount = "";
        private String kind = "message";
        private Instant timestamp = Instant.now();
        private final List<String> badges = new ArrayList<>();
        private final List<ChatEmote> emotes = new ArrayList<>();

        private Builder(String platform, String author, String text) {
            this.platform = platform;
            this.author = author;
            this.text = text;
        }

        public Builder authorId(String value) { authorId = value; return this; }
        public Builder authorColor(String value) { authorColor = value; return this; }
        public Builder messageId(String value) { messageId = value; return this; }
        public Builder amount(String value) { amount = value; return this; }
        public Builder kind(String value) { kind = value; return this; }
        public Builder timestamp(Instant value) { timestamp = value; return this; }
        public Builder badges(List<String> value) {
            badges.clear();
            if (value != null) badges.addAll(value);
            return this;
        }
        public Builder emotes(List<ChatEmote> value) {
            emotes.clear();
            if (value != null) emotes.addAll(value);
            return this;
        }
        public ChatMessage build() { return new ChatMessage(this); }
    }
}
