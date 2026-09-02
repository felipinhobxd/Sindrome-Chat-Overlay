package com.sindromegames.chatoverlay.overlay;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.provider.Settings;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.app.ServiceCompat;

import com.sindromegames.chatoverlay.ChatBus;
import com.sindromegames.chatoverlay.ChatEngine;
import com.sindromegames.chatoverlay.MainActivity;
import com.sindromegames.chatoverlay.R;

public final class OverlayService extends Service {
    public static final String ACTION_START = "com.sindromegames.chatoverlay.START";
    public static final String ACTION_STOP = "com.sindromegames.chatoverlay.STOP";
    public static final String ACTION_RESTART = "com.sindromegames.chatoverlay.RESTART";
    public static final String ACTION_SHOW = "com.sindromegames.chatoverlay.SHOW";
    public static final String ACTION_HIDE = "com.sindromegames.chatoverlay.HIDE";
    public static final String ACTION_TOGGLE_LOCK = "com.sindromegames.chatoverlay.TOGGLE_LOCK";
    private static final String CHANNEL = "chat_overlay";
    private static final int NOTIFICATION_ID = 7301;

    private ChatEngine engine;
    private OverlayWindow overlay;

    @Override public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        engine = new ChatEngine(this);
        overlay = new OverlayWindow(this, this::refreshNotification);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_START : intent.getAction();
        startInForeground();
        if (ACTION_STOP.equals(action)) {
            overlay.hide();
            engine.stop();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return START_NOT_STICKY;
        }
        if (ACTION_RESTART.equals(action)) {
            engine.restart();
            overlay.refreshSettings();
        } else if (ACTION_SHOW.equals(action)) {
            if (!ChatBus.state().running()) engine.start();
            if (Settings.canDrawOverlays(this)) overlay.show();
        } else if (ACTION_HIDE.equals(action)) {
            overlay.hide();
        } else if (ACTION_TOGGLE_LOCK.equals(action)) {
            overlay.toggleClickThrough();
        } else if (!ChatBus.state().running()) {
            engine.start();
        }
        refreshNotification();
        return START_STICKY;
    }

    @Override public void onDestroy() {
        overlay.hide();
        engine.destroy();
        super.onDestroy();
    }

    @Nullable @Override public IBinder onBind(Intent intent) { return null; }

    private void startInForeground() {
        int type = Build.VERSION.SDK_INT >= 34 ? ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE : 0;
        ServiceCompat.startForeground(this, NOTIFICATION_ID, notification(), type);
    }

    private void refreshNotification() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) manager.notify(NOTIFICATION_ID, notification());
    }

    private Notification notification() {
        ChatBus.State state = ChatBus.state();
        Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent openIntent = PendingIntent.getActivity(this, 1, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(R.string.notification_title)
                .setContentText(state.clickThrough() ? getString(R.string.overlay_unlock_notification)
                        : getString(R.string.notification_text))
                .setContentIntent(openIntent)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setCategory(NotificationCompat.CATEGORY_SERVICE)
                .setPriority(NotificationCompat.PRIORITY_LOW);
        if (state.overlayVisible()) {
            if (state.clickThrough()) builder.addAction(0, getString(R.string.action_unlock),
                    serviceIntent(ACTION_TOGGLE_LOCK, 4));
            builder.addAction(0, getString(R.string.action_hide), serviceIntent(ACTION_HIDE, 2));
        } else {
            builder.addAction(0, getString(R.string.action_show), serviceIntent(ACTION_SHOW, 3));
        }
        builder.addAction(0, getString(R.string.action_stop), serviceIntent(ACTION_STOP, 5));
        return builder.build();
    }

    private PendingIntent serviceIntent(String action, int requestCode) {
        Intent intent = new Intent(this, OverlayService.class).setAction(action);
        return PendingIntent.getService(this, requestCode, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL,
                getString(R.string.notification_channel_name), NotificationManager.IMPORTANCE_LOW);
        channel.setDescription(getString(R.string.notification_channel_description));
        channel.setSound(null, null);
        channel.enableVibration(false);
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) manager.createNotificationChannel(channel);
    }
}

