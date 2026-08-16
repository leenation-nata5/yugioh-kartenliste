package org.yugioh.kartenliste;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.Surface;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageCapture;
import androidx.camera.core.ImageCaptureException;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.io.File;
import java.util.concurrent.Executor;

/** Native CameraX capture activity used by the Kivy scanner as a stable Android path. */
public final class CameraXScanActivity extends AppCompatActivity {
    private PreviewView previewView;
    private ImageCapture imageCapture;
    private ProcessCameraProvider cameraProvider;
    private TextView statusView;
    private boolean captureRunning = false;
    private TextRecognizer liveRecognizer;
    private long lastAnalysisAt = 0L;
    private boolean analysisRunning = false;
    private String lastRecognizedText = "";
    private boolean tabletLayout = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        tabletLayout = getResources().getConfiguration().smallestScreenWidthDp >= 600;
        buildUi();
        startCamera();
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void buildUi() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        previewView = new PreviewView(this);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        previewView.setScaleType(PreviewView.ScaleType.FIT_CENTER);
        root.addView(previewView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        View cardGuide = new View(this);
        cardGuide.setContentDescription("Kartenrahmen");
        cardGuide.setBackgroundResource(android.R.drawable.dialog_holo_light_frame);
        int guideWidth = tabletLayout ? dp(360) : dp(250);
        int guideHeight = Math.round(guideWidth * 1.452f);
        FrameLayout.LayoutParams guideParams = new FrameLayout.LayoutParams(guideWidth, guideHeight);
        guideParams.gravity = Gravity.CENTER;
        root.addView(cardGuide, guideParams);

        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setPadding(dp(tabletLayout ? 20 : 12), dp(8), dp(tabletLayout ? 16 : 8), dp(8));
        topBar.setBackgroundColor(0xAA000000);

        statusView = new TextView(this);
        statusView.setText(tabletLayout ? "CameraX – Tabletansicht wird vorbereitet …" : "CameraX wird vorbereitet …");
        statusView.setTextColor(Color.WHITE);
        statusView.setTextSize(tabletLayout ? 18f : 15f);
        topBar.addView(statusView, new LinearLayout.LayoutParams(0, dp(48), 1f));

        Button closeButton = new Button(this);
        closeButton.setText("X");
        closeButton.setContentDescription("Scanner schließen");
        closeButton.setMinWidth(dp(48));
        closeButton.setMinHeight(dp(48));
        closeButton.setOnClickListener(v -> finishCancelled());
        topBar.addView(closeButton, new LinearLayout.LayoutParams(dp(52), dp(48)));

        FrameLayout.LayoutParams topParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        topParams.gravity = Gravity.TOP;
        root.addView(topBar, topParams);

        Button captureButton = new Button(this);
        captureButton.setText("Foto aufnehmen");
        captureButton.setContentDescription("Kartenfoto aufnehmen");
        captureButton.setMinHeight(dp(tabletLayout ? 64 : 56));
        captureButton.setTextSize(tabletLayout ? 18f : 14f);
        captureButton.setOnClickListener(v -> capturePhoto(captureButton));
        FrameLayout.LayoutParams captureParams = new FrameLayout.LayoutParams(
                dp(tabletLayout ? 320 : 220),
                dp(tabletLayout ? 68 : 58)
        );
        captureParams.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        captureParams.bottomMargin = dp(tabletLayout ? 36 : 24);
        root.addView(captureButton, captureParams);

        setContentView(root);
    }

    private void startCamera() {
        Executor executor = ContextCompat.getMainExecutor(this);
        ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            try {
                cameraProvider = future.get();
                Preview preview = new Preview.Builder().build();
                imageCapture = new ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setTargetRotation(currentRotation())
                        .build();
                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setTargetRotation(currentRotation())
                        .build();
                liveRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                analysis.setAnalyzer(executor, this::analyzeFrame);
                preview.setSurfaceProvider(previewView.getSurfaceProvider());
                cameraProvider.unbindAll();
                cameraProvider.bindToLifecycle(
                        this,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageCapture,
                        analysis
                );
                statusView.setText("Karte im Rahmen ausrichten");
            } catch (Throwable error) {
                statusView.setText("CameraX konnte nicht gestartet werden");
                Intent data = new Intent();
                data.putExtra("camera_error", String.valueOf(error.getMessage()));
                setResult(Activity.RESULT_CANCELED, data);
            }
        }, executor);
    }

    private void analyzeFrame(@NonNull ImageProxy imageProxy) {
        long now = System.currentTimeMillis();
        if (now - lastAnalysisAt < 650L || analysisRunning || liveRecognizer == null || imageProxy.getImage() == null) {
            imageProxy.close();
            return;
        }
        lastAnalysisAt = now;
        analysisRunning = true;
        InputImage input = InputImage.fromMediaImage(imageProxy.getImage(), imageProxy.getImageInfo().getRotationDegrees());
        liveRecognizer.process(input)
                .addOnSuccessListener(result -> {
                    String raw = result.getText();
                    if (raw != null && !raw.trim().isEmpty()) {
                        lastRecognizedText = raw;
                        String first = raw.trim().split("\n")[0];
                        if (first.length() > 48) {
                            first = first.substring(0, 48) + "…";
                        }
                        final String display = first;
                        statusView.post(() -> statusView.setText("Erkannt: " + display));
                    }
                })
                .addOnFailureListener(error -> {
                    // Liveanalyse ist optional; Aufnahme bleibt verfügbar.
                })
                .addOnCompleteListener(task -> {
                    analysisRunning = false;
                    imageProxy.close();
                });
    }

    private int currentRotation() {
        if (previewView != null && previewView.getDisplay() != null) {
            return previewView.getDisplay().getRotation();
        }
        return Surface.ROTATION_0;
    }

    private void capturePhoto(Button captureButton) {
        if (captureRunning || imageCapture == null) {
            return;
        }
        captureRunning = true;
        captureButton.setEnabled(false);
        statusView.setText("Foto wird gespeichert …");
        imageCapture.setTargetRotation(currentRotation());

        File output = new File(getCacheDir(), "camerax_scan_" + System.currentTimeMillis() + ".jpg");
        ImageCapture.OutputFileOptions options = new ImageCapture.OutputFileOptions.Builder(output).build();
        imageCapture.takePicture(options, ContextCompat.getMainExecutor(this), new ImageCapture.OnImageSavedCallback() {
            @Override
            public void onImageSaved(@NonNull ImageCapture.OutputFileResults outputFileResults) {
                Intent result = new Intent();
                result.putExtra("image_path", output.getAbsolutePath());
                result.putExtra("ocr_text", lastRecognizedText);
                setResult(Activity.RESULT_OK, result);
                finish();
            }

            @Override
            public void onError(@NonNull ImageCaptureException exception) {
                captureRunning = false;
                captureButton.setEnabled(true);
                statusView.setText("Foto fehlgeschlagen – erneut versuchen");
            }
        });
    }

    private void finishCancelled() {
        setResult(Activity.RESULT_CANCELED);
        finish();
    }

    @Override
    protected void onDestroy() {
        try {
            if (cameraProvider != null) {
                cameraProvider.unbindAll();
            }
            if (liveRecognizer != null) {
                liveRecognizer.close();
            }
        } catch (Throwable ignored) {
        }
        super.onDestroy();
    }
}
