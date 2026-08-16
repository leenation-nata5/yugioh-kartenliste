# -*- coding: utf-8 -*-
"""Kivy-unabhängiger Scanner-/UI-/Workflow-Vertrag für Just InCard v11.0."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD
    from scanner_v100 import (
        GALLERY_SCAN_MODE,
        SCAN_MODE_PROFILES,
        SUPPORTED_IMAGE_EXTENSIONS,
        effect_search_terms,
        effect_similarity,
        gallery_scan_profile,
        scan_mode_profile,
    )

    assert APP_VERSION == "11.2.2"
    assert APP_BUILD == 1122

    assert GALLERY_SCAN_MODE == "gründlich"
    assert scan_mode_profile("schnell")["hard_timeout_seconds"] == 6.0
    assert scan_mode_profile("normal")["hard_timeout_seconds"] == 10.0
    gallery = gallery_scan_profile()
    assert gallery["hard_timeout_seconds"] == 36.0
    assert gallery["effect_matching"] is True
    assert gallery["color_ocr_variants"] >= 6
    assert gallery["multiple_cards"] is True
    assert SCAN_MODE_PROFILES["schnell"]["guided_variants"] < gallery["guided_variants"]

    for ext in (".jpg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".heic", ".heif", ".avif"):
        assert ext in SUPPORTED_IMAGE_EXTENSIONS

    ocr_effect = (
        "Während der End Phase, falls diese Karte in diesem Spielzug als Normal- oder "
        "Spezialbeschwörung beschworen wurde: Du kannst 1 Zauberkarte in deinem Friedhof "
        "wählen; füge sie deiner Hand hinzu."
    )
    correct_effect = ocr_effect + " Du kannst diesen Effekt nur einmal pro Spielzug verwenden."
    wrong_effect = "Falls diese Karte beschworen wird: Zerstöre alle Zauber- und Fallenkarten deines Gegners."
    assert effect_search_terms(ocr_effect)
    assert effect_similarity(ocr_effect, correct_effect) > 0.75
    assert effect_similarity(ocr_effect, correct_effect) > effect_similarity(ocr_effect, wrong_effect) + 0.25

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")

    required_fragments = (
        "def show_home_page",
        'self._current_section = "home"',
        "ScanTimingStoreV100",
        "ScanDeadlineV100",
        "hard_timeout_seconds",
        "_scan_local_candidate_cards",
        "_scan_network_candidate_cards",
        "_find_cached_artwork_fallback",
        "allow_download=False",
        'self.make_inline_page("scan_progress"',
        'self.make_inline_page("scan_review"',
        "Zeitbudget erreicht",
        "normalize_scanner_image_file",
        "detect_card_regions",
        "rectify_card_crop",
        "analyze_scan_image_quality",
        "parse_scan_ocr_candidates",
        "_build_gallery_color_ocr_variant_images",
        "effect_similarity",
        'kind == "Effect"',
        'self._gallery_scan_active = True',
        'config = self.scan_mode_config("gallery")',
        "open_collection_card_preview",
        'self.make_inline_page("collection_preview"',
        "scan_learning.remember",
        "scan_timings.record",
    )
    for fragment in required_fragments:
        assert fragment in main, fragment

    # Galerie besitzt keine Schnell-/Normal-Auswahl: sie startet immer mit Override.
    gallery_section = main[main.index("def start_bulk_gallery_ocr_import"):main.index("def show_bulk_gallery_review_popup")]
    assert 'self._gallery_scan_active = True' in gallery_section
    assert 'scan_mode_config("gallery")' in gallery_section
    assert '"scan_mode": GALLERY_SCAN_MODE' in gallery_section

    # Der Live-Scanner ist jetzt vollflächig, automatisch und blendet ein
    # Bubble-Menü sowie das Ergebnis-Overlay direkt im Kamerabild ein.
    scanner_ui = main[main.index("def open_camera_scanner"):main.index("def set_scan_mode")]
    for fragment in (
        'scanner_fullscreen_layout',
        'auto_scan_result_panel',
        'bubble_source_menu',
        'device_name = self.get_android_device_display_name()',
        'toggle_source_bubbles',
        '_toggle_scanner_source_bubbles',
        'schedule_auto_scan(0.55)',
        'accept_current_result',
        'reject_current_result',
    ):
        assert fragment in scanner_ui, fragment

    # Sammlung öffnet eine eigene Vorschau und nicht nur den Suchdetailbereich.
    collection_row = main[main.index("def create_collection_row"):main.index("def delete_card_by_id")]
    assert "open_collection_card_preview(card)" in collection_row

    # Scanner bleibt eigener Hauptscreen; die Suche enthält keinen Scan-Button.
    search_section = main[main.index("# Einfache Suche:"):main.index("# Ergebnisliste und Detailansicht")]
    assert "Bilder scannen" not in search_section
    assert "open_camera_scanner" not in search_section

    assert re.search(r"^version\s*=\s*11\.2\.2\s*$", spec, re.M)
    assert re.search(r"^android\.archs\s*=\s*arm64-v8a\s*$", spec, re.M)
    assert "android debug" in workflow
    assert "android release" in workflow
    assert "tests/test_v100_scanner_contract.py" in workflow
    assert "just-incard-v1122-arm64-api35-ndk25b" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_2_2.txt"], txt_files

    print("v11.2.2 gallery precision scanner/UI/workflow contract tests: OK")


if __name__ == "__main__":
    run()
