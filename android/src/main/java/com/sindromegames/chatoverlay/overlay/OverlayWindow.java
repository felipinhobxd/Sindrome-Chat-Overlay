package com.sindromegames.chatoverlay.overlay;

import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.sindromegames.chatoverlay.ChatBus;
import com.sindromegames.chatoverlay.R;
import com.sindromegames.chatoverlay.settings.AppSettings;
import com.sindromegames.chatoverlay.ui.ChatListView;

public final class OverlayWindow {
    private static final String TAG = "OverlayWindow";

    private final Context context;
    private final WindowManager windowManager;
    private final Runnable stateChanged;
    private FrameLayout root;
    private WindowManager.LayoutParams parameters;
    private ChatListView chat;
    private TextView headerTitle;
    private AppSettings settings;

    public OverlayWindow(Context context, Runnable stateChanged) {
        this.context = context.getApplicationContext();
        this.windowManager = (WindowManager) this.context.getSystemService(Context.WINDOW_SERVICE);
        this.stateChanged = stateChanged;
        this.settings = AppSettings.load(this.context);
    }

    public boolean isVisible() { return root != null; }

    public void show() {
        if (isVisible() || windowManager == null || !Settings.canDrawOverlays(context)) return;
        settings = AppSettings.load(context);
        root = buildView();
        parameters = new WindowManager.LayoutParams(settings.overlayWidth, settings.overlayHeight,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                baseFlags(), PixelFormat.TRANSLUCENT);
        parameters.gravity = Gravity.TOP | Gravity.START;
        parameters.x = settings.overlayX;
        parameters.y = settings.overlayY;
        parameters.softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING;
        clampGeometry();
        applyClickThroughFlags();
        try {
            windowManager.addView(root, parameters);
            saveGeometry();
            ChatBus.updateOverlay(true, settings.overlayClickThrough);
            stateChanged.run();
        } catch (RuntimeException failure) {
            Log.e(TAG, "Unable to attach floating overlay", failure);
            root = null;
            parameters = null;
            chat = null;
            ChatBus.updateOverlay(false, false);
        }
    }

    public void hide() {
        if (root == null) return;
        saveGeometry();
        try {
            if (windowManager != null) windowManager.removeView(root);
        } catch (RuntimeException failure) {
            Log.w(TAG, "Unable to detach floating overlay cleanly", failure);
        }
        root = null;
        parameters = null;
        chat = null;
        headerTitle = null;
        ChatBus.updateOverlay(false, false);
        stateChanged.run();
    }

    public void refreshSettings() {
        settings = AppSettings.load(context);
        if (chat != null) chat.refreshSettings();
        if (root != null && parameters != null) {
            applyPanelOpacity();
            parameters.width = settings.overlayWidth;
            parameters.height = settings.overlayHeight;
            clampGeometry();
            applyClickThroughFlags();
            updateLayout();
            saveGeometry();
        }
    }

    public void toggleClickThrough() {
        if (root == null || parameters == null) return;
        settings.overlayClickThrough = !settings.overlayClickThrough;
        settings.save(context);
        applyClickThroughFlags();
        updateLayout();
        ChatBus.updateOverlay(true, settings.overlayClickThrough);
        stateChanged.run();
    }

    private FrameLayout buildView() {
        FrameLayout frame = new FrameLayout(context);
        LinearLayout content = new LinearLayout(context);
        content.setOrientation(LinearLayout.VERTICAL);
        frame.addView(content, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        LinearLayout header = new LinearLayout(context);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(8), dp(4), dp(4), dp(4));
        header.setTag("header");
        headerTitle = new TextView(context);
        headerTitle.setText(R.string.overlay_drag_hint);
        headerTitle.setTextColor(Color.WHITE);
        headerTitle.setTextSize(12);
        headerTitle.setGravity(Gravity.CENTER_VERTICAL);
        header.addView(headerTitle, new LinearLayout.LayoutParams(0, dp(34), 1));

        TextView lock = headerButton("◎");
        lock.setContentDescription(context.getString(R.string.overlay_locked));
        lock.setOnClickListener(view -> toggleClickThrough());
        header.addView(lock);
        TextView close = headerButton("×");
        close.setContentDescription(context.getString(R.string.action_hide));
        close.setOnClickListener(view -> hide());
        header.addView(close);
        content.addView(header, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(42)));
        header.setOnTouchListener(new DragListener());

        chat = new ChatListView(context);
        content.addView(chat, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));

        TextView resize = new TextView(context);
        resize.setText("⌟");
        resize.setTextColor(Color.argb(210, 245, 247, 251));
        resize.setTextSize(22);
        resize.setGravity(Gravity.BOTTOM | Gravity.END);
        resize.setContentDescription(context.getString(R.string.overlay_resize_hint));
        FrameLayout.LayoutParams resizeParams = new FrameLayout.LayoutParams(dp(38), dp(38),
                Gravity.BOTTOM | Gravity.END);
        frame.addView(resize, resizeParams);
        resize.setOnTouchListener(new ResizeListener());
        applyPanelOpacity(header);
        return frame;
    }

    private TextView headerButton(String text) {
        TextView button = new TextView(context);
        button.setText(text);
        button.setTextColor(Color.WHITE);
        button.setTextSize(20);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(4), 0, dp(4), 0);
        button.setLayoutParams(new LinearLayout.LayoutParams(dp(38), dp(34)));
        return button;
    }

    private int baseFlags() {
        return WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN;
    }

    private void applyClickThroughFlags() {
        if (parameters == null) return;
        parameters.flags = baseFlags();
        if (settings.overlayClickThrough)
            parameters.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
        if (headerTitle != null) headerTitle.setText(settings.overlayClickThrough
                ? R.string.overlay_locked : R.string.overlay_drag_hint);
    }

    private void applyPanelOpacity() {
        if (root == null) return;
        View header = root.findViewWithTag("header");
        if (header != null) applyPanelOpacity(header);
    }

    private void applyPanelOpacity(View header) {
        int alpha = Math.round(AppSettings.clamp(settings.backgroundOpacity, 0, 100) * 255 / 100f);
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.argb(alpha, 21, 27, 40));
        background.setCornerRadius(dp(9));
        header.setBackground(background);
    }

    private void updateLayout() {
        if (root == null || parameters == null || windowManager == null) return;
        clampGeometry();
        try {
            windowManager.updateViewLayout(root, parameters);
        } catch (RuntimeException failure) {
            Log.w(TAG, "Unable to update floating overlay geometry", failure);
        }
    }

    private void clampGeometry() {
        if (parameters == null || windowManager == null) return;
        Rect bounds = displayBounds();
        int availableWidth = Math.max(1, bounds.width());
        int availableHeight = Math.max(1, bounds.height());
        int minimumWidth = Math.min(dp(280), availableWidth);
        int minimumHeight = Math.min(dp(240), availableHeight);

        parameters.width = Math.max(minimumWidth, Math.min(parameters.width, availableWidth));
        parameters.height = Math.max(minimumHeight, Math.min(parameters.height, availableHeight));

        int maxX = Math.max(bounds.left, bounds.right - parameters.width);
        int maxY = Math.max(bounds.top, bounds.bottom - parameters.height);
        parameters.x = Math.max(bounds.left, Math.min(parameters.x, maxX));
        parameters.y = Math.max(bounds.top, Math.min(parameters.y, maxY));
    }

    @SuppressWarnings("deprecation")
    private Rect displayBounds() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            return new Rect(windowManager.getCurrentWindowMetrics().getBounds());
        }
        DisplayMetrics metrics = new DisplayMetrics();
        windowManager.getDefaultDisplay().getRealMetrics(metrics);
        return new Rect(0, 0, metrics.widthPixels, metrics.heightPixels);
    }

    private void saveGeometry() {
        if (parameters == null) return;
        clampGeometry();
        settings.overlayX = parameters.x;
        settings.overlayY = parameters.y;
        settings.overlayWidth = parameters.width;
        settings.overlayHeight = parameters.height;
        settings.save(context);
    }

    private final class DragListener implements View.OnTouchListener {
        private float startRawX, startRawY;
        private int startX, startY;
        @Override public boolean onTouch(View view, MotionEvent event) {
            if (parameters == null) return false;
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                startRawX = event.getRawX();
                startRawY = event.getRawY();
                startX = parameters.x;
                startY = parameters.y;
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_MOVE) {
                parameters.x = startX + Math.round(event.getRawX() - startRawX);
                parameters.y = startY + Math.round(event.getRawY() - startRawY);
                updateLayout();
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_UP
                    || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                saveGeometry();
                return true;
            }
            return false;
        }
    }

    private final class ResizeListener implements View.OnTouchListener {
        private float startRawX, startRawY;
        private int startWidth, startHeight;
        @Override public boolean onTouch(View view, MotionEvent event) {
            if (parameters == null) return false;
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                startRawX = event.getRawX();
                startRawY = event.getRawY();
                startWidth = parameters.width;
                startHeight = parameters.height;
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_MOVE) {
                parameters.width = startWidth + Math.round(event.getRawX() - startRawX);
                parameters.height = startHeight + Math.round(event.getRawY() - startRawY);
                updateLayout();
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_UP
                    || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                saveGeometry();
                return true;
            }
            return false;
        }
    }

    private int dp(int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }
}
