# -*- coding: utf-8 -*-
"""Fuzz responsive geometry across phones, tablets, foldables and freeform windows."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_v120 import adaptive_chrome, audit_overlay, scanner_overlay_layout, source_menu_geometry, virtual_window


def overlaps(a, b, tolerance=0.5) -> bool:
    ax, ay, aw, ah = map(float, a)
    bx, by, bw, bh = map(float, b)
    return not (
        ax + aw <= bx + tolerance or bx + bw <= ax + tolerance
        or ay + ah <= by + tolerance or by + bh <= ay + tolerance
    )


def run() -> None:
    profiles = 0
    heights = (240, 280, 320, 360, 480, 540, 640, 720, 800, 915, 1024, 1280, 1536, 2000)
    for width in range(240, 2001, 11):
        for height in heights:
            for tablet in (False, True):
                for result_visible in (False, True):
                    layout = scanner_overlay_layout(
                        width,
                        height,
                        is_tablet=tablet,
                        result_visible=result_visible,
                    )
                    assert list(audit_overlay(layout, width, height)) == [], (width, height, layout)
                    assert not overlaps(layout["status"], layout["device"]), (width, height, layout)
                    frame = layout["frame"]
                    assert abs((frame[3] / frame[2]) - 1.452) < 0.002
                    if result_visible:
                        assert layout["result"][1] + layout["result"][3] <= min(
                            layout["status"][1], layout["device"][1]
                        ) + 0.5
                    menu = source_menu_geometry(width, height, is_tablet=tablet)
                    assert menu["width_dp"] + menu["pad_dp"] * 2 <= width + 0.5
                    assert menu["height_dp"] + menu["pad_dp"] * 2 <= height + 0.5
                    assert menu["bubble_width_dp"] >= adaptive_chrome(width, height, is_tablet=tablet).touch_target_dp
                    profiles += 1

    assert adaptive_chrome(359, 800).window_class == "narrow"
    assert adaptive_chrome(360, 800).window_class == "compact"
    assert adaptive_chrome(600, 900, is_tablet=True).navigation == "bottom"
    assert adaptive_chrome(720, 900, is_tablet=True).navigation == "rail"
    assert adaptive_chrome(720, 900, is_tablet=True, reduce_motion=True).motion_budget_ms == 0
    assert adaptive_chrome(410, 900).touch_target_dp >= 48

    for total in (0, 1, 10, 50, 1_000_000):
        for fraction in (0.0, 0.1, 0.5, 0.9, 1.0):
            start, end = virtual_window(total, fraction, 12, overscan=4)
            assert 0 <= start <= end <= total
            assert end - start <= 20 or total <= 20

    from PIL import Image
    asset = ROOT / "assets/ui/scanner_surface_v120.webp"
    with Image.open(asset) as image:
        image.verify()
    with Image.open(asset) as image:
        assert image.width >= 768 and image.height >= 1024

    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    for fragment in (
        "source_menu_live_bubble = ScannerSourceTile",
        "source_menu_camera_bubble = ScannerSourceTile",
        "source_menu_gallery_bubble = ScannerSourceTile",
        "bubble_source_menu = ScannerSourceTile",
        "source_menu_geometry_v120",
        'source_menu_scrim.bind(on_release=lambda *_: toggle_source_bubbles(False))',
    ):
        assert fragment in main_source, fragment

    assert profiles > 8_000
    print(f"v12.0.0 responsive fuzz matrix: {profiles} viewport states OK")


if __name__ == "__main__":
    run()
