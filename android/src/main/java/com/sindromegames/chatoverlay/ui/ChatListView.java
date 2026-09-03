package com.sindromegames.chatoverlay.ui;

import android.content.Context;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.sindromegames.chatoverlay.ChatBus;
import com.sindromegames.chatoverlay.R;
import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.settings.AppSettings;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class ChatListView extends RecyclerView implements ChatBus.Listener {
    private static final int TYPE_EMPTY = 0;
    private static final int TYPE_MESSAGE = 1;

    private final MessageAdapter messageAdapter;
    private final Runnable scrollToEnd;
    private AppSettings settings;
    private boolean registered;
    private boolean scrollScheduled;

    public ChatListView(Context context) {
        super(context);
        setClipToPadding(false);
        setPadding(dp(3), dp(3), dp(3), dp(8));
        setItemAnimator(null);
        setItemViewCacheSize(8);
        getRecycledViewPool().setMaxRecycledViews(TYPE_MESSAGE, 16);

        LinearLayoutManager manager = new LinearLayoutManager(context);
        manager.setStackFromEnd(false);
        setLayoutManager(manager);

        settings = AppSettings.load(context);
        messageAdapter = new MessageAdapter();
        setAdapter(messageAdapter);
        scrollToEnd = () -> {
            scrollScheduled = false;
            if (!isAttachedToWindow() || !settings.autoScroll) return;
            int count = messageAdapter.getItemCount();
            if (count > 0) scrollToPosition(count - 1);
        };
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (!registered) {
            registered = true;
            ChatBus.register(this);
        }
    }

    @Override protected void onDetachedFromWindow() {
        if (registered) {
            registered = false;
            ChatBus.unregister(this);
        }
        removeCallbacks(scrollToEnd);
        scrollScheduled = false;
        super.onDetachedFromWindow();
    }

    public void refreshSettings() {
        settings = AppSettings.load(getContext());
        messageAdapter.replace(ChatBus.snapshot());
        scrollIfNeeded();
    }

    @Override public void onInitial(List<ChatMessage> initial, ChatBus.State state) {
        messageAdapter.replace(initial);
        scrollIfNeeded();
    }

    @Override public void onMessage(ChatMessage message) {
        messageAdapter.appendAll(Collections.singletonList(message));
        scrollIfNeeded();
    }

    @Override public void onMessages(List<ChatMessage> messages) {
        messageAdapter.appendAll(messages);
        scrollIfNeeded();
    }

    @Override public void onHistoryChanged(List<ChatMessage> history) {
        messageAdapter.replace(history);
        scrollIfNeeded();
    }

    @Override public void onState(ChatBus.State state) {}

    private void scrollIfNeeded() {
        if (!settings.autoScroll || scrollScheduled) return;
        scrollScheduled = true;
        postOnAnimation(scrollToEnd);
    }

    private final class MessageAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {
        private final ArrayList<ChatMessage> items = new ArrayList<>();

        @Override public int getItemViewType(int position) {
            return items.isEmpty() ? TYPE_EMPTY : TYPE_MESSAGE;
        }

        @NonNull @Override public RecyclerView.ViewHolder onCreateViewHolder(
                @NonNull ViewGroup parent, int viewType) {
            if (viewType == TYPE_EMPTY) {
                TextView empty = new TextView(parent.getContext());
                empty.setText(R.string.waiting_messages);
                empty.setTextColor(Color.rgb(174, 184, 204));
                empty.setGravity(Gravity.CENTER);
                empty.setPadding(dp(20), dp(32), dp(20), dp(32));
                empty.setLayoutParams(new RecyclerView.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
                return new SimpleHolder(empty);
            }
            ChatMessageView row = new ChatMessageView(parent.getContext());
            row.setLayoutParams(new RecyclerView.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            return new SimpleHolder(row);
        }

        @Override public void onBindViewHolder(@NonNull RecyclerView.ViewHolder holder, int position) {
            if (items.isEmpty()) return;
            ((ChatMessageView) holder.itemView).bind(items.get(position), settings);
        }

        @Override public void onViewRecycled(@NonNull RecyclerView.ViewHolder holder) {
            if (holder.itemView instanceof ChatMessageView row) row.unbind();
            super.onViewRecycled(holder);
        }

        @Override public int getItemCount() {
            return items.isEmpty() ? 1 : items.size();
        }

        void replace(List<ChatMessage> history) {
            items.clear();
            int limit = Math.max(20, settings.maxMessages);
            int start = Math.max(0, history.size() - limit);
            for (int index = start; index < history.size(); index++) items.add(history.get(index));
            notifyDataSetChanged();
        }

        void appendAll(List<ChatMessage> messages) {
            if (messages == null || messages.isEmpty()) return;

            boolean wasEmpty = items.isEmpty();
            int oldSize = items.size();
            items.addAll(messages);

            int limit = Math.max(20, settings.maxMessages);
            int removeCount = Math.max(0, items.size() - limit);
            if (removeCount > 0) items.subList(0, removeCount).clear();

            if (wasEmpty || removeCount > oldSize) {
                notifyDataSetChanged();
                return;
            }

            if (removeCount > 0) notifyItemRangeRemoved(0, removeCount);
            int retainedOld = oldSize - removeCount;
            notifyItemRangeInserted(retainedOld, messages.size());
        }
    }

    private static final class SimpleHolder extends RecyclerView.ViewHolder {
        SimpleHolder(@NonNull View itemView) { super(itemView); }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
