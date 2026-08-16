# -*- coding: utf-8 -*-
"""Adaptive v12 design primitives for Just InCard.

This module deliberately has no Kivy dependency.  All breakpoints and scanner
geometry can therefore be fuzz-tested on CI for phones, tablets, foldables,
multi-window and both orientations before the Android UI is started.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import floor
from typing import Dict, Iterable, Mapping, Tuple


CARD_ASPECT = 1.452


def clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


@dataclass(frozen=True)
class AdaptiveChromeV120:
    width_dp: float
    height_dp: float
    window_class: str
    navigation: str
    nav_extent_dp: float
    safe_margin_dp: float
    content_gap_dp: float
    scanner_header_mode: str
    source_menu_mode: str
    result_mode: str
    result_width_dp: float
    touch_target_dp: float
    motion_budget_ms: int
    image_decode_edge_px: int

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def adaptive_chrome(
    width_dp: float,
    height_dp: float,
    *,
    is_tablet: bool = False,
    reduce_motion: bool = False,
) -> AdaptiveChromeV120:
    """Return visual chrome values from *available window size*, never device name.

    Android may resize an activity for split screen, a foldable hinge or a freeform
    window.  Consequently the current width is the single source of truth for the
    navigation and overlay layout, while ``is_tablet`` only influences comfortable
    maximum sizes.
    """
    width = max(240.0, float(width_dp or 0))
    height = max(240.0, float(height_dp or 0))
    landscape = width > height
    if width < 360:
        window_class = "narrow"
    elif width < 600:
        window_class = "compact"
    elif width < 840:
        window_class = "medium"
    elif width < 1200:
        window_class = "expanded"
    else:
        window_class = "large"

    navigation = "rail" if width >= 720 and (is_tablet or landscape) else "bottom"
    nav_extent = 84.0 if navigation == "rail" else 72.0
    safe_margin = 8.0 if window_class == "narrow" else (12.0 if width < 600 else 16.0)
    gap = 8.0 if width < 600 else 12.0
    touch = 52.0 if width < 600 else 56.0

    if width < 390:
        header = "stacked"
    elif width < 720:
        header = "compact_overlay"
    else:
        header = "floating_overlay"

    if width < 420:
        source_menu = "vertical" if height >= 560 else "grid"
    elif width < 720:
        # Four horizontal bubbles cannot fit many 420–719 dp split-screen
        # windows. A compact 2×2 grid keeps every touch target visible.
        source_menu = "grid"
    else:
        source_menu = "grid" if height < 420 else "fan"

    result_mode = "bottom_sheet" if width < 520 else "floating_card"
    available = width - (nav_extent if navigation == "rail" else 0) - safe_margin * 2
    comfortable = 360.0 if is_tablet else 336.0
    result_width = min(
        max(1.0, available),
        clamp(available * (0.42 if width >= 720 else 0.92), 232.0, comfortable),
    )
    return AdaptiveChromeV120(
        width_dp=width,
        height_dp=height,
        window_class=window_class,
        navigation=navigation,
        nav_extent_dp=nav_extent,
        safe_margin_dp=safe_margin,
        content_gap_dp=gap,
        scanner_header_mode=header,
        source_menu_mode=source_menu,
        result_mode=result_mode,
        result_width_dp=result_width,
        touch_target_dp=touch,
        motion_budget_ms=0 if reduce_motion else 180,
        image_decode_edge_px=1024 if width < 600 else (1440 if width < 1200 else 1920),
    )


def scanner_frame(
    viewport_width: float,
    viewport_height: float,
    *,
    top_reserve: float = 0.0,
    bottom_reserve: float = 0.0,
    inset: float = 10.0,
) -> Tuple[float, float, float, float]:
    """Compute a centered, fully visible card guide in local viewport coordinates."""
    width = max(1.0, float(viewport_width or 0))
    height = max(1.0, float(viewport_height or 0))
    top = clamp(top_reserve, 0.0, height * 0.28)
    bottom = clamp(bottom_reserve, 0.0, height * 0.28)
    margin = max(float(inset), min(width, height) * 0.035)
    available_w = max(1.0, width - margin * 2)
    available_h = max(1.0, height - top - bottom - margin * 2)
    frame_h = available_h
    frame_w = frame_h / CARD_ASPECT
    if frame_w > available_w:
        frame_w = available_w
        frame_h = frame_w * CARD_ASPECT
    x = (width - frame_w) / 2.0
    y = bottom + margin + max(0.0, (available_h - frame_h) / 2.0)
    return x, y, frame_w, frame_h


def scanner_overlay_layout(
    viewport_width: float,
    viewport_height: float,
    *,
    is_tablet: bool = False,
    result_visible: bool = False,
) -> Dict[str, Tuple[float, float, float, float] | str]:
    """Place scanner overlays without overlap, even on very short landscape windows."""
    width = max(240.0, float(viewport_width or 0))
    height = max(240.0, float(viewport_height or 0))
    chrome = adaptive_chrome(width, height, is_tablet=is_tablet)
    pad = chrome.safe_margin_dp
    chip_h = chrome.touch_target_dp
    device_w = clamp(width * 0.30, 142.0, 232.0)
    status_w = clamp(width * 0.46, 212.0, 340.0)
    device = (width - pad - device_w, height - pad - chip_h, device_w, chip_h)
    status = ((width - status_w) / 2.0, height - pad - chip_h, status_w, chip_h)
    if status[0] + status[2] > device[0] - 8.0:
        # Narrow screens get two non-overlapping rows.
        status = (pad, height - pad * 2 - chip_h * 2, width - pad * 2, chip_h)
        device = (width - pad - device_w, height - pad - chip_h, device_w, chip_h)

    result_w = chrome.result_width_dp
    result_h = 148.0 if width >= 520 else 132.0
    # Ultra-short freeform windows still keep the result below the stacked
    # header. The UI may become denser, but it never spills behind system chrome.
    header_bottom = min(status[1], device[1])
    result_h = max(72.0, min(result_h, header_bottom - pad * 2.0))
    result = (pad, pad, result_w, result_h)
    source_w = 154.0 if width >= 520 else 132.0
    source_h = chip_h
    if chrome.source_menu_mode == "fan":
        source = (pad, max(pad, result[1] + (result_h + 12.0 if result_visible else 0.0)), source_w, source_h)
    else:
        source = (width - pad - source_w, pad, source_w, source_h)

    frame = scanner_frame(
        width,
        height,
        top_reserve=chip_h + pad * 2,
        bottom_reserve=(result_h + pad if result_visible and width < 520 else chip_h + pad),
        inset=pad,
    )
    return {
        "header_mode": chrome.scanner_header_mode,
        "source_menu_mode": chrome.source_menu_mode,
        "result_mode": chrome.result_mode,
        "device": device,
        "status": status,
        "result": result,
        "source": source,
        "frame": frame,
    }


def source_menu_geometry(
    viewport_width: float,
    viewport_height: float,
    *,
    is_tablet: bool = False,
) -> Dict[str, float | int | str]:
    """Return an open four-action menu that always fits the current window."""
    width = max(240.0, float(viewport_width or 0))
    height = max(240.0, float(viewport_height or 0))
    chrome = adaptive_chrome(width, height, is_tablet=is_tablet)
    mode = chrome.source_menu_mode
    gap = chrome.content_gap_dp
    pad = chrome.safe_margin_dp
    desired = 148.0 if width < 420 else 176.0
    if mode == "grid":
        columns, rows = 2, 2
        bubble_width = min(desired, max(chrome.touch_target_dp, (width - pad * 2 - gap) / 2.0))
    elif mode == "horizontal":
        columns, rows = 4, 1
        bubble_width = min(desired, max(chrome.touch_target_dp, (width - pad * 2 - gap * 3) / 4.0))
    else:
        columns, rows = 1, 4
        bubble_width = min(desired, max(chrome.touch_target_dp, width - pad * 2))
    menu_width = bubble_width * columns + gap * max(0, columns - 1)
    menu_height = chrome.touch_target_dp * rows + gap * max(0, rows - 1)
    return {
        "mode": mode,
        "columns": columns,
        "rows": rows,
        "bubble_width_dp": bubble_width,
        "bubble_height_dp": chrome.touch_target_dp,
        "width_dp": menu_width,
        "height_dp": menu_height,
        "pad_dp": pad,
    }


def virtual_window(total_items: int, scroll_fraction: float, viewport_rows: int, *, overscan: int = 3) -> Tuple[int, int]:
    """Small deterministic helper used by virtualized Kivy lists and tests."""
    total = max(0, int(total_items or 0))
    rows = max(1, int(viewport_rows or 1))
    extra = max(0, int(overscan or 0))
    if total <= rows + extra * 2:
        return 0, total
    fraction = clamp(scroll_fraction, 0.0, 1.0)
    max_start = max(0, total - rows)
    center_start = int(floor(max_start * fraction))
    start = max(0, center_start - extra)
    end = min(total, center_start + rows + extra)
    return start, end


def audit_overlay(layout: Mapping[str, object], viewport_width: float, viewport_height: float) -> Iterable[str]:
    """Return human-readable overlay violations for the responsive fuzz suite."""
    issues = []
    width = float(viewport_width or 0)
    height = float(viewport_height or 0)
    rect_names = ("device", "status", "result", "source", "frame")
    for name in rect_names:
        rect = layout.get(name)
        if not isinstance(rect, (tuple, list)) or len(rect) != 4:
            issues.append(f"{name}: ungültige Geometrie")
            continue
        x, y, w, h = (float(v) for v in rect)
        if w <= 0 or h <= 0:
            issues.append(f"{name}: leere Fläche")
        if x < -0.5 or y < -0.5 or x + w > width + 0.5 or y + h > height + 0.5:
            issues.append(f"{name}: außerhalb des Viewports")
    return issues
