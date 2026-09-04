package com.sindromegames.chatoverlay.providers;

import com.sindromegames.chatoverlay.model.ChatEmote;
import com.sindromegames.chatoverlay.model.ChatMessage;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

public final class TwitchProvider extends ChatProvider {
    private static final Pattern EMOTE_RANGE = Pattern.compile("(\\d+)-(\\d+)");
    private static final long HEARTBEAT_IDLE_MS = 45_000L;
    private static final long HEARTBEAT_GRACE_MS = 12_000L;
    private final String channel;
    private volatile SSLSocket socket;
    private volatile BufferedWriter writer;

    public TwitchProvider(ProviderCallback callback, String channel) {
        super(callback);
        this.channel = channel;
    }

    @Override public void stop() {
        super.stop();
        closeSocket();
    }

    @Override public void run() {
        long delay = 2000;
        while (!stopped.get()) {
            try {
                listen();
                delay = 2000;
            } catch (Exception ignored) {
                if (stopped.get()) break;
                callback.onStatus("twitch", "reconnecting", YouTubeMode.STOPPED);
                if (waitFor(delay)) break;
                delay = Math.min(delay * 2, 30_000);
            }
        }
        callback.onStatus("twitch", "stopped", YouTubeMode.STOPPED);
    }

    private void listen() throws IOException {
        callback.onStatus("twitch", "connecting", YouTubeMode.STOPPED);
        SSLSocket current = (SSLSocket) SSLSocketFactory.getDefault()
                .createSocket("irc.chat.twitch.tv", 6697);
        current.setSoTimeout(1000);
        current.startHandshake();
        socket = current;
        writer = new BufferedWriter(new OutputStreamWriter(current.getOutputStream(),
                StandardCharsets.UTF_8));
        BufferedReader reader = new BufferedReader(new InputStreamReader(current.getInputStream(),
                StandardCharsets.UTF_8));
        send("CAP REQ :twitch.tv/tags twitch.tv/commands");
        send("PASS SCHMOOPIIE");
        send("NICK justinfan" + (10_000 + new Random().nextInt(90_000)));
        send("JOIN #" + channel);
        boolean announced = false;
        long lastInbound = monotonicMs();
        long heartbeatSent = 0L;
        try {
            while (!stopped.get()) {
                String line;
                try {
                    line = reader.readLine();
                } catch (SocketTimeoutException ignored) {
                    long now = monotonicMs();
                    int heartbeat = heartbeatAction(now, lastInbound, heartbeatSent);
                    if (heartbeat == 1) {
                        send("PING :sindrome-overlay");
                        heartbeatSent = now;
                    } else if (heartbeat == 2) {
                        throw new IOException("Twitch heartbeat timed out");
                    }
                    continue;
                }
                if (line == null) throw new IOException("Twitch closed the connection");
                lastInbound = monotonicMs();
                heartbeatSent = 0L;
                ParsedLine parsed = parseLine(line);
                if (parsed.ping != null) send("PONG " + parsed.ping);
                if (parsed.reconnect) throw new IOException("Twitch requested reconnection");
                if (parsed.clear) callback.onClear("twitch");
                if (!parsed.deleteId.isEmpty()) callback.onDelete("twitch", parsed.deleteId);
                if (parsed.message != null) {
                    if (!announced) {
                        callback.onStatus("twitch", "connected", YouTubeMode.STOPPED);
                        announced = true;
                    }
                    callback.onMessage(parsed.message);
                }
                if (!announced && (line.contains(" 001 ") || line.contains(" ROOMSTATE "))) {
                    callback.onStatus("twitch", "connected", YouTubeMode.STOPPED);
                    announced = true;
                }
            }
        } finally {
            closeSocket();
        }
    }

    static int heartbeatAction(long now, long lastInbound, long heartbeatSent) {
        if (heartbeatSent > 0L)
            return now - heartbeatSent >= HEARTBEAT_GRACE_MS ? 2 : 0;
        return now - lastInbound >= HEARTBEAT_IDLE_MS ? 1 : 0;
    }

    private static long monotonicMs() {
        return System.nanoTime() / 1_000_000L;
    }

    private synchronized void send(String line) throws IOException {
        if (writer == null) throw new IOException("Twitch socket is unavailable");
        writer.write(line + "\r\n");
        writer.flush();
    }

    private synchronized void closeSocket() {
        writer = null;
        SSLSocket current = socket;
        socket = null;
        if (current != null) {
            try { current.close(); } catch (IOException ignored) {}
        }
    }

    public static ParsedLine parseLine(String line) {
        Map<String, String> tags = new HashMap<>();
        String rest = line == null ? "" : line;
        if (rest.startsWith("@")) {
            int separator = rest.indexOf(' ');
            if (separator > 1) {
                tags = parseTags(rest.substring(1, separator));
                rest = rest.substring(separator + 1);
            }
        }
        if (rest.startsWith("PING")) return ParsedLine.ping(rest.substring(4).trim());
        if (rest.contains(" RECONNECT")) return ParsedLine.reconnect();
        if (rest.contains(" CLEARMSG ")) return ParsedLine.delete(tags.getOrDefault("target-msg-id", ""));
        if (rest.contains(" CLEARCHAT ") && !rest.substring(rest.indexOf(" CLEARCHAT ") + 11)
                .contains(" :")) return ParsedLine.clear();

        if (rest.contains(" PRIVMSG ") && rest.contains(" :")) {
            int split = rest.indexOf(" :");
            String prefix = rest.substring(0, split);
            String text = rest.substring(split + 2);
            if (text.startsWith("\u0001ACTION ") && text.endsWith("\u0001"))
                text = text.substring(8, text.length() - 1);
            String fallback = prefix.startsWith(":")
                    ? prefix.substring(1).split("!", 2)[0] : "Twitch";
            String author = first(tags.get("display-name"), fallback, "Twitch");
            List<String> badges = badgeNames(tags.get("badges"));
            String amount = tags.getOrDefault("bits", "");
            if (!amount.isEmpty()) amount += " Bits";
            Instant timestamp = Instant.now();
            try { timestamp = Instant.ofEpochMilli(Long.parseLong(tags.get("tmi-sent-ts"))); }
            catch (Exception ignored) {}
            ChatMessage message = ChatMessage.builder("twitch", author, text)
                    .authorId(tags.get("user-id"))
                    .authorColor(tags.get("color"))
                    .messageId(tags.get("id"))
                    .badges(badges)
                    .amount(amount)
                    .kind(amount.isEmpty() ? "message" : "bits")
                    .timestamp(timestamp)
                    .emotes(parseEmotes(tags.get("emotes"), text))
                    .build();
            return ParsedLine.message(message);
        }

        if (rest.contains(" USERNOTICE ")) {
            String author = first(tags.get("display-name"), tags.get("login"), "Twitch");
            String text = first(tags.get("system-msg"), "Twitch event");
            return ParsedLine.message(ChatMessage.builder("twitch", author, text)
                    .authorId(tags.get("user-id"))
                    .authorColor(tags.get("color"))
                    .messageId(tags.get("id"))
                    .badges(badgeNames(tags.get("badges")))
                    .kind("event").build());
        }
        return ParsedLine.other();
    }

    public static Map<String, String> parseTags(String raw) {
        Map<String, String> tags = new HashMap<>();
        if (raw == null) return tags;
        for (String item : raw.split(";")) {
            String[] pair = item.split("=", 2);
            tags.put(pair[0], pair.length == 2 ? decodeTag(pair[1]) : "");
        }
        return tags;
    }

    public static List<ChatEmote> parseEmotes(String raw, String text) {
        List<ChatEmote> output = new ArrayList<>();
        if (raw == null || raw.isEmpty() || text == null) return output;
        for (String group : raw.split("/")) {
            String[] pair = group.split(":", 2);
            if (pair.length != 2 || !pair[0].matches("[A-Za-z0-9_-]{1,128}")) continue;
            for (String range : pair[1].split(",")) {
                Matcher match = EMOTE_RANGE.matcher(range);
                if (!match.matches()) continue;
                int start, end;
                try {
                    start = Integer.parseInt(match.group(1));
                    end = Integer.parseInt(match.group(2)) + 1;
                } catch (NumberFormatException ignored) { continue; }
                int[] selected = bestPosition(text, start, end);
                if (selected == null) continue;
                start = selected[0];
                end = selected[1];
                String name = text.substring(start, end);
                if (name.chars().anyMatch(Character::isWhitespace)) continue;
                output.add(new ChatEmote(pair[0], start, end, name));
            }
        }
        output.sort((a, b) -> Integer.compare(a.start, b.start));
        List<ChatEmote> distinct = new ArrayList<>();
        for (ChatEmote emote : output) {
            if (distinct.isEmpty() || emote.start >= distinct.get(distinct.size() - 1).end)
                distinct.add(emote);
        }
        return distinct;
    }

    private static int[] bestPosition(String text, int rawStart, int rawEnd) {
        ArrayList<int[]> candidates = new ArrayList<>();
        if (rawStart >= 0 && rawEnd > rawStart && rawEnd <= text.length())
            candidates.add(new int[]{rawStart, rawEnd});
        int codePoints = text.codePointCount(0, text.length());
        if (rawStart >= 0 && rawEnd > rawStart && rawEnd <= codePoints) {
            try {
                int convertedStart = text.offsetByCodePoints(0, rawStart);
                int convertedEnd = text.offsetByCodePoints(0, rawEnd);
                if (candidates.isEmpty() || candidates.get(0)[0] != convertedStart
                        || candidates.get(0)[1] != convertedEnd)
                    candidates.add(new int[]{convertedStart, convertedEnd});
            } catch (IndexOutOfBoundsException ignored) {}
        }
        int[] best = null;
        int bestScore = Integer.MIN_VALUE;
        for (int[] candidate : candidates) {
            String value = text.substring(candidate[0], candidate[1]);
            if (value.isEmpty() || value.chars().anyMatch(Character::isWhitespace)) continue;
            int score = 5;
            if (candidate[0] == 0 || Character.isWhitespace(text.charAt(candidate[0] - 1))) score += 3;
            if (candidate[1] == text.length() || Character.isWhitespace(text.charAt(candidate[1]))) score += 3;
            if (value.chars().allMatch(character -> character < 128)) score++;
            if (score > bestScore) { best = candidate; bestScore = score; }
        }
        return best;
    }

    private static List<String> badgeNames(String raw) {
        List<String> badges = new ArrayList<>();
        if (raw == null) return badges;
        for (String badge : raw.split(",")) {
            String name = badge.split("/", 2)[0].trim();
            if (!name.isEmpty()) badges.add(name.toUpperCase(Locale.ROOT));
        }
        return badges;
    }

    private static String decodeTag(String value) {
        StringBuilder result = new StringBuilder();
        boolean escaped = false;
        for (char c : value.toCharArray()) {
            if (escaped) {
                result.append(switch (c) {
                    case 's' -> ' ';
                    case ':' -> ';';
                    case 'r' -> '\r';
                    case 'n' -> '\n';
                    case '\\' -> '\\';
                    default -> c;
                });
                escaped = false;
            } else if (c == '\\') escaped = true;
            else result.append(c);
        }
        if (escaped) result.append('\\');
        return result.toString();
    }

    private static String first(String... values) {
        for (String value : values) if (value != null && !value.isEmpty()) return value;
        return "";
    }

    public static final class ParsedLine {
        public final ChatMessage message;
        public final String ping;
        public final String deleteId;
        public final boolean clear;
        public final boolean reconnect;
        private ParsedLine(ChatMessage message, String ping, String deleteId,
                           boolean clear, boolean reconnect) {
            this.message = message; this.ping = ping; this.deleteId = deleteId;
            this.clear = clear; this.reconnect = reconnect;
        }
        static ParsedLine message(ChatMessage value) { return new ParsedLine(value, null, "", false, false); }
        static ParsedLine ping(String value) { return new ParsedLine(null, value, "", false, false); }
        static ParsedLine delete(String value) { return new ParsedLine(null, null, value, false, false); }
        static ParsedLine clear() { return new ParsedLine(null, null, "", true, false); }
        static ParsedLine reconnect() { return new ParsedLine(null, null, "", false, true); }
        static ParsedLine other() { return new ParsedLine(null, null, "", false, false); }
    }
}
