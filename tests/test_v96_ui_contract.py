# -*- coding: utf-8 -*-
"""Kompatibilitätsprüfung: Die responsive v9.6-Oberfläche bleibt in v10.0.2 erhalten."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAIN = ROOT / "main.py"
FEATURES = ROOT / "features_v93.py"


def load_build_ui_profile():
    source = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "build_ui_profile")
    segment = ast.get_source_segment(source, node)

    class DummyWindow:
        width = 1080
        height = 2400

    from ui_v110 import make_layout_profile as make_layout_profile_v110
    namespace = {"Window": DummyWindow(), "make_layout_profile_v110": make_layout_profile_v110}
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

    tablet_landscape = profile({"density": 2.0, "smallest_width_dp": 800, "font_scale": 1.0}, (2560, 1600))
    assert tablet_landscape["layout_mode"] == "tablet_desktop"

    # Ein echtes Tablet muss im schmalen Split-Screen die kompakte Bottom-Navigation
    # verwenden, statt eine zu breite Seitenleiste in das Fenster zu quetschen.
    tablet_split = profile({"density": 2.0, "smallest_width_dp": 800, "font_scale": 1.0}, (1100, 1800))
    assert tablet_split["is_tablet"] is True
    assert tablet_split["layout_mode"] == "tablet_compact"
    assert tablet_split["navigation_mode"] == "bottom"

    # Große Android-Systemschrift darf Buttons nicht unkontrolliert vergrößern;
    # Fließtext bleibt dennoch stärker skalierbar und in ScrollViews lesbar.
    large_text = profile({"density": 3.0, "smallest_width_dp": 393, "font_scale": 1.8}, (1179, 2556))
    assert large_text["font_scale"] == 1.8
    assert large_text["control_font_scale"] == 1.18
    assert large_text["body_font_scale"] == 1.42

    # Hersteller können fehlerhafte Insets melden. Das Profil begrenzt sie auf
    # sichere Anteile der aktuellen App-Fenstergröße.
    insets = profile({
        "density": 3.0,
        "smallest_width_dp": 393,
        "inset_left_px": 9999,
        "inset_top_px": 9999,
        "inset_right_px": 9999,
        "inset_bottom_px": 9999,
    }, (1080, 2400))
    assert insets["safe"]["left"] <= 1080 * 0.12
    assert insets["safe"]["right"] <= 1080 * 0.12
    assert insets["safe"]["top"] <= 2400 * 0.12
    assert insets["safe"]["bottom"] <= 2400 * 0.16

    required = [
        'from app_version import APP_VERSION',
        'def open_unified_gallery_scan',
        'multiple=True',
        'class NavigationItem',
        'class ActionTile',
        'def _normalize_grid_heights',
        'WindowInsets$Type',
        'self.tablet_dashboard',
        'self.middle.orientation = "vertical"',
        'self.middle.orientation = "horizontal"',
        'source_menu_gallery_bubble',
        'ui_asset("app_mark")',
        'Window.bind(on_keyboard=self._handle_android_back)',
        'runner = DiagnosticsRunnerV93(os.path.dirname(os.path.abspath(__file__))',
    ]
    for fragment in required:
        assert fragment in source, fragment

    assert 'text="X"' not in source
    assert 'text="×"' not in source
    assert "\x08" not in source

    features_source = FEATURES.read_text(encoding="utf-8")
    assert 'required = ["main.py"' not in features_source
    assert 'importlib.util.find_spec' in features_source
    assert 'Android-Zertifikat-Fallback aktiv' in features_source

    required_icons = {
        "app_mark", "home", "search", "scan", "cards", "collection", "decks",
        "more", "settings", "camera", "gallery", "ocr", "history", "database",
        "sync", "web", "theme", "performance", "help", "diagnostics", "export", "custom",
    }
    available_icons = {path.stem for path in (ROOT / "assets" / "ui").glob("*.png")}
    assert required_icons <= available_icons, sorted(required_icons - available_icons)
    assert (ROOT / "docs" / "ui_mockup_v96.png").is_file()

    print("v9.6 UI compatibility under v11.2.2: OK")


if __name__ == "__main__":
    run()
