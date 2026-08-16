# -*- coding: utf-8 -*-
"""Galerie-Multi-Engine-Vertrag für Just InCard v11.0."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD
    from gallery_multiengine_v1091 import (
        GALLERY_MULTI_ENGINE_PLAN_V1093,
        fuse_region_detections,
        merge_ocr_engine_outputs,
        stable_region_session_id,
    )

    assert APP_VERSION == "11.3.0"
    assert APP_BUILD == 1130
    assert len(GALLERY_MULTI_ENGINE_PLAN_V1093) == 8
    for name in (
        "YOLOv8/YOLO11 Nano", "Google MediaPipe", "Google ML Kit Vision OCR",
        "PaddleOCR", "EasyOCR", "OpenCV ORB/AKAZE", "MobileNetV3",
        "Sentence-Transformers MiniLM",
    ):
        assert name in GALLERY_MULTI_ENGINE_PLAN_V1093

    detections = [
        {"x": 10, "y": 10, "width": 100, "height": 145, "confidence": 0.91, "engine": "yolo-onnx"},
        {"x": 13, "y": 12, "width": 98, "height": 143, "confidence": 0.82, "engine": "mediapipe-object-detector"},
        {"x": 220, "y": 10, "width": 100, "height": 145, "confidence": 0.76, "engine": "opencv-contour"},
    ]
    fused = fuse_region_detections(detections, image_width=400, image_height=240, max_cards=64)
    assert len(fused) == 2, fused
    consensus = next(item for item in fused if item["detector_consensus"] >= 2)
    assert "yolo-onnx" in consensus["detectors"]
    assert "mediapipe-object-detector" in consensus["detectors"]
    assert sorted(item["index"] for item in fused) == [1, 2]

    merged = merge_ocr_engine_outputs([
        {"engine": "mlkit_latin", "text": "LOB-DE001\nBlauäugiger w. Drache"},
        {"engine": "paddleocr", "text": "LOB-DE001\nBlauäugiger w. Drache"},
        {"engine": "easyocr", "text": "ATK 3000 DEF 2500"},
    ])
    assert "LOB-DE001" in merged["text"]
    assert "ATK 3000 DEF 2500" in merged["text"]
    assert set(merged["engines"]) == {"mlkit_latin", "paddleocr", "easyocr"}
    set_line = next(item for item in merged["lines"] if item["text"] == "LOB-DE001")
    assert len(set_line["engines"]) == 2

    a = stable_region_session_id("source-a", (1, 2, 100, 145), 1)
    b = stable_region_session_id("source-a", (1, 2, 100, 145), 1)
    c = stable_region_session_id("source-b", (1, 2, 100, 145), 1)
    assert a == b and a != c

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    for fragment in (
        "gallery_multi_engine_ocr_v1093",
        "fuse_region_detections",
        "native_mediapipe_regions",
        "native_mobilenet_similarity",
        "max_cards=64",
        "region_session_id",
        "YOLO/MediaPipe/OpenCV + ML Kit/Paddle/EasyOCR",
    ):
        assert fragment in main, fragment

    java = (ROOT / "android_src/org/yugioh/kartenliste/NativeAiScanner.java").read_text(encoding="utf-8")
    for fragment in ("detectMediaPipeCards", "compareMobileNet", "paddleOcrText"):
        assert fragment in java, fragment

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "tests/test_v1091_gallery_multiengine_contract.py" in workflow
    assert "just-incard-v1130-arm64-api35-ndk25b" in workflow

    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v11_3_0.txt"]
    print("v11.3.0 gallery multi-engine contract tests: OK")


if __name__ == "__main__":
    run()
