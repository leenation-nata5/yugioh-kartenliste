package org.yugioh.kartenliste;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.Camera;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ExposureState;
import androidx.camera.core.FocusMeteringAction;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageCapture;
import androidx.camera.core.ImageCaptureException;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.MeteringPoint;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.io.File;
import java.nio.ByteBuffer;
import java.util.Locale;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Responsive CameraX + ML Kit scanner for phones, tablets and foldables.
 * Analysis stays off the UI executor, keeps only the newest frame and limits
 * OCR evidence to the visible card guide. Auto capture needs three stable frames.
 */
public final class CameraXScanActivity extends AppCompatActivity {
    private static final int GOLD = 0xFFFFD45B;
    private static final int BLUE = 0xFF5B9DFF;
    private static final int GREEN = 0xFF21D87A;
    private static final int PANEL = 0xE60A1122;

    private PreviewView previewView;
    private CardGuideView guideView;
    private ImageCapture imageCapture;
    private ProcessCameraProvider cameraProvider;
    private Camera camera;
    private TextView statusView;
    private Button captureButton;
    private Button torchButton;
    private Button autoButton;
    private ExecutorService analysisExecutor;
    private TextRecognizer liveRecognizer;

    private boolean captureRunning = false;
    private boolean analysisRunning = false;
    private boolean torchEnabled = false;
    private boolean autoCaptureEnabled = true;
    private long lastAnalysisAt = 0L;
    private long lastAutoCaptureAt = 0L;
    private String lastRecognizedText = "";
    private String lastFingerprint = "";
    private int stableFrames = 0;
    private byte[] previousLumaSample;
    private float latestBrightness = 0f;
    private float latestMotion = 1f;
    private boolean tabletLayout = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        // Current window width is authoritative. A tablet in split screen must
        // receive the same safe two-row controls as a narrow phone window.
        tabletLayout = getResources().getConfiguration().screenWidthDp >= 720;
        analysisExecutor = Executors.newSingleThreadExecutor(runnable -> {
            Thread thread = new Thread(runnable, "JustInCard-CameraAnalysis");
            thread.setPriority(Thread.NORM_PRIORITY - 1);
            return thread;
        });
        buildUi();
        startCamera();
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable pill(int color, int strokeColor, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        drawable.setStroke(dp(1), strokeColor);
        return drawable;
    }

    private Button controlButton(String text, String description) {
        Button button = new Button(this);
        button.setText(text);
        button.setContentDescription(description);
        button.setTextColor(Color.WHITE);
        button.setTextSize(tabletLayout ? 15f : 13f);
        button.setAllCaps(false);
        button.setMinWidth(dp(52));
        button.setMinHeight(dp(52));
        button.setPadding(dp(10), 0, dp(10), 0);
        button.setBackground(pill(PANEL, 0x664E79B8, 26));
        return button;
    }

    private TextView chip(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(Color.WHITE);
        view.setGravity(Gravity.CENTER);
        view.setTextSize(tabletLayout ? 15f : 13f);
        view.setSingleLine(true);
        view.setPadding(dp(16), 0, dp(16), 0);
        view.setBackground(pill(PANEL, 0x554E79B8, 26));
        return view;
    }

    private void buildUi() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF020611);
        root.setFitsSystemWindows(true);

        previewView = new PreviewView(this);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        previewView.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        previewView.setContentDescription("Live-Kameravorschau");
        root.addView(previewView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        guideView = new CardGuideView();
        root.addView(guideView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(tabletLayout ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        topBar.setGravity(tabletLayout ? Gravity.CENTER_VERTICAL : Gravity.END);
        topBar.setPadding(dp(12), dp(10), dp(12), dp(6));

        statusView = chip("Automatische Erkennung wird vorbereitet …");
        LinearLayout.LayoutParams statusParams = tabletLayout
                ? new LinearLayout.LayoutParams(0, dp(54), 1f)
                : new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(50));
        if (tabletLayout) statusParams.setMarginEnd(dp(10));
        topBar.addView(statusView, statusParams);

        TextView deviceView = chip("●  " + deviceLabel());
        deviceView.setTextColor(0xFFE0E8FA);
        LinearLayout.LayoutParams deviceParams = new LinearLayout.LayoutParams(
                tabletLayout ? dp(238) : ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(50)
        );
        if (!tabletLayout) deviceParams.topMargin = dp(6);
        topBar.addView(deviceView, deviceParams);

        FrameLayout.LayoutParams topParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        topParams.gravity = Gravity.TOP;
        root.addView(topBar, topParams);

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(tabletLayout ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        controls.setGravity(Gravity.CENTER);
        controls.setPadding(dp(8), dp(6), dp(8), dp(10));

        LinearLayout primaryControls = controls;
        LinearLayout secondaryControls = controls;
        if (!tabletLayout) {
            primaryControls = new LinearLayout(this);
            primaryControls.setOrientation(LinearLayout.HORIZONTAL);
            primaryControls.setGravity(Gravity.CENTER);
            secondaryControls = new LinearLayout(this);
            secondaryControls.setOrientation(LinearLayout.HORIZONTAL);
            secondaryControls.setGravity(Gravity.CENTER);
            controls.addView(primaryControls, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(58)));
            LinearLayout.LayoutParams secondRow = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(58));
            secondRow.topMargin = dp(6);
            controls.addView(secondaryControls, secondRow);
        }

        Button closeButton = controlButton("Schließen", "Scanner schließen");
        closeButton.setOnClickListener(view -> finishCancelled());
        primaryControls.addView(closeButton, tabletLayout
                ? new LinearLayout.LayoutParams(dp(116), dp(56))
                : new LinearLayout.LayoutParams(0, dp(56), 0.86f));

        torchButton = controlButton("Licht", "Taschenlampe ein- oder ausschalten");
        torchButton.setOnClickListener(view -> toggleTorch());
        LinearLayout.LayoutParams smallParams = tabletLayout
                ? new LinearLayout.LayoutParams(dp(92), dp(56))
                : new LinearLayout.LayoutParams(0, dp(56), 0.68f);
        smallParams.setMarginStart(dp(8));
        primaryControls.addView(torchButton, smallParams);

        Button exposureDown = controlButton("EV −", "Belichtung verringern");
        exposureDown.setOnClickListener(view -> adjustExposure(-1));
        LinearLayout.LayoutParams exposureParams = tabletLayout
                ? new LinearLayout.LayoutParams(dp(78), dp(56))
                : new LinearLayout.LayoutParams(0, dp(56), 0.8f);
        if (tabletLayout) exposureParams.setMarginStart(dp(8));
        secondaryControls.addView(exposureDown, exposureParams);

        Button exposureUp = controlButton("EV +", "Belichtung erhöhen");
        exposureUp.setOnClickListener(view -> adjustExposure(1));
        LinearLayout.LayoutParams exposureUpParams = tabletLayout
                ? new LinearLayout.LayoutParams(dp(78), dp(56))
                : new LinearLayout.LayoutParams(0, dp(56), 0.8f);
        exposureUpParams.setMarginStart(dp(6));
        secondaryControls.addView(exposureUp, exposureUpParams);

        captureButton = controlButton("Aufnehmen", "Kartenfoto aufnehmen");
        captureButton.setTextSize(tabletLayout ? 17f : 14f);
        captureButton.setBackground(pill(0xFF174E9C, BLUE, 28));
        captureButton.setOnClickListener(view -> capturePhoto(false));
        LinearLayout.LayoutParams captureParams = tabletLayout
                ? new LinearLayout.LayoutParams(dp(170), dp(60))
                : new LinearLayout.LayoutParams(0, dp(56), 1.18f);
        captureParams.setMarginStart(dp(8));
        primaryControls.addView(captureButton, captureParams);

        autoButton = controlButton("Auto ✓", "Automatische Aufnahme ein- oder ausschalten");
        autoButton.setOnClickListener(view -> {
            autoCaptureEnabled = !autoCaptureEnabled;
            stableFrames = 0;
            autoButton.setText(autoCaptureEnabled ? "Auto ✓" : "Auto aus");
            autoButton.setBackground(pill(autoCaptureEnabled ? 0xFF0E6842 : PANEL, autoCaptureEnabled ? GREEN : 0x664E79B8, 26));
            setStatus(autoCaptureEnabled ? "Automatische Erkennung aktiv" : "Manuelle Aufnahme aktiv", autoCaptureEnabled ? BLUE : GOLD);
        });
        LinearLayout.LayoutParams autoParams = tabletLayout
                ? new LinearLayout.LayoutParams(dp(112), dp(56))
                : new LinearLayout.LayoutParams(0, dp(56), 1.05f);
        autoParams.setMarginStart(dp(8));
        secondaryControls.addView(autoButton, autoParams);

        FrameLayout.LayoutParams controlsParams = new FrameLayout.LayoutParams(
                tabletLayout ? ViewGroup.LayoutParams.WRAP_CONTENT : ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        controlsParams.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        controlsParams.bottomMargin = dp(tabletLayout ? 16 : 8);
        root.addView(controls, controlsParams);

        previewView.setOnTouchListener((view, event) -> {
            if (event.getAction() == MotionEvent.ACTION_UP) {
                focusAt(event.getX(), event.getY());
                view.performClick();
            }
            return true;
        });
        setContentView(root);
    }

    private String deviceLabel() {
        String manufacturer = Build.MANUFACTURER == null ? "Android" : Build.MANUFACTURER.trim();
        String model = Build.MODEL == null ? "Gerät" : Build.MODEL.trim();
        String label = model.toLowerCase(Locale.ROOT).startsWith(manufacturer.toLowerCase(Locale.ROOT))
                ? model : manufacturer + " " + model;
        return label.length() > 28 ? label.substring(0, 27) + "…" : label;
    }

    private void startCamera() {
        Executor mainExecutor = ContextCompat.getMainExecutor(this);
        ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            try {
                cameraProvider = future.get();
                Preview preview = new Preview.Builder().setTargetRotation(currentRotation()).build();
                imageCapture = new ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setJpegQuality(95)
                        .setTargetRotation(currentRotation())
                        .build();
                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                        .setTargetRotation(currentRotation())
                        .build();
                liveRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                analysis.setAnalyzer(analysisExecutor, this::analyzeFrame);
                preview.setSurfaceProvider(previewView.getSurfaceProvider());
                cameraProvider.unbindAll();
                camera = cameraProvider.bindToLifecycle(
                        this,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageCapture,
                        analysis
                );
                torchButton.setEnabled(camera.getCameraInfo().hasFlashUnit());
                setStatus("Karte vollständig im Rahmen ausrichten", BLUE);
            } catch (Throwable error) {
                setStatus("CameraX konnte nicht gestartet werden", Color.RED);
                Intent data = new Intent();
                data.putExtra("camera_error", String.valueOf(error.getMessage()));
                setResult(Activity.RESULT_CANCELED, data);
            }
        }, mainExecutor);
    }

    private void analyzeFrame(@NonNull ImageProxy imageProxy) {
        long now = System.currentTimeMillis();
        if (now - lastAnalysisAt < 420L || analysisRunning || liveRecognizer == null || imageProxy.getImage() == null) {
            imageProxy.close();
            return;
        }
        lastAnalysisAt = now;
        analysisRunning = true;
        analyzeLuma(imageProxy);
        int rotation = imageProxy.getImageInfo().getRotationDegrees();
        int orientedWidth = (rotation == 90 || rotation == 270) ? imageProxy.getHeight() : imageProxy.getWidth();
        int orientedHeight = (rotation == 90 || rotation == 270) ? imageProxy.getWidth() : imageProxy.getHeight();
        InputImage input = InputImage.fromMediaImage(imageProxy.getImage(), rotation);
        liveRecognizer.process(input)
                .addOnSuccessListener(result -> handleRecognizedText(result, orientedWidth, orientedHeight))
                .addOnFailureListener(error -> setStatus("Text wird neu fokussiert …", GOLD))
                .addOnCompleteListener(task -> {
                    analysisRunning = false;
                    imageProxy.close();
                });
    }

    private void analyzeLuma(ImageProxy proxy) {
        try {
            ByteBuffer buffer = proxy.getPlanes()[0].getBuffer().duplicate();
            int remaining = buffer.remaining();
            int samples = Math.min(256, Math.max(32, remaining / 256));
            byte[] current = new byte[samples];
            long sum = 0L;
            int step = Math.max(1, remaining / samples);
            int start = buffer.position();
            for (int index = 0; index < samples; index++) {
                int position = Math.min(buffer.limit() - 1, start + index * step);
                current[index] = buffer.get(position);
                sum += current[index] & 0xFF;
            }
            latestBrightness = (float) sum / (samples * 255f);
            if (previousLumaSample != null && previousLumaSample.length == current.length) {
                long delta = 0L;
                for (int index = 0; index < current.length; index++) {
                    delta += Math.abs((current[index] & 0xFF) - (previousLumaSample[index] & 0xFF));
                }
                latestMotion = (float) delta / (current.length * 255f);
            }
            previousLumaSample = current;
        } catch (Throwable ignored) {
            latestBrightness = 0.5f;
            latestMotion = 1f;
        }
    }

    private void handleRecognizedText(Text result, int width, int height) {
        RectF roi = new RectF(width * 0.12f, height * 0.08f, width * 0.88f, height * 0.94f);
        StringBuilder builder = new StringBuilder();
        for (Text.TextBlock block : result.getTextBlocks()) {
            Rect box = block.getBoundingBox();
            if (box != null && RectF.intersects(roi, new RectF(box))) {
                builder.append(block.getText()).append('\n');
            }
        }
        String raw = builder.toString().trim();
        if (raw.isEmpty()) {
            stableFrames = 0;
            updateGuidance("Kartenname und Setcode in den Rahmen bringen", GOLD, false);
            return;
        }
        lastRecognizedText = raw;
        String normalized = raw.toUpperCase(Locale.ROOT).replaceAll("[^A-Z0-9]", "");
        String fingerprint = Integer.toHexString(normalized.hashCode());
        boolean evidence = raw.matches("(?s).*[A-Za-z0-9]{2,6}[- ][A-Za-z0-9]{2,8}.*")
                || raw.matches("(?s).*\\b[0-9]{8}\\b.*")
                || raw.length() >= 18;

        if (latestBrightness < 0.18f) {
            stableFrames = 0;
            updateGuidance("Zu dunkel – Licht einschalten", GOLD, false);
        } else if (latestBrightness > 0.94f) {
            stableFrames = 0;
            updateGuidance("Blendung vermeiden", GOLD, false);
        } else if (latestMotion > 0.16f) {
            stableFrames = 0;
            updateGuidance("Ruhig halten", GOLD, false);
        } else if (!evidence) {
            stableFrames = 0;
            updateGuidance("Etwas näher heranführen", GOLD, false);
        } else {
            stableFrames = fingerprint.equals(lastFingerprint) ? stableFrames + 1 : 1;
            lastFingerprint = fingerprint;
            if (stableFrames >= 3) {
                updateGuidance("Stabil erkannt", GREEN, true);
                long now = System.currentTimeMillis();
                if (autoCaptureEnabled && now - lastAutoCaptureAt > 3500L && !captureRunning) {
                    lastAutoCaptureAt = now;
                    statusView.postDelayed(() -> capturePhoto(true), 180L);
                }
            } else {
                updateGuidance("Erkannt – ruhig halten " + stableFrames + "/3", BLUE, false);
            }
        }
    }

    private void updateGuidance(String text, int color, boolean stable) {
        statusView.post(() -> {
            setStatus(text, color);
            guideView.setStable(stable, color);
        });
    }

    private void setStatus(String text, int color) {
        if (statusView == null) return;
        statusView.setText(text);
        statusView.setBackground(pill(PANEL, color, 26));
    }

    private void focusAt(float x, float y) {
        if (camera == null || previewView == null) return;
        try {
            MeteringPoint point = previewView.getMeteringPointFactory().createPoint(x, y);
            FocusMeteringAction action = new FocusMeteringAction.Builder(
                    point,
                    FocusMeteringAction.FLAG_AF | FocusMeteringAction.FLAG_AE
            ).setAutoCancelDuration(3, TimeUnit.SECONDS).build();
            camera.getCameraControl().startFocusAndMetering(action);
            setStatus("Fokus gesetzt", BLUE);
        } catch (Throwable ignored) {
        }
    }

    private void toggleTorch() {
        if (camera == null || !camera.getCameraInfo().hasFlashUnit()) return;
        torchEnabled = !torchEnabled;
        camera.getCameraControl().enableTorch(torchEnabled);
        torchButton.setText(torchEnabled ? "Licht ✓" : "Licht");
        torchButton.setBackground(pill(torchEnabled ? 0xFF6C571A : PANEL, torchEnabled ? GOLD : 0x664E79B8, 26));
    }

    private void adjustExposure(int delta) {
        if (camera == null) return;
        try {
            ExposureState state = camera.getCameraInfo().getExposureState();
            int next = Math.max(state.getExposureCompensationRange().getLower(),
                    Math.min(state.getExposureCompensationRange().getUpper(),
                            state.getExposureCompensationIndex() + delta));
            camera.getCameraControl().setExposureCompensationIndex(next);
            setStatus("Belichtung EV " + (next >= 0 ? "+" : "") + next, BLUE);
        } catch (Throwable ignored) {
        }
    }

    private int currentRotation() {
        if (previewView != null && previewView.getDisplay() != null) {
            return previewView.getDisplay().getRotation();
        }
        return Surface.ROTATION_0;
    }

    private void capturePhoto(boolean automatic) {
        if (captureRunning || imageCapture == null) return;
        captureRunning = true;
        captureButton.setEnabled(false);
        setStatus(automatic ? "Stabil erkannt – Foto wird gespeichert" : "Foto wird gespeichert …", GREEN);
        imageCapture.setTargetRotation(currentRotation());

        File output = new File(getCacheDir(), "camerax_scan_" + System.currentTimeMillis() + ".jpg");
        ImageCapture.OutputFileOptions options = new ImageCapture.OutputFileOptions.Builder(output).build();
        imageCapture.takePicture(options, ContextCompat.getMainExecutor(this), new ImageCapture.OnImageSavedCallback() {
            @Override
            public void onImageSaved(@NonNull ImageCapture.OutputFileResults outputFileResults) {
                vibrateSuccess();
                Intent result = new Intent();
                result.putExtra("image_path", output.getAbsolutePath());
                result.putExtra("ocr_text", lastRecognizedText);
                result.putExtra("auto_captured", automatic);
                result.putExtra("frame_brightness", latestBrightness);
                result.putExtra("frame_motion", latestMotion);
                setResult(Activity.RESULT_OK, result);
                finish();
            }

            @Override
            public void onError(@NonNull ImageCaptureException exception) {
                captureRunning = false;
                captureButton.setEnabled(true);
                stableFrames = 0;
                setStatus("Foto fehlgeschlagen – erneut versuchen", Color.RED);
            }
        });
    }

    private void vibrateSuccess() {
        try {
            Vibrator vibrator = (Vibrator) getSystemService(VIBRATOR_SERVICE);
            if (vibrator == null || !vibrator.hasVibrator()) return;
            if (Build.VERSION.SDK_INT >= 26) {
                vibrator.vibrate(VibrationEffect.createOneShot(28, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                vibrator.vibrate(28);
            }
        } catch (Throwable ignored) {
        }
    }

    private void finishCancelled() {
        setResult(Activity.RESULT_CANCELED);
        finish();
    }

    @Override
    public void onBackPressed() {
        finishCancelled();
    }

    @Override
    protected void onDestroy() {
        try {
            if (cameraProvider != null) cameraProvider.unbindAll();
            if (liveRecognizer != null) liveRecognizer.close();
            if (analysisExecutor != null) analysisExecutor.shutdownNow();
        } catch (Throwable ignored) {
        }
        super.onDestroy();
    }

    /** Responsive card frame, dimmed exterior and golden/green corners. */
    private final class CardGuideView extends View {
        private final Paint dimPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint framePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint cornerPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF frame = new RectF();
        private int accent = GOLD;
        private boolean stable = false;

        CardGuideView() {
            super(CameraXScanActivity.this);
            setWillNotDraw(false);
            dimPaint.setColor(0x56000000);
            framePaint.setStyle(Paint.Style.STROKE);
            framePaint.setStrokeWidth(dp(1.2f));
            cornerPaint.setStyle(Paint.Style.STROKE);
            cornerPaint.setStrokeCap(Paint.Cap.ROUND);
            cornerPaint.setStrokeWidth(dp(4));
            setContentDescription("Adaptiver Kartenrahmen");
        }

        void setStable(boolean value, int color) {
            stable = value;
            accent = color;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float width = getWidth();
            float height = getHeight();
            float topReserve = dp(tabletLayout ? 86 : 128);
            float bottomReserve = dp(tabletLayout ? 92 : 148);
            float margin = dp(tabletLayout ? 26 : 14);
            float availableWidth = Math.max(1f, width - margin * 2f);
            float availableHeight = Math.max(1f, height - topReserve - bottomReserve - margin * 2f);
            float cardHeight = availableHeight;
            float cardWidth = cardHeight / 1.452f;
            if (cardWidth > availableWidth) {
                cardWidth = availableWidth;
                cardHeight = cardWidth * 1.452f;
            }
            float left = (width - cardWidth) / 2f;
            float top = topReserve + margin + Math.max(0f, (availableHeight - cardHeight) / 2f);
            frame.set(left, top, left + cardWidth, top + cardHeight);

            canvas.drawRect(0, 0, width, frame.top, dimPaint);
            canvas.drawRect(0, frame.bottom, width, height, dimPaint);
            canvas.drawRect(0, frame.top, frame.left, frame.bottom, dimPaint);
            canvas.drawRect(frame.right, frame.top, width, frame.bottom, dimPaint);

            framePaint.setColor(stable ? GREEN : 0xAAFFD45B);
            cornerPaint.setColor(stable ? GREEN : accent);
            canvas.drawRoundRect(frame, dp(22), dp(22), framePaint);
            float length = Math.min(frame.width(), frame.height()) * 0.12f;
            canvas.drawLine(frame.left, frame.top + length, frame.left, frame.top + dp(22), cornerPaint);
            canvas.drawLine(frame.left + dp(22), frame.top, frame.left + length, frame.top, cornerPaint);
            canvas.drawLine(frame.right - length, frame.top, frame.right - dp(22), frame.top, cornerPaint);
            canvas.drawLine(frame.right, frame.top + dp(22), frame.right, frame.top + length, cornerPaint);
            canvas.drawLine(frame.left, frame.bottom - length, frame.left, frame.bottom - dp(22), cornerPaint);
            canvas.drawLine(frame.left + dp(22), frame.bottom, frame.left + length, frame.bottom, cornerPaint);
            canvas.drawLine(frame.right - length, frame.bottom, frame.right - dp(22), frame.bottom, cornerPaint);
            canvas.drawLine(frame.right, frame.bottom - length, frame.right, frame.bottom - dp(22), cornerPaint);
        }
    }
}
