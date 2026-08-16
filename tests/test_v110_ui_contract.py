# -*- coding: utf-8 -*-
"""Statischer UI-/Scanner-Vertrag für Just InCard v11.0."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run() -> None:
    from app_version import APP_BUILD, APP_VERSION

    assert APP_VERSION == "11.2.2"
    assert APP_BUILD == 1122

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    ui = (ROOT / "ui_v110.py").read_text(encoding="utf-8")
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")

    required_main = (
        "class ModernChip",
        "class EmptyStateCard",
        "class ScannerSourceTile",
        "def apply_runtime_layout_guard_v110",
        "card_frame_geometry_v110",
        "cover_geometry_v110",
        'live_frame_ref["widget"] = camera_clip',
        'fit_mode = "cover"',
        'self._current_section = "home"',
        'scanner_fullscreen_layout',
        'auto_scan_result_panel',
        'bubble_source_menu',
        'device_chip_label',
        'toggle_source_bubbles',
        'source_menu_camera_bubble',
        'source_menu_gallery_bubble',
        'go_scanner',
    )
    for fragment in required_main:
        assert fragment in main, fragment

    required_ui = (
        "class LayoutProfileV110",
        "def make_layout_profile",
        "def card_frame_geometry",
        "def cover_geometry",
        "def scanner_stage_height",
        "def audit_profile",
    )
    for fragment in required_ui:
        assert fragment in ui, fragment

    assert "max_content_dp = 480.0" not in main
    assert "height=dp(214 if compact else" not in main
    assert "height=dp(224 if compact else 176)" not in main
    assert "source_card.height = dp(230 if current_source_cols == 1 else 118)" not in main
    assert "row_default_height=dp(48)" in main
    assert re.search(r"^version\s*=\s*11\.2\.2\s*$", spec, re.M)
    assert "android.numeric_version = 1122" in spec
    assert "just-incard-v1122-arm64-api35-ndk25b" in workflow
    assert "tests/test_v110_responsive_contract.py" in workflow
    assert "tests/test_v110_ui_contract.py" in workflow
    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v11_2_2.txt"]
    print("v11.2.2 modern responsive UI/scanner contract tests: OK")


if __name__ == "__main__":
    run()
