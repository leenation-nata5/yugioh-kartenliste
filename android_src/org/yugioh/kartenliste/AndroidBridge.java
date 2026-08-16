package org.yugioh.kartenliste;

import android.content.Context;

import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;

import java.util.concurrent.TimeUnit;

public final class AndroidBridge {
    private AndroidBridge() {
    }

    public static void scheduleScanResumeWorker(Context context, String queueId) {
        if (context == null || queueId == null || queueId.isEmpty()) {
            return;
        }
        Data data = new Data.Builder().putString("queue_id", queueId).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(ScanResumeWorker.class)
                .setInputData(data)
                .setInitialDelay(15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                "just_incard_scan_" + queueId,
                ExistingWorkPolicy.REPLACE,
                request
        );
    }

    public static void cancelScanResumeWorker(Context context, String queueId) {
        if (context == null || queueId == null || queueId.isEmpty()) {
            return;
        }
        WorkManager.getInstance(context).cancelUniqueWork("just_incard_scan_" + queueId);
    }
}
