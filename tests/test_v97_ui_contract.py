# -*- coding: utf-8 -*-
"""Kivy-unabhängige Vertragsprüfung für die responsive v9.7-Oberfläche unter v10.0."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAIN = ROOT / "main.py"
WORKFLOW = ROOT / ".github" / "workflows" / "build-android-apk.yml"


def load_build_ui_profile():
    source = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "build_ui_profile")
    segment = ast.get_source_segment(source, node)

    class DummyWindow:
        width = 1080
        height = 2400

    from ui_v110 import cap_safe_insets as cap_safe_insets_v110
    from ui_v110 import make_layout_profile as make_layout_profile_v110
    namespace = {
        "Window": DummyWindow(),
        "make_layout_profile_v110": make_layout_profile_v110,
        "cap_safe_insets_v110": cap_safe_insets_v110,
    }
    exec(segment, namespace)
    return namespace["build_ui_profile"], source


def run():
    profile, source = load_build_ui_profile()

    compact = profile({"density": 3.0, "smallest_width_dp": 320, "font_scale": 1.4}, (900, 1800))
    assert compact["device_class"] == "compact_phone"
    assert compact["navigation_mode"] == "bottom"

    phone = profile({"density": 2.75, "smallest_width_dp": 393, "font_scale": 1.0}, (1080, 2340))
    assert phone["is_phone"] is True
    assert phone["navigation_mode"] == "bottom"

    tablet = profile({"density": 2.0, "smallest_width_dp": 800, "font_scale": 1.0}, (1600, 2560))
    assert tablet["is_tablet"] is True
    assert tablet["navigation_mode"] == "rail"

    tablet_split = profile({"density": 2.0, "smallest_width_dp": 800, "font_scale": 1.0}, (1100, 1800))
    assert tablet_split["is_tablet"] is True
    assert tablet_split["layout_mode"] == "tablet_compact"
    assert tablet_split["navigation_mode"] == "bottom"

    large_text = profile({"density": 3.0, "smallest_width_dp": 393, "font_scale": 1.8}, (1179, 2556))
    assert large_text["control_font_scale"] == 1.18
    assert large_text["body_font_scale"] == 1.42

    required = [
        "from app_version import APP_VERSION",
        "def open_unified_gallery_scan",
        "multiple=True",
        "class NavigationItem",
        "class ActionTile",
        "WindowInsets$Type",
        "self.tablet_dashboard",
        'source_menu_gallery_bubble',
        "Window.bind(on_keyboard=self._handle_android_back)",
        "def save_session_state",
        "def restore_session_state",
        "def import_backup_zip",
        "def open_cache_management_popup",
        "def open_accessibility_popup",
        "large_touch_targets",
        "wifi_only_images",
        "android_is_unmetered_network",
    ]
    for fragment in required:
        assert fragment in source, fragment

    assert 'text="X"' not in source
    assert 'text="×"' not in source
    assert "\x08" not in source

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "actions/checkout@v4", "actions/cache@v4", "actions/upload-artifact@v4",
        "android debug", "android release", "apksigner", "zipalign",
        "JustInCard-v${APP_VERSION}-debug.apk", "release-test.apk",
    ):
        assert fragment in workflow, fragment

    assert (ROOT / "app_version.py").is_file()
    assert (ROOT / "features_v97.py").is_file()
    assert (ROOT / "ci" / "justincard-ci-test.keystore").is_file()

    print("v9.7 UI compatibility under v12.0.1: OK")


if __name__ == "__main__":
    run()
