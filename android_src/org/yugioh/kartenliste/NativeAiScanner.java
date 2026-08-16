package org.yugioh.kartenliste;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.RectF;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions;
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import org.json.JSONArray;
import org.json.JSONObject;
import org.opencv.android.OpenCVLoader;
import org.opencv.android.Utils;
import org.opencv.core.Core;
import org.opencv.core.DMatch;
import org.opencv.core.KeyPoint;
import org.opencv.core.Mat;
import org.opencv.core.MatOfDMatch;
import org.opencv.core.MatOfKeyPoint;
import org.opencv.core.MatOfPoint;
import org.opencv.core.MatOfPoint2f;
import org.opencv.core.Point;
import org.opencv.core.Rect;
import org.opencv.core.Size;
import org.opencv.features2d.AKAZE;
import org.opencv.features2d.BFMatcher;
import org.opencv.features2d.ORB;
import org.opencv.imgproc.Imgproc;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;

import java.nio.FloatBuffer;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.io.File;
import java.io.FileInputStream;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Native, synchrone Android-KI-Brücke für Python/Pyjnius.
 * Aufrufe müssen aus einem Worker-Thread erfolgen, nicht aus dem UI-Thread.
 */
public final class NativeAiScanner {
    private NativeAiScanner() {}

    private static Bitmap loadBitmap(String path) {
        Bitmap bitmap = BitmapFactory.decodeFile(path);
        if (bitmap == null) {
            throw new IllegalArgumentException("Bild konnte nicht geladen werden: " + path);
        }
        return bitmap;
    }

    public static String statusJson() {
        JSONObject root = new JSONObject();
        JSONArray engines = new JSONArray();
        try {
            root.put("available", true);
            engines.put("mlkit");
            engines.put("opencv_orb");
            engines.put("opencv_akaze");
            engines.put("opencv_card_regions");
            engines.put("onnx_yolo");
            engines.put("mediapipe_object_detector_optional");
            engines.put("mobilenet_v3_embedder_optional");
            engines.put("paddleocr_onnx_optional");
            root.put("opencv", OpenCVLoader.initLocal());
            root.put("engines", engines);
        } catch (Exception ignored) {}
        return root.toString();
    }

    public static String ocrText(String path, String script) throws Exception {
        Bitmap bitmap = loadBitmap(path);
        InputImage image = InputImage.fromBitmap(bitmap, 0);
        String normalized = script == null ? "latin" : script.toLowerCase();
        TextRecognizer recognizer;
        switch (normalized) {
            case "chinese":
            case "zh":
                recognizer = TextRecognition.getClient(new ChineseTextRecognizerOptions.Builder().build());
                break;
            case "japanese":
            case "ja":
                recognizer = TextRecognition.getClient(new JapaneseTextRecognizerOptions.Builder().build());
                break;
            case "korean":
            case "ko":
                recognizer = TextRecognition.getClient(new KoreanTextRecognizerOptions.Builder().build());
                break;
            case "devanagari":
                recognizer = TextRecognition.getClient(new DevanagariTextRecognizerOptions.Builder().build());
                break;
            default:
                recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                break;
        }
        try {
            Text result = Tasks.await(recognizer.process(image), 18, TimeUnit.SECONDS);
            return result == null ? "" : result.getText();
        } finally {
            recognizer.close();
            bitmap.recycle();
        }
    }

    private static Mat grayFromPath(String path) {
        if (!OpenCVLoader.initLocal()) {
            throw new IllegalStateException("OpenCV konnte nicht geladen werden");
        }
        Bitmap bitmap = loadBitmap(path);
        Mat rgba = new Mat();
        Utils.bitmapToMat(bitmap, rgba);
        bitmap.recycle();
        Mat gray = new Mat();
        Imgproc.cvtColor(rgba, gray, Imgproc.COLOR_RGBA2GRAY);
        rgba.release();
        Imgproc.equalizeHist(gray, gray);
        return gray;
    }

    public static String detectCardRegions(String path) throws Exception {
        Mat gray = grayFromPath(path);
        Mat blurred = new Mat();
        Mat edges = new Mat();
        Imgproc.GaussianBlur(gray, blurred, new Size(5, 5), 0.0);
        Imgproc.Canny(blurred, edges, 55, 150);
        List<MatOfPoint> contours = new ArrayList<>();
        Mat hierarchy = new Mat();
        Imgproc.findContours(edges, contours, hierarchy, Imgproc.RETR_EXTERNAL, Imgproc.CHAIN_APPROX_SIMPLE);
        double imageArea = Math.max(1.0, gray.width() * gray.height());
        List<Rect> boxes = new ArrayList<>();
        for (MatOfPoint contour : contours) {
            double area = Imgproc.contourArea(contour);
            if (area < imageArea * 0.008 || area > imageArea * 0.98) continue;
            MatOfPoint2f curve = new MatOfPoint2f(contour.toArray());
            MatOfPoint2f approx = new MatOfPoint2f();
            double perimeter = Imgproc.arcLength(curve, true);
            Imgproc.approxPolyDP(curve, approx, Math.max(4.0, perimeter * 0.025), true);
            if (approx.total() >= 4 && approx.total() <= 8) {
                Rect rect = Imgproc.boundingRect(new MatOfPoint(approx.toArray()));
                double ratio = rect.width / Math.max(1.0, (double) rect.height);
                double portrait = ratio <= 1.0 ? ratio : 1.0 / ratio;
                if (portrait >= 0.55 && portrait <= 0.80) {
                    boxes.add(rect);
                }
            }
            curve.release();
            approx.release();
        }
        Collections.sort(boxes, (a, b) -> Double.compare(b.area(), a.area()));
        JSONArray out = new JSONArray();
        List<Rect> kept = new ArrayList<>();
        for (Rect rect : boxes) {
            boolean duplicate = false;
            for (Rect existing : kept) {
                if (iou(rect, existing) > 0.65) {
                    duplicate = true;
                    break;
                }
            }
            if (duplicate) continue;
            kept.add(rect);
            JSONObject item = new JSONObject();
            item.put("x", rect.x);
            item.put("y", rect.y);
            item.put("width", rect.width);
            item.put("height", rect.height);
            item.put("confidence", 0.58);
            item.put("engine", "opencv-contour");
            out.put(item);
            if (kept.size() >= 64) break;
        }
        gray.release(); blurred.release(); edges.release(); hierarchy.release();
        return out.toString();
    }

    private static double iou(Rect a, Rect b) {
        int x1 = Math.max(a.x, b.x);
        int y1 = Math.max(a.y, b.y);
        int x2 = Math.min(a.x + a.width, b.x + b.width);
        int y2 = Math.min(a.y + a.height, b.y + b.height);
        int inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
        double union = a.area() + b.area() - inter;
        return union <= 0 ? 0.0 : inter / union;
    }

    public static double compareOrb(String pathA, String pathB) {
        Mat a = null, b = null, da = new Mat(), db = new Mat();
        MatOfKeyPoint ka = new MatOfKeyPoint(), kb = new MatOfKeyPoint();
        try {
            a = grayFromPath(pathA); b = grayFromPath(pathB);
            ORB detector = ORB.create(1200);
            detector.detectAndCompute(a, new Mat(), ka, da);
            detector.detectAndCompute(b, new Mat(), kb, db);
            return descriptorSimilarity(da, db, ka.toArray().length, kb.toArray().length);
        } catch (Exception exc) {
            return 0.0;
        } finally {
            if (a != null) a.release(); if (b != null) b.release();
            da.release(); db.release(); ka.release(); kb.release();
        }
    }

    public static double compareAkaze(String pathA, String pathB) {
        Mat a = null, b = null, da = new Mat(), db = new Mat();
        MatOfKeyPoint ka = new MatOfKeyPoint(), kb = new MatOfKeyPoint();
        try {
            a = grayFromPath(pathA); b = grayFromPath(pathB);
            AKAZE detector = AKAZE.create();
            detector.detectAndCompute(a, new Mat(), ka, da);
            detector.detectAndCompute(b, new Mat(), kb, db);
            return descriptorSimilarity(da, db, ka.toArray().length, kb.toArray().length);
        } catch (Exception exc) {
            return 0.0;
        } finally {
            if (a != null) a.release(); if (b != null) b.release();
            da.release(); db.release(); ka.release(); kb.release();
        }
    }

    private static double descriptorSimilarity(Mat da, Mat db, int countA, int countB) {
        if (da.empty() || db.empty()) return 0.0;
        BFMatcher matcher = BFMatcher.create(Core.NORM_HAMMING, false);
        List<MatOfDMatch> knn = new ArrayList<>();
        matcher.knnMatch(da, db, knn, 2);
        int good = 0;
        for (MatOfDMatch pair : knn) {
            DMatch[] values = pair.toArray();
            if (values.length >= 2 && values[0].distance < values[1].distance * 0.76f) good++;
            pair.release();
        }
        double denominator = Math.max(10.0, Math.min(countA, countB));
        return Math.max(0.0, Math.min(1.0, good / denominator));
    }

    /** Standard-Ultralytics-ONNX-Ausgabe [1,C,N] oder [1,N,C]. */
    public static String detectYoloCards(String imagePath, String modelPath, double threshold) throws Exception {
        Bitmap original = loadBitmap(imagePath);
        final int inputSize = 640;
        Bitmap scaled = Bitmap.createScaledBitmap(original, inputSize, inputSize, true);
        FloatBuffer buffer = FloatBuffer.allocate(1 * 3 * inputSize * inputSize);
        int[] pixels = new int[inputSize * inputSize];
        scaled.getPixels(pixels, 0, inputSize, 0, 0, inputSize, inputSize);
        for (int c = 0; c < 3; c++) {
            for (int pixel : pixels) {
                int value = c == 0 ? ((pixel >> 16) & 0xff) : (c == 1 ? ((pixel >> 8) & 0xff) : (pixel & 0xff));
                buffer.put(value / 255.0f);
            }
        }
        buffer.rewind();
        OrtEnvironment env = OrtEnvironment.getEnvironment();
        try (OrtSession session = env.createSession(modelPath, new OrtSession.SessionOptions())) {
            String inputName = session.getInputNames().iterator().next();
            long[] shape = new long[]{1, 3, inputSize, inputSize};
            try (OnnxTensor tensor = OnnxTensor.createTensor(env, buffer, shape);
                 OrtSession.Result result = session.run(Collections.singletonMap(inputName, tensor))) {
                Object raw = result.get(0).getValue();
                if (!(raw instanceof float[][][])) return "[]";
                float[][][] output = (float[][][]) raw;
                float[][] matrix = output[0];
                boolean channelsFirst = matrix.length < matrix[0].length;
                int channels = channelsFirst ? matrix.length : matrix[0].length;
                int boxes = channelsFirst ? matrix[0].length : matrix.length;
                List<float[]> candidates = new ArrayList<>();
                for (int i = 0; i < boxes; i++) {
                    float cx = channelsFirst ? matrix[0][i] : matrix[i][0];
                    float cy = channelsFirst ? matrix[1][i] : matrix[i][1];
                    float w = channelsFirst ? matrix[2][i] : matrix[i][2];
                    float h = channelsFirst ? matrix[3][i] : matrix[i][3];
                    float score = 0f;
                    for (int c = 4; c < channels; c++) {
                        score = Math.max(score, channelsFirst ? matrix[c][i] : matrix[i][c]);
                    }
                    if (score >= threshold) candidates.add(new float[]{cx, cy, w, h, score});
                }
                candidates.sort((a, b) -> Float.compare(b[4], a[4]));
                JSONArray array = new JSONArray();
                List<Rect> kept = new ArrayList<>();
                for (float[] box : candidates) {
                    int x = Math.max(0, Math.round((box[0] - box[2] / 2f) / inputSize * original.getWidth()));
                    int y = Math.max(0, Math.round((box[1] - box[3] / 2f) / inputSize * original.getHeight()));
                    int w = Math.min(original.getWidth() - x, Math.round(box[2] / inputSize * original.getWidth()));
                    int h = Math.min(original.getHeight() - y, Math.round(box[3] / inputSize * original.getHeight()));
                    Rect rect = new Rect(x, y, Math.max(1, w), Math.max(1, h));
                    boolean duplicate = false;
                    for (Rect old : kept) if (iou(rect, old) > 0.45) { duplicate = true; break; }
                    if (duplicate) continue;
                    kept.add(rect);
                    JSONObject item = new JSONObject();
                    item.put("x", rect.x); item.put("y", rect.y);
                    item.put("width", rect.width); item.put("height", rect.height);
                    item.put("confidence", box[4]); item.put("engine", "yolo-onnx");
                    array.put(item);
                    if (kept.size() >= 64) break;
                }
                return array.toString();
            }
        } finally {
            scaled.recycle(); original.recycle();
        }
    }

    private static ByteBuffer directModelBuffer(String modelPath) throws Exception {
        File file = new File(modelPath);
        if (!file.isFile()) throw new IllegalArgumentException("Modell fehlt: " + modelPath);
        byte[] data = new byte[(int) file.length()];
        try (FileInputStream input = new FileInputStream(file)) {
            int offset = 0;
            while (offset < data.length) {
                int read = input.read(data, offset, data.length - offset);
                if (read < 0) break;
                offset += read;
            }
        }
        ByteBuffer buffer = ByteBuffer.allocateDirect(data.length).order(ByteOrder.nativeOrder());
        buffer.put(data);
        buffer.rewind();
        return buffer;
    }

    private static Method methodByNameAndCount(Class<?> cls, String name, int count) throws Exception {
        for (Method method : cls.getMethods()) {
            if (method.getName().equals(name) && method.getParameterTypes().length == count) return method;
        }
        throw new NoSuchMethodException(cls.getName() + "." + name + "/" + count);
    }

    /**
     * Optionaler MediaPipe Object Detector. Reflection hält den stabilen Build
     * unabhängig von kleineren API-Unterschieden der Tasks-Vision-Bibliothek.
     */
    public static String detectMediaPipeCards(String imagePath, String modelPath, double threshold) {
        JSONArray out = new JSONArray();
        Bitmap bitmap = null;
        Object detector = null;
        Object mpImage = null;
        try {
            bitmap = loadBitmap(imagePath);
            Class<?> baseOptionsClass = Class.forName("com.google.mediapipe.tasks.core.BaseOptions");
            Object baseBuilder = baseOptionsClass.getMethod("builder").invoke(null);
            methodByNameAndCount(baseBuilder.getClass(), "setModelAssetBuffer", 1).invoke(baseBuilder, directModelBuffer(modelPath));
            Object baseOptions = baseBuilder.getClass().getMethod("build").invoke(baseBuilder);

            Class<?> optionsClass = Class.forName("com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector$ObjectDetectorOptions");
            Object optionsBuilder = optionsClass.getMethod("builder").invoke(null);
            methodByNameAndCount(optionsBuilder.getClass(), "setBaseOptions", 1).invoke(optionsBuilder, baseOptions);
            try { methodByNameAndCount(optionsBuilder.getClass(), "setScoreThreshold", 1).invoke(optionsBuilder, (float) threshold); } catch (Exception ignored) {}
            try { methodByNameAndCount(optionsBuilder.getClass(), "setMaxResults", 1).invoke(optionsBuilder, 64); } catch (Exception ignored) {}
            Object options = optionsBuilder.getClass().getMethod("build").invoke(optionsBuilder);

            Class<?> bitmapBuilderClass = Class.forName("com.google.mediapipe.framework.image.BitmapImageBuilder");
            Object bitmapBuilder = bitmapBuilderClass.getConstructor(Bitmap.class).newInstance(bitmap);
            mpImage = bitmapBuilderClass.getMethod("build").invoke(bitmapBuilder);

            Class<?> detectorClass = Class.forName("com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector");
            Class<?> activityClass = Class.forName("org.kivy.android.PythonActivity");
            Object activity = activityClass.getField("mActivity").get(null);
            detector = methodByNameAndCount(detectorClass, "createFromOptions", 2).invoke(null, activity, options);
            Object result = methodByNameAndCount(detectorClass, "detect", 1).invoke(detector, mpImage);
            Object detectionsObject = methodByNameAndCount(result.getClass(), "detections", 0).invoke(result);
            if (detectionsObject instanceof List) {
                for (Object detection : (List<?>) detectionsObject) {
                    Object boxObject = methodByNameAndCount(detection.getClass(), "boundingBox", 0).invoke(detection);
                    if (!(boxObject instanceof RectF)) continue;
                    RectF box = (RectF) boxObject;
                    double score = threshold;
                    try {
                        Object categoriesObject = methodByNameAndCount(detection.getClass(), "categories", 0).invoke(detection);
                        if (categoriesObject instanceof List && !((List<?>) categoriesObject).isEmpty()) {
                            Object category = ((List<?>) categoriesObject).get(0);
                            Object scoreObject = methodByNameAndCount(category.getClass(), "score", 0).invoke(category);
                            if (scoreObject instanceof Number) score = ((Number) scoreObject).doubleValue();
                        }
                    } catch (Exception ignored) {}
                    if (score < threshold) continue;
                    JSONObject item = new JSONObject();
                    item.put("x", Math.max(0, Math.round(box.left)));
                    item.put("y", Math.max(0, Math.round(box.top)));
                    item.put("width", Math.max(1, Math.round(box.width())));
                    item.put("height", Math.max(1, Math.round(box.height())));
                    item.put("confidence", score);
                    item.put("engine", "mediapipe-object-detector");
                    out.put(item);
                    if (out.length() >= 64) break;
                }
            }
        } catch (Exception ignored) {
            return "[]";
        } finally {
            try { if (detector != null) methodByNameAndCount(detector.getClass(), "close", 0).invoke(detector); } catch (Exception ignored) {}
            try { if (mpImage != null) methodByNameAndCount(mpImage.getClass(), "close", 0).invoke(mpImage); } catch (Exception ignored) {}
            if (bitmap != null) bitmap.recycle();
        }
        return out.toString();
    }

    private static float[] mediaPipeEmbedding(String imagePath, String modelPath) throws Exception {
        Bitmap bitmap = loadBitmap(imagePath);
        Object embedder = null;
        Object mpImage = null;
        try {
            Class<?> baseOptionsClass = Class.forName("com.google.mediapipe.tasks.core.BaseOptions");
            Object baseBuilder = baseOptionsClass.getMethod("builder").invoke(null);
            methodByNameAndCount(baseBuilder.getClass(), "setModelAssetBuffer", 1).invoke(baseBuilder, directModelBuffer(modelPath));
            Object baseOptions = baseBuilder.getClass().getMethod("build").invoke(baseBuilder);
            Class<?> optionsClass = Class.forName("com.google.mediapipe.tasks.vision.imageembedder.ImageEmbedder$ImageEmbedderOptions");
            Object optionsBuilder = optionsClass.getMethod("builder").invoke(null);
            methodByNameAndCount(optionsBuilder.getClass(), "setBaseOptions", 1).invoke(optionsBuilder, baseOptions);
            Object options = optionsBuilder.getClass().getMethod("build").invoke(optionsBuilder);
            Class<?> bitmapBuilderClass = Class.forName("com.google.mediapipe.framework.image.BitmapImageBuilder");
            Object bitmapBuilder = bitmapBuilderClass.getConstructor(Bitmap.class).newInstance(bitmap);
            mpImage = bitmapBuilderClass.getMethod("build").invoke(bitmapBuilder);
            Class<?> embedderClass = Class.forName("com.google.mediapipe.tasks.vision.imageembedder.ImageEmbedder");
            Class<?> activityClass = Class.forName("org.kivy.android.PythonActivity");
            Object activity = activityClass.getField("mActivity").get(null);
            embedder = methodByNameAndCount(embedderClass, "createFromOptions", 2).invoke(null, activity, options);
            Object result = methodByNameAndCount(embedderClass, "embed", 1).invoke(embedder, mpImage);
            Object embeddingResult = methodByNameAndCount(result.getClass(), "embeddingResult", 0).invoke(result);
            Object embeddingsObject = methodByNameAndCount(embeddingResult.getClass(), "embeddings", 0).invoke(embeddingResult);
            if (!(embeddingsObject instanceof List) || ((List<?>) embeddingsObject).isEmpty()) return new float[0];
            Object embedding = ((List<?>) embeddingsObject).get(0);
            Object floatEmbedding = methodByNameAndCount(embedding.getClass(), "floatEmbedding", 0).invoke(embedding);
            if (floatEmbedding instanceof float[]) return (float[]) floatEmbedding;
            if (floatEmbedding instanceof List) {
                List<?> values = (List<?>) floatEmbedding;
                float[] out = new float[values.size()];
                for (int i = 0; i < values.size(); i++) out[i] = ((Number) values.get(i)).floatValue();
                return out;
            }
            return new float[0];
        } finally {
            try { if (embedder != null) methodByNameAndCount(embedder.getClass(), "close", 0).invoke(embedder); } catch (Exception ignored) {}
            try { if (mpImage != null) methodByNameAndCount(mpImage.getClass(), "close", 0).invoke(mpImage); } catch (Exception ignored) {}
            bitmap.recycle();
        }
    }

    public static double compareMobileNet(String pathA, String pathB, String modelPath) {
        try {
            float[] a = mediaPipeEmbedding(pathA, modelPath);
            float[] b = mediaPipeEmbedding(pathB, modelPath);
            if (a.length == 0 || a.length != b.length) return 0.0;
            double dot = 0.0, na = 0.0, nb = 0.0;
            for (int i = 0; i < a.length; i++) {
                dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i];
            }
            if (na <= 0 || nb <= 0) return 0.0;
            return Math.max(0.0, Math.min(1.0, dot / (Math.sqrt(na) * Math.sqrt(nb))));
        } catch (Exception ignored) {
            return 0.0;
        }
    }

    /**
     * PaddleOCR bleibt optional. Die eigentliche PP-OCRv5-Ausführung wird über
     * das Python-/ONNX-Modellpaket oder eine spätere native Modellpipeline
     * bereitgestellt. Ein leeres Ergebnis aktiviert automatisch ML Kit/EasyOCR.
     */
    public static String paddleOcrText(String imagePath, String detModel, String recModel, String dictPath) {
        return "";
    }

}
