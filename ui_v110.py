# -*- coding: utf-8 -*-
"""Responsives Designsystem für Just InCard v11.0.

Das Modul bleibt absichtlich frei von Kivy-Imports. Dadurch können die
Breakpoint-, Typografie- und Scanner-Geometrien in GitHub Actions für viele
virtuelle Smartphone-/Tabletgrößen geprüft werden, ohne ein Android-Fenster zu
starten.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import ceil
from typing import Dict, Iterable, Mapping, Tuple

CARD_ASPECT = 1.45  # Höhe / Breite einer Yu-Gi-Oh!-Karte (gerundeter UI-Wert)


def clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


@dataclass(frozen=True)
class LayoutProfileV110:
    width_dp: float
    height_dp: float
    shortest_dp: float
    longest_dp: float
    landscape: bool
    device_class: str
    window_class: str
    navigation_mode: str
    layout_mode: str
    is_phone: bool
    is_tablet: bool
    content_max_dp: float
    content_columns: int
    search_columns: int
    result_columns: int
    dialog_max_dp: float
    outer_margin_dp: float
    gap_dp: float
    touch_dp: float
    control_font_scale: float
    body_font_scale: float
    compact_text: bool

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def make_layout_profile(
    width_dp: float,
    height_dp: float,
    *,
    smallest_width_dp: float = 0,
    font_scale: float = 1.0,
) -> LayoutProfileV110:
    """Ermittelt ein Material-3-artiges Fensterprofil.

    Die aktuelle Fensterbreite bestimmt das konkrete Layout. Die kleinste
    Gerätebreite hält Tablets auch im Split-Screen als Formfaktor erkennbar.
    """
    width_dp = max(240.0, float(width_dp or 0))
    height_dp = max(240.0, float(height_dp or 0))
    shortest = min(width_dp, height_dp)
    longest = max(width_dp, height_dp)
    landscape = width_dp > height_dp
    form_factor = float(smallest_width_dp or shortest)

    if width_dp < 360:
        window_class = "narrow"
    elif width_dp < 600:
        window_class = "compact"
    elif width_dp < 840:
        window_class = "medium"
    elif width_dp < 1200:
        window_class = "expanded"
    elif width_dp < 1600:
        window_class = "large"
    else:
        window_class = "extra_large"

    if form_factor >= 840:
        device_class = "large_tablet"
    elif form_factor >= 600:
        device_class = "tablet"
    elif shortest < 350 or width_dp < 330:
        device_class = "compact_phone"
    elif shortest < 480:
        device_class = "phone"
    else:
        device_class = "large_phone"

    is_tablet = device_class in {"tablet", "large_tablet"}
    is_phone = not is_tablet
    rail = is_tablet and width_dp >= 720
    desktop_split = is_tablet and (width_dp >= 900 or (landscape and width_dp >= 720))

    if desktop_split:
        layout_mode = "tablet_desktop"
        navigation_mode = "rail"
        content_max = 1520.0 if device_class == "large_tablet" else 1240.0
        content_columns = 2
        result_columns = 2 if width_dp >= 1180 else 1
    elif rail:
        layout_mode = "tablet_rail"
        navigation_mode = "rail"
        content_max = 1040.0
        content_columns = 1
        result_columns = 1
    elif is_tablet:
        layout_mode = "tablet_compact"
        navigation_mode = "bottom"
        content_max = 920.0
        content_columns = 1
        result_columns = 1
    else:
        layout_mode = "phone_landscape" if landscape else ("phone_compact" if device_class == "compact_phone" else "phone")
        navigation_mode = "bottom"
        content_max = 760.0 if landscape else 560.0
        content_columns = 1
        result_columns = 1

    if width_dp >= 1000:
        search_columns = 3
    elif width_dp >= 620:
        search_columns = 2
    else:
        search_columns = 1

    outer_margin = 8.0 if window_class == "narrow" else (12.0 if is_phone else 16.0)
    gap = 8.0 if window_class in {"narrow", "compact"} else (10.0 if window_class == "medium" else 12.0)
    touch = 50.0 if device_class == "compact_phone" else (52.0 if is_phone else 56.0)

    font_scale = clamp(font_scale, 0.80, 2.00)
    control_font_scale = clamp(font_scale, 0.90, 1.18)
    body_font_scale = clamp(font_scale, 0.92, 1.42)
    compact_text = width_dp < 360 or height_dp < 560

    dialog_max = 1180.0 if width_dp >= 1200 else (960.0 if width_dp >= 840 else (760.0 if width_dp >= 600 else width_dp))

    return LayoutProfileV110(
        width_dp=width_dp,
        height_dp=height_dp,
        shortest_dp=shortest,
        longest_dp=longest,
        landscape=landscape,
        device_class=device_class,
        window_class=window_class,
        navigation_mode=navigation_mode,
        layout_mode=layout_mode,
        is_phone=is_phone,
        is_tablet=is_tablet,
        content_max_dp=content_max,
        content_columns=content_columns,
        search_columns=search_columns,
        result_columns=result_columns,
        dialog_max_dp=dialog_max,
        outer_margin_dp=outer_margin,
        gap_dp=gap,
        touch_dp=touch,
        control_font_scale=control_font_scale,
        body_font_scale=body_font_scale,
        compact_text=compact_text,
    )


def text_sp(role: str, profile: Mapping[str, object]) -> float:
    """Zentrale Typografieskala. Werte sind logische sp vor Kivy-dp-Konvertierung."""
    table = {
        "display": 28.0,
        "headline": 22.0,
        "title": 18.0,
        "section": 15.0,
        "body": 13.0,
        "body_small": 11.5,
        "label": 11.0,
        "nav": 10.0,
    }
    base = table.get(str(role), 13.0)
    if bool(profile.get("compact_text")) and role in {"display", "headline", "title", "section"}:
        base -= 1.5
    if bool(profile.get("is_tablet")) and role in {"display", "headline", "title"}:
        base += 1.0
    return max(9.0, base)


def grid_height(item_count: int, columns: int, item_height: float, gap: float = 0.0) -> float:
    count = max(0, int(item_count or 0))
    cols = max(1, int(columns or 1))
    rows = int(ceil(count / float(cols))) if count else 0
    return rows * float(item_height or 0) + max(0, rows - 1) * float(gap or 0)


def card_frame_geometry(
    viewport_width: float,
    viewport_height: float,
    *,
    margin_ratio: float = 0.055,
    minimum_margin: float = 8.0,
    maximum_width_ratio: float = 0.92,
    maximum_height_ratio: float = 0.94,
) -> Tuple[float, float, float, float]:
    """Zentrierte Kartenfläche innerhalb eines beliebigen Viewports.

    Rückgabe: ``x, y, width, height`` relativ zum Viewport. Die Fläche bleibt
    vollständig sichtbar und besitzt auf Smartphone, Tablet und Querformat stets
    dasselbe Karten-Seitenverhältnis.
    """
    width = max(1.0, float(viewport_width or 0))
    height = max(1.0, float(viewport_height or 0))
    margin = max(float(minimum_margin), min(width, height) * clamp(margin_ratio, 0.0, 0.20))
    available_w = max(1.0, min(width - 2.0 * margin, width * clamp(maximum_width_ratio, 0.40, 1.0)))
    available_h = max(1.0, min(height - 2.0 * margin, height * clamp(maximum_height_ratio, 0.40, 1.0)))

    card_h = available_h
    card_w = card_h / CARD_ASPECT
    if card_w > available_w:
        card_w = available_w
        card_h = card_w * CARD_ASPECT
    x = (width - card_w) / 2.0
    y = (height - card_h) / 2.0
    return x, y, card_w, card_h


def cover_geometry(
    source_width: float,
    source_height: float,
    target_width: float,
    target_height: float,
    *,
    rotated: bool = False,
) -> Tuple[float, float, float, float]:
    """Cover-Fit ohne Verzerrung für Kamera- und Kartenbilder.

    Rückgabe: ``x, y, width, height`` relativ zur Ziel-/Clipfläche.
    """
    sw = max(1.0, float(source_width or 0))
    sh = max(1.0, float(source_height or 0))
    tw = max(1.0, float(target_width or 0))
    th = max(1.0, float(target_height or 0))
    if rotated:
        sw, sh = sh, sw
    scale = max(tw / sw, th / sh)
    width = sw * scale
    height = sh * scale
    return (tw - width) / 2.0, (th - height) / 2.0, width, height


def scanner_stage_height(profile: Mapping[str, object], available_height_dp: float) -> float:
    """Geräteabhängige, aber begrenzte Höhe des Scanner-Viewports."""
    available = max(240.0, float(available_height_dp or 0))
    if bool(profile.get("is_tablet")):
        preferred = 640.0 if bool(profile.get("landscape")) else 720.0
    else:
        preferred = 520.0 if not bool(profile.get("landscape")) else 420.0
    minimum = 260.0 if profile.get("device_class") == "compact_phone" else 300.0
    return clamp(available, minimum, preferred)


def audit_profile(profile: Mapping[str, object]) -> Iterable[str]:
    """Liefert Layoutverletzungen für automatisierte Responsive-Tests."""
    problems = []
    width = float(profile.get("width_dp") or 0)
    height = float(profile.get("height_dp") or 0)
    touch = float(profile.get("touch_dp") or 0)
    gap = float(profile.get("gap_dp") or 0)
    max_content = float(profile.get("content_max_dp") or 0)
    if width < 240 or height < 240:
        problems.append("Fensterprofil kleiner als unterstützte Mindestgröße")
    if touch < 48:
        problems.append("Touch-Ziel kleiner als 48 dp")
    if gap < 6:
        problems.append("Abstand kleiner als 6 dp")
    if max_content < 320:
        problems.append("Inhaltsbreite zu klein")
    if int(profile.get("search_columns") or 0) < 1:
        problems.append("Ungültige Suchspaltenzahl")
    if profile.get("navigation_mode") == "rail" and width < 720:
        problems.append("Rail-Navigation bei zu schmalem Fenster")
    return problems
