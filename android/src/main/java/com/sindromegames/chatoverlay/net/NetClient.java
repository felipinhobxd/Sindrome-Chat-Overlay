package com.sindromegames.chatoverlay.net;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public final class NetClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private final OkHttpClient client;

    public NetClient() {
        client = new OkHttpClient.Builder()
                .connectTimeout(12, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(15, TimeUnit.SECONDS)
                .followRedirects(true)
                .followSslRedirects(true)
                .build();
    }

    public ResponseData get(String url) throws IOException {
        return execute(new Request.Builder().url(url).header("User-Agent", userAgent())
                .header("Accept-Language", "en-US,en;q=0.8").get().build());
    }

    public JSONObject getJson(String url, Map<String, String> parameters)
            throws IOException, JSONException {
        HttpUrl parsed = HttpUrl.parse(url);
        if (parsed == null) throw new IOException("Invalid HTTPS URL");
        HttpUrl.Builder builder = parsed.newBuilder();
        for (Map.Entry<String, String> item : parameters.entrySet()) {
            if (item.getValue() != null && !item.getValue().isEmpty())
                builder.addQueryParameter(item.getKey(), item.getValue());
        }
        ResponseData response = get(builder.build().toString());
        if (response.code < 200 || response.code >= 300)
            throw new HttpFailure(response.code, response.body);
        return new JSONObject(response.body);
    }

    public ResponseData postJson(String url, JSONObject payload, Map<String, String> headers)
            throws IOException {
        Request.Builder builder = new Request.Builder().url(url)
                .header("User-Agent", userAgent())
                .post(RequestBody.create(payload.toString(), JSON));
        for (Map.Entry<String, String> item : headers.entrySet())
            builder.header(item.getKey(), item.getValue());
        return execute(builder.build());
    }

    private ResponseData execute(Request request) throws IOException {
        try (Response response = client.newCall(request).execute()) {
            String body = response.body() == null ? "" : response.body().string();
            return new ResponseData(response.code(), response.request().url().toString(), body);
        }
    }

    public void cancelAll() { client.dispatcher().cancelAll(); }

    private static String userAgent() {
        return "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                + "Chrome/131.0 Mobile Safari/537.36";
    }

    public record ResponseData(int code, String finalUrl, String body) {}

    public static final class HttpFailure extends IOException {
        public final int code;
        public final String responseBody;
        public HttpFailure(int code, String responseBody) {
            super("HTTPS request failed with status " + code);
            this.code = code;
            this.responseBody = responseBody == null ? "" : responseBody;
        }
    }
}

