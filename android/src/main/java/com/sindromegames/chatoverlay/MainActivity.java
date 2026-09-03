package com.sindromegames.chatoverlay;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.sindromegames.chatoverlay.model.ChatMessage;
import com.sindromegames.chatoverlay.overlay.OverlayService;
import com.sindromegames.chatoverlay.settings.AppSettings;
import com.sindromegames.chatoverlay.ui.ChatListView;

import java.util.List;

public final class MainActivity extends AppCompatActivity implements ChatBus.Listener {
    private Button startButton;
    private Button overlayButton;
    private TextView status;
    private boolean pendingOverlay;

    private final ActivityResultLauncher<Intent> overlayPermission = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(), result -> handleOverlayPermissionReturn());
    private final ActivityResultLauncher<Intent> settingsLauncher = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(), result -> {
                if (ChatBus.state().running()) send(OverlayService.ACTION_RESTART);
            });
    private final ActivityResultLauncher<String> notificationsPermission = registerForActivityResult(
            new ActivityResultContracts.RequestPermission(), granted -> {});

    @Override protected void onCreate(Bundle savedInstanceState) {
        AppSettings.applyLocale(this);
        super.onCreate(savedInstanceState);
        buildUi();
        requestNotificationsIfNeeded();
        getWindow().getDecorView().post(() -> {
            if (!isFinishing() && !ChatBus.state().running()) send(OverlayService.ACTION_START);
        });
    }

    @Override protected void onStart() {
        super.onStart();
        ChatBus.register(this);
    }

    @Override protected void onResume() {
        super.onResume();
        if (pendingOverlay && Settings.canDrawOverlays(this)) {
            pendingOverlay = false;
            send(OverlayService.ACTION_SHOW);
        }
    }

    @Override protected void onStop() {
        ChatBus.unregister(this);
        super.onStop();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(10), dp(12), dp(8));
        root.setBackgroundColor(ContextCompat.getColor(this, R.color.surface));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        TextView title = new TextView(this);
        title.setText(R.string.app_name);
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        TextView subtitle = new TextView(this);
        subtitle.setText(R.string.mobile_subtitle);
        subtitle.setTextColor(ContextCompat.getColor(this, R.color.text_secondary));
        subtitle.setTextSize(12);
        titles.addView(title);
        titles.addView(subtitle);
        header.addView(titles, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        Button settingsButton = new Button(this);
        settingsButton.setText("⚙");
        settingsButton.setContentDescription(getString(R.string.open_settings));
        settingsButton.setOnClickListener(view -> settingsLauncher.launch(
                new Intent(this, SettingsActivity.class)));
        header.addView(settingsButton, new LinearLayout.LayoutParams(dp(54), dp(48)));
        root.addView(header);

        status = new TextView(this);
        status.setTextColor(ContextCompat.getColor(this, R.color.text_secondary));
        status.setTextSize(12);
        status.setPadding(dp(2), dp(7), dp(2), dp(7));
        root.addView(status);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        startButton = new Button(this);
        startButton.setOnClickListener(view -> send(ChatBus.state().running()
                ? OverlayService.ACTION_STOP : OverlayService.ACTION_START));
        actions.addView(startButton, new LinearLayout.LayoutParams(0, dp(52), 1));
        overlayButton = new Button(this);
        overlayButton.setOnClickListener(view -> toggleOverlay());
        actions.addView(overlayButton, new LinearLayout.LayoutParams(0, dp(52), 1));
        Button clear = new Button(this);
        clear.setText("⌫");
        clear.setContentDescription(getString(R.string.action_stop));
        clear.setOnClickListener(view -> ChatBus.clearAll());
        actions.addView(clear, new LinearLayout.LayoutParams(dp(58), dp(52)));
        root.addView(actions);

        ChatListView chat = new ChatListView(this);
        root.addView(chat, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
        renderState(ChatBus.state());
    }

    private void toggleOverlay() {
        if (ChatBus.state().overlayVisible()) {
            send(OverlayService.ACTION_HIDE);
            return;
        }
        if (!Settings.canDrawOverlays(this)) {
            pendingOverlay = true;
            new AlertDialog.Builder(this)
                    .setTitle(R.string.permission_overlay_title)
                    .setMessage(R.string.permission_overlay_message)
                    .setNegativeButton(R.string.cancel, (dialog, which) -> pendingOverlay = false)
                    .setPositiveButton(android.R.string.ok, (dialog, which) ->
                            launchOverlayPermissionSettings())
                    .show();
            return;
        }
        send(OverlayService.ACTION_SHOW);
    }

    private void launchOverlayPermissionSettings() {
        Intent packagePermission = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName()));
        try {
            overlayPermission.launch(packagePermission);
            return;
        } catch (ActivityNotFoundException | SecurityException ignored) {}

        try {
            overlayPermission.launch(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION));
            return;
        } catch (ActivityNotFoundException | SecurityException ignored) {}

        openApplicationDetails();
    }

    private void handleOverlayPermissionReturn() {
        if (!pendingOverlay) return;
        if (Settings.canDrawOverlays(this)) {
            pendingOverlay = false;
            send(OverlayService.ACTION_SHOW);
            return;
        }
        pendingOverlay = false;
        showOverlayPermissionHelp();
    }

    private void showOverlayPermissionHelp() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.permission_overlay_title)
                .setMessage(R.string.overlay_permission_restricted_help)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.open_app_settings, (dialog, which) -> openApplicationDetails())
                .show();
    }

    private void openApplicationDetails() {
        Intent details = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.parse("package:" + getPackageName()));
        try {
            startActivity(details);
        } catch (ActivityNotFoundException | SecurityException ignored) {
            Toast.makeText(this, R.string.overlay_permission_missing, Toast.LENGTH_LONG).show();
        }
    }

    private void send(String action) {
        Intent intent = new Intent(this, OverlayService.class).setAction(action);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                    && !OverlayService.ACTION_STOP.equals(action)
                    && !OverlayService.ACTION_HIDE.equals(action)) {
                ContextCompat.startForegroundService(this, intent);
            } else {
                startService(intent);
            }
        } catch (RuntimeException failure) {
            Toast.makeText(this, R.string.unknown_error, Toast.LENGTH_LONG).show();
        }
    }

    private void requestNotificationsIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this,
                Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            notificationsPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
        }
    }

    private void renderState(ChatBus.State state) {
        startButton.setText(state.running() ? R.string.stop_chat : R.string.start_chat);
        overlayButton.setText(state.overlayVisible() ? R.string.hide_overlay : R.string.show_overlay);
        String twitch = readableStatus("Twitch", state.twitchStatus());
        String youtube = readableStatus("YouTube", state.youtubeStatus());
        status.setText(twitch + "  •  " + youtube);
    }

    private String readableStatus(String platform, String value) {
        int resource = switch (value) {
            case "connected" -> platform.equals("Twitch") ? R.string.twitch_connected : R.string.connected;
            case "compatibility" -> R.string.youtube_compatibility_connected;
            case "compatibility_fallback" -> R.string.youtube_mode_fallback;
            case "official_stream" -> R.string.youtube_official_connected;
            case "official_polling" -> R.string.youtube_official_polling_connected;
            case "waiting_live" -> R.string.waiting_live;
            case "rate_limited" -> R.string.rate_limited;
            case "chat_disabled" -> R.string.youtube_chat_disabled;
            case "invalid_key" -> R.string.youtube_key_rejected;
            case "reconnecting" -> R.string.reconnecting;
            case "connecting" -> R.string.connecting;
            default -> R.string.chat_stopped;
        };
        return getString(resource);
    }

    @Override public void onInitial(List<ChatMessage> messages, ChatBus.State state) {
        renderState(state);
    }

    @Override public void onMessage(ChatMessage message) {}
    @Override public void onHistoryChanged(List<ChatMessage> messages) {}
    @Override public void onState(ChatBus.State state) { renderState(state); }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
