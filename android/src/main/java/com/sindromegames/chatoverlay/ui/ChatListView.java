package com.sindromegames.chatoverlay.ui;

import android.content.Context;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.sindromegames.chatoverlay.ChatBus;
import com.sindromegames.chatoverlay.R;
import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.settings.AppSettings;

import java.util.List;

public final class ChatListView extends ScrollView implements ChatBus.Listener {
    private final LinearLayout messages;
    private AppSettings settings;
    private boolean registered;

    public ChatListView(Context context) {
        super(context);
        setFillViewport(true);
        setClipToPadding(false);
        setPadding(dp(3), dp(3), dp(3), dp(8));
        messages = new LinearLayout(context);
        messages.setOrientation(LinearLayout.VERTICAL);
        messages.setGravity(Gravity.BOTTOM);
        addView(messages, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        settings = AppSettings.load(context);
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (!registered) { registered = true; ChatBus.register(this); }
    }

    @Override protected void onDetachedFromWindow() {
        if (registered) { registered = false; ChatBus.unregister(this); }
        super.onDetachedFromWindow();
    }

    public void refreshSettings() {
        settings = AppSettings.load(getContext());
        replace(ChatBus.snapshot());
    }

    @Override public void onInitial(List<ChatMessage> initial, ChatBus.State state) { replace(initial); }

    @Override public void onMessage(ChatMessage message) {
        removeEmptyState();
        addMessage(message);
        while (messages.getChildCount() > settings.maxMessages) messages.removeViewAt(0);
        if (settings.autoScroll) post(() -> fullScroll(FOCUS_DOWN));
    }

    @Override public void onHistoryChanged(List<ChatMessage> history) { replace(history); }
    @Override public void onState(ChatBus.State state) {}

    private void replace(List<ChatMessage> history) {
        messages.removeAllViews();
        if (history.isEmpty()) {
            TextView empty = new TextView(getContext());
            empty.setTag("empty");
            empty.setText(R.string.waiting_messages);
            empty.setTextColor(Color.rgb(174, 184, 204));
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(20), dp(32), dp(20), dp(32));
            messages.addView(empty, new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        } else for (ChatMessage message : history) addMessage(message);
        if (settings.autoScroll) post(() -> fullScroll(FOCUS_DOWN));
    }

    private void addMessage(ChatMessage message) {
        ChatMessageView row = new ChatMessageView(getContext());
        row.bind(message, settings);
        messages.addView(row, new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
    }

    private void removeEmptyState() {
        if (messages.getChildCount() == 1) {
            View first = messages.getChildAt(0);
            if ("empty".equals(first.getTag())) messages.removeAllViews();
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}

