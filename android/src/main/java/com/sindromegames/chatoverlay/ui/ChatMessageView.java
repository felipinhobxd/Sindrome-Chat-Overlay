package com.sindromegames.chatoverlay.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ImageSpan;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.core.content.ContextCompat;

import com.sindromegames.chatoverlay.R;
import com.sindromegames.chatoverlay.model.ChatEmote;
import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.settings.AppSettings;
import com.sindromegames.chatoverlay.util.UserColor;

import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

public final class ChatMessageView extends LinearLayout {
    private static final DateTimeFormatter TIME = DateTimeFormatter.ofPattern("HH:mm")
            .withZone(ZoneId.systemDefault());
    private ChatMessage bound;
    private AppSettings settings;
    private final TextView body;
    private final LinearLayout metadata;

    public ChatMessageView(Context context) {
        super(context);
        setOrientation(VERTICAL);
        setPadding(dp(4), dp(3), dp(4), dp(3));
        metadata = new LinearLayout(context);
        metadata.setOrientation(HORIZONTAL);
        metadata.setGravity(Gravity.CENTER_VERTICAL);
        addView(metadata, new LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT));
        body = new TextView(context);
        body.setTextColor(Color.WHITE);
        body.setLineSpacing(0, 1.05f);
        body.setPadding(dp(6), dp(3), dp(6), dp(3));
        body.setBackground(ContextCompat.getDrawable(context, R.drawable.bg_message));
        LayoutParams bodyParams = new LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT);
        bodyParams.topMargin = dp(2);
        addView(body, bodyParams);
    }

    public void bind(ChatMessage message, AppSettings value) {
        bound = message;
        settings = value;
        metadata.removeAllViews();
        if (value.showPlatform) {
            TextView platform = meta(message.platform.equals("twitch")
                    ? getContext().getString(R.string.platform_twitch)
                    : getContext().getString(R.string.platform_youtube));
            platform.setTextColor(message.platform.equals("twitch")
                    ? Color.rgb(178, 125, 255) : Color.rgb(255, 90, 105));
            platform.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            metadata.addView(platform);
        }
        for (String badgeValue : message.badges) {
            TextView badge = meta(localizeBadge(badgeValue));
            badge.setTextColor(Color.rgb(245, 200, 87));
            badge.setTextSize(Math.max(9, value.fontSize - 5));
            metadata.addView(badge);
        }
        TextView author = meta(message.author);
        author.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        author.setTextColor(UserColor.resolve(message.platform, message.authorId,
                message.author, message.authorColor));
        metadata.addView(author);
        if (!message.amount.isEmpty()) {
            TextView amount = meta(message.amount);
            amount.setTextColor(Color.rgb(78, 225, 160));
            metadata.addView(amount);
        }
        if (value.showTimestamps) {
            TextView timestamp = meta(TIME.format(message.timestamp));
            timestamp.setTextColor(Color.rgb(174, 184, 204));
            metadata.addView(timestamp);
        }
        body.setTextSize(value.fontSize);
        renderBody(message);
    }

    public void unbind() {
        bound = null;
        settings = null;
        metadata.removeAllViews();
        body.setText(null);
    }

    private void renderBody(ChatMessage message) {
        AppSettings current = settings;
        if (current == null || bound != message) return;
        SpannableString output = new SpannableString(message.text);
        int imageSize = Math.max(dp(22), Math.round(current.fontSize * getResources()
                .getDisplayMetrics().scaledDensity * 1.35f));
        for (ChatEmote emote : message.emotes) {
            if (emote.start < 0 || emote.end > output.length() || emote.start >= emote.end) continue;
            Bitmap bitmap = EmoteLoader.get(getContext()).cached(emote.id);
            if (bitmap != null) {
                BitmapDrawable drawable = new BitmapDrawable(getResources(), bitmap);
                int width = Math.max(1, Math.round(imageSize * bitmap.getWidth()
                        / (float) Math.max(1, bitmap.getHeight())));
                drawable.setBounds(0, 0, width, imageSize);
                output.setSpan(new ImageSpan(drawable, ImageSpan.ALIGN_BOTTOM), emote.start,
                        emote.end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            } else {
                String id = emote.id;
                ChatMessage expected = bound;
                EmoteLoader.get(getContext()).load(id, () -> {
                    if (isAttachedToWindow() && bound == expected
                            && EmoteLoader.get(getContext()).cached(id) != null) renderBody(expected);
                });
            }
        }
        if (bound == message) body.setText(output);
    }

    private TextView meta(String value) {
        TextView view = new TextView(getContext());
        view.setText(value);
        view.setTextSize(Math.max(10, settings == null ? 12 : settings.fontSize - 3));
        view.setSingleLine(true);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMarginEnd(dp(5));
        view.setLayoutParams(params);
        return view;
    }

    private String localizeBadge(String badge) {
        String normalized = badge.toUpperCase(Locale.ROOT);
        if (normalized.contains("OWNER") || normalized.contains("PROPRI"))
            return getContext().getString(R.string.badge_owner);
        if (normalized.contains("MOD")) return getContext().getString(R.string.badge_mod);
        if (normalized.contains("MEMBER") || normalized.contains("MEMBRO")
                || normalized.contains("SUBSCRIBER")) return getContext().getString(R.string.badge_member);
        return normalized;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
