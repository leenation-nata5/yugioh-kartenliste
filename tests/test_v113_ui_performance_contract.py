# -*- coding: utf-8 -*-
"""Responsive-/Stabilitätsvertrag für Just InCard v12.0.0."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_version import APP_BUILD, APP_VERSION  # noqa: E402
from ui_v110 import cap_safe_insets, rects_overlap, scanner_control_layout  # noqa: E402


def inside(rect, bounds, tolerance=1e-6):
    x, y, width, height = rect
    bx, by, bwidth, bheight = bounds
    return (
        x >= bx - tolerance
        and y >= by - tolerance
        and x + width <= bx + bwidth + tolerance
        and y + height <= by + bheight + tolerance
    )


def run() -> None:
    assert APP_VERSION == "12.0.0"
    assert APP_BUILD == 1200

    devices = [
        ("tiny_split_square", 240, 240, False),
        ("tiny_split_portrait", 280, 360, False),
        ("tiny_split_landscape", 360, 240, False),
        ("small_phone", 320, 568, False),
        ("xiaomi_tall_phone", 342, 745, False),
        ("modern_phone", 393, 873, False),
        ("large_phone", 480, 800, False),
        ("phone_landscape", 873, 393, False),
        ("tablet_split", 540, 720, True),
        ("small_tablet", 600, 960, True),
        ("tablet_portrait", 800, 1280, True),
        ("tablet_landscape", 1280, 800, True),
        ("large_tablet", 1600, 2560, True),
    ]
    for name, width, height, tablet in devices:
        layout = scanner_control_layout(width, height, is_tablet=tablet)
        viewport = (0.0, 0.0, float(width), float(height))
        source = layout["source_rect"]
        status = layout["status_rect"]
        device = layout["device_rect"]
        stage = layout["stage_rect"]
        assert inside(source, viewport), name
        assert inside(status, viewport), name
        assert inside(device, viewport), name
        assert inside(stage, viewport), name
        assert not rects_overlap(source, status), name
        assert not rects_overlap(source, device), name
        assert not rects_overlap(status, device), name
        assert layout["control_height_dp"] >= 48
        menu_rects = list(layout["menu_rects"])
        assert len(menu_rects) == 4
        assert all(inside(rect, stage) for rect in menu_rects), name
        for index, first in enumerate(menu_rects):
            for second in menu_rects[index + 1:]:
                assert not rects_overlap(first, second), name
        assert inside(layout["result_rect"], stage), name

    capped = cap_safe_insets(
        1080,
        2400,
        3.0,
        {"left": 500, "top": 900, "right": 500, "bottom": 1200},
    )
    assert capped["left"] <= 144
    assert capped["right"] <= 144
    assert capped["top"] <= 168
    assert capped["bottom"] <= 216

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    scanner = main.split("    def open_camera_scanner", 1)[1].split("    def set_scan_mode", 1)[0]
    required_scanner = (
        "scanner_header_primary",
        "scanner_stage = FloatLayout",
        "result_anchor = AnchorLayout",
        "source_menu_scrim",
        "source_menu_stack",
        'menu_mode == "grid"',
        "set_source_launcher_visible",
        "_scanner_source_menu_is_open",
        "scan_live_latest.png",
        "scan_frame_latest.png",
        "quality_worker",
        "toggle_source_bubbles(False)",
    )
    for fragment in required_scanner:
        assert fragment in scanner, fragment
    assert 'pos_hint={"right": 0.98' not in scanner
    assert 'pos_hint={"x": 0.02' not in scanner
    assert "self.opacity = min(current, 0.46)" in main

    required_performance = (
        "_ui_profile_signature",
        "_collection_save_generation",
        "Clock.schedule_once(begin_persist, 0.35)",
        "def _persist_collection_snapshot",
        "def _persist_deck_snapshot",
        "batch_size =",
        "def render_batch(index=0)",
        "collection_page_state",
        "def _refresh_current_responsive_page",
        "responsive_callback=refresh_favorites",
        "responsive_callback=lambda: render_collection",
        "self.save_collection(show_popup=False, immediate=True)",
        "self.save_decks(immediate=True)",
    )
    for fragment in required_performance:
        assert fragment in main, fragment

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert "tests/test_v113_ui_performance_contract.py" in workflow
    assert "just-incard-v1200-arm64-api35-ndk27c" in workflow
    assert "version = 12.0.0" in spec
    assert "android.numeric_version = 1200" in spec
    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v12_0_0.txt"]
    print("v12.0.0 responsive UI, scanner overlay and performance contracts: OK")


if __name__ == "__main__":
    run()
