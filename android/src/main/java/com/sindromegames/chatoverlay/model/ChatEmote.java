package com.sindromegames.chatoverlay.model;

public final class ChatEmote {
    public final String id;
    public final int start;
    public final int end;
    public final String name;

    public ChatEmote(String id, int start, int end, String name) {
        this.id = id == null ? "" : id;
        this.start = Math.max(0, start);
        this.end = Math.max(this.start, end);
        this.name = name == null ? "" : name;
    }
}
