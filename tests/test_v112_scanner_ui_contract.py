# -*- coding: utf-8 -*-
"""Regressionstest für Scanner-, Galerie-, UI- und Erststart-Änderungen in v11.2.3."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD
    from scanner_v100 import gallery_scan_profile
    from gallery_multiengine_v1091 import bbox_containment, suppress_nested_regions

    assert APP_VERSION == "11.2.3"
    assert APP_BUILD == 1123

    profile = gallery_scan_profile()
    assert profile["max_attempts"] == 3
    assert profile["color_ocr_variants"] == 12
    assert profile["max_languages"] >= 10
    assert profile["hard_timeout_seconds"] == 36.0

    # Innenkontur wird entfernt, zweite echte Karte bleibt erhalten.
    regions = suppress_nested_regions([
        {"bbox": (0, 0, 700, 1015), "detection_score": 0.86, "detector": "opencv-contour"},
        {"bbox": (70, 190, 630, 610), "detection_score": 0.72, "detector": "opencv-python"},
        {"bbox": (760, 0, 1460, 1015), "detection_score": 0.84, "detector": "opencv-contour"},
    ])
    assert len(regions) == 2, regions
    assert bbox_containment((70, 190, 630, 610), (0, 0, 700, 1015)) > 0.95

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    for fragment in (
        'self.text_size = (available_w, available_h)',
        'def usable_content_width(',
        'def bind_adaptive_grid(',
        'raw_path', 'rectified_path', 'source_preview_path',
        'scan_region_raw_', 'scan_region_rectified_',
        'time.time_ns()',
        '_prepare_ocr_resolution_image',
        'self.ocr_scan_image(path, callback, deadline_at=deadline_at)',
        'float(best_similarity) < 0.74',
        'float(artwork_similarity) >= 0.78',
        'Build.MANUFACTURER', 'Build.MODEL',
        'Herzlich Willkommen',
        'first_launch_welcome_seen',
        'self.rail_status_card.height = 0',
        'scanner_fullscreen_layout',
        'auto_scan_result_panel',
        'bubble_source_menu',
        'source_menu_camera_bubble',
        'source_menu_gallery_bubble',
        'device_name = self.get_android_device_display_name()',
        'toggle_bubbles = getattr(self, "_toggle_scanner_source_bubbles", None)',
        'schedule_auto_scan(0.55)',
        'accept_current_result',
        'reject_current_result',
    ):
        assert fragment in main, fragment

    native = (ROOT / "native_ai_bridge_v109.py").read_text(encoding="utf-8")
    assert 'if not os.environ.get("ANDROID_ARGUMENT")' not in native

    manifest = json.loads((ROOT / "models/ai_models_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "11.2.3"
    engines = {item.get("id") for item in manifest.get("engines", [])}
    for engine in {"mlkit_text", "opencv_orb_akaze", "yolo_card_detector", "paddleocr", "mobilenet_v3_embedder"}:
        assert engine in engines

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert re.search(r"^version\s*=\s*11\.2\.3\s*$", spec, re.M)
    assert "android.numeric_version = 1123" in spec

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "tests/test_v112_scanner_ui_contract.py" in workflow
    assert "just-incard-v1123-arm64-api35-ndk25b" in workflow
    assert "include_extended_ai_models" in workflow and "default: true" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_2_3.txt"], txt_files
    print("v11.2.3 scanner/UI/first-launch contract tests: OK")


if __name__ == "__main__":
    run()
