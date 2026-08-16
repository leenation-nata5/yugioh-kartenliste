package org.yugioh.kartenliste;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.kivy.android.PythonActivity;

/** Reminds the user about a persisted scan queue if Android stopped the app. */
public final class ScanResumeWorker extends Worker {
    private static final String CHANNEL_ID = "just_incard_scan_queue";

    public ScanResumeWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        String queueId = getInputData().getString("queue_id");
        createChannel(context);
        Intent launchIntent = new Intent(context, PythonActivity.class);
        launchIntent.putExtra("just_incard_shortcut", "bulk_scan");
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                9101,
                launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(context.getApplicationInfo().icon)
                .setContentTitle("Just InCard – Scan fortsetzen")
                .setContentText("Ein Galerie-Scan wartet auf Fortsetzung.")
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT);
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        manager.notify(queueId == null ? 9101 : Math.abs(queueId.hashCode()), builder.build());
        return Result.success();
    }

    private static void createChannel(Context context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Scan-Warteschlange",
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            channel.setDescription("Erinnerung an unterbrochene Galerie-Scans");
            manager.createNotificationChannel(channel);
        }
    }
}
