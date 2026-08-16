# -*- coding: utf-8 -*-
"""Vertrag für den vollständig isolierten Galerie-Sammelscan in v10.8."""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD
    from ai_scanner_v102 import build_preview_records

    assert APP_VERSION == "11.2.1"
    assert APP_BUILD == 1121

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "same.jpg"
        source.write_bytes(b"not-a-real-image-but-copyable")
        records = build_preview_records([str(source), str(source)], str(root / "previews"), batch_id="batch-test")
        assert len(records) == 2
        assert records[0]["source_id"] != records[1]["source_id"]
        assert records[0]["preview_path"] != records[1]["preview_path"]
        assert Path(records[0]["preview_path"]).exists()
        assert Path(records[1]["preview_path"]).exists()

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    required = (
        "build_preview_records",
        "source_records = build_preview_records",
        "isolated_result_payload",
        "isolated_error_payload",
        "_isolated_scan_match_acceptance",
        '"source_id": source_id',
        '"source_index": source_index',
        'results = grouped_results',
        "Keine Gruppierung über verschiedene Bildquellen mehr",
        "matched_artwork_preview",
        "live_frame_ref[\"widget\"] = camera_clip",
        "scanner_fullscreen_layout",
        "max_items=250",
        "time.time_ns()",
        "float(best_similarity) < 0.74",
        "if similarity >= 0.58",
    )
    for fragment in required:
        assert fragment in main, fragment

    review_start = main.index("def show_bulk_gallery_review_popup")
    review_end = main.index("def open_manual_scan_assignment", review_start)
    review = main[review_start:review_end]
    assert "grouped_by_key" not in review
    assert 'item["duplicate_count"]' in review
    assert 'source=get_image_url(card)' in review

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "tests/test_v107_isolated_gallery_contract.py" in workflow
    assert "just-incard-v1121-arm64-api35-ndk25b" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_2_1.txt"], txt_files

    print("v11.2.1 isolated gallery scan contract tests: OK")


if __name__ == "__main__":
    run()
