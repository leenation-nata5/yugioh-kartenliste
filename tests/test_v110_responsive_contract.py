# -*- coding: utf-8 -*-
"""Kivy-unabhängige Responsive-Matrix für Just InCard v11.0."""
from __future__ import annotations

from math import isclose
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_v110 import (  # noqa: E402
    CARD_ASPECT,
    audit_profile,
    card_frame_geometry,
    cover_geometry,
    grid_height,
    make_layout_profile,
    scanner_stage_height,
    text_sp,
)


def run() -> None:
    devices = [
        ("small_phone", 320, 568, 320, 1.00),
        ("small_phone_large_text", 360, 640, 360, 1.30),
        ("modern_phone", 393, 873, 393, 1.00),
        ("modern_phone_max_text", 412, 915, 412, 2.00),
        ("large_phone", 480, 800, 480, 1.40),
        ("small_tablet", 600, 960, 600, 1.00),
        ("tablet_portrait", 800, 1280, 800, 1.25),
        ("tablet_landscape", 1280, 800, 800, 1.00),
        ("large_tablet", 1600, 2560, 1000, 1.00),
        ("tablet_split_window", 540, 720, 800, 1.30),
        ("phone_landscape", 873, 393, 393, 1.15),
    ]

    report = []
    for name, width, height, smallest, font_scale in devices:
        profile = make_layout_profile(
            width,
            height,
            smallest_width_dp=smallest,
            font_scale=font_scale,
        ).as_dict()
        problems = list(audit_profile(profile))
        assert not problems, (name, problems)
        assert profile["touch_dp"] >= 48
        assert 1 <= profile["search_columns"] <= 3
        assert profile["content_columns"] in (1, 2)
        assert profile["result_columns"] in (1, 2)
        assert profile["navigation_mode"] in ("bottom", "rail")
        if profile["navigation_mode"] == "rail":
            assert width >= 720
            assert profile["is_tablet"] is True
        if width < 600:
            assert profile["search_columns"] == 1
        assert text_sp("body", profile) >= 9
        assert text_sp("display", profile) > text_sp("body", profile)

        x, y, card_w, card_h = card_frame_geometry(width, max(260, height * 0.56))
        viewport_h = max(260, height * 0.56)
        assert x >= 0 and y >= 0
        assert x + card_w <= width + 1e-6
        assert y + card_h <= viewport_h + 1e-6
        assert isclose(card_h / card_w, CARD_ASPECT, rel_tol=0.002)

        stage = scanner_stage_height(profile, height * 0.68)
        assert stage >= 260
        assert stage <= max(720, height * 0.68)

        report.append({
            "name": name,
            "profile": profile,
            "scanner_stage_dp": round(stage, 2),
            "card_frame": [round(v, 2) for v in (x, y, card_w, card_h)],
        })

    # Cover-Fit muss den Zielrahmen ohne Verzerrung vollständig bedecken.
    for source in ((640, 480), (1920, 1080), (1080, 1920), (4032, 3024)):
        for target in ((260, 377), (420, 609), (700, 1015), (1000, 500)):
            for rotated in (False, True):
                x, y, width, height = cover_geometry(*source, *target, rotated=rotated)
                assert width + 1e-6 >= target[0]
                assert height + 1e-6 >= target[1]
                assert isclose(x, (target[0] - width) / 2.0, abs_tol=1e-6)
                assert isclose(y, (target[1] - height) / 2.0, abs_tol=1e-6)

    assert grid_height(0, 2, 48, 8) == 0
    assert grid_height(5, 2, 48, 8) == 160

    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    (logs / "ui_v110_matrix_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"v11.2 responsive matrix: {len(devices)} device profiles OK")


if __name__ == "__main__":
    run()
