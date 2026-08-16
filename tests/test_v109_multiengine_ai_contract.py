# -*- coding: utf-8 -*-
"""Multi-Engine-KI-Vertrag für Just InCard v11.0."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run() -> None:
    from app_version import APP_VERSION, APP_BUILD, APP_DEVELOPER, APP_ADMIN
    from ai_ensemble_v109 import (
        ENGINE_STACK_V109,
        MODEL_ASSET_PATHS_V109,
        detect_script,
        engine_availability,
        rerank_scan_results_v109,
        semantic_fallback_similarity,
        stable_image_session_key,
    )
    from prepare_ai_models_v109 import CORE_ASSETS, EXTENDED_ASSETS

    assert APP_VERSION == "12.0.0"
    assert APP_BUILD == 1200
    assert APP_DEVELOPER == APP_ADMIN == "leenation"

    ids = {item["id"] for item in ENGINE_STACK_V109}
    assert {
        "yolo_card_detector",
        "mediapipe_object_detector",
        "paddleocr",
        "mlkit_ocr",
        "easyocr",
        "opencv_orb_akaze",
        "mobilenet_v3_embedder",
        "sentence_transformer",
    }.issubset(ids)

    assert detect_script("Dunkler Magier") == "latin"
    assert detect_script("ブラック・マジシャン") == "japanese"
    assert detect_script("블랙 매지션") == "korean"
    assert detect_script("黑魔导") == "chinese"
    assert detect_script("Тёмный маг") == "cyrillic"
    assert detect_script("الساحر الأسود") == "arabic"

    close_effect = "Wenn diese Karte beschworen wird, kannst du 1 Zauberkarte aus deinem Friedhof deiner Hand hinzufügen."
    damaged_ocr = "wenn dise karte beschworen wird kanst du zauberkare aus dem friedhof deiner hand hinzufugen"
    unrelated = "Zerstöre alle Monster auf dem Spielfeld und füge deinem Gegner 500 Schaden zu."
    assert semantic_fallback_similarity(close_effect, damaged_ocr) > semantic_fallback_similarity(close_effect, unrelated)

    ranked = rerank_scan_results_v109([
        {
            "card": {"id": 1, "name": "Falscher Name", "desc": unrelated},
            "candidate": {"kind": "Name", "value": "Dunkler Magier"},
            "exact": True,
            "name_similarity": 1.0,
            "artwork_similarity": 0.95,
            "metadata_score": 0.8,
            "source_id": "image-b",
        },
        {
            "card": {"id": 2, "name": "Richtige Karte", "desc": close_effect},
            "candidate": {"kind": "Set-Code", "value": "YGLD-DE002"},
            "exact": True,
            "metadata_score": 0.9,
            "artwork_similarity": 0.72,
            "source_id": "image-a",
        },
    ], ocr_text=damaged_ocr, quality={"score": 90})
    assert ranked[0]["card"]["id"] == 2
    assert ranked[0]["artwork_scope_v109"] == "image-a"
    assert ranked[1]["artwork_scope_v109"] == "image-b"

    key_a = stable_image_session_key(ROOT / "app_logo.png", 0, "batch")
    key_b = stable_image_session_key(ROOT / "app_logo.png", 1, "batch")
    assert key_a != key_b

    all_assets = {item["id"]: item for item in list(CORE_ASSETS) + list(EXTENDED_ASSETS)}
    assert all_assets["yolo_card_detector"]["path"].endswith(".onnx")
    assert all_assets["paddle_det"]["sha256"]
    assert all_assets["paddle_latin_rec"]["sha256"]
    assert all_assets["minilm_quantized"]["sha256"]
    assert MODEL_ASSET_PATHS_V109["minilm_vocab"].endswith(".vocab")
    assert isinstance(engine_availability(str(ROOT)), dict)

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    for fragment in (
        "android.add_src = android_src",
        "com.google.mediapipe:tasks-vision:0.10.35",
        "org.opencv:opencv:4.12.0",
        "com.microsoft.onnxruntime:onnxruntime-android:1.21.1",
        "vocab",
    ):
        assert fragment in spec, fragment

    java = (ROOT / "android_src/org/yugioh/kartenliste/NativeAiScanner.java").read_text(encoding="utf-8")
    for fragment in ("TextRecognition", "detectCardRegions", "compareOrb", "compareAkaze", "detectYoloCards", "OnnxTensor"):
        assert fragment in java, fragment

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "include_extended_ai_models" in workflow
    assert "prepare_ai_models_v109.py --extended" in workflow
    assert "tests/test_v109_multiengine_ai_contract.py" in workflow
    assert "just-incard-v1200-arm64-api35-ndk27c" in workflow

    manifest = json.loads((ROOT / "models/ai_models_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "12.0.0"
    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v12_0_0.txt"]
    print("v12.0.0 multi-engine AI scanner contract tests: OK")


if __name__ == "__main__":
    run()
