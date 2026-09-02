package com.sindromegames.chatoverlay.providers;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.net.JsonTools;
import com.sindromegames.chatoverlay.net.NetClient;
import com.sindromegames.chatoverlay.util.UrlNormalizer;
import com.sindromegames.chatoverlay.youtube.proto.LiveChatMessage;
import com.sindromegames.chatoverlay.youtube.proto.LiveChatMessageAuthorDetails;
import com.sindromegames.chatoverlay.youtube.proto.LiveChatMessageListRequest;
import com.sindromegames.chatoverlay.youtube.proto.LiveChatMessageListResponse;
import com.sindromegames.chatoverlay.youtube.proto.LiveChatMessageSnippet;
import com.sindromegames.chatoverlay.youtube.proto.V3DataLiveChatMessageServiceGrpc;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.net.URI;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import io.grpc.ClientInterceptors;
import io.grpc.ManagedChannel;
import io.grpc.Metadata;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import io.grpc.okhttp.OkHttpChannelBuilder;
import io.grpc.stub.MetadataUtils;

public final class YouTubeProvider extends ChatProvider {
    private static final Pattern VIDEO_IN_HTML = Pattern.compile(
            "(?:\\\"videoId\\\"\\s*:\\s*\\\"|watch\\?v=|youtu\\.be/)([A-Za-z0-9_-]{11})");
    private final String input;
    private final String apiKey;
    private final String language;
    private final NetClient net = new NetClient();
    private final Set<String> seenIds = new HashSet<>();
    private final ArrayDeque<String> seenOrder = new ArrayDeque<>();
    private volatile ManagedChannel grpcChannel;
    private String officialChatId = "";
    private String officialPageToken = "";

    public YouTubeProvider(ProviderCallback callback, String input, String apiKey, String language) {
        super(callback);
        this.input = input;
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.language = language != null && language.startsWith("pt") ? "pt-BR" : "en-US";
    }

    @Override public void stop() {
        super.stop();
        net.cancelAll();
        ManagedChannel channel = grpcChannel;
        if (channel != null) channel.shutdownNow();
    }

    @Override public void run() {
        long delay = 3000;
        while (!stopped.get()) {
            try {
                callback.onStatus("youtube", "connecting", YouTubeMode.CONNECTING);
                String videoId = resolveVideoId();
                if (apiKey.isEmpty()) {
                    runCompatibility(videoId, YouTubeMode.COMPATIBILITY);
                } else {
                    try {
                        runOfficial(videoId);
                    } catch (ApiKeyRejected rejected) {
                        callback.onStatus("youtube", "invalid_key", YouTubeMode.INVALID_KEY);
                        if (waitFor(1500)) break;
                        runCompatibility(videoId, YouTubeMode.COMPATIBILITY_FALLBACK);
                    }
                }
                delay = 3000;
            } catch (StreamOffline | LiveEnded ignored) {
                callback.onStatus("youtube", "waiting_live", YouTubeMode.CONNECTING);
                if (waitFor(30_000)) break;
            } catch (ChatDisabled ignored) {
                callback.onStatus("youtube", "chat_disabled", YouTubeMode.CONNECTING);
                if (waitFor(60_000)) break;
            } catch (RateLimited ignored) {
                callback.onStatus("youtube", "rate_limited", YouTubeMode.CONNECTING);
                if (waitFor(60_000)) break;
            } catch (Exception ignored) {
                if (stopped.get()) break;
                callback.onStatus("youtube", "reconnecting", YouTubeMode.CONNECTING);
                if (waitFor(delay)) break;
                delay = Math.min(delay * 2, 60_000);
            }
        }
        callback.onStatus("youtube", "stopped", YouTubeMode.STOPPED);
    }

    private String resolveVideoId() throws Exception {
        String normalized = UrlNormalizer.youtubeInput(input);
        if (normalized.isEmpty()) throw new StreamOffline();
        String direct = UrlNormalizer.youtubeVideoId(normalized);
        if (!direct.isEmpty()) return direct;
        NetClient.ResponseData response = net.get(normalized);
        if (response.code() == 429 || response.finalUrl().contains("/sorry/")) throw new RateLimited();
        if (response.code() < 200 || response.code() >= 400) throw new IOException("YouTube unavailable");
        String redirected = UrlNormalizer.youtubeVideoId(response.finalUrl());
        if (!redirected.isEmpty()) return redirected;
        JSONObject initial = firstInitialData(response.body());
        String live = JsonTools.findLiveVideoId(initial);
        if (!live.isEmpty()) return live;
        if (response.body().contains("\"isLiveNow\":true")
                || response.body().contains("BADGE_STYLE_TYPE_LIVE_NOW")) {
            Matcher match = VIDEO_IN_HTML.matcher(response.body());
            if (match.find()) return match.group(1);
        }
        throw new StreamOffline();
    }

    private void runCompatibility(String videoId, YouTubeMode mode) throws Exception {
        Bootstrap bootstrap = bootstrap(videoId);
        String continuation = bootstrap.continuation;
        callback.onStatus("youtube", mode == YouTubeMode.COMPATIBILITY_FALLBACK
                ? "compatibility_fallback" : "compatibility", mode);
        int failures = 0;
        while (!stopped.get()) {
            String url = "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key="
                    + bootstrap.innertubeKey + "&prettyPrint=false";
            JSONObject payload = new JSONObject()
                    .put("context", bootstrap.context)
                    .put("continuation", continuation);
            Map<String, String> headers = new HashMap<>();
            headers.put("Origin", "https://www.youtube.com");
            headers.put("Referer", bootstrap.videoUrl);
            headers.put("X-YouTube-Client-Name", bootstrap.clientNameNumeric);
            headers.put("X-YouTube-Client-Version", bootstrap.clientVersion);
            NetClient.ResponseData response;
            try {
                response = net.postJson(url, payload, headers);
            } catch (IOException failure) {
                if (++failures >= 3) throw failure;
                if (waitFor(Math.min(1L << failures, 10) * 1000L)) return;
                continue;
            }
            if (response.code() == 429) throw new RateLimited();
            if (response.code() == 401 || response.code() == 403) {
                if (++failures >= 3) throw new IOException("Compatibility chat rejected");
                bootstrap = bootstrap(videoId);
                continuation = bootstrap.continuation;
                continue;
            }
            if (response.code() < 200 || response.code() >= 300)
                throw new IOException("YouTube chat HTTP " + response.code());
            JSONObject body = new JSONObject(response.body());
            JSONObject continuationContents = body.optJSONObject("continuationContents");
            JSONObject live = continuationContents == null ? null
                    : continuationContents.optJSONObject("liveChatContinuation");
            if (live == null) throw new LiveEnded();
            parseActions(live.optJSONArray("actions"));
            JsonTools.Continuation next = JsonTools.findContinuation(live.opt("continuations"));
            if (next.token().isEmpty()) throw new LiveEnded();
            continuation = next.token();
            failures = 0;
            if (waitFor(next.timeoutMs())) return;
        }
    }

    private Bootstrap bootstrap(String videoId) throws Exception {
        String videoUrl = "https://www.youtube.com/watch?v=" + videoId;
        NetClient.ResponseData response = net.get(videoUrl);
        if (response.code() == 429) throw new RateLimited();
        if (response.code() < 200 || response.code() >= 300) throw new IOException("Watch page unavailable");
        JSONObject initial = firstInitialData(response.body());
        if (initial == null) throw new IOException("Missing YouTube initial data");
        Object liveRenderer = JsonTools.findFirst(initial, "liveChatRenderer");
        if (!(liveRenderer instanceof JSONObject renderer)) throw new ChatDisabled();
        JsonTools.Continuation continuation = JsonTools.findContinuation(renderer.opt("continuations"));
        if (continuation.token().isEmpty()) throw new ChatDisabled();
        String key = JsonTools.extractConfigString(response.body(), "INNERTUBE_API_KEY");
        String clientVersion = JsonTools.extractConfigString(response.body(), "INNERTUBE_CLIENT_VERSION");
        String clientName = JsonTools.extractConfigString(response.body(), "INNERTUBE_CLIENT_NAME");
        String clientNumber = JsonTools.extractConfigNumber(response.body(), "INNERTUBE_CONTEXT_CLIENT_NAME");
        if (clientName.isEmpty()) clientName = "WEB";
        if (clientNumber.isEmpty()) clientNumber = "1";
        if (key.isEmpty() || clientVersion.isEmpty()) throw new IOException("Missing YouTube client data");
        JSONObject context = JsonTools.extractObject(response.body(), "\"INNERTUBE_CONTEXT\"");
        if (context == null) context = new JSONObject().put("client", new JSONObject());
        JSONObject client = context.optJSONObject("client");
        if (client == null) { client = new JSONObject(); context.put("client", client); }
        client.put("hl", language).put("gl", language.startsWith("pt") ? "BR" : "US")
                .put("clientName", clientName).put("clientVersion", clientVersion);
        String visitor = JsonTools.extractConfigString(response.body(), "VISITOR_DATA");
        if (!visitor.isEmpty()) client.put("visitorData", visitor);
        return new Bootstrap(videoUrl, continuation.token(), key, clientNumber, clientVersion, context);
    }

    private void runOfficial(String videoId) throws Exception {
        String chatId = officialChatId(videoId);
        if (!chatId.equals(officialChatId)) {
            officialChatId = chatId;
            officialPageToken = "";
        }
        callback.onStatus("youtube", "official_stream", YouTubeMode.OFFICIAL_STREAM);
        try {
            streamOfficial(videoId, chatId);
        } catch (StreamingUnavailable ignored) {
            if (stopped.get()) return;
            callback.onStatus("youtube", "official_polling", YouTubeMode.OFFICIAL_POLLING);
            pollOfficial(chatId);
        }
    }

    private String officialChatId(String videoId) throws Exception {
        Map<String, String> parameters = new LinkedHashMap<>();
        parameters.put("part", "liveStreamingDetails");
        parameters.put("id", videoId);
        parameters.put("key", apiKey);
        JSONObject details = apiGet("https://www.googleapis.com/youtube/v3/videos", parameters);
        JSONArray items = details.optJSONArray("items");
        if (items == null || items.length() == 0) throw new StreamOffline();
        JSONObject firstItem = items.optJSONObject(0);
        JSONObject live = firstItem == null ? null : firstItem.optJSONObject("liveStreamingDetails");
        if (live == null) throw new StreamOffline();
        String chatId = live.optString("activeLiveChatId", "");
        if (chatId.isEmpty()) {
            if (live.has("actualEndTime") || !live.has("actualStartTime")) throw new StreamOffline();
            throw new ChatDisabled();
        }
        return chatId;
    }

    private void streamOfficial(String videoId, String chatId) throws Exception {
        int failures = 0;
        boolean invalidTokenRetried = false;
        while (!stopped.get()) {
            ManagedChannel channel = OkHttpChannelBuilder.forAddress("youtube.googleapis.com", 443)
                    .useTransportSecurity()
                    .keepAliveTime(60, TimeUnit.SECONDS)
                    .keepAliveTimeout(10, TimeUnit.SECONDS)
                    .build();
            grpcChannel = channel;
            try {
                Metadata headers = new Metadata();
                Metadata.Key<String> apiHeader = Metadata.Key.of("x-goog-api-key",
                        Metadata.ASCII_STRING_MARSHALLER);
                headers.put(apiHeader, apiKey);
                V3DataLiveChatMessageServiceGrpc.V3DataLiveChatMessageServiceBlockingStub stub =
                        V3DataLiveChatMessageServiceGrpc.newBlockingStub(ClientInterceptors.intercept(
                                channel, MetadataUtils.newAttachHeadersInterceptor(headers)));
                LiveChatMessageListRequest.Builder request = LiveChatMessageListRequest.newBuilder()
                        .setLiveChatId(chatId).setHl(language).setProfileImageSize(32)
                        .addPart("snippet").addPart("authorDetails");
                if (!officialPageToken.isEmpty()) request.setPageToken(officialPageToken);
                Iterator<LiveChatMessageListResponse> responses = stub.streamList(request.build());
                boolean received = false;
                while (!stopped.get() && responses.hasNext()) {
                    LiveChatMessageListResponse response = responses.next();
                    received = true;
                    failures = 0;
                    invalidTokenRetried = false;
                    if (!response.getNextPageToken().isEmpty())
                        officialPageToken = response.getNextPageToken();
                    for (LiveChatMessage item : response.getItemsList()) {
                        if (item.hasSnippet() && item.getSnippet().getType()
                                == LiveChatMessageSnippet.Type.CHAT_ENDED_EVENT) throw new LiveEnded();
                        ChatMessage parsed = officialStreamMessage(item);
                        if (parsed != null) emitOnce(parsed);
                    }
                    if (!response.getOfflineAt().isEmpty()) throw new LiveEnded();
                }
                if (!received && ++failures >= 3) throw new StreamingUnavailable();
            } catch (StatusRuntimeException failure) {
                if (stopped.get()) return;
                Status.Code code = failure.getStatus().getCode();
                String details = String.valueOf(failure.getStatus().getDescription()).toLowerCase(Locale.ROOT);
                if (code == Status.Code.RESOURCE_EXHAUSTED || details.contains("rate"))
                    throw new RateLimited();
                if (code == Status.Code.PERMISSION_DENIED || code == Status.Code.UNAUTHENTICATED)
                    throw new ApiKeyRejected();
                if (code == Status.Code.NOT_FOUND) throw new LiveEnded();
                if (code == Status.Code.INVALID_ARGUMENT) {
                    if (!officialPageToken.isEmpty() && !invalidTokenRetried) {
                        officialPageToken = "";
                        invalidTokenRetried = true;
                        continue;
                    }
                    throw new LiveEnded();
                }
                if (code == Status.Code.FAILED_PRECONDITION) {
                    if (details.contains("disabled")) throw new ChatDisabled();
                    String current = officialChatId(videoId);
                    if (!current.equals(chatId) || details.contains("ended")) throw new LiveEnded();
                }
                if (++failures >= 3) throw new StreamingUnavailable();
            } finally {
                channel.shutdownNow();
                if (grpcChannel == channel) grpcChannel = null;
            }
            if (waitFor(Math.min(1L << Math.max(1, failures), 15) * 1000L)) return;
        }
    }

    private void pollOfficial(String chatId) throws Exception {
        while (!stopped.get()) {
            Map<String, String> parameters = new LinkedHashMap<>();
            parameters.put("part", "id,snippet,authorDetails");
            parameters.put("liveChatId", chatId);
            parameters.put("maxResults", "200");
            parameters.put("key", apiKey);
            if (!officialPageToken.isEmpty()) parameters.put("pageToken", officialPageToken);
            JSONObject body = apiGet("https://www.googleapis.com/youtube/v3/liveChat/messages", parameters);
            JSONArray items = body.optJSONArray("items");
            if (items != null) for (int index = 0; index < items.length(); index++) {
                ChatMessage message = officialJsonMessage(items.optJSONObject(index));
                if (message != null) emitOnce(message);
            }
            if (body.has("offlineAt")) throw new LiveEnded();
            officialPageToken = body.optString("nextPageToken", "");
            if (officialPageToken.isEmpty()) throw new LiveEnded();
            long interval = Math.max(1000, body.optLong("pollingIntervalMillis", 5000));
            if (waitFor(interval)) return;
        }
    }

    private JSONObject apiGet(String url, Map<String, String> parameters) throws Exception {
        try {
            return net.getJson(url, parameters);
        } catch (NetClient.HttpFailure failure) {
            String reason = apiErrorReason(failure.responseBody);
            if (failure.code == 429 || reason.contains("quota") || reason.contains("rate"))
                throw new RateLimited();
            if (reason.equals("liveChatDisabled")) throw new ChatDisabled();
            if (reason.equals("liveChatEnded") || reason.equals("liveChatNotFound")) throw new LiveEnded();
            if (reason.equals("keyInvalid") || reason.equals("forbidden")
                    || reason.equals("ipRefererBlocked") || failure.code == 401)
                throw new ApiKeyRejected();
            throw failure;
        }
    }

    private static String apiErrorReason(String body) {
        try {
            JSONObject error = new JSONObject(body).optJSONObject("error");
            JSONArray errors = error == null ? null : error.optJSONArray("errors");
            JSONObject first = errors == null ? null : errors.optJSONObject(0);
            return first == null ? "" : first.optString("reason", "");
        } catch (JSONException ignored) { return ""; }
    }

    private void parseActions(JSONArray actions) {
        if (actions == null) return;
        for (int index = 0; index < actions.length(); index++) {
            JSONObject action = actions.optJSONObject(index);
            if (action == null) continue;
            JSONObject replay = action.optJSONObject("replayChatItemAction");
            if (replay != null) parseActions(replay.optJSONArray("actions"));
            JSONObject deleted = action.optJSONObject("markChatItemAsDeletedAction");
            if (deleted == null) deleted = action.optJSONObject("removeChatItemAction");
            if (deleted != null) {
                String id = deleted.optString("targetItemId", "");
                if (!id.isEmpty()) callback.onDelete("youtube", id);
            }
            JSONObject add = action.optJSONObject("addChatItemAction");
            JSONObject item = add == null ? null : add.optJSONObject("item");
            ChatMessage message = compatibilityMessage(item);
            if (message != null) emitOnce(message);
        }
    }

    public static ChatMessage compatibilityMessage(JSONObject item) {
        if (item == null) return null;
        String[] types = {"liveChatTextMessageRenderer", "liveChatPaidMessageRenderer",
                "liveChatPaidStickerRenderer", "liveChatMembershipItemRenderer",
                "liveChatSponsorshipsGiftPurchaseAnnouncementRenderer",
                "liveChatSponsorshipsGiftRedemptionAnnouncementRenderer"};
        JSONObject renderer = null;
        String kind = "message";
        for (String type : types) {
            renderer = item.optJSONObject(type);
            if (renderer != null) {
                if (type.contains("Paid")) kind = "paid";
                else if (type.contains("Membership") || type.contains("Sponsorship")) kind = "membership";
                break;
            }
        }
        if (renderer == null) return null;
        String author = JsonTools.cleanText(renderer.opt("authorName"));
        if (author.isEmpty()) author = "YouTube";
        String text = JsonTools.cleanText(renderer.opt("message"));
        if (text.isEmpty()) text = JsonTools.cleanText(renderer.opt("headerSubtext"));
        if (text.isEmpty()) text = JsonTools.cleanText(renderer.opt("primaryText"));
        if (text.isEmpty()) text = JsonTools.cleanText(renderer.opt("subtext"));
        if (text.isEmpty()) text = kind.equals("paid") ? "Super Chat / Super Sticker"
                : kind.equals("membership") ? "Channel membership event" : "";
        if (text.isEmpty()) return null;
        String authorId = renderer.optString("authorExternalChannelId", "");
        if (authorId.isEmpty()) {
            Object browse = JsonTools.findFirst(renderer.opt("authorName"), "browseId");
            if (browse != null) authorId = String.valueOf(browse);
        }
        List<String> badges = compatibilityBadges(renderer.optJSONArray("authorBadges"));
        return ChatMessage.builder("youtube", author, text)
                .authorId(authorId)
                .messageId(renderer.optString("id", ""))
                .amount(JsonTools.cleanText(renderer.opt("purchaseAmountText")))
                .kind(kind).badges(badges)
                .timestamp(JsonTools.parseTimestampUsec(renderer.opt("timestampUsec")))
                .build();
    }

    private static List<String> compatibilityBadges(JSONArray raw) {
        List<String> badges = new ArrayList<>();
        if (raw == null) return badges;
        for (int index = 0; index < raw.length(); index++) {
            JSONObject item = raw.optJSONObject(index);
            JSONObject badge = item == null ? null : item.optJSONObject("liveChatAuthorBadgeRenderer");
            String label = badge == null ? "" : JsonTools.cleanText(badge.opt("tooltip"));
            if (!label.isEmpty()) badges.add(label.toUpperCase(Locale.ROOT));
        }
        return badges;
    }

    private ChatMessage officialStreamMessage(LiveChatMessage item) {
        if (!item.hasSnippet() || !item.hasAuthorDetails()) return null;
        LiveChatMessageSnippet snippet = item.getSnippet();
        LiveChatMessageAuthorDetails author = item.getAuthorDetails();
        String text = snippet.getDisplayMessage();
        String amount = "";
        String kind = "message";
        switch (snippet.getType()) {
            case TEXT_MESSAGE_EVENT -> text = first(snippet.getTextMessageDetails().getMessageText(), text);
            case SUPER_CHAT_EVENT -> {
                text = first(snippet.getSuperChatDetails().getUserComment(), text, "Super Chat");
                amount = snippet.getSuperChatDetails().getAmountDisplayString(); kind = "paid";
            }
            case SUPER_STICKER_EVENT -> {
                text = first(text, snippet.getSuperStickerDetails().getSuperStickerMetadata().getAltText(),
                        "Super Sticker");
                amount = snippet.getSuperStickerDetails().getAmountDisplayString(); kind = "paid";
            }
            case NEW_SPONSOR_EVENT, MEMBER_MILESTONE_CHAT_EVENT, MEMBERSHIP_GIFTING_EVENT,
                    GIFT_MEMBERSHIP_RECEIVED_EVENT -> {
                if (snippet.getType() == LiveChatMessageSnippet.Type.MEMBER_MILESTONE_CHAT_EVENT)
                    text = first(snippet.getMemberMilestoneChatDetails().getUserComment(), text);
                text = first(text, "Channel membership event"); kind = "membership";
            }
            case GIFT_EVENT -> { text = first(snippet.getGiftDetails().getAltText(),
                    snippet.getGiftDetails().getGiftName(), text); kind = "event"; }
            default -> { return null; }
        }
        if (text.isEmpty()) return null;
        List<String> badges = new ArrayList<>();
        if (author.getIsChatOwner()) badges.add("OWNER");
        if (author.getIsChatModerator()) badges.add("MOD");
        if (author.getIsChatSponsor()) badges.add("MEMBER");
        if (author.getIsVerified()) badges.add("VERIFIED");
        return ChatMessage.builder("youtube", first(author.getDisplayName(), "YouTube"), text)
                .authorId(first(author.getChannelId(), snippet.getAuthorChannelId()))
                .messageId(item.getId()).amount(amount).kind(kind).badges(badges)
                .timestamp(JsonTools.parseInstant(snippet.getPublishedAt())).build();
    }

    private ChatMessage officialJsonMessage(JSONObject item) {
        if (item == null) return null;
        JSONObject snippet = item.optJSONObject("snippet");
        JSONObject author = item.optJSONObject("authorDetails");
        if (snippet == null || author == null) return null;
        String type = snippet.optString("type", "");
        String text = JsonTools.cleanText(snippet.opt("displayMessage"));
        String amount = "";
        String kind = "message";
        if (type.equals("superChatEvent")) {
            JSONObject details = snippet.optJSONObject("superChatDetails");
            if (details != null) {
                text = first(JsonTools.cleanText(details.opt("userComment")), text, "Super Chat");
                amount = JsonTools.cleanText(details.opt("amountDisplayString"));
            }
            kind = "paid";
        } else if (type.equals("superStickerEvent")) {
            JSONObject details = snippet.optJSONObject("superStickerDetails");
            if (details != null) amount = JsonTools.cleanText(details.opt("amountDisplayString"));
            text = first(text, "Super Sticker"); kind = "paid";
        } else if (type.contains("Sponsor") || type.contains("Membership") || type.contains("member")) {
            text = first(text, "Channel membership event"); kind = "membership";
        }
        if (text.isEmpty()) return null;
        List<String> badges = new ArrayList<>();
        if (author.optBoolean("isChatOwner")) badges.add("OWNER");
        if (author.optBoolean("isChatModerator")) badges.add("MOD");
        if (author.optBoolean("isChatSponsor")) badges.add("MEMBER");
        return ChatMessage.builder("youtube", first(author.optString("displayName"), "YouTube"), text)
                .authorId(author.optString("channelId"))
                .messageId(item.optString("id"))
                .amount(amount).kind(kind).badges(badges)
                .timestamp(JsonTools.parseInstant(snippet.optString("publishedAt"))).build();
    }

    private void emitOnce(ChatMessage message) {
        if (message.messageId.isEmpty()) { callback.onMessage(message); return; }
        synchronized (seenIds) {
            if (seenIds.contains(message.messageId)) return;
            if (seenOrder.size() >= 3000) seenIds.remove(seenOrder.removeFirst());
            seenOrder.addLast(message.messageId);
            seenIds.add(message.messageId);
        }
        callback.onMessage(message);
    }

    private static JSONObject firstInitialData(String html) {
        JSONObject result = JsonTools.extractObject(html, "var ytInitialData");
        if (result == null) result = JsonTools.extractObject(html, "ytInitialData =");
        if (result == null) result = JsonTools.extractObject(html, "window[\"ytInitialData\"]");
        return result;
    }

    private static String first(String... values) {
        for (String value : values) if (value != null && !value.isEmpty()) return value;
        return "";
    }

    private record Bootstrap(String videoUrl, String continuation, String innertubeKey,
                             String clientNameNumeric, String clientVersion, JSONObject context) {}
    private static final class StreamOffline extends Exception {}
    private static final class LiveEnded extends Exception {}
    private static final class ChatDisabled extends Exception {}
    private static final class RateLimited extends Exception {}
    private static final class ApiKeyRejected extends Exception {}
    private static final class StreamingUnavailable extends Exception {}
}
