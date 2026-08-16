# -*- coding: utf-8 -*-
"""
Just InCard v11.2.3 für Android/Kivy
- schnelle Kartensuche über YGOPRODeck API v7
- deutsche Suche als Standard, Sprache auswählbar
- Sammlung/Decks/Einstellungen primär in SQLite, JSON als kompatible Sicherung
- XLSX-Export ohne openpyxl
- adaptive Smartphone-UI und tabletoptimierte Desktop-/Rail-Ansicht
- Light/Dark Theme Umschalter
- seitenweise Ergebnisanzeige für mehr Stabilität bei vielen Treffern
- App-Logo über app_logo.png personalisierbar
- scannerzentrierte v11.2.3-KI-Ensemble-Pipeline mit Zeitbudgets, lokaler Sofortsuche, Bildqualitaetspruefung,
  Mehrkarten-/Artwork-Fallback und geräteadaptiven Vollseiten-Prüfansichten
"""

import json
import base64
import copy
import mimetypes
import math
import io
import os
import hashlib
from difflib import SequenceMatcher
import re
import ssl
import sqlite3
import threading
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from pathlib import Path
from html import escape as html_escape
from xml.sax.saxutils import escape as xml_escape

from app_version import APP_VERSION, APP_BUILD, BACKUP_SCHEMA_VERSION
from storage_v91 import AppDatabaseV91
from features_v93 import (
    ScanLearningStoreV93,
    UndoManagerV93,
    IncrementalSyncStateV93,
    CollectionAnalyticsV93,
    DiagnosticsRunnerV93,
    PERFORMANCE_MODES_V93,
    recommend_performance_mode,
)
from features_v97 import (
    SessionStateStoreV97,
    BackupInspectorV97,
    CacheManagerV97,
    apply_pending_restore,
    normalize_accessibility_settings,
    schedule_backup_restore,
)
from ai_scanner_v102 import (
    AI_MODEL_STACK_V102, CARD_LANGUAGE_CODES_V102, CARD_LANGUAGE_LABELS_V102, TEXT_COLOR_PROFILES_V102,
    artwork_identity_key, build_preview_map, build_preview_records, collection_artwork_suffix, rank_scan_items, card_family, visual_similarity,
)
from deck_ai_v102 import build_deck_suggestions
from features_v104 import (
    APP_ADMIN,
    APP_DEVELOPER,
    AutomaticBackupManagerV104,
    CARD_CONDITIONS_V104,
    DEFAULT_PRIVACY_V104,
    EDITION_OPTIONS_V104,
    confidence_breakdown_text,
    card_role,
    explain_deck_synergy,
    find_duplicate_variant_groups,
    normalized_collection_metadata,
    offline_status,
    redact_diagnostics,
    scanner_learning_statistics,
    simulate_deck_hands,
)
from security_v104 import verify_integrity_manifest
from ai_ensemble_v109 import ENGINE_STACK_V109, engine_availability, model_stack_summary, rerank_scan_results_v109
from ui_v110 import (
    audit_profile as audit_ui_profile_v110,
    card_frame_geometry as card_frame_geometry_v110,
    cover_geometry as cover_geometry_v110,
    grid_height as grid_height_v110,
    make_layout_profile as make_layout_profile_v110,
    scanner_stage_height as scanner_stage_height_v110,
    text_sp as text_sp_v110,
)
from gallery_multiengine_v1091 import (
    GALLERY_MULTI_ENGINE_PLAN_V1093,
    fuse_region_detections,
    gallery_engine_summary,
    merge_ocr_engine_outputs,
    stable_region_session_id,
    suppress_nested_regions,
)
from native_ai_bridge_v109 import (
    native_status,
    detect_card_regions as native_detect_card_regions,
    orb_similarity as native_orb_similarity,
    akaze_similarity as native_akaze_similarity,
    yolo_regions as native_yolo_regions,
    mediapipe_regions as native_mediapipe_regions,
    mobilenet_similarity as native_mobilenet_similarity,
    mlkit_ocr as native_mlkit_ocr,
    paddle_ocr as native_paddle_ocr,
)
from optional_ocr_v109 import optional_ocr_bundle
from scanner_v108 import (
    card_metadata_consistency,
    exact_set_item_for_code,
    extract_scan_metadata,
    detect_script_language,
    identifier_stage,
    language_code_from_set_code,
    language_label as strict_language_label,
    merge_scan_metadata,
    strict_set_code_equal,
)
from scanner_v100 import (
    GALLERY_SCAN_MODE,
    SCAN_MODE_PROFILES,
    SUPPORTED_IMAGE_EXTENSIONS,
    ScanDeadlineV100,
    ScanTimingStoreV100,
    accepted_image_extension,
    effect_search_terms,
    effect_similarity,
    effect_tokens,
    fusion_bonus,
    gallery_scan_profile,
    mode_timing_text,
    normalize_effect_text,
    scan_mode_profile,
    script_fallback_order,
)

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from kivy.resources import resource_find
from kivy.utils import platform, escape_markup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
try:
    from kivy.uix.camera import Camera
except Exception:
    Camera = None
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image, AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.scatterlayout import ScatterLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.widget import Widget

# KI-Scanner v11.2.3: lokaler Modellstapel fuer Galerie-Genauigkeit
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
CARDSETS_URL = "https://db.ygoprodeck.com/api/v7/cardsets.php"
CARDSETS_CACHE = None
DB_VERSION_URL = "https://db.ygoprodeck.com/api/v7/checkDBVer.php"
ROCKROLLER_ALL_CARDS_URL = "https://yugioh-api.rockroller.xyz/cards.json"
YGOJSON_INDIVIDUAL_ZIP_URL = "https://github.com/iconmaster5326/YGOJSON/releases/download/v1/individual.zip"
YGOJSON_AGGREGATE_ZIP_URL = "https://github.com/iconmaster5326/YGOJSON/releases/download/v1/aggregate.zip"
# Project Ignis / EDOPro-CDBs: SQLite-Datenbanken mit offiziellen, Skill-, Rush-, Pre-Release- und optional inoffiziellen Karten.
BABELCDB_URLS = [
    ("Project Ignis EDOPro official", "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/cards.cdb"),
    ("Project Ignis EDOPro skills", "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/cards-skills.cdb"),
    ("Project Ignis EDOPro rush", "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/cards-rush.cdb"),
    ("Project Ignis EDOPro unofficial", "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/cards-unofficial.cdb"),
    ("Project Ignis EDOPro skills unofficial", "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/cards-skills-unofficial.cdb"),
    ("Project Ignis EDOPro prerelease", "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/prerelease-others.cdb"),
]
LOCAL_BUNDLED_SOURCE_FILE = "just_incard_local_seed.json"
LOCAL_SOURCE_REGISTRY_FILE = "just_incard_source_registry.json"
CUSTOM_CARDS_PATH = ""
LOCAL_CARD_DATABASE_DIR = ""
# Weitere optionale Quellen. Sie werden defensiv genutzt: wenn Format/Netzwerk nicht passt, wird die Quelle übersprungen.
YUGIPEDIA_CARGO_API_URL = "https://yugipedia.com/api.php"
YGOPRODECK_ARCHETYPES_URL = "https://db.ygoprodeck.com/api/v7/archetypes.php"
PRIMARY_SYNC_LANGUAGES = ["de", "", "fr", "it", "pt"]
YGORESOURCES_BASE_URL = "https://db.ygoresources.com"
YGORESOURCES_NAME_INDEX = YGORESOURCES_BASE_URL + "/data/idx/card/name/{lang}"
YGORESOURCES_PRINTCODE_INDEX = YGORESOURCES_BASE_URL + "/data/meta/index/printcode"
YGORESOURCES_CARD_DATA = YGORESOURCES_BASE_URL + "/data/card/{card_id}"
SUPPLEMENTAL_SOURCE_LANGS = ["en", "de", "fr", "it", "es", "pt", "ko", "ja", "zh"]
APP_DISPLAY_NAME = "Just InCard"
APP_COPYRIGHT = "© 2026 Just InCard"
APP_USER_AGENT = f"JustInCard/{APP_VERSION}"
APP_MOTTO = "Scannen. Sammeln. Verwalten. Duellbereit."
APP_LOGO_FILE = "app_logo.png"
APP_LOGO_TRANSPARENT_FILE = "app_logo_transparent.png"
PRESPLASH_FILE = "presplash.png"
STARTUP_BG_HEX = "#020512"
STARTUP_BG = (2 / 255.0, 5 / 255.0, 18 / 255.0, 1)
HELP_ICON_LIGHT = "help_icon_light.png"
HELP_ICON_DARK = "help_icon_dark.png"
SETTINGS_ICON_LIGHT = "settings_icon_light.png"
SETTINGS_ICON_DARK = "settings_icon_dark.png"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

# Sicherheitsfallback für fehlende Icons
for _icon_name in ["HELP_ICON_LIGHT","HELP_ICON_DARK","SETTINGS_ICON_LIGHT","SETTINGS_ICON_DARK"]:
    if _icon_name not in globals():
        globals()[_icon_name] = ""

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
PREVIEW_PLACEHOLDER_FILE = "preview_placeholder.png"
UI_ICON_DIR = os.path.join("assets", "ui")
UI_MOCKUP_REFERENCE_FILE = os.path.join("docs", "ui_mockup_v96.png")
DIAGNOSTIC_FILE = "just_incard_fehlerbericht.txt"
BACKUP_PREFIX = "JustInCard_Backup"
PAGE_SIZE = 50
MAX_DECKS = 50
PROGRAMMER_NAME = APP_DEVELOPER
ADMIN_NAME = APP_ADMIN
MAIN_DECK_MAX = 60
MIN_DECK_SIZE = 40


def ui_asset(name):
    """Löst ein mitgeliefertes v10.0-UI-Symbol plattformunabhängig auf."""
    filename = str(name or "").strip()
    if not filename:
        return ""
    if not filename.lower().endswith(".png"):
        filename += ".png"
    relative = os.path.join(UI_ICON_DIR, filename)
    return resource_find(relative) or (relative if os.path.exists(relative) else "")



def atomic_write_json(path, payload, indent=2):
    """Schreibt wichtige App-Daten atomar, damit ein Abbruch keine JSON-Datei zerstört."""
    target = os.path.abspath(str(path or ""))
    if not target:
        raise ValueError("Ungültiger Dateipfad")
    folder = os.path.dirname(target)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp_path = target + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=indent)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except Exception:
            pass
    os.replace(temp_path, target)
    return target


def safe_read_json(path, default=None):
    """Liest JSON defensiv und ignoriert beschädigte oder leere Dateien."""
    fallback = default if default is not None else {}
    try:
        if not path or not os.path.exists(path) or os.path.getsize(path) <= 0:
            return fallback
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return fallback


def fetch_primary_database_version(timeout=12):
    """Liest die aktuelle YGOPRODeck-Datenbankversion defensiv."""
    try:
        req = urllib.request.Request(DB_VERSION_URL, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"})
        raw = open_url_bytes(req, timeout=timeout)
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if isinstance(payload, dict):
            return str(payload.get("database_version") or payload.get("last_update") or payload.get("version") or payload.get("0") or "")
    except Exception:
        return ""
    return ""


def get_android_screen_metrics_snapshot():
    """Liest reale Android-Displaydaten inkl. Dichte und Systemleisten.

    Die Funktion ist bewusst unabhängig von Kivy-Widgets und kann in einem
    Hintergrund-Thread ausgeführt werden. Bei älteren Android-Versionen wird
    automatisch auf DisplayMetrics zurückgefallen.
    """
    result = {
        "width_px": int(max(1, Window.width)),
        "height_px": int(max(1, Window.height)),
        "density": 1.0,
        "density_dpi": 160,
        "scaled_density": 1.0,
        "font_scale": 1.0,
        "screen_width_dp": 0,
        "screen_height_dp": 0,
        "smallest_width_dp": 0,
        "inset_left_px": 0,
        "inset_top_px": 0,
        "inset_right_px": 0,
        "inset_bottom_px": 0,
        "source": "kivy",
    }
    try:
        from kivy.metrics import Metrics
        result["density"] = float(getattr(Metrics, "density", 1.0) or 1.0)
        result["font_scale"] = float(getattr(Metrics, "fontscale", 1.0) or 1.0)
        result["scaled_density"] = result["font_scale"] * result["density"]
        result["density_dpi"] = int(round(result["density"] * 160.0))
    except Exception:
        pass
    if platform != "android":
        return result
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        DisplayMetrics = autoclass("android.util.DisplayMetrics")
        BuildVersion = autoclass("android.os.Build$VERSION")
        activity = PythonActivity.mActivity
        metrics = DisplayMetrics()
        display = activity.getWindowManager().getDefaultDisplay()
        try:
            display.getRealMetrics(metrics)
        except Exception:
            display.getMetrics(metrics)
        density_value = float(metrics.density or 1.0)
        scaled_density_value = float(metrics.scaledDensity or metrics.density or 1.0)
        result.update({
            "width_px": int(metrics.widthPixels),
            "height_px": int(metrics.heightPixels),
            "density": density_value,
            "density_dpi": int(metrics.densityDpi or 160),
            "scaled_density": scaled_density_value,
            "font_scale": max(0.75, min(2.0, scaled_density_value / max(0.5, density_value))),
            "android_api": int(BuildVersion.SDK_INT),
            "source": "android",
        })
        # Die Android-Configuration unterscheidet ein echtes Tablet wesentlich
        # zuverlässiger von einem großen Smartphone als reine Pixelmaße.
        try:
            configuration = activity.getResources().getConfiguration()
            result["screen_width_dp"] = int(getattr(configuration, "screenWidthDp", 0) or 0)
            result["screen_height_dp"] = int(getattr(configuration, "screenHeightDp", 0) or 0)
            result["smallest_width_dp"] = int(getattr(configuration, "smallestScreenWidthDp", 0) or 0)
            result["font_scale"] = max(0.75, min(2.0, float(getattr(configuration, "fontScale", result["font_scale"]) or result["font_scale"])))
        except Exception:
            pass

        # API 30+: aktuelle WindowMetrics statt nur der physischen Displaygröße.
        # Das berücksichtigt Split-Screen, Foldables, DeX und Display-Aussparungen.
        try:
            if int(BuildVersion.SDK_INT) >= 30:
                WindowInsetsType = autoclass("android.view.WindowInsets$Type")
                window_metrics = activity.getWindowManager().getCurrentWindowMetrics()
                bounds = window_metrics.getBounds()
                current_w = max(1, int(bounds.width()))
                current_h = max(1, int(bounds.height()))
                result["window_metrics_width_px"] = current_w
                result["window_metrics_height_px"] = current_h
                insets = window_metrics.getWindowInsets().getInsetsIgnoringVisibility(
                    WindowInsetsType.systemBars() | WindowInsetsType.displayCutout()
                )
                result.update({
                    "inset_left_px": max(0, int(insets.left)),
                    "inset_top_px": max(0, int(insets.top)),
                    "inset_right_px": max(0, int(insets.right)),
                    "inset_bottom_px": max(0, int(insets.bottom)),
                    "window_metrics_source": "android-window-metrics",
                })
        except Exception:
            pass

        # API 23+: sichtbaren Bereich des Decor-Views abfragen. Das funktioniert
        # auch auf vielen Geräten mit Notch, Gestenleiste oder Hersteller-Navigation.
        try:
            Rect = autoclass("android.graphics.Rect")
            rect = Rect()
            decor = activity.getWindow().getDecorView()
            decor.getWindowVisibleDisplayFrame(rect)
            left = max(0, int(rect.left))
            top = max(0, int(rect.top))
            right = max(0, int(result["width_px"] - rect.right))
            bottom = max(0, int(result["height_px"] - rect.bottom))
            result.update({
                "inset_left_px": max(int(result.get("inset_left_px") or 0), left),
                "inset_top_px": max(int(result.get("inset_top_px") or 0), top),
                "inset_right_px": max(int(result.get("inset_right_px") or 0), right),
                "inset_bottom_px": max(int(result.get("inset_bottom_px") or 0), bottom),
            })
        except Exception:
            pass
    except Exception:
        pass
    return result


def build_ui_profile(metrics=None, window_size=None):
    """Erstellt das zentrale v11.2.3-UI-Profil für Android-Fenster jeder Größe.

    Die eigentliche Breakpoint-Logik liegt in :mod:`ui_v110` und wird dort ohne
    Kivy-Abhängigkeit gegen viele Smartphone-/Tabletgrößen getestet. Android-
    Insets bleiben in Kivy-Pixeln erhalten, während die Designentscheidungen in
    logischen dp getroffen werden.
    """
    metrics = dict(metrics or {})
    win_w, win_h = window_size or (Window.width, Window.height)
    win_w = float(max(1, win_w))
    win_h = float(max(1, win_h))
    density = float(metrics.get("density") or 1.0)
    density = max(0.5, min(6.0, density))
    scaled_density = float(metrics.get("scaled_density") or density)
    font_scale = float(metrics.get("font_scale") or (scaled_density / max(0.5, density)))
    font_scale = max(0.80, min(2.00, font_scale))

    width_dp = win_w / density
    height_dp = win_h / density
    pure = make_layout_profile_v110(
        width_dp,
        height_dp,
        smallest_width_dp=float(metrics.get("smallest_width_dp") or 0),
        font_scale=font_scale,
    ).as_dict()

    safe = {
        "left": float(metrics.get("inset_left_px") or 0),
        "top": float(metrics.get("inset_top_px") or 0),
        "right": float(metrics.get("inset_right_px") or 0),
        "bottom": float(metrics.get("inset_bottom_px") or 0),
    }
    safe["left"] = min(max(0.0, safe["left"]), win_w * 0.12)
    safe["right"] = min(max(0.0, safe["right"]), win_w * 0.12)
    safe["top"] = min(max(0.0, safe["top"]), win_h * 0.12)
    safe["bottom"] = min(max(0.0, safe["bottom"]), win_h * 0.16)

    shortest_dp = float(pure.get("shortest_dp") or min(width_dp, height_dp))
    pure.update({
        "width_px": win_w,
        "height_px": win_h,
        "real_width_px": float(metrics.get("width_px") or win_w),
        "real_height_px": float(metrics.get("height_px") or win_h),
        "density": density,
        "font_scale": font_scale,
        "ui_scale": max(0.84, min(1.22, shortest_dp / 600.0 + 0.18)),
        "safe": safe,
        "source": metrics.get("source", "kivy"),
    })
    return pure

def ui_font_px(sp_value, profile=None, body=False):
    """Liefert eine begrenzte, gerätesichere Schriftgröße in Kivy-Pixeln."""
    try:
        profile = profile or getattr(App.get_running_app(), "ui_profile", None) or build_ui_profile()
        scale = float(profile.get("body_font_scale" if body else "control_font_scale") or 1.0)
    except Exception:
        scale = 1.0
    return dp(float(sp_value) * max(0.80, min(1.35 if body else 1.16, scale)))


def set_android_screen_orientation(mode="unspecified"):
    """Setzt die Android-Bildschirmausrichtung optional per pyjnius.
    Auf Desktop, GitHub-Builds oder Geräten ohne pyjnius wird nichts geändert.
    mode: portrait, sensor, unspecified
    """
    if platform != "android":
        return False
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ActivityInfo = autoclass("android.content.pm.ActivityInfo")
        activity = PythonActivity.mActivity
        constants = {
            "portrait": ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,
            "sensor": ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR,
            "unspecified": ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED,
        }
        activity.setRequestedOrientation(constants.get(mode, ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED))
        return True
    except Exception:
        return False


def get_android_display_rotation_degrees():
    """Liest die aktuelle Display-Rotation von Android.

    Rückgabe: 0, 90, 180 oder 270.
    Wird genutzt, damit die Kivy-Livekamera im Querformat nicht zusätzlich um 90 Grad falsch liegt.
    """
    if platform != "android":
        return 90 if Window.width > Window.height else 0
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Surface = autoclass("android.view.Surface")
        activity = PythonActivity.mActivity
        display = activity.getWindowManager().getDefaultDisplay()
        rotation = int(display.getRotation())
        mapping = {
            int(Surface.ROTATION_0): 0,
            int(Surface.ROTATION_90): 90,
            int(Surface.ROTATION_180): 180,
            int(Surface.ROTATION_270): 270,
        }
        return mapping.get(rotation, 0)
    except Exception:
        return 90 if Window.width > Window.height else 0


def compute_live_camera_rotation(base_rotation=270):
    """Berechnet die sichtbare Livekamera-Rotation abhängig von Geräteausrichtung.

    Die App nutzt 270° als gespeicherten Nullpunkt für Android-Hochformat.
    Wenn das Gerät quer gehalten wird, muss diese Korrektur mit der Display-Rotation
    verrechnet werden. Sonst bleibt das Livebild im Querformat um 90° verdreht.
    """
    try:
        base = int(base_rotation or 270) % 360
    except Exception:
        base = 270
    display_rotation = get_android_display_rotation_degrees()
    if platform == "android":
        return (base + display_rotation) % 360
    if Window.width > Window.height:
        return 0
    return base


def android_haptic_feedback(duration_ms=35):
    """Kurzes optionales Vibrationsfeedback für erfolgreiche Scan-/Speicheraktionen."""
    if platform != "android":
        return False
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        BuildVersion = autoclass("android.os.Build$VERSION")
        vibrator = PythonActivity.mActivity.getSystemService(Context.VIBRATOR_SERVICE)
        if vibrator is None or not vibrator.hasVibrator():
            return False
        if int(BuildVersion.SDK_INT) >= 26:
            VibrationEffect = autoclass("android.os.VibrationEffect")
            vibrator.vibrate(VibrationEffect.createOneShot(int(duration_ms), VibrationEffect.DEFAULT_AMPLITUDE))
        else:
            vibrator.vibrate(int(duration_ms))
        return True
    except Exception:
        return False


def hide_android_system_ui():
    """Blendet Status-/Navigationsleisten auf Android so weit wie möglich aus."""
    if platform != "android":
        return False
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        View = autoclass("android.view.View")
        WindowManagerLayoutParams = autoclass("android.view.WindowManager$LayoutParams")
        activity = PythonActivity.mActivity
        window = activity.getWindow()
        window.addFlags(WindowManagerLayoutParams.FLAG_FULLSCREEN)
        decor = window.getDecorView()
        flags = (
            View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        )
        decor.setSystemUiVisibility(flags)
        return True
    except Exception:
        return False



def set_android_torch(enabled=True):
    """Schaltet die Android-Taschenlampe so defensiv wie möglich.

    Wichtig: Manche Hersteller blockieren setTorchMode, solange die Kamera bereits von
    der Live-Vorschau verwendet wird. Darum pausiert der Scanner vor dem Aufruf die
    Livekamera und diese Funktion probiert danach alle gemeldeten Flash-Kameras.
    Sie wirft keine Exception nach außen.
    """
    if platform != "android":
        return False, "Taschenlampe ist nur auf Android verfügbar."
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        PackageManager = autoclass("android.content.pm.PackageManager")
        activity = PythonActivity.mActivity
        if not activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_FLASH):
            return False, "Dieses Gerät meldet keine Taschenlampe."
        camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
        CameraCharacteristics = autoclass("android.hardware.camera2.CameraCharacteristics")
        last_error = ""
        preferred = []
        fallback = []
        for cam_id in camera_manager.getCameraIdList():
            try:
                characteristics = camera_manager.getCameraCharacteristics(cam_id)
                has_flash = characteristics.get(CameraCharacteristics.FLASH_INFO_AVAILABLE)
                lens_facing = characteristics.get(CameraCharacteristics.LENS_FACING)
                if bool(has_flash):
                    if int(lens_facing) == int(CameraCharacteristics.LENS_FACING_BACK):
                        preferred.append(cam_id)
                    else:
                        fallback.append(cam_id)
            except Exception as exc:
                last_error = str(exc)
        for cam_id in preferred + fallback:
            try:
                camera_manager.setTorchMode(cam_id, bool(enabled))
                return True, "Taschenlampe ein" if enabled else "Taschenlampe aus"
            except Exception as exc:
                last_error = str(exc)
        return False, "Taschenlampe gerade nicht verfügbar" + (f": {last_error}" if last_error else ".")
    except Exception as exc:
        return False, f"Taschenlampe konnte nicht geschaltet werden: {exc}"

def request_android_runtime_permissions(callback=None):
    """Fragt beim ersten Start die nötigen Android-Laufzeitberechtigungen ab."""
    if platform != "android":
        if callback:
            callback([])
        return False
    try:
        from android.permissions import Permission, request_permissions
        permissions = []
        for name in ("CAMERA", "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "READ_MEDIA_IMAGES", "POST_NOTIFICATIONS"):
            value = getattr(Permission, name, None)
            if value and value not in permissions:
                permissions.append(value)
        if permissions:
            request_permissions(permissions, callback)
        return True
    except Exception:
        return False

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = ssl.create_default_context()

# Nur als Fallback für Geräte mit kaputtem Android/Python-Zertifikatsspeicher.
INSECURE_SSL_FALLBACK = ssl._create_unverified_context()


def disable_android_file_uri_exposure_guard():
    """Verhindert auf manchen Android-Versionen den Absturz
    android.os.FileUriExposedException beim Öffnen der nativen Kamera über Plyer.

    Hintergrund: Einige Kivy/Plyer-Versionen übergeben der Android-Kamera noch eine
    file:// URI. Android 7+ blockiert das normalerweise. Da das Foto nur privat im
    App-Speicher für den Scanner verwendet wird, deaktivieren wir nur vor dem
    Kamera-Intent diese StrictMode-Prüfung. Falls das Gerät die Methode nicht
    unterstützt, läuft die App normal weiter.
    """
    if platform != "android":
        return False
    try:
        from jnius import autoclass
        StrictMode = autoclass("android.os.StrictMode")
        StrictMode.disableDeathOnFileUriExposure()
        return True
    except Exception:
        return False



def copy_android_content_uri_to_file(uri_value, output_dir, prefix="scan"):
    """Kopiert eine Android content:// URI zuverlässig in eine echte lokale Datei.
    Diese Funktion wird für Kamera und Galerie genutzt, weil Kivy/Image und OCR mit
    echten Dateien stabiler arbeiten als mit content:// Rückgaben einzelner Apps.
    """
    if platform != "android":
        return ""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Uri = autoclass("android.net.Uri")
        OpenableColumns = autoclass("android.provider.OpenableColumns")

        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        try:
            uri_text = str(uri_value.toString()) if hasattr(uri_value, "toString") else str(uri_value)
        except Exception:
            uri_text = str(uri_value)
        uri = uri_value if hasattr(uri_value, "getScheme") else Uri.parse(uri_text)

        ext = ".jpg"
        try:
            mime = resolver.getType(uri)
            if mime:
                m = str(mime).lower()
                if "png" in m:
                    ext = ".png"
                elif "webp" in m:
                    ext = ".webp"
                elif "heic" in m or "heif" in m:
                    ext = ".heic"
                elif "avif" in m:
                    ext = ".avif"
                elif "bmp" in m:
                    ext = ".bmp"
                elif "tiff" in m:
                    ext = ".tiff"
                elif "gif" in m:
                    ext = ".gif"
                elif "jpeg" in m or "jpg" in m:
                    ext = ".jpg"
                elif "zip" in m:
                    ext = ".zip"
                elif "json" in m:
                    ext = ".json"
                elif "spreadsheet" in m or "xlsx" in m:
                    ext = ".xlsx"
                elif "text" in m:
                    ext = ".txt"
        except Exception:
            pass

        try:
            cursor = resolver.query(uri, None, None, None, None)
            if cursor is not None:
                try:
                    name_index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if cursor.moveToFirst() and name_index >= 0:
                        display_name = str(cursor.getString(name_index) or "").lower()
                        suffix = os.path.splitext(display_name)[1]
                        if suffix in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif", ".avif", ".zip", ".json", ".xlsx", ".txt", ".db", ".sqlite", ".sqlite3", ".cdb"):
                            ext = suffix
                finally:
                    cursor.close()
        except Exception:
            pass

        os.makedirs(output_dir, exist_ok=True)
        unique_stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000_000:09d}_{hashlib.sha1(uri_text.encode('utf-8', 'ignore')).hexdigest()[:8]}"
        target = os.path.join(output_dir, f"{prefix}_{unique_stamp}{ext}")
        stream = resolver.openInputStream(uri)
        if stream is None:
            return ""
        try:
            with open(target, "wb") as out:
                buf = bytearray(1024 * 64)
                while True:
                    n = stream.read(buf)
                    if n is None or int(n) <= 0:
                        break
                    out.write(bytes(buf[:int(n)]))
        finally:
            try:
                stream.close()
            except Exception:
                pass
        return target if os.path.exists(target) and os.path.getsize(target) > 0 else ""
    except Exception:
        return ""



def normalize_scanner_image_file(path, output_dir, prefix="scan_normalized"):
    """Normalisiert Galerie-/Kamerabilder für Vorschau und OCR.

    Unterstützt über Pillow u. a. JPEG, PNG, WEBP, BMP, GIF und TIFF. Für
    HEIC/HEIF/AVIF oder herstellerspezifische Android-Decoder wird zusätzlich
    BitmapFactory verwendet. Das Ergebnis ist immer eine EXIF-korrigierte
    JPEG-Datei, die Kivy und ML Kit zuverlässig lesen können.
    """
    source = str(path or "").strip()
    if not source or not os.path.exists(source) or os.path.getsize(source) <= 0:
        return ""
    os.makedirs(output_dir, exist_ok=True)
    stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000_000:09d}"
    target = os.path.join(output_dir, f"{prefix}_{stamp}.jpg")

    try:
        from PIL import Image as PILImage, ImageOps
        with PILImage.open(source) as opened:
            try:
                opened.seek(0)
            except Exception:
                pass
            try:
                image = ImageOps.exif_transpose(opened)
            except Exception:
                image = opened.copy()
            if image.mode not in ("RGB", "L"):
                # Transparenz wird auf neutralem Weiß abgelegt, damit OCR keine
                # schwarzen Flächen aus Alpha-Kanälen erhält.
                if image.mode in ("RGBA", "LA"):
                    background = PILImage.new("RGB", image.size, (255, 255, 255))
                    alpha = image.getchannel("A")
                    background.paste(image.convert("RGB"), mask=alpha)
                    image = background
                else:
                    image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")
            max_side = max(image.size or (0, 0))
            if max_side > 4096:
                scale = 4096.0 / float(max_side)
                image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
            image.save(target, "JPEG", quality=94, optimize=True)
        if os.path.exists(target) and os.path.getsize(target) > 0:
            return target
    except Exception:
        pass

    if platform == "android":
        try:
            from jnius import autoclass
            BitmapFactory = autoclass("android.graphics.BitmapFactory")
            BitmapCompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
            FileOutputStream = autoclass("java.io.FileOutputStream")
            bitmap = BitmapFactory.decodeFile(source)
            if bitmap is not None:
                stream = FileOutputStream(target)
                try:
                    bitmap.compress(BitmapCompressFormat.JPEG, 94, stream)
                    stream.flush()
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass
                    try:
                        bitmap.recycle()
                    except Exception:
                        pass
                if os.path.exists(target) and os.path.getsize(target) > 0:
                    return target
        except Exception:
            pass

    # ML Kit kann manche Formate direkt lesen. In diesem Fall bleibt die
    # Originaldatei als letzter Fallback erhalten.
    return source


def start_android_camera_content_uri(output_dir, on_complete, on_error=None):
    """Startet die native Android-Kamera mit MediaStore-content:// URI.
    Fix für Android/Pyjnius: MediaStore.Images.Media wird als eigene Java-Klasse
    android.provider.MediaStore$Images$Media geladen. Dadurch entsteht nicht mehr
    der Fehler "MediaStore has no attribute Images".
    """
    if platform != "android":
        if on_error:
            on_error("Native Kamera ist nur auf Android verfügbar.")
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore")
        ImagesMedia = autoclass("android.provider.MediaStore$Images$Media")
        ContentValues = autoclass("android.content.ContentValues")
        Build = autoclass("android.os.Build")
        Activity = autoclass("android.app.Activity")
        Bundle = autoclass("android.os.Bundle")

        py_activity = PythonActivity.mActivity
        resolver = py_activity.getContentResolver()
        display_name = "just_incard_scan_%s.jpg" % time.strftime("%Y%m%d_%H%M%S")

        values = ContentValues()
        # Pyjnius liefert MediaStore.Images.Media.* Konstanten auf manchen Android-Builds
        # als None/null. Das erzeugt "Invalid column null". Darum nutzen wir hier
        # bewusst die stabilen Android-Spaltennamen als Strings.
        values.put("_display_name", display_name)
        values.put("mime_type", "image/jpeg")
        try:
            if int(Build.VERSION.SDK_INT) >= 29:
                values.put("relative_path", "Pictures/JustInCard")
        except Exception:
            pass

        image_uri = resolver.insert(ImagesMedia.EXTERNAL_CONTENT_URI, values)
        if image_uri is None:
            raise RuntimeError("MediaStore konnte keinen Bildspeicherplatz anlegen.")

        request_code = int(time.time()) % 50000 + 1200

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK):
                    if on_error:
                        on_error("Die Kamera wurde geschlossen, ohne ein Foto zu speichern.")
                    return
                target = copy_android_content_uri_to_file(image_uri, output_dir, "camera_scan")
                if target:
                    on_complete(target)
                elif on_error:
                    on_error("Das Foto konnte nicht aus Android MediaStore gelesen werden.")
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        # Originalqualität: Kamera schreibt direkt in eine MediaStore-content:// URI.
        # Wichtig: nicht über putExtra(String, Uri) gehen, weil Pyjnius auf manchen
        # Geräten die falsche Überladung wählt. Bundle.putParcelable erzwingt Uri/Parcelable.
        extras = Bundle()
        extras.putParcelable(MediaStore.EXTRA_OUTPUT, image_uri)
        intent.putExtras(extras)
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        py_activity.grantUriPermission(py_activity.getPackageName(), image_uri, Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception as exc:
        try:
            if on_error:
                on_error(str(exc))
        except Exception:
            pass
        return False



def start_android_camera_thumbnail(output_dir, on_complete, on_error=None):
    """Fallback ohne EXTRA_OUTPUT/content:// URI.
    Einige Kamera-Apps geben dann nur ein kleines Bitmap-Thumbnail zurück, aber es ist
    sehr stabil und vermeidet FileUriExposed/MediaStore-Probleme. Dieses Thumbnail wird
    als lokale JPG-Datei gespeichert und kann im Scanner ausgerichtet werden.
    """
    if platform != "android":
        if on_error:
            on_error("Native Kamera ist nur auf Android verfügbar.")
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore")
        Activity = autoclass("android.app.Activity")
        BitmapCompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
        FileOutputStream = autoclass("java.io.FileOutputStream")

        py_activity = PythonActivity.mActivity
        request_code = int(time.time()) % 50000 + 8200

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK) or data is None:
                    if on_error:
                        on_error("Die Kamera wurde geschlossen, ohne ein Foto zurückzugeben.")
                    return
                extras = data.getExtras()
                if extras is None:
                    if on_error:
                        on_error("Die Kamera hat kein Bild zurückgegeben.")
                    return
                bitmap = extras.get("data")
                if bitmap is None:
                    if on_error:
                        on_error("Die Kamera hat kein Bild-Thumbnail zurückgegeben.")
                    return
                os.makedirs(output_dir, exist_ok=True)
                target = os.path.join(output_dir, "camera_thumb_%s.jpg" % time.strftime("%Y%m%d_%H%M%S"))
                stream = FileOutputStream(target)
                try:
                    bitmap.compress(BitmapCompressFormat.JPEG, 95, stream)
                    stream.flush()
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass
                if os.path.exists(target) and os.path.getsize(target) > 0:
                    on_complete(target)
                elif on_error:
                    on_error("Das Kamera-Thumbnail konnte nicht gespeichert werden.")
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception as exc:
        if on_error:
            try:
                on_error(str(exc))
            except Exception:
                pass
        return False

def start_android_camerax_capture(on_complete, on_error=None):
    """Startet die optionale native CameraX-Aktivität.

    v9.2: Das native Java-Modul ist im Standard-GitHub-Build deaktiviert, weil es
    den Buildozer/p4a-Build in v9.1 instabil gemacht hat. Fehlt die Klasse, wird
    ohne Fehlermeldungs-Popup sauber auf MediaStore/Android-Kamera zurückgefallen.
    """
    if platform != "android":
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        try:
            CameraXActivity = autoclass("org.yugioh.kartenliste.CameraXScanActivity")
        except Exception:
            # Erwarteter Fall im stabilen Standard-Build: native Erweiterung fehlt.
            return False
        Intent = autoclass("android.content.Intent")
        Activity = autoclass("android.app.Activity")
        py_activity = PythonActivity.mActivity
        request_code = int(time.time()) % 50000 + 9100

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK) or data is None:
                    message = "Native CameraX-Aufnahme wurde abgebrochen."
                    if data is not None:
                        try:
                            message = str(data.getStringExtra("camera_error") or message)
                        except Exception:
                            pass
                    if on_error:
                        on_error(message)
                    return
                path = str(data.getStringExtra("image_path") or "")
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    on_complete(path)
                elif on_error:
                    on_error("CameraX hat keine lesbare Bilddatei zurückgegeben.")
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent = Intent(py_activity, CameraXActivity)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception:
        # Standard-Fallback wird vom Aufrufer gestartet; kein doppeltes Fehlerfenster.
        return False


def schedule_android_scan_resume_worker(queue_id):
    """Plant optional einen nativen Resume-Worker; fällt ohne Java-Modul lautlos zurück."""
    if platform != "android" or not queue_id:
        return False
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        try:
            Bridge = autoclass("org.yugioh.kartenliste.AndroidBridge")
        except Exception:
            return False
        Bridge.scheduleScanResumeWorker(PythonActivity.mActivity, str(queue_id))
        return True
    except Exception:
        return False


def cancel_android_scan_resume_worker(queue_id):
    if platform != "android" or not queue_id:
        return False
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Bridge = autoclass("org.yugioh.kartenliste.AndroidBridge")
        Bridge.cancelScanResumeWorker(PythonActivity.mActivity, str(queue_id))
        return True
    except Exception:
        return False


def _build_android_photo_picker_intent(multiple=False, max_items=150):
    """Erstellt bevorzugt den Android Photo Picker und fällt auf SAF zurück."""
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    MediaStore = autoclass("android.provider.MediaStore")
    BuildVersion = autoclass("android.os.Build$VERSION")
    sdk = int(BuildVersion.SDK_INT)

    if sdk >= 33:
        try:
            intent = Intent(MediaStore.ACTION_PICK_IMAGES)
            intent.setType("image/*")
            if multiple:
                try:
                    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
                except Exception:
                    pass
                try:
                    intent.putExtra(MediaStore.EXTRA_PICK_IMAGES_MAX, max(2, min(int(max_items or 150), 250)))
                except Exception:
                    pass
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            return intent, True
        except Exception:
            pass

    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("image/*")
    if multiple:
        try:
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
        except Exception:
            pass
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
    return intent, False


def start_android_image_picker(output_dir, on_complete, on_error=None):
    """Öffnet den offiziellen Android Photo Picker mit SAF-Fallback."""
    if platform != "android":
        if on_error:
            on_error("Galerie ist nur auf Android verfügbar.")
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Activity = autoclass("android.app.Activity")

        py_activity = PythonActivity.mActivity
        request_code = int(time.time()) % 50000 + 6200

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK) or data is None:
                    if on_error:
                        on_error("Es wurde kein Bild ausgewählt.")
                    return
                uri = data.getData()
                if uri is None:
                    clip = data.getClipData()
                    if clip is not None and int(clip.getItemCount()) > 0:
                        uri = clip.getItemAt(0).getUri()
                if uri is None:
                    if on_error:
                        on_error("Die Galerie hat keine Bild-URI zurückgegeben.")
                    return
                try:
                    flags = data.getFlags()
                    take_flags = flags & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    py_activity.getContentResolver().takePersistableUriPermission(uri, take_flags)
                except Exception:
                    pass
                target = copy_android_content_uri_to_file(uri, output_dir, "gallery_scan")
                if target:
                    on_complete(target)
                elif on_error:
                    on_error("Das ausgewählte Bild konnte nicht gelesen werden.")
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent, _is_photo_picker = _build_android_photo_picker_intent(multiple=False)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception as exc:
        try:
            if on_error:
                on_error(str(exc))
        except Exception:
            pass
        return False


def start_android_multi_image_picker(output_dir, on_complete, on_error=None):
    """Offizieller Android Photo Picker mit Mehrfachauswahl und SAF-Fallback.

    Einzelne beschädigte oder nicht lesbare URIs werden übersprungen. Dadurch
    kann der restliche Sammelimport weiterlaufen.
    """
    if platform != "android":
        if on_error:
            on_error("Mehrfach-Galerie ist nur auf Android verfügbar.")
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Activity = autoclass("android.app.Activity")

        py_activity = PythonActivity.mActivity
        request_code = int(time.time()) % 50000 + 7200

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK) or data is None:
                    if on_error:
                        on_error("Es wurden keine Bilder ausgewählt.")
                    return

                uris = []
                clip = None
                try:
                    clip = data.getClipData()
                except Exception:
                    clip = None
                if clip is not None:
                    for idx in range(int(clip.getItemCount())):
                        try:
                            uri = clip.getItemAt(idx).getUri()
                            if uri is not None:
                                uris.append(uri)
                        except Exception:
                            continue
                try:
                    single_uri = data.getData()
                    if single_uri is not None and not uris:
                        uris.append(single_uri)
                except Exception:
                    pass

                if not uris:
                    if on_error:
                        on_error("Die Galerie hat keine Bild-URI zurückgegeben.")
                    return

                copied_paths = []
                resolver = py_activity.getContentResolver()
                try:
                    flags = data.getFlags()
                    take_flags = flags & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                except Exception:
                    take_flags = 0

                for idx, uri in enumerate(uris):
                    try:
                        if take_flags:
                            try:
                                resolver.takePersistableUriPermission(uri, take_flags)
                            except Exception:
                                pass
                        target = copy_android_content_uri_to_file(uri, output_dir, f"gallery_bulk_{idx + 1}")
                        if target and os.path.exists(target) and os.path.getsize(target) > 0:
                            copied_paths.append(target)
                    except Exception:
                        continue

                if copied_paths:
                    on_complete(copied_paths)
                elif on_error:
                    on_error("Die ausgewählten Bilder konnten nicht gelesen werden.")
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent, _is_photo_picker = _build_android_photo_picker_intent(multiple=True, max_items=250)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception as exc:
        try:
            if on_error:
                on_error(str(exc))
        except Exception:
            pass
        return False



def start_android_create_document(source_path, mime_type, suggested_name, on_complete=None, on_error=None):
    """Speichert eine vorhandene Datei über Androids Storage Access Framework."""
    if platform != "android":
        if on_complete:
            on_complete(source_path)
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Activity = autoclass("android.app.Activity")
        py_activity = PythonActivity.mActivity
        request_code = int(time.time()) % 50000 + 8300

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK) or data is None or data.getData() is None:
                    if on_error:
                        on_error("Speichern wurde abgebrochen.")
                    return
                uri = data.getData()
                stream = py_activity.getContentResolver().openOutputStream(uri, "w")
                if stream is None:
                    raise RuntimeError("Android konnte den Zielspeicher nicht öffnen.")
                try:
                    with open(source_path, "rb") as handle:
                        while True:
                            chunk = handle.read(64 * 1024)
                            if not chunk:
                                break
                            stream.write(chunk)
                    stream.flush()
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass
                if on_complete:
                    on_complete(str(uri.toString()))
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType(str(mime_type or "application/octet-stream"))
        intent.putExtra(Intent.EXTRA_TITLE, str(suggested_name or os.path.basename(source_path)))
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception as exc:
        if on_error:
            try:
                on_error(str(exc))
            except Exception:
                pass
        return False


def start_android_document_picker(output_dir, mime_type="application/zip", prefix="import", on_complete=None, on_error=None):
    """Öffnet Androids Storage Access Framework für beliebige Importdateien.

    Die ausgewählte content://-Datei wird zuerst in den App-Speicher kopiert.
    Dadurch kann die Wiederherstellung auch nach dem Schließen des Pickers sicher
    und ohne dauerhaft offene Android-URI erfolgen.
    """
    if platform != "android":
        if on_error:
            on_error("Der Android-Dateidialog ist nur auf Android verfügbar.")
        return False
    try:
        from jnius import autoclass
        from android import activity as android_activity
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Activity = autoclass("android.app.Activity")
        py_activity = PythonActivity.mActivity
        request_code = int(time.time()) % 50000 + 8600

        def result_callback(req, result, data):
            if int(req) != request_code:
                return
            try:
                android_activity.unbind(on_activity_result=result_callback)
            except Exception:
                pass
            try:
                if int(result) != int(Activity.RESULT_OK) or data is None or data.getData() is None:
                    if on_error:
                        on_error("Es wurde keine Datei ausgewählt.")
                    return
                uri = data.getData()
                try:
                    flags = data.getFlags()
                    take_flags = flags & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    py_activity.getContentResolver().takePersistableUriPermission(uri, take_flags)
                except Exception:
                    pass
                target = copy_android_content_uri_to_file(uri, output_dir, prefix)
                if target:
                    if on_complete:
                        on_complete(target)
                elif on_error:
                    on_error("Die ausgewählte Datei konnte nicht gelesen werden.")
            except Exception as exc:
                if on_error:
                    on_error(str(exc))

        android_activity.bind(on_activity_result=result_callback)
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType(str(mime_type or "application/octet-stream"))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        py_activity.startActivityForResult(intent, request_code)
        return True
    except Exception as exc:
        if on_error:
            try:
                on_error(str(exc))
            except Exception:
                pass
        return False


def android_is_unmetered_network():
    """Erkennt WLAN/Ethernet defensiv; außerhalb Android wird True geliefert."""
    if platform != "android":
        return True
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        NetworkCapabilities = autoclass("android.net.NetworkCapabilities")
        activity = PythonActivity.mActivity
        manager = activity.getSystemService(Context.CONNECTIVITY_SERVICE)
        network = manager.getActiveNetwork()
        if network is None:
            return False
        capabilities = manager.getNetworkCapabilities(network)
        if capabilities is None:
            return False
        return bool(
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            or capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
        )
    except Exception:
        # Auf älteren Hersteller-ROMs lieber nicht fälschlich alle Bilder sperren.
        return True


THEMES = {
    "dark": {
        "window": STARTUP_BG,
        "panel": (0.035, 0.047, 0.074, 1),
        "panel2": (0.050, 0.067, 0.105, 1),
        "card": (0.066, 0.086, 0.132, 1),
        "input": (0.027, 0.038, 0.062, 1),
        "input2": (0.086, 0.112, 0.174, 1),
        "border": (0.190, 0.248, 0.370, 0.88),
        "text": (0.970, 0.978, 0.995, 1),
        "muted": (0.650, 0.700, 0.800, 1),
        "hint": (0.510, 0.570, 0.680, 1),
        "accent": (0.315, 0.490, 0.980, 1),
        "accent2": (0.100, 0.165, 0.300, 1),
        "success": (0.120, 0.690, 0.520, 1),
        "danger": (0.900, 0.315, 0.390, 1),
        "gold": (0.955, 0.700, 0.250, 1),
        "popup": (0.025, 0.035, 0.058, 0.995),
    },
    "light": {
        "window": (0.955, 0.967, 0.985, 1),
        "panel": (0.992, 0.996, 1.000, 1),
        "panel2": (0.925, 0.944, 0.977, 1),
        "card": (0.975, 0.983, 0.996, 1),
        "input": (0.945, 0.960, 0.986, 1),
        "input2": (0.850, 0.892, 0.960, 1),
        "border": (0.420, 0.505, 0.650, 0.78),
        "text": (0.035, 0.052, 0.090, 1),
        "muted": (0.295, 0.350, 0.455, 1),
        "hint": (0.390, 0.450, 0.560, 1),
        "accent": (0.130, 0.345, 0.850, 1),
        "accent2": (0.790, 0.850, 0.945, 1),
        "success": (0.050, 0.545, 0.400, 1),
        "danger": (0.760, 0.135, 0.210, 1),
        "gold": (0.790, 0.505, 0.065, 1),
        "popup": (0.995, 0.997, 1.000, 0.998),
    },
    "colorblind": {
        "window": (0.018, 0.027, 0.041, 1),
        "panel": (0.040, 0.060, 0.082, 1),
        "panel2": (0.060, 0.083, 0.112, 1),
        "card": (0.080, 0.108, 0.143, 1),
        "input": (0.030, 0.046, 0.065, 1),
        "input2": (0.115, 0.155, 0.205, 1),
        "border": (0.430, 0.650, 0.820, 0.92),
        "text": (0.990, 0.990, 0.965, 1),
        "muted": (0.760, 0.815, 0.865, 1),
        "hint": (0.690, 0.755, 0.825, 1),
        "accent": (0.000, 0.620, 0.830, 1),
        "accent2": (0.155, 0.220, 0.285, 1),
        "success": (0.000, 0.620, 0.830, 1),
        "danger": (0.980, 0.630, 0.000, 1),
        "gold": (0.980, 0.630, 0.000, 1),
        "popup": (0.030, 0.045, 0.064, 0.995),
    },
}


# Aktive Palette. Wird beim Umschalten neu gesetzt.
DARK_BG = THEMES["dark"]["window"]
PANEL_BG = THEMES["dark"]["panel"]
PANEL_BG_2 = THEMES["dark"]["panel2"]
CARD_BG = THEMES["dark"]["card"]
INPUT_BG = THEMES["dark"]["input"]
INPUT_BG_2 = THEMES["dark"]["input2"]
BORDER = THEMES["dark"]["border"]
TEXT = THEMES["dark"]["text"]
MUTED = THEMES["dark"]["muted"]
HINT = THEMES["dark"]["hint"]
ACCENT = THEMES["dark"]["accent"]
ACCENT_2 = THEMES["dark"]["accent2"]
SUCCESS = THEMES["dark"]["success"]
DANGER = THEMES["dark"]["danger"]
GOLD = THEMES["dark"]["gold"]
POPUP_BG = THEMES["dark"]["popup"]


def markup_hex(color):
    """Konvertiert eine RGBA-Palette in eine Kivy-Markup-Farbe."""
    try:
        values = [max(0, min(255, int(round(float(channel) * 255)))) for channel in color[:3]]
        return "#" + "".join(f"{value:02X}" for value in values)
    except Exception:
        return "#FFFFFF"


def set_palette(name):
    global DARK_BG, PANEL_BG, PANEL_BG_2, CARD_BG, INPUT_BG, INPUT_BG_2
    global BORDER, TEXT, MUTED, HINT, ACCENT, ACCENT_2, SUCCESS, DANGER, GOLD, POPUP_BG
    theme = THEMES.get(name, THEMES["dark"])
    DARK_BG = theme["window"]
    PANEL_BG = theme["panel"]
    PANEL_BG_2 = theme["panel2"]
    CARD_BG = theme["card"]
    INPUT_BG = theme["input"]
    INPUT_BG_2 = theme["input2"]
    BORDER = theme["border"]
    TEXT = theme["text"]
    MUTED = theme["muted"]
    HINT = theme["hint"]
    ACCENT = theme["accent"]
    ACCENT_2 = theme["accent2"]
    SUCCESS = theme["success"]
    DANGER = theme["danger"]
    GOLD = theme["gold"]
    POPUP_BG = theme["popup"]


CATEGORY_ORDER = [
    "Normalmonster",
    "Effektmonster",
    "Pendelmonster",
    "Ritual",
    "Fusion",
    "Synchro",
    "XYZ",
    "Link",
    "Zauber - Normal",
    "Zauber - Schnellzauber",
    "Zauber - Ausrüstung",
    "Zauber - Spielfeld",
    "Zauber - Permanent",
    "Zauber - Ritual",
    "Zauber - Sonstige",
    "Falle - Normal",
    "Falle - Permanent",
    "Falle - Konter",
    "Falle - Sonstige",
    "Sonstige",
]

SPELL_RACE_MAP = {
    "Normal": "Zauber - Normal",
    "Quick-Play": "Zauber - Schnellzauber",
    "Equip": "Zauber - Ausrüstung",
    "Field": "Zauber - Spielfeld",
    "Continuous": "Zauber - Permanent",
    "Ritual": "Zauber - Ritual",
}

TRAP_RACE_MAP = {
    "Normal": "Falle - Normal",
    "Continuous": "Falle - Permanent",
    "Counter": "Falle - Konter",
}

# Anzeige komplett auf Deutsch. Die API bekommt intern weiterhin die englischen Codes.
ATTRIBUTES = ["Eigenschaft", "Dunkel", "Licht", "Erde", "Wasser", "Feuer", "Wind", "Göttlich"]
ATTRIBUTE_API_MAP = {
    "": "", "Eigenschaft": "",
    "Dunkel": "DARK", "Dark": "DARK", "DARK": "DARK",
    "Licht": "LIGHT", "Light": "LIGHT", "LIGHT": "LIGHT",
    "Erde": "EARTH", "Earth": "EARTH", "EARTH": "EARTH",
    "Wasser": "WATER", "Water": "WATER", "WATER": "WATER",
    "Feuer": "FIRE", "Fire": "FIRE", "FIRE": "FIRE",
    "Wind": "WIND", "WIND": "WIND",
    "Göttlich": "DIVINE", "Goettlich": "DIVINE", "Divine": "DIVINE", "DIVINE": "DIVINE",
}
ATTRIBUTE_DISPLAY_MAP = {v: k for k, v in ATTRIBUTE_API_MAP.items() if v and k in ATTRIBUTES}
GROUPS = [
    "Alle",
    "Monster", "Normalmonster", "Effektmonster", "Pendelmonster", "Ritualmonster",
    "Fusionsmonster", "Synchromonster", "Xyz-Monster", "Linkmonster", "Toonmonster", "Spiritmonster", "Unionmonster", "Gemini-Monster", "Flipmonster", "Empfänger/Tuner", "Token", "Extra Deck",
    "Zauberkarten", "Normale Zauber", "Schnellzauber", "Ausrüstungszauber", "Spielfeldzauber", "Permanente Zauber", "Ritualzauber",
    "Fallenkarten", "Normale Fallen", "Permanente Fallen", "Konterfallen",
]
GROUP_API_MAP = {
    "Alle": "Alle", "": "Alle",
    "Monster": "Monster", "Normalmonster": "Normalmonster", "Effektmonster": "Effektmonster",
    "Pendel": "Pendelmonster", "Pendelmonster": "Pendelmonster", "Ritualmonster": "Ritualmonster",
    "Fusion": "Fusionsmonster", "Fusionsmonster": "Fusionsmonster", "Synchro": "Synchromonster", "Synchromonster": "Synchromonster",
    "XYZ": "Xyz-Monster", "Xyz": "Xyz-Monster", "Xyz-Monster": "Xyz-Monster", "Link": "Linkmonster", "Linkmonster": "Linkmonster",
    "Extra": "Extra Deck", "Extra Deck": "Extra Deck",
    "Toon": "Toonmonster", "Toonmonster": "Toonmonster", "Spirit": "Spiritmonster", "Spiritmonster": "Spiritmonster",
    "Union": "Unionmonster", "Unionmonster": "Unionmonster", "Gemini": "Gemini-Monster", "Gemini-Monster": "Gemini-Monster",
    "Flip": "Flipmonster", "Flipmonster": "Flipmonster", "Tuner": "Empfänger/Tuner", "Empfänger/Tuner": "Empfänger/Tuner",
    "Empfaenger/Tuner": "Empfänger/Tuner", "Token": "Token",
    "Zauber": "Zauberkarten", "Zauberkarten": "Zauberkarten", "Normale Zauber": "Normale Zauber", "Schnellzauber": "Schnellzauber",
    "Ausrüstungszauber": "Ausrüstungszauber", "Spielfeldzauber": "Spielfeldzauber", "Permanente Zauber": "Permanente Zauber", "Ritualzauber": "Ritualzauber",
    "Falle": "Fallenkarten", "Fallenkarten": "Fallenkarten", "Normale Fallen": "Normale Fallen", "Permanente Fallen": "Permanente Fallen", "Konterfallen": "Konterfallen",
}
RACE_API_MAP = {
    "drache": "Dragon", "dragon": "Dragon",
    "hexer": "Spellcaster", "magier": "Spellcaster", "spellcaster": "Spellcaster",
    "krieger": "Warrior", "warrior": "Warrior",
    "maschine": "Machine", "machine": "Machine",
    "fee": "Fairy", "fairy": "Fairy",
    "unterweltler": "Fiend", "fiend": "Fiend",
    "zombie": "Zombie",
    "fels": "Rock", "rock": "Rock",
    "pflanze": "Plant", "plant": "Plant",
    "insekt": "Insect", "insect": "Insect",
    "dinosaurier": "Dinosaur", "dinosaur": "Dinosaur",
    "reptil": "Reptile", "reptile": "Reptile",
    "fisch": "Fish", "fish": "Fish",
    "seeschlange": "Sea Serpent", "sea serpent": "Sea Serpent",
    "aqua": "Aqua", "wasser": "Aqua",
    "pyro": "Pyro", "feuer": "Pyro",
    "donner": "Thunder", "thunder": "Thunder",
    "geflügeltes ungeheuer": "Winged Beast", "gefluegeltes ungeheuer": "Winged Beast", "winged beast": "Winged Beast",
    "ungeheuer": "Beast", "beast": "Beast",
    "ungeheuer-krieger": "Beast-Warrior", "beast-warrior": "Beast-Warrior",
    "cyberse": "Cyberse",
    "wyrm": "Wyrm",
    "göttlich": "Divine-Beast", "goettlich": "Divine-Beast", "divine-beast": "Divine-Beast",
}

def attribute_to_api(value):
    return ATTRIBUTE_API_MAP.get(str(value or "").strip(), str(value or "").strip().upper())

def group_to_api(value):
    return GROUP_API_MAP.get(str(value or "").strip(), str(value or "").strip())

def race_to_api(value):
    raw = str(value or "").strip()
    return RACE_API_MAP.get(normalize_search_text(raw), raw)
LANGUAGES = ["Deutsch", "Englisch", "Französisch", "Italienisch", "Portugiesisch", "Spanisch", "Japanisch", "Koreanisch", "Chinesisch"]
LANGUAGE_CODES = {
    "Deutsch": "de",
    "Englisch": "",
    "Französisch": "fr",
    "Italienisch": "it",
    "Portugiesisch": "pt",
    "Spanisch": "es",
    "Japanisch": "ja",
    "Koreanisch": "ko",
    "Chinesisch": "zh",
}

# Sprachen, die beim Galerie-Sammelimport automatisch durchsucht werden.
# "" bedeutet YGOPRODeck-Standardsprache Englisch.
# Zusätzlich zu den UI-Sprachen werden weitere verfügbare Lokalisationen genutzt,
# damit OCR-Treffer auch bei importierten internationalen Karten besser erkannt werden.
SCAN_SEARCH_LANGUAGE_CODES = list(CARD_LANGUAGE_CODES_V102)

def scan_language_label(language_code):
    return CARD_LANGUAGE_LABELS_V102.get(language_code, language_code or "Englisch")


def expand_scan_ocr_chars(value, replacements, limit=8):
    """Erzeugt wenige kontrollierte OCR-Varianten für mehrsprachige Scan-Treffer.

    Beispiel: DAB1-DEO42 -> DABL-DE042 / DABI-DE042.
    Die Anzahl wird bewusst klein gehalten, damit der Scan trotz zusätzlicher
    Korrekturvarianten stabil bleibt.
    """
    value = str(value or "")
    results = [""]
    for ch in value:
        options = replacements.get(ch, [ch])
        if not isinstance(options, (list, tuple, set)):
            options = [options]
        next_results = []
        for prefix in results:
            for option in options:
                item = prefix + str(option)
                if item not in next_results:
                    next_results.append(item)
                if len(next_results) >= int(limit or 8):
                    break
            if len(next_results) >= int(limit or 8):
                break
        results = next_results or results
    unique = []
    seen = set()
    for item in results:
        item = str(item or "")
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[: int(limit or 8)]


def build_scan_code_aliases(raw_value):
    """Liefert wenige plausible Set-Code-Korrekturen für OCR-Fehler.

    Die Struktur wird vor der Zeichenkorrektur getrennt, damit ein Code wie
    DAB1-DEO42 nicht versehentlich zu einem falschen Präfix zerlegt wird.
    """
    raw = re.sub(r"\s+", "", str(raw_value or "").upper())
    raw = raw.replace("_", "-").replace("/", "-")
    raw = re.sub(r"[^A-Z0-9\-]", "", raw)
    if not raw:
        return []

    aliases = []
    seen = set()
    allowed_langs = {"DE", "EN", "FR", "IT", "PT", "ES", "SP", "JP", "KR", "AE", "EU", "NA"}

    def add(value):
        value = str(value or "").strip("-")
        value = re.sub(r"-{2,}", "-", value)
        if not value or value in seen:
            return
        seen.add(value)
        aliases.append(value)

    broad = re.sub(r"[^A-Z0-9]", "", raw)
    # Wichtig: freie OCR-Wörter wie DE008DIESER dürfen nicht ungeprüft als
    # Set-Code in die Suche gelangen. Der Rohwert wird nur übernommen, wenn
    # bereits eine plausible Set-Code-Struktur mit numerischem Ende vorliegt.
    if re.fullmatch(r"[A-Z0-9]{2,10}-(?:(?:DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA))?[A-Z0-9]{1,4}", raw):
        add(raw)

    alpha_map = {
        "0": ["0", "O"],
        "1": ["1", "I", "L"],
        "2": ["2", "Z"],
        "5": ["5", "S"],
        "6": ["6", "G"],
        "8": ["8", "B"],
    }
    digit_translation = str.maketrans({
        "O": "0", "Q": "0", "D": "0", "C": "0",
        "I": "1", "L": "1", "Z": "2",
        "S": "5", "G": "6", "B": "8",
    })

    structures = []
    if "-" in raw:
        prefix_raw, suffix_raw = raw.split("-", 1)
        if 2 <= len(prefix_raw) <= 12:
            if len(suffix_raw) >= 3:
                structures.append((prefix_raw, suffix_raw[:2], suffix_raw[2:]))
            structures.append((prefix_raw, "", suffix_raw))
    else:
        # Sprachcode möglichst nahe am Ende suchen; drei Ziffern sind bei Sets am häufigsten.
        for number_len in (3, 4):
            lang_pos = len(broad) - number_len - 2
            if 2 <= lang_pos <= 12:
                prefix_raw = broad[:lang_pos]
                lang_raw = broad[lang_pos:lang_pos + 2]
                number_raw = broad[lang_pos + 2:]
                structures.append((prefix_raw, lang_raw, number_raw))
        # Ohne Sprachcode ist die typische Kartennummer dreistellig.
        split_pos = len(broad) - 3
        if 2 <= split_pos <= 12:
            structures.append((broad[:split_pos], "", broad[split_pos:]))

    for prefix_raw, lang_raw, number_raw in structures:
        if not prefix_raw or not number_raw or sum(ch.isalpha() for ch in prefix_raw) < 2:
            continue
        prefix_options = expand_scan_ocr_chars(prefix_raw, alpha_map, limit=8) or [prefix_raw]
        lang_options = expand_scan_ocr_chars(lang_raw, alpha_map, limit=8) if lang_raw else [""]
        lang_options = [lang for lang in lang_options if not lang or lang in allowed_langs]
        if lang_raw and not lang_options:
            continue
        number = str(number_raw).translate(digit_translation)
        if not number.isdigit() or not (1 <= len(number) <= 4):
            continue
        number = number.zfill(3)
        for prefix in prefix_options:
            corrected_prefixes = [prefix]
            if prefix.endswith("I"):
                corrected_prefixes.append(prefix[:-1] + "L")
            for corrected_prefix in corrected_prefixes:
                for lang in lang_options or [""]:
                    suffix = f"{lang}{number}" if lang else number
                    add(f"{corrected_prefix}-{suffix}")
                    if len(aliases) >= 12:
                        return aliases[:12]
    return aliases[:12]


def build_scan_name_aliases(raw_value):
    """Kleine Hilfsvarianten für OCR-Namen ohne zu viele Dubletten."""
    value = re.sub(r"\s+", " ", str(raw_value or "").strip())
    if not value:
        return []
    aliases = []
    seen = set()
    def add(item):
        item = re.sub(r"\s+", " ", str(item or "").strip(" -.,;:"))
        if not item:
            return
        sig = normalize_search_text(item)
        if not sig or sig in seen:
            return
        seen.add(sig)
        aliases.append(item)
    add(value)
    fixed = value.replace("|", "I").replace("0", "O")
    fixed = re.sub(r"\b1\b", "I", fixed)
    fixed = fixed.replace("’", "'")
    add(fixed)
    title = " ".join(part.capitalize() if part.islower() else part for part in fixed.split())
    add(title)
    return aliases[:4]


RARITY_ORDER = [
    "Common",
    "Short Print",
    "Super Short Print",
    "Rare",
    "Super Rare",
    "Ultra Rare",
    "Ultimate Rare",
    "Secret Rare",
    "Prismatic Secret Rare",
    "Platinum Secret Rare",
    "Quarter Century Secret Rare",
    "Ghost Rare",
    "Ghost/Gold Rare",
    "Gold Rare",
    "Gold Secret Rare",
    "Premium Gold Rare",
    "Collector's Rare",
    "Starlight Rare",
    "Mosaic Rare",
    "Parallel Rare",
    "Duel Terminal Normal Parallel Rare",
    "Duel Terminal Rare Parallel Rare",
    "Duel Terminal Super Parallel Rare",
    "Duel Terminal Ultra Parallel Rare",
    "Duel Terminal Secret Parallel Rare",
]

RARITY_ACCENT = {
    "Ghost Rare": GOLD,
    "Ghost/Gold Rare": GOLD,
    "Starlight Rare": GOLD,
    "Quarter Century Secret Rare": GOLD,
    "Collector's Rare": ACCENT,
    "Ultimate Rare": ACCENT,
    "Prismatic Secret Rare": ACCENT,
    "Secret Rare": ACCENT_2,
    "Ultra Rare": ACCENT_2,
    "Super Rare": SUCCESS,
}


def clean_filename(text):
    text = re.sub(r"[^A-Za-z0-9_äöüÄÖÜß -]+", "_", str(text)).strip()
    return text or "datei"


def short_text(value, length=85):
    value = str(value or "")
    return value if len(value) <= length else value[: length - 3] + "..."


def rarity_sort_key(card_set):
    rarity = (card_set.get("set_rarity") or "").strip()
    try:
        rarity_idx = RARITY_ORDER.index(rarity)
    except ValueError:
        rarity_idx = 999
    return (rarity_idx, (card_set.get("set_name") or "").lower(), card_set.get("set_code") or "")


def rarity_summary(card, limit=5):
    card_sets = card.get("card_sets") or []
    rarities = []
    for item in card_sets:
        rarity = (item.get("set_rarity") or "Unbekannt").strip() or "Unbekannt"
        if rarity not in rarities:
            rarities.append(rarity)
    if not rarities:
        return "Keine Set-/Rarity-Daten"
    text = ", ".join(rarities[:limit])
    if len(rarities) > limit:
        text += f" +{len(rarities) - limit} weitere"
    return text


def rarity_color(rarity):
    return RARITY_ACCENT.get(rarity, INPUT_BG_2)


def get_card_id(card):
    base = str(card.get("id") or card.get("name") or "unknown")
    variant = card.get("_variant_key")
    if variant and str(variant) != base:
        return f"{base}__artwork_{variant}"
    return base


def get_image_url(card):
    artwork = card.get("_artwork_image")
    if isinstance(artwork, dict):
        return artwork.get("image_url") or artwork.get("image_url_small") or ""
    images = card.get("card_images") or []
    if images:
        return images[0].get("image_url") or images[0].get("image_url_small") or ""
    return ""


def get_artwork_images(card):
    images = card.get("card_images") or []
    # Duplikate nach Bild-ID/URL entfernen, damit dasselbe Artwork nicht mehrfach angezeigt wird.
    unique = []
    seen = set()
    for image in images:
        key = str(image.get("id") or image.get("image_url") or image.get("image_url_small") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(image)
    return unique


def artwork_count(card):
    return max(1, len(get_artwork_images(card)))


def artwork_label(card):
    total = int(card.get("_artwork_total") or artwork_count(card))
    idx = int(card.get("_artwork_index") or 0) + 1
    if total <= 1:
        return "Standard-Artwork"
    return f"Artwork {idx}/{total}"


def expand_artwork_variants(cards):
    """Erzeugt eigenständige Suchtreffer pro Artwork.
    Sets/Rarities bleiben als Beschreibung am jeweiligen Artwork erhalten.
    Hinweis: Die API liefert keine eindeutige Set-Code-zu-Artwork-Zuordnung; daher werden
    die bekannten Set-Einträge bei jedem Artwork als Reprint-Info angezeigt.
    """
    expanded = []
    for card in cards:
        images = get_artwork_images(card)
        if len(images) <= 1:
            clone = dict(card)
            clone["_artwork_index"] = 0
            clone["_artwork_total"] = 1
            if images:
                clone["_artwork_image"] = images[0]
                clone["_variant_key"] = str(images[0].get("id") or get_card_id(card))
            else:
                clone["_variant_key"] = get_card_id(card)
            expanded.append(clone)
            continue
        for idx, image in enumerate(images):
            clone = dict(card)
            clone["_artwork_index"] = idx
            clone["_artwork_total"] = len(images)
            clone["_artwork_image"] = image
            clone["_variant_key"] = str(image.get("id") or f"{get_card_id(card)}-art{idx + 1}")
            expanded.append(clone)
    return expanded


def set_entries_text(card, limit=10):
    entries = sorted(card.get("card_sets") or [], key=rarity_sort_key)
    if not entries:
        return "Keine Set-/Reprint-Daten vorhanden."
    lines = []
    for item in entries[:limit]:
        set_name = item.get("set_name", "Unbekanntes Set") or "Unbekanntes Set"
        set_code = item.get("set_code", "-") or "-"
        rarity = item.get("set_rarity", "Unbekannt") or "Unbekannt"
        lines.append(f"• {set_name} — {set_code} — {rarity}")
    if len(entries) > limit:
        lines.append(f"… +{len(entries) - limit} weitere Sets/Reprints über den Reprints/Rarity-Button")
    return "\n".join(lines)


def get_level_value(card):
    if card.get("level") is not None:
        return card.get("level")
    if card.get("linkval") is not None:
        return card.get("linkval")
    return ""


def is_pendulum_card(card):
    ctype = str(card.get("type", "") or "")
    frame = str(card.get("frameType", "") or "")
    return "Pendulum" in ctype or "pendulum" in frame.lower() or get_pendulum_scale(card) not in ("", None)


def get_pendulum_scale(card):
    for key in ("scale", "pendulumScale", "pendulum_scale", "lscale", "rscale", "leftScale", "rightScale"):
        value = card.get(key)
        if value not in (None, ""):
            return value
    return ""


def pendulum_text(card):
    scale = get_pendulum_scale(card)
    return str(scale) if scale not in (None, "") else "-"


def category_for(card):
    ctype = card.get("type", "") or ""
    race = card.get("race", "") or ""

    if "Spell Card" in ctype:
        return SPELL_RACE_MAP.get(race, "Zauber - Sonstige")
    if "Trap Card" in ctype:
        return TRAP_RACE_MAP.get(race, "Falle - Sonstige")

    if is_pendulum_card(card):
        return "Pendelmonster"
    if "Ritual" in ctype:
        return "Ritual"
    if "Fusion" in ctype:
        return "Fusion"
    if "Synchro" in ctype:
        return "Synchro"
    if "XYZ" in ctype or "Xyz" in ctype:
        return "XYZ"
    if "Link" in ctype:
        return "Link"

    if "Monster" in ctype:
        if "Normal" in ctype and "Effect" not in ctype:
            return "Normalmonster"
        return "Effektmonster"

    return "Sonstige"


def category_sort_key(card):
    category = category_for(card)
    try:
        cat_index = CATEGORY_ORDER.index(category)
    except ValueError:
        cat_index = 999
    level = get_level_value(card)
    try:
        level_sort = int(level)
    except Exception:
        level_sort = 999
    return (cat_index, level_sort, (card.get("name") or "").lower())


def card_matches_group(card, group):
    group = group_to_api(group)
    if group in ("", "Alle"):
        return True
    ctype = str(card.get("type", "") or "")
    race = str(card.get("race", "") or "")
    frame = str(card.get("frameType", "") or "")
    if group == "Monster":
        return "Monster" in ctype or frame in ("normal", "effect", "ritual", "fusion", "synchro", "xyz", "link")
    if group == "Normalmonster":
        return "Normal" in ctype and "Effect" not in ctype and "Monster" in ctype
    if group == "Effektmonster":
        return "Effect" in ctype and not is_pendulum_card(card)
    if group == "Pendelmonster":
        return is_pendulum_card(card)
    if group == "Ritualmonster":
        return "Ritual" in ctype
    if group == "Fusionsmonster":
        return "Fusion" in ctype
    if group == "Synchromonster":
        return "Synchro" in ctype
    if group == "Xyz-Monster":
        return "XYZ" in ctype or "Xyz" in ctype
    if group == "Linkmonster":
        return "Link" in ctype
    if group == "Extra Deck":
        return any(word in ctype for word in ["Fusion", "Synchro", "XYZ", "Xyz", "Link"])
    if group == "Toonmonster":
        return "Toon" in ctype or "Toon" in race
    if group == "Spiritmonster":
        return "Spirit" in ctype or "Spirit" in race
    if group == "Unionmonster":
        return "Union" in ctype or "Union" in race
    if group == "Gemini-Monster":
        return "Gemini" in ctype or "Gemini" in race
    if group == "Flipmonster":
        return "Flip" in ctype or "Flip" in race
    if group == "Empfänger/Tuner":
        return "Tuner" in ctype or "Tuner" in race
    if group == "Token":
        return "Token" in ctype or frame == "token"
    if group == "Zauberkarten":
        return "Spell Card" in ctype
    if group == "Normale Zauber":
        return "Spell Card" in ctype and race == "Normal"
    if group == "Schnellzauber":
        return "Spell Card" in ctype and race == "Quick-Play"
    if group == "Ausrüstungszauber":
        return "Spell Card" in ctype and race == "Equip"
    if group == "Spielfeldzauber":
        return "Spell Card" in ctype and race == "Field"
    if group == "Permanente Zauber":
        return "Spell Card" in ctype and race == "Continuous"
    if group == "Ritualzauber":
        return "Spell Card" in ctype and race == "Ritual"
    if group == "Fallenkarten":
        return "Trap Card" in ctype
    if group == "Normale Fallen":
        return "Trap Card" in ctype and race == "Normal"
    if group == "Permanente Fallen":
        return "Trap Card" in ctype and race == "Continuous"
    if group == "Konterfallen":
        return "Trap Card" in ctype and race == "Counter"
    return True


def minimal_card(card):
    keep = [
        "id", "name", "type", "frameType", "desc", "atk", "def", "level", "race",
        "attribute", "archetype", "linkval", "scale", "pendulumScale", "pendulum_scale", "lscale", "rscale", "card_images", "card_sets",
        "_artwork_index", "_artwork_total", "_artwork_image", "_variant_key",
        "_collection_set_name", "_collection_set_code", "_collection_set_rarity", "_collection_set_price",
    ]
    return {k: card.get(k) for k in keep if k in card}


def normalize_collection_key(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-z0-9äöüß_-]+", "_", text)
    return text.strip("_") or "unbekannt"


def get_collection_set_from_card(card):
    if not card:
        return None
    if card.get("_collection_set_code") or card.get("_collection_set_name") or card.get("_collection_set_rarity"):
        return {
            "set_name": card.get("_collection_set_name", ""),
            "set_code": card.get("_collection_set_code", ""),
            "set_rarity": card.get("_collection_set_rarity", ""),
            "set_price": card.get("_collection_set_price", ""),
        }
    return None


def apply_collection_set_to_card(card, set_item):
    clone = minimal_card(card)
    set_item = set_item or {}
    clone["_collection_set_name"] = set_item.get("set_name", "") or ""
    clone["_collection_set_code"] = set_item.get("set_code", "") or ""
    clone["_collection_set_rarity"] = set_item.get("set_rarity", "") or ""
    clone["_collection_set_price"] = set_item.get("set_price", "") or ""
    return clone


def collection_key_for(card, set_item=None):
    base = get_card_id(card)
    artwork_suffix = collection_artwork_suffix(card)
    selected = set_item or get_collection_set_from_card(card)
    if not selected:
        return f"{base}{artwork_suffix}"
    set_code = selected.get("set_code") or selected.get("set_name") or "set"
    rarity = selected.get("set_rarity") or "rarity"
    return f"{base}{artwork_suffix}__set_{normalize_collection_key(set_code)}__{normalize_collection_key(rarity)}"


def requested_language_from_set_query(query):
    compact = re.sub(r"\s+", "", str(query or "").upper()).replace("_", "-")
    match = re.search(r"-([A-Z]{2})(\d{2,4}[A-Z]?)$", compact)
    return match.group(1) if match else ""


def localize_set_item_for_query(set_item, query):
    clone = dict(set_item or {})
    lang = requested_language_from_set_query(query)
    if not lang:
        return clone
    raw_code = str(clone.get("set_code") or "").strip().upper()
    match = re.match(r"^([A-Z0-9]{2,10})-([A-Z]{2})(\d{2,4}[A-Z]?)$", raw_code)
    if match:
        clone["set_code"] = f"{match.group(1)}-{lang}{match.group(3)}"
    return clone


def dedupe_card_sets_for_display(card_sets, query=""):
    seen = set()
    result = []
    for item in card_sets or []:
        if not isinstance(item, dict):
            continue
        clone = localize_set_item_for_query(item, query)
        key = (normalize_set_code_signature(clone.get("set_code", "")), normalize_search_text(clone.get("set_name", "")), normalize_search_text(clone.get("set_rarity", "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(clone)
    return result


def choose_set_item_for_query(card, query):
    query = str(query or "").strip()
    if not query:
        return None
    matches = []
    for item in dedupe_card_sets_for_display(card.get("card_sets") or [], query):
        if card_matches_set_query({"card_sets": [item]}, query):
            matches.append(item)
    if not matches:
        return None
    q_sig = normalize_set_code_signature(query)
    q_lang = requested_language_from_set_query(query)
    def score(item):
        code = str(item.get("set_code") or "").upper()
        sig = normalize_set_code_signature(code)
        value = 0
        if q_sig and sig == q_sig:
            value += 100
        if q_lang and f"-{q_lang}" in code:
            value += 20
        if normalize_search_text(query) in normalize_search_text(item.get("set_name", "")):
            value += 10
        return value
    return sorted(matches, key=score, reverse=True)[0]


def dedupe_search_cards(cards):
    best = {}
    for card in cards or []:
        if not isinstance(card, dict) or is_sparse_placeholder_card(card):
            continue
        key = str(card.get("_variant_key") or "").strip()
        if not key:
            image = get_image_url(card)
            key = f"{get_card_id(card)}::{card.get('_artwork_index', 0)}::{image or normalize_search_text(card.get('name', ''))}"
        score = 0
        if get_image_url(card):
            score += 30
        score += min(60, len(card.get("card_sets") or []))
        if card.get("desc"):
            score += 5
        if card.get("_source") == "YGOPRODeck":
            score += 10
        old = best.get(key)
        if old is None or score > old[0]:
            best[key] = (score, card)
    return [v[1] for v in best.values()]


def collection_set_label(card):
    selected = get_collection_set_from_card(card)
    if not selected:
        sets = card.get("card_sets") or []
        selected = sets[0] if sets else {}
    set_name = selected.get("set_name") or "Kein Set"
    set_code = selected.get("set_code") or "-"
    rarity = selected.get("set_rarity") or "Unbekannt"
    return set_name, set_code, rarity



SET_WORD_ALIASES = {
    # Deutsch
    "koenig": "king", "konig": "king", "koenigs": "king", "konigs": "king", "könig": "king", "königs": "king",
    "hof": "court", "gericht": "court", "sammlung": "collection", "meister": "master", "duellant": "duelist", "duellanten": "duelist",
    "duell": "duel", "drachen": "dragon", "drache": "dragon", "dunkel": "dark", "licht": "light", "magier": "magician",
    "legendaer": "legendary", "legendär": "legendary", "geheimnis": "mystery", "labyrinth": "labyrinth", "albtraum": "nightmare",
    "uralt": "ancient", "antike": "ancient", "antiker": "ancient", "chaos": "chaos", "macht": "power", "kraft": "power",
    "welt": "world", "welten": "world", "erbe": "legacy", "vermächtnis": "legacy", "vermaechtnis": "legacy",
    "aufstieg": "rise", "fall": "fall", "schatten": "shadow", "zauberer": "spellcaster", "maschine": "machine",
    # Französisch
    "roi": "king", "reine": "queen", "cour": "court", "duelliste": "duelist", "dragon": "dragon", "magicien": "magician",
    "lumiere": "light", "lumière": "light", "tenebres": "dark", "ténèbres": "dark", "heritage": "legacy", "héritage": "legacy",
    # Italienisch
    "re": "king", "regina": "queen", "corte": "court", "duellante": "duelist", "drago": "dragon", "mago": "magician",
    "luce": "light", "oscurita": "dark", "oscurità": "dark", "eredita": "legacy", "eredità": "legacy",
    # Portugiesisch / Spanisch
    "rei": "king", "rainha": "queen", "corte": "court", "duelista": "duelist", "dragao": "dragon", "dragão": "dragon",
    "mago": "magician", "luz": "light", "trevas": "dark", "oscuridad": "dark", "legado": "legacy", "poder": "power",
}

def strip_accents(value):
    value = str(value or "")
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))

def translate_set_terms(value):
    tokens = normalize_search_text(value).split()
    return " ".join(SET_WORD_ALIASES.get(token, token) for token in tokens)

def normalize_search_text(value):
    value = strip_accents(str(value or "")).lower().strip()
    value = value.replace("’", "'").replace("`", "'")
    value = value.replace("ß", "ss")
    value = re.sub(r"[^a-z0-9' -]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def looks_like_set_code_query(value):
    """Erkennt Set-Kürzel/Setnummern wie KICO, KICO-DE027, RA01-EN001."""
    raw = str(value or "").strip()
    compact = re.sub(r"\s+", "", raw).upper()
    if not compact:
        return False
    if re.match(r"^[A-Z0-9]{2,8}-[A-Z]{2}\d{2,4}$", compact):
        return True
    if re.match(r"^[A-Z0-9]{2,8}-\d{2,4}$", compact):
        return True
    if re.match(r"^[A-Z0-9]{3,8}$", compact) and raw.upper() == raw and any(ch.isalpha() for ch in compact):
        return True
    return False




def get_cardsets_cached(timeout=6):
    """Lädt die YGOPRODeck-Setliste einmalig und hält sie im Speicher.
    Dadurch können Set-Kürzel wie AGOV, DABL, BLMR usw. schnell in den
    offiziellen Set-Namen übersetzt werden, ohne die komplette Kartendatenbank
    lokal durchsuchen zu müssen.
    """
    global CARDSETS_CACHE
    if isinstance(CARDSETS_CACHE, list):
        return CARDSETS_CACHE
    req = urllib.request.Request(
        CARDSETS_URL,
        headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"},
    )
    raw = open_url_bytes(req, timeout=timeout)
    data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    CARDSETS_CACHE = data if isinstance(data, list) else []
    return CARDSETS_CACHE


def extract_set_prefix(value):
    compact = re.sub(r"\s+", "", str(value or "").upper()).replace("_", "-")
    if not compact:
        return ""
    return compact.split("-")[0]


def resolve_set_code_to_set_name(set_query):
    """Übersetzt jedes Set-Kürzel/Printcode, das im YGOPRODeck-Card-Sets-Endpunkt vorhanden ist,
    in den offiziellen Setnamen. Das ist keine Beispiel-Whitelist: Die App prüft dynamisch
    alle Sets aus der API, z. B. AGOV, DABL, BLMR, SBCB, Speed Duel, Promos usw.
    Gibt "" zurück, wenn kein Set gefunden wurde.
    """
    if not looks_like_set_code_query(set_query):
        return ""
    q_prefix = extract_set_prefix(set_query)
    if not q_prefix:
        return ""
    try:
        for item in get_cardsets_cached(timeout=5):
            api_code = str(item.get("set_code") or "").upper().strip()
            api_name = str(item.get("set_name") or "").strip()
            if not api_code or not api_name:
                continue
            if q_prefix == api_code or api_code.startswith(q_prefix + "-"):
                return api_name
    except Exception:
        return ""
    return ""


def is_full_print_code_query(value):
    compact = re.sub(r"\s+", "", str(value or "").upper()).replace("_", "-")
    return bool(
        re.match(r"^[A-Z0-9]{2,10}-[A-Z]{2}\d{2,4}[A-Z]?$", compact)
        or re.match(r"^[A-Z0-9]{2,10}-\d{2,4}[A-Z]?$", compact)
    )

def normalize_set_code_signature(value):
    """Normalisiert Set-Codes sprachunabhängig.
    VASM-EN042, VASM-DE042, VASM-FR042 usw. werden zu VASM-042.
    """
    compact = re.sub(r"\s+", "", str(value or "").upper())
    compact = compact.replace("_", "-")
    match = re.match(r"^([A-Z0-9]{2,10})-([A-Z]{2})(\d{2,4}[A-Z]?)$", compact)
    if match:
        return f"{match.group(1)}-{match.group(3)}"
    match = re.match(r"^([A-Z0-9]{2,10})-(\d{2,4}[A-Z]?)$", compact)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return compact

def card_matches_set_query(card, query):
    """Sucht robust in Set-Namen und Set-Codes.
    Akzeptiert volle Namen, Teilnamen, Kürzel und Codes sowie einfache mehrsprachige Alias-Wörter.
    Beispiel: KICO, KICO-DE027, King's Court, Königshof, Cour du Roi.
    """
    q = normalize_search_text(query)
    q_translated = translate_set_terms(query)
    q_code = re.sub(r"\s+", "", str(query or "").upper())
    q_code_sig = normalize_set_code_signature(query)
    if not q and not q_code:
        return True
    q_tokens = [t for t in q_translated.split() if len(t) >= 2]
    for set_item in card.get("card_sets") or []:
        raw_name = set_item.get("set_name", "")
        raw_code = set_item.get("set_code", "")
        set_name = normalize_search_text(raw_name)
        set_name_translated = translate_set_terms(raw_name)
        set_code = re.sub(r"\s+", "", str(raw_code).upper())
        set_code_sig = normalize_set_code_signature(raw_code)
        set_code_plain = normalize_search_text(raw_code.replace("-", " "))
        if q and (q in set_name or q in set_code_plain):
            return True
        if q_translated and (q_translated in set_name_translated or q_translated in set_code_plain):
            return True
        if q_tokens and all(token in set_name_translated or token in set_code_plain for token in q_tokens):
            return True
        if q_code and (q_code == set_code or set_code.startswith(q_code) or q_code in set_code):
            return True
        if q_code_sig and (q_code_sig == set_code_sig or set_code_sig.startswith(q_code_sig) or q_code_sig in set_code_sig):
            return True
    return False

def card_matches_local_filters(card, filters):
    """Lokaler Filter für Set-Code-Suchen, wenn die API nicht direkt per cardset suchen kann."""
    if filters.get("card_id") and str(card.get("id", "")) != filters.get("card_id", "").strip():
        return False
    if filters.get("name"):
        wanted_name = normalize_search_text(filters.get("name"))
        searchable = " ".join([
            str(card.get("name", "")),
            str(card.get("desc", "")),
            " ".join(str(x) for x in (card.get("_alt_names") or [])),
            str(card.get("_search_blob", "")),
        ])
        if wanted_name not in normalize_search_text(searchable):
            return False
    if filters.get("set") and not card_matches_set_query(card, filters.get("set")):
        return False
    for key in ["atk", "def", "level"]:
        wanted = str(filters.get(key) or "").strip()
        if wanted:
            actual = str(get_level_value(card) if key == "level" else card.get(key, "")).strip()
            if actual != wanted:
                return False
    if filters.get("race"):
        wanted_race = race_to_api(filters.get("race"))
        if normalize_search_text(wanted_race) not in normalize_search_text(card.get("race", "")):
            return False
    if filters.get("attribute"):
        wanted_attr = attribute_to_api(filters.get("attribute"))
        if str(card.get("attribute", "")).upper() != str(wanted_attr).upper():
            return False
    return card_matches_group(card, filters.get("group", "Alle"))

def build_api_url(filters):
    params = {}
    if filters.get("card_id"):
        params["id"] = filters["card_id"].strip()
    if filters.get("name"):
        params["fname"] = filters["name"].strip()
    if filters.get("set") and not looks_like_set_code_query(filters.get("set")):
        params["cardset"] = filters["set"].strip()
    if filters.get("atk"):
        params["atk"] = filters["atk"].strip()
    if filters.get("def"):
        params["def"] = filters["def"].strip()
    if filters.get("level"):
        params["level"] = filters["level"].strip()
    if filters.get("race"):
        params["race"] = race_to_api(filters["race"])
    if filters.get("attribute"):
        params["attribute"] = attribute_to_api(filters["attribute"])

    group = group_to_api(filters.get("group"))
    if group == "Zauber":
        params["type"] = "Spell Card"
    elif group == "Falle":
        params["type"] = "Trap Card"

    language_code = filters.get("language", "de")
    if language_code:
        params["language"] = language_code

    return API_URL + "?" + urllib.parse.urlencode(params)


def open_url_bytes(url_or_request, timeout=25):
    try:
        with urllib.request.urlopen(url_or_request, timeout=timeout, context=SSL_CONTEXT) as response:
            return response.read()
    except urllib.error.URLError as exc:
        text = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in text or "certificate verify failed" in text:
            with urllib.request.urlopen(url_or_request, timeout=timeout, context=INSECURE_SSL_FALLBACK) as response:
                return response.read()
        raise


def retry_sleep_seconds(attempt):
    # Kleine, defensive Wartezeit zwischen fehlgeschlagenen Quellenzugriffen.
    # In Thread-Kontext unkritisch; die Kivy-Oberfläche bleibt frei.
    return min(12.0, 1.5 * max(1, attempt))


def call_source_with_retries(label, fn, language_code="de", timeout=None, attempts=4, progress_cb=None, step=1, total=1):
    """Laedt eine Datenquelle mehrfach, bevor sie als nicht erreichbar gilt.

    Manche Quellen antworten auf Android/GitHub Actions kurzzeitig langsam oder werfen Timeout/SSL/HTTP-Fehler.
    Diese Funktion versucht die Quelle mehrmals mit wachsendem Timeout.
    """
    last_error = ""
    attempts = max(1, int(attempts or 1))

    for attempt in range(1, attempts + 1):
        try:
            if progress_cb:
                progress_cb(step, total, f"{label} Versuch {attempt}/{attempts}...", 0, "")

            if timeout is None:
                cards = fn(language_code)
            else:
                # Timeout pro Versuch etwas erhoehen, damit langsame Server nicht zu frueh abbrechen.
                current_timeout = int(timeout + (attempt - 1) * max(10, timeout * 0.35))
                cards = fn(language_code, timeout=current_timeout)

            cards = cards or []
            if progress_cb:
                progress_cb(step, total, f"{label} fertig nach Versuch {attempt}", len(cards), "")
            return cards

        except Exception as exc:
            last_error = str(exc)
            if progress_cb:
                progress_cb(step, total, f"{label} Fehler bei Versuch {attempt}/{attempts}", 0, last_error)
            if attempt < attempts:
                try:
                    time.sleep(retry_sleep_seconds(attempt))
                except Exception:
                    pass

    raise RuntimeError(last_error or f"{label} nicht erreichbar")



def set_local_card_database_dir(path):
    global LOCAL_CARD_DATABASE_DIR
    LOCAL_CARD_DATABASE_DIR = path or ""


def set_custom_cards_file(path):
    global CUSTOM_CARDS_PATH
    CUSTOM_CARDS_PATH = path or ""


def load_custom_cards():
    if not CUSTOM_CARDS_PATH:
        return []
    try:
        if not os.path.exists(CUSTOM_CARDS_PATH):
            return []
        with open(CUSTOM_CARDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cards = data.get("cards", data) if isinstance(data, dict) else data
        return cards if isinstance(cards, list) else []
    except Exception:
        return []


def save_custom_cards(cards):
    if not CUSTOM_CARDS_PATH:
        return ""
    atomic_write_json(CUSTOM_CARDS_PATH, {"cards": cards})
    return CUSTOM_CARDS_PATH


def local_database_file(language_code="de"):
    lang = language_code or "en"
    folder = LOCAL_CARD_DATABASE_DIR or os.getcwd()
    return os.path.join(folder, f"just_incard_cards_{lang}.json")


def local_database_meta_file():
    folder = LOCAL_CARD_DATABASE_DIR or os.getcwd()
    return os.path.join(folder, "just_incard_cards_meta.json")


def load_local_card_database(language_code="de"):
    """Laedt die lokale Kartendatenbank, falls sie bereits synchronisiert wurde."""
    try:
        path = local_database_file(language_code)
        if not os.path.exists(path) or os.path.getsize(path) <= 0:
            return []
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            cards = payload.get("data") or payload.get("cards") or []
        elif isinstance(payload, list):
            cards = payload
        else:
            cards = []
        return cards if isinstance(cards, list) else []
    except Exception:
        return []


def save_local_card_database(cards, language_code="de", meta=None):
    """Speichert alle geladenen Karten lokal, damit Suche auch zuhause/offline weiter moeglich ist."""
    try:
        folder = LOCAL_CARD_DATABASE_DIR or os.getcwd()
        os.makedirs(folder, exist_ok=True)
        path = local_database_file(language_code)
        payload = {
            "language": language_code or "en",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(cards or []),
            "source": "YGOPRODeck v7 mehrsprachig + YGOResources + RockRoller/Yugipedia + YGOJSON + Project Ignis/BabelCDB + Yugipedia Cargo + lokale Seed-/Registry-Daten",
            "data": cards or [],
        }
        atomic_write_json(path, payload, indent=None)
        meta_payload = meta or {}
        meta_payload.update({"last_language": language_code or "en", "last_count": len(cards or []), "last_file": path, "updated_at": payload["updated_at"]})
        atomic_write_json(local_database_meta_file(), meta_payload)
        return path
    except Exception:
        return ""




def local_sqlite_database_file(language_code="de"):
    lang = language_code or "en"
    folder = LOCAL_CARD_DATABASE_DIR or os.getcwd()
    return os.path.join(folder, f"just_incard_cards_{lang}.sqlite")


def save_local_card_database_sqlite(cards, language_code="de"):
    """Erstellt zusätzlich zur JSON-Datei eine SQLite-Spiegeldatenbank.
    Die App nutzt weiterhin JSON als kompatiblen Hauptspeicher; SQLite ist ab v8.1
    als schnellerer Such-/Reparaturpfad und Grundlage für spätere v9-Funktionen dabei.
    """
    try:
        folder = LOCAL_CARD_DATABASE_DIR or os.getcwd()
        os.makedirs(folder, exist_ok=True)
        path = local_sqlite_database_file(language_code)
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS cards")
        cur.execute("""
            CREATE TABLE cards (
                card_key TEXT PRIMARY KEY,
                passcode TEXT,
                name TEXT,
                type TEXT,
                race TEXT,
                attribute TEXT,
                level TEXT,
                atk TEXT,
                def TEXT,
                set_codes TEXT,
                has_image INTEGER,
                effect_text TEXT,
                raw_json TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_passcode ON cards(passcode)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_set_codes ON cards(set_codes)")
        for card in cards or []:
            if not isinstance(card, dict):
                continue
            try:
                cid = str(card.get("id") or card.get("name") or time.time())
                variant = str(card.get("_variant_key") or card.get("_artwork_index") or "0")
                key = cid + "|" + variant
                set_codes = " ".join(str(s.get("set_code", "")) for s in (card.get("card_sets") or []) if isinstance(s, dict))
                cur.execute(
                    "INSERT OR REPLACE INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        key,
                        str(card.get("id", "")),
                        str(card.get("name", "")),
                        str(card.get("type", "")),
                        str(card.get("race", "")),
                        str(card.get("attribute", "")),
                        str(card.get("level", card.get("linkval", ""))),
                        str(card.get("atk", "")),
                        str(card.get("def", "")),
                        set_codes,
                        1 if get_image_url(card) else 0,
                        normalize_effect_text(card.get("desc") or card.get("description") or card.get("effect") or ""),
                        json.dumps(card, ensure_ascii=False),
                    ),
                )
            except Exception:
                continue
        conn.commit()
        conn.close()
        return path
    except Exception:
        return ""


def load_local_card_database_sqlite(language_code="de", limit=0):
    """Lädt Karten aus SQLite, falls die JSON-Datei beschädigt ist."""
    try:
        path = local_sqlite_database_file(language_code)
        if not os.path.exists(path):
            return []
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        query = "SELECT raw_json FROM cards"
        if limit and int(limit) > 0:
            query += f" LIMIT {int(limit)}"
        rows = cur.execute(query).fetchall()
        conn.close()
        cards = []
        for (raw,) in rows:
            try:
                card = json.loads(raw)
                if isinstance(card, dict):
                    cards.append(card)
            except Exception:
                continue
        return cards
    except Exception:
        return []


def repair_card_database_file(language_code="de"):
    """Repariert die lokale Datenbank defensiv: entfernt ungültige Einträge und schreibt JSON + SQLite neu."""
    cards = load_local_card_database(language_code)
    if not cards:
        cards = load_local_card_database_sqlite(language_code)
    repaired = []
    seen = set()
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        if is_sparse_placeholder_card(card):
            continue
        key = str(card.get("id") or "") + "|" + normalize_search_text(card.get("name", "")) + "|" + str(card.get("_variant_key") or card.get("_artwork_index") or "")
        if key in seen:
            continue
        seen.add(key)
        repaired.append(card)
    path = save_local_card_database(repaired, language_code, meta={"repaired_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    save_local_card_database_sqlite(repaired, language_code)
    return path, len(repaired)


def fetch_all_cards_from_primary(language_code="de", timeout=75):
    params = {}
    if language_code:
        params["language"] = language_code
    url = API_URL + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"})
    raw = open_url_bytes(req, timeout=timeout)
    payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    if isinstance(payload, dict):
        return payload.get("data", []) or []
    return []



def fetch_all_cards_from_primary_all_languages(preferred_language_code="de", timeout=75):
    """Lädt YGOPRODeck in mehreren unterstützten Sprachen.
    Dadurch findet die lokale Suche Karten auch über andere Sprach-Namen.
    Die erste Sprache bleibt bevorzugt für Anzeige/Bilder/Sets, weitere Sprachen werden als Such-Aliase gemerged.
    """
    ordered = []
    preferred = preferred_language_code if preferred_language_code is not None else ""
    for lang in [preferred] + PRIMARY_SYNC_LANGUAGES:
        if lang not in ordered:
            ordered.append(lang)
    all_cards = []
    for lang in ordered:
        try:
            cards = fetch_all_cards_from_primary(lang, timeout=timeout)
            label = lang or "en"
            for c in cards:
                if isinstance(c, dict):
                    c.setdefault("_source", "YGOPRODeck")
                    c.setdefault("_source_language", label)
            all_cards.extend(cards)
        except Exception:
            continue
    return all_cards



def as_list_from_payload(payload):
    """Extrahiert defensiv Kartenlisten aus unterschiedlichen JSON-Strukturen."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "cards", "results", "items", "card", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        # Manche Quellen speichern Karten als Dict nach ID/UUID.
        dict_values = list(payload.values())
        if dict_values and all(isinstance(v, dict) for v in dict_values[: min(len(dict_values), 10)]):
            return dict_values
    return []


def localized_text_value(value, language_code="de", fallback_langs=None):
    fallback_langs = fallback_langs or [language_code, "de", "en", "fr", "it", "es", "pt", "ja", "ko"]
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for lang in fallback_langs:
            entry = value.get(lang) or value.get(str(lang).upper())
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                for k in ("name", "title", "text", "description", "effect"):
                    if entry.get(k):
                        return str(entry.get(k))
        for entry in value.values():
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                for k in ("name", "title", "text", "description", "effect"):
                    if entry.get(k):
                        return str(entry.get(k))
    if isinstance(value, list):
        for entry in value:
            result = localized_text_value(entry, language_code, fallback_langs)
            if result:
                return result
    return ""


def convert_external_card_to_ygopro(card, source_name="Zusatzquelle", language_code="de"):
    """Konvertiert Fremdquellen sehr vorsichtig in das interne Kartenformat.
    Ziel ist maximale Suche/Anzeige ohne Absturz. Fehlende Bild-/Setdaten bleiben leer.
    """
    if not isinstance(card, dict):
        return None
    cid = card.get("id") or card.get("konamiId") or card.get("konami_id") or card.get("databaseId") or card.get("passcode") or card.get("password") or card.get("cardId") or card.get("card_id") or card.get("ygoprodeckId") or card.get("ygoprodeck_id")
    texts = card.get("text") or card.get("texts") or card.get("locales") or card.get("localizations") or card.get("localized") or {}
    name = (card.get("name") or card.get("cardName") or card.get("title") or localized_text_value(texts, language_code) or localized_text_value(card.get("names"), language_code) or localized_text_value(card.get("locale"), language_code))
    if isinstance(name, dict):
        name = localized_text_value(name, language_code)
    name = str(name or "").strip()
    if not name:
        return None
    desc = (card.get("desc") or card.get("description") or card.get("effect") or card.get("cardText") or localized_text_value(card.get("effectText"), language_code) or localized_text_value(texts, language_code))
    ctype = card.get("type") or card.get("cardType") or card.get("card_type") or card.get("frameType") or card.get("classification") or "Monster Card"
    race = card.get("race") or card.get("monsterType") or card.get("property") or card.get("attributeType") or card.get("subtype") or ""
    images = card.get("card_images") or card.get("images") or card.get("image") or []
    if isinstance(images, str):
        images = [{"image_url": images}]
    elif isinstance(images, dict):
        url = images.get("image_url") or images.get("url") or images.get("full") or images.get("small") or images.get("image")
        images = [{"image_url": url}] if url else []
    sets = card.get("card_sets") or card.get("sets") or card.get("prints") or card.get("printings") or []
    converted_sets = []
    if isinstance(sets, dict):
        sets = list(sets.values())
    if isinstance(sets, list):
        for s in sets[:200]:
            if isinstance(s, dict):
                converted_sets.append({
                    "set_name": str(s.get("set_name") or s.get("name") or s.get("set") or s.get("title") or ""),
                    "set_code": str(s.get("set_code") or s.get("code") or s.get("printCode") or s.get("print_code") or s.get("number") or ""),
                    "set_rarity": str(s.get("set_rarity") or s.get("rarity") or s.get("rarityName") or ""),
                    "set_price": str(s.get("set_price") or s.get("price") or ""),
                })
    return {
        "id": int(cid) if str(cid or "").isdigit() else (str(cid) if cid else clean_filename(name).lower()),
        "name": name,
        "type": str(ctype or ""),
        "frameType": str(card.get("frameType") or card.get("frame") or ""),
        "desc": str(desc or "Zusatzdaten aus externem Datenbestand."),
        "atk": card.get("atk", card.get("attack", "")),
        "def": card.get("def", card.get("defense", "")),
        "level": card.get("level", card.get("rank", "")),
        "race": str(race or ""),
        "attribute": str(card.get("attribute") or card.get("monsterAttribute") or ""),
        "archetype": str(card.get("archetype") or card.get("series") or ""),
        "linkval": card.get("linkval", card.get("link", card.get("linkRating", ""))),
        "scale": card.get("scale", card.get("pendulumScale", card.get("pendulum_scale", card.get("lscale", card.get("leftScale", ""))))),
        "card_images": images if isinstance(images, list) else [],
        "card_sets": converted_sets,
        "_source": source_name,
    }


def merge_card_lists(*card_lists):
    """Führt Kartenquellen zusammen. YGOPRODeck-Daten gewinnen bei gleicher ID, externe Quellen ergänzen fehlende Karten."""
    merged = []
    by_key = {}
    for cards in card_lists:
        for card in cards or []:
            if not isinstance(card, dict):
                continue
            key = str(card.get("id") or "").strip() or normalize_search_text(card.get("name", ""))
            if not key:
                continue
            if key in by_key:
                existing = by_key[key]
                # Ergänze Sets/Bilder nur, wenn sie fehlen.
                if not existing.get("card_sets") and card.get("card_sets"):
                    existing["card_sets"] = card.get("card_sets")
                if not existing.get("card_images") and card.get("card_images"):
                    existing["card_images"] = card.get("card_images")
                # Mehrsprachige Namen/Beschreibungen als Such-Aliase behalten, ohne die bevorzugte Anzeige zu überschreiben.
                alt_names = existing.setdefault("_alt_names", [])
                name = str(card.get("name") or "").strip()
                if name and name != str(existing.get("name") or "").strip() and name not in alt_names:
                    alt_names.append(name)
                blob_parts = [existing.get("_search_blob", ""), card.get("name", ""), card.get("desc", ""), card.get("archetype", "")]
                for s in card.get("card_sets") or []:
                    if isinstance(s, dict):
                        blob_parts.extend([s.get("set_name", ""), s.get("set_code", ""), s.get("set_rarity", "")])
                existing["_search_blob"] = " ".join(str(x) for x in blob_parts if x)[:20000]
                if not existing.get("_sources"):
                    existing["_sources"] = [existing.get("_source") or "YGOPRODeck"]
                src = card.get("_source") or "YGOPRODeck"
                if src not in existing["_sources"]:
                    existing["_sources"].append(src)
                continue
            by_key[key] = card
            merged.append(card)
    return merged


def fetch_rockroller_cards(language_code="de", timeout=90):
    """Zusatzquelle auf Yugipedia-Basis. Wird nur beim Datenbank-Sync genutzt."""
    try:
        req = urllib.request.Request(ROCKROLLER_ALL_CARDS_URL, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"})
        raw = open_url_bytes(req, timeout=timeout)
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        converted = []
        for item in as_list_from_payload(payload):
            card = convert_external_card_to_ygopro(item, "RockRoller/Yugipedia", language_code)
            if card:
                converted.append(card)
        return converted
    except Exception:
        return []


def fetch_ygojson_cards(language_code="de", timeout=120, max_cards=0):
    """Lädt YGOJSON als Zusatzdatenbestand. Wenn die Quelle oder das Format nicht passt, wird leer zurückgegeben."""
    urls = [YGOJSON_AGGREGATE_ZIP_URL, YGOJSON_INDIVIDUAL_ZIP_URL]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/zip,application/octet-stream,*/*"})
            raw = open_url_bytes(req, timeout=timeout)
            converted = []
            with zipfile.ZipFile(__import__("io").BytesIO(raw)) as z:
                names = z.namelist()
                # Aggregate zuerst, dann einzelne Karten. Begrenze Einzeldateien optional defensiv.
                priority = [n for n in names if n.endswith("cards.json") or n.endswith("aggregate/cards.json")]
                individual = [n for n in names if "/cards/" in n and n.endswith(".json")]
                for name in priority + individual:
                    try:
                        data = json.loads(z.read(name).decode("utf-8"))
                        items = as_list_from_payload(data)
                        if not items and isinstance(data, dict):
                            items = [data]
                        for item in items:
                            card = convert_external_card_to_ygopro(item, "YGOJSON", language_code)
                            if card:
                                converted.append(card)
                                if max_cards and len(converted) >= max_cards:
                                    return converted
                    except Exception:
                        continue
            if converted:
                return converted
        except Exception:
            continue
    return []



def edo_type_to_ygopro(type_value):
    """EDOPro type bitmask grob in YGOPRODeck-ähnliche Kategorien übersetzen.
    Das reicht für Suche, Sammlung und Anzeige; Detaildaten bleiben über YGOPRODeck/YGOResources genauer.
    """
    try:
        t = int(type_value or 0)
    except Exception:
        t = 0
    if t & 0x2:
        return "Spell Card"
    if t & 0x4:
        return "Trap Card"
    parts = []
    if t & 0x1:
        parts.append("Monster")
    if t & 0x80:
        parts.append("Fusion")
    if t & 0x2000:
        parts.append("Synchro")
    if t & 0x800000:
        parts.append("XYZ")
    if t & 0x4000000:
        parts.append("Link")
    if t & 0x20:
        parts.append("Effect")
    elif t & 0x10:
        parts.append("Normal")
    if t & 0x40:
        parts.append("Ritual")
    if t & 0x1000000:
        parts.append("Pendulum")
    return " ".join(parts) + " Monster" if parts else "Monster Card"


def load_bundled_local_cards(language_code="de"):
    """Kleine direkt mitgelieferte Seed-Datei.
    Sie ersetzt keine vollständige Online-Datenbank, sorgt aber dafür, dass die App auch ohne Sync eine lokale Zusatzquelle kennt.
    """
    try:
        path = resource_find(LOCAL_BUNDLED_SOURCE_FILE) or (LOCAL_BUNDLED_SOURCE_FILE if os.path.exists(LOCAL_BUNDLED_SOURCE_FILE) else "")
        if not path:
            return []
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cards = payload.get("cards", payload if isinstance(payload, list) else [])
        converted = []
        for item in cards if isinstance(cards, list) else []:
            card = convert_external_card_to_ygopro(item, "Just InCard lokale Seed-Daten", language_code)
            if card:
                converted.append(card)
        return converted
    except Exception:
        return []


def fetch_babelcdb_cards(language_code="de", timeout=75, max_per_db=0):
    """Lädt Project-Ignis/BabelCDB SQLite-CDB-Dateien defensiv.
    Diese Quelle ergänzt vor allem OCG/TCG, Skill-, Rush-, Pre-Release- und inoffizielle Karten-Namen/Passcodes.
    """
    all_cards = []
    for source_name, url in BABELCDB_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/octet-stream,*/*"})
            raw = open_url_bytes(req, timeout=timeout)
            if not raw:
                continue
            # sqlite3 kann Bytes nicht direkt als DB öffnen; daher temporär im App-/Arbeitsordner speichern.
            tmp_dir = LOCAL_CARD_DATABASE_DIR or os.getcwd()
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, clean_filename(source_name) + ".cdb")
            with open(tmp_path, "wb") as f:
                f.write(raw)
            conn = sqlite3.connect(tmp_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = """
                SELECT texts.id, texts.name, texts.desc, datas.type, datas.atk, datas.def, datas.level, datas.race, datas.attribute
                FROM texts LEFT JOIN datas ON texts.id = datas.id
            """
            count = 0
            for row in cur.execute(query):
                try:
                    cid = row["id"]
                    name = str(row["name"] or "").strip()
                    if not name:
                        continue
                    card = {
                        "id": int(cid) if str(cid).isdigit() else str(cid),
                        "name": name,
                        "type": edo_type_to_ygopro(row["type"]),
                        "frameType": "",
                        "desc": str(row["desc"] or "Zusatzdaten aus Project Ignis / EDOPro CDB."),
                        "atk": row["atk"] if row["atk"] is not None else "",
                        "def": row["def"] if row["def"] is not None else "",
                        "level": row["level"] if row["level"] is not None else "",
                        "race": str(row["race"] or ""),
                        "attribute": str(row["attribute"] or ""),
                        "card_images": [],
                        "card_sets": [],
                        "_source": source_name,
                    }
                    all_cards.append(card)
                    count += 1
                    if max_per_db and count >= max_per_db:
                        break
                except Exception:
                    continue
            conn.close()
        except Exception:
            continue
    return all_cards

def fetch_yugipedia_cargo_cards(language_code="de", timeout=45, max_pages=40):
    """Direkter Yugipedia-Cargo-Fallback.
    RockRoller nutzt bereits Yugipedia aufbereitet; diese Funktion versucht zusätzlich die öffentliche MediaWiki/Cargo-API.
    Wenn sich Feldnamen ändern oder Yugipedia blockiert/limitiert, wird einfach [] zurückgegeben.
    """
    converted = []
    offset = 0
    limit = 500
    # Mehrere mögliche Feldnamen als Cargo-Query. Fehler werden defensiv abgefangen.
    fields = "_pageName=page,name,passcode,card_type,attribute,types,property,atk,def,level,rank,link_arrows,lore"
    for _ in range(max_pages):
        try:
            params = {
                "action": "cargoquery",
                "format": "json",
                "tables": "Cards",
                "fields": fields,
                "limit": str(limit),
                "offset": str(offset),
            }
            url = YUGIPEDIA_CARGO_API_URL + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"})
            raw = open_url_bytes(req, timeout=timeout)
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            items = payload.get("cargoquery", []) if isinstance(payload, dict) else []
            if not items:
                break
            for item in items:
                title = item.get("title") if isinstance(item, dict) else {}
                if not isinstance(title, dict):
                    continue
                name = title.get("name") or title.get("page") or title.get("_pageName")
                if not name:
                    continue
                card = convert_external_card_to_ygopro({
                    "id": title.get("passcode") or title.get("password"),
                    "name": name,
                    "type": title.get("card_type") or title.get("types") or title.get("property"),
                    "attribute": title.get("attribute"),
                    "atk": title.get("atk"),
                    "def": title.get("def"),
                    "level": title.get("level") or title.get("rank"),
                    "desc": title.get("lore") or "Zusatzdaten aus Yugipedia Cargo.",
                }, "Yugipedia Cargo", language_code)
                if card:
                    converted.append(card)
            if len(items) < limit:
                break
            offset += limit
        except Exception:
            break
    return converted


def load_source_registry_cards(language_code="de"):
    """Lädt optionale lokale Zusatzkarten aus der Quellen-Registry, falls später manuell ergänzt.
    Die Datei ist absichtlich offen gehalten, damit weitere JSON-Quellen nachgetragen werden können,
    ohne App-Code zu ändern. Standardmäßig enthält sie Metadaten, keine riesigen Kartendaten.
    """
    try:
        path = resource_find(LOCAL_SOURCE_REGISTRY_FILE) or (LOCAL_SOURCE_REGISTRY_FILE if os.path.exists(LOCAL_SOURCE_REGISTRY_FILE) else "")
        if not path:
            return []
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cards = payload.get("local_cards", []) if isinstance(payload, dict) else []
        out = []
        for item in cards:
            card = convert_external_card_to_ygopro(item, "Just InCard Quellen-Registry", language_code)
            if card:
                out.append(card)
        return out
    except Exception:
        return []


def fetch_combined_card_database(language_code="de", progress_cb=None):
    """Kombiniert mehrere Quellen in einem lokalen Suchbestand.
    Primär bleibt YGOPRODeck; Zusatzquellen werden defensiv ergänzt, damit die App nicht abstürzt.
    progress_cb(step, total, label, count, error) kann genutzt werden, um den Fortschritt live anzuzeigen.
    """
    sources = []

    def report(step, total, label, count=0, error=""):
        if progress_cb:
            try:
                progress_cb(step, total, label, count, error)
            except Exception:
                pass

    def fetch_source(label, fn, timeout=None, attempts=4):
        step = len(sources) + 1
        total = 7
        report(step, total, label + " wird geladen...", 0, "")
        try:
            # Lokale Quellen brauchen keine Wiederholungen, Online-Quellen schon.
            if timeout is None:
                cards = fn(language_code) or []
                report(step, total, label + " fertig", len(cards), "")
            else:
                cards = call_source_with_retries(
                    label, fn, language_code=language_code, timeout=timeout,
                    attempts=attempts, progress_cb=progress_cb, step=step, total=total
                ) or []
            sources.append(cards)
            return cards
        except Exception as exc:
            sources.append([])
            report(step, total, label + " nach mehreren Versuchen übersprungen", 0, str(exc))
            return []

    fetch_source("YGOPRODeck mehrsprachig", fetch_all_cards_from_primary_all_languages, timeout=120, attempts=5)
    fetch_source("RockRoller/Yugipedia", fetch_rockroller_cards, timeout=120, attempts=5)
    fetch_source("YGOJSON", fetch_ygojson_cards, timeout=150, attempts=5)
    fetch_source("Project Ignis/BabelCDB", fetch_babelcdb_cards, timeout=120, attempts=5)
    fetch_source("Yugipedia Cargo", fetch_yugipedia_cargo_cards, timeout=75, attempts=4)
    fetch_source("Lokale Seed-Daten", load_bundled_local_cards, timeout=None, attempts=1)
    fetch_source("Quellen-Registry", load_source_registry_cards, timeout=None, attempts=1)

    report(7, 7, "Quellen werden zusammengeführt...", sum(len(s) for s in sources), "")
    merged = merge_card_lists(*sources)
    report(7, 7, "Synchronisierung fertig", len(merged), "")
    return merged

def local_database_status_text(language_code="de"):
    try:
        path = local_database_file(language_code)
        if not os.path.exists(path):
            return "Noch keine lokale Kartendatenbank vorhanden."
        cards = load_local_card_database(language_code)
        updated = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        return f"Lokale Datenbank: {len(cards)} Karten | Sprache: {language_code or 'en'} | Stand: {updated}"
    except Exception:
        return "Lokale Datenbank konnte nicht gelesen werden."


def ygoresources_json(url, timeout=25):
    """Liest eine YGOResources-JSON-Datei sicher aus.
    Diese Quelle wird nur ergänzend genutzt. Wenn sie nicht erreichbar ist,
    läuft die App normal mit YGOPRODeck weiter.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"},
    )
    raw = open_url_bytes(req, timeout=timeout)
    return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)


def flatten_ygoresources_ids(value):
    ids = []
    def walk(item):
        if item is None:
            return
        if isinstance(item, int):
            ids.append(str(item))
            return
        if isinstance(item, str):
            if item.strip().isdigit():
                ids.append(item.strip())
            return
        if isinstance(item, dict):
            for key in ("id", "cid", "card_id", "cardId", "card"):
                if key in item:
                    walk(item.get(key))
            for child in item.values():
                if isinstance(child, (list, tuple, dict)):
                    walk(child)
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                walk(child)
    walk(value)
    seen = set()
    unique = []
    for cid in ids:
        if cid and cid not in seen:
            seen.add(cid)
            unique.append(cid)
    return unique


def fetch_ygoresources_candidate_ids(filters, max_ids=30):
    """Findet Karten-IDs über zusätzliche Indexe.
    Unterstützt Namen in mehreren Sprachen sowie Druck-/Set-Codes wie VASM-DE042.
    Die IDs werden danach wieder gegen YGOPRODeck abgeglichen, damit Bild-/Setdaten
    im bekannten Format bleiben.
    """
    candidates = []
    name_query = (filters.get("name") or "").strip()
    set_query = (filters.get("set") or "").strip()

    def add_ids(values):
        for cid in flatten_ygoresources_ids(values):
            if cid not in candidates:
                candidates.append(cid)
                if len(candidates) >= max_ids:
                    return

    # Druckcode-Index: wichtig für verschiedene Sprachcodes, z. B. VASM-DE042/EN042/FR042.
    if set_query:
        compact = re.sub(r"\s+", "", set_query.upper())
        signature = normalize_set_code_signature(set_query)
        try:
            index = ygoresources_json(YGORESOURCES_PRINTCODE_INDEX, timeout=30)
            if isinstance(index, dict):
                for raw_code, value in index.items():
                    code = re.sub(r"\s+", "", str(raw_code).upper())
                    code_sig = normalize_set_code_signature(raw_code)
                    if compact and (compact == code or compact in code or code.startswith(compact)):
                        add_ids(value)
                    elif signature and (signature == code_sig or signature in code_sig or code_sig.startswith(signature)):
                        add_ids(value)
                    if len(candidates) >= max_ids:
                        break
        except Exception:
            pass

    # Namensindexe in allen unterstützten Sprachen.
    if name_query and len(candidates) < max_ids:
        q = normalize_search_text(name_query)
        for lang in SUPPLEMENTAL_SOURCE_LANGS:
            try:
                index = ygoresources_json(YGORESOURCES_NAME_INDEX.format(lang=lang), timeout=25)
                if isinstance(index, dict):
                    for card_name, value in index.items():
                        if q and q in normalize_search_text(card_name):
                            add_ids(value)
                        if len(candidates) >= max_ids:
                            break
            except Exception:
                continue
            if len(candidates) >= max_ids:
                break
    return candidates[:max_ids]


def convert_ygoresources_card(card_id, payload):
    """Sehr defensiver Fallback-Konverter, falls eine Karte nicht in YGOPRODeck landet.
    Bilddaten sind bei solchen Fallback-Karten ggf. nicht vorhanden.
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("card") if isinstance(payload.get("card"), dict) else payload
    name = ""
    texts = data.get("text") or data.get("texts") or data.get("name") or {}
    if isinstance(texts, dict):
        for lang in ("de", "en", "fr", "it", "pt", "es", "ja", "ko"):
            entry = texts.get(lang)
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("title") or name
            elif isinstance(entry, str):
                name = entry
            if name:
                break
    elif isinstance(texts, str):
        name = texts
    name = name or str(data.get("name") or f"Karte {card_id}")
    return {
        "id": int(card_id) if str(card_id).isdigit() else str(card_id),
        "name": name,
        "type": str(data.get("type") or data.get("card_type") or "Monster Card"),
        "desc": str(data.get("desc") or data.get("description") or "Zusatzdaten aus YGOResources. Keine vollständigen Bild-/Setdaten gefunden."),
        "race": str(data.get("race") or data.get("property") or ""),
        "attribute": str(data.get("attribute") or ""),
        "atk": data.get("atk", ""),
        "def": data.get("def", ""),
        "level": data.get("level", ""),
        "card_images": [],
        "card_sets": [],
        "_source": "YGOResources",
    }


def fetch_cards_by_ids_from_primary(ids, language_code="de"):
    cards = []
    seen = set()
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        try:
            url = API_URL + "?" + urllib.parse.urlencode({"id": cid, **({"language": language_code} if language_code else {})})
            req = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"})
            raw = open_url_bytes(req, timeout=25)
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            if isinstance(payload, dict):
                cards.extend(payload.get("data", []) or [])
        except Exception:
            try:
                payload = ygoresources_json(YGORESOURCES_CARD_DATA.format(card_id=cid), timeout=25)
                converted = convert_ygoresources_card(cid, payload)
                if converted:
                    cards.append(converted)
            except Exception:
                continue
    return cards

def download_card_image(card, cache_dir):
    url = get_image_url(card)
    if not url:
        return ""
    os.makedirs(cache_dir, exist_ok=True)
    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    filename = clean_filename(get_card_id(card)) + ext
    path = os.path.join(cache_dir, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "YuGiOhKartenlisteKivy/1.4",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    data = open_url_bytes(req, timeout=25)
    with open(path, "wb") as f:
        f.write(data)
    return path


def fetch_cards(filters):
    has_input = any(filters.get(k) for k in ["card_id", "name", "set", "atk", "def", "level", "race", "attribute"])

    original_set_query = (filters.get("set") or "").strip()
    set_query = original_set_query

    # Schneller Set-Kürzel-Fix: AGOV, DABL, BLMR oder AGOV-DE042 werden zuerst
    # über den kleinen Card-Sets-Endpunkt in den offiziellen Set-Namen übersetzt.
    # Dadurch muss die App nicht jedes Mal die große Kartendatenbank laden.
    exact_print_filter = ""
    if set_query and looks_like_set_code_query(set_query):
        exact_print_filter = set_query if is_full_print_code_query(set_query) else ""
        resolved_set_name = resolve_set_code_to_set_name(set_query)
        if resolved_set_name:
            filters = dict(filters)
            filters["set"] = resolved_set_name
            set_query = resolved_set_name

    # Leere Suche ist erlaubt: Dann werden alle Karten geladen und nur seitenweise gerendert.
    # Set-Namen laufen über den schnellen API-Weg. Nur echte lokale Spezialfälle oder
    # leere Suche nutzen den lokalen Scan.
    use_local_scan = (bool(original_set_query) and looks_like_set_code_query(original_set_query)) or not has_input

    def parse_payload(raw):
        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception:
            return []
        if isinstance(payload, dict):
            return payload.get("data", []) or []
        return []

    def fetch_regular():
        url = build_api_url(filters)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"},
        )
        try:
            raw = open_url_bytes(req, timeout=25)
            return parse_payload(raw)
        except urllib.error.HTTPError as exc:
            # YGOPRODeck liefert bei nicht existierenden Suchanfragen oft HTTP 400/404.
            # Das ist kein App-Fehler: Es bedeutet einfach 0 Treffer.
            if exc.code in (400, 404):
                local_cards = load_local_card_database(filters.get("language", "de"))
                return [c for c in local_cards if card_matches_local_filters(c, filters)] if local_cards else []
            raise
        except Exception:
            local_cards = load_local_card_database(filters.get("language", "de"))
            if local_cards:
                return [c for c in local_cards if card_matches_local_filters(c, filters)]
            raise

    def fetch_all_and_filter():
        # Für "alle Karten" und Set-Kürzel/Set-Code-Suchen wird die Datenbank einmal geladen
        # und lokal gefiltert. Die Oberfläche zeigt danach weiterhin nur eine Seite auf einmal.
        params = {}
        language_code = filters.get("language", "de")
        if language_code:
            params["language"] = language_code
        payload_cards = load_local_card_database(language_code)
        if not payload_cards:
            url = API_URL + ("?" + urllib.parse.urlencode(params) if params else "")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"},
            )
            try:
                raw = open_url_bytes(req, timeout=60)
                payload_cards = parse_payload(raw)
                if payload_cards:
                    save_local_card_database(payload_cards, language_code)
            except urllib.error.HTTPError as exc:
                if exc.code in (400, 404):
                    return []
                raise
            except Exception:
                # Wenn Internet ausfaellt, bleibt die App stabil und nutzt vorhandene lokale Daten, falls moeglich.
                payload_cards = load_local_card_database(language_code)
        return [c for c in payload_cards if card_matches_local_filters(c, filters)]

    # Offline-first: Ist eine lokale Sprachdatenbank vorhanden, ist sie die
    # sichtbare Hauptquelle. Das Netzwerk bleibt Fallback und Ergänzungsquelle.
    local_first_cards = []
    try:
        local_payload = load_local_card_database(filters.get("language", "de"))
        if local_payload:
            local_first_cards = [c for c in local_payload if card_matches_local_filters(c, filters)]
    except Exception:
        local_first_cards = []

    try:
        if local_first_cards:
            cards = local_first_cards
        else:
            cards = fetch_all_and_filter() if use_local_scan else fetch_regular()
    except Exception:
        if set_query or not has_input:
            cards = local_first_cards or []
        else:
            raise

    # Zusätzliche Quellen/Indexe nutzen, um möglichst alle bisher vorhandenen Karten
    # und sprachabhängige Druckcodes/Namen zu finden. YGOPRODeck bleibt die Hauptquelle
    # für Bilder, Sets, Preise und Rarities; YGOResources ergänzt Namen/Printcodes.
    try:
        supplemental_ids = fetch_ygoresources_candidate_ids(filters)
        if supplemental_ids:
            existing_ids = {str(c.get("id")) for c in cards}
            extra_cards = fetch_cards_by_ids_from_primary(supplemental_ids, filters.get("language", "de"))
            for extra in extra_cards:
                eid = str(extra.get("id"))
                if eid and eid not in existing_ids:
                    cards.append(extra)
                    existing_ids.add(eid)
    except Exception:
        pass

    try:
        custom_matches = [c for c in load_custom_cards() if card_matches_local_filters(c, filters)]
        if custom_matches:
            cards = merge_card_lists(cards, custom_matches)
    except Exception:
        pass

    if exact_print_filter:
        exact_cards = [c for c in cards if card_matches_set_query(c, exact_print_filter)]
        if exact_cards:
            cards = exact_cards

    # Finale Sicherheitsbereinigung: keine kaputten Objekte, keine Platzhalter, keine doppelten Basis-Karten.
    # Wichtig: Normale Karten dürfen hier nicht versehentlich herausfallen.
    cleaned_cards = []
    seen_cards = set()
    allow_sparse_by_id = bool((filters.get("card_id") or "").strip())
    for c in cards or []:
        if not isinstance(c, dict):
            continue
        if is_sparse_placeholder_card(c) and not allow_sparse_by_id:
            continue
        key = str(c.get("id") or normalize_search_text(c.get("name", ""))) + "|" + str(c.get("_variant_key") or c.get("_artwork_index") or get_image_url(c) or "0")
        if key in seen_cards:
            continue
        seen_cards.add(key)
        cleaned_cards.append(c)
    cards = cleaned_cards

    group = filters.get("group", "Alle")
    cards = [c for c in cards if card_matches_group(c, group)]
    if False and set_query and not use_set_local_scan:
        # Zusätzlicher lokaler Check erlaubt Teilnamen wie "king court" und schützt vor API-Ungenauigkeiten.
        matching = [c for c in cards if card_matches_set_query(c, set_query)]
        if matching:
            cards = matching
    cards = dedupe_search_cards(expand_artwork_variants(cards))
    cards.sort(key=lambda c: (category_sort_key(c), int(c.get("_artwork_index") or 0)))
    return cards

def is_sparse_placeholder_card(card):
    name = str(card.get("name") or "").strip()
    has_image = bool(get_image_url(card))
    has_sets = bool(card.get("card_sets"))
    has_desc = bool(str(card.get("desc") or "").strip())
    return name.lower().startswith("karte ") and not has_image and not has_sets and not has_desc


def collection_count_for(collection, card):
    """Zaehlt alle Sammlungsvarianten desselben Artworks, unabhaengig von Set/Rarity."""
    base_id = get_card_id(card)
    total = 0
    for item in collection.values():
        item_card = item.get("card", {}) if isinstance(item, dict) else {}
        if get_card_id(item_card) == base_id:
            total += int(item.get("count", 0) or 0)
    if total == 0:
        direct = collection.get(base_id, {})
        total += int(direct.get("count", 0) or 0)
    return total


def stat_text(card):
    base = f"ATK {card.get('atk', '-')}  |  DEF {card.get('def', '-')}  |  Stufe {get_level_value(card) or '-'}"
    if is_pendulum_card(card):
        base += f"  |  Pendel {pendulum_text(card)}"
    return base


# ---------------- Stil-Widgets ----------------

class SurfaceMixin:
    """Gemeinsame, leichte Material-Fläche mit optionaler Tiefe.

    Schatten werden nur für wenige Hauptkarten aktiviert. Listenzeilen und
    Scannerframes bleiben flach, damit auch ältere Android-Geräte flüssig laufen.
    """
    def _init_surface(
        self,
        bg_color=PANEL_BG,
        border_color=BORDER,
        radius=dp(18),
        border_width=1.0,
        elevation=0,
    ):
        self._bg_color = tuple(bg_color)
        self._border_color = tuple(border_color)
        self._radius = float(radius)
        self._border_width = float(border_width)
        self._elevation = max(0.0, float(elevation or 0))
        with self.canvas.before:
            self._shadow_color = Color(0, 0, 0, 0.20 if self._elevation else 0)
            self._shadow_rect = RoundedRectangle(
                pos=(self.x, self.y - dp(self._elevation)),
                size=self.size,
                radius=[self._radius + dp(1)],
            )
            self._color_bg = Color(*self._bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
            self._color_border = Color(*self._border_color)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius),
                width=self._border_width,
            )
        self.bind(pos=self._update_surface, size=self._update_surface)

    def _update_surface(self, *_):
        try:
            self._shadow_rect.pos = (self.x, self.y - dp(self._elevation))
            self._shadow_rect.size = self.size
            self._rect.pos = self.pos
            self._rect.size = self.size
            self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)
        except Exception:
            pass

    def set_surface_colors(self, bg=None, border=None):
        try:
            if bg is not None:
                self._bg_color = tuple(bg)
                self._color_bg.rgba = self._bg_color
            if border is not None:
                self._border_color = tuple(border)
                self._color_border.rgba = self._border_color
        except Exception:
            pass


class SurfaceBox(BoxLayout, SurfaceMixin):
    def __init__(self, bg_color=PANEL_BG, border_color=BORDER, radius=dp(18), elevation=0, border_width=1.0, **kwargs):
        super().__init__(**kwargs)
        self._init_surface(
            bg_color=bg_color,
            border_color=border_color,
            radius=radius,
            border_width=border_width,
            elevation=elevation,
        )


class DarkButton(Button, SurfaceMixin):
    """Einheitlicher Button mit sicheren Touchflächen und responsivem Text."""
    def __init__(self, **kwargs):
        bg = kwargs.pop("bg", ACCENT)
        bold = kwargs.pop("bold", False)
        self._no_wrap = bool(kwargs.pop("no_wrap", False))
        self._compact = bool(kwargs.pop("compact", False))
        self._button_radius = kwargs.pop("radius", dp(16))
        self._button_elevation = kwargs.pop("elevation", 0)
        explicit_font_size = kwargs.get("font_size")
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        try:
            luminance = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
            self.color = (0.035, 0.050, 0.085, 1) if luminance > 0.56 else (1, 1, 1, 1)
        except Exception:
            self.color = TEXT
        self.font_size = explicit_font_size or ui_font_px(12.8 if self._compact else 13.5)
        self.bold = bold
        self.halign = "center"
        self.valign = "middle"
        self.padding = (dp(10 if not self._compact else 7), dp(5))
        if self._no_wrap:
            try:
                self.shorten = True
                self.shorten_from = "right"
                self.max_lines = 1
            except Exception:
                pass
        self.bind(size=self._fit_button_text, disabled=self._update_disabled_visual)
        self._init_surface(
            bg_color=bg,
            border_color=(1, 1, 1, 0.10),
            radius=self._button_radius,
            border_width=0.9,
            elevation=self._button_elevation,
        )

    def _fit_button_text(self, *_):
        try:
            available_w = max(1, self.width - dp(20 if not self._compact else 12))
            available_h = max(1, self.height - dp(8))
            # Auch Einzeiler bekommen immer eine echte Breitenbegrenzung.
            self.text_size = (available_w, available_h)
            if self._no_wrap:
                self.shorten = True
                self.shorten_from = "right"
                self.max_lines = 1
        except Exception:
            pass

    def _update_disabled_visual(self, *_):
        try:
            self.opacity = 0.46 if self.disabled else 1.0
        except Exception:
            pass

    def on_press(self):
        try:
            self._color_bg.rgba = tuple(max(0, c - 0.065) if i < 3 else c for i, c in enumerate(self._bg_color))
            self._shadow_color.a = 0.08
        except Exception:
            pass

    def on_release(self):
        try:
            self._color_bg.rgba = self._bg_color
            self._shadow_color.a = 0.20 if self._elevation else 0
        except Exception:
            pass


class DarkLabel(Label):
    """Label mit sicherem Wrapping und optionaler texturbasierter Höhe."""
    def __init__(self, **kwargs):
        self._auto_height = bool(kwargs.pop("auto_height", False))
        self._min_auto_height = float(kwargs.pop("min_height", 0) or 0)
        self._auto_height_padding = float(kwargs.pop("height_padding", dp(8)) or 0)
        kwargs.setdefault("color", TEXT)
        kwargs.setdefault("font_size", ui_font_px(13.2, body=True))
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        if self._auto_height:
            kwargs["size_hint_y"] = None
        super().__init__(**kwargs)
        self.bind(size=self._update_text_size)
        if self._auto_height:
            self.bind(texture_size=self._sync_auto_height)
            Clock.schedule_once(self._sync_auto_height, 0)

    def _horizontal_padding(self):
        try:
            padding = self.padding or (0, 0)
            if isinstance(padding, (list, tuple)):
                if len(padding) >= 4:
                    return float(padding[0]) + float(padding[2])
                if len(padding) >= 2:
                    return float(padding[0]) * 2.0
                return 0.0
            return float(padding or 0) * 2.0
        except Exception:
            return 0.0

    def _update_text_size(self, *_):
        try:
            self.text_size = (max(1, self.width - self._horizontal_padding()), None)
        except Exception:
            pass

    def _sync_auto_height(self, *_):
        if not self._auto_height:
            return
        try:
            target = max(self._min_auto_height, float(self.texture_size[1]) + self._auto_height_padding)
            if abs(float(self.height) - target) > 0.5:
                self.height = target
        except Exception:
            pass


class AutoHeightLabel(DarkLabel):
    """Mehrzeiliges Label, dessen Höhe nie auf einen festen Textwert vertraut."""
    def __init__(self, **kwargs):
        kwargs.setdefault("auto_height", True)
        kwargs.setdefault("height_padding", dp(10))
        super().__init__(**kwargs)


class DarkInput(TextInput, SurfaceMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = TEXT
        self.cursor_color = ACCENT
        self.hint_text_color = HINT
        self.selection_color = (ACCENT[0], ACCENT[1], ACCENT[2], 0.34)
        self.multiline = bool(getattr(self, "multiline", False))
        try:
            profile = getattr(App.get_running_app(), "ui_profile", {}) or build_ui_profile()
            compact = profile.get("device_class") == "compact_phone"
        except Exception:
            profile = build_ui_profile()
            compact = Window.width < dp(360)
        self.font_size = ui_font_px(13.2 if compact else 14.0, profile)
        self.padding = [dp(13 if compact else 15), dp(12), dp(13 if compact else 15), dp(9)]
        self._init_surface(bg_color=INPUT_BG, border_color=BORDER, radius=dp(16), border_width=1.0)
        self.bind(focus=self._on_focus_visual, disabled=self._on_disabled_visual)

    def _on_focus_visual(self, *_):
        try:
            self._color_border.rgba = tuple(list(ACCENT[:3]) + [0.95]) if self.focus else BORDER
            self._line.width = 1.55 if self.focus else 1.0
        except Exception:
            pass

    def _on_disabled_visual(self, *_):
        try:
            self.opacity = 0.48 if self.disabled else 1.0
        except Exception:
            pass


class DarkSpinner(Spinner, SurfaceMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.color = TEXT
        self.font_size = ui_font_px(13.5)
        self.halign = "center"
        self.valign = "middle"
        try:
            self.shorten = True
            self.shorten_from = "right"
            self.max_lines = 1
        except Exception:
            pass
        self.bind(size=self._fit_spinner_text, is_open=self._on_open_visual)
        self._init_surface(bg_color=INPUT_BG, border_color=BORDER, radius=dp(16), border_width=1.0)

    def _fit_spinner_text(self, *_):
        try:
            self.text_size = (max(1, self.width - dp(22)), max(1, self.height - dp(8)))
        except Exception:
            pass

    def _on_open_visual(self, *_):
        try:
            self._color_border.rgba = ACCENT if self.is_open else BORDER
        except Exception:
            pass


class ModernChip(ButtonBehavior, SurfaceBox):
    """Kompakter Filter-/Statuschip mit optionalem Bildsymbol."""
    def __init__(self, text, icon_name="", active=False, accent=None, **kwargs):
        self.chip_text = str(text or "")
        self.chip_accent = accent or ACCENT
        self.active = bool(active)
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            spacing=dp(6),
            padding=(dp(10), dp(6)),
            bg_color=tuple(list((accent or ACCENT)[:3]) + [0.15 if active else 0.07]),
            border_color=tuple(list((accent or ACCENT)[:3]) + [0.52 if active else 0.22]),
            radius=dp(19),
            **kwargs,
        )
        if icon_name:
            self.add_widget(Image(source=ui_asset(icon_name), size_hint=(None, 1), width=dp(20), allow_stretch=True, keep_ratio=True))
        self.label = DarkLabel(
            text=self.chip_text,
            color=TEXT if active else MUTED,
            halign="center",
            font_size=ui_font_px(10.5),
        )
        self.add_widget(self.label)

    def set_active(self, value):
        self.active = bool(value)
        accent = self.chip_accent
        self.set_surface_colors(
            tuple(list(accent[:3]) + [0.18 if self.active else 0.07]),
            tuple(list(accent[:3]) + [0.62 if self.active else 0.22]),
        )
        self.label.color = TEXT if self.active else MUTED


class EmptyStateCard(SurfaceBox):
    """Ruhiger Leer-/Fehlerzustand statt nacktem Text im Layout."""
    def __init__(self, title, message, icon_name="cards", **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            height=dp(180),
            spacing=dp(8),
            padding=dp(18),
            bg_color=INPUT_BG,
            border_color=tuple(list(ACCENT[:3]) + [0.15]),
            radius=dp(22),
            **kwargs,
        )
        self.add_widget(Image(source=ui_asset(icon_name), size_hint_y=None, height=dp(50), allow_stretch=True, keep_ratio=True, opacity=0.74))
        self.add_widget(DarkLabel(text=f"[b]{html_escape(str(title))}[/b]", markup=True, halign="center", size_hint_y=None, height=dp(28), font_size=ui_font_px(14.5)))
        self.add_widget(AutoHeightLabel(text=str(message), color=MUTED, halign="center", min_height=dp(52), font_size=ui_font_px(11.5, body=True)))


CARD_TYPE_MAP = {
    "Normal Monster": "Normales Monster",
    "Effect Monster": "Effektmonster",
    "Fusion Monster": "Fusionsmonster",
    "Synchro Monster": "Synchromonster",
    "XYZ Monster": "Xyz-Monster",
    "Xyz Monster": "Xyz-Monster",
    "Link Monster": "Linkmonster",
    "Ritual Monster": "Ritualmonster",
    "Pendulum Effect Monster": "Pendel-Effektmonster",
    "Pendulum Normal Monster": "Pendel-Normalmonster",
    "Pendulum Tuner Effect Monster": "Pendel-Empfänger-Effektmonster",
    "Pendulum Flip Effect Monster": "Pendel-Klapp-Effektmonster",
    "Pendulum Effect Fusion Monster": "Pendel-Fusionsmonster",
    "Pendulum Effect Synchro Monster": "Pendel-Synchromonster",
    "Pendulum Effect Xyz Monster": "Pendel-Xyz-Monster",
    "Pendulum Effect Link Monster": "Pendel-Linkmonster",
    "Spell Card": "Zauberkarte",
    "Trap Card": "Fallenkarte",
    "Skill Card": "Skill-Karte",
    "Monster Card": "Monsterkarte",
    "Token": "Spielmarke",
}


def display_card_type(value):
    text = str(value or "").strip()
    if not text:
        return "-"
    if text in CARD_TYPE_MAP:
        return CARD_TYPE_MAP[text]
    for en, de in sorted(CARD_TYPE_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
        text = text.replace(en, de)
    return text


class StatPill(DarkLabel, SurfaceMixin):
    def __init__(self, bg_color=INPUT_BG_2, text_color=TEXT, **kwargs):
        super().__init__(**kwargs)
        self.color = text_color
        self.padding = (dp(10), dp(6))
        self._init_surface(bg_color=bg_color, border_color=(1, 1, 1, 0.08), radius=dp(12), border_width=0.9)


class SectionTitle(BoxLayout):
    def __init__(self, title, subtitle="", accent=ACCENT, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(8), **kwargs)
        self.title_text = str(title or "")
        self.subtitle_text = str(subtitle or "")
        self.accent = accent
        self.label = DarkLabel(markup=True, auto_height=True, min_height=dp(30), height_padding=dp(6))
        self.add_widget(self.label)
        self.bind(width=self._refresh_section_title)
        self.label.bind(height=self._sync_height)
        Clock.schedule_once(self._refresh_section_title, 0)

    def _sync_height(self, *_):
        try:
            self.height = max(dp(32), self.label.height)
        except Exception:
            pass

    def _refresh_section_title(self, *_):
        compact = self.width < dp(520)
        text = f"[b]{html_escape(self.title_text)}[/b]"
        if self.subtitle_text:
            separator = "\n" if compact else "  "
            text += f"{separator}[color={markup_hex(MUTED)}]{html_escape(self.subtitle_text)}[/color]"
        self.label.text = text
        self.label.font_size = ui_font_px(12.5 if compact else 14, body=True)
        self.label.text_size = (max(1, self.width), None)
        Clock.schedule_once(self.label._sync_auto_height, 0)


class LogoView(SurfaceBox):
    def __init__(self, logo_source, **kwargs):
        super().__init__(orientation="vertical", bg_color=(0, 0, 0, 0), border_color=(1, 1, 1, 0.0), radius=dp(16), padding=dp(2), **kwargs)
        if logo_source:
            self.add_widget(Image(source=logo_source, allow_stretch=True, keep_ratio=True))
        else:
            self.add_widget(DarkLabel(text="LOGO", color=GOLD, halign="center", valign="middle"))


class HeaderImageButton(ButtonBehavior, SurfaceBox):
    def __init__(self, icon_source, fallback_text="?", **kwargs):
        super().__init__(orientation="vertical", bg_color=(0, 0, 0, 0), border_color=(1, 1, 1, 0.0), radius=dp(22), padding=dp(0), **kwargs)
        try:
            if icon_source:
                self.icon = Image(source=icon_source, allow_stretch=True, keep_ratio=True)
                self.add_widget(self.icon)
            else:
                self.add_widget(DarkLabel(text=fallback_text, color=TEXT, halign="center", valign="middle", font_size=ui_font_px(20, body=True)))
        except Exception:
            self.add_widget(DarkLabel(text=fallback_text, color=TEXT, halign="center", valign="middle", font_size=ui_font_px(20, body=True)))



class NavigationItem(ButtonBehavior, SurfaceBox):
    """Android-Navigationselement mit echtem Bildsymbol statt Font-Sonderzeichen."""
    def __init__(self, icon_name, text, vertical=False, **kwargs):
        self.icon_name = icon_name
        self.nav_text = text
        self.vertical_mode = bool(vertical)
        super().__init__(
            orientation="vertical" if self.vertical_mode else "horizontal",
            spacing=dp(2 if self.vertical_mode else 10),
            padding=(dp(6), dp(5)) if self.vertical_mode else (dp(10), dp(6)),
            bg_color=(0, 0, 0, 0),
            border_color=(0, 0, 0, 0),
            radius=dp(15),
            **kwargs,
        )
        self.icon = Image(
            source=ui_asset(icon_name),
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(1, 0.56) if self.vertical_mode else (None, 1),
            width=dp(30 if self.vertical_mode else 28),
            opacity=0.74,
        )
        self.label = DarkLabel(
            text=text,
            color=MUTED,
            halign="center" if self.vertical_mode else "left",
            valign="middle",
            font_size=ui_font_px(9.5 if self.vertical_mode else 12.5),
            size_hint=(1, 0.44) if self.vertical_mode else (1, 1),
        )
        self.add_widget(self.icon)
        self.add_widget(self.label)
        self.active = False

    def set_active(self, active):
        self.active = bool(active)
        bg = ACCENT_2 if self.active else (0, 0, 0, 0)
        border = tuple(list(ACCENT[:3]) + [0.34]) if self.active else (0, 0, 0, 0)
        try:
            self._bg_color = bg
            self._color_bg.rgba = bg
            self._border_color = border
            self._color_border.rgba = border
            self.label.color = TEXT if self.active else MUTED
            self.icon.opacity = 1.0 if self.active else 0.70
        except Exception:
            pass

    def apply_profile(self, profile, vertical=None):
        if vertical is not None and bool(vertical) != self.vertical_mode:
            # Die Instanzen werden pro Navigationsmodus getrennt erzeugt. Dieser
            # Zweig bleibt nur als defensiver Schutz für spätere Erweiterungen.
            self.vertical_mode = bool(vertical)
        compact = profile.get("device_class") == "compact_phone"
        if self.vertical_mode:
            self.padding = (dp(4), dp(4))
            self.spacing = dp(1)
            self.label.font_size = ui_font_px(8.7 if compact else 9.5, profile)
            self.icon.width = dp(27 if compact else 30)
        else:
            self.padding = (dp(10), dp(6))
            self.spacing = dp(9)
            self.label.font_size = ui_font_px(12 if compact else 12.8, profile)
            self.icon.width = dp(26 if compact else 30)


class ActionTile(ButtonBehavior, SurfaceBox):
    """Große, leicht erfassbare Funktionskachel für Tablet und Dialoge."""
    def __init__(self, icon_name, title, subtitle="", accent=None, **kwargs):
        self.tile_accent = accent or ACCENT
        super().__init__(
            orientation="horizontal",
            spacing=dp(10),
            padding=(dp(10), dp(8)),
            bg_color=CARD_BG,
            border_color=tuple(list((accent or ACCENT)[:3]) + [0.18]),
            radius=dp(16),
            **kwargs,
        )
        icon_box = SurfaceBox(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(48),
            padding=dp(8),
            bg_color=tuple(list((accent or ACCENT)[:3]) + [0.12]),
            border_color=(0, 0, 0, 0),
            radius=dp(14),
        )
        icon_box.add_widget(Image(source=ui_asset(icon_name), allow_stretch=True, keep_ratio=True))
        self.add_widget(icon_box)
        labels = BoxLayout(orientation="vertical", spacing=0)
        self.title_label = DarkLabel(text=f"[b]{title}[/b]", markup=True, color=TEXT, halign="left", font_size=ui_font_px(12.5))
        self.subtitle_label = DarkLabel(text=subtitle, color=MUTED, halign="left", font_size=ui_font_px(9.8, body=True))
        labels.add_widget(self.title_label)
        labels.add_widget(self.subtitle_label)
        self.add_widget(labels)

    def apply_profile(self, profile):
        self.title_label.font_size = ui_font_px(12.2 if profile.get("is_phone") else 13.2, profile)
        self.subtitle_label.font_size = ui_font_px(9.4 if profile.get("is_phone") else 10.4, profile, body=True)


class ScannerSourceTile(ButtonBehavior, SurfaceBox):
    """Große, moderne Scanquellen-Kachel mit eindeutigem Aktivzustand."""
    def __init__(self, icon_name, title, subtitle, active=False, **kwargs):
        self.source_active = bool(active)
        super().__init__(
            orientation="horizontal",
            spacing=dp(8),
            padding=(dp(10), dp(7)),
            bg_color=tuple(list(ACCENT[:3]) + [0.16 if active else 0.05]),
            border_color=tuple(list(ACCENT[:3]) + [0.60 if active else 0.18]),
            radius=dp(18),
            **kwargs,
        )
        icon_box = SurfaceBox(
            orientation="vertical", size_hint=(None, 1), width=dp(40), padding=dp(8),
            bg_color=tuple(list(ACCENT[:3]) + [0.15]), border_color=(0, 0, 0, 0), radius=dp(13),
        )
        icon_box.add_widget(Image(source=ui_asset(icon_name), allow_stretch=True, keep_ratio=True))
        self.add_widget(icon_box)
        labels = BoxLayout(orientation="vertical", spacing=0)
        self.title_label = DarkLabel(text=f"[b]{html_escape(str(title))}[/b]", markup=True, color=TEXT, halign="left", font_size=ui_font_px(11.8))
        self.subtitle_label = DarkLabel(text=str(subtitle), color=MUTED, halign="left", font_size=ui_font_px(9.2, body=True))
        labels.add_widget(self.title_label)
        labels.add_widget(self.subtitle_label)
        self.add_widget(labels)

    def set_active(self, active):
        self.source_active = bool(active)
        self.set_surface_colors(
            tuple(list(ACCENT[:3]) + [0.16 if self.source_active else 0.05]),
            tuple(list(ACCENT[:3]) + [0.68 if self.source_active else 0.18]),
        )
        self.title_label.color = TEXT if self.source_active else MUTED
        self.subtitle_label.color = TEXT if self.source_active else HINT


class AdaptivePopup(Popup):
    """Popup mit zentraler Safe-Area-Größenberechnung.

    Dadurch bleiben Titel und untere Aktionsleisten auch auf sehr
    schmalen Displays, Tablets, Foldables und bei Orientierungswechseln sichtbar.
    """
    def __init__(self, app_ref=None, requested_size_hint=(0.86, 0.5), **kwargs):
        self.app_ref = app_ref
        self.requested_size_hint = requested_size_hint or (0.86, 0.5)
        kwargs["size_hint"] = (None, None)
        super().__init__(**kwargs)
        self._adaptive_bound = False
        self.bind(on_open=self._on_adaptive_open, on_dismiss=self._on_adaptive_dismiss)

    def _on_adaptive_open(self, *_):
        if not self._adaptive_bound:
            Window.bind(size=self._fit_to_safe_area)
            self._adaptive_bound = True
        Clock.schedule_once(self._fit_to_safe_area, 0)

    def _on_adaptive_dismiss(self, *_):
        if self._adaptive_bound:
            try:
                Window.unbind(size=self._fit_to_safe_area)
            except Exception:
                pass
            self._adaptive_bound = False

    def _fit_to_safe_area(self, *_):
        try:
            app = self.app_ref or App.get_running_app()
            if app is not None and hasattr(app, "current_ui_profile"):
                profile = app.current_ui_profile()
            else:
                profile = getattr(app, "ui_profile", None) or build_ui_profile()
            safe = profile.get("safe", {})
            base_margin = dp(8 if profile.get("device_class") == "compact_phone" else 12)
            left = float(safe.get("left", 0)) + base_margin
            right = float(safe.get("right", 0)) + base_margin
            top = float(safe.get("top", 0)) + base_margin
            keyboard_height = max(0.0, float(getattr(Window, "keyboard_height", 0) or 0))
            bottom = float(safe.get("bottom", 0)) + base_margin + keyboard_height
            available_w = max(dp(260), Window.width - left - right)
            available_h = max(dp(220), Window.height - top - bottom)
            rw, rh = self.requested_size_hint
            rw = max(0.30, min(1.0, float(rw or 0.86)))
            rh = max(0.24, min(1.0, float(rh or 0.50)))
            min_w = min(available_w, dp(280 if profile.get("device_class") == "compact_phone" else 320))
            min_h = min(available_h, dp(220))
            device_class = profile.get("device_class", "phone")
            window_class = profile.get("window_class", "compact")
            if window_class == "extra_large" or device_class == "large_tablet":
                dialog_max_w = min(available_w, dp(1180))
            elif window_class in {"large", "expanded"} or device_class == "tablet":
                dialog_max_w = min(available_w, dp(960))
            elif window_class == "medium":
                dialog_max_w = min(available_w, dp(760))
            else:
                dialog_max_w = available_w
            width = min(dialog_max_w, max(min_w, available_w * rw))
            height = min(available_h, max(min_h, available_h * rh))
            self.size = (width, height)
            self.pos = (
                left + max(0, (available_w - width) / 2.0),
                bottom + max(0, (available_h - height) / 2.0),
            )
            if str(getattr(self, "title", "") or "").strip():
                self.title_size = ui_font_px(14 if profile.get("device_class") == "compact_phone" else 15, profile)
            else:
                self.title = ""
                self.title_size = 0
                try:
                    self.separator_height = 0
                    self.title_padding = (0, 0)
                    self.padding = 0
                except Exception:
                    pass
            self._normalize_close_buttons(profile)
            self._normalize_header_labels(profile)
            self._normalize_grid_heights(profile)
            Clock.schedule_once(lambda *_: self._normalize_grid_heights(profile), 0)
        except Exception:
            pass

    def _normalize_close_buttons(self, profile):
        """Kompatibilitätsprüfung für ältere Dialoge; v10.0 zeigt keine X-Schaltflächen."""
        side = dp(46 if profile.get("device_class") == "compact_phone" else 50)
        stack = [self.content] if self.content is not None else []
        while stack:
            widget = stack.pop()
            try:
                stack.extend(list(getattr(widget, "children", []) or []))
            except Exception:
                pass
            try:
                if isinstance(widget, DarkButton) and str(getattr(widget, "text", "")).strip().upper() in {"X", "×"} and getattr(widget, "size_hint_x", None) is None:
                    widget.size_hint = (None, None)
                    widget.size = (side, side)
                    parent = getattr(widget, "parent", None)
                    if parent is not None and getattr(parent, "size_hint_y", None) is None:
                        def _fit_header(*_args, _parent=parent, _button=widget):
                            try:
                                spacing = float(getattr(_parent, "spacing", 0) or 0)
                                labels = [child for child in getattr(_parent, "children", []) if isinstance(child, DarkLabel)]
                                label_height = 0.0
                                for label in labels:
                                    available = max(dp(80), float(_parent.width) - float(_button.width) - spacing - dp(4))
                                    label.text_size = (available, None)
                                    label_height = max(label_height, float(label.texture_size[1] or 0) + dp(8))
                                _parent.height = max(side, label_height)
                            except Exception:
                                try:
                                    _parent.height = max(float(getattr(_parent, "height", 0) or 0), side)
                                except Exception:
                                    pass
                        _fit_header()
                        if not getattr(parent, "_just_incard_header_bound", False):
                            try:
                                parent.bind(width=_fit_header)
                                for sibling in getattr(parent, "children", []):
                                    if isinstance(sibling, DarkLabel):
                                        sibling.bind(texture_size=_fit_header)
                                parent._just_incard_header_bound = True
                            except Exception:
                                pass
            except Exception:
                continue

    def _normalize_grid_heights(self, profile):
        """Verhindert gequetschte GridLayouts in alten v9.5-Dialogen.

        Mehrere v9.5-Dialoge änderten auf schmalen Geräten zwar die Spaltenzahl,
        ließen aber die ursprüngliche Ein-Zeilen-Höhe stehen. v10.0 berechnet die
        benötigte Zeilenzahl für jedes feste Grid neu und lässt vorhandene größere
        Höhen unangetastet.
        """
        stack = [self.content] if self.content is not None else []
        visited = 0
        default_h = dp(46 if profile.get("device_class") == "compact_phone" else 48)
        while stack and visited < 420:
            widget = stack.pop()
            visited += 1
            try:
                children = list(getattr(widget, "children", []) or [])
                stack.extend(children)
            except Exception:
                children = []
            if not isinstance(widget, GridLayout) or getattr(widget, "size_hint_y", 1) is not None or not children:
                continue
            try:
                cols = max(1, int(getattr(widget, "cols", 1) or 1))
                rows = int(math.ceil(len(children) / float(cols)))
                padding = getattr(widget, "padding", (0, 0, 0, 0))
                if isinstance(padding, (int, float)):
                    pad_y = float(padding) * 2
                elif len(padding) == 2:
                    pad_y = float(padding[1]) * 2
                else:
                    pad_y = float(padding[1]) + float(padding[3])
                spacing = getattr(widget, "spacing", 0)
                if isinstance(spacing, (tuple, list)):
                    spacing_y = float(spacing[1] if len(spacing) > 1 else spacing[0])
                else:
                    spacing_y = float(spacing or 0)
                child_h = default_h
                for child in children:
                    explicit = float(getattr(child, "height", 0) or 0)
                    if getattr(child, "size_hint_y", 1) is None and explicit > 0:
                        child_h = max(child_h, explicit)
                computed = pad_y + rows * child_h + max(0, rows - 1) * spacing_y
                minimum = float(getattr(widget, "minimum_height", 0) or 0)
                widget.height = max(float(getattr(widget, "height", 0) or 0), minimum, computed)
            except Exception:
                continue

    def _normalize_header_labels(self, profile):
        """Passt kurze Dialog-Kopfzeilen an Breite und Systemschrift an."""
        stack = [self.content] if self.content is not None else []
        visited = 0
        while stack and visited < 240:
            widget = stack.pop()
            visited += 1
            try:
                children = list(getattr(widget, "children", []) or [])
                stack.extend(children)
            except Exception:
                children = []
            try:
                if not isinstance(widget, BoxLayout):
                    continue
                if str(getattr(widget, "orientation", "")) != "horizontal":
                    continue
                if getattr(widget, "size_hint_y", 1) is not None:
                    continue
                if float(getattr(widget, "height", 0) or 0) > dp(110):
                    continue
                labels = [child for child in children if isinstance(child, DarkLabel)]
                if not labels:
                    continue
                fixed_width = 0.0
                for child in children:
                    if child in labels:
                        continue
                    if getattr(child, "size_hint_x", 1) is None:
                        fixed_width += float(getattr(child, "width", 0) or 0)
                spacing = float(getattr(widget, "spacing", 0) or 0) * max(0, len(children) - 1)
                available = max(dp(120), float(widget.width) - fixed_width - spacing - dp(4))
                target = dp(46)
                for label in labels:
                    label.text_size = (available, None)
                    target = max(target, float(label.texture_size[1] or 0) + dp(12))
                widget.height = min(dp(104), target)
            except Exception:
                continue


class InlinePageHandle:
    """Leichtgewichtiger Seiten-Controller mit Popup-kompatibler Schnittstelle.

    Bestehende v9.5-v9.8-Dialoglogik kann dadurch schrittweise als echter
    Navigationsscreen verwendet werden, ohne dunkles Modal-Overlay und ohne X.
    """
    def __init__(self, app_ref, key, content, back_to="search"):
        self.app_ref = app_ref
        self.key = str(key or "page")
        self.content = content
        self.back_to = str(back_to or "search")
        self.requested_size_hint = (1, 1)
        self._dismiss_callbacks = []
        self._opened = False

    def bind(self, **kwargs):
        callback = kwargs.get("on_dismiss")
        if callable(callback):
            self._dismiss_callbacks.append(callback)
        return self

    def open(self, *_):
        self.app_ref._activate_inline_page(self)
        self._opened = True
        return self

    def dismiss(self, *_):
        self.app_ref._close_inline_page(self, navigate=True)
        return True

    def _dispatch_dismiss(self):
        callbacks = list(self._dismiss_callbacks)
        self._dismiss_callbacks = []
        for callback in callbacks:
            try:
                callback(self)
            except TypeError:
                try:
                    callback()
                except Exception:
                    pass
            except Exception:
                pass

    def _fit_to_safe_area(self, *_):
        # Die Seite wird von _activate_inline_page bereits mit Safe-Area-Rändern
        # und der aktuellen Fensterbreite aufgebaut.
        return None


# ---------------- App ----------------

class YuGiOhApp(App):
    title = APP_DISPLAY_NAME

    def build(self):
        self._app_started_at = time.perf_counter()
        self.collection = {}
        self.search_results = []
        self.selected_card = None
        self.last_scan_photo = ""
        self.current_page = 0
        self.is_searching = False
        self._search_token = 0
        self._layout_event = None
        self._compact_panel_event = None
        self._screen_probe_generation = 0
        self._last_probe_orientation = bool(Window.width > Window.height)
        self._last_probe_window_size = (float(Window.width), float(Window.height))
        self._last_layout_signature = None
        self.screen_metrics = {
            "width_px": int(max(1, Window.width)),
            "height_px": int(max(1, Window.height)),
            "density": float(max(0.5, dp(1))),
            "source": "kivy-startup",
        }
        self.ui_profile = build_ui_profile(self.screen_metrics)
        self._interface_ready = False
        self.theme_name = "dark"
        self.permissions_requested = False
        self.database_install_prompted = False
        self.first_launch_welcome_seen = False
        self.camera_rotation = 270
        self.openai_api_key = ""
        self.openai_model = DEFAULT_OPENAI_MODEL
        self.scan_mode = "normal"
        self._gallery_scan_active = False
        self.performance_mode = "auto"
        self.reduce_motion = False
        self.large_touch_targets = False
        self.high_contrast_focus = True
        self.wifi_only_images = False
        self.cache_limit_mb = 500
        self.scan_history = []
        self.last_scan_import_transaction = {}
        self._navigation_history = []
        self._current_section = "home"
        self._active_inline_page = None
        self._inline_page_outer = None
        self._scanner_resume_callback = None
        self._scan_cancel_requested = False
        self._scan_pause_requested = False
        self.collection_file = os.path.join(self.user_data_dir, "yugioh_sammlung.json")
        self.settings_file = os.path.join(self.user_data_dir, "settings.json")
        self.decks_file = os.path.join(self.user_data_dir, "decks.json")
        self.image_cache_dir = os.path.join(self.user_data_dir, "card_images")
        self.local_database_dir = os.path.join(self.user_data_dir, "card_database")
        self.custom_cards_file = os.path.join(self.user_data_dir, "custom_cards.json")
        self.scan_history_file = os.path.join(self.user_data_dir, "scan_history.json")
        self.scan_undo_file = os.path.join(self.user_data_dir, "scan_last_import.json")
        self.scan_artwork_cache_dir = os.path.join(self.user_data_dir, "scan_artwork_cache")
        self.scan_learning_file = os.path.join(self.user_data_dir, "scan_learning_v93.json")
        self.scan_timing_file = os.path.join(self.user_data_dir, "scan_timing_v100.json")
        self.scan_artwork_index_file = os.path.join(self.user_data_dir, "scan_artwork_index_v100.json")
        self.undo_history_file = os.path.join(self.user_data_dir, "undo_history_v93.json")
        self.incremental_sync_file = os.path.join(self.user_data_dir, "incremental_sync_v93.json")
        self.session_state_file = os.path.join(self.user_data_dir, "session_state_v97.json")
        self.pending_restore_file = os.path.join(self.user_data_dir, "pending_restore_v97.json")
        self.auto_backup_dir = os.path.join(self.user_data_dir, "auto_backups_v104")
        self.diagnostics_dir = os.path.join(self.user_data_dir, "diagnostics_v104")
        self.crash_log_file = os.path.join(self.user_data_dir, "just_incard_crash.log")
        self.app_database_file = os.path.join(self.user_data_dir, "just_incard_v91.sqlite3")
        # Ein zuvor ausgewähltes Backup wird vor dem Öffnen der SQLite-Datenbank
        # angewendet. So wird keine laufende Datenbankdatei überschrieben.
        self.last_restore_report = apply_pending_restore(self.user_data_dir, self.pending_restore_file)
        self.app_db = AppDatabaseV91(self.app_database_file)
        self.scan_learning = ScanLearningStoreV93(self.scan_learning_file)
        self.scan_timings = ScanTimingStoreV100(self.scan_timing_file)
        self._scan_artwork_index = safe_read_json(self.scan_artwork_index_file, {}) or {}
        self._scan_index_lock = threading.RLock()
        self.undo_manager = UndoManagerV93(self.undo_history_file)
        self.incremental_sync = IncrementalSyncStateV93(self.incremental_sync_file)
        self.session_store = SessionStateStoreV97(self.session_state_file)
        self.cache_manager = CacheManagerV97([self.image_cache_dir, self.scan_artwork_cache_dir])
        self.auto_backup_manager = AutomaticBackupManagerV104(self.auto_backup_dir, keep=5, min_interval_seconds=86400)
        self.active_scan_queue_id = ""
        self._open_popups = []
        set_local_card_database_dir(self.local_database_dir)
        set_custom_cards_file(self.custom_cards_file)
        self.load_settings()
        self.load_scan_history()
        self.load_last_scan_import_transaction()
        self.load_collection(show_popup=False)
        self.load_decks()

        self.root_holder = BoxLayout(orientation="vertical")
        Window.clearcolor = STARTUP_BG
        Window.softinput_mode = "below_target"
        try:
            Window.fullscreen = "auto"
        except Exception:
            pass
        hide_android_system_ui()
        Window.bind(size=self._schedule_responsive_layout)
        Window.bind(on_keyboard=self._handle_android_back)
        self.start_background_screen_probe()
        self.start_background_maintenance()
        self.show_start_loading_screen()
        Clock.schedule_once(lambda *_: self.finish_start_loading_screen(), 0.95)
        Clock.schedule_once(lambda *_: threading.Thread(target=self.run_integrity_check_v104, daemon=True).start(), 2.0)
        return self.root_holder

    def make_inline_page(self, key, content, back_to="search"):
        """Erzeugt einen Hauptscreen statt eines modalen Popups."""
        return InlinePageHandle(self, key, content, back_to=back_to)

    def _activate_inline_page(self, handle):
        previous = getattr(self, "_active_inline_page", None)
        if previous is not None and previous is not handle:
            self._close_inline_page(previous, navigate=False)
        profile = self.current_ui_profile()
        safe = profile.get("safe", {})
        width_dp = float(profile.get("width_dp") or 0)
        is_tablet = bool(profile.get("is_tablet")) and width_dp >= 600
        outer_margin = dp(8 if profile.get("device_class") == "compact_phone" else (12 if not is_tablet else 16))
        outer = BoxLayout(
            orientation="vertical",
            padding=(
                float(safe.get("left", 0) or 0) + outer_margin,
                float(safe.get("top", 0) or 0) + outer_margin,
                float(safe.get("right", 0) or 0) + outer_margin,
                outer_margin,
            ),
        )
        outer.add_widget(handle.content)
        self.page_host.clear_widgets()
        self.page_host.add_widget(outer)
        self._inline_page_outer = outer
        self._active_inline_page = handle
        self._current_section = handle.key
        self._set_navigation_active(handle.key)

    def _close_inline_page(self, handle=None, navigate=True):
        current = getattr(self, "_active_inline_page", None)
        target = handle or current
        if target is None:
            if navigate:
                self.show_search_page()
            return
        if current is target:
            self._active_inline_page = None
            self._inline_page_outer = None
        try:
            target._dispatch_dismiss()
        except Exception:
            pass
        if navigate and current is target:
            destination = str(getattr(target, "back_to", "home") or "home")
            if destination == "scanner":
                self.open_camera_scanner()
            elif destination == "collection":
                self.open_collection_popup()
            elif destination == "decks":
                self.open_decks_popup()
            elif destination == "search":
                self.show_search_page()
            elif destination == "home":
                self.show_home_page()
            else:
                self.show_home_page()

    def show_home_page(self, *_):
        """Moderne v11.2.3-Startseite mit klaren Aktionen und sicheren Höhen."""
        current = getattr(self, "_active_inline_page", None)
        if current is not None:
            self._close_inline_page(current, navigate=False)
        profile = self.current_ui_profile()
        safe = profile.get("safe", {})
        is_tablet = bool(profile.get("is_tablet"))
        compact = profile.get("device_class") == "compact_phone"
        gap = dp(float(profile.get("gap_dp") or 8))
        outer_margin = dp(float(profile.get("outer_margin_dp") or 12))
        usable_w = max(dp(260), Window.width - float(safe.get("left", 0)) - float(safe.get("right", 0)))
        max_content = dp(float(profile.get("content_max_dp") or 760))
        side_center = max(0.0, (usable_w - max_content) / 2.0)

        shell = BoxLayout(
            orientation="vertical",
            padding=(
                float(safe.get("left", 0)) + outer_margin + side_center,
                float(safe.get("top", 0)) + outer_margin,
                float(safe.get("right", 0)) + outer_margin + side_center,
                outer_margin,
            ),
        )
        scroll = ScrollView(bar_width=dp(3), scroll_type=["bars", "content"], do_scroll_x=False)
        body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=gap)
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)
        shell.add_widget(scroll)

        logo_source = resource_find(APP_LOGO_TRANSPARENT_FILE) or resource_find(APP_LOGO_FILE) or ui_asset("app_mark") or ""
        hero = SurfaceBox(
            orientation="horizontal" if is_tablet and not compact else "vertical",
            size_hint_y=None,
            height=dp(270 if is_tablet else (290 if compact else 320)),
            spacing=dp(16),
            padding=dp(18 if compact else 22),
            bg_color=PANEL_BG_2,
            border_color=tuple(list(ACCENT[:3]) + [0.20]),
            radius=dp(28),
            elevation=2,
        )
        logo_box = SurfaceBox(
            orientation="vertical",
            size_hint=(0.38 if is_tablet else 1, 1 if is_tablet else 0.50),
            padding=dp(8),
            bg_color=tuple(list(ACCENT[:3]) + [0.055]),
            border_color=(0, 0, 0, 0),
            radius=dp(24),
        )
        logo_box.add_widget(Image(source=logo_source, allow_stretch=True, keep_ratio=True))
        hero.add_widget(logo_box)

        hero_text = BoxLayout(orientation="vertical", spacing=dp(6), size_hint=(0.62 if is_tablet else 1, 1 if is_tablet else 0.50))
        hero_text.add_widget(DarkLabel(
            text="[b]Just InCard[/b]",
            markup=True,
            color=TEXT,
            halign="left" if is_tablet else "center",
            size_hint_y=None,
            height=dp(48),
            font_size=ui_font_px(text_sp_v110("display", profile), profile),
        ))
        hero_text.add_widget(DarkLabel(
            text="Scannen. Sammeln. Decks bauen.",
            color=GOLD,
            halign="left" if is_tablet else "center",
            size_hint_y=None,
            height=dp(28),
            font_size=ui_font_px(text_sp_v110("section", profile), profile),
        ))
        hero_text.add_widget(AutoHeightLabel(
            text="Deine Yu-Gi-Oh!-Karten in einer klaren, schnellen Oberfläche – passend für Smartphone, Tablet, Hochformat und Querformat.",
            color=MUTED,
            halign="left" if is_tablet else "center",
            min_height=dp(58),
            font_size=ui_font_px(text_sp_v110("body", profile), profile, body=True),
        ))
        hero_status = ModernChip("Scanner und Sammlung bereit", "scan", active=True, accent=SUCCESS, size_hint_x=None)
        hero_status.width = dp(250 if is_tablet else 230)
        if not is_tablet:
            status_holder = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40))
            status_holder.add_widget(Widget())
            status_holder.add_widget(hero_status)
            status_holder.add_widget(Widget())
            hero_text.add_widget(status_holder)
        else:
            hero_text.add_widget(hero_status)
        hero.add_widget(hero_text)
        body.add_widget(hero)

        body.add_widget(SectionTitle("Schnellzugriff", "Die wichtigsten Bereiche ohne Umwege", accent=ACCENT))
        quick_grid = GridLayout(
            cols=4 if is_tablet and float(profile.get("width_dp") or 0) >= 900 else 2,
            size_hint_y=None,
            spacing=gap,
        )
        quick_actions = [
            ("scan", "Scanner", "Live, Foto, Galerie", self.open_camera_scanner, GOLD),
            ("search", "Suche", "Karte direkt finden", self.show_search_page, ACCENT),
            ("cards", "Sammlung", "Bestand verwalten", self.open_collection_popup, SUCCESS),
            ("decks", "Decks", "Decks planen", self.open_decks_popup, ACCENT),
        ]
        tile_h = dp(88 if compact else 98)
        quick_grid.height = grid_height_v110(len(quick_actions), quick_grid.cols, tile_h, gap)
        for icon_name, title, subtitle, callback, accent in quick_actions:
            tile = ActionTile(icon_name, title, subtitle, accent=accent, size_hint_y=None, height=tile_h)
            tile.bind(on_release=lambda *_args, _callback=callback: _callback())
            quick_grid.add_widget(tile)
        body.add_widget(quick_grid)

        total_cards = sum(int(item.get("count", 0) or 0) for item in self.collection.values())
        unique_cards = sum(1 for item in self.collection.values() if int(item.get("count", 0) or 0) > 0)
        stats = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            height=dp(150 if compact else 136),
            spacing=dp(10),
            padding=dp(14),
            bg_color=PANEL_BG,
            border_color=tuple(list(SUCCESS[:3]) + [0.16]),
            radius=dp(22),
        )
        stats.add_widget(SectionTitle("Dein Überblick", "Lokal auf diesem Gerät", accent=SUCCESS))
        stat_grid = GridLayout(cols=2 if not is_tablet else 4, spacing=gap, size_hint_y=None)
        values = [
            (f"{total_cards:,}".replace(",", "."), "Karten"),
            (str(unique_cards), "Varianten"),
            (str(len(getattr(self, "decks", []) or [])), "Decks"),
            ("Bereit", "Scanner"),
        ]
        visible_values = values if is_tablet else values[:2]
        stat_grid.height = dp(62)
        for value, label in visible_values:
            pill = SurfaceBox(orientation="vertical", padding=(dp(8), dp(5)), bg_color=INPUT_BG, border_color=(1, 1, 1, 0.06), radius=dp(16))
            pill.add_widget(DarkLabel(text=f"[b]{html_escape(value)}[/b]", markup=True, halign="center", font_size=ui_font_px(16, profile)))
            pill.add_widget(DarkLabel(text=label, color=MUTED, halign="center", font_size=ui_font_px(10, profile, body=True)))
            stat_grid.add_widget(pill)
        stats.add_widget(stat_grid)
        body.add_widget(stats)

        self.page_host.clear_widgets()
        self.page_host.add_widget(shell)
        self._active_inline_page = None
        self._inline_page_outer = None
        self._current_section = "home"
        self._set_navigation_active("home")

    def show_search_page(self, *_):
        current = getattr(self, "_active_inline_page", None)
        if current is not None:
            self._close_inline_page(current, navigate=False)
        if hasattr(self, "page_host") and hasattr(self, "main_scroll"):
            self.page_host.clear_widgets()
            self.page_host.add_widget(self.main_scroll)
        self._current_section = "search"
        self._set_navigation_active("search")
        try:
            self.main_scroll.scroll_y = 1.0
        except Exception:
            pass
        self.apply_responsive_layout(force=True)

    def start_background_screen_probe(self):
        """Ermittelt Displaygröße/Dichte/Insets im Hintergrund und aktualisiert das UI-Profil."""
        self._screen_probe_generation = int(getattr(self, "_screen_probe_generation", 0) or 0) + 1
        generation = self._screen_probe_generation

        def worker():
            metrics = get_android_screen_metrics_snapshot()
            Clock.schedule_once(lambda *_: self._apply_screen_metrics(metrics, generation), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_screen_metrics(self, metrics, generation=0):
        if generation and generation != getattr(self, "_screen_probe_generation", generation):
            return
        try:
            self.screen_metrics = dict(metrics or {})
            self.ui_profile = build_ui_profile(self.screen_metrics, (Window.width, Window.height))
            if getattr(self, "_interface_ready", False):
                self.apply_responsive_layout(force=True)
        except Exception as exc:
            try:
                self.append_crash_log(exc)
            except Exception:
                pass

    def start_background_maintenance(self):
        """Bereinigt nur neu erzeugbare Scanner- und Artwork-Zwischendateien.

        Neben dem Alterslimit gilt ein Größenlimit, damit Stapelscans auf Geräten
        mit wenig freiem Speicher nicht unbemerkt mehrere Gigabyte belegen.
        """
        def worker():
            try:
                now = time.time()
                max_age = 7 * 24 * 60 * 60
                max_cache_bytes = int(max(100, min(2000, getattr(self, "cache_limit_mb", 500)))) * 1024 * 1024
                prefixes = ("ocr_retry_", "guided_ocr_", "scan_live_", "scan_frame_", "scan_region_", "scan_perspective_")
                candidates = []
                total_size = 0
                for folder in {self.user_data_dir, getattr(self, "scan_artwork_cache_dir", "")}: 
                    if not folder or not os.path.isdir(folder):
                        continue
                    for name in os.listdir(folder):
                        path = os.path.join(folder, name)
                        try:
                            if not os.path.isfile(path):
                                continue
                            generated = name.startswith(prefixes) or folder == getattr(self, "scan_artwork_cache_dir", "")
                            if not generated:
                                continue
                            size = os.path.getsize(path)
                            mtime = os.path.getmtime(path)
                            if now - mtime > max_age:
                                os.remove(path)
                                continue
                            candidates.append((mtime, path, size))
                            total_size += size
                        except Exception:
                            continue
                if total_size > max_cache_bytes:
                    for _mtime, path, size in sorted(candidates):
                        try:
                            os.remove(path)
                            total_size -= size
                        except Exception:
                            pass
                        if total_size <= max_cache_bytes:
                            break
                self.record_performance("cache_maintenance", details={"remaining_bytes": total_size, "files": len(candidates)})
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def current_ui_profile(self):
        """Gibt immer ein zur aktuellen Window-Größe passendes UI-Profil zurück."""
        try:
            self.ui_profile = build_ui_profile(getattr(self, "screen_metrics", {}), (Window.width, Window.height))
        except Exception:
            self.ui_profile = build_ui_profile()
        return self.ui_profile

    def usable_window_width(self, fraction=1.0):
        profile = self.current_ui_profile()
        safe = profile.get("safe", {})
        width = max(dp(240), Window.width - float(safe.get("left", 0)) - float(safe.get("right", 0)) - dp(16))
        return max(dp(120), width * max(0.1, min(1.0, float(fraction or 1.0))))

    def usable_content_width(self, fraction=1.0, widget=None):
        """Reale Inhaltsbreite nach Seitenleiste, Safe-Area und Seitenpadding."""
        width = 0.0
        try:
            if widget is not None and float(getattr(widget, "width", 0) or 0) > dp(120):
                width = float(widget.width)
            elif float(getattr(getattr(self, "page_host", None), "width", 0) or 0) > dp(160):
                width = float(self.page_host.width)
        except Exception:
            width = 0.0
        if width <= 0:
            width = float(self.usable_window_width())
            profile = self.current_ui_profile()
            width_dp = float(profile.get("width_dp") or 0)
            if bool(profile.get("is_tablet")) and width_dp >= 720:
                rail = float(getattr(getattr(self, "navigation_rail", None), "width", 0) or 0)
                if rail <= 0:
                    rail = dp(176 if width_dp < 1000 else 208)
                width = max(dp(180), width - rail - dp(16))
        return max(dp(120), width * max(0.1, min(1.0, float(fraction or 1.0))))

    @staticmethod
    def responsive_columns_for_width(width, min_item_dp=160, max_cols=4, min_cols=1, gap_px=None):
        gap = float(gap_px if gap_px is not None else dp(8))
        width = max(dp(120), float(width or 0))
        cols = int((width + gap) // (dp(float(min_item_dp)) + gap))
        return max(int(min_cols), min(int(max_cols), max(1, cols)))

    def bind_adaptive_grid(self, grid, item_count, min_item_dp=160, max_cols=4, min_cols=1, row_height=None, gap_px=None, on_layout=None):
        """Bindet Spalten und Höhe an die tatsächlich verfügbare Widgetbreite."""
        row_height = float(row_height if row_height is not None else dp(52))
        gap = float(gap_px if gap_px is not None else dp(8))
        def _apply(*_):
            width = float(getattr(grid, "width", 0) or self.usable_content_width())
            cols = self.responsive_columns_for_width(width, min_item_dp, max_cols, min_cols, gap)
            grid.cols = cols
            grid.height = self.grid_height(int(item_count), cols, row_height, gap)
            if callable(on_layout):
                try:
                    on_layout(cols, float(grid.height))
                except Exception:
                    pass
        grid.bind(width=_apply)
        Clock.schedule_once(_apply, 0)
        return _apply

    def ui_width_below(self, threshold_dp, fraction=1.0):
        return self.usable_content_width(fraction) < dp(float(threshold_dp))

    def responsive_columns(self, min_item_dp=160, max_cols=4, min_cols=1, fraction=1.0):
        width = self.usable_content_width(fraction)
        return self.responsive_columns_for_width(width, min_item_dp, max_cols, min_cols)

    def record_performance(self, event_name, started_at=None, details=None):
        """Speichert kompakte Leistungsdaten ohne Nutzerdaten oder API-Schlüssel."""
        try:
            duration_ms = None
            if started_at is not None:
                duration_ms = max(0.0, (time.perf_counter() - float(started_at)) * 1000.0)
            if getattr(self, "app_db", None) is not None:
                self.app_db.record_performance(event_name, duration_ms, details or {})
        except Exception:
            pass

    def _handle_android_back(self, _window, key, *_args):
        """Android-Zurück zuerst für Dialoge, danach für die aktuelle Ansicht."""
        if int(key or 0) != 27:
            return False
        try:
            while self._open_popups:
                popup = self._open_popups[-1]
                if popup is None:
                    self._open_popups.pop()
                    continue
                try:
                    popup.dismiss()
                    return True
                except Exception:
                    self._open_popups.pop()
            inline_page = getattr(self, "_active_inline_page", None)
            if inline_page is not None:
                inline_page.dismiss()
                return True
            if hasattr(self, "main_scroll") and float(getattr(self.main_scroll, "scroll_y", 1.0)) < 0.98:
                self.main_scroll.scroll_y = 1.0
                return True
            if str(getattr(self, "_current_section", "home") or "home") != "home":
                self.show_home_page()
                return True
        except Exception:
            pass
        return False

    def install_android_shortcuts(self):
        """Erstellt Android-Schnellaktionen für die wichtigsten Bereiche."""
        if platform != "android":
            return False
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ShortcutManager = autoclass("android.content.pm.ShortcutManager")
            ShortcutInfoBuilder = autoclass("android.content.pm.ShortcutInfo$Builder")
            Icon = autoclass("android.graphics.drawable.Icon")
            Intent = autoclass("android.content.Intent")
            ArrayList = autoclass("java.util.ArrayList")
            BuildVersion = autoclass("android.os.Build$VERSION")
            if int(BuildVersion.SDK_INT) < 25:
                return False
            activity = PythonActivity.mActivity
            manager = activity.getSystemService(ShortcutManager)
            shortcuts = ArrayList()
            actions = [
                ("scan", "Karte scannen", "Scanner öffnen"),
                ("bulk_scan", "Mehrere Bilder", "Galerie-Sammelimport"),
                ("collection", "Sammlung", "Sammlung öffnen"),
                ("search", "Karte suchen", "Kartensuche öffnen"),
            ]
            for shortcut_id, short_label, long_label in actions:
                intent = Intent(activity, activity.getClass())
                intent.setAction(Intent.ACTION_VIEW)
                intent.putExtra("just_incard_shortcut", shortcut_id)
                builder = ShortcutInfoBuilder(activity, shortcut_id)
                builder.setShortLabel(short_label)
                builder.setLongLabel(long_label)
                builder.setIntent(intent)
                try:
                    builder.setIcon(Icon.createWithResource(activity, activity.getApplicationInfo().icon))
                except Exception:
                    pass
                shortcuts.add(builder.build())
            manager.setDynamicShortcuts(shortcuts)
            return True
        except Exception:
            return False

    def consume_android_shortcut(self):
        if platform != "android":
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = PythonActivity.mActivity.getIntent()
            action = str(intent.getStringExtra("just_incard_shortcut") or "")
            if not action:
                return
            try:
                intent.removeExtra("just_incard_shortcut")
            except Exception:
                pass
            if action in {"scan", "bulk_scan"}:
                self.open_camera_scanner()
            elif action == "collection":
                self.open_collection_popup()
            elif action == "search" and hasattr(self, "main_scroll"):
                self.main_scroll.scroll_y = 1.0
        except Exception:
            pass

    def offer_resume_scan_queue(self):
        """Bietet einen nach App-Abbruch gespeicherten Galerie-Scan erneut an."""
        try:
            queued = self.app_db.latest_active_scan_queue() if getattr(self, "app_db", None) else None
            if not queued:
                return
            paths = [p for p in (queued.get("paths") or []) if p and os.path.exists(p)]
            if not paths:
                self.app_db.clear_scan_queue(queued.get("queue_id", ""))
                return
            content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
            content.add_widget(DarkLabel(
                text=f"[b]Unterbrochenen Scan fortsetzen?[/b]\n{len(paths)} gespeicherte Bilddatei(en) wurden gefunden. Der Scan wird sicher neu gestartet und bereits bestätigte Sammlungsänderungen werden nicht doppelt ausgeführt.",
                markup=True,
                color=TEXT,
            ))
            buttons = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(8))
            discard = DarkButton(text="Verwerfen", bg=INPUT_BG_2)
            resume = DarkButton(text="Fortsetzen", bg=ACCENT)
            buttons.add_widget(discard)
            buttons.add_widget(resume)
            content.add_widget(buttons)
            popup = self.make_popup("Scan-Wiederherstellung", content, size_hint=(0.90, 0.48))
            def discard_queue(*_):
                popup.dismiss()
                self.app_db.clear_scan_queue(queued.get("queue_id", ""))
            def resume_queue(*_):
                popup.dismiss()
                self.app_db.clear_scan_queue(queued.get("queue_id", ""))
                self.start_bulk_gallery_ocr_import(paths)
            discard.bind(on_release=discard_queue)
            resume.bind(on_release=resume_queue)
            popup.open()
        except Exception as exc:
            self.append_crash_log(exc, "Scan-Wiederherstellung")

    def run_integrity_check_v104(self):
        """Prüft die mitgelieferten Kernressourcen ohne die App zu blockieren."""
        try:
            manifest = resource_find("security_integrity_manifest.json") or os.path.join(os.path.dirname(__file__), "security_integrity_manifest.json")
            if not manifest or not os.path.exists(manifest):
                return
            result = verify_integrity_manifest(os.path.dirname(__file__), manifest)
            if not result.get("ok"):
                self.append_crash_log(
                    "Integritätsabweichung: " + json.dumps(result, ensure_ascii=False),
                    "Security v11.2.3",
                )
        except Exception as exc:
            self.append_crash_log(exc, "Security v11.2.3")

    def load_settings(self):
        data = {}
        try:
            if getattr(self, "app_db", None) is not None:
                data = self.app_db.get_value("app", "settings", {}) or {}
            if not data:
                data = safe_read_json(self.settings_file, {})
                if data and getattr(self, "app_db", None) is not None:
                    self.app_db.set_value("app", "settings", data)
            self.theme_name = data.get("theme", "dark") if data.get("theme") in THEMES else "dark"
            self.permissions_requested = bool(data.get("permissions_requested", False))
            self.database_install_prompted = bool(data.get("database_install_prompted", False))
            self.first_launch_welcome_seen = bool(data.get("first_launch_welcome_seen", False))
            self.openai_api_key = data.get("openai_api_key", "") or ""
            self.openai_model = data.get("openai_model", DEFAULT_OPENAI_MODEL) or DEFAULT_OPENAI_MODEL
            self.cloud_ai_scan_enabled = bool(data.get("cloud_ai_scan_enabled", False))
            self.privacy_settings_v104 = dict(DEFAULT_PRIVACY_V104)
            self.privacy_settings_v104.update(data.get("privacy_v104") or {})
            self.auto_backup_enabled = bool(data.get("auto_backup_enabled", True))
            self.scan_mode = data.get("scan_mode", "normal") if data.get("scan_mode", "normal") in {"schnell", "normal"} else "normal"
            perf = str(data.get("performance_mode", "auto") or "auto")
            self.performance_mode = perf if perf in {"auto", "eco", "balanced", "quality"} else "auto"
            accessibility = normalize_accessibility_settings(data)
            self.reduce_motion = accessibility["reduce_motion"]
            self.large_touch_targets = accessibility["large_touch_targets"]
            self.high_contrast_focus = accessibility["high_contrast_focus"]
            self.wifi_only_images = accessibility["wifi_only_images"]
            self.cache_limit_mb = accessibility["cache_limit_mb"]
            self.camera_rotation = int(data.get("camera_rotation", 270)) % 360
        except Exception:
            self.theme_name = "dark"
            self.permissions_requested = False
            self.database_install_prompted = False
            self.first_launch_welcome_seen = False
            self.camera_rotation = 270
            self.openai_api_key = ""
            self.openai_model = DEFAULT_OPENAI_MODEL
            self.cloud_ai_scan_enabled = False
            self.privacy_settings_v104 = dict(DEFAULT_PRIVACY_V104)
            self.auto_backup_enabled = True
            self.scan_mode = "normal"
            self.performance_mode = "auto"
            self.reduce_motion = False
            self.large_touch_targets = False
            self.high_contrast_focus = True
            self.wifi_only_images = False
            self.cache_limit_mb = 500

    def save_settings(self):
        payload = {
            "theme": self.theme_name,
            "permissions_requested": self.permissions_requested,
            "database_install_prompted": self.database_install_prompted,
            "first_launch_welcome_seen": bool(getattr(self, "first_launch_welcome_seen", False)),
            "camera_rotation": self.camera_rotation,
            "openai_api_key": self.openai_api_key,
            "openai_model": self.openai_model,
            "cloud_ai_scan_enabled": bool(getattr(self, "cloud_ai_scan_enabled", False)),
            "privacy_v104": dict(getattr(self, "privacy_settings_v104", DEFAULT_PRIVACY_V104)),
            "auto_backup_enabled": bool(getattr(self, "auto_backup_enabled", True)),
            "scan_mode": self.scan_mode,
            "performance_mode": self.performance_mode,
            "reduce_motion": bool(self.reduce_motion),
            "large_touch_targets": bool(self.large_touch_targets),
            "high_contrast_focus": bool(self.high_contrast_focus),
            "wifi_only_images": bool(self.wifi_only_images),
            "cache_limit_mb": int(self.cache_limit_mb),
        }
        try:
            if getattr(self, "app_db", None) is not None:
                self.app_db.set_value("app", "settings", payload)
            atomic_write_json(self.settings_file, payload)
        except Exception:
            pass

    def load_scan_history(self):
        """Lädt die letzten Scan-Sitzungen defensiv aus einer lokalen JSON-Datei."""
        self.scan_history = []
        try:
            if os.path.exists(self.scan_history_file):
                with open(self.scan_history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.scan_history = data[:20]
        except Exception:
            self.scan_history = []

    def save_scan_history(self):
        try:
            atomic_write_json(self.scan_history_file, (self.scan_history or [])[:20])
        except Exception:
            pass

    def capture_session_state(self):
        """Erfasst nur kleine UI-Werte; Sammlungsdaten liegen weiterhin separat."""
        selected_id = ""
        try:
            selected_id = str(get_card_id(self.selected_card)) if self.selected_card else ""
        except Exception:
            selected_id = ""
        return {
            "section": getattr(self, "_current_section", "search"),
            "filters": self.get_filters_safe(),
            "page": int(getattr(self, "current_page", 0) or 0),
            "selected_card_id": selected_id,
            "main_scroll_y": float(getattr(getattr(self, "main_scroll", None), "scroll_y", 1.0) or 1.0),
            "results_scroll_y": float(getattr(getattr(self, "results_scroll", None), "scroll_y", 1.0) or 1.0),
            "advanced_filters": not bool(getattr(self, "_advanced_filters_collapsed", True)),
            "active_deck": int(getattr(self, "_active_deck_index", -1) or -1),
        }

    def save_session_state(self, show_popup=False):
        try:
            state = self.session_store.save(self.capture_session_state())
            if show_popup:
                self.show_info("App-Zustand gespeichert", "Suche, Filter, Seite und Scrollposition wurden gespeichert.")
            return state
        except Exception as exc:
            self.append_crash_log(exc, "Sitzungszustand speichern")
            if show_popup:
                self.show_error("Speichern fehlgeschlagen", str(exc))
            return {}

    def restore_session_state(self):
        """Stellt die letzte Suche wieder her, ohne automatisch Netzwerkzugriffe zu starten."""
        try:
            state = self.session_store.load()
            if not state or not getattr(self, "_interface_ready", False):
                return False
            self.apply_filters_to_widgets(state.get("filters") or {})
            self.current_page = max(0, int(state.get("page") or 0))
            self._advanced_filters_collapsed = not bool(state.get("advanced_filters", False))
            self._sync_advanced_panel_height()
            self.render_current_page(reset_scroll=False)
            # v10.0 startet bewusst auf der neutralen Logo-Seite. Suchfilter und
            # Scrollwerte werden vorbereitet, aber erst beim Öffnen der Suche gezeigt.
            self._current_section = "home"
            self._set_navigation_active("home")
            self.show_home_page()
            def apply_scroll(*_):
                try:
                    self.main_scroll.scroll_y = float(state.get("main_scroll_y") or 1.0)
                    self.results_scroll.scroll_y = float(state.get("results_scroll_y") or 1.0)
                except Exception:
                    pass
            Clock.schedule_once(apply_scroll, 0.08)
            return True
        except Exception as exc:
            self.append_crash_log(exc, "Sitzungszustand wiederherstellen")
            return False

    def clear_session_state(self, *_):
        try:
            self.session_store.clear()
            self.show_info("App-Zustand zurückgesetzt", "Gespeicherte Suche, Filter und Scrollposition wurden entfernt.")
        except Exception as exc:
            self.show_error("Zurücksetzen fehlgeschlagen", str(exc))

    def show_last_restore_result(self):
        report = getattr(self, "last_restore_report", {}) or {}
        if report.get("applied"):
            files = report.get("files") or []
            message = f"{len(files)} Datendatei(en) wurden aus dem Backup wiederhergestellt."
            if report.get("errors"):
                message += "\n\nEinige Dateien konnten nicht übernommen werden:\n" + "\n".join(report.get("errors")[:8])
            self.show_info("Backup wiederhergestellt", message)
        elif report.get("errors"):
            self.show_error("Backup-Wiederherstellung", "\n".join(report.get("errors")[:10]))

    def _accept_backup_import(self, path):
        try:
            report = BackupInspectorV97.inspect(path)
            if not report.get("valid"):
                self.show_error("Backup ungültig", "\n".join(report.get("warnings") or ["Keine unterstützten Daten gefunden."]))
                return
            manifest = report.get("manifest") or {}
            size_mb = float(report.get("total_uncompressed") or 0) / (1024.0 * 1024.0)
            lines = [
                f"App-Version im Backup: {manifest.get('version', 'unbekannt')}",
                f"Wiederherstellbare Dateien: {len(report.get('restorable') or [])}",
                f"Entpackte Größe: {size_mb:.1f} MB".replace(".", ","),
            ]
            if report.get("ignored"):
                lines.append(f"Ignorierte fremde Dateien: {len(report.get('ignored') or [])}")
            content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(9), bg_color=PANEL_BG)
            content.add_widget(AutoHeightLabel(
                text="[b]Backup beim nächsten Start wiederherstellen?[/b]\n\n" + html_escape("\n".join(lines)) +
                     "\n\nDie aktuelle Sammlung, Decks und Einstellungen werden durch den Inhalt des Backups ersetzt.",
                markup=True,
                color=TEXT,
                min_height=dp(190),
                height_padding=dp(18),
            ))
            buttons = GridLayout(cols=1 if self.ui_width_below(380) else 2, spacing=dp(8), size_hint_y=None)
            buttons.height = self.grid_height(2, buttons.cols, dp(50), dp(8))
            cancel = DarkButton(text="Abbrechen", bg=INPUT_BG_2)
            confirm = DarkButton(text="Wiederherstellung vormerken", bg=GOLD, bold=True)
            buttons.add_widget(cancel)
            buttons.add_widget(confirm)
            content.add_widget(buttons)
            popup = self.make_popup("Backup importieren", content, size_hint=(0.92, 0.62))
            cancel.bind(on_release=popup.dismiss)
            def confirm_restore(*_):
                try:
                    schedule_backup_restore(path, self.pending_restore_file)
                    popup.dismiss()
                    self.show_info(
                        "Backup vorgemerkt",
                        "Das Backup wird sicher vor dem Öffnen der Datenbank angewendet. Bitte die App vollständig schließen und erneut starten.",
                    )
                except Exception as exc:
                    self.show_error("Wiederherstellung fehlgeschlagen", str(exc))
            confirm.bind(on_release=confirm_restore)
            popup.open()
        except Exception as exc:
            self.show_error("Backup konnte nicht geprüft werden", str(exc))

    def import_backup_zip(self, *_):
        """Wählt ein Backup über Android SAF oder über Plyers Dateiauswahl."""
        import_dir = os.path.join(self.user_data_dir, "imports")
        os.makedirs(import_dir, exist_ok=True)
        if platform == "android":
            started = start_android_document_picker(
                import_dir,
                "application/zip",
                "backup_import",
                lambda path: Clock.schedule_once(lambda *_: self._accept_backup_import(path), 0),
                lambda message: Clock.schedule_once(lambda *_: self.set_status(message), 0),
            )
            if started:
                return
        try:
            from plyer import filechooser
            def selected(selection):
                value = selection[0] if isinstance(selection, (list, tuple)) and selection else (selection or "")
                if value:
                    Clock.schedule_once(lambda *_: self._accept_backup_import(str(value)), 0)
            try:
                filechooser.open_file(on_selection=selected, filters=[("ZIP-Backup", "*.zip")])
            except TypeError:
                filechooser.open_file(on_selection=selected)
        except Exception as exc:
            self.show_error("Dateiauswahl fehlgeschlagen", str(exc))

    def open_cache_management_popup(self, *_):
        report = self.cache_manager.report()
        size_mb = float(report.get("bytes") or 0) / (1024.0 * 1024.0)
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(9), bg_color=PANEL_BG)
        label = AutoHeightLabel(
            text=(
                f"[b]Bild- und Scanner-Cache[/b]\n"
                f"{int(report.get('files') or 0)} Dateien • {size_mb:.1f} MB\n\n".replace(".", ",") +
                "Das Leeren entfernt nur erneut ladbare Vorschaubilder und temporäre Scannerdateien. Sammlung, Decks und lokale Kartendatenbank bleiben erhalten."
            ),
            markup=True,
            color=TEXT,
            min_height=dp(150),
            height_padding=dp(18),
        )
        content.add_widget(label)
        clear_btn = DarkButton(text="Cache sicher leeren", bg=DANGER, size_hint_y=None, height=dp(50))
        content.add_widget(clear_btn)
        popup = self.make_popup("Cache verwalten", content, size_hint=(0.90, 0.52))
        def clear_cache(*_):
            result = self.cache_manager.clear()
            popup.dismiss()
            removed_mb = float(result.get("removed_bytes") or 0) / (1024.0 * 1024.0)
            self.show_info("Cache geleert", f"{result.get('removed_files', 0)} Dateien und {removed_mb:.1f} MB wurden entfernt.".replace(".", ","))
        clear_btn.bind(on_release=clear_cache)
        popup.open()

    def open_accessibility_popup(self, *_):
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(9), bg_color=PANEL_BG)
        title = AutoHeightLabel(
            text="[b]Barrierefreiheit & Datenverbrauch[/b]\nDie Einstellungen werden sofort gespeichert. Größere Touchflächen werden nach dem Neuaufbau der Oberfläche aktiv.",
            markup=True,
            color=TEXT,
            min_height=dp(86),
            height_padding=dp(14),
        )
        content.add_widget(title)
        status = DarkLabel(text="", markup=True, size_hint_y=None, height=dp(82), color=MUTED)
        content.add_widget(status)
        buttons = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        buttons.bind(minimum_height=buttons.setter("height"))
        reduce_btn = DarkButton(size_hint_y=None, height=dp(48), bg=INPUT_BG_2)
        touch_btn = DarkButton(size_hint_y=None, height=dp(48), bg=INPUT_BG_2)
        wifi_btn = DarkButton(size_hint_y=None, height=dp(48), bg=INPUT_BG_2)
        rebuild_btn = DarkButton(text="Oberfläche neu berechnen", size_hint_y=None, height=dp(48), bg=ACCENT_2)
        for button in (reduce_btn, touch_btn, wifi_btn, rebuild_btn):
            buttons.add_widget(button)
        content.add_widget(buttons)
        popup = self.make_popup("Barrierefreiheit", content, size_hint=(0.92, 0.70))
        def refresh():
            reduce_btn.text = f"Animationen reduzieren: {'Ein' if self.reduce_motion else 'Aus'}"
            touch_btn.text = f"Große Touchflächen: {'Ein' if self.large_touch_targets else 'Aus'}"
            wifi_btn.text = f"Kartenbilder nur über WLAN: {'Ein' if self.wifi_only_images else 'Aus'}"
            status.text = (
                f"Theme: [b]{html_escape(self.theme_name)}[/b] • "
                f"Systemschrift: {float(self.current_ui_profile().get('font_scale') or 1.0):.2f}×\n"
                "Statusinformationen werden zusätzlich mit Symbolen und Text dargestellt; Farbe allein ist nicht entscheidend."
            )
        def toggle(attr):
            setattr(self, attr, not bool(getattr(self, attr, False)))
            self.save_settings()
            refresh()
        reduce_btn.bind(on_release=lambda *_: toggle("reduce_motion"))
        touch_btn.bind(on_release=lambda *_: toggle("large_touch_targets"))
        wifi_btn.bind(on_release=lambda *_: toggle("wifi_only_images"))
        rebuild_btn.bind(on_release=lambda *_: (popup.dismiss(), self.rebuild_interface()))
        refresh()
        popup.open()

    def add_scan_history_entry(self, results, errors, added_count=0, added_variants=0):
        """Speichert einen kompakten, erneut öffnungsfähigen Scan-Verlauf."""
        try:
            serial_results = []
            for item in (results or []):
                card = item.get("card") or {}
                if not card:
                    continue
                serial_results.append({
                    "path": item.get("path", ""),
                    "attempt_path": item.get("attempt_path", ""),
                    "attempt": int(item.get("attempt") or 1),
                    "value": item.get("value", ""),
                    "kind": item.get("kind", "Name"),
                    "card": card,
                    "set_item": item.get("set_item") or {},
                    "matches": int(item.get("matches") or 0),
                    "language": item.get("language", "de"),
                    "language_label": item.get("language_label", "Deutsch"),
                    "score": float(item.get("score") or 0),
                    "confidence": int(item.get("confidence") or 0),
                    "confidence_reason": item.get("confidence_reason", ""),
                    "quality": item.get("quality") or {},
                    "count": int(item.get("count") or 1),
                })
            serial_errors = []
            for item in (errors or []):
                serial_errors.append({
                    "path": item.get("path", ""),
                    "value": item.get("value", ""),
                    "error": item.get("error", "Unbekannter Fehler"),
                    "quality": item.get("quality") or {},
                    "ignored": bool(item.get("ignored", False)),
                })
            entry = {
                "id": f"scan_{int(time.time() * 1000)}",
                "created_at": time.strftime("%d.%m.%Y %H:%M:%S"),
                "mode": self.scan_mode,
                "image_hits": len(serial_results),
                "errors_count": len(serial_errors),
                "added_count": int(added_count or 0),
                "added_variants": int(added_variants or 0),
                "results": serial_results,
                "errors": serial_errors,
            }
            self.scan_history.insert(0, entry)
            self.scan_history = self.scan_history[:20]
            self.save_scan_history()
            return entry
        except Exception:
            return None

    def load_last_scan_import_transaction(self):
        self.last_scan_import_transaction = {}
        try:
            data = safe_read_json(self.scan_undo_file, {})
            if isinstance(data, dict):
                self.last_scan_import_transaction = data
        except Exception:
            self.last_scan_import_transaction = {}

    def save_last_scan_import_transaction(self, transaction):
        self.last_scan_import_transaction = transaction or {}
        try:
            atomic_write_json(self.scan_undo_file, self.last_scan_import_transaction)
        except Exception:
            pass

    def undo_last_scan_import(self, *_):
        """Entfernt ausschließlich die Mengen des letzten bestätigten Sammelimports."""
        transaction = self.last_scan_import_transaction or {}
        entries = transaction.get("entries") or []
        if not entries:
            self.show_info("Nichts rückgängig", "Es gibt keinen gespeicherten Scan-Import, der rückgängig gemacht werden kann.")
            return
        removed = 0
        affected = 0
        for item in entries:
            try:
                key = str(item.get("key") or "")
                amount = max(0, int(item.get("amount") or 0))
                if not key or amount <= 0 or key not in self.collection:
                    continue
                current = int(self.collection[key].get("count", 0) or 0)
                take = min(current, amount)
                new_count = current - take
                removed += take
                affected += 1 if take else 0
                if new_count <= 0:
                    self.collection.pop(key, None)
                else:
                    self.collection[key]["count"] = new_count
            except Exception:
                continue
        self.save_last_scan_import_transaction({})
        self.update_collection_info()
        self.save_collection(show_popup=False)
        self.refresh_results_list()
        self.show_info("Scan-Import rückgängig", f"{removed} Exemplar(e) aus {affected} Karten/Varianten wurden wieder entfernt.")

    def show_start_loading_screen(self):
        """Nahtloser Marken-Startscreen passend zum nativen Android-Presplash.

        Android-Presplash und erster Kivy-Frame verwenden dieselbe Datei,
        Hintergrundfarbe und Skalierung. Dadurch gibt es beim Übergang kein
        schwarzes Zwischenbild, keinen Größen-Sprung des Logos und kein sichtbares
        Umschalten zwischen zwei unterschiedlich gestalteten Startscreens.
        """
        self.root_holder.clear_widgets()
        splash = FloatLayout()
        self._startup_splash_widget = splash
        with splash.canvas.before:
            self._splash_bg_color = Color(*STARTUP_BG)
            self._splash_bg_rect = RoundedRectangle(pos=splash.pos, size=splash.size, radius=[0])

        def update_bg(instance, *_):
            self._splash_bg_rect.pos = instance.pos
            self._splash_bg_rect.size = instance.size

        splash.bind(pos=update_bg, size=update_bg)
        presplash_source = resource_find(PRESPLASH_FILE) or (PRESPLASH_FILE if os.path.exists(PRESPLASH_FILE) else "")
        if presplash_source:
            branded_screen = Image(
                source=presplash_source,
                allow_stretch=True,
                keep_ratio=True,
                size_hint=(1, 1),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
            try:
                if hasattr(branded_screen, "fit_mode"):
                    branded_screen.fit_mode = "contain"
            except Exception:
                pass
            splash.add_widget(branded_screen)
        else:
            # Defensive fallback: gleiche Markenfarbe und dasselbe transparente Logo.
            logo_source = resource_find(APP_LOGO_TRANSPARENT_FILE) or resource_find(APP_LOGO_FILE) or ""
            splash.add_widget(Image(
                source=logo_source,
                allow_stretch=True,
                keep_ratio=True,
                size_hint=(0.58, 0.42),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            ))
        self.root_holder.add_widget(splash)

    def finish_start_loading_screen(self):
        hide_android_system_ui()
        try:
            self.rebuild_interface()
            self.install_android_shortcuts()
            self.record_performance("app_start", getattr(self, "_app_started_at", None), {"ui_profile": self.current_ui_profile()})
            Clock.schedule_once(lambda *_: self.restore_session_state(), 0.18)
            Clock.schedule_once(lambda *_: self.show_last_restore_result(), 0.28)
            Clock.schedule_once(lambda *_: self.ensure_first_launch_welcome_then_permissions(), 0.35)
            Clock.schedule_once(lambda *_: self.offer_resume_scan_queue(), 1.35)
            Clock.schedule_once(lambda *_: self.consume_android_shortcut(), 1.20)
        except Exception as exc:
            # Schutz, damit ein UI-Fehler die App nicht direkt wieder schließt.
            try:
                self.append_crash_log(exc)
            except Exception:
                pass
            self.root_holder.clear_widgets()
            fallback = SurfaceBox(orientation="vertical", padding=dp(14), spacing=dp(10), bg_color=PANEL_BG)
            fallback.add_widget(DarkLabel(text="[b]Startfehler abgefangen[/b]", markup=True, size_hint_y=None, height=dp(40)))
            fallback.add_widget(DarkLabel(text=f"Die App läuft weiter. Bitte Version/ZIP prüfen.\n\nDetails: {html_escape(str(exc))}", color=(1, 0.75, 0.75, 1)))
            retry = DarkButton(text="Erneut versuchen", size_hint_y=None, height=dp(48), bg=ACCENT_2, on_release=lambda *_: self.finish_start_loading_screen())
            fallback.add_widget(retry)
            self.root_holder.add_widget(fallback)

    def get_android_device_display_name(self):
        """Liefert Hersteller + Modell ohne zusätzliche Android-Berechtigung."""
        if platform == "android":
            try:
                from jnius import autoclass
                Build = autoclass("android.os.Build")
                manufacturer = str(Build.MANUFACTURER or "").strip()
                model = str(Build.MODEL or "").strip()
                if manufacturer and model:
                    if model.casefold().startswith(manufacturer.casefold()):
                        return model
                    return f"{manufacturer} {model}"
                return model or manufacturer or "Android-Gerät"
            except Exception:
                return "Android-Gerät"
        try:
            return str(os.uname().nodename or "dieses Gerät")
        except Exception:
            return "dieses Gerät"

    def ensure_first_launch_welcome_then_permissions(self):
        """Zeigt die Begrüßung exakt einmal nach einer frischen Installation."""
        if bool(getattr(self, "first_launch_welcome_seen", False)):
            self.ensure_first_run_permissions()
            return
        device_name = self.get_android_device_display_name()
        content = SurfaceBox(orientation="vertical", padding=dp(16), spacing=dp(12), bg_color=PANEL_BG)
        content.add_widget(AutoHeightLabel(
            text=(
                f"[b]{escape_markup(device_name)}[/b]\n\n"
                "Just InCard ist bereit. Scanner, Sammlung und Decks passen sich automatisch an dieses Gerät an."
            ),
            markup=True, color=TEXT, min_height=dp(130), height_padding=dp(18),
            font_size=ui_font_px(14, body=True),
        ))
        ok_btn = DarkButton(text="Los geht’s", bg=ACCENT, bold=True, size_hint_y=None, height=dp(52))
        content.add_widget(ok_btn)
        popup = self.make_popup("Herzlich Willkommen", content, size_hint=(0.88, 0.46))
        popup.auto_dismiss = False
        finished = {"value": False}
        def _finish(*_):
            if finished["value"]:
                return
            finished["value"] = True
            self.first_launch_welcome_seen = True
            self.save_settings()
            try:
                popup.dismiss()
            except Exception:
                pass
            Clock.schedule_once(lambda *_args: self.ensure_first_run_permissions(), 0.20)
        ok_btn.bind(on_release=_finish)
        popup.open()

    def ensure_first_run_permissions(self):
        hide_android_system_ui()
        if getattr(self, "permissions_requested", False):
            Clock.schedule_once(lambda *_: self.ensure_first_database_prompt(), 0.35)
            return

        def _permission_done(*_):
            self.permissions_requested = True
            self.save_settings()
            hide_android_system_ui()
            self.set_status("Berechtigungen gespeichert. Kamera und Export sind bereit.")
            Clock.schedule_once(lambda *_: self.ensure_first_database_prompt(), 0.55)

        started = request_android_runtime_permissions(callback=_permission_done)
        if not started:
            self.permissions_requested = True
            self.save_settings()
            Clock.schedule_once(lambda *_: self.ensure_first_database_prompt(), 0.55)

    def ensure_first_database_prompt(self):
        """v10.0 öffnet beim Start keinen zusätzlichen Datenbank-Dialog.

        Die neutrale Logo-Seite bleibt sichtbar. Eine fehlende Offline-Datenbank
        wird lediglich im Status vermerkt und kann unter Mehr → Datenbank oder
        über die Tablet-Navigation synchronisiert werden.
        """
        hide_android_system_ui()
        if getattr(self, "database_install_prompted", False):
            return
        self.database_install_prompted = True
        self.save_settings()
        try:
            existing_path = local_database_file("de")
            if os.path.exists(existing_path) and os.path.getsize(existing_path) > 1024 * 128:
                self.set_status("Lokale Kartendatenbank bereit. Scanner-Sofortsuche ist aktiv.")
            else:
                self.set_status("Offline-Datenbank fehlt. Unter Mehr → Datenbank synchronisieren für schnellere Scans.")
        except Exception:
            self.set_status("Datenbankstatus konnte nicht geprüft werden. Synchronisierung ist unter Mehr verfügbar.")


    def on_pause(self):
        # Android kann Apps im Hintergrund jederzeit beenden. Wichtige Nutzerdaten
        # werden deshalb vor dem Pausieren atomar gesichert.
        try:
            self.save_collection(show_popup=False)
            self.save_decks()
            self.save_settings()
            self.save_scan_history()
            self.save_session_state(show_popup=False)
        except Exception as exc:
            self.append_crash_log(exc, "on_pause")
        return True

    def on_stop(self):
        try:
            self.save_collection(show_popup=False)
            self.save_decks()
            self.save_settings()
            self.save_session_state(show_popup=False)
        except Exception as exc:
            self.append_crash_log(exc, "on_stop")

    def on_resume(self):
        hide_android_system_ui()
        self.start_background_screen_probe()
        Clock.schedule_once(lambda *_: self.apply_responsive_layout(force=True), 0.20)
        Clock.schedule_once(lambda *_: self.consume_android_shortcut(), 0.45)
        resume = getattr(self, "_scanner_resume_callback", None)
        if callable(resume) and getattr(self, "_current_section", "") == "scanner":
            Clock.schedule_once(lambda *_: resume(), 0.55)
        return True

    def on_start(self):
        hide_android_system_ui()
        self.start_background_screen_probe()

    def rebuild_interface(self):
        """Erstellt die moderne v10.0-Oberfläche vollständig neu.

        Smartphones verwenden eine ruhige, einspaltige Oberfläche mit kompakter
        Bottom-Navigation. Tablets erhalten eine Desktop-artige Rail-/List-Detail-
        Ansicht. Alle Größen werden ausschließlich in dp und anhand der aktuell
        nutzbaren Fensterbreite berechnet.
        """
        previous_ready = bool(getattr(self, "_interface_ready", False))
        target_section = str(getattr(self, "_current_section", "home") or "home")
        self._interface_ready = False
        profile = self.current_ui_profile()
        filters = self.get_filters_safe()
        selected = self.selected_card
        page = self.current_page
        set_palette(self.theme_name)
        Window.clearcolor = STARTUP_BG if str(getattr(self, "theme_name", "dark")) == "dark" else DARK_BG
        self.root_holder.clear_widgets()

        # Grundgerüst: Rail + Inhaltsfläche + optionale Bottom-Navigation.
        self.app_shell = BoxLayout(orientation="horizontal", size_hint_y=1)
        self.navigation_rail = SurfaceBox(
            orientation="vertical",
            size_hint_x=None,
            width=0,
            spacing=dp(8),
            padding=dp(8),
            bg_color=PANEL_BG,
            radius=0,
            border_color=(0, 0, 0, 0),
        )
        self.page_host = BoxLayout(orientation="vertical")
        self.main_scroll = ScrollView(
            bar_width=dp(4),
            scroll_type=["bars", "content"],
            do_scroll_x=False,
        )
        self.content = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(10),
            size_hint_y=None,
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        self.main_scroll.add_widget(self.content)
        self.page_host.add_widget(self.main_scroll)
        self.app_shell.add_widget(self.navigation_rail)
        self.app_shell.add_widget(self.page_host)

        self.bottom_navigation = SurfaceBox(
            orientation="horizontal",
            size_hint_y=None,
            height=0,
            spacing=dp(4),
            padding=dp(4),
            bg_color=PANEL_BG,
            radius=0,
            border_color=(0, 0, 0, 0),
        )
        self.root_holder.add_widget(self.app_shell)
        self.root_holder.add_widget(self.bottom_navigation)

        def go_search(*_):
            self.show_search_page()

        def go_scanner(*_):
            if str(getattr(self, "_current_section", "") or "") == "scanner":
                toggle_bubbles = getattr(self, "_toggle_scanner_source_bubbles", None)
                if callable(toggle_bubbles):
                    try:
                        toggle_bubbles()
                        return
                    except Exception:
                        pass
            self.open_camera_scanner()

        nav_actions = [
            ("search", "Suche", "search", go_search),
            ("collection", "Karten", "cards", lambda *_: self.open_collection_popup()),
            ("scanner", "Scan", "scan", go_scanner),
            ("decks", "Decks", "decks", lambda *_: self.open_decks_popup()),
            ("more", "Mehr", "more", lambda *_: self.open_settings_popup()),
        ]
        self.navigation_rail_buttons = []
        self.bottom_navigation_buttons = []
        self._navigation_button_map = {}

        self.rail_brand = SurfaceBox(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(76),
            spacing=dp(8),
            padding=(dp(8), dp(8)),
            bg_color=PANEL_BG_2,
            border_color=tuple(list(ACCENT[:3]) + [0.18]),
            radius=dp(18),
        )
        self.rail_logo = LogoView(ui_asset("app_mark") or resource_find(APP_LOGO_TRANSPARENT_FILE) or resource_find(APP_LOGO_FILE), size_hint=(None, 1), width=dp(44))
        self.rail_brand.add_widget(self.rail_logo)
        rail_brand_text = BoxLayout(orientation="vertical", spacing=0)
        rail_brand_text.add_widget(DarkLabel(text="[b]Just InCard[/b]", markup=True, color=TEXT, halign="left", font_size=ui_font_px(13.5, profile)))
        rail_brand_text.add_widget(DarkLabel(text="Deine Karten", color=MUTED, halign="left", font_size=ui_font_px(9.4, profile, body=True)))
        self.rail_brand.add_widget(rail_brand_text)
        self.navigation_rail.add_widget(self.rail_brand)

        for key, label, icon_name, callback in nav_actions:
            rail_btn = NavigationItem(
                icon_name,
                label,
                vertical=False,
                size_hint_y=None,
                height=dp(52),
            )
            rail_btn.bind(on_release=callback)
            self.navigation_rail.add_widget(rail_btn)
            self.navigation_rail_buttons.append(rail_btn)

            bottom_btn = NavigationItem(
                icon_name,
                label,
                vertical=True,
                size_hint=(1, 1),
            )
            bottom_btn.bind(on_release=callback)
            self.bottom_navigation.add_widget(bottom_btn)
            self.bottom_navigation_buttons.append(bottom_btn)
            self._navigation_button_map[key] = (rail_btn, bottom_btn)

        self.navigation_rail.add_widget(BoxLayout(size_hint_y=1))
        self.rail_status_card = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            height=dp(102),
            spacing=dp(3),
            padding=dp(9),
            bg_color=CARD_BG,
            border_color=tuple(list(SUCCESS[:3]) + [0.22]),
            radius=dp(16),
        )
        self.rail_status_label = DarkLabel(
            text="[b]Datenbank[/b]\n[color=#55D6A5]Geräteprofil aktiv[/color]\nLayout automatisch",
            markup=True,
            color=TEXT,
            halign="left",
            font_size=ui_font_px(9.7, profile, body=True),
        )
        self.rail_status_card.add_widget(self.rail_status_label)
        # Diagnoseinformationen gehören in Mehr → App-Diagnose und nicht dauerhaft
        # in die Navigation.
        self.rail_status_card.height = 0
        self.rail_status_card.opacity = 0
        self.rail_status_card.disabled = True

        # Moderne, kompakte App-Leiste ohne doppelte Sammlungs-/Deckbuttons.
        logo_source = ui_asset("app_mark") or resource_find(APP_LOGO_TRANSPARENT_FILE) or resource_find(APP_LOGO_FILE) or ""
        self.header = SurfaceBox(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(72),
            spacing=dp(10),
            padding=(dp(10), dp(8), dp(10), dp(8)),
            bg_color=PANEL_BG_2,
            radius=dp(20),
        )
        self.title_row = self.header
        self.logo_view = LogoView(logo_source, size_hint=(None, None), width=dp(52), height=dp(52))
        self.logo_view.bind(on_touch_down=lambda widget, touch: self.show_home_page() if widget.collide_point(*touch.pos) else False)
        self.header.add_widget(self.logo_view)

        self.title_box = BoxLayout(orientation="vertical", spacing=0, size_hint_x=1)
        self.app_title_label = DarkLabel(
            text=f"[b]{APP_DISPLAY_NAME}[/b]",
            markup=True,
            font_size=ui_font_px(20, profile),
            size_hint_y=None,
            height=dp(30),
            color=TEXT,
            halign="left",
        )
        self.app_subtitle_label = DarkLabel(
            text="Deine Karten. Einfach organisiert.",
            color=MUTED,
            font_size=ui_font_px(10.5, profile, body=True),
            size_hint_y=None,
            height=dp(22),
            halign="left",
        )
        self.title_box.add_widget(self.app_title_label)
        self.title_box.add_widget(self.app_subtitle_label)
        self.header.add_widget(self.title_box)

        self.header_right_meta = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(220),
            spacing=dp(6),
        )
        self.collection_info_label = DarkLabel(
            text="0 Karten",
            color=TEXT,
            size_hint_x=1,
            halign="right",
            valign="middle",
            font_size=ui_font_px(11.5, profile),
        )
        self.header_right_meta.add_widget(self.collection_info_label)
        # v10.0: Zahnrad und Fragezeichen werden aus der Kopfzeile entfernt.
        # Einstellungen/Hilfe liegen geordnet im Bereich „Mehr“. Die Attribute
        # bleiben unsichtbar erhalten, damit ältere Layout-Helfer kompatibel bleiben.
        self.settings_button = HeaderImageButton("", fallback_text="", size_hint=(None, None), width=0, height=0)
        self.help_button = HeaderImageButton("", fallback_text="", size_hint=(None, None), width=0, height=0)
        self.settings_button.opacity = self.help_button.opacity = 0
        self.settings_button.disabled = self.help_button.disabled = True
        self.header_right_meta.width = dp(86)
        self.header.add_widget(self.header_right_meta)
        self.content.add_widget(self.header)

        # Auf Tablets wird die vorhandene Funktionsvielfalt als ruhiges Dashboard
        # sichtbar. Smartphones behalten die kurze Suche ohne zusätzliche Höhe.
        self.tablet_dashboard = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            height=0,
            opacity=0,
            disabled=True,
            spacing=dp(8),
            padding=dp(10),
            bg_color=PANEL_BG,
            border_color=tuple(list(ACCENT[:3]) + [0.20]),
            radius=dp(20),
        )
        self.tablet_dashboard_title = SectionTitle("Schnellzugriff", "Sammlung, Scanner, Daten und Einstellungen", accent=ACCENT)
        self.tablet_dashboard.add_widget(self.tablet_dashboard_title)
        self.tablet_quick_grid = GridLayout(cols=3, size_hint_y=None, spacing=dp(8), height=dp(156))
        quick_actions = [
            ("cards", "Sammlung", "Karten verwalten", lambda *_: self.open_collection_popup(), ACCENT),
            ("decks", "Decks", "Decks erstellen", lambda *_: self.open_decks_popup(), ACCENT_2),
            ("scan", "Scanner", "Live, Foto oder Galerie", lambda *_: self.open_camera_scanner(), GOLD),
            ("database", "Datenbank", "Offline-Daten synchronisieren", lambda *_: self.open_database_popup(), SUCCESS),
            ("web", "Web-Quellen", "Datenquellen verwalten", lambda *_: self.open_external_sources_popup(), ACCENT),
            ("settings", "Einstellungen", "Darstellung und Wartung", lambda *_: self.open_settings_popup(), ACCENT_2),
        ]
        self.tablet_quick_tiles = []
        for icon_name, title, subtitle, callback, tile_accent in quick_actions:
            tile = ActionTile(icon_name, title, subtitle, accent=tile_accent, size_hint_y=None, height=dp(74))
            tile.bind(on_release=callback)
            self.tablet_quick_tiles.append(tile)
            self.tablet_quick_grid.add_widget(tile)
        self.tablet_dashboard.add_widget(self.tablet_quick_grid)
        self.content.add_widget(self.tablet_dashboard)

        # Einfache Suche: wichtigste Felder direkt sichtbar, alles Weitere einklappbar.
        self.search_wrap = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(14),
            spacing=dp(10),
            bg_color=PANEL_BG,
            border_color=tuple(list(ACCENT[:3]) + [0.18]),
            radius=dp(24),
            elevation=1,
        )
        self.search_wrap.bind(minimum_height=self.search_wrap.setter("height"))
        heading = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(64), spacing=dp(10))
        heading_icon = SurfaceBox(
            orientation="vertical", size_hint=(None, None), width=dp(48), height=dp(48),
            padding=dp(10), bg_color=tuple(list(ACCENT[:3]) + [0.14]),
            border_color=tuple(list(ACCENT[:3]) + [0.24]), radius=dp(16),
        )
        heading_icon.add_widget(Image(source=ui_asset("search"), allow_stretch=True, keep_ratio=True))
        heading.add_widget(heading_icon)
        heading.add_widget(AutoHeightLabel(
            text=f"[b]Karten finden[/b]\n[color={markup_hex(MUTED)}]Set-Code und Passcode werden exakt geprüft; der Name dient als komfortable Suche.[/color]",
            markup=True,
            color=TEXT,
            min_height=dp(56),
            font_size=ui_font_px(text_sp_v110("section", profile), profile, body=True),
        ))
        self.search_wrap.add_widget(heading)

        self.search_priority_strip = GridLayout(cols=3, size_hint_y=None, height=dp(38), spacing=dp(6))
        for chip_text, chip_icon, chip_active in [
            ("1  Set-Code", "database", True),
            ("2  Passcode", "scan", True),
            ("3  Name", "search", False),
        ]:
            self.search_priority_strip.add_widget(ModernChip(chip_text, chip_icon, active=chip_active, accent=ACCENT))
        self.search_wrap.add_widget(self.search_priority_strip)

        self.name_input = DarkInput(hint_text="Kartenname")
        self.set_input = DarkInput(hint_text="Set, Set-Code oder Kürzel")
        self.language_spinner = DarkSpinner(text="Deutsch", values=LANGUAGES)
        self.card_id_input = DarkInput(hint_text="Karten-ID / Passcode")
        self.atk_input = DarkInput(hint_text="ATK")
        self.def_input = DarkInput(hint_text="DEF")
        self.level_input = DarkInput(hint_text="Stufe / Rang / Link")
        self.race_input = DarkInput(hint_text="Typ, z. B. Drache")
        self.attribute_spinner = DarkSpinner(text="Eigenschaft", values=ATTRIBUTES)
        self.group_spinner = DarkSpinner(text="Alle", values=GROUPS)
        self.primary_filter_widgets = [self.name_input, self.set_input, self.language_spinner]
        self.advanced_filter_widgets = [
            self.card_id_input, self.atk_input, self.def_input, self.level_input,
            self.race_input, self.attribute_spinner, self.group_spinner,
        ]
        self.filter_widgets = self.primary_filter_widgets + self.advanced_filter_widgets
        for widget in self.filter_widgets:
            widget.size_hint_y = None
            widget.height = dp(52)
        for input_widget in [self.name_input, self.set_input, self.card_id_input, self.atk_input, self.def_input, self.level_input, self.race_input]:
            try:
                input_widget.bind(on_text_validate=lambda *_: self.start_search())
            except Exception:
                pass

        self.search_panel = GridLayout(cols=1, size_hint_y=None, spacing=dp(8))
        self.search_panel.bind(minimum_height=self.search_panel.setter("height"))
        for widget in self.primary_filter_widgets:
            self.search_panel.add_widget(widget)
        self.search_wrap.add_widget(self.search_panel)

        if not hasattr(self, "_advanced_filters_collapsed"):
            self._advanced_filters_collapsed = True
        self.filter_toggle_btn = DarkButton(
            text="Mehr Filter",
            bg=INPUT_BG_2,
            size_hint_y=None,
            height=dp(46),
            on_release=lambda *_: self.toggle_advanced_filters(),
            no_wrap=True,
        )
        self.search_wrap.add_widget(self.filter_toggle_btn)

        self.advanced_search_panel = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), height=0, opacity=0, disabled=True)
        self.advanced_search_panel.bind(minimum_height=self._sync_advanced_panel_height)
        for widget in self.advanced_filter_widgets:
            self.advanced_search_panel.add_widget(widget)
        self.search_wrap.add_widget(self.advanced_search_panel)

        self.action_row = GridLayout(cols=2, size_hint_y=None, height=dp(104), spacing=dp(8))
        self.search_button = DarkButton(text="Suchen", bg=ACCENT, bold=True, no_wrap=True, on_release=lambda *_: self.start_search())
        self.clear_search_button = DarkButton(text="Leeren", bg=ACCENT_2, no_wrap=True, on_release=lambda *_: self.clear_filters())
        self.custom_card_button = DarkButton(text="Eigene Karte", bg=ACCENT_2, no_wrap=True, on_release=lambda *_: self.open_custom_card_popup())
        self.search_action_buttons = [self.search_button, self.clear_search_button, self.custom_card_button]
        for action_button in self.search_action_buttons:
            self.action_row.add_widget(action_button)
        self.search_wrap.add_widget(self.action_row)

        # Scanner und Web-Quellen gehören seit v10.0 nicht mehr zur Suchseite.
        self.secondary_action_row = GridLayout(cols=1, size_hint_y=None, height=0, spacing=0, opacity=0, disabled=True)
        self.search_wrap.add_widget(self.secondary_action_row)

        self.database_profile_strip = SurfaceBox(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(46),
            spacing=dp(8),
            padding=(dp(9), dp(6)),
            bg_color=INPUT_BG,
            border_color=tuple(list(SUCCESS[:3]) + [0.18]),
            radius=dp(14),
        )
        self.database_profile_strip.add_widget(Image(source=ui_asset("database"), size_hint=(None, 1), width=dp(28), allow_stretch=True, keep_ratio=True))
        self.database_profile_label = DarkLabel(
            text="Lokale Datenbank und Geräteprofil werden automatisch erkannt.",
            color=MUTED,
            halign="left",
            font_size=ui_font_px(10.5, profile, body=True),
        )
        self.database_profile_strip.add_widget(self.database_profile_label)
        self.search_wrap.add_widget(self.database_profile_strip)

        self.status_label = AutoHeightLabel(
            text="Bereit. Suche nach Name, Set-Code oder Karten-ID.",
            color=MUTED,
            min_height=dp(34),
            height_padding=dp(10),
            font_size=ui_font_px(11.5, profile, body=True),
        )
        self.search_wrap.add_widget(self.status_label)
        self.content.add_widget(self.search_wrap)

        # Ergebnisliste und Detailansicht. Auf Smartphones untereinander, auf
        # Tablets nebeneinander wie in einer Desktop-Anwendung.
        self.middle = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None)
        self.left = SurfaceBox(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(10),
            size_hint_x=0.52,
            bg_color=PANEL_BG,
            radius=dp(20),
        )
        self.left.add_widget(SectionTitle("Ergebnisse", f"Bis zu {PAGE_SIZE} Karten pro Seite", accent=ACCENT))
        self.result_meta_label = AutoHeightLabel(
            text="Noch keine Suche ausgeführt.",
            color=MUTED,
            min_height=dp(26),
            height_padding=dp(8),
            font_size=ui_font_px(11.5, profile, body=True),
        )
        self.left.add_widget(self.result_meta_label)
        self.pager_row = GridLayout(cols=3, size_hint_y=None, height=dp(50), spacing=dp(8))
        self.prev_page_btn = DarkButton(text="Zurück", bg=INPUT_BG_2, no_wrap=True, on_release=lambda *_: self.prev_page())
        self.page_label = DarkLabel(text="Seite 0 / 0", color=MUTED, halign="center")
        self.next_page_btn = DarkButton(text="Weiter", bg=INPUT_BG_2, no_wrap=True, on_release=lambda *_: self.next_page())
        self.pager_row.add_widget(self.prev_page_btn)
        self.pager_row.add_widget(self.page_label)
        self.pager_row.add_widget(self.next_page_btn)
        self.left.add_widget(self.pager_row)
        self.results_grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter("height"))
        self.results_grid.bind(height=lambda *_: self._schedule_compact_panel_refresh())
        self.results_scroll = ScrollView(bar_width=dp(4), scroll_type=["bars", "content"], do_scroll_x=False)
        self.results_scroll.add_widget(self.results_grid)
        self.left.add_widget(self.results_scroll)

        self.right = SurfaceBox(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(10),
            size_hint_x=0.48,
            bg_color=PANEL_BG,
            radius=dp(20),
        )
        self.right.add_widget(SectionTitle("Kartendetails", "Artwork, Werte, Effekt und Druckvarianten", accent=GOLD))
        self.detail_identity_card = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            height=dp(86),
            spacing=dp(2),
            padding=(dp(12), dp(8)),
            bg_color=CARD_BG,
            border_color=tuple(list(GOLD[:3]) + [0.16]),
            radius=dp(18),
        )
        self.detail_name_label = DarkLabel(
            text="[b]Noch keine Karte ausgewählt[/b]",
            markup=True,
            color=TEXT,
            halign="left",
            size_hint_y=None,
            height=dp(42),
            font_size=ui_font_px(15.5, profile),
        )
        self.detail_meta_label = DarkLabel(
            text="Tippe auf ein Suchergebnis, um Artwork und Kartendaten zu öffnen.",
            color=MUTED,
            halign="left",
            size_hint_y=None,
            height=dp(28),
            font_size=ui_font_px(10.5, profile, body=True),
        )
        self.detail_identity_card.add_widget(self.detail_name_label)
        self.detail_identity_card.add_widget(self.detail_meta_label)
        self.right.add_widget(self.detail_identity_card)

        self.preview_frame = SurfaceBox(
            orientation="vertical",
            bg_color=INPUT_BG,
            border_color=tuple(list(GOLD[:3]) + [0.30]),
            radius=dp(22),
            size_hint_y=None,
            height=dp(380),
            padding=dp(10),
            elevation=1,
        )
        preview_float = FloatLayout()
        placeholder_source = resource_find(PREVIEW_PLACEHOLDER_FILE) or ""
        self.preview_placeholder_image = Image(source=placeholder_source, allow_stretch=True, keep_ratio=True, opacity=1, pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(0.92, 0.92))
        self.preview_image = Image(source="", allow_stretch=True, keep_ratio=True, opacity=0, pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(0.98, 0.98))
        self.preview_image.bind(on_touch_down=self._on_preview_touch)
        self.preview_placeholder = DarkLabel(text="", markup=True, color=MUTED, halign="center", valign="middle", opacity=0, pos_hint={"center_x": 0.5, "center_y": 0.14}, size_hint=(0.92, 0.22))
        preview_float.add_widget(self.preview_placeholder_image)
        preview_float.add_widget(self.preview_image)
        preview_float.add_widget(self.preview_placeholder)
        self.preview_frame.add_widget(preview_float)
        self.right.add_widget(self.preview_frame)

        self.stats_row = GridLayout(cols=2, size_hint_y=None, height=dp(92), spacing=dp(8))
        self.info_type = StatPill(text="Typ: -", markup=True)
        self.info_attribute = StatPill(text="Eigenschaft: -", markup=True)
        self.info_level = StatPill(text="Stufe / Rang / Link: -", markup=True)
        self.info_values = StatPill(text="ATK - / DEF -", markup=True)
        for widget in [self.info_type, self.info_attribute, self.info_level, self.info_values]:
            self.stats_row.add_widget(widget)
        self.right.add_widget(self.stats_row)

        self.detail_card = SurfaceBox(orientation="vertical", bg_color=INPUT_BG, border_color=(1, 1, 1, 0.07), radius=dp(16), size_hint_y=None, height=dp(260), padding=dp(10))
        self.detail_label = DarkLabel(text="Wähle eine Karte aus, um Details zu sehen.", color=MUTED, markup=True, size_hint_y=None)
        self.detail_label.bind(texture_size=lambda instance, value: setattr(instance, "height", max(value[1] + dp(18), dp(220))))
        detail_scroll = ScrollView(bar_width=dp(4), scroll_type=["bars", "content"], do_scroll_x=False)
        detail_scroll.add_widget(self.detail_label)
        self.detail_card.add_widget(detail_scroll)
        self.right.add_widget(self.detail_card)

        self.img_btn_row = GridLayout(cols=3, size_hint_y=None, height=dp(50), spacing=dp(8))
        self.img_btn_row.add_widget(DarkButton(text="Artwork", bg=ACCENT_2, no_wrap=True, compact=True, on_release=lambda *_: self.open_selected_image()))
        self.img_btn_row.add_widget(DarkButton(text="Effekttext", bg=ACCENT, no_wrap=True, compact=True, on_release=lambda *_: self.show_selected_effect()))
        self.img_btn_row.add_widget(DarkButton(text="Sets & Reprints", bg=GOLD, no_wrap=True, compact=True, on_release=lambda *_: self.show_selected_reprints()))
        self.right.add_widget(self.img_btn_row)

        self.middle.add_widget(self.left)
        self.middle.add_widget(self.right)
        self.content.add_widget(self.middle)

        self.apply_filters_to_widgets(filters)
        self.current_page = page
        self.update_collection_info()
        self.render_current_page()
        if selected:
            self.select_card(selected, load_image=True)
        self._interface_ready = True
        self.apply_responsive_layout(force=True)
        # Nur beim echten App-Start wird die neutrale Logo-Seite erzwungen. Bei
        # einem Theme-/Layout-Neuaufbau bleibt der zuvor geöffnete Hauptbereich erhalten.
        if not previous_ready or target_section == "home":
            self.show_home_page()
        elif target_section == "search":
            self.show_search_page()
        elif target_section == "scanner":
            Clock.schedule_once(lambda *_: self.open_camera_scanner(), 0)
        elif target_section == "collection":
            Clock.schedule_once(lambda *_: self.open_collection_popup(), 0)
        elif target_section == "decks":
            Clock.schedule_once(lambda *_: self.open_decks_popup(), 0)
        elif target_section == "more":
            Clock.schedule_once(lambda *_: self.open_settings_popup(), 0)
        else:
            self.show_home_page()
        Clock.schedule_once(lambda *_: self.apply_responsive_layout(force=True), 0)

    def _set_navigation_active(self, key):
        """Markiert den aktiven Hauptbereich ohne zusätzliche Icons oder Textumbruch."""
        try:
            for nav_key, pair in getattr(self, "_navigation_button_map", {}).items():
                for button in pair:
                    try:
                        if hasattr(button, "set_active"):
                            button.set_active(nav_key == key)
                            continue
                        color = ACCENT if nav_key == key else INPUT_BG_2
                        button._bg_color = color
                        button._color_bg.rgba = color
                        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                        button.color = (0.055, 0.070, 0.110, 1) if luminance > 0.50 else (1, 1, 1, 1)
                    except Exception:
                        pass
        except Exception:
            pass

    def _sync_advanced_panel_height(self, *_):
        try:
            if getattr(self, "_advanced_filters_collapsed", True):
                self.advanced_search_panel.height = 0
            else:
                self.advanced_search_panel.height = self.advanced_search_panel.minimum_height
        except Exception:
            pass

    def toggle_advanced_filters(self, *_):
        self._advanced_filters_collapsed = not bool(getattr(self, "_advanced_filters_collapsed", True))
        try:
            self.filter_toggle_btn.text = "Mehr Filter" if self._advanced_filters_collapsed else "Weniger Filter"
        except Exception:
            pass
        self.apply_responsive_layout(force=True)

    def _schedule_compact_panel_refresh(self, *_):
        """Aktualisiert dynamische Smartphone-Panels nach Ergebnis-/Textänderungen."""
        if not getattr(self, "_interface_ready", False):
            return
        try:
            if self._compact_panel_event is not None:
                self._compact_panel_event.cancel()
        except Exception:
            pass
        self._compact_panel_event = Clock.schedule_once(lambda *_: self.apply_responsive_layout(force=True), 0.06)

    def _sync_content_height(self, *_):
        try:
            profile = getattr(self, "ui_profile", {}) or {}
            safe = profile.get("safe", {})
            visible_h = max(dp(240), Window.height - float(safe.get("top", 0)) - float(safe.get("bottom", 0)))
            self.content.height = max(self.content.minimum_height, visible_h)
        except Exception:
            self.content.height = max(self.content.minimum_height, Window.height)

    def _schedule_responsive_layout(self, *_):
        try:
            orientation = bool(Window.width > Window.height)
            previous_size = getattr(self, "_last_probe_window_size", (Window.width, Window.height))
            previous_w = max(1.0, float(previous_size[0] or 1))
            previous_h = max(1.0, float(previous_size[1] or 1))
            changed_significantly = (
                abs(float(Window.width) - previous_w) / previous_w > 0.08
                or abs(float(Window.height) - previous_h) / previous_h > 0.08
            )
            if orientation != getattr(self, "_last_probe_orientation", orientation) or changed_significantly:
                self._last_probe_orientation = orientation
                self._last_probe_window_size = (float(Window.width), float(Window.height))
                self.start_background_screen_probe()
            self.ui_profile = build_ui_profile(getattr(self, "screen_metrics", {}), (Window.width, Window.height))
        except Exception:
            pass
        if self._layout_event:
            try:
                self._layout_event.cancel()
            except Exception:
                pass
        # Etwas längeres Debounce verhindert Layout-Flackern beim Drehen/Falten.
        self._layout_event = Clock.schedule_once(lambda *_: self.apply_responsive_layout(), 0.02 if getattr(self, "reduce_motion", False) else 0.14)

    def apply_responsive_layout(self, force=False):
        """Legt die v11.2.3-Oberfläche anhand der nutzbaren Fensterbreite neu aus.

        Wichtig ist nicht die physische Pixelzahl, sondern die Breite in dp. Damit
        sehen verschiedene Smartphones nebeneinander nahezu gleich aus, während
        Tablets automatisch eine Desktop-artige List-/Detailansicht erhalten.
        """
        if not getattr(self, "_interface_ready", False) and not force:
            return
        try:
            profile = self.current_ui_profile()
            width = float(max(1, Window.width))
            height = float(max(1, Window.height))
            safe = profile.get("safe", {})
            safe_left = float(safe.get("left", 0) or 0)
            safe_top = float(safe.get("top", 0) or 0)
            safe_right = float(safe.get("right", 0) or 0)
            safe_bottom = float(safe.get("bottom", 0) or 0)
            width_dp = float(profile.get("width_dp") or (width / max(0.5, float(profile.get("density") or 1.0))))
            is_tablet = bool(profile.get("is_tablet")) and width_dp >= 600
            desktop_tablet = is_tablet and width_dp >= 840
            compact_phone = not is_tablet and width_dp < 360
            phone_landscape = not is_tablet and bool(profile.get("landscape"))

            # Sichtbare Bestätigung, dass reale Android-Metriken verwendet werden.
            density_value = float(profile.get("density") or 1.0)
            device_label = "Tablet" if is_tablet else "Smartphone"
            layout_label = "Seitenleiste" if is_tablet and width_dp >= 720 else "Bottom-Navigation"
            if hasattr(self, "database_profile_label"):
                if compact_phone:
                    self.database_profile_label.text = f"{device_label} · {int(width_dp)} dp · automatische Skalierung"
                else:
                    density_text = (f"{density_value:.2f}").replace(".", ",")
                    self.database_profile_label.text = f"{device_label} · {int(width_dp)} dp · Dichte {density_text}× · sichere Ränder aktiv"
            if hasattr(self, "rail_status_label"):
                self.rail_status_label.text = (
                    f"[b]Geräteprofil[/b]\n[color=#55D6A5]{device_label} erkannt[/color]\n"
                    f"{int(width_dp)} dp · {layout_label}"
                )

            gap = dp(float(profile.get("gap_dp") or (8 if not is_tablet else 10)))
            outer = dp(float(profile.get("outer_margin_dp") or (8 if compact_phone else (10 if not is_tablet else 14))))
            inline_outer = getattr(self, "_inline_page_outer", None)
            if inline_outer is not None:
                inline_outer.padding = (
                    safe_left + outer,
                    safe_top + outer,
                    safe_right + outer,
                    outer,
                )
            touch_base = float(profile.get("touch_dp") or 50)
            if getattr(self, "large_touch_targets", False):
                touch_base = max(56.0, touch_base)
            touch = dp(touch_base)

            # Navigation: Bottom-Bar auf Smartphones, klare Rail ab 720 dp.
            if is_tablet and width_dp >= 720:
                rail_width = dp(176 if width_dp < 1000 else 208)
                self.navigation_rail.width = rail_width
                self.navigation_rail.opacity = 1
                self.navigation_rail.disabled = False
                self.navigation_rail.padding = (dp(10), safe_top + dp(10), dp(10), safe_bottom + dp(10))
                self.navigation_rail.spacing = dp(8)
                self.bottom_navigation.height = 0
                self.bottom_navigation.opacity = 0
                self.bottom_navigation.disabled = True
                self.rail_brand.height = dp(76)
                self.rail_status_card.height = 0
                self.rail_status_card.opacity = 0
                self.rail_status_card.disabled = True
                for button in self.navigation_rail_buttons:
                    button.height = dp(52)
                    button.apply_profile(profile)
                bottom_height = 0
            else:
                rail_width = 0
                self.navigation_rail.width = 0
                self.navigation_rail.opacity = 0
                self.navigation_rail.disabled = True
                nav_core = dp(58 if compact_phone else 64)
                bottom_height = nav_core + safe_bottom + dp(6)
                self.bottom_navigation.height = bottom_height
                self.bottom_navigation.opacity = 1
                self.bottom_navigation.disabled = False
                self.bottom_navigation.padding = (dp(4), dp(3), dp(4), safe_bottom + dp(2))
                self.bottom_navigation.spacing = dp(3)
                for button in self.bottom_navigation_buttons:
                    button.apply_profile(profile)

            # Auf Smartphones wird die Inhaltsspalte auf höchstens 480 dp begrenzt.
            # Dadurch bleiben Ränder und Größen zwischen unterschiedlichen Geräten konsistent.
            usable_w = max(dp(260), width - safe_left - safe_right - rail_width)
            max_content_dp = float(profile.get("content_max_dp") or (560.0 if not is_tablet else 1040.0))
            if is_tablet:
                max_content_dp = min(max_content_dp, 1240.0 if desktop_tablet else 960.0)
            max_content = dp(max_content_dp)
            side_center = max(0.0, (usable_w - max_content) / 2.0)
            self.content.padding = (
                safe_left + outer + side_center,
                safe_top + outer,
                safe_right + outer + side_center,
                outer,
            )
            self.content.spacing = gap
            self.main_scroll.bar_width = dp(3 if compact_phone else 4)

            # App-Leiste.
            header_h = dp(64 if compact_phone else (70 if not is_tablet else 78))
            logo_side = dp(44 if compact_phone else (50 if not is_tablet else 58))
            self.header.height = header_h
            self.header.spacing = dp(7 if compact_phone else 10)
            self.header.padding = (dp(8), dp(7), dp(8), dp(7))
            self.logo_view.size = (logo_side, logo_side)
            self.app_title_label.height = dp(28 if compact_phone else 31)
            self.app_title_label.font_size = ui_font_px(18 if compact_phone else (20 if not is_tablet else 23), profile)
            self.app_subtitle_label.font_size = ui_font_px(9.5 if compact_phone else 10.5, profile, body=True)
            self.app_subtitle_label.height = 0 if compact_phone else dp(20)
            self.app_subtitle_label.opacity = 0 if compact_phone else 1

            # v10.0 hält die Kopfzeile auf allen Geräten ruhig: nur Logo, Name
            # und Sammlungszähler; Zahnrad/Fragezeichen befinden sich unter „Mehr“.
            self.header_right_meta.width = dp(82 if compact_phone else (96 if not is_tablet else 116))
            self.settings_button.size = (0, 0)
            self.help_button.size = (0, 0)
            self.settings_button.opacity = self.help_button.opacity = 0
            self.settings_button.disabled = self.help_button.disabled = True
            self.collection_info_label.font_size = ui_font_px(9.4 if compact_phone else 10.8, profile)

            # Die Suchseite bleibt auf allen Geräten auf Textsuche, Ergebnisliste
            # und Vorschau beschränkt. Schnellzugriffe liegen in der Navigation.
            self.tablet_dashboard.height = 0
            self.tablet_dashboard.opacity = 0
            self.tablet_dashboard.disabled = True

            # Suchkarte: Spalten folgen dem zentral getesteten v11.2.3-Profil.
            search_cols = max(1, int(profile.get("search_columns") or 1))
            self.search_panel.cols = search_cols
            self.search_panel.spacing = gap
            for widget in self.primary_filter_widgets:
                widget.height = touch
            primary_rows = int(math.ceil(len(self.primary_filter_widgets) / float(search_cols)))
            self.search_panel.height = primary_rows * touch + max(0, primary_rows - 1) * gap

            collapsed = bool(getattr(self, "_advanced_filters_collapsed", True))
            adv_cols = 1 if compact_phone else max(1, min(3, int(profile.get("search_columns") or 1) + (1 if is_tablet and width_dp >= 900 else 0)))
            self.advanced_search_panel.cols = adv_cols
            self.advanced_search_panel.spacing = gap
            for widget in self.advanced_filter_widgets:
                widget.height = touch
            if collapsed:
                self.advanced_search_panel.height = 0
                self.advanced_search_panel.opacity = 0
                self.advanced_search_panel.disabled = True
                self.filter_toggle_btn.text = "Mehr Filter"
            else:
                adv_rows = int(math.ceil(len(self.advanced_filter_widgets) / float(adv_cols)))
                self.advanced_search_panel.height = adv_rows * touch + max(0, adv_rows - 1) * gap
                self.advanced_search_panel.opacity = 1
                self.advanced_search_panel.disabled = False
                self.filter_toggle_btn.text = "Weniger Filter"
            self.filter_toggle_btn.height = touch

            action_cols = 3 if (is_tablet or width_dp >= 390) else 2
            self.action_row.cols = action_cols
            action_count = len(getattr(self, "search_action_buttons", []) or [])
            action_rows = int(math.ceil(action_count / float(action_cols))) if action_count else 0
            self.action_row.height = action_rows * touch + max(0, action_rows - 1) * gap
            self.action_row.spacing = gap
            for action_button in getattr(self, "search_action_buttons", []):
                action_button.height = touch
            self.secondary_action_row.height = 0
            self.secondary_action_row.opacity = 0
            self.secondary_action_row.disabled = True
            self.database_profile_strip.height = dp(58 if compact_phone else 52)
            self.database_profile_label.font_size = ui_font_px(9.6 if compact_phone else 10.5, profile, body=True)
            self.search_wrap.padding = dp(11 if compact_phone else 14)
            self.search_wrap.spacing = gap
            if hasattr(self, "search_priority_strip"):
                priority_cols = 1 if compact_phone else 3
                self.search_priority_strip.cols = priority_cols
                self.search_priority_strip.spacing = dp(6)
                self.search_priority_strip.height = grid_height_v110(3, priority_cols, dp(38), dp(6))

            # Ergebnis-/Detailbereich.
            self.middle.spacing = gap
            if is_tablet:
                self.middle.orientation = "horizontal"
                if self.left.parent is not self.middle:
                    self.middle.add_widget(self.left)
                if self.right.parent is not self.middle:
                    self.middle.add_widget(self.right)
                self.left.size_hint_x = 0.54 if not desktop_tablet else 0.56
                self.right.size_hint_x = 0.46 if not desktop_tablet else 0.44
                self.left.size_hint_y = 1
                self.right.size_hint_y = 1
                viewport_h = max(dp(620), height - safe_top - safe_bottom - header_h - self.tablet_dashboard.height - self.search_wrap.height - dp(70))
                self.middle.height = min(dp(920), viewport_h)
                self.left.height = self.middle.height
                self.right.height = self.middle.height
                self.detail_identity_card.height = dp(86)
                self.preview_frame.height = min(dp(440), self.middle.height * 0.45)
                self.detail_card.size_hint_y = 1
                reserved_detail = self.detail_identity_card.height + self.preview_frame.height + self.stats_row.height + self.img_btn_row.height + dp(118)
                self.detail_card.height = max(dp(210), self.middle.height - reserved_detail)
                self.results_scroll.size_hint_y = 1
            else:
                self.middle.orientation = "vertical"
                if self.left.parent is not self.middle:
                    self.middle.add_widget(self.left)
                if self.selected_card:
                    if self.right.parent is not self.middle:
                        self.middle.add_widget(self.right)
                else:
                    if self.right.parent is self.middle:
                        self.middle.remove_widget(self.right)

                visible_count = min(PAGE_SIZE, len(self.search_results or []))
                if visible_count <= 0:
                    left_h = dp(280)
                else:
                    item_h = dp(254 if compact_phone else 196)
                    left_h = min(dp(720 if not phone_landscape else 500), dp(150) + min(3, visible_count) * item_h)
                self.left.size_hint_y = None
                self.left.height = left_h
                self.left.size_hint_x = 1
                self.results_scroll.size_hint_y = 1
                right_h = 0
                if self.selected_card:
                    self.detail_identity_card.height = dp(96 if compact_phone else 86)
                    self.preview_frame.height = dp(390 if not compact_phone else 340)
                    self.detail_card.size_hint_y = None
                    self.detail_card.height = dp(300 if not compact_phone else 280)
                    right_h = (
                        self.detail_identity_card.height + self.preview_frame.height + self.stats_row.height
                        + self.detail_card.height + self.img_btn_row.height + dp(126)
                    )
                    self.right.size_hint_y = None
                    self.right.height = right_h
                    self.right.size_hint_x = 1
                self.middle.height = left_h + (gap + right_h if right_h > 0 else 0)

            self.pager_row.height = touch
            self.stats_row.height = dp(98 if not compact_phone else 112)
            self.img_btn_row.height = touch
            if hasattr(self, "detail_name_label"):
                self.detail_name_label.font_size = ui_font_px(14.0 if compact_phone else (16.5 if is_tablet else 15.0), profile)
            if hasattr(self, "detail_meta_label"):
                self.detail_meta_label.font_size = ui_font_px(9.8 if compact_phone else 10.6, profile, body=True)
            self._last_layout_signature = (
                int(width), int(height), profile.get("device_class"), profile.get("window_class"),
                bool(profile.get("landscape")), is_tablet, int(safe_left), int(safe_top),
                int(safe_right), int(safe_bottom),
            )
            Clock.schedule_once(lambda *_: self.apply_runtime_layout_guard_v110(), 0.03)
        except Exception as exc:
            try:
                self.append_crash_log(exc, "apply_responsive_layout_v96")
            except Exception:
                pass

    def apply_runtime_layout_guard_v110(self, root=None):
        """Defensive Text-/Touchprüfung nach Größen- und Schriftänderungen.

        Die Methode verändert keine fachlichen Inhalte. Sie begrenzt nur seltene
        Herstellerfälle, in denen Android nach einem Font-Scale- oder Split-Screen-
        Wechsel Texturen später als das Layout berechnet.
        """
        root = root or getattr(self, "root_holder", None)
        if root is None:
            return {"visited": 0, "adjusted": 0}
        profile = self.current_ui_profile()
        minimum_touch = dp(48 if not getattr(self, "large_touch_targets", False) else 56)
        minimum_font = dp(9.0)
        stack = [root]
        visited = 0
        adjusted = 0
        while stack and visited < 2200:
            widget = stack.pop()
            visited += 1
            try:
                stack.extend(list(getattr(widget, "children", []) or []))
            except Exception:
                pass
            try:
                if isinstance(widget, DarkLabel):
                    widget._update_text_size()
                    if getattr(widget, "_auto_height", False):
                        widget._sync_auto_height()
                    elif getattr(widget, "size_hint_y", 1) is None and float(getattr(widget, "height", 0) or 0) > 0:
                        texture_h = float(getattr(widget, "texture_size", (0, 0))[1] or 0)
                        available_h = max(1.0, float(widget.height) - dp(4))
                        if texture_h > available_h * 1.08 and float(widget.font_size) > minimum_font:
                            ratio = max(0.78, min(1.0, available_h / max(1.0, texture_h)))
                            widget.font_size = max(minimum_font, float(widget.font_size) * ratio)
                            adjusted += 1
                elif isinstance(widget, (DarkButton, DarkInput, DarkSpinner)):
                    visible = float(getattr(widget, "opacity", 1) or 0) > 0.05 and not bool(getattr(widget, "disabled", False))
                    if isinstance(widget, DarkButton):
                        widget._fit_button_text()
                        try:
                            available_w = max(1.0, float(widget.width) - dp(18))
                            available_h = max(1.0, float(widget.height) - dp(8))
                            texture_w = float(getattr(widget, "texture_size", (0, 0))[0] or 0)
                            texture_h = float(getattr(widget, "texture_size", (0, 0))[1] or 0)
                            if (texture_w > available_w * 1.04 or texture_h > available_h * 1.04) and float(widget.font_size) > minimum_font:
                                ratio = min(available_w / max(1.0, texture_w), available_h / max(1.0, texture_h), 1.0)
                                widget.font_size = max(minimum_font, float(widget.font_size) * max(0.78, ratio))
                                widget._fit_button_text()
                                adjusted += 1
                        except Exception:
                            pass
                    if visible and getattr(widget, "size_hint_y", 1) is None:
                        current_h = float(getattr(widget, "height", 0) or 0)
                        if 0 < current_h < minimum_touch:
                            widget.height = minimum_touch
                            adjusted += 1
            except Exception:
                continue
        try:
            self.record_performance(
                "layout_guard_v110",
                details={
                    "visited": visited,
                    "adjusted": adjusted,
                    "device_class": profile.get("device_class"),
                    "window_class": profile.get("window_class"),
                },
            )
        except Exception:
            pass
        return {"visited": visited, "adjusted": adjusted}

    def grid_height(self, item_count, columns, item_height, spacing=0):
        """Berechnet die feste Höhe responsiver GridLayouts ohne leere Restzeilen."""
        try:
            count = max(0, int(item_count or 0))
            cols = max(1, int(columns or 1))
            rows = int(math.ceil(count / float(cols))) if count else 0
            return rows * float(item_height or 0) + max(0, rows - 1) * float(spacing or 0)
        except Exception:
            return 0

    def toggle_theme(self, *_):
        """Wechselt konsistent zwischen Dark, Light und Farbenblind-Modus."""
        order = ["dark", "light", "colorblind"]
        try:
            index = order.index(self.theme_name)
        except Exception:
            index = 0
        self.theme_name = order[(index + 1) % len(order)]
        self.save_settings()
        self.rebuild_interface()
        labels = {
            "dark": "Dark Theme",
            "light": "Light Theme",
            "colorblind": "Farbenblind-Modus",
        }
        self.set_status(f"Darstellung: {labels.get(self.theme_name, self.theme_name)}")

    def update_collection_info(self):
        total_unique = len(self.collection)
        total_cards = sum(int(item.get("count", 0)) for item in self.collection.values())
        if hasattr(self, "collection_info_label"):
            try:
                profile = self.current_ui_profile()
                if profile.get("is_tablet"):
                    self.collection_info_label.text = f"{total_cards} Karten\n{total_unique} Arten"
                else:
                    self.collection_info_label.text = f"{total_cards:,}".replace(",", ".") + "\nKarten"
            except Exception:
                self.collection_info_label.text = str(total_cards)

    def get_filters_safe(self):
        if not hasattr(self, "name_input"):
            return {"name": "", "card_id": "", "set": "", "language_name": "Deutsch", "atk": "", "def": "", "level": "", "race": "", "attribute_name": "Eigenschaft", "group": "Alle"}
        return {
            "name": self.name_input.text.strip(),
            "card_id": self.card_id_input.text.strip(),
            "set": self.set_input.text.strip(),
            "language_name": self.language_spinner.text.strip() or "Deutsch",
            "atk": self.atk_input.text.strip(),
            "def": self.def_input.text.strip(),
            "level": self.level_input.text.strip(),
            "race": self.race_input.text.strip(),
            "attribute_name": self.attribute_spinner.text.strip() or "Eigenschaft",
            "group": self.group_spinner.text.strip() or "Alle",
        }

    def apply_filters_to_widgets(self, filters):
        self.name_input.text = filters.get("name", "")
        self.card_id_input.text = filters.get("card_id", "")
        self.set_input.text = filters.get("set", "")
        self.language_spinner.text = filters.get("language_name", "Deutsch")
        self.atk_input.text = filters.get("atk", "")
        self.def_input.text = filters.get("def", "")
        self.level_input.text = filters.get("level", "")
        self.race_input.text = filters.get("race", "")
        self.attribute_spinner.text = filters.get("attribute_name", "Eigenschaft")
        self.group_spinner.text = filters.get("group", "Alle")

    def get_filters(self):
        attr = attribute_to_api(self.attribute_spinner.text.strip())
        lang_name = self.language_spinner.text.strip() or "Deutsch"
        return {
            "name": self.name_input.text.strip(),
            "card_id": self.card_id_input.text.strip(),
            "set": self.set_input.text.strip(),
            "atk": self.atk_input.text.strip(),
            "def": self.def_input.text.strip(),
            "level": self.level_input.text.strip(),
            "race": race_to_api(self.race_input.text.strip()),
            "attribute": attr,
            "group": group_to_api(self.group_spinner.text.strip() or "Alle"),
            "language": LANGUAGE_CODES.get(lang_name, "de"),
        }

    def clear_filters(self):
        self.name_input.text = ""
        self.card_id_input.text = ""
        self.set_input.text = ""
        self.language_spinner.text = "Deutsch"
        self.atk_input.text = ""
        self.def_input.text = ""
        self.level_input.text = ""
        self.race_input.text = ""
        self.attribute_spinner.text = "Eigenschaft"
        self.group_spinner.text = "Alle"
        self.set_status("Suchfelder wurden geleert. Sprache bleibt Deutsch.")

    def set_status(self, text):
        if hasattr(self, "status_label"):
            self.status_label.text = text

    def start_search(self):
        if self.is_searching:
            return
        self.is_searching = True
        self._search_started_at = time.perf_counter()
        self._search_token += 1
        token = self._search_token
        self.search_button.disabled = True
        self.search_button.text = "Suche..."
        self.set_status("Suche läuft...")
        self.result_meta_label.text = "Suche läuft..."
        self.results_grid.clear_widgets()
        self.results_grid.add_widget(EmptyStateCard(
            "Suche läuft",
            "Kartendaten, Set-Ausgaben und Artworks werden geladen.",
            icon_name="search",
        ))
        threading.Thread(target=self._search_thread, args=(token, self.get_filters()), daemon=True).start()

    def _search_thread(self, token, filters):
        try:
            cards = fetch_cards(filters)
            Clock.schedule_once(lambda *_: self._finish_search(token, cards=cards), 0)
        except Exception as exc:
            Clock.schedule_once(lambda *_: self._finish_search(token, error=str(exc)), 0)

    def _finish_search(self, token, cards=None, error=None):
        if token != self._search_token:
            return
        self.is_searching = False
        self.search_button.disabled = False
        self.search_button.text = "Suchen"
        if error:
            self.record_performance("search", getattr(self, "_search_started_at", None), {"success": False, "error": short_text(error, 180)})
            self.show_error("Suche fehlgeschlagen", f"Die App läuft weiter. Bitte Suchbegriff prüfen oder Internetverbindung testen.\n\nDetails: {error}")
            self.search_results = []
            self.result_meta_label.text = "Keine Ergebnisse geladen."
            self.set_status("Suche fehlgeschlagen, App läuft weiter.")
            return
        self.search_results = cards or []
        self.record_performance("search", getattr(self, "_search_started_at", None), {"success": True, "results": len(self.search_results)})
        self.current_page = 0
        self.render_current_page()

    def render_current_page(self, reset_scroll=True):
        if not hasattr(self, "results_grid"):
            return
        self.results_grid.clear_widgets()
        total = len(self.search_results)
        if total == 0:
            self.result_meta_label.text = "0 Treffer"
            self.page_label.text = "Seite 0 / 0"
            self.prev_page_btn.disabled = True
            self.next_page_btn.disabled = True
            self.results_grid.add_widget(EmptyStateCard(
                "Noch keine passende Karte",
                "Prüfe Schreibweise, Set-Code, Passcode oder öffne die erweiterten Filter.",
                icon_name="cards",
            ))
            self.set_status("Keine Karten gefunden. Bitte Suchbegriff, Set-Code oder Filter prüfen.")
            self._schedule_compact_panel_refresh()
            return

        pages = max(1, int(math.ceil(total / float(PAGE_SIZE))))
        self.current_page = max(0, min(self.current_page, pages - 1))
        start = self.current_page * PAGE_SIZE
        end = min(total, start + PAGE_SIZE)
        page_cards = self.search_results[start:end]

        self.result_meta_label.text = f"{total} Treffer | Anzeige {start + 1}-{end} | Sprache: {self.language_spinner.text}"
        self.page_label.text = f"Seite {self.current_page + 1} / {pages}"
        self.prev_page_btn.disabled = self.current_page <= 0
        self.next_page_btn.disabled = self.current_page >= pages - 1

        # Nur die aktuelle Seite wird als Widget-Liste gebaut. Das verhindert Ruckler/Abstürze bei sehr vielen Treffern.
        for card in page_cards:
            self.results_grid.add_widget(self.create_result_row(card))
        if reset_scroll:
            self.results_scroll.scroll_y = 1
        self.set_status(f"{total} Karte(n) gefunden. Es werden immer nur {PAGE_SIZE} pro Seite gerendert.")
        self._schedule_compact_panel_refresh()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_current_page()

    def next_page(self):
        pages = int(math.ceil(len(self.search_results) / float(PAGE_SIZE))) if self.search_results else 0
        if self.current_page + 1 < pages:
            self.current_page += 1
            self.render_current_page()

    def create_result_row(self, card):
        """Moderne, bildgestützte Ergebniskarte ohne feste Textüberlagerungen."""
        profile = self.current_ui_profile()
        compact = float(profile.get("width_dp") or 0) < 360
        is_tablet = bool(profile.get("is_tablet"))
        content_h_dp = 124 if compact else 118
        action_cols = 2 if compact else 4
        action_h_dp = grid_height_v110(4, action_cols, 48, 6)
        row_h = dp(content_h_dp + action_h_dp + 28)
        row = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            height=row_h,
            spacing=dp(8),
            padding=dp(10),
            bg_color=CARD_BG,
            border_color=tuple(list(ACCENT[:3]) + [0.12]),
            radius=dp(20),
        )

        content_h = dp(content_h_dp)
        content_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=content_h, spacing=dp(10))
        thumb_w = dp(78 if compact else 82)
        thumb = SurfaceBox(
            orientation="vertical",
            size_hint=(None, None),
            width=thumb_w,
            height=content_h,
            padding=dp(4),
            bg_color=INPUT_BG,
            border_color=tuple(list(GOLD[:3]) + [0.20]),
            radius=dp(14),
        )
        image_url = get_image_url(card)
        if image_url:
            card_img = AsyncImage(source=image_url, allow_stretch=True, keep_ratio=True)
            try:
                if hasattr(card_img, "fit_mode"):
                    card_img.fit_mode = "contain"
            except Exception:
                pass
            thumb.add_widget(card_img)
        else:
            thumb.add_widget(Image(source=resource_find(PREVIEW_PLACEHOLDER_FILE) or "", allow_stretch=True, keep_ratio=True))
        content_row.add_widget(thumb)

        info_box = BoxLayout(orientation="vertical", spacing=dp(3), size_hint_x=1)
        name = str(card.get("name") or "Unbekannte Karte")
        name_label = DarkLabel(
            text=f"[b]{html_escape(name)}[/b]",
            markup=True,
            color=TEXT,
            halign="left",
            size_hint_y=None,
            height=dp(44),
            font_size=ui_font_px(13.5 if compact else 14.2, profile),
        )
        try:
            name_label.max_lines = 2
            name_label.shorten = True
            name_label.shorten_from = "right"
        except Exception:
            pass
        info_box.add_widget(name_label)

        type_text = display_card_type(card.get("type", ""))
        stat_line = stat_text(card)
        info_box.add_widget(DarkLabel(
            text=f"{type_text}\n{stat_line}",
            color=MUTED,
            halign="left",
            size_hint_y=None,
            height=dp(42),
            font_size=ui_font_px(10.2 if compact else 10.8, profile, body=True),
        ))

        sets = card.get("card_sets") or []
        first_set = sets[0] if sets else {}
        set_code = str(first_set.get("set_code") or first_set.get("code") or "Kein Set-Code")
        rarity = str(first_set.get("set_rarity") or first_set.get("rarity") or artwork_label(card))
        info_box.add_widget(DarkLabel(
            text=f"[color={markup_hex(GOLD)}]{html_escape(set_code)}[/color]  •  {html_escape(short_text(rarity, 34))}",
            markup=True,
            color=GOLD,
            halign="left",
            size_hint_y=None,
            height=dp(28),
            font_size=ui_font_px(10.2, profile, body=True),
        ))
        content_row.add_widget(info_box)
        content_row.bind(on_touch_down=lambda _w, touch, _card=card: self.select_card(_card) if _w.collide_point(*touch.pos) else None)
        row.add_widget(content_row)

        owned = collection_count_for(self.collection, card)
        action_h = dp(action_h_dp)
        actions = GridLayout(
            cols=action_cols,
            size_hint_y=None,
            height=action_h,
            spacing=dp(6),
            row_default_height=dp(48),
            row_force_default=True,
        )
        details_btn = DarkButton(text="Details", bg=ACCENT_2, no_wrap=True, compact=True, on_release=lambda *_: self.select_card(card))
        minus_btn = DarkButton(text="−", bg=DANGER, no_wrap=True, compact=True, on_release=lambda *_: self.remove_card(card))
        owned_pill = StatPill(
            text=f"{owned}× vorhanden",
            bg_color=tuple(list(SUCCESS[:3]) + [0.12]) if owned else INPUT_BG,
            text_color=TEXT if owned else MUTED,
            halign="center",
            font_size=ui_font_px(10.0, profile),
        )
        plus_btn = DarkButton(text="+ Hinzufügen", bg=SUCCESS, no_wrap=True, compact=True, on_release=lambda *_: self.add_card(card))
        for widget in (details_btn, minus_btn, owned_pill, plus_btn):
            actions.add_widget(widget)
        row.add_widget(actions)
        return row

    def refresh_results_list(self, keep_scroll=True):
        if self.search_results:
            old_scroll_y = getattr(self.results_scroll, "scroll_y", 1) if keep_scroll and hasattr(self, "results_scroll") else 1
            self.render_current_page(reset_scroll=False)
            if keep_scroll and hasattr(self, "results_scroll"):
                Clock.schedule_once(lambda *_: setattr(self.results_scroll, "scroll_y", old_scroll_y), 0)

    def select_card(self, card, load_image=True):
        self.selected_card = card
        self.preview_image.source = ""
        self.preview_image.reload()
        self.preview_placeholder.opacity = 0
        self.preview_placeholder_image.opacity = 1
        self.preview_image.opacity = 0
        img = get_image_url(card)
        if img and load_image:
            self.set_status("Karte ausgewählt. Artwork wird geladen …")
            threading.Thread(target=self._load_image_thread, args=(card,), daemon=True).start()
        elif not img:
            self.set_status(f"Ausgewählt: {card.get('name', '')} | Kein Artwork verfügbar.")

        name = str(card.get("name") or "Unbekannte Karte")
        desc = str(card.get("desc") or "Kein Effekttext vorhanden.")
        desc = short_text(desc, 3200)
        card_sets = card.get("card_sets") or []
        first_set = card_sets[0] if card_sets else {}
        set_name = str(first_set.get("set_name") or "-")
        set_code = str(first_set.get("set_code") or first_set.get("code") or "-")
        rarity = str(first_set.get("set_rarity") or first_set.get("rarity") or "-")
        language = str(card.get("language") or card.get("lang") or "-").upper()
        muted_markup = markup_hex(MUTED)

        if hasattr(self, "detail_name_label"):
            self.detail_name_label.text = f"[b]{html_escape(name)}[/b]"
        if hasattr(self, "detail_meta_label"):
            self.detail_meta_label.text = (
                f"{html_escape(set_code)}  •  {html_escape(short_text(rarity, 36))}  •  "
                f"{html_escape(display_card_type(card.get('type', '')))}"
            )

        self.detail_label.text = (
            f"[b]Kartenprofil[/b]\n"
            f"[color={muted_markup}]Artwork:[/color] {html_escape(artwork_label(card))}\n"
            f"[color={muted_markup}]Kategorie:[/color] {html_escape(category_for(card))}\n"
            f"[color={muted_markup}]Kartentyp:[/color] {html_escape(display_card_type(card.get('type', '')))}\n"
            f"[color={muted_markup}]Typ / Untertyp:[/color] {html_escape(str(card.get('race') or '-'))}\n"
            f"[color={muted_markup}]Eigenschaft:[/color] {html_escape(str(card.get('attribute') or '-'))}\n"
            f"[color={muted_markup}]Sprache:[/color] {html_escape(language)}\n"
            f"[color={muted_markup}]Erstes Set:[/color] {html_escape(set_name)} ({html_escape(set_code)})\n"
            f"[color={muted_markup}]Rarity:[/color] {html_escape(rarity)}\n"
            f"[color={muted_markup}]Pendelskala:[/color] {html_escape(pendulum_text(card))}\n"
            f"[color={muted_markup}]Besitz dieses Artworks:[/color] {collection_count_for(self.collection, card)}\n\n"
            f"[b]Effekt / Beschreibung[/b]\n{html_escape(desc)}\n\n"
            f"[b]Sets und Reprints dieses Artworks[/b]\n{html_escape(set_entries_text(card, 14))}"
        )
        self.info_type.text = f"Typ: {html_escape(str(card.get('race') or '-'))}"
        self.info_attribute.text = f"Eigenschaft: {html_escape(str(card.get('attribute') or '-'))}"
        self.info_level.text = f"Stufe / Rang / Link: {get_level_value(card) or '-'}" + (f" | Pendel {pendulum_text(card)}" if is_pendulum_card(card) else "")
        self.info_values.text = f"ATK {card.get('atk', '-')}  /  DEF {card.get('def', '-')}"
        self._schedule_compact_panel_refresh()

    def _load_image_thread(self, card):
        try:
            if getattr(self, "wifi_only_images", False) and not android_is_unmetered_network():
                Clock.schedule_once(lambda *_: self.set_status("Kartenbild nicht geladen: WLAN-only ist aktiv."), 0)
                return
            path = download_card_image(card, self.image_cache_dir)
            Clock.schedule_once(lambda *_: self._set_preview_image(get_card_id(card), path), 0)
        except Exception as exc:
            msg = str(exc)
            Clock.schedule_once(lambda *_: self.set_status(f"Bild konnte nicht geladen werden: {short_text(msg, 90)}"), 0)

    def _set_preview_image(self, card_id, path):
        if self.selected_card and get_card_id(self.selected_card) == card_id and path:
            self.preview_image.source = path
            self.preview_image.opacity = 1
            self.preview_image.reload()
            self.preview_placeholder.opacity = 0
            self.preview_placeholder_image.opacity = 0
            self.set_status(f"Ausgewählt: {self.selected_card.get('name', '')}")

    def add_selected(self):
        if not self.selected_card:
            self.show_error("Keine Auswahl", "Bitte zuerst eine Karte aus der Ergebnisliste antippen.")
            return
        self.add_card(self.selected_card)

    def remove_selected(self):
        if not self.selected_card:
            self.show_error("Keine Auswahl", "Bitte zuerst eine Karte aus der Ergebnisliste antippen.")
            return
        self.remove_card(self.selected_card)

    def show_add_card_set_popup(self, card):
        active_set_query = self.set_input.text.strip() if hasattr(self, "set_input") else ""
        card_sets = sorted(dedupe_card_sets_for_display(card.get("card_sets") or [], active_set_query), key=rarity_sort_key)
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56), spacing=dp(8))
        header.add_widget(DarkLabel(
            text=(
                f"[b]{html_escape(card.get('name', 'Karte'))}[/b]\n"
                "Set und Rarity wählen. +1 kann mehrfach gedrückt werden; die Anzeige bleibt offen."
            ),
            markup=True,
        ))
        close_top = self.make_close_button(bg=DANGER)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        summary = DarkLabel(text="", color=GOLD, size_hint_y=None, height=dp(28))
        wrapper.add_widget(summary)
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        def count_for_item(set_item):
            selected = apply_collection_set_to_card(card, set_item or {})
            cid = collection_key_for(selected)
            return int(self.collection.get(cid, {}).get("count", 0) or 0)

        def update_summary():
            total_variants = 0
            total_count = 0
            for item in card_sets or [{}]:
                count = count_for_item(item)
                if count:
                    total_variants += 1
                    total_count += count
            summary.text = f"In Sammlung aus {total_variants} Set/Rarity-Variante(n): {total_count} Exemplar(e)"

        def add_and_stay(set_item, count_label=None):
            self.add_card(card, set_item=set_item, ask_set=False)
            if count_label is not None:
                count_label.text = f"Anzahl: {count_for_item(set_item)}"
            update_summary()

        if not card_sets:
            card_sets = [{}]
        for set_item in card_sets:
            rarity = (set_item.get("set_rarity") or "Unbekannt").strip() or "Unbekannt"
            row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(92), spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
            row.add_widget(DarkLabel(
                text=(
                    f"[b]{html_escape(set_item.get('set_name', 'Ohne Set'))}[/b]\n"
                    f"Code: {html_escape(set_item.get('set_code', '-') or '-')}  |  Rarity: {html_escape(rarity)}"
                ),
                markup=True,
                size_hint_x=0.64,
            ))
            right = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=0.36)
            count_label = DarkLabel(text=f"Anzahl: {count_for_item(set_item)}", halign="center", size_hint_y=None, height=dp(26))
            right.add_widget(count_label)
            right.add_widget(DarkButton(text="+1", bg=SUCCESS, on_release=lambda _btn, item=set_item, lbl=count_label: add_and_stay(item, lbl)))
            row.add_widget(right)
            grid.add_widget(row)
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        done_btn = DarkButton(text="Fertig", size_hint_y=None, height=dp(50), bg=ACCENT_2)
        wrapper.add_widget(done_btn)
        popup = self.make_popup("Set & Rarity wählen", wrapper, size_hint=(0.96, 0.88))
        close_top.bind(on_release=popup.dismiss)
        done_btn.bind(on_release=popup.dismiss)
        update_summary()
        popup.open()

    def add_card(self, card, set_item=None, ask_set=True):
        if ask_set and not get_collection_set_from_card(card):
            active_set_query = self.set_input.text.strip() if hasattr(self, "set_input") else ""
            if active_set_query:
                set_item = choose_set_item_for_query(card, active_set_query) or set_item
            card_sets = dedupe_card_sets_for_display(card.get("card_sets") or [], active_set_query)
            if not set_item and len(card_sets) > 1:
                self.show_add_card_set_popup(card)
                return
            if not set_item and len(card_sets) == 1:
                set_item = card_sets[0]
        selected_card = apply_collection_set_to_card(card, localize_set_item_for_query(set_item or get_collection_set_from_card(card) or {}, self.set_input.text.strip() if hasattr(self, "set_input") else ""))
        cid = collection_key_for(selected_card)
        before_item = json.loads(json.dumps(self.collection.get(cid), ensure_ascii=False)) if cid in self.collection else None
        self.push_collection_delta_undo(cid, before_item, f"{card.get('name', 'Karte')} hinzufügen")
        if cid not in self.collection:
            self.collection[cid] = {"count": 0, "card": selected_card}
        else:
            self.collection[cid]["card"] = {**self.collection[cid].get("card", {}), **selected_card}
        self.collection[cid]["count"] += 1
        _set_name, set_code, rarity = collection_set_label(selected_card)
        self.set_status(f"+1 {card.get('name', '')} | {set_code} | {rarity} | Anzahl: {self.collection[cid]['count']}")
        self.update_collection_info()
        self.save_collection(show_popup=False)
        self.refresh_results_list()
        if self.selected_card and get_card_id(self.selected_card) == get_card_id(card):
            self.select_card(self.selected_card, load_image=False)

    def _first_matching_collection_key(self, card):
        exact = collection_key_for(card)
        if exact in self.collection:
            return exact
        base_id = get_card_id(card)
        for key, item in self.collection.items():
            item_card = item.get("card", {}) if isinstance(item, dict) else {}
            if get_card_id(item_card) == base_id:
                return key
        return exact

    def remove_card(self, card):
        cid = self._first_matching_collection_key(card)
        if cid not in self.collection:
            self.set_status("Diese Karte ist nicht in deiner Sammlung.")
            return
        before_item = json.loads(json.dumps(self.collection.get(cid), ensure_ascii=False))
        self.push_collection_delta_undo(cid, before_item, f"{card.get('name', 'Karte')} entfernen")
        self.collection[cid]["count"] -= 1
        stored_card = self.collection[cid].get("card", card)
        _set_name, set_code, rarity = collection_set_label(stored_card)
        if self.collection[cid]["count"] <= 0:
            del self.collection[cid]
            self.set_status(f"{card.get('name', '')} ({set_code}, {rarity}) wurde aus der Sammlung entfernt.")
        else:
            self.set_status(f"-1 {card.get('name', '')} | {set_code} | {rarity} | Anzahl: {self.collection[cid]['count']}")
        self.update_collection_info()
        self.save_collection(show_popup=False)
        self.refresh_results_list()
        if self.selected_card and get_card_id(self.selected_card) == get_card_id(card):
            self.select_card(card, load_image=False)

    def save_collection(self, show_popup=True):
        try:
            if getattr(self, "app_db", None) is not None:
                self.app_db.save_collection(self.collection)
            atomic_write_json(self.collection_file, self.collection)
            self.update_collection_info()
            if bool(getattr(self, "auto_backup_enabled", True)):
                try:
                    self.auto_backup_manager.create(
                        [self.collection_file, self.decks_file, self.settings_file, self.custom_cards_file, self.scan_history_file],
                        APP_VERSION,
                        developer=APP_DEVELOPER,
                    )
                except Exception as backup_exc:
                    self.append_crash_log(backup_exc, "Automatisches Backup")
            if show_popup:
                self.show_info("Gespeichert", "Sammlung wurde transaktional in SQLite gespeichert und zusätzlich als JSON gesichert.")
        except Exception as exc:
            self.show_error("Speichern fehlgeschlagen", str(exc))

    def load_collection(self, show_popup=True):
        try:
            data = self.app_db.load_collection() if getattr(self, "app_db", None) is not None else {}
            if not data:
                data = safe_read_json(self.collection_file, {})
                if isinstance(data, dict) and data and getattr(self, "app_db", None) is not None:
                    self.app_db.save_collection(data)
            self.collection = data if isinstance(data, dict) else {}
            self.update_collection_info()
            if show_popup:
                self.show_info("Geladen", f"Sammlung geladen.\nEinträge: {len(self.collection)}")
        except Exception as exc:
            self.collection = {}
            self.show_error("Laden fehlgeschlagen", str(exc))

    def load_decks(self):
        try:
            data = self.app_db.load_decks() if getattr(self, "app_db", None) is not None else []
            if not data:
                data = safe_read_json(self.decks_file, [])
                if isinstance(data, list) and data and getattr(self, "app_db", None) is not None:
                    self.app_db.save_decks(data)
            self.decks = data if isinstance(data, list) else []
        except Exception:
            self.decks = []

    def save_decks(self):
        try:
            decks = self.decks[:MAX_DECKS]
            if getattr(self, "app_db", None) is not None:
                self.app_db.save_decks(decks)
            atomic_write_json(self.decks_file, decks)
        except Exception:
            pass

    def deck_card_total(self, deck):
        return sum(int(item.get("count", 0) or 0) for item in deck.get("cards", []))

    def deck_zone_totals(self, deck):
        totals = {"main": 0, "extra": 0, "side": 0}
        for item in (deck or {}).get("cards", []):
            card = item.get("card") or {}
            zone = str(item.get("zone") or self.deck_zone_for_card(card))
            if zone not in totals:
                zone = "main"
            totals[zone] += max(0, int(item.get("count", 0) or 0))
        return totals

    def deck_card_copies(self, deck, card):
        card_id = str((card or {}).get("id") or normalize_search_text((card or {}).get("name", "")))
        total = 0
        for item in (deck or {}).get("cards", []):
            entry_card = item.get("card") or {}
            entry_id = str(entry_card.get("id") or normalize_search_text(entry_card.get("name", "")))
            if card_id and entry_id == card_id:
                total += max(0, int(item.get("count", 0) or 0))
        return total

    def collection_total_count(self):
        return sum(int(item.get("count", 0) or 0) for item in self.collection.values())

    def deck_count_for_collection_key(self, deck, collection_key):
        total = 0
        for entry in deck.get("cards", []):
            if entry.get("collection_key") == collection_key:
                total += int(entry.get("count", 0) or 0)
        return total

    def deck_preview_card(self, deck):
        cover_key = str((deck or {}).get("cover_collection_key") or "")
        if cover_key:
            for entry in (deck or {}).get("cards", []):
                if str(entry.get("collection_key") or "") == cover_key:
                    card = entry.get("card") or {}
                    if card:
                        return card
        for entry in (deck or {}).get("cards", []):
            card = entry.get("card") or {}
            if get_image_url(card):
                return card
        for entry in (deck or {}).get("cards", []):
            card = entry.get("card") or {}
            if card:
                return card
        return {}

    def favorite_deck_entries(self):
        entries = []
        for idx, deck in enumerate((self.decks or [])[:MAX_DECKS]):
            if deck.get("favorite") and not deck.get("archived"):
                entries.append((idx, deck))
        entries.sort(key=lambda pair: (int(pair[1].get("favorite_order") or 999), pair[0]))
        return entries[:5]

    def set_deck_favorite(self, deck_index, value):
        if not (0 <= deck_index < len(self.decks)):
            return
        value = bool(value)
        if value and not self.decks[deck_index].get("favorite"):
            current = sum(1 for deck in self.decks[:MAX_DECKS] if deck.get("favorite"))
            if current >= 5:
                self.show_error("Favoriten", "Es sind maximal 5 Favoriten-Decks mit Vorschau möglich.")
                return
        self.decks[deck_index]["favorite"] = value
        if value:
            orders = [int(deck.get("favorite_order") or 0) for deck in self.decks if deck.get("favorite")]
            self.decks[deck_index]["favorite_order"] = max(orders or [0]) + 1
            self.decks[deck_index]["archived"] = False
        else:
            self.decks[deck_index].pop("favorite_order", None)
        self.save_decks()

    def duplicate_deck_v104(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        if len(self.decks) >= MAX_DECKS:
            self.show_error("Deck-Limit", f"Es sind maximal {MAX_DECKS} Decks möglich.")
            return
        clone = json.loads(json.dumps(self.decks[deck_index], ensure_ascii=False))
        clone["name"] = str(clone.get("name") or "Deck") + " – Kopie"
        clone["favorite"] = False
        clone.pop("favorite_order", None)
        clone["archived"] = False
        self.decks.append(clone)
        self.save_decks()
        self.set_status("Deck wurde dupliziert.")

    def toggle_deck_archive_v104(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        deck["archived"] = not bool(deck.get("archived"))
        if deck["archived"]:
            deck["favorite"] = False
            deck.pop("favorite_order", None)
        self.save_decks()
        self.set_status("Deck archiviert." if deck["archived"] else "Deck wieder aktiviert.")

    def move_favorite_deck_v104(self, deck_index, delta):
        favorites = self.favorite_deck_entries()
        positions = [idx for idx, _deck in favorites]
        if deck_index not in positions:
            return
        current = positions.index(deck_index)
        target = max(0, min(len(positions) - 1, current + int(delta)))
        if target == current:
            return
        positions[current], positions[target] = positions[target], positions[current]
        for order, idx in enumerate(positions, start=1):
            self.decks[idx]["favorite_order"] = order
        self.save_decks()

    def choose_deck_cover_popup(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        cards = list(deck.get("cards") or [])
        if not cards:
            self.show_error("Deck-Cover", "Das Deck enthält noch keine Karte.")
            return
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(9), bg_color=PANEL_BG)
        wrapper.add_widget(DarkLabel(text="[b]Deck-Cover wählen[/b]\nWähle eine Karte aus dem Deck als Vorschaubild.", markup=True, size_hint_y=None, height=dp(58)))
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        popup_ref = {"popup": None}
        for entry in cards:
            card = entry.get("card") or {}
            key = str(entry.get("collection_key") or "")
            row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(84), spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
            img = get_image_url(card)
            if img:
                row.add_widget(AsyncImage(source=img, allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(54)))
            row.add_widget(DarkLabel(text=f"[b]{html_escape(card.get('name', 'Karte'))}[/b]\n{html_escape(artwork_label(card))}", markup=True, halign="left"))
            choose = DarkButton(text="Als Cover", bg=ACCENT_2, size_hint_x=None, width=dp(118))
            def set_cover(_btn, _key=key):
                deck["cover_collection_key"] = _key
                self.save_decks()
                if popup_ref.get("popup"):
                    popup_ref["popup"].dismiss()
                self.set_status("Deck-Cover gespeichert.")
            choose.bind(on_release=set_cover)
            row.add_widget(choose)
            grid.add_widget(row)
        popup = self.make_popup("Deck-Cover", wrapper, size_hint=(0.94, 0.88))
        popup_ref["popup"] = popup
        popup.open()

    def open_all_decks_popup(self):
        self.load_decks()
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(10), padding=dp(10), bg_color=DARK_BG, border_color=(0, 0, 0, 0), radius=0)
        header = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(66), spacing=dp(10), padding=dp(10), bg_color=PANEL_BG_2, border_color=tuple(list(ACCENT[:3]) + [0.15]), radius=dp(20))
        header.add_widget(AutoHeightLabel(text=f"[b]Alle Decks[/b]\n[color={markup_hex(MUTED)}]{len(self.decks[:MAX_DECKS])}/{MAX_DECKS} Decks gespeichert[/color]", markup=True, min_height=dp(48), font_size=ui_font_px(13.2, body=True)))
        header.add_widget(self.make_close_button(bg=INPUT_BG_2))
        wrapper.add_widget(header)
        deck_list = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        deck_list.bind(minimum_height=deck_list.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(deck_list)
        wrapper.add_widget(scroll)

        def delete_deck(index):
            if 0 <= index < len(self.decks):
                del self.decks[index]
                self.save_decks()
                refresh()

        def refresh():
            deck_list.clear_widgets()
            if not self.decks:
                deck_list.add_widget(EmptyStateCard(
                    "Noch kein Deck vorhanden",
                    "Erstelle ein neues Deck oder lasse dir aus deiner Sammlung einen Vorschlag erzeugen.",
                    icon_name="decks",
                ))
                return
            for idx, deck in enumerate(self.decks[:MAX_DECKS]):
                compact_all_decks = self.ui_width_below(720)
                row = SurfaceBox(
                    orientation="vertical" if compact_all_decks else "horizontal",
                    size_hint_y=None,
                    height=dp(254 if compact_all_decks else 178),
                    spacing=dp(8), padding=dp(10), bg_color=CARD_BG,
                    border_color=tuple(list(ACCENT[:3]) + [0.12]), radius=dp(20),
                )
                preview_card = self.deck_preview_card(deck)
                img_url = get_image_url(preview_card)
                overview = BoxLayout(orientation="horizontal", size_hint=(1, None) if compact_all_decks else (0.58, 1), height=dp(118) if compact_all_decks else 0, spacing=dp(10))
                if img_url:
                    overview.add_widget(AsyncImage(source=img_url, allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(78)))
                else:
                    holder = SurfaceBox(orientation="vertical", bg_color=INPUT_BG, size_hint_x=None, width=dp(78), padding=dp(5), radius=dp(14))
                    holder.add_widget(DarkLabel(text="Kein\nArtwork", color=MUTED, halign="center"))
                    overview.add_widget(holder)
                info = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_x=1)
                star = "★" if deck.get("favorite") else "☆"
                archived_label = " • Archiviert" if deck.get("archived") else ""
                info.add_widget(DarkLabel(text=f"[b]{star} {html_escape(deck.get('name', 'Deck'))}{archived_label}[/b]", markup=True, size_hint_y=None, height=dp(34), halign="left", font_size=ui_font_px(13.2)))
                info.add_widget(DarkLabel(text=f"{self.deck_card_total(deck)} Karten • {len(deck.get('cards', []))} Einträge", color=MUTED, size_hint_y=None, height=dp(24), halign="left", font_size=ui_font_px(10.5, body=True)))
                zone = self.deck_zone_totals(deck)
                info.add_widget(DarkLabel(text=f"Main {zone['main']}/60 • Extra {zone['extra']}/15 • Side {zone['side']}/15", color=TEXT, size_hint_y=None, height=dp(24), halign="left", font_size=ui_font_px(10.5, body=True)))
                info.add_widget(DarkLabel(text=artwork_label(preview_card) if preview_card else "Kein Vorschaubild verfügbar", color=MUTED, size_hint_y=None, height=dp(28), halign="left", font_size=ui_font_px(9.8, body=True)))
                overview.add_widget(info)
                row.add_widget(overview)
                actions = GridLayout(
                    cols=3 if compact_all_decks else 2,
                    spacing=dp(6),
                    size_hint=(1, None) if compact_all_decks else (0.42, 1),
                    height=dp(102) if compact_all_decks else 0,
                    row_default_height=dp(48),
                    row_force_default=True,
                )
                actions.add_widget(DarkButton(text="Öffnen", bg=ACCENT_2, compact=True, on_release=lambda _btn, i=idx: self.open_single_deck_popup(i)))
                actions.add_widget(DarkButton(text="Favorit" if not deck.get('favorite') else "Lösen", bg=GOLD if not deck.get('favorite') else INPUT_BG_2, compact=True, on_release=lambda _btn, i=idx: (self.set_deck_favorite(i, not bool(self.decks[i].get('favorite'))), refresh(), self.set_status('Deck-Favoriten aktualisiert.'))))
                actions.add_widget(DarkButton(text="Kopieren", bg=ACCENT_2, compact=True, on_release=lambda _btn, i=idx: (self.duplicate_deck_v104(i), refresh())))
                actions.add_widget(DarkButton(text="Aktivieren" if deck.get('archived') else "Archiv", bg=INPUT_BG_2, compact=True, on_release=lambda _btn, i=idx: (self.toggle_deck_archive_v104(i), refresh())))
                actions.add_widget(DarkButton(text="Löschen", bg=DANGER, compact=True, on_release=lambda _btn, i=idx: delete_deck(i)))
                row.add_widget(actions)
                deck_list.add_widget(row)

        controls = GridLayout(cols=2 if not self.ui_width_below(540) else 1, size_hint_y=None, height=dp(50 if not self.ui_width_below(540) else 104), spacing=dp(8))
        controls.add_widget(DarkButton(text="Neues Deck", bg=SUCCESS, on_release=lambda *_: (self.decks.append({"name": f"Deck {len(self.decks)+1}", "cards": []}) if len(self.decks) < MAX_DECKS else self.show_error("Deck-Limit", f"Es sind maximal {MAX_DECKS} Decks möglich."), self.save_decks(), refresh()) ))
        controls.add_widget(DarkButton(text="KI Deck", bg=GOLD, on_release=lambda *_: self.request_ai_deck_from_collection()))
        wrapper.add_widget(controls)
        popup = self.make_inline_page("decks_all", wrapper, back_to="decks")
        refresh()
        popup.open()

    def open_decks_popup(self):
        self.load_decks()
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(10), padding=dp(10), bg_color=DARK_BG, border_color=(0, 0, 0, 0), radius=0)
        header = SurfaceBox(
            orientation="horizontal", size_hint_y=None, height=dp(72), spacing=dp(10), padding=(dp(10), dp(8)),
            bg_color=PANEL_BG_2, border_color=tuple(list(ACCENT[:3]) + [0.16]), radius=dp(22), elevation=1,
        )
        icon_box = SurfaceBox(orientation="vertical", size_hint=(None, None), width=dp(50), height=dp(50), padding=dp(10), bg_color=tuple(list(ACCENT[:3]) + [0.13]), border_color=(0, 0, 0, 0), radius=dp(16))
        icon_box.add_widget(Image(source=ui_asset("decks"), allow_stretch=True, keep_ratio=True))
        header.add_widget(icon_box)
        header.add_widget(AutoHeightLabel(
            text=f"[b]Decks[/b]\n[color={markup_hex(MUTED)}]Bis zu {MAX_DECKS} Decks und fünf Favoriten mit Artwork-Vorschau[/color]",
            markup=True, min_height=dp(54), font_size=ui_font_px(13.8, body=True),
        ))
        header.add_widget(self.make_close_button(bg=INPUT_BG_2))
        wrapper.add_widget(header)

        summary = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(88), spacing=dp(4), padding=dp(12), bg_color=CARD_BG, border_color=tuple(list(GOLD[:3]) + [0.14]), radius=dp(20))
        summary.add_widget(DarkLabel(text="[b]Favoriten-Vorschau[/b]", markup=True, size_hint_y=None, height=dp(22), halign="left"))
        summary.add_widget(DarkLabel(text=f"{sum(1 for deck in self.decks[:MAX_DECKS] if deck.get('favorite'))}/5 Favoriten gesetzt • {len(self.decks[:MAX_DECKS])}/{MAX_DECKS} Decks gespeichert", color=MUTED, size_hint_y=None, height=dp(18), halign="left", font_size=ui_font_px(12, body=True)))
        summary.add_widget(DarkLabel(text="Alle weiteren Decks erreichst du über 'Alle Decks'.", color=MUTED, size_hint_y=None, height=dp(18), halign="left", font_size=ui_font_px(11, body=True)))
        wrapper.add_widget(summary)

        fav_grid = GridLayout(cols=1 if self.ui_width_below(620) else 2, spacing=dp(8), size_hint_y=None)
        fav_grid.bind(minimum_height=fav_grid.setter("height"))
        fav_scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        fav_scroll.add_widget(fav_grid)
        wrapper.add_widget(fav_scroll)

        def refresh_favorites():
            fav_grid.clear_widgets()
            favorites = self.favorite_deck_entries()
            if not favorites:
                fav_grid.add_widget(EmptyStateCard(
                    "Noch keine Favoriten",
                    "Markiere unter ‚Alle Decks‘ bis zu fünf Lieblingsdecks. Diese erscheinen hier mit Cover und Zonenübersicht.",
                    icon_name="decks",
                ))
                return
            for idx, deck in favorites:
                compact_favorite = self.ui_width_below(700)
                row = SurfaceBox(
                    orientation="vertical" if compact_favorite else "horizontal",
                    size_hint_y=None,
                    height=dp(246 if compact_favorite else 142),
                    spacing=dp(8), padding=dp(10), bg_color=CARD_BG,
                    border_color=tuple(list(GOLD[:3]) + [0.14]), radius=dp(20),
                )
                preview_card = self.deck_preview_card(deck)
                img_url = get_image_url(preview_card)
                overview = BoxLayout(orientation="horizontal", size_hint=(1, None) if compact_favorite else (0.66, 1), height=dp(116) if compact_favorite else 0, spacing=dp(10))
                if img_url:
                    overview.add_widget(AsyncImage(source=img_url, allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(82)))
                else:
                    holder = SurfaceBox(orientation="vertical", bg_color=INPUT_BG, size_hint_x=None, width=dp(82), padding=dp(5), radius=dp(14))
                    holder.add_widget(DarkLabel(text="Kein\nArtwork", color=MUTED, halign="center"))
                    overview.add_widget(holder)
                info = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_x=1)
                info.add_widget(DarkLabel(text=f"[b]★ {html_escape(deck.get('name', 'Deck'))}[/b]", markup=True, size_hint_y=None, height=dp(32), halign="left", font_size=ui_font_px(13.2)))
                info.add_widget(DarkLabel(text=f"{self.deck_card_total(deck)} Karten • {len(deck.get('cards', []))} Einträge", color=MUTED, size_hint_y=None, height=dp(22), halign="left", font_size=ui_font_px(10.3, body=True)))
                zone = self.deck_zone_totals(deck)
                info.add_widget(DarkLabel(text=f"Main {zone['main']} • Extra {zone['extra']} • Side {zone['side']}", color=TEXT, size_hint_y=None, height=dp(22), halign="left", font_size=ui_font_px(10.3, body=True)))
                info.add_widget(DarkLabel(text=artwork_label(preview_card) if preview_card else "Vorschau aus der ersten Deckkarte", color=MUTED, size_hint_y=None, height=dp(28), halign="left", font_size=ui_font_px(9.6, body=True)))
                overview.add_widget(info)
                row.add_widget(overview)
                buttons = GridLayout(
                    cols=2,
                    size_hint=(1, None) if compact_favorite else (0.34, 1),
                    height=dp(102) if compact_favorite else 0,
                    spacing=dp(6),
                    row_default_height=dp(48),
                    row_force_default=True,
                )
                buttons.add_widget(DarkButton(text="Öffnen", bg=ACCENT_2, compact=True, on_release=lambda _btn, i=idx: self.open_single_deck_popup(i)))
                buttons.add_widget(DarkButton(text="Cover", bg=ACCENT_2, compact=True, on_release=lambda _btn, i=idx: self.choose_deck_cover_popup(i)))
                buttons.add_widget(DarkButton(text="Verschieben", bg=GOLD, compact=True, on_release=lambda _btn, i=idx: (self.move_favorite_deck_v104(i, 1), refresh_favorites())))
                buttons.add_widget(DarkButton(text="Lösen", bg=INPUT_BG_2, compact=True, on_release=lambda _btn, i=idx: (self.set_deck_favorite(i, False), refresh_favorites(), self.set_status('Favorit entfernt.'))))
                row.add_widget(buttons)
                fav_grid.add_widget(row)

        def create_deck(*_):
            if len(self.decks) >= MAX_DECKS:
                self.show_error("Deck-Limit", f"Es sind maximal {MAX_DECKS} Decks möglich.")
                return
            number = len(self.decks) + 1
            self.decks.append({"name": f"Deck {number}", "cards": []})
            self.save_decks()
            refresh_favorites()

        btn_row = GridLayout(
            cols=2 if self.ui_width_below(640) else 4,
            size_hint_y=None,
            height=dp(104 if self.ui_width_below(640) else 50),
            spacing=dp(8),
            row_default_height=dp(48 if self.ui_width_below(640) else 50),
            row_force_default=True,
        )
        btn_row.add_widget(DarkButton(text="Neues Deck", bg=SUCCESS, on_release=create_deck))
        btn_row.add_widget(DarkButton(text="KI Deck", bg=GOLD, on_release=lambda *_: self.request_ai_deck_from_collection()))
        btn_row.add_widget(DarkButton(text="Alle Decks", bg=ACCENT_2, on_release=lambda *_: self.open_all_decks_popup()))
        btn_row.add_widget(DarkButton(text="KI-Key", bg=INPUT_BG_2, on_release=lambda *_: self.open_ai_settings_popup()))
        wrapper.add_widget(btn_row)
        popup = self.make_inline_page("decks", wrapper, back_to="home")
        refresh_favorites()
        popup.open()

    def open_single_deck_popup(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8))
        name_input = DarkInput(text=deck.get("name", f"Deck {deck_index + 1}"), hint_text="Deckname")
        header.add_widget(name_input)
        close_top = self.make_close_button(bg=DANGER)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        total_label = DarkLabel(text="", color=GOLD, size_hint_y=None, height=dp(28))
        wrapper.add_widget(total_label)
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)

        def refresh():
            grid.clear_widgets()
            deck["name"] = name_input.text.strip() or f"Deck {deck_index + 1}"
            zone_totals = self.deck_zone_totals(deck)
            total_label.text = f"Main {zone_totals['main']}/60 • Extra {zone_totals['extra']}/15 • Side {zone_totals['side']}/15 • {len(deck.get('cards', []))} Einträge"
            if not deck.get("cards"):
                grid.add_widget(EmptyStateCard(
                    "Dieses Deck ist noch leer",
                    "Füge Karten aus deiner Sammlung hinzu. Main-, Extra- und Side-Deck werden automatisch getrennt gezählt.",
                    icon_name="decks",
                ))
            for idx, entry in enumerate(list(deck.get("cards", []))):
                card = entry.get("card", {})
                count = int(entry.get("count", 0) or 0)
                set_name, set_code, rarity = collection_set_label(card)
                owned = int(self.collection.get(entry.get("collection_key"), {}).get("count", 0) or 0)
                zone = str(entry.get("zone") or self.deck_zone_for_card(card))
                entry["zone"] = zone
                zone_label = {"main": "Main", "extra": "Extra", "side": "Side"}.get(zone, "Main")
                compact_deck_row = self.ui_width_below(680)
                row = SurfaceBox(
                    orientation="vertical" if compact_deck_row else "horizontal",
                    size_hint_y=None,
                    height=dp(202 if compact_deck_row else 112),
                    spacing=dp(8), padding=dp(10), bg_color=CARD_BG,
                    border_color=tuple(list(ACCENT[:3]) + [0.12]), radius=dp(18),
                )
                card_info = AutoHeightLabel(
                    text=(
                        f"[b]{html_escape(card.get('name', ''))}[/b]  ×{count}\n"
                        f"[color={markup_hex(GOLD)}]{html_escape(set_code)}[/color] • {html_escape(rarity)}\n"
                        f"Sammlung: {owned} • Bereich: {zone_label}"
                    ),
                    markup=True, min_height=dp(72),
                    size_hint=(1, None) if compact_deck_row else (0.50, 1),
                    font_size=ui_font_px(10.8, body=True),
                )
                row.add_widget(card_info)
                controls = GridLayout(
                    cols=3 if compact_deck_row else 5,
                    spacing=dp(6),
                    size_hint=(1, None) if compact_deck_row else (0.50, 1),
                    height=dp(102) if compact_deck_row else 0,
                    row_default_height=dp(48),
                    row_force_default=True,
                )
                controls.add_widget(DarkButton(text="+", bg=SUCCESS, compact=True, on_release=lambda _btn, i=idx: change_deck_count(i, 1)))
                controls.add_widget(DarkButton(text="−", bg=DANGER, compact=True, on_release=lambda _btn, i=idx: change_deck_count(i, -1)))
                controls.add_widget(DarkButton(text="Bereich", bg=GOLD, compact=True, on_release=lambda _btn, i=idx: cycle_deck_zone(i)))
                controls.add_widget(DarkButton(text="Artwork", bg=ACCENT_2, compact=True, on_release=lambda _btn, c=card: self.open_image_for_card(c)))
                controls.add_widget(DarkButton(text="Entfernen", bg=DANGER, compact=True, on_release=lambda _btn, i=idx: delete_entry(i)))
                row.add_widget(controls)
                grid.add_widget(row)

        def change_deck_count(idx, delta):
            cards = deck.setdefault("cards", [])
            if 0 <= idx < len(cards):
                key = cards[idx].get("collection_key")
                owned = int(self.collection.get(key, {}).get("count", 0) or 0) if key in self.collection else 0
                current = int(cards[idx].get("count", 0) or 0)
                new_count = max(0, current + delta)
                card = cards[idx].get("card") or {}
                zone = str(cards[idx].get("zone") or self.deck_zone_for_card(card))
                if delta > 0 and owned and new_count > owned:
                    self.show_error("Nicht genug Karten", f"Von dieser Karte besitzt du nur {owned} Exemplar(e).")
                    return
                if delta > 0 and self.deck_card_copies(deck, card) >= 3:
                    self.show_error("Kartenlimit", "Maximal 3 Exemplare derselben Karte sind im Deck erlaubt.")
                    return
                limits = {"main": 60, "extra": 15, "side": 15}
                if delta > 0 and self.deck_zone_totals(deck).get(zone, 0) >= limits.get(zone, 60):
                    self.show_error("Bereich voll", f"Der Bereich {zone.title()} hat sein Kartenlimit erreicht.")
                    return
                cards[idx]["count"] = new_count
                if cards[idx]["count"] <= 0:
                    cards.pop(idx)
                self.save_decks()
                refresh()

        def cycle_deck_zone(idx):
            cards = deck.setdefault("cards", [])
            if not (0 <= idx < len(cards)):
                return
            current = str(cards[idx].get("zone") or self.deck_zone_for_card(cards[idx].get("card") or {}))
            order = ["main", "extra", "side"]
            next_zone = order[(order.index(current) + 1) % len(order)] if current in order else "main"
            limits = {"main": 60, "extra": 15, "side": 15}
            amount = max(0, int(cards[idx].get("count", 0) or 0))
            if self.deck_zone_totals(deck).get(next_zone, 0) + amount > limits[next_zone]:
                self.show_error("Bereich voll", f"Im Bereich {next_zone.title()} ist nicht genug Platz.")
                return
            cards[idx]["zone"] = next_zone
            self.save_decks()
            refresh()

        def delete_entry(idx):
            cards = deck.setdefault("cards", [])
            if 0 <= idx < len(cards):
                cards.pop(idx)
                self.save_decks()
                refresh()

        def save_name(*_):
            deck["name"] = name_input.text.strip() or f"Deck {deck_index + 1}"
            self.save_decks()
            zone_totals = self.deck_zone_totals(deck)
            total_label.text = f"Main {zone_totals['main']}/60 • Extra {zone_totals['extra']}/15 • Side {zone_totals['side']}/15 • {len(deck.get('cards', []))} Einträge"
            self.set_status(f"Deck gespeichert: {deck['name']}")

        def add_from_collection(*_):
            self.open_add_collection_to_deck_popup(deck_index, refresh)

        btn_row = GridLayout(cols=2 if self.ui_width_below(620) else 6, size_hint_y=None, height=dp(100 if self.ui_width_below(620) else 46), spacing=dp(8))
        btn_row.add_widget(DarkButton(text="Karte hinzufügen", bg=SUCCESS, on_release=add_from_collection))
        btn_row.add_widget(DarkButton(text="KI-Ideen", bg=GOLD, on_release=lambda *_: self.show_deck_ideas(deck_index)))
        btn_row.add_widget(DarkButton(text="Testhand", bg=ACCENT_2, on_release=lambda *_: self.open_deck_test_hand_popup(deck_index)))
        btn_row.add_widget(DarkButton(text="Analyse", bg=ACCENT_2, on_release=lambda *_: self.open_deck_explanation_popup(deck_index)))
        btn_row.add_widget(DarkButton(text="Cover", bg=ACCENT_2, on_release=lambda *_: self.choose_deck_cover_popup(deck_index)))
        btn_row.add_widget(DarkButton(text="Speichern", bg=ACCENT, on_release=save_name))
        wrapper.add_widget(btn_row)
        popup = self.make_popup("Deck bearbeiten", wrapper, size_hint=(0.96, 0.92))
        close_top.bind(on_release=lambda *_: (save_name(), popup.dismiss()))
        refresh()
        popup.open()

    def open_add_collection_to_deck_popup(self, deck_index, callback=None):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        header.add_widget(DarkLabel(text="[b]Karte aus Sammlung wählen[/b]", markup=True))
        close_top = self.make_close_button(bg=DANGER)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        filter_row = GridLayout(cols=1 if self.ui_width_below(620) else 2, spacing=dp(8), size_hint_y=None, height=dp(104 if self.ui_width_below(620) else 50))
        deck_search_input = DarkInput(hint_text="Sammlung im Deckbuilder durchsuchen")
        deck_type_spinner = DarkSpinner(text="Alle Typen", values=["Alle Typen", "Monster", "Zauber", "Fallen", "Extra Deck"])
        filter_row.add_widget(deck_search_input)
        filter_row.add_widget(deck_type_spinner)
        wrapper.add_widget(filter_row)
        summary = DarkLabel(text="", color=GOLD, size_hint_y=None, height=dp(28))
        wrapper.add_widget(summary)
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)

        def update_summary():
            summary.text = f"Deck aktuell: {self.deck_card_total(deck)} Karte(n). Du kannst mehrere Karten hinzufügen, ohne dieses Fenster zu schließen."

        def add_entry(collection_key, card):
            owned = int(self.collection.get(collection_key, {}).get("count", 0) or 0)
            already = self.deck_count_for_collection_key(deck, collection_key)
            if owned <= 0:
                self.show_error("Nicht in Sammlung", "Diese Karte ist nicht mehr in deiner Sammlung vorhanden.")
                return
            if already >= owned:
                self.show_error("Nicht genug Karten", f"Du besitzt nur {owned} Exemplar(e) dieser Kartenvariante. Mehr können nicht ins Deck.")
                return
            if self.deck_card_copies(deck, card) >= 3:
                self.show_error("Kartenlimit", "Maximal 3 Exemplare derselben Karte sind im Deck erlaubt.")
                return
            zone = self.deck_zone_for_card(card)
            limits = {"main": 60, "extra": 15, "side": 15}
            if self.deck_zone_totals(deck).get(zone, 0) >= limits[zone]:
                self.show_error("Bereich voll", f"Der Bereich {zone.title()} hat sein Kartenlimit erreicht.")
                return
            cards = deck.setdefault("cards", [])
            for entry in cards:
                if entry.get("collection_key") == collection_key:
                    entry["count"] = int(entry.get("count", 0) or 0) + 1
                    entry.setdefault("zone", zone)
                    break
            else:
                cards.append({"collection_key": collection_key, "count": 1, "card": minimal_card(card), "zone": zone})
            self.save_decks()
            if callback:
                callback()
            refresh_rows(keep_scroll=True)

        def remove_entry(collection_key):
            cards = deck.setdefault("cards", [])
            for idx, entry in enumerate(list(cards)):
                if entry.get("collection_key") == collection_key:
                    entry["count"] = int(entry.get("count", 0) or 0) - 1
                    if entry["count"] <= 0:
                        cards.pop(idx)
                    self.save_decks()
                    if callback:
                        callback()
                    refresh_rows(keep_scroll=True)
                    return

        def delete_entry(collection_key):
            cards = deck.setdefault("cards", [])
            deck["cards"] = [entry for entry in cards if entry.get("collection_key") != collection_key]
            self.save_decks()
            if callback:
                callback()
            refresh_rows(keep_scroll=True)

        def refresh_rows(keep_scroll=False):
            old_scroll = getattr(scroll, "scroll_y", 1)
            grid.clear_widgets()
            update_summary()
            if not self.collection:
                empty = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(70), padding=dp(8), bg_color=INPUT_BG)
                empty.add_widget(DarkLabel(text="Deine Sammlung ist leer.", color=MUTED))
                grid.add_widget(empty)
            query = normalize_search_text(deck_search_input.text.strip())
            selected_type = str(deck_type_spinner.text or "Alle Typen")
            for key, item in self.collection.items():
                card = item.get("card", {})
                count = int(item.get("count", 0) or 0)
                if query:
                    search_blob = normalize_search_text(" ".join([
                        str(card.get("name") or ""),
                        str(card.get("type") or ""),
                        str(card.get("race") or ""),
                        str(card.get("attribute") or ""),
                        str(card.get("_collection_set_code") or ""),
                        str(card.get("_collection_set_rarity") or ""),
                    ]))
                    if query not in search_blob:
                        continue
                card_type = str(card.get("type") or "")
                zone = self.deck_zone_for_card(card)
                if selected_type == "Monster" and "Monster" not in card_type:
                    continue
                if selected_type == "Zauber" and "Spell" not in card_type:
                    continue
                if selected_type == "Fallen" and "Trap" not in card_type:
                    continue
                if selected_type == "Extra Deck" and zone != "extra":
                    continue
                set_name, set_code, rarity = collection_set_label(card)
                used = self.deck_count_for_collection_key(deck, key)
                row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(98), spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
                row.add_widget(DarkLabel(
                    text=f"[b]{html_escape(card.get('name', ''))}[/b]\nSammlung: {count} • im Deck: {used} • {html_escape(set_code)} • {html_escape(rarity)}",
                    markup=True,
                    size_hint_x=0.58,
                ))
                controls = GridLayout(cols=3, spacing=dp(6), size_hint_x=0.42)
                add_btn = DarkButton(text="+", bg=SUCCESS if used < count else INPUT_BG_2, on_release=lambda _btn, k=key, c=card: add_entry(k, c))
                add_btn.disabled = used >= count
                minus_btn = DarkButton(text="-", bg=DANGER if used > 0 else INPUT_BG_2, on_release=lambda _btn, k=key: remove_entry(k))
                minus_btn.disabled = used <= 0
                del_btn = DarkButton(text="Löschen", bg=DANGER if used > 0 else INPUT_BG_2, on_release=lambda _btn, k=key: delete_entry(k))
                del_btn.disabled = used <= 0
                controls.add_widget(add_btn)
                controls.add_widget(minus_btn)
                controls.add_widget(del_btn)
                row.add_widget(controls)
                grid.add_widget(row)
            if keep_scroll:
                Clock.schedule_once(lambda *_: setattr(scroll, "scroll_y", old_scroll), 0)

        deck_search_input.bind(text=lambda *_: refresh_rows(keep_scroll=False))
        deck_type_spinner.bind(text=lambda *_: refresh_rows(keep_scroll=False))
        popup = self.make_popup("Karte hinzufügen", wrapper, size_hint=(0.96, 0.90))
        close_top.bind(on_release=popup.dismiss)
        refresh_rows()
        popup.open()

    def show_deck_ideas(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        cards = [entry.get("card", {}) for entry in deck.get("cards", []) for _ in range(max(1, int(entry.get("count", 0) or 0)))]
        if not cards:
            self.show_info("Deck-Ideen", "Dieses Deck ist noch leer. Füge zuerst Karten aus deiner Sammlung hinzu.")
            return
        if getattr(self, "openai_api_key", "").strip():
            deck_payload = [{"name": c.get("name", ""), "type": c.get("type", ""), "archetype": c.get("archetype", ""), "race": c.get("race", "")} for c in cards]
            prompt = "Analysiere dieses Yu-Gi-Oh Deck auf Deutsch. Erkläre Strategie, Schwächen, Karten die zusammenpassen, und welche Karten aus der Sammlung ergänzt werden könnten. Deck: " + json.dumps(deck_payload, ensure_ascii=False)
            self.call_openai_deck_helper(prompt, lambda txt: self.show_scroll_text("KI-Deck-Ideen", txt))
            return
        monsters = [c for c in cards if "Monster" in (c.get("type") or "")]
        spells = [c for c in cards if "Spell Card" in (c.get("type") or "")]
        traps = [c for c in cards if "Trap Card" in (c.get("type") or "")]
        archetypes = {}
        for c in cards:
            arc = c.get("archetype") or ""
            if arc:
                archetypes[arc] = archetypes.get(arc, 0) + 1
        top_arcs = sorted(archetypes.items(), key=lambda x: -x[1])[:3]
        lines = [
            "[b]Lokale Deck-Ideen[/b]",
            "Diese Analyse ist keine Online-KI, sondern eine lokale Hilfsfunktion auf Basis deiner gespeicherten Karten.",
            "",
            f"Karten gesamt: {len(cards)}",
            f"Monster: {len(monsters)} | Zauber: {len(spells)} | Fallen: {len(traps)}",
        ]
        if top_arcs:
            lines.append("Häufige Archetypes: " + ", ".join(f"{name} ({count})" for name, count in top_arcs))
        lines += ["", "[b]Spiel-Idee[/b]"]
        if top_arcs:
            lines.append(f"Baue den Kern um {top_arcs[0][0]} und nutze Karten, die denselben Archetype suchen, beschwören oder schützen.")
        elif len(monsters) > len(spells) + len(traps):
            lines.append("Das Deck wirkt monsterlastig. Ergänze Sucher, Schutzkarten und Boardbreaker, damit du nicht nur Normalbeschwörungen hast.")
        else:
            lines.append("Das Deck wirkt kontrollorientiert. Achte darauf, genug Starter/Monster zu spielen, damit du aktiv ins Spiel kommst.")
        if len(cards) < 40:
            lines.append("Für ein spielbares Main Deck fehlen noch Karten bis 40.")
        elif len(cards) > 60:
            lines.append("Das Deck hat mehr als 60 Karten. Reduziere es, damit du wichtige Karten häufiger ziehst.")
        else:
            lines.append("Die Deckgröße liegt im spielbaren Bereich. Prüfe als Nächstes die Balance zwischen Startern, Extendern und Schutz.")
        self.show_scroll_text("Deck-Ideen", "\n".join(lines))


    def open_ai_settings_popup(self):
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(10), bg_color=PANEL_BG)
        wrapper.add_widget(DarkLabel(
            text="[b]KI-Verknüpfung[/b]\nTrage deinen eigenen OpenAI API-Key ein. Der Key wird nur lokal in den App-Einstellungen gespeichert.",
            markup=True,
            size_hint_y=None,
            height=dp(72),
        ))
        key_input = DarkInput(text=getattr(self, "openai_api_key", ""), hint_text="OpenAI API-Key, beginnt meist mit sk-...")
        key_input.password = True
        key_input.size_hint_y = None
        key_input.height = dp(52)
        model_input = DarkInput(text=getattr(self, "openai_model", DEFAULT_OPENAI_MODEL), hint_text="Modell, z. B. gpt-4o-mini")
        model_input.size_hint_y = None
        model_input.height = dp(52)
        wrapper.add_widget(key_input)
        wrapper.add_widget(model_input)
        cloud_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        cloud_check = CheckBox(active=bool(getattr(self, "cloud_ai_scan_enabled", False)), size_hint_x=None, width=dp(44))
        cloud_row.add_widget(cloud_check)
        cloud_row.add_widget(DarkLabel(text="Cloud-KI als letzter Scanner-Fallback verwenden", color=TEXT))
        wrapper.add_widget(cloud_row)
        info = DarkLabel(
            text="Hinweis: API-Anfragen kosten je nach OpenAI-Konto Geld. Teile den Key nicht und lade ihn nicht in GitHub hoch.",
            color=MUTED,
            size_hint_y=None,
            height=dp(54),
        )
        wrapper.add_widget(info)
        btns = GridLayout(cols=3, size_hint_y=None, height=dp(50), spacing=dp(8))
        save_btn = DarkButton(text="Speichern", bg=SUCCESS)
        clear_btn = DarkButton(text="Key löschen", bg=DANGER)
        close_btn = DarkButton(text="Schließen", bg=ACCENT_2)
        btns.add_widget(save_btn)
        btns.add_widget(clear_btn)
        btns.add_widget(close_btn)
        wrapper.add_widget(btns)
        popup = self.make_popup("KI-Verknüpfung", wrapper, size_hint=(0.94, 0.62))

        def save_key(*_):
            self.openai_api_key = key_input.text.strip()
            self.openai_model = model_input.text.strip() or DEFAULT_OPENAI_MODEL
            self.cloud_ai_scan_enabled = bool(cloud_check.active)
            self.save_settings()
            self.show_info("Gespeichert", "KI-Verknüpfung wurde lokal gespeichert.")

        def clear_key(*_):
            self.openai_api_key = ""
            key_input.text = ""
            self.save_settings()
            self.set_status("KI-Key wurde gelöscht.")

        save_btn.bind(on_release=save_key)
        clear_btn.bind(on_release=clear_key)
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def call_openai_scan_vision(self, image_path, callback, error_callback=None):
        """Optionaler letzter Cloud-Fallback. Wird nur mit eigenem Key und Zustimmung verwendet."""
        api_key = getattr(self, "openai_api_key", "").strip()
        if not api_key or not bool(getattr(self, "cloud_ai_scan_enabled", False)):
            if error_callback:
                error_callback("Cloud-KI ist nicht aktiviert.")
            return
        model = getattr(self, "openai_model", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL

        def worker():
            try:
                mime = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
                raw = Path(str(image_path)).read_bytes()
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError("Bild ist für den Cloud-Fallback größer als 8 MB.")
                data_url = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
                prompt = (
                    "Analysiere diese Yu-Gi-Oh!-Karte. Antworte ausschließlich als kompaktes JSON mit den Schlüsseln "
                    "name, set_code, passcode, language, card_type, effect_excerpt, artwork_description und confidence. "
                    "Unbekannte Werte als leere Zeichenkette. Verwechsle verschiedene Artworks nicht."
                )
                payload = {
                    "model": model,
                    "store": False,
                    "input": [{"role": "user", "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url, "detail": "high"},
                    ]}],
                    "max_output_tokens": 700,
                }
                req = urllib.request.Request(
                    OPENAI_RESPONSES_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                    method="POST",
                )
                response_raw = open_url_bytes(req, timeout=45).decode("utf-8", errors="replace")
                response = json.loads(response_raw)
                text = response.get("output_text") or ""
                if not text:
                    parts = []
                    for item in response.get("output", []) or []:
                        for content in item.get("content", []) or []:
                            if content.get("type") in ("output_text", "text"):
                                parts.append(content.get("text", ""))
                    text = "\n".join(parts).strip()
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
                match = re.search(r"\{[\s\S]*\}", text)
                result = json.loads(match.group(0) if match else text)
                Clock.schedule_once(lambda *_: callback(result), 0)
            except Exception as exc:
                message = str(exc)
                Clock.schedule_once(lambda *_: (error_callback(message) if error_callback else self.show_error("Cloud-KI", message)), 0)

        threading.Thread(target=worker, daemon=True).start()

    def call_openai_deck_helper(self, prompt, callback, error_callback=None):
        api_key = getattr(self, "openai_api_key", "").strip()
        if not api_key:
            self.open_ai_settings_popup()
            self.show_error("KI-Key fehlt", "Bitte zuerst deinen OpenAI API-Key eintragen. Ohne Key bleibt die lokale Deckanalyse aktiv.")
            return
        model = getattr(self, "openai_model", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL

        def worker():
            try:
                payload = {
                    "model": model,
                    "input": prompt,
                    "max_output_tokens": 1600,
                }
                req = urllib.request.Request(
                    OPENAI_RESPONSES_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )
                raw = open_url_bytes(req, timeout=45).decode("utf-8", errors="replace")
                data = json.loads(raw)
                text = data.get("output_text") or ""
                if not text:
                    parts = []
                    for item in data.get("output", []) or []:
                        for content in item.get("content", []) or []:
                            if content.get("type") in ("output_text", "text"):
                                parts.append(content.get("text", ""))
                    text = "\n".join(parts).strip()
                if not text:
                    text = json.dumps(data, ensure_ascii=False)[:2500]
                Clock.schedule_once(lambda *_: callback(text), 0)
            except Exception as exc:
                msg = str(exc)
                Clock.schedule_once(lambda *_: (error_callback(msg) if error_callback else self.show_error("KI-Fehler", msg)), 0)

        threading.Thread(target=worker, daemon=True).start()
        self.set_status("KI-Anfrage läuft...")

    def collection_ai_payload(self, limit=180):
        rows = []
        for key, item in self.collection.items():
            card = item.get("card", {})
            count = int(item.get("count", 0) or 0)
            if count <= 0:
                continue
            set_name, set_code, rarity = collection_set_label(card)
            rows.append({
                "key": key,
                "count": count,
                "name": card.get("name", ""),
                "type": card.get("type", ""),
                "race": card.get("race", ""),
                "attribute": card.get("attribute", ""),
                "archetype": card.get("archetype", ""),
                "desc": card.get("desc", ""),
                "atk": card.get("atk"), "def": card.get("def"), "level": card.get("level"),
                "scale": card.get("scale") or card.get("pendulumScale"), "linkval": card.get("linkval"),
                "frameType": card.get("frameType", ""), "card_family": card_family(card),
                "artwork_id": artwork_identity_key(card),
                "set_code": set_code,
                "rarity": rarity,
            })
        rows.sort(key=lambda x: (x.get("archetype") or "", x.get("name") or ""))
        return rows[:limit]

    def request_ai_deck_from_collection(self):
        """Erstellt lokal bis zu drei Deckvorschläge ausschließlich aus der Sammlung."""
        total = sum(int(item.get("count", 0) or 0) for item in self.collection.values())
        if total < MIN_DECK_SIZE:
            self.show_error("Deck unvollständig", f"Für ein KI-Deck brauchst du mindestens {MIN_DECK_SIZE} Main-Deck-Karten in der Sammlung. Aktuell: {total}.")
            return
        suggestions = build_deck_suggestions(self.collection, max_suggestions=3)
        if not suggestions:
            self.show_error("KI-Deck", "Aus der Sammlung konnte kein gültiges 40-Karten-Main-Deck gebaut werden. Prüfe, ob genug Main-Deck-Karten vorhanden sind.")
            return

        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(10), bg_color=PANEL_BG)
        wrapper.add_widget(AutoHeightLabel(
            text="[b]Lokale KI-Deckvorschläge[/b]\n[color=%s]Archetype, Kartentext, Typ, Attribut, Stufe und Extra-Deck-Synergien werden kombiniert. Es werden nur vorhandene Karten verwendet.[/color]" % markup_hex(MUTED),
            markup=True, min_height=dp(72), height_padding=dp(12), color=TEXT,
        ))
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        popup = self.make_popup("KI-Deck", wrapper, size_hint=(0.96, 0.88))

        def create_suggestion(suggestion):
            if len(self.decks) >= MAX_DECKS:
                self.show_error("Deck-Limit", f"Es sind maximal {MAX_DECKS} Decks möglich.")
                return
            cards = []
            for entry in suggestion.get("cards") or []:
                key = str(entry.get("collection_key") or "")
                if key not in self.collection:
                    continue
                owned = int(self.collection[key].get("count") or 0)
                count = max(0, min(3, owned, int(entry.get("count") or 0)))
                if count <= 0:
                    continue
                cards.append({
                    "collection_key": key,
                    "count": count,
                    "zone": entry.get("zone") or self.deck_zone_for_card(entry.get("card") or {}),
                    "card": minimal_card(entry.get("card") or self.collection[key].get("card") or {}),
                })
            main_total = sum(int(x.get("count") or 0) for x in cards if x.get("zone") == "main")
            if main_total < 40:
                self.show_error("KI-Deck", f"Der Vorschlag enthält nur {main_total} Main-Deck-Karten.")
                return
            self.decks.append({"name": suggestion.get("name") or f"KI Deck {len(self.decks)+1}", "cards": cards})
            self.save_decks()
            popup.dismiss()
            stats = suggestion.get("stats") or {}
            self.show_scroll_text("KI-Deck erstellt", (
                f"{suggestion.get('name')}\n\n{suggestion.get('strategy','')}\n\n"
                f"Main: {stats.get('main',0)} • Extra: {stats.get('extra',0)} • Side: {stats.get('side',0)}\n"
                f"Synergie-Wert: {suggestion.get('score',0)}"
            ))

        for suggestion in suggestions:
            stats = suggestion.get("stats") or {}
            card = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(142), padding=dp(9), spacing=dp(6), bg_color=CARD_BG)
            card.add_widget(AutoHeightLabel(
                text=(f"[b]{escape_markup(str(suggestion.get('name','KI Deck')))}[/b]\n"
                      f"[color={markup_hex(MUTED)}]Main {stats.get('main',0)} • Extra {stats.get('extra',0)} • Side {stats.get('side',0)} • Synergie {suggestion.get('score',0)}[/color]\n"
                      f"{escape_markup(str(suggestion.get('strategy','')))}"),
                markup=True, min_height=dp(82), height_padding=dp(8), color=TEXT,
            ))
            card.add_widget(DarkButton(text="Dieses Deck erstellen", bg=GOLD, size_hint_y=None, height=dp(50), on_release=lambda _b, sug=suggestion: create_suggestion(sug)))
            grid.add_widget(card)
        popup.open()

    def try_create_deck_from_ai_text(self, text):
        try:
            match = re.search(r"\[[\s\S]*\]", text or "")
            if not match:
                return False
            items = json.loads(match.group(0))
            if not isinstance(items, list):
                return False
            deck_cards = []
            total = 0
            for it in items:
                key = str(it.get("key", ""))
                if key not in self.collection:
                    continue
                owned = int(self.collection[key].get("count", 0) or 0)
                cnt = max(0, min(int(it.get("count", 1) or 1), owned))
                if cnt <= 0:
                    continue
                deck_cards.append({"collection_key": key, "count": cnt, "card": minimal_card(self.collection[key].get("card", {}))})
                total += cnt
            if total < MIN_DECK_SIZE:
                self.show_error("Deck unvollständig", f"Der KI-Vorschlag enthält nur {total} nutzbare Karten aus deiner Sammlung.")
                return False
            if len(self.decks) >= MAX_DECKS:
                self.show_error("Deck-Limit", f"Es sind maximal {MAX_DECKS} Decks möglich.")
                return False
            self.decks.append({"name": f"KI Deck {len(self.decks) + 1}", "cards": deck_cards})
            self.save_decks()
            self.set_status(f"KI Deck mit {total} Karten erstellt.")
            return True
        except Exception as exc:
            self.show_error("KI-Auswertung", f"Antwort konnte nicht automatisch als Deck gespeichert werden: {exc}")
            return False

    def open_external_sources_popup(self):
        query = " ".join([self.name_input.text.strip() if hasattr(self, "name_input") else "", self.card_id_input.text.strip() if hasattr(self, "card_id_input") else "", self.set_input.text.strip() if hasattr(self, "set_input") else ""]).strip()
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(10), bg_color=PANEL_BG)
        wrapper.add_widget(DarkLabel(
            text="[b]Web-Quellen prüfen und lokal speichern[/b]\nCardmarket/Cardcluster werden im Browser geöffnet. Die Felder unten entsprechen jetzt der lokalen Kartenanlage, damit du gefundene Daten direkt sauber speichern kannst.",
            markup=True,
            size_hint_y=None,
            height=dp(86),
        ))
        q_input = DarkInput(text=query, hint_text="Kartenname, Set-Code oder Passcode")
        q_input.size_hint_y = None
        q_input.height = dp(50)
        wrapper.add_widget(q_input)
        btns = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(8))
        btns.add_widget(DarkButton(text="Cardmarket öffnen", bg=GOLD, on_release=lambda *_: webbrowser.open("https://www.cardmarket.com/de/YuGiOh/Products/Search?searchString=" + urllib.parse.quote(q_input.text.strip()))))
        btns.add_widget(DarkButton(text="Cardcluster öffnen", bg=ACCENT_2, on_release=lambda *_: webbrowser.open("https://cardcluster.com/search/" + urllib.parse.quote(q_input.text.strip()))))
        wrapper.add_widget(btns)

        fields = {}
        specs = [
            ("name", "Name"),
            ("card_id", "Eigene ID / Passcode"),
            ("type", "Kartentyp z. B. Effect Monster"),
            ("race", "Typ/Race z. B. Dragon"),
            ("attribute", "Eigenschaft z. B. DARK"),
            ("level", "Stufe / Rank / Link"),
            ("atk", "ATK"),
            ("def", "DEF"),
            ("set_name", "Set-Name"),
            ("set_code", "Set-Code/Kürzel z. B. SBCB-DE001"),
            ("rarity", "Rarity"),
            ("image", "Bild-URL oder lokaler Bildpfad"),
        ]
        grid = GridLayout(cols=1 if self.ui_width_below(560) else 2, spacing=dp(8), size_hint_y=None)
        for key, hint in specs:
            inp = DarkInput(hint_text=hint)
            inp.size_hint_y = None
            inp.height = dp(50)
            if key == "name":
                inp.text = q_input.text.strip()
            if key == "card_id":
                inp.text = re.sub(r"\W+", "_", q_input.text.strip()).strip("_")[:40]
            fields[key] = inp
            grid.add_widget(inp)
        grid.height = self.grid_height(len(specs), grid.cols, dp(50), dp(8))
        wrapper.add_widget(grid)

        image_btns = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(8))
        use_last_photo = DarkButton(text="Letztes Foto nutzen", bg=GOLD)
        choose_gallery = DarkButton(text="Bild aus Galerie", bg=ACCENT_2)
        image_btns.add_widget(use_last_photo)
        image_btns.add_widget(choose_gallery)
        wrapper.add_widget(image_btns)

        desc = DarkInput(hint_text="Effekt/Beschreibung oder Notiz aus Webquelle")
        desc.multiline = True
        desc.size_hint_y = None
        desc.height = dp(110)
        wrapper.add_widget(desc)
        bottom = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(8))
        save_btn = DarkButton(text="Lokal speichern", bg=SUCCESS)
        close_btn = DarkButton(text="Schließen", bg=ACCENT_2)
        bottom.add_widget(save_btn)
        bottom.add_widget(close_btn)
        wrapper.add_widget(bottom)
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"], do_scroll_x=False)
        scroll.add_widget(wrapper)
        popup = self.make_popup("Web-Quelle speichern", scroll, size_hint=(0.96, 0.94))

        def use_photo(*_):
            path = getattr(self, "last_scan_photo", "") or ""
            if path and os.path.exists(path):
                fields["image"].text = path
                self.set_status("Letztes Scannerfoto als Kartenbild eingetragen.")
            else:
                self.show_error("Kein Foto", "Bitte zuerst im Karten-Scanner ein Foto/Galeriebild laden oder eine Bild-URL/einen lokalen Pfad eintragen.")

        def choose_gallery_image(*_):
            def accept(path):
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    fields["image"].text = path
                    self.last_scan_photo = path
                    self.set_status("Galeriebild als lokales Kartenbild eingetragen.")
                else:
                    self.show_error("Kein Bild", "Das ausgewählte Bild konnte nicht gelesen werden.")
            def fallback(message=""):
                try:
                    from plyer import filechooser
                    def _on_selection(selection):
                        selected = selection[0] if isinstance(selection, (list, tuple)) and selection else (selection or "")
                        selected = str(selected.toString()) if hasattr(selected, "toString") else str(selected)
                        if not selected:
                            return
                        if selected.startswith("content://") and platform == "android":
                            selected = copy_android_content_uri_to_file(selected, self.user_data_dir, "custom_card_image")
                        accept(selected)
                    try:
                        filechooser.open_file(on_selection=_on_selection, filters=[("Bilder", "*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff", "*.heic", "*.heif", "*.avif")])
                    except TypeError:
                        filechooser.open_file(on_selection=_on_selection)
                except Exception as exc:
                    self.show_error("Galerie", str(exc) or message or "Galerie konnte nicht geöffnet werden.")
            if platform == "android":
                started = start_android_image_picker(
                    self.user_data_dir,
                    lambda path: Clock.schedule_once(lambda *_: accept(path), 0),
                    lambda msg: Clock.schedule_once(lambda *_: fallback(msg), 0),
                )
                if started:
                    return
            fallback("Android-Bildauswahl konnte nicht gestartet werden.")

        def as_int(value):
            try:
                value = str(value or "").strip()
                return int(value) if value else None
            except Exception:
                return None

        def save_external(*_):
            name = fields["name"].text.strip() or q_input.text.strip()
            if not name:
                self.show_error("Name fehlt", "Bitte mindestens einen Kartennamen oder Code eintragen.")
                return
            cid = fields["card_id"].text.strip() or ("EXT-" + re.sub(r"\W+", "_", name).strip("_")[:40])
            image = fields["image"].text.strip()
            card = {
                "id": cid,
                "name": name,
                "type": fields["type"].text.strip() or "External / Web Source",
                "frameType": "custom",
                "desc": desc.text.strip() or "Lokal gespeicherter Eintrag aus Cardmarket/Cardcluster-Recherche.",
                "race": fields["race"].text.strip(),
                "attribute": fields["attribute"].text.strip(),
                "level": as_int(fields["level"].text),
                "atk": as_int(fields["atk"].text),
                "def": as_int(fields["def"].text),
                "custom": True,
                "external_source": True,
                "card_images": [{"id": cid, "image_url": image, "image_url_small": image}] if image else [],
                "card_sets": [{"set_name": fields["set_name"].text.strip() or "Web-Quelle", "set_code": fields["set_code"].text.strip(), "set_rarity": fields["rarity"].text.strip() or "Unbekannt", "set_price": "0.00"}],
            }
            cards = load_custom_cards()
            cards = [c for c in cards if str(c.get("id")) != str(cid)]
            cards.append(card)
            path = save_custom_cards(cards)
            self.set_status(f"Lokal gespeichert: {name}")
            self.show_info("Webkarte gespeichert", f"{name} wurde lokal gespeichert.\n\n{path}")
            popup.dismiss()

        use_last_photo.bind(on_release=use_photo)
        choose_gallery.bind(on_release=choose_gallery_image)
        save_btn.bind(on_release=save_external)
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def open_collection_popup(self):
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(10), padding=dp(10), bg_color=DARK_BG, border_color=(0, 0, 0, 0), radius=0)
        header = SurfaceBox(
            orientation="horizontal", size_hint_y=None, height=dp(72), spacing=dp(10), padding=(dp(10), dp(8)),
            bg_color=PANEL_BG_2, border_color=tuple(list(SUCCESS[:3]) + [0.16]), radius=dp(22), elevation=1,
        )
        icon_box = SurfaceBox(orientation="vertical", size_hint=(None, None), width=dp(50), height=dp(50), padding=dp(10), bg_color=tuple(list(SUCCESS[:3]) + [0.13]), border_color=(0, 0, 0, 0), radius=dp(16))
        icon_box.add_widget(Image(source=ui_asset("cards"), allow_stretch=True, keep_ratio=True))
        header.add_widget(icon_box)
        title_label = AutoHeightLabel(text="[b]Deine Sammlung[/b]\n[color=%s]Varianten, Mengen und Artworks übersichtlich verwalten[/color]" % markup_hex(MUTED), markup=True, min_height=dp(54), font_size=ui_font_px(13.8, body=True))
        total_label = ModernChip("0 Karten", "collection", active=True, accent=SUCCESS, size_hint_x=None)
        total_label.width = dp(130)
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(title_label)
        header.add_widget(total_label)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        collection_profile = self.current_ui_profile()
        collection_filter_cols = 1 if float(collection_profile.get("width_dp") or 0) < 560 else 3
        collection_filter_h = dp(48)
        filter_row = GridLayout(
            cols=collection_filter_cols,
            spacing=dp(8),
            size_hint_y=None,
            height=self.grid_height(3, collection_filter_cols, collection_filter_h, dp(8)),
        )
        collection_search = DarkInput(hint_text="Sammlung durchsuchen", size_hint_y=None, height=collection_filter_h)
        collection_sort = DarkSpinner(text="Sortierung: Kategorie", values=["Sortierung: Kategorie", "Name A-Z", "Set-Code", "Rarity", "Anzahl"], size_hint_y=None, height=collection_filter_h)
        collection_filter = DarkSpinner(text="Alle Karten", values=["Alle Karten", "Nur doppelte", "Ohne Set", "Ohne Bild"], size_hint_y=None, height=collection_filter_h)
        filter_row.add_widget(collection_search)
        filter_row.add_widget(collection_sort)
        filter_row.add_widget(collection_filter)
        wrapper.add_widget(filter_row)

        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)

        def update_total_label():
            value = f"{sum(int(i.get('count', 0)) for i in self.collection.values())} Karten"
            try:
                total_label.label.text = value
            except Exception:
                pass

        def render_collection():
            keep_scroll = getattr(scroll, "scroll_y", 1)
            grid.clear_widgets()
            update_total_label()
            if not self.collection:
                grid.add_widget(EmptyStateCard(
                    "Deine Sammlung ist noch leer",
                    "Füge Karten über die Suche oder den Scanner hinzu. Jede Set- und Artwork-Variante bleibt getrennt.",
                    icon_name="cards",
                ))
            else:
                query = normalize_search_text(collection_search.text)
                filter_mode = collection_filter.text
                grouped = {}
                for key, item in self.collection.items():
                    card = item.get("card", {})
                    if query and query not in normalize_search_text(card.get("name", "") + " " + collection_set_label(card)[1] + " " + collection_set_label(card)[2]):
                        continue
                    if filter_mode == "Nur doppelte" and int(item.get("count", 0) or 0) < 2:
                        continue
                    if filter_mode == "Ohne Set" and (card.get("card_sets") or get_collection_set_from_card(card)):
                        continue
                    if filter_mode == "Ohne Bild" and get_image_url(card):
                        continue
                    grouped.setdefault(category_for(card), []).append((key, item))
                for cat in CATEGORY_ORDER:
                    items = grouped.get(cat, [])
                    if not items:
                        continue
                    title_card = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(42), padding=dp(8), bg_color=INPUT_BG_2)
                    title_card.add_widget(DarkLabel(text=f"[b]{cat}[/b]", markup=True))
                    grid.add_widget(title_card)
                    if collection_sort.text == "Name A-Z":
                        items.sort(key=lambda pair: normalize_search_text(pair[1].get("card", {}).get("name", "")))
                    elif collection_sort.text == "Set-Code":
                        items.sort(key=lambda pair: collection_set_label(pair[1].get("card", {}))[1])
                    elif collection_sort.text == "Rarity":
                        items.sort(key=lambda pair: collection_set_label(pair[1].get("card", {}))[2])
                    elif collection_sort.text == "Anzahl":
                        items.sort(key=lambda pair: -int(pair[1].get("count", 0) or 0))
                    else:
                        items.sort(key=lambda pair: category_sort_key(pair[1].get("card", {})))
                    for key, item in items:
                        card = item.get("card", {})
                        count = int(item.get("count", 0))
                        grid.add_widget(self.create_collection_row(key, card, count, render_callback=render_collection, total_callback=update_total_label))
            Clock.schedule_once(lambda *_: setattr(scroll, "scroll_y", keep_scroll), 0)

        popup = self.make_inline_page("collection", wrapper, back_to="search")
        close_top.bind(on_release=popup.dismiss)
        collection_search.bind(text=lambda *_: render_collection())
        collection_sort.bind(text=lambda *_: render_collection())
        collection_filter.bind(text=lambda *_: render_collection())
        render_collection()
        popup.open()

    def open_collection_card_preview(self, card):
        """Zeigt eine echte Kartenansicht innerhalb des Sammlungsbereichs."""
        card = dict(card or {})
        if not card:
            self.show_error("Keine Karte", "Für diesen Sammlungseintrag sind keine Kartendaten vorhanden.")
            return
        self.selected_card = card
        profile = self.current_ui_profile()
        compact = float(profile.get("width_dp") or 0) < 620
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(9), padding=dp(9), bg_color=PANEL_BG)

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8))
        header.add_widget(DarkLabel(
            text=f"[b]{html_escape(card.get('name', 'Karte'))}[/b]\n[color={markup_hex(MUTED)}]Sammlungs-Vorschau[/color]",
            markup=True,
            color=TEXT,
            halign="left",
        ))
        wrapper.add_widget(header)

        scroll = ScrollView(bar_width=dp(5), scroll_type=["bars", "content"], do_scroll_x=False)
        body = BoxLayout(
            orientation="vertical" if compact else "horizontal",
            size_hint_y=None,
            spacing=dp(10),
            padding=(0, 0, 0, dp(10)),
        )
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)
        wrapper.add_widget(scroll)

        image_card = SurfaceBox(
            orientation="vertical",
            size_hint=(1, None) if compact else (0.42, None),
            height=dp(430 if compact else 560),
            padding=dp(10),
            bg_color=CARD_BG,
            radius=dp(20),
        )
        placeholder = resource_find(PREVIEW_PLACEHOLDER_FILE) or ""
        preview = Image(source=placeholder, allow_stretch=True, keep_ratio=True)
        image_card.add_widget(preview)
        body.add_widget(image_card)

        set_name, set_code, rarity = collection_set_label(card)
        collection_key = self._first_matching_collection_key(card)
        collection_entry = self.collection.get(collection_key, {}) if collection_key else {}
        metadata_v104 = normalized_collection_metadata(collection_entry.get("metadata") or {})
        desc = str(card.get("desc") or card.get("description") or card.get("effect") or "Kein Effekttext vorhanden.")
        details_text = (
            f"[b][size=18]{html_escape(card.get('name', 'Karte'))}[/size][/b]\n"
            f"[color={markup_hex(GOLD)}]{html_escape(artwork_label(card))}[/color]\n\n"
            f"[b]Sammlungsvariante[/b]\n"
            f"Set: {html_escape(set_name or '-')}\n"
            f"Set-Code: {html_escape(set_code or '-')}\n"
            f"Rarity: {html_escape(rarity or '-')}\n"
            f"Anzahl: {collection_count_for(self.collection, card)}\n"
            f"Zustand: {html_escape(metadata_v104.get('condition', 'Near Mint'))}\n"
            f"Sprache: {html_escape(metadata_v104.get('language', 'Deutsch'))}\n"
            f"Auflage: {html_escape(metadata_v104.get('edition', 'Unbekannt'))}\n"
            f"Lagerort: {html_escape(metadata_v104.get('storage_location', '-') or '-')}\n\n"
            f"[b]Kartendaten[/b]\n"
            f"Typ: {html_escape(display_card_type(card.get('type', '')))}\n"
            f"Untertyp: {html_escape(card.get('race', '-') or '-')}\n"
            f"Eigenschaft: {html_escape(card.get('attribute', '-') or '-')}\n"
            f"Stufe/Rang/Link: {html_escape(str(get_level_value(card) or '-'))}\n"
            f"ATK {html_escape(str(card.get('atk', '-')))} / DEF {html_escape(str(card.get('def', '-')))}\n\n"
            f"[b]Effekt / Beschreibung[/b]\n{html_escape(desc)}\n\n"
            f"[b]Sets und Reprints[/b]\n{html_escape(set_entries_text(card, 16))}"
        )
        detail_card = SurfaceBox(
            orientation="vertical",
            size_hint=(1, None) if compact else (0.58, None),
            height=dp(520 if compact else 560),
            padding=dp(12),
            spacing=dp(8),
            bg_color=CARD_BG,
            radius=dp(20),
        )
        detail_scroll = ScrollView(bar_width=dp(5), scroll_type=["bars", "content"], do_scroll_x=False)
        detail_label = AutoHeightLabel(
            text=details_text,
            markup=True,
            color=TEXT,
            font_size=ui_font_px(11.8, profile, body=True),
            min_height=dp(120),
            height_padding=dp(18),
        )
        detail_scroll.add_widget(detail_label)
        detail_card.add_widget(detail_scroll)
        body.add_widget(detail_card)

        actions_cols = 1 if self.ui_width_below(420) else 4
        actions = GridLayout(
            cols=actions_cols,
            size_hint_y=None,
            height=self.grid_height(4, actions_cols, dp(48), dp(7)),
            spacing=dp(7),
        )
        large_btn = DarkButton(text="Bild groß anzeigen", bg=ACCENT_2, no_wrap=True)
        effect_btn = DarkButton(text="Effekt lesen", bg=ACCENT_2, no_wrap=True)
        metadata_btn = DarkButton(text="Details bearbeiten", bg=GOLD, no_wrap=True)
        back_btn = DarkButton(text="Zur Sammlung", bg=INPUT_BG_2, no_wrap=True)
        actions.add_widget(large_btn)
        actions.add_widget(effect_btn)
        actions.add_widget(metadata_btn)
        actions.add_widget(back_btn)
        wrapper.add_widget(actions)

        page = self.make_inline_page("collection_preview", wrapper, back_to="collection")
        large_btn.bind(on_release=lambda *_: self.show_large_card_image(card))
        effect_btn.bind(on_release=lambda *_: self.show_scroll_text(card.get("name", "Kartentext"), desc))
        metadata_btn.bind(on_release=lambda *_: self.open_collection_metadata_editor(card))
        back_btn.bind(on_release=lambda *_: page.dismiss())
        page.open()

        def set_preview(path):
            try:
                if path and os.path.exists(path):
                    preview.source = path
                    preview.reload()
            except Exception:
                pass

        image_url = get_image_url(card)
        if image_url and os.path.exists(str(image_url)):
            set_preview(str(image_url))
        elif image_url:
            def worker():
                try:
                    path = download_card_image(card, self.image_cache_dir)
                    Clock.schedule_once(lambda *_: set_preview(path), 0)
                except Exception as exc:
                    Clock.schedule_once(lambda *_: self.set_status(f"Sammlungsbild konnte nicht geladen werden: {short_text(exc, 90)}"), 0)
            threading.Thread(target=worker, daemon=True).start()

    def create_collection_row(self, cid, card, count, render_callback=None, total_callback=None):
        """Bildgestützte Sammlungszeile mit getrennten, sicheren Aktionen."""
        profile = self.current_ui_profile()
        compact = float(profile.get("width_dp") or 0) < 560
        top_h_dp = 148
        action_cols = 3 if compact else 5
        action_h_dp = grid_height_v110(5, action_cols, 48, 6)
        row = SurfaceBox(
            orientation="vertical",
            size_hint_y=None,
            height=dp(top_h_dp + action_h_dp + 28),
            spacing=dp(8),
            padding=dp(10),
            bg_color=CARD_BG,
            border_color=tuple(list(SUCCESS[:3]) + [0.12]),
            radius=dp(20),
        )
        set_name, set_code, rarity = collection_set_label(card)
        top_h = dp(top_h_dp)
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=top_h, spacing=dp(10))

        thumb = SurfaceBox(
            orientation="vertical", size_hint=(None, None), width=dp(82), height=top_h,
            padding=dp(4), bg_color=INPUT_BG, border_color=tuple(list(GOLD[:3]) + [0.20]), radius=dp(14),
        )
        image_url = get_image_url(card)
        if image_url:
            img = AsyncImage(source=image_url, allow_stretch=True, keep_ratio=True)
            try:
                if hasattr(img, "fit_mode"):
                    img.fit_mode = "contain"
            except Exception:
                pass
            thumb.add_widget(img)
        else:
            thumb.add_widget(Image(source=resource_find(PREVIEW_PLACEHOLDER_FILE) or "", allow_stretch=True, keep_ratio=True))
        top.add_widget(thumb)

        info_box = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_x=1)
        title_label = DarkLabel(
            text=f"[b]{html_escape(str(card.get('name') or 'Unbekannte Karte'))}[/b]",
            markup=True, color=TEXT, halign="left", size_hint_y=None, height=dp(42),
            font_size=ui_font_px(13.8, profile),
        )
        info_box.add_widget(title_label)
        info_box.add_widget(DarkLabel(
            text=(
                f"{html_escape(category_for(card))}  •  {html_escape(display_card_type(card.get('type', '')))}\n"
                f"ATK {card.get('atk', '-')}  •  DEF {card.get('def', '-')}  •  Stufe {get_level_value(card) or '-'}"
            ),
            color=MUTED, halign="left", size_hint_y=None, height=dp(42),
            font_size=ui_font_px(10.4, profile, body=True),
        ))
        variant_label = DarkLabel(
            text=f"[color={markup_hex(GOLD)}]{html_escape(set_code or '-')}[/color]  •  {html_escape(short_text(rarity or '-', 36))}",
            markup=True, color=GOLD, halign="left", size_hint_y=None, height=dp(28),
            font_size=ui_font_px(10.2, profile, body=True),
        )
        info_box.add_widget(variant_label)
        count_label = DarkLabel(
            text=f"[b]{count}× in Sammlung[/b]",
            markup=True, color=SUCCESS if count else MUTED, halign="left", size_hint_y=None, height=dp(26),
            font_size=ui_font_px(10.6, profile),
        )
        info_box.add_widget(count_label)
        top.add_widget(info_box)
        top.bind(on_touch_down=lambda widget, touch: self.open_collection_card_preview(card) if widget.collide_point(*touch.pos) else None)
        row.add_widget(top)

        def refresh_row_text(new_count):
            count_label.text = f"[b]{new_count}× in Sammlung[/b]"
            count_label.color = SUCCESS if new_count else MUTED

        def plus_one(*_):
            if cid not in self.collection:
                self.collection[cid] = {"count": 0, "card": minimal_card(card)}
            self.collection[cid]["count"] = int(self.collection[cid].get("count", 0) or 0) + 1
            refresh_row_text(self.collection[cid]["count"])
            self.update_collection_info()
            if total_callback:
                total_callback()
            self.save_collection(show_popup=False)
            self.refresh_results_list()

        def minus_one(*_):
            if cid not in self.collection:
                return
            self.collection[cid]["count"] = int(self.collection[cid].get("count", 0) or 0) - 1
            if self.collection[cid]["count"] <= 0:
                del self.collection[cid]
                self.update_collection_info()
                self.save_collection(show_popup=False)
                self.refresh_results_list()
                if render_callback:
                    render_callback()
                return
            refresh_row_text(self.collection[cid]["count"])
            self.update_collection_info()
            if total_callback:
                total_callback()
            self.save_collection(show_popup=False)
            self.refresh_results_list()

        actions = GridLayout(
            cols=action_cols,
            size_hint_y=None,
            height=dp(action_h_dp),
            spacing=dp(6),
            row_default_height=dp(48),
            row_force_default=True,
        )
        actions.add_widget(DarkButton(text="Ansehen", bg=ACCENT_2, no_wrap=True, compact=True, on_release=lambda *_: self.open_collection_card_preview(card)))
        actions.add_widget(DarkButton(text="−", bg=DANGER, no_wrap=True, compact=True, on_release=minus_one))
        actions.add_widget(DarkButton(text="+", bg=SUCCESS, no_wrap=True, compact=True, on_release=plus_one))
        actions.add_widget(DarkButton(text="Artwork", bg=ACCENT_2, no_wrap=True, compact=True, on_release=lambda *_: self.open_image_for_card(card)))
        actions.add_widget(DarkButton(text="Entfernen", bg=DANGER, no_wrap=True, compact=True, on_release=lambda *_: self.delete_card_by_id(cid, render_callback=render_callback)))
        row.add_widget(actions)
        return row

    def delete_card_by_id(self, cid, render_callback=None):
        if cid in self.collection:
            name = self.collection[cid].get("card", {}).get("name", "Karte")
            del self.collection[cid]
            self.update_collection_info()
            self.save_collection(show_popup=False)
            self.refresh_results_list()
            if render_callback:
                render_callback()
            self.set_status(f"{name} wurde aus der Sammlung gelöscht.")

    def _on_preview_touch(self, instance, touch):
        if instance.collide_point(*touch.pos) and self.selected_card:
            self.show_large_card_image(self.selected_card)
            return True
        return False

    def show_large_card_image(self, card):
        source = ""
        if self.selected_card and get_card_id(self.selected_card) == get_card_id(card):
            source = getattr(self.preview_image, "source", "") or ""
        if source and os.path.exists(source):
            self._open_large_image_popup(source, card.get("name", "Kartenbild"))
            return
        if get_image_url(card):
            self.set_status("Großansicht wird geladen...")
            threading.Thread(target=self._large_image_thread, args=(card,), daemon=True).start()
            return
        self.show_error("Kein Bild", "Für diese Karte wurde kein Bild gefunden.")

    def _large_image_thread(self, card):
        try:
            if getattr(self, "wifi_only_images", False) and not android_is_unmetered_network():
                Clock.schedule_once(lambda *_: self.show_info("WLAN-only aktiv", "Das große Kartenbild wird erst über WLAN oder Ethernet geladen."), 0)
                return
            path = download_card_image(card, self.image_cache_dir)
            title = card.get("name", "Kartenbild")
            Clock.schedule_once(lambda *_: self._open_large_image_popup(path, title), 0)
        except Exception as exc:
            Clock.schedule_once(lambda *_: self.show_error("Bild konnte nicht geladen werden", str(exc)), 0)

    def _open_large_image_popup(self, source, title):
        if not source:
            self.show_error("Kein Bild", "Das Vorschaubild ist noch nicht geladen.")
            return
        content = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(8), bg_color=PANEL_BG)
        image_holder = SurfaceBox(orientation="vertical", bg_color=INPUT_BG, border_color=(0.91, 0.72, 0.26, 0.35), radius=dp(18), padding=dp(8))
        big_image = Image(source=source, allow_stretch=True, keep_ratio=True)
        image_holder.add_widget(big_image)
        content.add_widget(image_holder)
        btn_row = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(8), row_default_height=dp(50), row_force_default=True)
        open_btn = DarkButton(text="Im Browser öffnen", bg=ACCENT_2, on_release=lambda *_: self.open_image_for_card(self.selected_card or {}))
        close_btn = DarkButton(text="Schließen", bg=ACCENT)
        btn_row.add_widget(open_btn)
        btn_row.add_widget(close_btn)
        content.add_widget(btn_row)
        popup = self.make_popup(title, content, size_hint=(0.96, 0.94))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def open_selected_image(self):
        if not self.selected_card:
            self.show_error("Keine Auswahl", "Bitte zuerst eine Karte auswählen.")
            return
        self.show_large_card_image(self.selected_card)

    def open_image_for_card(self, card):
        url = get_image_url(card)
        if not url:
            self.show_error("Kein Bild", "Für diese Karte wurde kein Bild gefunden.")
            return
        try:
            webbrowser.open(url)
        except Exception as exc:
            self.show_error("Bild konnte nicht geöffnet werden", str(exc))

    def show_selected_reprints(self):
        if not self.selected_card:
            self.show_error("Keine Auswahl", "Bitte zuerst eine Karte auswählen.")
            return
        self.show_reprints_popup(self.selected_card)

    def show_reprints_popup(self, card):
        card_sets = sorted(card.get("card_sets") or [], key=rarity_sort_key)
        images = get_artwork_images(card)
        if not images and card.get("_artwork_image"):
            images = [card.get("_artwork_image")]
        content = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(8), bg_color=PANEL_BG)
        title = DarkLabel(
            text=(
                f"[b]{html_escape(card.get('name', ''))}[/b]\n"
                f"{max(1, len(images))} Artwork(s) • {len(card_sets)} Set-Eintrag(e) • {html_escape(rarity_summary(card, 8))}"
            ),
            markup=True,
            color=TEXT,
            size_hint_y=None,
            height=dp(58),
        )
        content.add_widget(title)

        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        if not card_sets and not images:
            empty = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(110), padding=dp(10), bg_color=INPUT_BG)
            empty.add_widget(DarkLabel(text="Für diese Karte liefert die API keine Reprint-/Rarity-Daten.", color=MUTED))
            grid.add_widget(empty)
        else:
            if not images:
                images = [None]
            total = max(1, len(images))
            for idx, image in enumerate(images):
                variant = dict(card)
                variant["_artwork_index"] = idx
                variant["_artwork_total"] = total
                if image:
                    variant["_artwork_image"] = image
                    variant["_variant_key"] = str(image.get("id") or f"{card.get('id', card.get('name', 'card'))}-art{idx + 1}")
                grid.add_widget(self.create_artwork_reprint_group(variant, card_sets))

        scroll.add_widget(grid)
        content.add_widget(scroll)
        close_btn = DarkButton(text="Schließen", size_hint_y=None, height=dp(50), bg=ACCENT)
        content.add_widget(close_btn)
        popup = self.make_popup("Artworks, Reprints & Rarities", content, size_hint=(0.96, 0.92))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def create_artwork_reprint_group(self, card, card_sets):
        visible_sets = sorted(card_sets or [], key=rarity_sort_key)
        height = dp(168) + min(len(visible_sets), 8) * dp(26)
        if len(visible_sets) > 8:
            height += dp(24)
        row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=height, spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
        img_url = get_image_url(card)
        if img_url:
            row.add_widget(AsyncImage(source=img_url, allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(96)))
        else:
            holder = SurfaceBox(orientation="vertical", bg_color=INPUT_BG, size_hint_x=None, width=dp(96), padding=dp(4))
            holder.add_widget(DarkLabel(text="Kein\nBild", color=MUTED, halign="center"))
            row.add_widget(holder)

        info = BoxLayout(orientation="vertical", spacing=dp(3))
        info.add_widget(DarkLabel(text=f"[b]{html_escape(artwork_label(card))}[/b]", markup=True, size_hint_y=None, height=dp(26)))
        info.add_widget(DarkLabel(text="Als eigene Karte/Sammlungsvariante geführt, wenn sich das Artwork unterscheidet.", color=MUTED, size_hint_y=None, height=dp(34), font_size=ui_font_px(11, body=True)))
        info.add_widget(DarkLabel(text="[b]Sets mit gleichem Artwork / Reprints[/b]", markup=True, size_hint_y=None, height=dp(24), font_size=ui_font_px(13, body=True)))
        if not visible_sets:
            info.add_widget(DarkLabel(text="Keine Set-Daten vorhanden.", color=MUTED, size_hint_y=None, height=dp(24), font_size=ui_font_px(12, body=True)))
        else:
            for item in visible_sets[:8]:
                rarity = (item.get("set_rarity") or "Unbekannt").strip() or "Unbekannt"
                line = f"• {item.get('set_name', 'Unbekanntes Set')} — {item.get('set_code', '-') or '-'} — {rarity}"
                info.add_widget(DarkLabel(text=html_escape(line), color=TEXT, size_hint_y=None, height=dp(24), font_size=ui_font_px(12, body=True)))
            if len(visible_sets) > 8:
                info.add_widget(DarkLabel(text=f"… +{len(visible_sets) - 8} weitere Sets in der Kartenbeschreibung", color=GOLD, size_hint_y=None, height=dp(24), font_size=ui_font_px(12, body=True)))
        info.add_widget(DarkLabel(text="Hinweis: Die API liefert Sets/Rarities, aber keine sichere Set-Code-zu-Artwork-Zuordnung. Deshalb werden bekannte Set-Einträge beim Artwork zusammen angezeigt.", color=MUTED, size_hint_y=None, height=dp(42), font_size=ui_font_px(10, body=True)))
        row.add_widget(info)
        return row

    def create_reprint_row(self, card, set_item):
        rarity = (set_item.get("set_rarity") or "Unbekannt").strip() or "Unbekannt"
        row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(122), spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
        img_url = get_image_url(card)
        if img_url:
            row.add_widget(AsyncImage(source=img_url, allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(70)))
        else:
            holder = SurfaceBox(orientation="vertical", bg_color=INPUT_BG, size_hint_x=None, width=dp(70), padding=dp(4))
            holder.add_widget(DarkLabel(text="Kein\nBild", color=MUTED, halign="center"))
            row.add_widget(holder)

        info = BoxLayout(orientation="vertical", spacing=dp(3))
        info.add_widget(DarkLabel(text=f"[b]{html_escape(set_item.get('set_name', 'Unbekanntes Set'))}[/b]", markup=True, size_hint_y=None, height=dp(26)))
        info.add_widget(DarkLabel(text=f"Set-Code: {html_escape(set_item.get('set_code', '-') or '-')}", color=MUTED, size_hint_y=None, height=dp(20), font_size=ui_font_px(12, body=True)))
        info.add_widget(DarkLabel(text=f"Rarity: {html_escape(rarity)}", color=TEXT, size_hint_y=None, height=dp(22), font_size=ui_font_px(13, body=True)))
        price = set_item.get("set_price", "")
        if price not in (None, ""):
            info.add_widget(DarkLabel(text=f"Preis/API: {html_escape(str(price))}", color=GOLD, size_hint_y=None, height=dp(20), font_size=ui_font_px(12, body=True)))
        else:
            info.add_widget(DarkLabel(text="Preis/API: -", color=MUTED, size_hint_y=None, height=dp(20), font_size=ui_font_px(12, body=True)))
        info.add_widget(DarkLabel(text="Hinweis: Das Bild kommt von der Kartendatenbank; Set-Code/Rarity unterscheiden die Reprints.", color=MUTED, size_hint_y=None, height=dp(28), font_size=ui_font_px(10, body=True)))
        row.add_widget(info)

        tag = StatPill(text=rarity, bg_color=rarity_color(rarity), size_hint_x=None, width=dp(108), halign="center")
        row.add_widget(tag)
        return row

    def show_selected_effect(self):
        if not self.selected_card:
            self.show_error("Keine Auswahl", "Bitte zuerst eine Karte auswählen.")
            return
        desc = self.selected_card.get("desc", "Kein Effekttext vorhanden.")
        self.show_scroll_text(self.selected_card.get("name", "Kartentext"), desc)

    def show_scroll_text(self, title, text):
        content = SurfaceBox(orientation="vertical", spacing=dp(10), padding=dp(10), bg_color=PANEL_BG)

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        title_row.add_widget(DarkLabel(text=f"[b]{html_escape(title)}[/b]", markup=True, color=TEXT, font_size=ui_font_px(16, body=True)))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        title_row.add_widget(close_top)
        content.add_widget(title_row)

        label = DarkLabel(text=text, color=TEXT, markup=True, size_hint_y=None, font_size=ui_font_px(13, body=True))
        label.bind(width=lambda instance, value: setattr(instance, "text_size", (max(1, value - dp(12)), None)))
        label.bind(texture_size=lambda instance, value: setattr(instance, "height", value[1] + dp(26)))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(label)
        content.add_widget(scroll)
        popup = self.make_popup("", content, size_hint=(0.94, 0.86))
        close_top.bind(on_release=popup.dismiss)
        popup.open()

    def open_unified_gallery_scan(self, *_):
        """Öffnet genau einen Android-Bilddialog für ein oder mehrere Bilder.

        Die App entscheidet erst nach der Auswahl automatisch, ob ein Einzelbild
        oder ein Stapel verarbeitet wird. Dadurch gibt es keine getrennten Buttons
        mehr für Galerie und Mehrfachauswahl.
        """
        self.set_status("Bilder auswählen …")

        def accept_paths(paths):
            clean = []
            for raw_path in paths or []:
                try:
                    value = str(raw_path or "")
                    if value and os.path.exists(value) and os.path.getsize(value) > 0:
                        clean.append(value)
                except Exception:
                    continue
            # Reihenfolge erhalten und doppelte URI-Kopien vermeiden.
            unique = []
            seen = set()
            for item in clean:
                signature = os.path.abspath(item)
                if signature not in seen:
                    seen.add(signature)
                    unique.append(item)
            if not unique:
                self.show_error("Keine Bilder", "Es wurden keine lesbaren Bilder ausgewählt.")
                return
            count = len(unique)
            self.set_status(f"{count} Bild(er) ausgewählt. Scan wird vorbereitet …")
            self.start_bulk_gallery_ocr_import(unique)

        def fallback_picker(message=""):
            try:
                from plyer import filechooser
            except Exception:
                self.show_error("Galerie nicht verfügbar", message or "Der Android-Bilddialog konnte nicht geöffnet werden.")
                return

            def selected(selection):
                values = []
                for raw in selection or []:
                    try:
                        value = str(raw.toString()) if hasattr(raw, "toString") else str(raw)
                    except Exception:
                        value = str(raw)
                    if value.startswith("content://") and platform == "android":
                        try:
                            value = copy_android_content_uri_to_file(value, self.user_data_dir, "gallery_scan")
                        except Exception:
                            value = ""
                    if value:
                        values.append(value)
                Clock.schedule_once(lambda *_: accept_paths(values), 0)

            try:
                filechooser.open_file(
                    on_selection=selected,
                    filters=[("Bilder", "*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff", "*.heic", "*.heif", "*.avif")],
                    multiple=True,
                )
            except TypeError:
                try:
                    filechooser.open_file(on_selection=selected, filters=[("Bilder", "*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff", "*.heic", "*.heif", "*.avif")])
                except Exception as exc:
                    self.show_error("Galerie nicht verfügbar", str(exc))
            except Exception as exc:
                self.show_error("Galerie nicht verfügbar", str(exc))

        try:
            if platform == "android":
                started = start_android_multi_image_picker(
                    self.user_data_dir,
                    lambda paths: Clock.schedule_once(lambda *_: accept_paths(paths), 0),
                    lambda msg: Clock.schedule_once(lambda *_: fallback_picker(msg), 0),
                )
                if started:
                    return
            fallback_picker("Android Photo Picker konnte nicht gestartet werden.")
        except Exception as exc:
            fallback_picker(str(exc))

    def open_camera_scanner(self):
        """Vollflächiger Live-Scanner v11.2.3 mit automatischer Erkennung.

        - Die Live-Fläche füllt den verfügbaren Bildschirm responsiv für Smartphones
          und Tablets.
        - Manuelle Textfelder sowie große Buttonleisten entfallen.
        - Karten werden automatisch gesucht; Treffer erscheinen unten links im
          kompakten auto_scan_result_panel mit + / - Aktionen.
        - Ein bubble_source_menu kann direkt im Screen oder durch erneutes Tippen
          auf den Scan-Reiter geöffnet werden.
        - Oben rechts wird der neutrale Android-Gerätename angezeigt.
        """
        set_android_screen_orientation("unspecified")

        last_photo_path = getattr(self, "last_scan_photo", "") or ""
        adjusted_photo_path = ""
        photo_image = None
        photo_scatter = None
        photo_clip = None
        guide_line = None
        center_line = None
        grid_lines = []
        live_fit_callback = {"callback": None}
        photo_fit_callback = {"callback": None}
        live_camera_ref = {"widget": None}
        live_frame_ref = {"widget": None}
        live_clip_ref = {"widget": None}
        auto_scan_event = {"event": None}
        scan_state = {
            "busy": False,
            "token": 0,
            "result": None,
            "alternatives": [],
            "source": "live",
            "status": "Automatische Erkennung aktiv",
        }
        source_menu_state = {"open": False}

        profile = self.current_ui_profile()
        compact_scanner = profile.get("device_class") == "compact_phone"
        is_tablet = bool(profile.get("is_tablet"))
        device_name = self.get_android_device_display_name()

        def scanner_metrics():
            current = self.current_ui_profile()
            safe = current.get("safe", {})
            usable_w = max(dp(240), self.usable_content_width())
            usable_h = max(dp(320), Window.height - float(safe.get("top", 0)) - float(safe.get("bottom", 0)) - dp(10))
            compact = current.get("device_class") == "compact_phone"
            tablet = bool(current.get("is_tablet"))
            pad = dp(6 if compact else (10 if not tablet else 12))
            bubble_h = dp(48 if compact else 52)
            result_w = min(max(dp(250), usable_w * (0.76 if compact else 0.56)), dp(420 if not tablet else 520))
            result_h = dp(114 if compact else 128)
            device_w = min(max(dp(128), usable_w * 0.28), dp(320 if tablet else 250))
            chip_w = dp(116 if compact else 124)
            source_bubble_w = dp(126 if compact else 138)
            return {
                "pad": pad,
                "usable_w": usable_w,
                "usable_h": usable_h,
                "bubble_h": bubble_h,
                "result_w": result_w,
                "result_h": result_h,
                "device_w": device_w,
                "chip_w": chip_w,
                "source_bubble_w": source_bubble_w,
                "compact": compact,
                "tablet": tablet,
            }

        metrics = scanner_metrics()

        content = SurfaceBox(
            orientation="vertical",
            padding=metrics["pad"],
            spacing=0,
            bg_color=DARK_BG,
            border_color=(0, 0, 0, 0),
            radius=0,
            size_hint=(1, 1),
        )

        scanner_fullscreen_layout = FloatLayout(size_hint=(1, 1))
        content.add_widget(scanner_fullscreen_layout)

        camera_holder = SurfaceBox(
            orientation="vertical",
            size_hint=(1, 1),
            padding=dp(3),
            bg_color=(0.008, 0.012, 0.022, 1),
            border_color=tuple(list(GOLD[:3]) + [0.42]),
            radius=dp(24),
            elevation=1,
        )
        scanner_fullscreen_layout.add_widget(camera_holder)

        stage_top_left = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            height=dp(42),
            width=dp(252 if metrics["compact"] else 272),
            spacing=dp(8),
            pos_hint={"x": 0.02, "top": 0.985},
        )
        source_mode_chip = ModernChip("Live", "scan", active=True, accent=SUCCESS, size_hint=(None, None))
        source_mode_chip.width = metrics["chip_w"]
        source_mode_chip.height = dp(40)
        scan_stage_chip = ModernChip("Auto-Scan", "search", active=True, accent=ACCENT, size_hint=(None, None))
        scan_stage_chip.width = metrics["chip_w"]
        scan_stage_chip.height = dp(40)
        stage_top_left.add_widget(source_mode_chip)
        stage_top_left.add_widget(scan_stage_chip)
        scanner_fullscreen_layout.add_widget(stage_top_left)

        device_chip = SurfaceBox(
            orientation="horizontal",
            size_hint=(None, None),
            width=metrics["device_w"],
            height=dp(42),
            spacing=dp(6),
            padding=(dp(10), dp(5)),
            bg_color=tuple(list(ACCENT_2[:3]) + [0.40]),
            border_color=tuple(list(ACCENT[:3]) + [0.32]),
            radius=dp(21),
            pos_hint={"right": 0.98, "top": 0.985},
        )
        device_chip.add_widget(Image(source=ui_asset("diagnostics"), size_hint=(None, 1), width=dp(18), allow_stretch=True, keep_ratio=True, opacity=0.82))
        device_chip_label = DarkLabel(
            text=f"[b]{html_escape(short_text(device_name, 28))}[/b]",
            markup=True,
            color=TEXT,
            halign="center",
            font_size=ui_font_px(10.8 if metrics["compact"] else 11.4, body=True),
        )
        device_chip.add_widget(device_chip_label)
        scanner_fullscreen_layout.add_widget(device_chip)

        auto_scan_result_panel = SurfaceBox(
            orientation="horizontal",
            size_hint=(None, None),
            width=metrics["result_w"],
            height=metrics["result_h"],
            spacing=dp(8),
            padding=dp(8),
            bg_color=tuple(list(PANEL_BG[:3]) + [0.96]),
            border_color=tuple(list(ACCENT[:3]) + [0.24]),
            radius=dp(22),
            elevation=2,
            pos_hint={"x": 0.02, "y": 0.02},
            opacity=0,
            disabled=True,
        )
        result_thumb_box = SurfaceBox(
            orientation="vertical",
            size_hint=(None, None),
            width=dp(72 if metrics["compact"] else 82),
            height=dp(98 if metrics["compact"] else 112),
            padding=dp(4),
            bg_color=INPUT_BG,
            border_color=tuple(list(GOLD[:3]) + [0.22]),
            radius=dp(16),
        )
        result_thumb = AsyncImage(allow_stretch=True, keep_ratio=True, opacity=1)
        result_thumb_box.add_widget(result_thumb)
        auto_scan_result_panel.add_widget(result_thumb_box)

        result_info = BoxLayout(orientation="vertical", spacing=dp(1), size_hint=(1, 1))
        result_title = DarkLabel(text="", markup=True, color=TEXT, halign="left", font_size=ui_font_px(13.4 if metrics["compact"] else 14.0), size_hint_y=None, height=dp(30))
        result_meta = DarkLabel(text="", color=MUTED, halign="left", font_size=ui_font_px(10.0 if metrics["compact"] else 10.6, body=True), size_hint_y=None, height=dp(24))
        result_detail = DarkLabel(text="", color=TEXT, halign="left", font_size=ui_font_px(9.8 if metrics["compact"] else 10.2, body=True))
        result_info.add_widget(result_title)
        result_info.add_widget(result_meta)
        result_info.add_widget(result_detail)
        auto_scan_result_panel.add_widget(result_info)

        result_actions = BoxLayout(orientation="vertical", size_hint=(None, 1), width=dp(58 if metrics["compact"] else 64), spacing=dp(8))
        accept_btn = DarkButton(text="+", bg=SUCCESS, bold=True, radius=dp(18), size_hint=(1, 0.5))
        reject_btn = DarkButton(text="−", bg=DANGER, bold=True, radius=dp(18), size_hint=(1, 0.5))
        result_actions.add_widget(accept_btn)
        result_actions.add_widget(reject_btn)
        auto_scan_result_panel.add_widget(result_actions)
        scanner_fullscreen_layout.add_widget(auto_scan_result_panel)

        source_menu_anchor = FloatLayout(size_hint=(1, 1))
        scanner_fullscreen_layout.add_widget(source_menu_anchor)
        source_menu_live_bubble = DarkButton(
            text="Live",
            bg=ACCENT_2,
            radius=dp(24),
            size_hint=(None, None),
            width=metrics["source_bubble_w"],
            height=metrics["bubble_h"],
            pos_hint={"right": 0.98, "y": 0.22},
            opacity=0,
            disabled=True,
        )
        source_menu_camera_bubble = DarkButton(
            text="Kamera",
            bg=ACCENT,
            radius=dp(24),
            size_hint=(None, None),
            width=metrics["source_bubble_w"],
            height=metrics["bubble_h"],
            pos_hint={"right": 0.98, "y": 0.14},
            opacity=0,
            disabled=True,
        )
        source_menu_gallery_bubble = DarkButton(
            text="Galerie",
            bg=GOLD,
            radius=dp(24),
            size_hint=(None, None),
            width=metrics["source_bubble_w"],
            height=metrics["bubble_h"],
            pos_hint={"right": 0.98, "y": 0.06},
            opacity=0,
            disabled=True,
        )
        bubble_source_menu = DarkButton(
            text="Quellen",
            bg=tuple(list(ACCENT[:3]) + [1]),
            radius=dp(26),
            size_hint=(None, None),
            width=metrics["source_bubble_w"],
            height=metrics["bubble_h"],
            pos_hint={"right": 0.98, "y": 0.02},
            bold=True,
        )
        for bubble in (source_menu_live_bubble, source_menu_camera_bubble, source_menu_gallery_bubble, bubble_source_menu):
            source_menu_anchor.add_widget(bubble)

        def set_stage_state(text, accent=None):
            label = str(text or "Bereit")
            scan_state["status"] = label
            self.set_status(label)
            try:
                scan_stage_chip.label.text = short_text(label, 18)
                scan_stage_chip.chip_accent = accent or scan_stage_chip.chip_accent
                scan_stage_chip.set_active(True)
            except Exception:
                pass

        def set_source_mode(label, accent=SUCCESS):
            scan_state["source"] = str(label or "live").lower()
            try:
                source_mode_chip.label.text = short_text(str(label or "Live"), 16)
                source_mode_chip.chip_accent = accent
                source_mode_chip.set_active(True)
            except Exception:
                pass

        def show_result_panel(best, quality=None):
            card = (best or {}).get("card") or {}
            set_item = (best or {}).get("set_item") or {}
            title = str(card.get("name") or "Unbekannte Karte")
            set_code = str(set_item.get("set_code") or set_item.get("code") or "-")
            rarity = str(set_item.get("set_rarity") or set_item.get("rarity") or "-")
            language = str((best or {}).get("language_label") or scan_language_label(language_code_from_set_code(set_code) or "de"))
            confidence = int(float((best or {}).get("confidence") or 0))
            collection_preview = apply_collection_set_to_card(card, set_item or {})
            already_have = collection_count_for(self.collection, collection_preview)
            result_title.text = f"[b]{html_escape(short_text(title, 38))}[/b]"
            result_meta.text = f"{html_escape(display_card_type(card.get('type', '')))} • {html_escape(set_code)}"
            detail_line = f"{html_escape(rarity)} • {html_escape(language)} • {confidence} % Treffer"
            if quality:
                detail_line += f"\nBildqualität: {int(quality.get('score') or 0)} • In Sammlung: {already_have}"
            else:
                detail_line += f"\nIn Sammlung: {already_have}"
            result_detail.text = detail_line
            image_url = get_image_url(card)
            result_thumb.source = image_url or ""
            try:
                result_thumb.reload()
            except Exception:
                pass
            auto_scan_result_panel.opacity = 1
            auto_scan_result_panel.disabled = False
            set_stage_state(f"Treffer: {title}", SUCCESS)

        def hide_result_panel(reset_text=True):
            auto_scan_result_panel.opacity = 0
            auto_scan_result_panel.disabled = True
            result_title.text = ""
            result_meta.text = ""
            result_detail.text = ""
            result_thumb.source = ""
            if reset_text:
                set_stage_state("Automatische Erkennung aktiv", ACCENT)

        def cancel_auto_scan():
            event = auto_scan_event.get("event")
            if event is not None:
                try:
                    event.cancel()
                except Exception:
                    pass
            auto_scan_event["event"] = None

        def schedule_auto_scan(delay=0.8):
            cancel_auto_scan()
            if getattr(self, "_current_section", "") != "scanner":
                return
            if scan_state.get("busy") or scan_state.get("result") is not None:
                return
            auto_scan_event["event"] = Clock.schedule_once(start_auto_scan, max(0.12, float(delay or 0)))

        def export_adjusted_frame():
            nonlocal adjusted_photo_path
            if photo_clip is None:
                return ""
            try:
                os.makedirs(self.user_data_dir, exist_ok=True)
                adjusted_photo_path = os.path.join(self.user_data_dir, f"scan_frame_{time.strftime('%Y%m%d_%H%M%S')}.png")
                photo_clip.export_to_png(adjusted_photo_path)
                self.last_scan_photo = adjusted_photo_path
                return adjusted_photo_path
            except Exception:
                return last_photo_path if last_photo_path and os.path.exists(last_photo_path) else ""

        def export_live_frame():
            live_outer = live_frame_ref.get("widget")
            if live_outer is None:
                return ""
            try:
                os.makedirs(self.user_data_dir, exist_ok=True)
                live_path = os.path.join(self.user_data_dir, f"scan_live_{time.strftime('%Y%m%d_%H%M%S')}.png")
                live_outer.export_to_png(live_path)
                if live_path and os.path.exists(live_path) and os.path.getsize(live_path) > 0:
                    return live_path
            except Exception:
                return ""
            return ""

        def set_photo_message(message, error=False):
            camera_holder.clear_widgets()
            message_wrap = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(8))
            message_wrap.add_widget(Image(
                source=ui_asset("diagnostics" if error else "scan"),
                size_hint_y=None, height=dp(58), allow_stretch=True, keep_ratio=True,
                opacity=0.86,
            ))
            message_wrap.add_widget(AutoHeightLabel(
                text=message,
                markup=True,
                color=(1, 0.72, 0.74, 1) if error else MUTED,
                halign="center",
                min_height=dp(80),
                font_size=ui_font_px(11.6, body=True),
            ))
            camera_holder.add_widget(message_wrap)
            set_stage_state("Live nicht verfügbar" if error else "Bereit", DANGER if error else ACCENT)

        def build_photo_frame(path):
            nonlocal photo_image, photo_scatter, photo_clip, guide_line, center_line, grid_lines
            try:
                camera_holder.clear_widgets()
                outer = FloatLayout(size_hint=(1, 1))
                photo_clip = StencilView(size_hint=(None, None))
                photo_scatter = ScatterLayout(
                    size_hint=(None, None),
                    do_translation=True,
                    do_rotation=False,
                    do_scale=True,
                    auto_bring_to_front=False,
                )
                photo_image = Image(source=path, allow_stretch=True, keep_ratio=True, size_hint=(None, None))
                photo_scatter.add_widget(photo_image)
                photo_clip.add_widget(photo_scatter)
                outer.add_widget(photo_clip)

                with outer.canvas.after:
                    Color(0.91, 0.72, 0.26, 0.90)
                    guide_line = Line(width=1.35)
                    center_line = Line(width=0.85)
                    grid_lines = [Line(width=0.65) for _ in range(4)]

                def fit_photo_frame(*_):
                    if not outer.width or not outer.height:
                        return
                    fw = max(1, outer.width)
                    fh = max(1, outer.height)
                    ox, oy = outer.pos
                    photo_clip.size = (fw, fh)
                    photo_clip.pos = (ox, oy)
                    photo_scatter.size = (fw, fh)
                    if not getattr(photo_scatter, "_just_incard_initialized", False):
                        photo_scatter.pos = (ox, oy)
                        photo_scatter.center = (ox + fw / 2.0, oy + fh / 2.0)
                        photo_scatter.scale = 1.0
                        photo_scatter._just_incard_initialized = True
                    photo_image.size = (fw, fh)
                    photo_image.pos = (0, 0)
                    try:
                        photo_image.keep_ratio = True
                        photo_image.allow_stretch = True
                        if hasattr(photo_image, "fit_mode"):
                            photo_image.fit_mode = "contain"
                    except Exception:
                        pass
                    try:
                        center_line.points = []
                        for gl in grid_lines:
                            gl.points = []
                    except Exception:
                        pass
                    rel_x, rel_y, card_w, card_h = card_frame_geometry_v110(
                        fw, fh, margin_ratio=0.055, minimum_margin=dp(8),
                        maximum_width_ratio=0.92, maximum_height_ratio=0.94,
                    )
                    card_x = ox + rel_x
                    card_y = oy + rel_y
                    guide_line.rounded_rectangle = (card_x, card_y, card_w, card_h, dp(16))
                    title_y_bot = card_y + card_h - card_h * 0.105
                    picture_y_bot = title_y_bot - card_h * 0.39
                    inset = max(dp(10), card_w * 0.06)
                    center_line.points = [card_x + inset, picture_y_bot, card_x + card_w - inset, picture_y_bot]
                    corner = min(card_w, card_h) * 0.10
                    if grid_lines:
                        grid_lines[0].points = [card_x + corner, card_y, card_x, card_y, card_x, card_y + corner]
                        grid_lines[1].points = [card_x + card_w - corner, card_y, card_x + card_w, card_y, card_x + card_w, card_y + corner]
                        grid_lines[2].points = [card_x, card_y + card_h - corner, card_x, card_y + card_h, card_x + corner, card_y + card_h]
                        grid_lines[3].points = [card_x + card_w - corner, card_y + card_h, card_x + card_w, card_y + card_h, card_x + card_w, card_y + card_h - corner]

                photo_fit_callback["callback"] = fit_photo_frame
                outer.bind(size=fit_photo_frame, pos=fit_photo_frame)
                Clock.schedule_once(lambda *_: fit_photo_frame(), 0)
                camera_holder.add_widget(outer)
                set_source_mode("Foto", GOLD)
                set_stage_state("Foto geladen", GOLD)
                return True
            except Exception as exc:
                set_photo_message(f"[b]Foto konnte nicht angezeigt werden[/b]\n\n{exc}", error=True)
                return False

        def stop_live_preview():
            try:
                cam = live_camera_ref.get("widget")
                if cam is not None:
                    cam.play = False
            except Exception:
                pass
            live_camera_ref["widget"] = None
            live_frame_ref["widget"] = None
            live_clip_ref["widget"] = None
            live_fit_callback["callback"] = None

        def pause_live_preview():
            try:
                cam = live_camera_ref.get("widget")
                if cam is not None:
                    cam.play = False
            except Exception:
                pass

        def resume_live_preview(*_):
            if getattr(self, "_current_section", "") != "scanner":
                return False
            try:
                cam = live_camera_ref.get("widget")
                frame = live_frame_ref.get("widget")
                if cam is not None and frame is not None and frame.parent is not None:
                    cam.play = True
                    set_stage_state("Live-Vorschau fortgesetzt", SUCCESS)
                    return True
            except Exception:
                pass
            return build_live_preview()

        self._scanner_resume_callback = resume_live_preview

        def build_live_preview(*_):
            nonlocal guide_line, center_line, grid_lines
            try:
                if Camera is None:
                    set_photo_message("[b]Live-Kamera nicht verfügbar[/b]\n\nNutze Kamera oder Galerie.", error=True)
                    return False
                stop_live_preview()
                camera_holder.clear_widgets()
                outer = FloatLayout(size_hint=(1, 1))
                camera_clip = StencilView(size_hint=(None, None))
                outer.add_widget(camera_clip)
                cam_scatter = ScatterLayout(
                    do_translation=False,
                    do_rotation=False,
                    do_scale=False,
                    size_hint=(None, None),
                    auto_bring_to_front=False,
                )
                cam_scatter.rotation = compute_live_camera_rotation(getattr(self, "camera_rotation", 270))
                cam = Camera(
                    play=True,
                    resolution=(640, 480),
                    allow_stretch=True,
                    keep_ratio=False,
                    size_hint=(None, None),
                )
                if hasattr(cam, "fit_mode"):
                    try:
                        cam.fit_mode = "cover"
                    except Exception:
                        pass
                cam_scatter.add_widget(cam)
                camera_clip.add_widget(cam_scatter)
                live_camera_ref["widget"] = cam
                live_frame_ref["widget"] = camera_clip
                live_clip_ref["widget"] = camera_clip

                with outer.canvas.after:
                    Color(0.91, 0.72, 0.26, 0.90)
                    guide_line = Line(width=1.35)
                    center_line = Line(width=0.85)
                    grid_lines = [Line(width=0.65) for _ in range(4)]

                def fit_live_frame(*__):
                    fw = max(1, outer.width)
                    fh = max(1, outer.height)
                    ox, oy = outer.pos
                    rel_x, rel_y, card_w, card_h = card_frame_geometry_v110(
                        fw, fh, margin_ratio=0.045, minimum_margin=dp(7),
                        maximum_width_ratio=0.94, maximum_height_ratio=0.96,
                    )
                    card_x = ox + rel_x
                    card_y = oy + rel_y
                    camera_clip.size = (card_w, card_h)
                    camera_clip.pos = (card_x, card_y)
                    cam_scatter.size = (card_w, card_h)
                    cam_scatter.pos = (card_x, card_y)
                    cam_scatter.center = (card_x + card_w / 2.0, card_y + card_h / 2.0)
                    cam_scatter.rotation = compute_live_camera_rotation(getattr(self, "camera_rotation", 270))
                    rotation = int(getattr(cam_scatter, "rotation", 0)) % 360
                    src_w = src_h = 0
                    tex = getattr(cam, "texture", None)
                    if tex is not None:
                        try:
                            src_w, src_h = map(float, tex.size)
                        except Exception:
                            src_w = src_h = 0
                    if not src_w or not src_h:
                        try:
                            src_w, src_h = map(float, getattr(cam, "resolution", (640, 480)))
                        except Exception:
                            src_w, src_h = 640.0, 480.0
                    cam_x, cam_y, cam_w, cam_h = cover_geometry_v110(
                        src_w, src_h, card_w, card_h, rotated=rotation in (90, 270)
                    )
                    cam.size = (cam_w, cam_h)
                    cam.pos = (cam_x, cam_y)
                    guide_line.rounded_rectangle = (card_x, card_y, card_w, card_h, dp(18))
                    picture_y_bot = card_y + card_h * 0.50
                    inset = max(dp(10), card_w * 0.06)
                    center_line.points = [card_x + inset, picture_y_bot, card_x + card_w - inset, picture_y_bot]
                    corner = min(card_w, card_h) * 0.10
                    if grid_lines:
                        grid_lines[0].points = [card_x + corner, card_y, card_x, card_y, card_x, card_y + corner]
                        grid_lines[1].points = [card_x + card_w - corner, card_y, card_x + card_w, card_y, card_x + card_w, card_y + corner]
                        grid_lines[2].points = [card_x, card_y + card_h - corner, card_x, card_y + card_h, card_x + corner, card_y + card_h]
                        grid_lines[3].points = [card_x + card_w - corner, card_y + card_h, card_x + card_w, card_y + card_h, card_x + card_w, card_y + card_h - corner]

                live_fit_callback["callback"] = fit_live_frame
                outer.bind(size=fit_live_frame, pos=fit_live_frame)
                try:
                    cam.bind(texture=fit_live_frame)
                except Exception:
                    pass
                Clock.schedule_once(fit_live_frame, 0)
                Clock.schedule_once(fit_live_frame, 0.15)
                camera_holder.add_widget(outer)
                set_source_mode("Live", SUCCESS)
                set_stage_state("Live-Vorschau aktiv", SUCCESS)
                return True
            except Exception as exc:
                set_photo_message("[b]Live-Kamera konnte nicht gestartet werden[/b]\n\n" + str(exc), error=True)
                return False

        def toggle_source_bubbles(force=None):
            open_state = (not source_menu_state["open"]) if force is None else bool(force)
            source_menu_state["open"] = open_state
            for bubble in (source_menu_live_bubble, source_menu_camera_bubble, source_menu_gallery_bubble):
                bubble.opacity = 1 if open_state else 0
                bubble.disabled = not open_state
            bubble_source_menu.text = "Schließen" if open_state else "Quellen"
            return open_state

        self._toggle_scanner_source_bubbles = toggle_source_bubbles

        def get_android_picture_dir():
            candidates = []
            if platform == "android":
                try:
                    from jnius import autoclass
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    Environment = autoclass("android.os.Environment")
                    activity = PythonActivity.mActivity
                    ext_dir = activity.getExternalFilesDir(Environment.DIRECTORY_PICTURES)
                    if ext_dir is not None:
                        candidates.append(str(ext_dir.getAbsolutePath()))
                except Exception:
                    pass
                candidates.append("/storage/emulated/0/Pictures/JustInCard")
            candidates.append(self.user_data_dir)
            for folder in candidates:
                try:
                    if not folder:
                        continue
                    os.makedirs(folder, exist_ok=True)
                    test = os.path.join(folder, ".write_test")
                    with open(test, "w", encoding="utf-8") as f:
                        f.write("ok")
                    try:
                        os.remove(test)
                    except Exception:
                        pass
                    return folder
                except Exception:
                    continue
            return self.user_data_dir

        def make_photo_path():
            folder = get_android_picture_dir()
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, f"scan_{time.strftime('%Y%m%d_%H%M%S')}.jpg")

        def copy_image_to_scanner_cache(source_path):
            try:
                if not source_path:
                    return ""
                os.makedirs(self.user_data_dir, exist_ok=True)
                target = os.path.join(self.user_data_dir, f"gallery_scan_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
                src = str(source_path)
                if src.startswith("content://") and platform == "android":
                    return copy_android_content_uri_to_file(src, self.user_data_dir, "gallery_scan")
                if os.path.exists(src) and os.path.getsize(src) > 0:
                    ext = os.path.splitext(src)[1].lower()
                    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                        ext = ".jpg"
                    target = os.path.join(self.user_data_dir, f"gallery_scan_{time.strftime('%Y%m%d_%H%M%S')}{ext}")
                    with open(src, "rb") as inp, open(target, "wb") as out:
                        out.write(inp.read())
                    return target
            except Exception:
                return ""
            return ""

        def find_latest_scan_photo(expected_path="", after_ts=0):
            candidates = []
            try:
                if expected_path:
                    candidates.append(expected_path)
                folders = [
                    get_android_picture_dir(),
                    self.user_data_dir,
                    "/storage/emulated/0/Pictures/JustInCard",
                    "/storage/emulated/0/DCIM/Camera",
                    "/storage/emulated/0/DCIM",
                    "/storage/emulated/0/Pictures",
                ]
                seen = set()
                for folder in folders:
                    if not folder or folder in seen or not os.path.isdir(folder):
                        continue
                    seen.add(folder)
                    try:
                        for name in os.listdir(folder):
                            lower = name.lower()
                            if lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
                                path = os.path.join(folder, name)
                                try:
                                    if os.path.getsize(path) <= 0:
                                        continue
                                    if lower.startswith("scan_") or os.path.getmtime(path) >= after_ts:
                                        candidates.append(path)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                existing = [p for p in candidates if p and os.path.exists(p) and os.path.getsize(p) > 0]
                if not existing:
                    return ""
                existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                return existing[0]
            except Exception:
                return ""

        def open_android_camera(*_):
            nonlocal last_photo_path
            toggle_source_bubbles(False)
            pause_live_preview()
            started_ts = time.time() - 2.0
            path = make_photo_path()
            set_stage_state("Native Kamera wird geöffnet", ACCENT)

            def accept_photo(final_path):
                nonlocal last_photo_path
                final_path = normalize_scanner_image_file(final_path, self.user_data_dir, "camera_scan")
                if not final_path or not os.path.exists(final_path) or os.path.getsize(final_path) <= 0:
                    self.show_error("Kein Foto", "Das Foto konnte nicht gelesen werden. Bitte erneut aufnehmen oder Galerie nutzen.")
                    resume_live_preview()
                    return
                last_photo_path = final_path
                self.last_scan_photo = final_path
                build_photo_frame(final_path)
                hide_result_panel(reset_text=False)
                schedule_auto_scan(0.35)

            def camera_error(message):
                recent = find_latest_scan_photo(path, started_ts)
                if recent:
                    accept_photo(recent)
                    return
                self.show_error(
                    "Kein Foto",
                    (message or "Die Android-Kamera hat kein Foto an die App zurückgegeben.")
                    + "\n\nNutze alternativ die Galerie, wenn das Bild in der Kamera-App gespeichert wurde."
                )
                Clock.schedule_once(resume_live_preview, 0.25)

            try:
                if platform == "android":
                    native_started = start_android_camerax_capture(
                        lambda final_path: Clock.schedule_once(lambda *_: accept_photo(final_path), 0),
                        lambda msg: Clock.schedule_once(lambda *_: camera_error(msg), 0),
                    )
                    if native_started:
                        return
                    started = start_android_camera_content_uri(
                        self.user_data_dir,
                        lambda final_path: Clock.schedule_once(lambda *_: accept_photo(final_path), 0),
                        lambda msg: Clock.schedule_once(lambda *_: camera_error(msg), 0),
                    )
                    if started:
                        return
                    thumb_started = start_android_camera_thumbnail(
                        self.user_data_dir,
                        lambda final_path: Clock.schedule_once(lambda *_: accept_photo(final_path), 0),
                        lambda msg: Clock.schedule_once(lambda *_: camera_error(msg), 0),
                    )
                    if thumb_started:
                        return
                    try:
                        from plyer import camera as plyer_camera
                    except Exception as exc:
                        camera_error("Kamera konnte nicht geladen werden: " + str(exc))
                        return
                    def _on_complete(filename):
                        def poll_for_photo(attempt=0):
                            try:
                                raw_path = filename or path
                                final_path = raw_path if raw_path and os.path.exists(raw_path) and os.path.getsize(raw_path) > 0 else find_latest_scan_photo(path, started_ts)
                                if final_path:
                                    accept_photo(final_path)
                                    return
                                if attempt < 18:
                                    Clock.schedule_once(lambda *__: poll_for_photo(attempt + 1), 0.35)
                                    return
                                camera_error("Die Android-Kamera hat kein Foto an die App zurückgegeben.")
                            except Exception as exc:
                                camera_error(str(exc))
                        Clock.schedule_once(lambda *__: poll_for_photo(0), 0.20)
                    disable_android_file_uri_exposure_guard()
                    plyer_camera.take_picture(filename=path, on_complete=_on_complete)
                else:
                    self.show_error("Nur Android", "Die native Kamera wird nur auf Android geöffnet. Nutze ein vorhandenes Bild oder den Live-Scan.")
            except Exception as exc:
                camera_error(str(exc))

        def open_bulk_gallery_images(*_):
            toggle_source_bubbles(False)
            pause_live_preview()
            try:
                set_stage_state("Galerie wird geöffnet", GOLD)

                def accept_bulk(paths):
                    clean_paths = []
                    for pth in paths or []:
                        try:
                            normalized = normalize_scanner_image_file(pth, self.user_data_dir, "gallery_bulk")
                            if normalized and os.path.exists(normalized) and os.path.getsize(normalized) > 0:
                                clean_paths.append(normalized)
                        except Exception:
                            continue
                    if not clean_paths:
                        self.show_error("Keine Bilder", "Es konnten keine lesbaren Bilder übernommen werden.")
                        Clock.schedule_once(resume_live_preview, 0.25)
                        return
                    self.set_status(f"Sammel-OCR läuft für {len(clean_paths)} Bild(er)...")
                    self.start_bulk_gallery_ocr_import(clean_paths)
                    Clock.schedule_once(resume_live_preview, 0.45)

                def picker_error(message):
                    try:
                        from plyer import filechooser
                    except Exception:
                        self.show_error("Mehrfach-Galerie nicht verfügbar", (message or "Galerie konnte nicht geöffnet werden."))
                        return

                    def _on_selection(selection):
                        try:
                            selected_paths = []
                            if selection:
                                if not isinstance(selection, (list, tuple)):
                                    selection = [selection]
                                for selected in selection:
                                    try:
                                        if hasattr(selected, "toString"):
                                            selected = str(selected.toString())
                                        else:
                                            selected = str(selected)
                                    except Exception:
                                        selected = str(selected)
                                    final_path = copy_image_to_scanner_cache(selected) or selected
                                    if final_path:
                                        selected_paths.append(final_path)
                            Clock.schedule_once(lambda *_: accept_bulk(selected_paths), 0)
                        except Exception as exc:
                            self.show_error("Mehrfach-Galerie fehlgeschlagen", str(exc))

                    try:
                        filechooser.open_file(on_selection=_on_selection, filters=[("Bilder", "*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff", "*.heic", "*.heif", "*.avif")], multiple=True)
                    except TypeError:
                        try:
                            filechooser.open_file(on_selection=_on_selection, filters=[("Bilder", "*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff", "*.heic", "*.heif", "*.avif")])
                        except Exception as exc:
                            self.show_error("Galerie konnte nicht geöffnet werden", str(exc))
                    except Exception as exc:
                        self.show_error("Galerie konnte nicht geöffnet werden", str(exc))

                if platform == "android":
                    started = start_android_multi_image_picker(
                        self.user_data_dir,
                        lambda paths: Clock.schedule_once(lambda *_: accept_bulk(paths), 0),
                        lambda msg: Clock.schedule_once(lambda *_: picker_error(msg), 0),
                    )
                    if started:
                        return
                picker_error("Android-Mehrfachauswahl konnte nicht gestartet werden.")
            except Exception as exc:
                self.show_error("Mehrfach-Galerie", str(exc))

        def choose_live(*_):
            toggle_source_bubbles(False)
            hide_result_panel(reset_text=False)
            scan_state["result"] = None
            scan_state["alternatives"] = []
            set_source_mode("Live", SUCCESS)
            ok = build_live_preview()
            if ok:
                schedule_auto_scan(0.55)
            return ok

        source_menu_live_bubble.bind(on_release=choose_live)
        source_menu_camera_bubble.bind(on_release=open_android_camera)
        source_menu_gallery_bubble.bind(on_release=open_bulk_gallery_images)
        bubble_source_menu.bind(on_release=lambda *_: toggle_source_bubbles())

        def start_auto_scan(*_):
            if getattr(self, "_current_section", "") != "scanner":
                return False
            if scan_state.get("busy") or scan_state.get("result") is not None:
                return False
            path = export_adjusted_frame() or export_live_frame()
            if not path:
                schedule_auto_scan(0.8)
                return False
            scan_state["busy"] = True
            scan_state["token"] += 1
            token = scan_state["token"]
            set_stage_state("Suche läuft", ACCENT)
            quality = self.analyze_scan_image_quality(path)
            current_config = self.scan_mode_config()
            deadline = ScanDeadlineV100.start(float(current_config.get("hard_timeout_seconds") or 10.0))

            def finalize(best=None, error="", alternatives=None):
                def on_ui(*_):
                    if token != scan_state.get("token"):
                        return
                    scan_state["busy"] = False
                    if best:
                        scan_state["result"] = best
                        scan_state["alternatives"] = alternatives or []
                        show_result_panel(best, quality=quality)
                    else:
                        scan_state["result"] = None
                        scan_state["alternatives"] = []
                        hide_result_panel(reset_text=False)
                        set_stage_state(error or "Keine Karte erkannt – erneuter Versuch", ACCENT)
                        schedule_auto_scan(0.95 if scan_state.get("source") == "live" else 1.25)
                Clock.schedule_once(on_ui, 0)

            def after_ocr(text, error=""):
                def resolve_worker():
                    best = None
                    alternatives = []
                    err = error or ""
                    try:
                        candidates = self.parse_scan_ocr_candidates(text or "")
                        best, _tried, alternatives = self._find_scan_matches_for_candidates(
                            candidates,
                            scan_path=path,
                            quality=quality,
                            include_artwork=True,
                            max_alternatives=3,
                            deadline_at=deadline.deadline_at,
                        )
                    except Exception as exc:
                        err = short_text(str(exc), 180)
                    finalize(best, err, alternatives)
                threading.Thread(target=resolve_worker, daemon=True).start()

            self.smart_ocr_scan_image(
                path,
                after_ocr,
                max_variant_images=int(current_config.get("guided_variants") or 0),
                deadline_at=deadline.deadline_at,
            )
            return True

        def accept_current_result(*_):
            best = scan_state.get("result") or {}
            card = best.get("card") or {}
            if not card:
                return
            set_item = best.get("set_item") or {}
            self.add_card(card, set_item=set_item, ask_set=False)
            name = str(card.get("name") or "Karte")
            hide_result_panel(reset_text=False)
            scan_state["result"] = None
            scan_state["alternatives"] = []
            set_stage_state(f"{name} hinzugefügt", SUCCESS)
            schedule_auto_scan(0.65)

        def reject_current_result(*_):
            hide_result_panel(reset_text=False)
            scan_state["result"] = None
            scan_state["alternatives"] = []
            set_stage_state("Treffer verworfen – neuer Versuch", ACCENT)
            schedule_auto_scan(0.35)

        accept_btn.bind(on_release=accept_current_result)
        reject_btn.bind(on_release=reject_current_result)

        popup = self.make_inline_page("scanner", content, back_to="search")

        def resize_scanner(*_):
            nonlocal metrics
            metrics = scanner_metrics()
            content.padding = metrics["pad"]
            auto_scan_result_panel.width = metrics["result_w"]
            auto_scan_result_panel.height = metrics["result_h"]
            device_chip.width = metrics["device_w"]
            source_mode_chip.width = metrics["chip_w"]
            scan_stage_chip.width = metrics["chip_w"]
            for bubble in (bubble_source_menu, source_menu_live_bubble, source_menu_camera_bubble, source_menu_gallery_bubble):
                bubble.width = metrics["source_bubble_w"]
                bubble.height = metrics["bubble_h"]
            stage_top_left.width = dp(252 if metrics["compact"] else 272)
            result_thumb_box.width = dp(72 if metrics["compact"] else 82)
            result_thumb_box.height = dp(98 if metrics["compact"] else 112)
            device_chip_label.font_size = ui_font_px(10.8 if metrics["compact"] else 11.4, body=True)
            result_title.font_size = ui_font_px(13.4 if metrics["compact"] else 14.0)
            result_meta.font_size = ui_font_px(10.0 if metrics["compact"] else 10.6, body=True)
            result_detail.font_size = ui_font_px(9.8 if metrics["compact"] else 10.2, body=True)
            try:
                callback = live_fit_callback.get("callback")
                if callable(callback):
                    callback()
            except Exception:
                pass
            try:
                callback = photo_fit_callback.get("callback")
                if callable(callback):
                    callback()
            except Exception:
                pass

        Window.bind(size=resize_scanner)

        def stop_and_restore(*_):
            cancel_auto_scan()
            self._scanner_resume_callback = None
            self._toggle_scanner_source_bubbles = None
            stop_live_preview()
            try:
                Window.unbind(size=resize_scanner)
            except Exception:
                pass
            Clock.schedule_once(lambda *__: set_android_screen_orientation("unspecified"), 0.25)

        popup.bind(on_dismiss=stop_and_restore)
        popup.open()
        Clock.schedule_once(lambda *_: choose_live(), 0.12)

    def set_scan_mode(self, mode, show_popup=True):
        """Live/Kamera bieten Schnell und Normal; Galerie ist immer Gründlich."""
        mode = str(mode or "normal").lower()
        if mode not in {"schnell", "normal"}:
            mode = "normal"
        self.scan_mode = mode
        self.save_settings()
        label = self.scan_mode_config(mode).get("label", mode.title())
        self.set_status(f"Scanmodus gesetzt: {label}")
        if show_popup:
            self.show_info(
                "Scanmodus",
                f"Live/Kamera verwenden jetzt: {label}.\n\nGalerieimporte laufen automatisch im gründlichen Präzisionsmodus.",
            )

    def open_scan_timing_popup(self, *_):
        """Zeigt Zielzeiten und reale Messwerte dieses Geräts pro Modus."""
        lines = [
            "Scanner-Zeiten pro einzelner Kartenfläche",
            "",
            "KI-Ensemble v11.2.3: " + model_stack_summary(),
            "",
            "Die Zielwerte gelten bei installierter lokaler Kartendatenbank. ",
            "Große/unscharfe Bilder und der erste Modellstart können länger dauern.",
            "",
        ]
        for mode in ("schnell", "normal"):
            config = self.scan_mode_config(mode)
            summary = self.scan_timings.summary(mode)
            lines.append(f"{config.get('label', mode.title())}: {mode_timing_text(mode, summary)}")
            lines.append(f"  {config.get('description', '')}")
            if summary.get("samples"):
                lines.append(f"  Erfolgsquote auf diesem Gerät: {float(summary.get('success_rate') or 0):.1f} %")
            lines.append("")
        gallery = gallery_scan_profile()
        gallery_summary = self.scan_timings.summary(GALLERY_SCAN_MODE)
        lines.append(f"Galerie – Gründlich: Ziel {gallery['target_min_seconds']:.0f}–{gallery['target_max_seconds']:.0f} s • Abbruchgrenze {gallery['hard_timeout_seconds']:.0f} s")
        lines.append("  Immer aktiv für Galerieimporte; inklusive Farbkanal-, Effekt- und Artwork-Abgleich.")
        if gallery_summary.get("samples"):
            lines.append(f"  Erfolgsquote auf diesem Gerät: {float(gallery_summary.get('success_rate') or 0):.1f} %")
        lines.append("")
        self.show_scroll_text("Scanner-Zeiten", "\n".join(lines))

    def scan_mode_config(self, mode=None):
        """Liefert echte, voneinander abweichende Scannerprofile mit Zeitbudget.

        Die Abbruchgrenze begrenzt neue OCR-/Suchschritte. Bereits laufende native
        ML-Kit-Aufgaben können nicht hart unterbrochen werden, aber es werden danach
        keine weiteren teuren Varianten oder Sprachen gestartet.
        """
        requested_mode = str(mode or getattr(self, "scan_mode", "normal")).lower()
        gallery_active = bool(getattr(self, "_gallery_scan_active", False)) or requested_mode in {"gallery", "galerie"}
        mode = GALLERY_SCAN_MODE if gallery_active else requested_mode
        config = gallery_scan_profile() if gallery_active else scan_mode_profile(mode)
        try:
            profile = self.current_ui_profile()
            device_class = profile.get("device_class", "phone")
            if device_class == "compact_phone":
                config["max_image_edge"] = 1280
                config["guided_variants"] = min(int(config.get("guided_variants") or 0), 1)
            elif device_class in {"phone", "large_phone"}:
                config["max_image_edge"] = 1600
            elif device_class == "tablet":
                config["max_image_edge"] = 1900
            else:
                config["max_image_edge"] = 2100
            config["device_class"] = device_class
        except Exception:
            config["max_image_edge"] = 1600
            config["device_class"] = "phone"
        try:
            selected_mode = str(getattr(self, "performance_mode", "auto") or "auto")
            if selected_mode == "auto":
                selected_mode = recommend_performance_mode(self.current_ui_profile())
            perf = PERFORMANCE_MODES_V93.get(selected_mode, PERFORMANCE_MODES_V93["balanced"])
            config["performance_mode"] = perf.key
            config["performance_label"] = perf.title
            config["max_image_edge"] = min(int(config.get("max_image_edge") or perf.max_scan_side), int(perf.max_scan_side))
            config["concurrent_preparation"] = max(1, min(2, int(perf.concurrent_preparation)))
            config["animations"] = bool(perf.animations)
            config["preview_cache_items"] = int(perf.preview_cache_items)
            if not perf.artwork_compare:
                config["artwork"] = False
                config["artwork_candidates"] = 0
        except Exception:
            config["performance_mode"] = "balanced"
            config["performance_label"] = "Ausgewogen"
        return config

    def analyze_scan_image_quality(self, path, card_coverage=1.0):
        """Bewertet Helligkeit, Kontrast, Schärfe, Spiegelung und Kartengröße."""
        result = {
            "score": 0,
            "label": "Nicht prüfbar",
            "brightness": 0,
            "contrast": 0,
            "sharpness": 0,
            "glare": 0,
            "darkness": 0,
            "card_coverage": float(card_coverage or 0),
            "warnings": [],
        }
        try:
            from PIL import Image as PILImage, ImageOps, ImageFilter, ImageStat
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            gray = ImageOps.grayscale(image)
            gray.thumbnail((512, 512))
            stat = ImageStat.Stat(gray)
            brightness = float(stat.mean[0] if stat.mean else 0)
            contrast = float(stat.stddev[0] if stat.stddev else 0)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            sharpness = float(edge_stat.mean[0] if edge_stat.mean else 0)
            hist = gray.histogram()
            pixels = max(1, sum(hist))
            glare = 100.0 * sum(hist[245:]) / pixels
            darkness = 100.0 * sum(hist[:28]) / pixels

            brightness_score = max(0.0, 100.0 - abs(brightness - 142.0) * 0.75)
            contrast_score = min(100.0, contrast * 2.3)
            sharpness_score = min(100.0, sharpness * 4.2)
            glare_score = max(0.0, 100.0 - glare * 5.5)
            darkness_score = max(0.0, 100.0 - darkness * 4.2)
            coverage_score = min(100.0, max(0.0, float(card_coverage or 0) * 135.0))
            score = int(round(
                brightness_score * 0.20
                + contrast_score * 0.22
                + sharpness_score * 0.28
                + glare_score * 0.12
                + darkness_score * 0.08
                + coverage_score * 0.10
            ))
            score = max(0, min(100, score))
            warnings = []
            if brightness < 72:
                warnings.append("Bild zu dunkel")
            elif brightness > 225:
                warnings.append("Bild zu hell")
            if contrast < 24:
                warnings.append("zu wenig Kontrast")
            if sharpness < 8.5:
                warnings.append("Bild möglicherweise unscharf")
            if glare > 9:
                warnings.append("starke Spiegelung")
            if darkness > 18:
                warnings.append("große dunkle Bereiche")
            if float(card_coverage or 0) < 0.20:
                warnings.append("Karte ist im Bild sehr klein")
            label = "Sehr gut" if score >= 82 else "Gut" if score >= 67 else "Mittel" if score >= 48 else "Schlecht"
            result.update({
                "score": score,
                "label": label,
                "brightness": round(brightness, 1),
                "contrast": round(contrast, 1),
                "sharpness": round(sharpness, 1),
                "glare": round(glare, 1),
                "darkness": round(darkness, 1),
                "warnings": warnings,
            })
        except Exception as exc:
            result["warnings"] = [f"Qualitätsprüfung fehlgeschlagen: {exc}"]
        return result

    def _scan_connected_components(self, binary_image, max_components=30):
        """Kleine Connected-Component-Suche auf einer stark verkleinerten Maske."""
        try:
            w, h = binary_image.size
            pix = binary_image.load()
            visited = bytearray(w * h)
            components = []
            neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))
            for y in range(h):
                for x in range(w):
                    idx = y * w + x
                    if visited[idx] or pix[x, y] == 0:
                        continue
                    stack = [(x, y)]
                    visited[idx] = 1
                    minx = maxx = x
                    miny = maxy = y
                    count = 0
                    while stack:
                        cx, cy = stack.pop()
                        count += 1
                        minx = min(minx, cx)
                        maxx = max(maxx, cx)
                        miny = min(miny, cy)
                        maxy = max(maxy, cy)
                        for dx, dy in neighbors:
                            nx, ny = cx + dx, cy + dy
                            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                                continue
                            nidx = ny * w + nx
                            if visited[nidx] or pix[nx, ny] == 0:
                                continue
                            visited[nidx] = 1
                            stack.append((nx, ny))
                    if count > 8:
                        components.append((count, (minx, miny, maxx + 1, maxy + 1)))
            components.sort(key=lambda item: item[0], reverse=True)
            return components[: int(max_components or 30)]
        except Exception:
            return []

    def _scan_bbox_iou(self, a, b):
        try:
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            ix1, iy1 = max(ax1, bx1), max(ay1, by1)
            ix2, iy2 = min(ax2, bx2), min(ay2, by2)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
            area_b = max(1, (bx2 - bx1) * (by2 - by1))
            return inter / float(area_a + area_b - inter)
        except Exception:
            return 0.0

    def _detect_card_regions_v109_legacy(self, path, max_cards=64):
        """Erkennt getrennte Kartenflächen über YOLO, OpenCV und Pillow-Fallback.

        Jede Region bleibt an das Quellbild gebunden. YOLO/OpenCV werden nur als
        Lokalisierer verwendet; die eigentliche Kartenidentität wird danach für
        jede Region separat über Set-Code, Passcode, Metadaten, Artwork und Effekt
        bestimmt.
        """
        regions = []
        native_boxes = []
        try:
            model_path = os.path.join(os.path.dirname(__file__), "models", "yolo_card_detector.onnx")
            if os.path.isfile(model_path):
                native_boxes.extend(native_yolo_regions(path, model_path) or [])
        except Exception:
            pass
        try:
            native_boxes.extend(native_detect_card_regions(path) or [])
        except Exception:
            pass
        if native_boxes:
            selected = []
            for raw in sorted(native_boxes, key=lambda item: float(item.get("confidence") or 0.0), reverse=True):
                try:
                    x = int(raw.get("x") or 0); y = int(raw.get("y") or 0)
                    w = int(raw.get("width") or 0); h = int(raw.get("height") or 0)
                    if w < 32 or h < 48:
                        continue
                    bbox = (x, y, x + w, y + h)
                    if any(self._scan_bbox_iou(bbox, existing["bbox"]) > 0.62 for existing in selected):
                        continue
                    selected.append({
                        "bbox": bbox,
                        "coverage": 0.0,
                        "index": len(selected) + 1,
                        "portrait": h >= w,
                        "detector": str(raw.get("engine") or "native-ai"),
                        "detector_confidence": float(raw.get("confidence") or 0.0),
                    })
                    if len(selected) >= int(max_cards or 64):
                        break
                except Exception:
                    continue
            if selected:
                return selected
        try:
            from PIL import Image as PILImage, ImageOps, ImageFilter, ImageStat
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            ow, oh = image.size
            if ow < 60 or oh < 60:
                return regions
            work = ImageOps.grayscale(image)
            scale = min(1.0, 900.0 / max(ow, oh))
            if scale < 1.0:
                work = work.resize((max(1, int(ow * scale)), max(1, int(oh * scale))))
            work = ImageOps.autocontrast(work)
            edge = work.filter(ImageFilter.FIND_EDGES)
            stats = ImageStat.Stat(edge)
            mean = float(stats.mean[0] if stats.mean else 0)
            std = float(stats.stddev[0] if stats.stddev else 0)
            threshold = int(max(24, min(165, mean + std * 0.72)))
            mask = edge.point(lambda v: 255 if v >= threshold else 0, mode="1")
            mask = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(5))
            mw, mh = mask.size
            small_scale = min(1.0, 300.0 / max(mw, mh))
            if small_scale < 1.0:
                mask = mask.resize((max(1, int(mw * small_scale)), max(1, int(mh * small_scale))))
            sw, sh = mask.size
            components = self._scan_connected_components(mask, max_components=60)
            image_area = float(sw * sh)
            raw_boxes = []
            for count, box in components:
                x1, y1, x2, y2 = box
                bw, bh = x2 - x1, y2 - y1
                area = bw * bh
                if area < image_area * 0.018 or area > image_area * 0.94:
                    continue
                ratio = bw / float(max(1, bh))
                portrait_ok = 0.46 <= ratio <= 0.88
                landscape_ok = 1.14 <= ratio <= 2.17
                if not (portrait_ok or landscape_ok):
                    continue
                fill = count / float(max(1, area))
                if fill < 0.025:
                    continue
                # Rand etwas erweitern, damit Kartenrahmen nicht abgeschnitten wird.
                pad_x = int(bw * 0.06)
                pad_y = int(bh * 0.04)
                x1 = max(0, x1 - pad_x)
                y1 = max(0, y1 - pad_y)
                x2 = min(sw, x2 + pad_x)
                y2 = min(sh, y2 + pad_y)
                raw_boxes.append((area, (x1, y1, x2, y2)))
            raw_boxes.sort(key=lambda item: item[0], reverse=True)
            chosen = []
            for area, box in raw_boxes:
                if any(self._scan_bbox_iou(box, existing) > 0.58 for existing in chosen):
                    continue
                chosen.append(box)
                if len(chosen) >= int(max_cards or 12):
                    break
            scale_x = ow / float(sw)
            scale_y = oh / float(sh)
            for index, box in enumerate(chosen):
                x1, y1, x2, y2 = box
                obox = (
                    max(0, int(x1 * scale_x)),
                    max(0, int(y1 * scale_y)),
                    min(ow, int(x2 * scale_x)),
                    min(oh, int(y2 * scale_y)),
                )
                bw, bh = obox[2] - obox[0], obox[3] - obox[1]
                coverage = (bw * bh) / float(max(1, ow * oh))
                regions.append({
                    "bbox": obox,
                    "coverage": coverage,
                    "index": index + 1,
                    "portrait": bh >= bw,
                })
        except Exception:
            return []
        return regions

    def _python_opencv_card_regions_v1093(self, path, max_cards=64):
        """Optionale OpenCV-Konturerkennung als zusätzlicher Galerie-Detektor."""
        output = []
        try:
            import cv2
            image = cv2.imread(str(path))
            if image is None:
                return output
            height, width = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(gray, 45, 145)
            contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            image_area = float(max(1, width * height))
            for contour in sorted(contours, key=cv2.contourArea, reverse=True):
                area = float(cv2.contourArea(contour))
                if area < image_area * 0.006 or area > image_area * 0.98:
                    continue
                perimeter = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, max(4.0, perimeter * 0.025), True)
                if len(approx) < 4 or len(approx) > 10:
                    continue
                x, y, w, h = cv2.boundingRect(approx)
                short_ratio = min(w, h) / float(max(1, max(w, h)))
                if not 0.50 <= short_ratio <= 0.82:
                    continue
                rectangularity = area / float(max(1, w * h))
                if rectangularity < 0.42:
                    continue
                output.append({
                    "x": int(x), "y": int(y), "width": int(w), "height": int(h),
                    "confidence": min(0.88, 0.48 + rectangularity * 0.36),
                    "engine": "opencv-python",
                })
                if len(output) >= int(max_cards or 64):
                    break
        except Exception:
            return []
        return output

    def detect_card_regions(self, path, max_cards=64):
        """Multi-Engine-Erkennung für Galerie-/Ordnerseiten in v11.2.3.

        YOLO, MediaPipe, native/Python-OpenCV und der bisherige Pillow-Pfad
        stimmen gemeinsam über jede Kartenfläche ab. Die Resultate werden per
        Weighted-NMS fusioniert und danach visuell von oben nach unten sortiert.
        """
        detections = []
        image_width = image_height = 0
        try:
            from PIL import Image as PILImage, ImageOps
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            image_width, image_height = image.size
        except Exception:
            pass
        if not image_width or not image_height:
            return self._detect_card_regions_v109_legacy(path, max_cards=max_cards)

        model_root = os.path.join(os.path.dirname(__file__), "models")
        yolo_model = os.path.join(model_root, "yolo_card_detector.onnx")
        mediapipe_models = [
            os.path.join(model_root, "mediapipe_card_detector.tflite"),
            os.path.join(model_root, "mediapipe_card_detector.task"),
        ]
        if os.path.isfile(yolo_model):
            try:
                detections.extend(native_yolo_regions(path, yolo_model) or [])
            except Exception:
                pass
        for model_path in mediapipe_models:
            if os.path.isfile(model_path):
                try:
                    detections.extend(native_mediapipe_regions(path, model_path) or [])
                except Exception:
                    pass
                break
        try:
            detections.extend(native_detect_card_regions(path) or [])
        except Exception:
            pass
        detections.extend(self._python_opencv_card_regions_v1093(path, max_cards=max_cards))
        try:
            legacy = self._detect_card_regions_v109_legacy(path, max_cards=max_cards) or []
            for item in legacy:
                clone = dict(item or {})
                clone.setdefault("detector", "pillow-edge")
                clone.setdefault("detector_confidence", float(clone.get("detection_score") or 0.56))
                detections.append(clone)
        except Exception:
            pass
        return fuse_region_detections(
            detections,
            image_width=int(image_width),
            image_height=int(image_height),
            max_cards=max_cards,
            iou_threshold=0.46,
        )

    def detect_screenshot_card_region(self, path):
        """Findet eine nahezu vollbreite Kartenabbildung in Browser-/Galerie-Screenshots.

        Solche Bilder enthalten oben Browserleisten und unten Bedienelemente. Die
        bisherige Vollbild-OCR las dadurch oft UI- und Effekttext statt Titel,
        Set-Code und Passcode. Die Suche bleibt bewusst klein und Pillow-basiert.
        """
        try:
            from PIL import Image as PILImage, ImageOps, ImageFilter, ImageStat
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            ow, oh = image.size
            if ow < 240 or oh < 420 or (oh / float(max(1, ow))) < 1.55:
                return None
            gray = ImageOps.autocontrast(ImageOps.grayscale(image))
            scale = min(1.0, 320.0 / float(max(ow, oh)))
            if scale < 1.0:
                gray = gray.resize((max(1, int(ow * scale)), max(1, int(oh * scale))))
            edge = gray.filter(ImageFilter.FIND_EDGES)
            sw, sh = edge.size
            row_energy = [float(ImageStat.Stat(edge.crop((0, y, sw, y + 1))).mean[0]) for y in range(sh)]
            col_energy = [float(ImageStat.Stat(edge.crop((x, 0, x + 1, sh))).mean[0]) for x in range(sw)]
            best = None
            for width_fraction in (0.78, 0.88, 0.96, 1.0):
                cw = max(80, int(sw * width_fraction))
                ch = int(cw * 1.46)
                if ch >= sh:
                    continue
                for x in sorted(set((0, max(0, (sw - cw) // 2), max(0, sw - cw)))):
                    for y in range(0, max(1, sh - ch), 2):
                        top = sum(row_energy[max(0, y - 1):min(sh, y + 2)]) / max(1, len(row_energy[max(0, y - 1):min(sh, y + 2)]))
                        bottom_y = y + ch
                        bottom = sum(row_energy[max(0, bottom_y - 2):min(sh, bottom_y + 1)]) / max(1, len(row_energy[max(0, bottom_y - 2):min(sh, bottom_y + 1)]))
                        left = sum(col_energy[max(0, x - 1):min(sw, x + 2)]) / max(1, len(col_energy[max(0, x - 1):min(sw, x + 2)]))
                        right_x = x + cw
                        right = sum(col_energy[max(0, right_x - 2):min(sw, right_x + 1)]) / max(1, len(col_energy[max(0, right_x - 2):min(sw, right_x + 1)]))
                        crop = gray.crop((x, y, x + cw, y + ch))
                        contrast = float(ImageStat.Stat(crop).stddev[0])
                        center_penalty = abs((y + ch / 2.0) - sh / 2.0) / float(sh) * 20.0
                        score = top + bottom + 0.4 * (left + right) + contrast * 0.8 + (cw / float(sw)) * 20.0 - center_penalty
                        if best is None or score > best[0]:
                            best = (score, (x, y, x + cw, y + ch))
            if not best or best[0] < 175.0:
                return None
            x1, y1, x2, y2 = best[1]
            sx, sy = ow / float(sw), oh / float(sh)
            bbox = (
                max(0, int(x1 * sx)), max(0, int(y1 * sy)),
                min(ow, int(x2 * sx)), min(oh, int(y2 * sy)),
            )
            # Etwas Rand zurückgeben, damit Titelzeile und Passcode am Kartenrand
            # nicht durch die Screenshot-Erkennung abgeschnitten werden.
            bw0, bh0 = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad_x, pad_y = int(bw0 * 0.03), int(bh0 * 0.02)
            bbox = (
                max(0, bbox[0] - pad_x), max(0, bbox[1] - pad_y),
                min(ow, bbox[2] + pad_x), min(oh, bbox[3] + pad_y),
            )
            bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            coverage = (bw * bh) / float(max(1, ow * oh))
            if coverage < 0.35 or coverage > 0.90:
                return None
            return {
                "bbox": bbox, "coverage": coverage, "index": 1,
                "portrait": True, "screenshot_fallback": True,
                "detection_score": min(1.0, best[0] / 300.0),
            }
        except Exception:
            return None

    def _estimate_card_quad(self, crop):
        """Schätzt vier Außenpunkte einer Karte aus den Randkanten eines Crops."""
        try:
            from PIL import ImageOps, ImageFilter, ImageStat
            gray = ImageOps.autocontrast(ImageOps.grayscale(crop))
            small = gray.copy()
            small.thumbnail((420, 420))
            sw, sh = small.size
            edge = small.filter(ImageFilter.FIND_EDGES)
            stat = ImageStat.Stat(edge)
            threshold = int(max(35, min(180, (stat.mean[0] if stat.mean else 0) + (stat.stddev[0] if stat.stddev else 0) * 0.85)))
            pix = edge.load()
            points = []
            border_x = max(4, int(sw * 0.22))
            border_y = max(4, int(sh * 0.22))
            for y in range(sh):
                for x in range(sw):
                    if pix[x, y] < threshold:
                        continue
                    if x <= border_x or x >= sw - border_x or y <= border_y or y >= sh - border_y:
                        points.append((x, y))
            if len(points) < 24:
                return None
            tl = min(points, key=lambda p: p[0] + p[1])
            tr = max(points, key=lambda p: p[0] - p[1])
            bl = min(points, key=lambda p: p[0] - p[1])
            br = max(points, key=lambda p: p[0] + p[1])
            sx = crop.width / float(sw)
            sy = crop.height / float(sh)
            quad = tuple((int(x * sx), int(y * sy)) for x, y in (tl, tr, br, bl))
            return quad
        except Exception:
            return None

    def rectify_card_crop(self, image, bbox, use_perspective=True):
        """Schneidet eine Karte aus und begradigt die Perspektive bestmöglich."""
        try:
            from PIL import Image as PILImage, ImageOps
            crop = image.crop(tuple(int(v) for v in bbox))
            if crop.width > crop.height:
                crop = crop.rotate(90, expand=True)
            target_w = max(360, min(900, crop.width))
            target_h = int(target_w * 1.45)
            if use_perspective:
                quad = self._estimate_card_quad(crop)
                if quad:
                    tl, tr, br, bl = quad
                    data = (tl[0], tl[1], bl[0], bl[1], br[0], br[1], tr[0], tr[1])
                    try:
                        crop = crop.transform((target_w, target_h), PILImage.Transform.QUAD, data, resample=PILImage.Resampling.BICUBIC)
                    except Exception:
                        crop = crop.resize((target_w, target_h))
                else:
                    crop = ImageOps.fit(crop, (target_w, target_h), method=PILImage.Resampling.LANCZOS)
            else:
                crop = ImageOps.fit(crop, (target_w, target_h), method=PILImage.Resampling.LANCZOS)
            return crop
        except Exception:
            try:
                return image.crop(tuple(int(v) for v in bbox))
            except Exception:
                return image

    def prepare_scan_regions(self, path, mode=None):
        """Bereitet ein Bild für Einzel- oder Mehrkarten-Scan vor."""
        config = self.scan_mode_config(mode)
        records = []
        try:
            from PIL import Image as PILImage, ImageOps
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            width, height = image.size
            regions = self.detect_card_regions(path, max_cards=64) if config.get("detect_regions") else []
            screenshot_region = self.detect_screenshot_card_region(path) if config.get("detect_regions") else None
            if screenshot_region and not any(self._scan_bbox_iou(screenshot_region.get("bbox"), item.get("bbox")) > 0.72 for item in regions if item.get("bbox")):
                regions.append(screenshot_region)
            regions = suppress_nested_regions(regions, containment_threshold=0.86)
            for _index, _region in enumerate(sorted(regions, key=lambda r: (int((r.get("bbox") or (0, 0, 0, 0))[1]), int((r.get("bbox") or (0, 0, 0, 0))[0]))), start=1):
                _region["index"] = _index
            if regions and not config.get("multiple_cards"):
                regions = sorted(
                    regions,
                    key=lambda r: (float(r.get("detection_score") or 0), float(r.get("coverage") or 0)),
                    reverse=True,
                )[:1]
            if not regions:
                regions = [{"bbox": (0, 0, width, height), "coverage": 1.0, "index": 1, "portrait": height >= width, "fallback": True}]
            os.makedirs(self.user_data_dir, exist_ok=True)
            stamp = f"{time.time_ns()}_{hashlib.md5(str(path).encode('utf-8', 'ignore')).hexdigest()[:7]}"
            for region in regions:
                bbox = tuple(int(v) for v in (region.get("bbox") or (0, 0, width, height)))
                x1, y1, x2, y2 = bbox
                raw_crop = image.crop((max(0, x1), max(0, y1), min(width, x2), min(height, y2)))
                rectified_crop = self.rectify_card_crop(image, bbox, use_perspective=bool(config.get("perspective")))
                region_index = int(region.get("index") or 1)
                raw_out = os.path.join(self.user_data_dir, f"scan_region_raw_{stamp}_{region_index}.jpg")
                rectified_out = os.path.join(self.user_data_dir, f"scan_region_rectified_{stamp}_{region_index}.jpg")
                raw_crop.convert("RGB").save(raw_out, "JPEG", quality=97, subsampling=0)
                rectified_crop.convert("RGB").save(rectified_out, "JPEG", quality=95, subsampling=0)
                quality = self.analyze_scan_image_quality(raw_out, card_coverage=float(region.get("coverage") or 1.0))
                records.append({
                    "path": raw_out,
                    "raw_path": raw_out,
                    "rectified_path": rectified_out,
                    "source_path": path,
                    "region_index": int(region.get("index") or 1),
                    "detected_regions": len(regions),
                    "bbox": bbox,
                    "coverage": float(region.get("coverage") or 1.0),
                    "fallback": bool(region.get("fallback", False)),
                    "quality": quality,
                    "detector": str(region.get("detector") or "unknown"),
                    "detectors": list(region.get("detectors") or [region.get("detector") or "unknown"]),
                    "detection_score": float(region.get("detection_score") or 0.0),
                    "region_session_id": stable_region_session_id(str(path), bbox, int(region.get("index") or 1)),
                })
        except Exception as exc:
            quality = self.analyze_scan_image_quality(path, card_coverage=1.0)
            quality.setdefault("warnings", []).append(f"Kartenrahmen-Erkennung fehlgeschlagen: {exc}")
            records.append({
                "path": path,
                "raw_path": path,
                "rectified_path": path,
                "source_path": path,
                "region_index": 1,
                "detected_regions": 1,
                "bbox": None,
                "coverage": 1.0,
                "fallback": True,
                "quality": quality,
            })
        return records

    def _scan_image_dhash(self, path, artwork_only=False):
        try:
            from PIL import Image as PILImage, ImageOps
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            if image.width > image.height:
                image = image.rotate(90, expand=True)
            if artwork_only:
                w, h = image.size
                image = image.crop((int(w * 0.08), int(h * 0.18), int(w * 0.92), int(h * 0.61)))
            image = ImageOps.grayscale(image).resize((9, 8))
            pixels = list(image.getdata())
            value = 0
            for row in range(8):
                for col in range(8):
                    left = pixels[row * 9 + col]
                    right = pixels[row * 9 + col + 1]
                    value = (value << 1) | (1 if left > right else 0)
            return value
        except Exception:
            return None

    def _scan_best_artwork_variant(self, scan_path, card, allow_download=False):
        """Vergleicht alle bekannten Artworks und liefert die tatsächlich passendste Variante."""
        best_card = dict(card or {})
        best_similarity = None
        variants = expand_artwork_variants([card or {}]) or [card or {}]
        for variant in variants:
            try:
                url = get_image_url(variant)
                if not url:
                    continue
                os.makedirs(self.scan_artwork_cache_dir, exist_ok=True)
                ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
                if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                    ext = ".jpg"
                cached = os.path.join(self.scan_artwork_cache_dir, hashlib.sha1(url.encode("utf-8", "ignore")).hexdigest() + ext)
                if not os.path.exists(cached) or os.path.getsize(cached) < 128:
                    if not allow_download:
                        continue
                    request = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT})
                    data = open_url_bytes(request, timeout=5)
                    with open(cached, "wb") as f:
                        f.write(data)
                try:
                    self._scan_artwork_index[os.path.basename(cached)] = {
                        "card_id": str(variant.get("id") or card.get("id") or ""),
                        "name": str(variant.get("name") or card.get("name") or ""),
                        "url": url,
                        "artwork_id": artwork_identity_key(variant),
                    }
                    atomic_write_json(self.scan_artwork_index_file, self._scan_artwork_index, indent=None)
                except Exception:
                    pass
                similarity = visual_similarity(scan_path, cached, artwork_only=True)
                orb_score = native_orb_similarity(scan_path, cached)
                akaze_score = native_akaze_similarity(scan_path, cached)
                mobilenet_model = os.path.join(os.path.dirname(__file__), "models", "mobilenet_v3_small_075_224_embedder.tflite")
                mobilenet_score = native_mobilenet_similarity(scan_path, cached, mobilenet_model) if os.path.isfile(mobilenet_model) else None
                visual_scores = [float(value) for value in (similarity, orb_score, akaze_score, mobilenet_score) if value is not None]
                if visual_scores:
                    # Hash/Farbe bleibt robust gegen Folien; ORB/AKAZE bestätigt markante Artwork-Punkte.
                    fused_similarity = max(visual_scores) * 0.72 + (sum(visual_scores) / len(visual_scores)) * 0.28
                else:
                    fused_similarity = None
                if fused_similarity is not None and (best_similarity is None or fused_similarity > best_similarity):
                    best_similarity = float(fused_similarity)
                    best_card = dict(variant)
                    best_card["_artwork_orb_similarity"] = orb_score
                    best_card["_artwork_akaze_similarity"] = akaze_score
                    best_card["_artwork_mobilenet_similarity"] = mobilenet_score
            except Exception:
                continue
        # Eine Artwork-Variante wird nur automatisch übernommen, wenn das
        # aktuelle Bild sie ausreichend eindeutig bestätigt. Ansonsten bleibt
        # die ursprüngliche Kartenvariante erhalten und muss geprüft werden.
        if best_similarity is None or float(best_similarity) < 0.74:
            base_card = dict(card or {})
            base_card["_artwork_unconfirmed"] = True
            return base_card, best_similarity
        best_card["_artwork_verified"] = True
        return best_card, best_similarity

    def _scan_artwork_similarity(self, scan_path, card, allow_download=False):
        """Kompatibilitäts-Wrapper: liefert weiterhin nur die beste Ähnlichkeit."""
        _selected, similarity = self._scan_best_artwork_variant(scan_path, card, allow_download=allow_download)
        return similarity

    def _find_cached_artwork_fallback(self, scan_path, max_results=5, deadline_at=None):
        """Vergleicht nur bereits lokale Kartenbilder und liefert nahe Vorschläge.

        Es werden während des aktiven Scans keine zehntausenden Bilder heruntergeladen.
        Dadurch bleibt der Fallback schnell und offlinefähig.
        """
        if deadline_at is None:
            deadline_at = time.perf_counter() + 4.0
        scan_hash = self._scan_image_dhash(scan_path, artwork_only=True)
        if scan_hash is None:
            return []
        candidates = []
        seen_paths = set()
        try:
            for filename, meta in list((self._scan_artwork_index or {}).items()):
                path = os.path.join(self.scan_artwork_cache_dir, filename)
                if os.path.exists(path) and path not in seen_paths:
                    seen_paths.add(path)
                    candidates.append((path, str((meta or {}).get("card_id") or ""), str((meta or {}).get("url") or ""), str((meta or {}).get("artwork_id") or "")))
        except Exception:
            pass
        try:
            if os.path.isdir(self.image_cache_dir):
                for name in os.listdir(self.image_cache_dir):
                    if time.perf_counter() >= deadline_at or len(candidates) >= 260:
                        break
                    path = os.path.join(self.image_cache_dir, name)
                    if path in seen_paths or not os.path.isfile(path):
                        continue
                    if os.path.splitext(name)[1].lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                        continue
                    seen_paths.add(path)
                    card_id = re.sub(r"[^0-9]", "", os.path.splitext(name)[0])
                    candidates.append((path, card_id, "", ""))
        except Exception:
            pass
        if not candidates:
            return []
        scored = []
        for path, card_id, artwork_url, artwork_id in candidates:
            if time.perf_counter() >= deadline_at:
                break
            similarity = visual_similarity(scan_path, path, artwork_only=True)
            if similarity is None:
                continue
            if similarity >= 0.58:
                scored.append((similarity, card_id, path, artwork_url, artwork_id))
        scored.sort(reverse=True, key=lambda item: item[0])
        wanted_ids = {card_id for _similarity, card_id, _path, _url, _artid in scored[: max(12, int(max_results) * 3)] if card_id}
        card_map = {}
        if wanted_ids:
            for lang in ("de", "", "en", "fr", "it", "pt", "es", "ja", "ko"):
                if time.perf_counter() >= deadline_at:
                    break
                try:
                    for card in load_local_card_database(lang):
                        cid = str(card.get("id") or "")
                        if cid in wanted_ids and cid not in card_map:
                            card_map[cid] = card
                    if wanted_ids.issubset(card_map.keys()):
                        break
                except Exception:
                    continue
        results = []
        for similarity, card_id, path, artwork_url, artwork_id in scored:
            card = card_map.get(card_id)
            if not card:
                continue
            selected_card = card
            if artwork_url or artwork_id:
                for variant in expand_artwork_variants([card]) or [card]:
                    if artwork_id and artwork_identity_key(variant) == artwork_id:
                        selected_card = variant
                        break
                    if artwork_url and get_image_url(variant) == artwork_url:
                        selected_card = variant
                        break
            set_item = (selected_card.get("card_sets") or [{}])[0] if isinstance(selected_card.get("card_sets"), list) else {}
            confidence = max(35, min(92, int(round(similarity * 100))))
            results.append({
                "candidate": {"kind": "Artwork", "value": selected_card.get("name", ""), "priority": 45, "source": "Artwork-Cache"},
                "card": selected_card, "set_item": set_item or {}, "matches": len(scored),
                "language": "de", "language_label": "Artwork-Vergleich",
                "score": similarity * 100.0, "confidence": confidence,
                "confidence_reason": f"Lokales Artwork zu {similarity * 100:.0f} % ähnlich; Druckvariante bitte prüfen.",
                "artwork_similarity": similarity, "lookup_source": "artwork-cache",
                "artwork_path": path, "artwork_identity_key": artwork_identity_key(selected_card),
            })
            if len(results) >= int(max_results or 5):
                break
        return results

    def scan_language_order_for_candidates(self, candidates):
        """Bestimmt die Scan-Suchsprachen ohne automatische Deutsch-Bevorzugung.

        Reihenfolge:
        1. Sprache aus einem erkannten Set-Code
        2. Sprache aus Schrift-/Effekterkennung
        3. Englisch als neutraler API-Fallback
        4. alle weiteren unterstützten Kartensprachen
        """
        detected = []
        metadata = merge_scan_metadata([
            item for item in (candidates or []) if str((item or {}).get("kind") or "") == "Metadata"
        ])
        for candidate in candidates or []:
            if str(candidate.get("kind") or "") != "Set-Code":
                continue
            code = language_code_from_set_code(candidate.get("value"))
            if code is not None and code not in detected:
                detected.append(code)
        hint = metadata.get("language_hint")
        if hint is not None and hint not in detected:
            detected.append(hint)
        neutral_order = ["", "de", "fr", "it", "pt", "es", "ja", "ko", "zh", "zh-tw"]
        return detected + [code for code in neutral_order if code in SCAN_SEARCH_LANGUAGE_CODES and code not in detected]

    def compute_scan_confidence(self, best, quality=None, alternatives=None):
        """Erzeugt eine verständliche Treffer-Sicherheit mit Begründung."""
        quality = quality or {}
        alternatives = alternatives or []
        candidate = (best or {}).get("candidate") or {}
        kind = str(candidate.get("kind") or "Name")
        source = str(candidate.get("source") or "OCR")
        value = str(candidate.get("value") or "")
        card = (best or {}).get("card") or {}
        set_item = (best or {}).get("set_item") or {}
        matches_count = int((best or {}).get("matches") or 0)
        ai_confidence = float((best or {}).get("ai_confidence_v102") or 0.0)
        confidence = max(52, int(round(ai_confidence * 100))) if ai_confidence else 52
        reasons = [f"KI-Ensemble {int(ai_confidence * 100)} %"] if ai_confidence else []
        if kind == "Set-Code" and set_item:
            confidence = 97
            reasons.append("Set-Code mit Set-Variante gefunden")
        elif kind == "Passcode" and re.sub(r"\D+", "", value) == str(card.get("id") or ""):
            confidence = 95
            reasons.append("Passcode exakt gefunden")
        elif kind == "Name" and normalize_search_text(value) == normalize_search_text(card.get("name", "")):
            confidence = 90
            reasons.append("Kartenname exakt gefunden")
        elif kind == "Name":
            ratio = SequenceMatcher(None, normalize_search_text(value), normalize_search_text(card.get("name", ""))).ratio()
            confidence = int(55 + ratio * 32)
            reasons.append(f"Kartenname ähnlich ({int(ratio * 100)} %)")
        if kind == "Effect":
            similarity = float((best or {}).get("effect_similarity") or 0.0)
            confidence = max(confidence, int(42 + similarity * 48))
            reasons.append(f"Effekttext passt zu {int(similarity * 100)} %")
        secondary_effect = float((best or {}).get("effect_similarity") or 0.0)
        if kind != "Effect" and secondary_effect > 0:
            if secondary_effect >= 0.48:
                confidence += 9
                reasons.append(f"Effekt bestätigt Treffer ({int(secondary_effect * 100)} %)")
            elif secondary_effect >= 0.30:
                confidence += 4
                reasons.append(f"Effekt teilweise passend ({int(secondary_effect * 100)} %)")
        if "Korrektur" in source or "Fuzzy" in source:
            confidence -= 6
            reasons.append("OCR-Zeichen automatisch korrigiert")
        if matches_count == 1:
            confidence += 3
            reasons.append("eindeutiger Datenbanktreffer")
        elif matches_count > 5:
            confidence -= min(14, matches_count // 2)
            reasons.append(f"{matches_count} mögliche Datenbanktreffer")
        metadata_score = float((best or {}).get("metadata_score") or 0.0)
        metadata_matches = list((best or {}).get("metadata_matches") or [])
        metadata_conflicts = list((best or {}).get("metadata_conflicts") or [])
        if metadata_matches:
            confidence += min(12, len(metadata_matches) * 3)
            reasons.append("Kartendaten bestätigt: " + ", ".join(metadata_matches[:2]))
        if metadata_conflicts:
            confidence -= min(35, len(metadata_conflicts) * 12)
            reasons.append("Kartendaten widersprechen OCR")
        elif metadata_score >= 0.8:
            confidence += 5
        artwork_similarity = (best or {}).get("artwork_similarity")
        if artwork_similarity is not None:
            art_pct = int(float(artwork_similarity) * 100)
            if artwork_similarity >= 0.83:
                confidence += 7
                reasons.append(f"Artwork passt sehr gut ({art_pct} %)")
            elif artwork_similarity >= 0.68:
                confidence += 3
                reasons.append(f"Artwork passt ({art_pct} %)")
            elif artwork_similarity < 0.48:
                confidence -= 9
                reasons.append(f"Artwork weicht ab ({art_pct} %)")
        quality_score = int(quality.get("score") or 0)
        if quality_score and quality_score < 45:
            confidence -= 10
            reasons.append("schwache Bildqualität")
        elif quality_score >= 80:
            confidence += 2
            reasons.append("gute Bildqualität")
        if alternatives:
            second_score = float(alternatives[0].get("score") or 0)
            best_score = float((best or {}).get("score") or 0)
            if second_score and abs(best_score - second_score) < 18:
                confidence -= 9
                reasons.append("ähnlich starker Alternativtreffer")
        confidence = max(15, min(99, int(confidence)))
        return confidence, "; ".join(reasons[:7]) or "Treffer aus OCR und Kartendatenbank"

    def scan_failure_reason(self, quality=None, ocr_text="", lookup_attempts=None, frame_fallback=False):
        quality = quality or {}
        warnings = list(quality.get("warnings") or [])
        if not str(ocr_text or "").strip():
            if warnings:
                return "OCR hat keinen Text erkannt: " + ", ".join(warnings)
            return "OCR hat keinen Text erkannt"
        if frame_fallback:
            warnings.insert(0, "kein eindeutiger Kartenrahmen erkannt")
        if lookup_attempts:
            warnings.append("erkannter Text konnte keiner Karte sicher zugeordnet werden")
        return "; ".join(dict.fromkeys(warnings)) or "Name/Set-Code erkannt, aber keine passende Karte gefunden"


    def scan_error_display_summary(self, error_text):
        """Kurze, verständliche Fehleranzeige; technische Details bleiben in Historie/Log."""
        value = re.sub(r"\s+", " ", str(error_text or "")).strip()
        value = value.split("geprüft:", 1)[0].strip(" .;:")
        value = value.split("Suche 1:", 1)[0].strip(" .;:")
        if not value:
            value = "Die Karte konnte nicht sicher erkannt werden."
        if len(value) > 190:
            value = value[:187].rstrip() + "…"
        return value

    def parse_scan_ocr_text(self, text):
        """Extrahiert OCR-Rohtext mit Priorität: Set-Code, danach Passcode, erst dann Name."""
        raw = text or ""
        upper_raw = raw.upper()

        # Set-/Printcodes haben Vorrang vor dem 8-stelligen Passcode unten links.
        # Unterstützt typische OCR-Varianten wie "SBCB-DE001", "SBCB DE001", "SBCB D E 001" oder "RA01 001".
        set_patterns = [
            r"\b([A-Z0-9]{2,10})[\s\-_/]*(DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA)[\s\-_/]*(\d{1,4})\b",
            r"\b([A-Z0-9]{2,10})[\s\-_/]*([A-Z])[\s\-_/]*([A-Z])[\s\-_/]*(\d{1,4})\b",
            r"\b([A-Z0-9]{2,10})[\s\-_/]+(\d{1,4})\b",
        ]
        for idx, pattern in enumerate(set_patterns):
            for match in re.finditer(pattern, upper_raw):
                groups = match.groups()
                if idx == 0:
                    prefix, lang, number = groups
                elif idx == 1:
                    prefix, l1, l2, number = groups
                    lang = (l1 + l2)
                    if lang not in {"DE", "EN", "FR", "IT", "PT", "ES", "SP", "JP", "KR", "AE", "EU", "NA"}:
                        continue
                else:
                    prefix, number = groups
                    lang = ""

                # Häufige Nicht-Set-Wörter herausfiltern, damit z. B. ATK 2500 nicht als Set erkannt wird.
                if prefix in {"ATK", "DEF", "KONAMI", "CARD", "MONSTER", "SPELL", "TRAP", "SPEED", "DUEL"}:
                    continue

                set_code = f"{prefix}-{lang + str(number).zfill(3) if lang else str(number).zfill(3)}"
                return {"passcode": "", "set_code": set_code, "name": "", "raw": raw}

        # Yu-Gi-Oh!-Passcodes sind in der Regel 8-stellig; 7- bis 10-stellige Treffer werden toleriert.
        # Dieser Fallback kommt bewusst erst nach der Set-Code-Erkennung.
        digit_candidates = re.findall(r"(?<!\d)(\d[\d\s\-]{5,12}\d)(?!\d)", raw)
        cleaned_digits = []
        for item in digit_candidates:
            digits = re.sub(r"\D+", "", item)
            if 7 <= len(digits) <= 10:
                cleaned_digits.append(digits)
        if cleaned_digits:
            cleaned_digits.sort(key=lambda d: (len(d) == 8, len(d)), reverse=True)
            # Passcode nur behalten, aber Name kann unten noch gewinnen, wenn kein reiner Code-Scan möglich ist.
            best_passcode = cleaned_digits[0]
        else:
            best_passcode = ""

        bad_words = {
            "ATK", "DEF", "EN", "DE", "FR", "IT", "PT", "KONAMI", "YUGIOH", "YU-GI-OH",
            "1ST", "EDITION", "LIMITED", "SPELL", "TRAP", "CARD", "MONSTER", "EFFECT",
        }
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            line = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ0-9 '\-.,:&/]+", " ", line)
            line = re.sub(r"\s+", " ", line).strip(" -.,")
            if len(line) < 3:
                continue
            upper = line.upper()
            if upper in bad_words:
                continue
            if sum(ch.isalpha() for ch in line) < 3:
                continue
            if any(word in upper.split() for word in bad_words):
                # Nicht sofort verwerfen, aber niedrig priorisieren.
                score_penalty = 2
            else:
                score_penalty = 0
            # Namen stehen oft oben und bestehen aus Buchstaben mit wenigen Zahlen.
            score = len(line) - score_penalty * 12 - max(0, sum(ch.isdigit() for ch in line) - 2) * 4
            lines.append((score, line))
        if best_passcode:
            return {"passcode": best_passcode, "set_code": "", "name": "", "raw": raw}
        if lines:
            lines.sort(reverse=True)
            return {"passcode": "", "set_code": "", "name": lines[0][1], "raw": raw}
        return {"passcode": "", "set_code": "", "name": "", "raw": raw}

    def parse_scan_ocr_candidates(self, text, max_names=8):
        """Liefert mehrere OCR-Kandidaten für den Sammelimport.
        Der Scanner nutzt dadurch nicht nur den zuerst erkannten Wert, sondern sucht
        pro Bild nach Set-Code, Kartenname und Passcode in allen verfügbaren Sprachen.
        Zusätzlich werden häufige OCR-Fehler (z. B. O/0, I/1/L) korrigiert.
        """
        raw = text or ""
        upper_raw = raw.upper()
        candidates = []
        seen = set()

        def add(kind, value, priority, source="OCR"):
            value = str(value or "").strip()
            if not value:
                return
            value = re.sub(r"\s+", " ", value).strip(" -.,;:")
            if not value:
                return
            sig = (kind, normalize_search_text(value))
            if sig in seen:
                return
            seen.add(sig)
            candidates.append({"kind": kind, "value": value, "priority": int(priority), "source": source})

        def add_with_aliases(kind, value, priority, source="OCR"):
            add(kind, value, priority, source)
            if kind == "Set-Code":
                for alias in build_scan_code_aliases(value):
                    if normalize_search_text(alias) != normalize_search_text(value):
                        add(kind, alias, max(42, int(priority) - 6), source + "-Korrektur")
            elif kind == "Name":
                for alias in build_scan_name_aliases(value):
                    if normalize_search_text(alias) != normalize_search_text(value):
                        add(kind, alias, max(30, int(priority) - 5), source + "-Korrektur")

        # 1) Set-/Printcodes in allen Sprachvarianten erkennen.
        lang_tokens = "DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA"
        blocked_prefixes = {"ATK", "DEF", "KONAMI", "CARD", "MONSTER", "SPELL", "TRAP", "SPEED", "DUEL", "LINK"}
        set_patterns = [
            r"\b([A-Z0-9]{2,10})[\s\-_/]*(" + lang_tokens + r")[\s\-_/]*(\d{1,4})\b",
            r"\b([A-Z0-9]{2,10})[\s\-_/]*([A-Z])[\s\-_/]*([A-Z])[\s\-_/]*(\d{1,4})\b",
            r"\b([A-Z0-9]{2,10})[\s\-_/]+(\d{1,4})\b",
        ]
        for idx, pattern in enumerate(set_patterns):
            for match in re.finditer(pattern, upper_raw):
                try:
                    groups = match.groups()
                    if idx == 0:
                        prefix, lang, number = groups
                    elif idx == 1:
                        prefix, l1, l2, number = groups
                        lang = l1 + l2
                        if lang not in set(lang_tokens.split("|")):
                            continue
                    else:
                        prefix, number = groups
                        lang = ""
                    if prefix in blocked_prefixes:
                        continue
                    if lang:
                        add_with_aliases("Set-Code", f"{prefix}-{lang}{str(number).zfill(3)}", 100, "OCR-Set")
                    else:
                        add_with_aliases("Set-Code", f"{prefix}-{str(number).zfill(3)}", 86, "OCR-Set")
                except Exception:
                    continue

        # 1b) Fuzzy-Setcodes: toleriert O/0/I/1/L usw. bei OCR.
        fuzzy_patterns = [
            # Mit Trenner: YGLD-DEO02 / YGLD DE 002 / YGLD-DE002.
            r"\b([A-Z0-9]{2,10})[\s\-_/]+((?:DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA)?)[\s\-_/]*([A-Z0-9]{2,4})\b",
            # Kompakt ohne Trenner: YGLDDE002. Muss mit 2–4 ziffernähnlichen
            # Zeichen enden; normale Wörter aus dem Effekttext werden verworfen.
            r"\b([A-Z0-9]{2,10})((?:DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA))([0-9OQDCILZSG]{2,4})\b",
        ]
        for pattern in fuzzy_patterns:
            for match in re.finditer(pattern, upper_raw):
                groups = match.groups()
                raw_code = "".join(groups) if len(groups) > 1 else groups[0]
                if not raw_code or raw_code in blocked_prefixes:
                    continue
                for alias in build_scan_code_aliases(raw_code):
                    prefix_only = alias.split("-", 1)[0]
                    if prefix_only in blocked_prefixes:
                        continue
                    add("Set-Code", alias, 54, "OCR-Set-Fuzzy")

        # 2) Passcodes/Karten-IDs sammeln.
        digit_candidates = re.findall(r"(?<!\d)(\d[\d\s\-]{5,12}\d)(?!\d)", raw)
        for item in digit_candidates:
            digits = re.sub(r"\D+", "", item)
            if 7 <= len(digits) <= 10:
                add("Passcode", digits, 112 if len(digits) == 8 else 62, "OCR-Code")

        # 3) Namenskandidaten aus allen sinnvollen OCR-Zeilen ziehen.
        bad_words = {
            "ATK", "DEF", "EN", "DE", "FR", "IT", "PT", "ES", "SP", "JP", "KR",
            "KONAMI", "YUGIOH", "YU-GI-OH", "1ST", "EDITION", "LIMITED", "SPELL",
            "TRAP", "CARD", "MONSTER", "EFFECT", "DUEL", "SPEED", "KAZUKI", "TAKAHASHI",
        }
        name_lines = []
        effect_lines = []
        effect_markers = {
            "AKTIVIERE", "BESCHWÖREN", "BESCHWOREN", "ZERSTÖRT", "ZERSTORT", "VERBANNE", "WÄHLE", "WAHLE",
            "DU KANNST", "FALLS", "WENN", "EFFECT", "ACTIVATE", "SPECIAL SUMMON", "DESTROY", "TARGET",
            "BANNISSEZ", "INVOQUEZ", "DETRUISEZ", "PUEDES", "DESTRUYE", "EVOCAR", "PUOI", "DISTRUGGI",
        }
        for line_index, raw_line in enumerate(raw.splitlines()):
            original = raw_line.strip()
            line = "".join(ch if (ch.isalnum() or ch in " '-.,:&/()[]") else " " for ch in original)
            line = re.sub(r"\s+", " ", line).strip(" -.,")
            if len(line) < 3:
                continue
            upper = line.upper()
            if upper in bad_words:
                continue
            alpha_count = sum(ch.isalpha() for ch in line)
            if alpha_count < 3:
                continue
            if re.fullmatch(r"[A-Z0-9]{2,10}[\s\-_/]*(?:" + lang_tokens + r")?[\s\-_/]*[A-Z0-9]{1,4}", upper):
                continue
            words = [part for part in re.split(r"\s+", line) if part]
            punctuation = sum(line.count(mark) for mark in (".", ";", ":"))
            looks_like_effect = (
                len(line) > 68
                or len(words) >= 11
                or punctuation >= 2
                or any(marker in upper for marker in effect_markers)
            )
            if looks_like_effect:
                effect_lines.append((line_index, line))

            # Kartennamen stehen überwiegend oben, sind relativ kurz und enthalten
            # selten vollständige Effekt-Sätze. Lange Effektzeilen werden nicht mehr
            # als Namenskandidaten bewertet.
            if len(line) > 72 or len(words) > 10 or punctuation >= 2:
                continue
            word_penalty = 0
            parts = set(upper.replace("/", " ").replace("-", " ").split())
            if parts & bad_words:
                word_penalty += 2
            if any(marker in upper for marker in effect_markers):
                word_penalty += 3
            digit_penalty = max(0, sum(ch.isdigit() for ch in line) - 2) * 4
            top_bonus = max(0, 32 - line_index * 4)
            length_bonus = min(18, len(line))
            score = 42 + top_bonus + length_bonus - word_penalty * 14 - digit_penalty
            name_lines.append((score, line))
        name_lines.sort(reverse=True)
        for score, line in name_lines[:max_names]:
            add_with_aliases("Name", line, max(35, min(96, score)), "OCR-Name")

        # 4) Effekt-Fallback für unsichere Karten. Mehrere OCR-Zeilen werden zu
        # markanten Textblöcken kombiniert; gesucht wird später nur lokal und nur,
        # wenn Set-Code/Passcode/Name nicht eindeutig sind.
        if effect_lines:
            effect_lines.sort(key=lambda item: item[0])
            effect_text = " ".join(line for _idx, line in effect_lines[:10])
            if len(effect_tokens(effect_text, limit=120)) >= 4:
                add("Effect", effect_text[:1800], 26, "OCR-Effekt")
            for start in range(0, min(len(effect_lines), 8), 3):
                chunk = " ".join(line for _idx, line in effect_lines[start:start + 4])
                if len(effect_tokens(chunk, limit=80)) >= 4:
                    add("Effect", chunk[:900], 22, "OCR-Effekt-Teil")

        # 5) Volltext-Fallback: sinnvolle Wortgruppen als Namens-Backup.
        compact_lines = [re.sub(r"\s+", " ", part).strip(" -.,") for part in raw.splitlines()]
        compact_lines = [part for part in compact_lines if len(part) >= 4 and sum(ch.isalpha() for ch in part) >= 3]
        if compact_lines:
            joined = " ".join(compact_lines[:3])
            if 4 <= len(joined) <= 80:
                add_with_aliases("Name", joined, 34, "OCR-Zeilen-Fallback")

        # 6) Teiltreffer kombinieren: Präfix, Sprachcode und Nummer können in
        # unterschiedlichen OCR-Zeilen stehen. Daraus werden plausible Set-Codes gebaut.
        try:
            prefix_tokens = []
            number_tokens = []
            language_tokens_found = []
            for token in re.findall(r"[A-Z0-9]{2,12}", upper_raw):
                if token in blocked_prefixes or token in bad_words:
                    continue
                if token in set(lang_tokens.split("|")):
                    language_tokens_found.append(token)
                    continue
                if token.isdigit() and 1 <= len(token) <= 4:
                    number_tokens.append(token)
                    continue
                if 2 <= len(token) <= 10 and sum(ch.isalpha() for ch in token) >= 2:
                    prefix_tokens.append(token)
            # Nur wenige Kombinationen erzeugen, damit der Scan schnell bleibt.
            for prefix in prefix_tokens[:4]:
                for number in number_tokens[:5]:
                    if language_tokens_found:
                        for lang in language_tokens_found[:3]:
                            add_with_aliases("Set-Code", f"{prefix}-{lang}{str(number).zfill(3)}", 82, "OCR-Teiltreffer")
                    else:
                        add_with_aliases("Set-Code", f"{prefix}-{str(number).zfill(3)}", 68, "OCR-Teiltreffer")
        except Exception:
            pass

        # 7) Den bisherigen Einzelparser als zusätzlichen Fallback einbauen.
        try:
            primary = self.parse_scan_ocr_text(raw)
            if primary.get("set_code"):
                add_with_aliases("Set-Code", primary.get("set_code"), 102, "OCR-Haupttreffer")
            if primary.get("name"):
                add_with_aliases("Name", primary.get("name"), 90, "OCR-Haupttreffer")
            if primary.get("passcode"):
                add("Passcode", primary.get("passcode"), 114, "OCR-Haupttreffer")
        except Exception:
            pass

        candidates.sort(key=lambda c: int(c.get("priority") or 0), reverse=True)
        try:
            if getattr(self, "scan_learning", None) is not None:
                candidates = self.scan_learning.expand_candidates(candidates)
        except Exception:
            pass
        metadata = extract_scan_metadata(raw)
        if metadata:
            candidates.append({
                "kind": "Metadata",
                "value": "",
                "priority": 0,
                "source": "OCR-Metadaten",
                "metadata": metadata,
            })
        return candidates

    def _scan_has_strong_ocr_candidate(self, candidates):
        """Beendet OCR früh nur bei wirklich belastbaren Kartenmerkmalen.

        In v10.0 reichte bereits irgendein Fuzzy-Kandidat. Dadurch konnten Wörter
        aus dem Effekttext die gezielten Name-/Set-/Passcode-Zonen verhindern.
        """
        for candidate in candidates or []:
            kind = str(candidate.get("kind") or "")
            value = str(candidate.get("value") or "").strip()
            source = str(candidate.get("source") or "")
            if kind == "Passcode" and len(re.sub(r"\D+", "", value)) == 8:
                return True
            if kind == "Set-Code":
                normalized = re.sub(r"\s+", "", value.upper())
                if re.fullmatch(r"[A-Z0-9]{2,10}-(?:(?:DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA))?[0-9]{1,4}", normalized):
                    return True
            if kind == "Name" and not bool(getattr(self, "_gallery_scan_active", False)) and "Fuzzy" not in source and "Teiltreffer" not in source:
                words = [part for part in re.split(r"\s+", value) if part]
                if 1 <= len(words) <= 8 and 4 <= len(value) <= 64 and sum(ch.isalpha() for ch in value) >= 4:
                    return True
        return False

    def _build_guided_ocr_variant_images(self, path, max_variants=3):
        """Erzeugt wenige gezielte OCR-Hilfsbilder aus einem Scan.

        Ziel:
        - Kartenbereich besser in den Fokus bringen
        - obere/untere Textzonen separat hervorheben
        - Hoch-/Querformat robuster behandeln
        """
        variants = []
        try:
            from PIL import Image as PILImage, ImageOps, ImageEnhance, ImageFilter
            if not path or not os.path.exists(path):
                return variants
            base = PILImage.open(path)
            try:
                base = ImageOps.exif_transpose(base)
            except Exception:
                pass
            if base.mode not in ("RGB", "L"):
                base = base.convert("RGB")
            try:
                max_edge = int(self.scan_mode_config().get("max_image_edge") or 1900)
                if max(base.size) > max_edge:
                    scale = float(max_edge) / float(max(base.size))
                    base = base.resize((max(1, int(base.width * scale)), max(1, int(base.height * scale))), PILImage.Resampling.LANCZOS)
            except Exception:
                pass
            tmp_dir = self.user_data_dir if hasattr(self, "user_data_dir") else os.path.dirname(path)
            os.makedirs(tmp_dir, exist_ok=True)
            stamp = str(time.time_ns())

            def save_variant(img, label):
                if len(variants) >= int(max_variants or 0):
                    return
                try:
                    out = os.path.join(tmp_dir, f"guided_ocr_{stamp}_{len(variants)+1}_{label}.jpg")
                    img.save(out, "JPEG", quality=94)
                    variants.append(out)
                except Exception:
                    pass

            portrait_candidates = [base]
            if base.width > base.height * 1.18:
                portrait_candidates.append(base.rotate(90, expand=True))
                portrait_candidates.append(base.rotate(270, expand=True))
            portrait = max(portrait_candidates, key=lambda img: (img.height / max(1, img.width), img.height))

            # 1) Komplettbild mit mehr Kontrast und Schärfe.
            full = ImageEnhance.Contrast(ImageOps.grayscale(portrait)).enhance(2.0).filter(ImageFilter.SHARPEN)
            save_variant(full, "full")

            pw, ph = portrait.size
            card_w = min(pw, max(140, int(ph / 1.42)))
            card_h = min(ph, max(200, int(card_w * 1.42)))
            x1 = max(0, int((pw - card_w) / 2))
            y1 = max(0, int((ph - card_h) / 2))
            x2 = min(pw, x1 + card_w)
            y2 = min(ph, y1 + card_h)
            center = portrait.crop((x1, y1, x2, y2))
            center = ImageEnhance.Contrast(ImageOps.grayscale(center)).enhance(2.2).filter(ImageFilter.SHARPEN)
            save_variant(center, "center")

            # 3) Wichtige OCR-Zonen kombinieren: Kartenname oben, Set-/Passcode unten.
            if len(variants) < int(max_variants or 0):
                cw, ch = center.size
                name_zone = center.crop((0, 0, cw, max(1, int(ch * 0.17))))
                set_zone = center.crop((int(cw * 0.34), max(0, int(ch * 0.80)), cw, ch))
                pass_zone = center.crop((0, max(0, int(ch * 0.84)), int(cw * 0.62), ch))
                pieces = [name_zone, set_zone, pass_zone]
                spacer = int(dp(4))
                total_h = int(sum(piece.height for piece in pieces) + spacer * (len(pieces) - 1))
                board = PILImage.new("L", (max(piece.width for piece in pieces), total_h), 255)
                y = 0
                for piece in pieces:
                    piece = ImageEnhance.Contrast(ImageOps.grayscale(piece)).enhance(2.5).filter(ImageFilter.SHARPEN)
                    board.paste(piece, (0, y))
                    y += piece.height + spacer
                save_variant(board, "zones")
        except Exception:
            return variants[: int(max_variants or 0)]
        return variants[: int(max_variants or 0)]

    def _build_gallery_color_ocr_variant_images(self, path, max_variants=6):
        """Erzeugt farbunabhängige OCR-Bilder für Gold-, Silber- und Foil-Schrift.

        Seltenheiten verändern häufig Farbe, Glanz und Kontrast der Schrift. Statt
        nur Graustufen zu verwenden, werden Helligkeit, invertierte Helligkeit sowie
        einzelne RGB-Kanäle und kontrastierte Textzonen getestet.
        """
        variants = []
        try:
            from PIL import Image as PILImage, ImageOps, ImageEnhance, ImageFilter, ImageChops
            if not path or not os.path.exists(path):
                return variants
            base = PILImage.open(path)
            try:
                base = ImageOps.exif_transpose(base)
            except Exception:
                pass
            base = base.convert("RGB")
            max_edge = int(self.scan_mode_config("gallery").get("max_image_edge") or 1900)
            if max(base.size) > max_edge:
                scale = float(max_edge) / float(max(base.size))
                base = base.resize((max(1, int(base.width * scale)), max(1, int(base.height * scale))), PILImage.Resampling.LANCZOS)

            # Auf den wahrscheinlichsten Kartenbereich zentrieren. prepare_scan_regions
            # liefert normalerweise schon einen begradigten Kartenausschnitt; dieser
            # Fallback schützt Browser-Screenshots und breite Galeriebilder.
            portrait = base
            if portrait.width > portrait.height * 1.18:
                rotated = [portrait.rotate(90, expand=True), portrait.rotate(270, expand=True)]
                portrait = max([portrait] + rotated, key=lambda img: img.height / max(1, img.width))
            pw, ph = portrait.size
            expected_w = min(pw, max(160, int(ph / 1.45)))
            expected_h = min(ph, max(230, int(expected_w * 1.45)))
            x1 = max(0, (pw - expected_w) // 2)
            y1 = max(0, (ph - expected_h) // 2)
            card = portrait.crop((x1, y1, min(pw, x1 + expected_w), min(ph, y1 + expected_h)))
            cw, ch = card.size

            # Titel, Effekt, Set-Code und Passcode gemeinsam auf einer weißen Tafel.
            zones = [
                card.crop((0, 0, cw, max(1, int(ch * 0.17)))),
                card.crop((0, max(0, int(ch * 0.60)), cw, max(1, int(ch * 0.91)))),
                card.crop((int(cw * 0.32), max(0, int(ch * 0.78)), cw, ch)),
                card.crop((0, max(0, int(ch * 0.84)), int(cw * 0.68), ch)),
            ]
            spacer = 8
            board_w = max(zone.width for zone in zones)
            board_h = sum(zone.height for zone in zones) + spacer * (len(zones) - 1)
            board = PILImage.new("RGB", (board_w, board_h), "white")
            y = 0
            for zone in zones:
                board.paste(zone.convert("RGB"), (0, y))
                y += zone.height + spacer

            tmp_dir = self.user_data_dir if hasattr(self, "user_data_dir") else os.path.dirname(path)
            os.makedirs(tmp_dir, exist_ok=True)
            stamp = str(time.time_ns())

            def save_variant(image, label):
                if len(variants) >= max(0, int(max_variants or 0)):
                    return
                try:
                    image = image.filter(ImageFilter.SHARPEN)
                    out = os.path.join(tmp_dir, f"gallery_color_ocr_{stamp}_{len(variants)+1}_{label}.jpg")
                    image.convert("L").save(out, "JPEG", quality=94)
                    variants.append(out)
                except Exception:
                    pass

            gray = ImageOps.autocontrast(ImageOps.grayscale(board), cutoff=1)
            save_variant(ImageEnhance.Contrast(gray).enhance(1.7), "luma")
            save_variant(ImageEnhance.Contrast(ImageOps.invert(gray)).enhance(1.6), "luma_inv")

            red, green, blue = board.split()
            channels = [
                (ImageOps.autocontrast(red), "red"),
                (ImageOps.autocontrast(green), "green"),
                (ImageOps.autocontrast(blue), "blue"),
                (ImageOps.autocontrast(ImageChops.lighter(red, ImageChops.lighter(green, blue))), "brightest"),
                (ImageOps.autocontrast(ImageChops.darker(red, ImageChops.darker(green, blue))), "darkest"),
            ]
            for channel, label in channels:
                save_variant(ImageEnhance.Contrast(channel).enhance(1.9), label)

            # Seltenheits-/Foil-Profile: Gold hebt Rot+Grün gegen Blau hervor,
            # Silber misst geringe Farbsättigung, Holo verstärkt Kanalunterschiede.
            gold = ImageChops.subtract(ImageChops.lighter(red, green), blue)
            save_variant(ImageEnhance.Contrast(ImageOps.autocontrast(gold)).enhance(2.15), "gold")
            channel_max = ImageChops.lighter(red, ImageChops.lighter(green, blue))
            channel_min = ImageChops.darker(red, ImageChops.darker(green, blue))
            saturation = ImageChops.subtract(channel_max, channel_min)
            silver = ImageOps.invert(ImageOps.autocontrast(saturation))
            save_variant(ImageEnhance.Contrast(silver).enhance(1.85), "silver")
            rg = ImageChops.difference(red, green)
            gb = ImageChops.difference(green, blue)
            holo = ImageChops.lighter(rg, gb)
            save_variant(ImageEnhance.Contrast(ImageOps.autocontrast(holo)).enhance(2.0), "holo")

            # Zwei Schwellenwerte helfen bei metallisch heller und sehr dunkler Schrift.
            for threshold, label in ((108, "threshold_dark"), (176, "threshold_light")):
                if len(variants) >= int(max_variants or 0):
                    break
                binary = gray.point(lambda px, t=threshold: 255 if px > t else 0)
                save_variant(binary, label)
        except Exception:
            return variants[: max(0, int(max_variants or 0))]
        return variants[: max(0, int(max_variants or 0))]

    def gallery_multi_engine_ocr_v1093(self, path, callback, deadline_at=None, full_ensemble=True):
        """OCR-Ensemble pro isolierter Kartenfläche.

        ML Kit liest alle relevanten Schriftsysteme lokal. PaddleOCR und
        EasyOCR werden nur genutzt, wenn ihre Runtime/Modelle verfügbar sind.
        Jede Engine liefert einen eigenen Textstrom; erst danach werden Zeilen
        zusammengeführt, damit kein Bild die OCR-Daten einer anderen Fläche erbt.
        """
        if deadline_at is None:
            deadline_at = time.perf_counter() + 20.0

        def worker():
            outputs = []
            errors = []
            scripts = ("latin", "japanese", "korean", "chinese", "devanagari")
            if platform == "android":
                for script in scripts:
                    if time.perf_counter() >= deadline_at:
                        break
                    try:
                        value = native_mlkit_ocr(path, script=script)
                        if value and str(value).strip():
                            outputs.append({"engine": f"mlkit_{script}", "text": str(value), "weight": 1.0})
                    except Exception as exc:
                        errors.append(f"ML Kit {script}: {exc}")
                if full_ensemble and time.perf_counter() < deadline_at:
                    model_root = os.path.join(os.path.dirname(__file__), "models", "paddleocr")
                    det_model = os.path.join(model_root, "det", "inference.onnx")
                    rec_model = os.path.join(model_root, "rec_latin", "inference.onnx")
                    dict_path = os.path.join(model_root, "rec_latin", "ppocrv5_latin_dict.vocab")
                    if os.path.isfile(det_model) and os.path.isfile(rec_model):
                        try:
                            value = native_paddle_ocr(path, det_model, rec_model, dict_path)
                            if value and str(value).strip():
                                outputs.append({"engine": "paddleocr", "text": str(value), "weight": 0.95})
                        except Exception as exc:
                            errors.append("PaddleOCR: " + str(exc))
                # Fallback auf den bereits bewährten direkten Pyjnius-ML-Kit-Pfad,
                # falls die Java-Bridge auf einem Herstellergerät nicht geladen wurde.
                if not outputs and time.perf_counter() < deadline_at:
                    Clock.schedule_once(lambda *_: self.ocr_scan_image(path, callback, deadline_at=deadline_at), 0)
                    return
            else:
                try:
                    optional = optional_ocr_bundle(
                        path,
                        languages=("en", "de", "fr", "es", "it", "pt", "ja", "ko", "ch_sim", "ch_tra"),
                    )
                    for engine, value in optional.items():
                        if engine.endswith("_error"):
                            errors.append(f"{engine}: {value}")
                        elif value and str(value).strip():
                            normalized_engine = "easyocr" if engine == "easyocr" else "paddleocr"
                            outputs.append({"engine": normalized_engine, "text": str(value), "weight": 0.92 if normalized_engine == "paddleocr" else 0.82})
                except Exception as exc:
                    errors.append("Optionale OCR: " + str(exc))
                try:
                    from PIL import Image as PILImage
                    import pytesseract
                    remaining = max(1, int(deadline_at - time.perf_counter()))
                    value = pytesseract.image_to_string(PILImage.open(path), lang="eng+deu", timeout=remaining)
                    if value and str(value).strip():
                        outputs.append({"engine": "tesseract", "text": str(value), "weight": 0.68})
                except Exception as exc:
                    errors.append("Tesseract: " + str(exc))
            merged = merge_ocr_engine_outputs(outputs)
            message = "" if merged.get("text") else "; ".join(errors) or "Keine OCR-Engine lieferte Text."
            Clock.schedule_once(lambda *_: callback(str(merged.get("text") or ""), message), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _prepare_ocr_resolution_image(self, path):
        """Skaliert nur kleine Karten-Crops kontrolliert für OCR hoch."""
        try:
            from PIL import Image as PILImage, ImageOps
            image = PILImage.open(path)
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            w, h = image.size
            short_edge = min(w, h)
            if short_edge >= 760 or short_edge <= 0:
                return path
            factor = min(3.0, max(1.35, 900.0 / float(short_edge)))
            nw, nh = int(round(w * factor)), int(round(h * factor))
            max_edge = max(nw, nh)
            if max_edge > 3600:
                scale = 3600.0 / float(max_edge)
                nw, nh = int(nw * scale), int(nh * scale)
            if nw <= w and nh <= h:
                return path
            out = os.path.join(self.user_data_dir, f"ocr_upscale_{time.time_ns()}.jpg")
            image.convert("RGB").resize((nw, nh), PILImage.Resampling.LANCZOS).save(out, "JPEG", quality=97, subsampling=0)
            return out
        except Exception:
            return path

    def smart_ocr_scan_image(self, path, callback, max_variant_images=3, deadline_at=None):
        """OCR mit frühem Erfolg: Varianten laufen nur, solange kein Kandidat vorliegt."""
        path = self._prepare_ocr_resolution_image(path)
        config = self.scan_mode_config()
        if deadline_at is None:
            deadline_at = time.perf_counter() + float(config.get("hard_timeout_seconds") or 10.0)
        normalized_path = normalize_scanner_image_file(path, self.user_data_dir, "ocr_input")
        path = normalized_path or path
        image_paths = [path]
        gallery_active = bool(getattr(self, "_gallery_scan_active", False))
        try:
            if time.perf_counter() < deadline_at:
                image_paths.extend(self._build_guided_ocr_variant_images(path, max_variants=max(0, int(max_variant_images or 0))))
            if gallery_active and time.perf_counter() < deadline_at:
                color_count = int(self.scan_mode_config("gallery").get("color_ocr_variants") or 0)
                image_paths.extend(self._build_gallery_color_ocr_variant_images(path, max_variants=color_count))
        except Exception:
            pass
        # Doppelte Pfade entfernen, Reihenfolge beibehalten.
        image_paths = list(dict.fromkeys(item for item in image_paths if item))
        collected_texts = []
        collected_errors = []

        def finish(reason=""):
            combined = "\n\n".join([item for item in collected_texts if item])
            error = "" if combined else (reason or "; ".join(collected_errors) or "OCR lieferte keinen verwertbaren Text.")
            try:
                callback(combined, error)
            except Exception:
                pass

        def run_index(index):
            if index >= len(image_paths):
                finish()
                return
            if time.perf_counter() >= deadline_at:
                finish("Zeitbudget erreicht; weitere OCR-Varianten wurden übersprungen.")
                return
            current_path = image_paths[index]

            def after(text, error=""):
                if text and str(text).strip():
                    collected_texts.append(str(text))
                    try:
                        parsed_candidates = self.parse_scan_ocr_candidates(text)
                        if gallery_active:
                            # Galerie sammelt mehrere Farb-/Zonenvarianten. Früh beendet
                            # wird nur bei einem exakten Identifikator; ein scheinbar
                            # plausibler Name aus dem Effekttext reicht nicht aus.
                            exact_identifier = any(
                                (c.get("kind") == "Passcode" and len(re.sub(r"\D+", "", str(c.get("value") or ""))) == 8)
                                or (c.get("kind") == "Set-Code" and "Fuzzy" not in str(c.get("source") or "") and "Teiltreffer" not in str(c.get("source") or ""))
                                for c in parsed_candidates
                            )
                            if exact_identifier and len(collected_texts) >= 2:
                                finish()
                                return
                        elif self._scan_has_strong_ocr_candidate(parsed_candidates):
                            finish()
                            return
                    except Exception:
                        pass
                elif error:
                    collected_errors.append(str(error))
                run_index(index + 1)

            try:
                if gallery_active:
                    self.gallery_multi_engine_ocr_v1093(
                        current_path,
                        after,
                        deadline_at=deadline_at,
                        full_ensemble=(index == 0),
                    )
                else:
                    self.ocr_scan_image(current_path, after, deadline_at=deadline_at)
            except Exception as exc:
                collected_errors.append(str(exc))
                run_index(index + 1)

        run_index(0)

    def _create_ocr_retry_images(self, path, max_extra_attempts=1):
        """Erzeugt optionale Bildvarianten für zusätzliche OCR-Versuche.
        Die App funktioniert auch ohne Pillow; dann wird nur das Original genutzt.
        """
        variants = []
        try:
            from PIL import Image as PILImage, ImageOps, ImageEnhance, ImageFilter
            if not path or not os.path.exists(path):
                return variants
            base = PILImage.open(path)
            try:
                base = ImageOps.exif_transpose(base)
            except Exception:
                pass
            if base.mode not in ("RGB", "L"):
                base = base.convert("RGB")
            tmp_dir = self.user_data_dir if hasattr(self, "user_data_dir") else os.path.dirname(path)
            stamp = str(time.time_ns())

            def save_variant(img, label):
                if len(variants) >= int(max_extra_attempts or 1):
                    return
                try:
                    out = os.path.join(tmp_dir, f"ocr_retry_{stamp}_{len(variants)+1}_{label}.jpg")
                    img.save(out, "JPEG", quality=92)
                    variants.append(out)
                except Exception:
                    pass

            gray = ImageOps.grayscale(base)
            save_variant(ImageEnhance.Contrast(gray).enhance(1.9).filter(ImageFilter.SHARPEN), "contrast")
            save_variant(base.rotate(90, expand=True), "rot90")
            save_variant(base.rotate(270, expand=True), "rot270")
            try:
                w, h = base.size
                # Name und Set-Code liegen bei Yu-Gi-Oh!-Karten häufig im oberen/unteren Bereich.
                upper = base.crop((0, 0, w, max(1, int(h * 0.42))))
                lower = base.crop((0, max(0, int(h * 0.58)), w, h))
                merged_h = upper.height + lower.height
                merged = PILImage.new("RGB", (max(upper.width, lower.width), merged_h), (255, 255, 255))
                merged.paste(upper.convert("RGB"), (0, 0))
                merged.paste(lower.convert("RGB"), (0, upper.height))
                save_variant(ImageEnhance.Contrast(ImageOps.grayscale(merged)).enhance(1.8), "name_set")
            except Exception:
                pass
        except Exception:
            return variants[:int(max_extra_attempts or 1)]
        return variants[:int(max_extra_attempts or 1)]

    def _scan_filters_for_candidate(self, candidate, language_code):
        value = str((candidate or {}).get("value") or "").strip()
        kind = str((candidate or {}).get("kind") or "Name")
        filters = {
            "name": "", "card_id": "", "set": "", "atk": "", "def": "", "level": "",
            "race": "", "attribute": "", "group": "Alle", "language": language_code,
        }
        if kind == "Set-Code":
            filters["set"] = value
        elif kind == "Passcode":
            filters["card_id"] = re.sub(r"\D+", "", value)
        elif kind == "Effect":
            # Effekte werden über den lokalen Volltext-/Ähnlichkeitspfad gesucht.
            pass
        else:
            filters["name"] = value
        return filters

    def _scan_match_score(self, card, set_item, candidate, language_code, matches_count, scan_metadata=None):
        value = str((candidate or {}).get("value") or "").strip()
        kind = str((candidate or {}).get("kind") or "Name")
        score = int((candidate or {}).get("priority") or 0)
        try:
            if kind == "Set-Code" and set_item and strict_set_code_equal(value, set_item.get("set_code")):
                score += 1200
            if kind == "Passcode" and re.sub(r"\D+", "", value) == str(card.get("id") or ""):
                score += 1100
            if kind == "Name" and normalize_search_text(value) == normalize_search_text(card.get("name", "")):
                score += 380
            elif kind == "Name":
                ratio = SequenceMatcher(None, normalize_search_text(value), normalize_search_text(card.get("name", ""))).ratio()
                score += int(ratio * 240)
            if kind == "Effect":
                similarity = effect_similarity(value, card.get("desc") or card.get("description") or card.get("effect") or "")
                score += int(similarity * 480)
                if similarity >= 0.50:
                    score += 100
                elif similarity >= 0.34:
                    score += 40
            metadata_result = card_metadata_consistency(card, scan_metadata)
            score += int(float(metadata_result.get("score") or 0.0) * 280)
            score -= min(520, len(metadata_result.get("conflicts") or []) * 150)
            if set_item:
                score += 80
            if get_image_url(card):
                score += 30
            if card.get("card_sets"):
                score += 20
            # Keine pauschale Deutsch- oder Englisch-Bevorzugung. Sprache zählt
            # nur, wenn OCR/Set-Code dafür einen konkreten Hinweis geliefert hat.
            language_hint = (scan_metadata or {}).get("language_hint")
            if language_hint is not None:
                score += 70 if language_code == language_hint else -20
            score += max(0, 20 - int(matches_count or 0))
        except Exception:
            pass
        return score

    def _scan_local_candidate_cards(self, candidate, language_code, limit=10):
        """Schnelle Offline-Abfrage über die vorhandene SQLite-Spiegeldatenbank."""
        value = str((candidate or {}).get("value") or "").strip()
        kind = str((candidate or {}).get("kind") or "Name")
        if not value:
            return []
        cards = []
        path = local_sqlite_database_file(language_code)
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                conn = sqlite3.connect(path, timeout=1.5)
                try:
                    cur = conn.cursor()
                    if kind == "Passcode":
                        cur.execute("SELECT raw_json FROM cards WHERE passcode = ? LIMIT ?", (re.sub(r"\D+", "", value), int(limit)))
                    elif kind == "Set-Code":
                        signature = normalize_set_code_signature(value)
                        raw = value.upper().replace(" ", "")
                        probes = [raw, signature, raw.split("-")[0]]
                        clauses = " OR ".join(["UPPER(REPLACE(set_codes, ' ', '')) LIKE ?" for _ in probes])
                        params = [f"%{probe}%" for probe in probes] + [int(limit)]
                        cur.execute(f"SELECT raw_json FROM cards WHERE {clauses} LIMIT ?", params)
                    elif kind == "Effect":
                        normalized_terms = effect_search_terms(value, limit=6)
                        if not normalized_terms:
                            return []
                        # Neue Datenbanken besitzen normalisierten effect_text. Bei
                        # älteren Datenbanken werden zusätzlich Originalwörter und
                        # robuste Wortpräfixe genutzt, damit Umlaute/Akzente den SQL-
                        # Kandidatenpool nicht verhindern.
                        try:
                            columns = {str(row[1]) for row in cur.execute("PRAGMA table_info(cards)").fetchall()}
                        except Exception:
                            columns = set()
                        effect_field = "effect_text" if "effect_text" in columns else "raw_json"
                        if effect_field == "effect_text":
                            query_terms = normalized_terms
                        else:
                            raw_tokens = []
                            for raw_token in re.findall(r"[^\W_]+", str(value or "").casefold(), flags=re.UNICODE):
                                if len(raw_token) >= 5 and raw_token not in raw_tokens:
                                    raw_tokens.append(raw_token)
                            raw_tokens.sort(key=len, reverse=True)
                            query_terms = []
                            for token in raw_tokens[:6] + normalized_terms:
                                for probe in (token, token[:8] if len(token) > 8 else token):
                                    if len(probe) >= 5 and probe not in query_terms:
                                        query_terms.append(probe)
                            query_terms = query_terms[:10]
                        clauses = " OR ".join([f"LOWER({effect_field}) LIKE ?" for _ in query_terms])
                        params = [f"%{term.lower()}%" for term in query_terms] + [max(int(limit), 80)]
                        cur.execute(f"SELECT raw_json FROM cards WHERE {clauses} LIMIT ?", params)
                    else:
                        cur.execute("SELECT raw_json FROM cards WHERE LOWER(name) = LOWER(?) OR LOWER(name) LIKE LOWER(?) LIMIT ?", (value, f"%{value}%", int(limit)))
                    for row in cur.fetchall():
                        try:
                            card = json.loads(row[0])
                            if isinstance(card, dict):
                                cards.append(card)
                        except Exception:
                            continue
                finally:
                    conn.close()
        except Exception:
            cards = []
        if kind == "Set-Code" and cards:
            # SQLite-LIKE liefert bewusst einen breiten Kandidatenpool. Vor der
            # Rückgabe werden ausschließlich exakt passende Druckcodes behalten.
            cards = [card for card in cards if exact_set_item_for_code(card, value)]
        elif kind == "Passcode" and cards:
            digits = re.sub(r"\D+", "", value)
            cards = [card for card in cards if str(card.get("id") or "") == digits]
        if cards:
            if kind == "Effect":
                scored = []
                for card in cards:
                    similarity = effect_similarity(value, card.get("desc") or card.get("description") or card.get("effect") or "")
                    if similarity >= 0.10:
                        scored.append((similarity, card))
                scored.sort(key=lambda item: item[0], reverse=True)
                return [card for _score, card in scored[: int(limit)]]
            return cards[: int(limit)]
        # JSON-Fallback bleibt offline. Für Effekte wird ein kleiner bewerteter
        # Kandidatenpool aufgebaut, bei normalen Kandidaten bleibt der bisherige Filter.
        try:
            filters = self._scan_filters_for_candidate(candidate, language_code)
            payload = load_local_card_database(language_code)
            if kind == "Effect":
                scored = []
                for card in payload:
                    similarity = effect_similarity(value, card.get("desc") or card.get("description") or card.get("effect") or "")
                    if similarity >= 0.16:
                        scored.append((similarity, card))
                scored.sort(key=lambda item: item[0], reverse=True)
                cards = [card for _score, card in scored[: int(limit)]]
            else:
                for card in payload:
                    if card_matches_local_filters(card, filters):
                        cards.append(card)
                        if len(cards) >= int(limit):
                            break
        except Exception:
            pass
        if kind == "Set-Code":
            cards = [card for card in cards if exact_set_item_for_code(card, value)]
        elif kind == "Passcode":
            digits = re.sub(r"\D+", "", value)
            cards = [card for card in cards if str(card.get("id") or "") == digits]
        return cards[: int(limit)]

    def _scan_network_candidate_cards(self, candidate, language_code, timeout_seconds=4.0, limit=10):
        """Kurzer API-Fallback mit strikter Nachprüfung von Set-Code/Passcode."""
        try:
            kind = str((candidate or {}).get("kind") or "Name")
            value = str((candidate or {}).get("value") or "").strip()
            filters = self._scan_filters_for_candidate(candidate, language_code)
            if kind == "Set-Code":
                # Die API akzeptiert Set-Namen, aber keine vollständigen Druckcodes.
                # Daher wird zunächst der Set-Name aufgelöst und anschließend strikt
                # auf den tatsächlich erkannten Druckcode zurückgefiltert.
                resolved = resolve_set_code_to_set_name(value)
                if not resolved:
                    return []
                filters["set"] = resolved
            url = build_api_url(filters)
            req = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"})
            raw = open_url_bytes(req, timeout=max(1, min(6, int(timeout_seconds or 4))))
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            cards = [card for card in (payload.get("data", []) if isinstance(payload, dict) else []) if isinstance(card, dict)]
            if kind == "Set-Code":
                cards = [card for card in cards if exact_set_item_for_code(card, value)]
            elif kind == "Passcode":
                digits = re.sub(r"\D+", "", value)
                cards = [card for card in cards if str(card.get("id") or "") == digits]
            return cards[: int(limit)]
        except Exception:
            return []

    def _isolated_scan_match_acceptance(self, best, candidates=None):
        """Verhindert automatische Fehlzuordnungen bei schwachen Einzelsignalen.

        Jeder Bildscan muss für sich ausreichend Belege liefern. Exakte Set-Codes
        und Passcodes werden akzeptiert. Namen, Effekte und Artworks benötigen
        eine höhere Sicherheit oder ein zweites, unabhängiges Signal.
        """
        if not best or not best.get("card"):
            return False, "Kein eigenständiger Kartenkandidat vorhanden."
        candidate = best.get("candidate") or {}
        kind = str(candidate.get("kind") or "Name")
        exact = bool(best.get("exact"))
        confidence = int(best.get("confidence") or 0)
        artwork_similarity = best.get("artwork_similarity")
        effect_similarity_value = float(best.get("effect_similarity") or 0.0)
        evidence_kinds = {
            str(item.get("kind") or "")
            for item in (best.get("evidence") or [])
            if isinstance(item, dict)
        }
        metadata_conflicts = list(best.get("metadata_conflicts") or [])
        metadata_comparable = int(best.get("metadata_comparable") or 0)
        if exact and kind in {"Set-Code", "Passcode"}:
            if len(metadata_conflicts) >= 2 or (metadata_comparable <= 2 and metadata_conflicts and not best.get("metadata_matches")):
                return False, "Exakter Code gefunden, aber ATK/DEF/Typ oder andere Kartendaten widersprechen dem Treffer."
            return True, "Exakter Kartenidentifikator mit Kartendaten-Gegenprüfung."
        if artwork_similarity is not None and float(artwork_similarity) < 0.34:
            return False, "Artwork widerspricht dem vorgeschlagenen Treffer."
        if kind == "Artwork":
            if artwork_similarity is not None and float(artwork_similarity) >= 0.78:
                return True, "Artwork eigenständig und deutlich ausreichend ähnlich."
            return False, "Artwork-Ähnlichkeit ist für eine automatische Zuordnung zu niedrig."
        independent_signals = len({k for k in evidence_kinds if k in {"Name", "Effect", "Set-Code", "Passcode", "Artwork"}})
        if confidence >= 82:
            return True, "Hohe isolierte Trefferbewertung."
        if confidence >= 72 and independent_signals >= 2:
            return True, "Mindestens zwei unabhängige Signale bestätigen den Treffer."
        if float(artwork_similarity or 0.0) >= 0.74 and (kind == "Name" or effect_similarity_value >= 0.44):
            return True, "Text und Artwork bestätigen sich gegenseitig."
        if effect_similarity_value >= 0.58 and kind in {"Name", "Effect"}:
            return True, "Effekttext bestätigt den Kandidaten deutlich."
        return False, "Treffer war nicht eindeutig genug und bleibt zur manuellen Prüfung offen."

    def _find_scan_matches_for_candidates(self, candidates, scan_path="", quality=None, include_artwork=None, max_alternatives=4, deadline_at=None):
        """Strenge mehrstufige Suche für einen einzelnen Scan.

        Feste Reihenfolge:
        1. Set-Code – ausschließlich exakt passende Druckcodes
        2. Passcode – ausschließlich exakt passende Karten-ID
        3. Kartenname erst, wenn Set-Code und Passcode nichts ergeben
        4. Effekttext und Artwork nur als Fallback/Bestätigung

        ATK, DEF, Level/Rang/Link, Pendelskala, Kartentyp, Attribut und
        Monstertyp werden zur Gegenprüfung jedes Kandidaten verwendet.
        """
        config = self.scan_mode_config()
        if deadline_at is None:
            deadline_at = time.perf_counter() + float(config.get("hard_timeout_seconds") or 10.0)
        quality = quality or {}
        tried = []
        all_candidates = list(candidates or [])
        metadata_candidates = [item for item in all_candidates if str((item or {}).get("kind") or "") == "Metadata"]
        scan_metadata = merge_scan_metadata(metadata_candidates)
        set_candidates = sorted(
            [item for item in all_candidates if str((item or {}).get("kind") or "") == "Set-Code"],
            key=lambda item: int(item.get("priority") or 0), reverse=True,
        )
        passcode_candidates = sorted(
            [item for item in all_candidates if str((item or {}).get("kind") or "") == "Passcode"],
            key=lambda item: int(item.get("priority") or 0), reverse=True,
        )
        name_candidates = sorted(
            [item for item in all_candidates if str((item or {}).get("kind") or "") == "Name"],
            key=lambda item: int(item.get("priority") or 0), reverse=True,
        )
        effect_candidates = sorted(
            [item for item in all_candidates if str((item or {}).get("kind") or "") == "Effect"],
            key=lambda item: int(item.get("priority") or 0), reverse=True,
        )
        language_order = self.scan_language_order_for_candidates(all_candidates)
        max_languages = max(1, int(config.get("max_languages") or len(SCAN_SEARCH_LANGUAGE_CODES)))
        language_order = language_order[:max_languages]
        candidate_limit = max(1, int(config.get("max_candidates") or 8))
        cards_limit = max(2, int(config.get("max_cards_per_query") or 12))
        if include_artwork is None:
            include_artwork = bool(config.get("artwork"))

        def add_cards(target, seen, cards, candidate, lang, source, stage):
            value = str(candidate.get("value") or "").strip()
            kind = str(candidate.get("kind") or "Name")
            for card in list(cards or [])[:cards_limit]:
                if time.perf_counter() >= deadline_at:
                    break
                try:
                    set_item = None
                    exact = False
                    if kind == "Set-Code":
                        set_item = exact_set_item_for_code(card, value)
                        if not set_item:
                            continue
                        exact = True
                    elif kind == "Passcode":
                        if re.sub(r"\D+", "", value) != str(card.get("id") or ""):
                            continue
                        exact = True
                    else:
                        sets = dedupe_card_sets_for_display(card.get("card_sets") or [], "")
                        if len(sets) == 1:
                            set_item = sets[0]
                        exact = kind == "Name" and normalize_search_text(value) == normalize_search_text(card.get("name", ""))

                    actual_lang = language_code_from_set_code((set_item or {}).get("set_code"))
                    if actual_lang is None:
                        actual_lang = lang
                    metadata_result = card_metadata_consistency(card, scan_metadata)
                    score = self._scan_match_score(
                        card, set_item, candidate, actual_lang, len(cards or []), scan_metadata=scan_metadata
                    )
                    effect_score = effect_similarity(value, card.get("desc") or card.get("description") or card.get("effect") or "") if kind == "Effect" else 0.0
                    name_similarity = 0.0
                    if kind == "Name":
                        name_similarity = SequenceMatcher(
                            None, normalize_search_text(value), normalize_search_text(card.get("name", ""))
                        ).ratio()
                    score += fusion_bonus(kind, exact=exact, quality_score=float(quality.get("score") or 0))
                    card_id = str(get_card_id(card) or card.get("name") or "")
                    set_code = str((set_item or {}).get("set_code") or "")
                    key = (int(stage), card_id, set_code)
                    evidence_sig = (kind, normalize_search_text(value), str(source))
                    item = {
                        "candidate": copy.deepcopy(candidate),
                        "card": copy.deepcopy(card),
                        "set_item": copy.deepcopy(set_item or {}),
                        "matches": len(cards or []),
                        "language": actual_lang,
                        "language_label": scan_language_label(actual_lang),
                        "score": float(score),
                        "lookup_source": source,
                        "exact": bool(exact),
                        "search_stage": int(stage),
                        "effect_similarity": float(effect_score),
                        "name_similarity": float(name_similarity),
                        "scan_metadata": copy.deepcopy(scan_metadata),
                        "metadata_score": float(metadata_result.get("score") or 0.0),
                        "metadata_matches": list(metadata_result.get("matches") or []),
                        "metadata_conflicts": list(metadata_result.get("conflicts") or []),
                        "metadata_comparable": int(metadata_result.get("comparable") or 0),
                        "metadata_severe_conflict": bool(metadata_result.get("severe_conflict")),
                        "evidence": [{"kind": kind, "value": value, "source": source, "score": float(score)}],
                        "_evidence_signatures": {evidence_sig},
                    }
                    existing = seen.get(key)
                    if existing is None:
                        seen[key] = item
                        target.append(item)
                        continue
                    signatures = existing.setdefault("_evidence_signatures", set())
                    if evidence_sig not in signatures:
                        signatures.add(evidence_sig)
                        existing.setdefault("evidence", []).append(item["evidence"][0])
                        existing_kinds = {str(ev.get("kind") or "") for ev in existing.get("evidence", [])[:-1]}
                        factor = 0.30 if kind not in existing_kinds else 0.06
                        existing["score"] = float(existing.get("score") or 0) + min(180.0, max(0.0, float(score)) * factor)
                    existing["effect_similarity"] = max(float(existing.get("effect_similarity") or 0.0), float(effect_score))
                    existing["name_similarity"] = max(float(existing.get("name_similarity") or 0.0), float(name_similarity))
                    if exact or float(score) > float(existing.get("score") or 0):
                        combined = max(float(existing.get("score") or 0), float(score))
                        preserved_evidence = existing.get("evidence") or []
                        preserved_signatures = existing.get("_evidence_signatures") or set()
                        existing.update(item)
                        existing["score"] = combined
                        existing["evidence"] = preserved_evidence
                        existing["_evidence_signatures"] = preserved_signatures
                except Exception:
                    continue

        def search_stage(stage_candidates, stage, allow_network=True):
            stage_results = []
            stage_seen = {}
            network_queries = 0
            for candidate in list(stage_candidates or [])[:candidate_limit]:
                if time.perf_counter() >= deadline_at:
                    break
                value = str(candidate.get("value") or "").strip()
                if not value:
                    continue
                candidate_found = False
                for lang in language_order:
                    if time.perf_counter() >= deadline_at:
                        break
                    local_cards = self._scan_local_candidate_cards(candidate, lang, limit=cards_limit)
                    tried.append(
                        f"Stufe {stage} lokal {candidate.get('kind')} '{short_text(value, 55)}' in {scan_language_label(lang)}: {len(local_cards)}"
                    )
                    add_cards(stage_results, stage_seen, local_cards, candidate, lang, "lokal", stage)
                    if local_cards:
                        candidate_found = True
                if candidate_found:
                    continue
                if allow_network and network_queries < int(config.get("network_fallback_queries") or 0):
                    for lang in language_order:
                        if time.perf_counter() >= deadline_at:
                            break
                        remaining = max(0.5, deadline_at - time.perf_counter())
                        if remaining <= 0.5:
                            break
                        cards = self._scan_network_candidate_cards(
                            candidate, lang, timeout_seconds=min(4.0, remaining), limit=cards_limit
                        )
                        network_queries += 1
                        tried.append(
                            f"Stufe {stage} Netz {candidate.get('kind')} '{short_text(value, 55)}' in {scan_language_label(lang)}: {len(cards)}"
                        )
                        add_cards(stage_results, stage_seen, cards, candidate, lang, "netz", stage)
                        if cards or network_queries >= int(config.get("network_fallback_queries") or 0):
                            break
            return stage_results

        # Stufe 1: Set-Code. Namen dürfen diese Stufe niemals überstimmen.
        set_results = search_stage(set_candidates, 0, allow_network=True) if set_candidates else []
        locked_results = []
        locked_stage = None
        if set_results:
            consistent = [item for item in set_results if not item.get("metadata_severe_conflict")]
            if consistent:
                locked_results = consistent
                locked_stage = 0
            elif passcode_candidates:
                # Nur bei deutlichem ATK/DEF/Typ-Widerspruch darf ein vorhandener
                # Passcode die fehlerhaft gelesene Set-Code-Stufe korrigieren.
                pass_results = search_stage(passcode_candidates, 1, allow_network=True)
                consistent_pass = [item for item in pass_results if not item.get("metadata_severe_conflict")]
                if consistent_pass:
                    locked_results = consistent_pass
                    locked_stage = 1
                else:
                    locked_results = set_results
                    locked_stage = 0
            else:
                locked_results = set_results
                locked_stage = 0

        # Stufe 2: Passcode nur wenn kein Set-Code-Datenbanktreffer existiert.
        if not locked_results and passcode_candidates:
            pass_results = search_stage(passcode_candidates, 1, allow_network=True)
            if pass_results:
                locked_results = pass_results
                locked_stage = 1

        # Stufe 3: Kartenname ausschließlich, wenn beide Identifikator-Stufen leer sind.
        if not locked_results:
            fallback_results = search_stage(name_candidates, 2, allow_network=True) if name_candidates else []
            fallback_seen = {
                (int(item.get("search_stage") or 2), str(get_card_id(item.get("card") or {}) or ""), str((item.get("set_item") or {}).get("set_code") or "")): item
                for item in fallback_results
            }
            # Effekttext ist ein unabhängiges Zusatzsignal und darf bei fehlenden
            # Identifikatoren Kandidaten bestätigen oder neu liefern.
            if bool(config.get("effect_matching")) and effect_candidates and time.perf_counter() < deadline_at:
                for candidate in effect_candidates[:4]:
                    for lang in language_order:
                        if time.perf_counter() >= deadline_at:
                            break
                        cards = self._scan_local_candidate_cards(candidate, lang, limit=cards_limit)
                        tried.append(f"Stufe 3 lokal Effekt in {scan_language_label(lang)}: {len(cards)}")
                        add_cards(fallback_results, fallback_seen, cards, candidate, lang, "lokal-effekt", 2)
                        if cards:
                            break
            locked_results = fallback_results
            locked_stage = 2 if fallback_results else None

        # Wenn keinerlei Texttreffer vorliegt, darf der lokale Artwork-Fallback
        # eigenständig Vorschläge erzeugen. Er wird niemals gegen einen exakten
        # Set-Code oder Passcode ausgespielt.
        if not locked_results and include_artwork and scan_path and time.perf_counter() < deadline_at:
            artwork_results = self._find_cached_artwork_fallback(
                scan_path, max_results=max(3, int(config.get("artwork_candidates") or 3)), deadline_at=deadline_at
            )
            for item in artwork_results:
                metadata_result = card_metadata_consistency(item.get("card") or {}, scan_metadata)
                item["scan_metadata"] = copy.deepcopy(scan_metadata)
                item["metadata_score"] = float(metadata_result.get("score") or 0.0)
                item["metadata_matches"] = list(metadata_result.get("matches") or [])
                item["metadata_conflicts"] = list(metadata_result.get("conflicts") or [])
                item["metadata_comparable"] = int(metadata_result.get("comparable") or 0)
                item["metadata_severe_conflict"] = bool(metadata_result.get("severe_conflict"))
                item["search_stage"] = 4
                item.setdefault("evidence", []).append({"kind": "Artwork", "value": item.get("candidate", {}).get("value", ""), "source": "Artwork-Cache", "score": item.get("score", 0)})
            locked_results = artwork_results
            locked_stage = 4 if artwork_results else None

        # Effekttext bestätigt eine bereits per Set-Code/Passcode identifizierte
        # Karte, darf sie aber nicht durch eine andere Karte ersetzen.
        if locked_results and locked_stage in {0, 1} and effect_candidates:
            for item in locked_results:
                card_desc = (item.get("card") or {}).get("desc") or ""
                best_effect = max(
                    [effect_similarity(candidate.get("value") or "", card_desc) for candidate in effect_candidates] or [0.0]
                )
                item["effect_similarity"] = max(float(item.get("effect_similarity") or 0.0), float(best_effect))
                if best_effect >= 0.30:
                    item["score"] = float(item.get("score") or 0) + int(best_effect * 160)
                    item.setdefault("evidence", []).append({"kind": "Effect", "value": "Effekt-Gegenprüfung", "source": "OCR-Effekt", "score": best_effect * 160})

        # Artwork-Vergleich bleibt auf die bereits identifizierte Karte und deren
        # eigene Artwork-Varianten begrenzt. Dadurch kann ein anderes Artwork nie
        # mehr eine Set-Code-/Passcode-Karte ersetzen.
        art_limit = max(0, int(config.get("artwork_candidates") or 0))
        if include_artwork and scan_path and locked_results and locked_stage != 4 and art_limit and time.perf_counter() < deadline_at:
            for item in locked_results[:art_limit]:
                if time.perf_counter() >= deadline_at:
                    break
                selected_artwork_card, similarity = self._scan_best_artwork_variant(
                    scan_path, item.get("card") or {}, allow_download=False
                )
                item["artwork_similarity"] = similarity
                if selected_artwork_card:
                    item["card"] = copy.deepcopy(selected_artwork_card)
                    item["artwork_identity_key"] = artwork_identity_key(selected_artwork_card)
                if similarity is not None:
                    item["score"] = float(item.get("score") or 0) + fusion_bonus("Artwork", artwork_similarity=similarity)

        ocr_signal_text = " ".join(
            str((item or {}).get("value") or "") for item in all_candidates if str((item or {}).get("kind") or "") != "Metadata"
        )
        locked_results = rank_scan_items(locked_results, quality=quality, ocr_text=ocr_signal_text)
        locked_results = rerank_scan_results_v109(
            locked_results,
            ocr_text=ocr_signal_text,
            quality=quality,
            scan_metadata=scan_metadata,
        )
        # Stufen bleiben hart gesperrt; innerhalb einer Stufe entscheiden Exaktheit,
        # Kartendaten-Gegenprüfung und Ensemblewert.
        locked_results.sort(
            key=lambda item: (
                bool(item.get("exact")),
                not bool(item.get("metadata_severe_conflict")),
                float(item.get("metadata_score") or 0.0),
                float(item.get("score") or 0.0),
                float(item.get("artwork_similarity") or 0.0),
            ),
            reverse=True,
        )
        best = locked_results[0] if locked_results else None
        alternatives = []
        if best:
            best_card_id = str(get_card_id(best.get("card") or {}) or "")
            best_set_code = str((best.get("set_item") or {}).get("set_code") or "")
            for item in locked_results[1:]:
                if len(alternatives) >= int(max_alternatives or 4):
                    break
                card_id = str(get_card_id(item.get("card") or {}) or "")
                set_code = str((item.get("set_item") or {}).get("set_code") or "")
                if card_id == best_card_id and set_code == best_set_code:
                    continue
                alternatives.append(item)
            confidence, reason = self.compute_scan_confidence(best, quality=quality, alternatives=alternatives)
            best["confidence"] = confidence
            best["confidence_reason"] = reason
            for alt in alternatives:
                alt_conf, alt_reason = self.compute_scan_confidence(alt, quality=quality, alternatives=[])
                alt["confidence"] = alt_conf
                alt["confidence_reason"] = alt_reason
        for item in locked_results:
            item.pop("_evidence_signatures", None)
        return best, tried, alternatives

    def _find_best_scan_match_for_candidates(self, candidates, scan_path="", quality=None):
        """Kompatibilitäts-Wrapper für bestehende Aufrufe."""
        best, tried, _alternatives = self._find_scan_matches_for_candidates(
            candidates,
            scan_path=scan_path,
            quality=quality,
            include_artwork=False,
            max_alternatives=0,
        )
        return best, tried

    def ocr_scan_image(self, path, callback, deadline_at=None):
        """Zeitbegrenzte ML-Kit-OCR. Schnell/Normal lesen Latin; Gründlich nutzt bei Bedarf Zusatzmodelle."""
        config = self.scan_mode_config()
        if deadline_at is None:
            deadline_at = time.perf_counter() + float(config.get("hard_timeout_seconds") or 10.0)
        if platform == "android":
            scripts = ["latin"]
            if bool(getattr(self, "_gallery_scan_active", False)) or str(getattr(self, "scan_mode", "normal")).lower() == "gründlich":
                scripts.extend(["japanese", "korean", "chinese", "devanagari"])
            texts = []
            errors = []

            def run_script(index):
                if index >= len(scripts) or time.perf_counter() >= deadline_at:
                    combined = "\n\n".join(texts)
                    timeout_msg = "Zeitbudget erreicht." if time.perf_counter() >= deadline_at and not combined else ""
                    callback(combined, "; ".join(errors) if not combined else timeout_msg)
                    return
                script = scripts[index]

                def after(text, error=""):
                    if text and str(text).strip():
                        texts.append(str(text))
                        try:
                            if self.parse_scan_ocr_candidates(text):
                                callback("\n\n".join(texts), "")
                                return
                        except Exception:
                            pass
                    if error:
                        errors.append(f"{script}: {error}")
                    run_script(index + 1)

                try:
                    self._ocr_scan_image_android_mlkit(path, after, script=script)
                except Exception as exc:
                    errors.append(f"{script}: {exc}")
                    run_script(index + 1)

            run_script(0)
            return

        def worker():
            texts = []
            errors = []
            # EasyOCR/PaddleOCR sind optionale Desktop-/Server-Fallbacks.
            try:
                optional = optional_ocr_bundle(path, languages=("en", "de", "fr", "es", "it", "pt"))
                for engine, value in optional.items():
                    if engine.endswith("_error"):
                        errors.append(f"{engine}: {value}")
                    elif value and str(value).strip():
                        texts.append(str(value).strip())
            except Exception as exc:
                errors.append("Optionale OCR: " + str(exc))
            try:
                from PIL import Image as PILImage
                import pytesseract
                image = PILImage.open(path)
                remaining = max(1, int(deadline_at - time.perf_counter()))
                text = pytesseract.image_to_string(image, lang="eng+deu", timeout=remaining)
                if text and str(text).strip():
                    texts.append(str(text).strip())
            except Exception as exc:
                errors.append("Tesseract: " + str(exc))
            combined = "\n\n".join(dict.fromkeys(texts))
            message = "" if combined else "OCR-Modul ist nicht verfügbar oder konnte das Bild nicht lesen: " + "; ".join(errors)
            Clock.schedule_once(lambda *_: callback(combined, message), 0)
        threading.Thread(target=worker, daemon=True).start()

    def _ocr_scan_image_android_mlkit(self, path, callback, script="latin"):
        from jnius import autoclass, PythonJavaClass, java_method

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        File = autoclass("java.io.File")
        Uri = autoclass("android.net.Uri")
        InputImage = autoclass("com.google.mlkit.vision.common.InputImage")
        TextRecognition = autoclass("com.google.mlkit.vision.text.TextRecognition")

        script = str(script or "latin").lower()
        if script == "chinese":
            Builder = autoclass("com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions$Builder")
            options = Builder().build()
        elif script == "devanagari":
            Builder = autoclass("com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions$Builder")
            options = Builder().build()
        elif script == "japanese":
            Builder = autoclass("com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions$Builder")
            options = Builder().build()
        elif script == "korean":
            Builder = autoclass("com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions$Builder")
            options = Builder().build()
        else:
            TextRecognizerOptions = autoclass("com.google.mlkit.vision.text.latin.TextRecognizerOptions")
            options = TextRecognizerOptions.DEFAULT_OPTIONS

        activity = PythonActivity.mActivity
        uri = Uri.fromFile(File(path))
        image = InputImage.fromFilePath(activity, uri)
        recognizer = TextRecognition.getClient(options)

        class SuccessListener(PythonJavaClass):
            __javainterfaces__ = ["com/google/android/gms/tasks/OnSuccessListener"]
            __javacontext__ = "app"

            @java_method("(Ljava/lang/Object;)V")
            def onSuccess(self, result):
                try:
                    recognized_text = result.getText()
                except Exception:
                    recognized_text = ""
                try:
                    recognizer.close()
                except Exception:
                    pass
                Clock.schedule_once(lambda *_: callback(recognized_text, ""), 0)

        class FailureListener(PythonJavaClass):
            __javainterfaces__ = ["com/google/android/gms/tasks/OnFailureListener"]
            __javacontext__ = "app"

            @java_method("(Ljava/lang/Exception;)V")
            def onFailure(self, exc):
                try:
                    msg = exc.getMessage()
                except Exception:
                    msg = str(exc)
                try:
                    recognizer.close()
                except Exception:
                    pass
                Clock.schedule_once(lambda *_: callback("", "OCR fehlgeschlagen: " + str(msg)), 0)

        if not hasattr(self, "_ocr_listener_refs"):
            self._ocr_listener_refs = []
        success_listener = SuccessListener()
        failure_listener = FailureListener()
        self._ocr_listener_refs.extend([success_listener, failure_listener])
        self._ocr_listener_refs = self._ocr_listener_refs[-24:]
        task = recognizer.process(image)
        task.addOnSuccessListener(success_listener)
        task.addOnFailureListener(failure_listener)

    def apply_scanner_search(self, value):
        cleaned = value.strip()
        upper = cleaned.upper().replace("_", "-").replace("/", "-")
        digits = re.sub(r"\D+", "", cleaned)
        set_match = re.search(r"\b[A-Z0-9]{2,8}[\s\-]*(?:DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA)?[\s\-]*\d{1,4}\b", upper)
        previous_language = self.language_spinner.text if hasattr(self, "language_spinner") else "Englisch"
        self.clear_filters()
        self.language_spinner.text = previous_language if previous_language in LANGUAGES else "Englisch"
        # Set-Code + Kartennummer hat auch bei manueller Scanner-Übernahme Priorität vor Passcode.
        if set_match:
            code = re.sub(r"\s+", "-", set_match.group(0)).replace("--", "-")
            self.set_input.text = code
            language_code = language_code_from_set_code(code)
            if language_code is not None:
                label = strict_language_label(language_code)
                if label in LANGUAGES:
                    self.language_spinner.text = label
            self.set_status(f"Scanner-Suche nach Set-Code {code} ({self.language_spinner.text})...")
        elif digits and len(digits) >= 4 and len(digits) >= len(cleaned.replace(" ", "")) - 1:
            self.card_id_input.text = digits
            self.set_status(f"Scanner-Suche nach Karten-ID {digits} ohne erzwungene Sprache...")
        else:
            language_code = detect_script_language(cleaned)
            if language_code is not None:
                label = strict_language_label(language_code)
                if label in LANGUAGES:
                    self.language_spinner.text = label
            self.name_input.text = cleaned
            self.set_status(f"Scanner-Suche nach Name: {cleaned} ({self.language_spinner.text})...")
        self.start_search()


    def _scan_result_filters_from_value(self, value):
        """Erzeugt sichere Suchfilter für Scanner-/OCR-Ergebnisse."""
        cleaned = str(value or "").strip()
        upper = cleaned.upper().replace("_", "-").replace("/", "-")
        digits = re.sub(r"\D+", "", cleaned)
        set_match = re.search(r"\b[A-Z0-9]{2,10}[\s\-]*(?:DE|EN|FR|IT|PT|ES|SP|JP|KR|AE|EU|NA)?[\s\-]*\d{1,4}\b", upper)
        filters = {
            "name": "", "card_id": "", "set": "", "atk": "", "def": "", "level": "",
            "race": "", "attribute": "", "group": "Alle", "language": "de",
        }
        kind = "Name"
        if set_match:
            code = re.sub(r"\s+", "-", set_match.group(0)).replace("--", "-")
            filters["set"] = code
            kind = "Set-Code"
            cleaned = code
        elif digits and len(digits) >= 4 and len(digits) >= len(cleaned.replace(" ", "")) - 1:
            filters["card_id"] = digits
            kind = "Passcode"
            cleaned = digits
        else:
            filters["name"] = cleaned
        return filters, kind, cleaned

    def _best_card_from_scan_matches(self, cards, query_value):
        """Wählt aus OCR-Suchergebnissen möglichst die exakt passende Karte."""
        query = str(query_value or "").strip()
        if not cards:
            return None, None
        set_item = None
        ranked = []
        for card in cards:
            try:
                score = 0
                if query and card_matches_set_query(card, query):
                    score += 100
                if query and normalize_search_text(query) == normalize_search_text(card.get("name", "")):
                    score += 60
                if get_image_url(card):
                    score += 10
                if card.get("card_sets"):
                    score += 5
                ranked.append((score, card))
            except Exception:
                continue
        if not ranked:
            return cards[0], None
        ranked.sort(key=lambda item: item[0], reverse=True)
        best = ranked[0][1]
        try:
            set_item = choose_set_item_for_query(best, query)
            if not set_item:
                sets = dedupe_card_sets_for_display(best.get("card_sets") or [], query)
                if len(sets) == 1:
                    set_item = sets[0]
        except Exception:
            set_item = None
        return best, set_item

    def start_bulk_gallery_ocr_import(self, image_paths, initial_results=None, initial_errors=None):
        """Verarbeitet Galerie-Bilder mit Kartenrahmen-, Mehrkarten- und OCR-Scan.

        Im gründlichen Modus kann ein einzelnes Bild mehrere Karten liefern. Jede
        erkannte Kartenfläche wird separat begradigt, bewertet, per OCR gelesen und
        in allen verfügbaren Sprachen gesucht. Ein Fehler stoppt nie den Rest.
        """
        paths = [p for p in (image_paths or []) if p]
        if not paths:
            self.show_error("Keine Bilder", "Es wurden keine Bilder für den Sammelimport übergeben.")
            return

        # Jede Quelle erhält eine vollständig eigene Scan-Session und eine
        # unveränderliche Vorschaukopie. Weder OCR-Kandidaten noch Artworks,
        # Alternativen oder Fehlerbilder werden zwischen Quellen geteilt.
        queue_id = "scan_" + time.strftime("%Y%m%d_%H%M%S") + "_" + hashlib.sha1(
            ("|".join(map(str, paths)) + f"|{time.time_ns()}").encode("utf-8", "ignore")
        ).hexdigest()[:10]
        source_records = build_preview_records(
            paths,
            os.path.join(self.user_data_dir, "scan_source_previews"),
            batch_id=queue_id,
        )
        source_record_by_id = {record["source_id"]: record for record in source_records}

        # Galerie besitzt ausschließlich den gründlichen Präzisionsmodus.
        # Die Einstellung für Live/Kamera wird nicht verändert.
        self._gallery_scan_active = True
        scan_started_at = time.perf_counter()
        self.active_scan_queue_id = queue_id
        try:
            self.app_db.save_scan_queue(queue_id, {
                "paths": paths,
                "scan_mode": GALLERY_SCAN_MODE,
                "status": "gestartet",
                "current": 0,
                "created_at": time.time(),
            })
        except Exception:
            pass
        schedule_android_scan_resume_worker(queue_id)

        config = self.scan_mode_config("gallery")
        max_attempts_total = max(1, min(3, int(config.get("max_attempts") or 3)))
        # Tiefe Kopien verhindern, dass spätere Auswahländerungen an einem Bild
        # versehentlich Karten-/Artwork-Daten eines anderen Bildes verändern.
        results = copy.deepcopy(list(initial_results or []))
        errors = copy.deepcopy(list(initial_errors or []))
        scan_units = []
        state = {
            "paused": False,
            "cancelled": False,
            "finished": False,
            "current": 0,
            "prepared_sources": 0,
        }

        def persist_queue(status="läuft"):
            try:
                self.app_db.save_scan_queue(queue_id, {
                    "paths": paths,
                    "scan_mode": GALLERY_SCAN_MODE,
                    "status": status,
                    "current": int(state.get("current") or 0),
                    "prepared_sources": int(state.get("prepared_sources") or 0),
                    "total_units": len(scan_units),
                    "recognized": len(results),
                    "errors": len(errors),
                    "updated_at": time.time(),
                })
            except Exception:
                pass

        progress_box = SurfaceBox(orientation="vertical", padding=dp(12), spacing=dp(8), bg_color=PANEL_BG)
        progress_label = DarkLabel(
            text=(
                f"[b]Sammel-Scan wird vorbereitet[/b]\n"
                f"Modus: {html_escape(config.get('label', 'Normal'))} • {len(paths)} Ausgangsbild(er) • Multi-Engine: YOLO/MediaPipe/OpenCV + ML Kit/Paddle/EasyOCR • maximal {max_attempts_total} Scan-Versuch(e) je Kartenfläche."
            ),
            markup=True,
            color=TEXT,
        )
        progress_box.add_widget(progress_label)
        control_cols = 1 if self.ui_width_below(520) else 3
        controls = GridLayout(cols=control_cols, size_hint_y=None, height=dp(50 if control_cols > 1 else 150), spacing=dp(8))
        pause_btn = DarkButton(text="Pause", bg=ACCENT_2)
        interim_btn = DarkButton(text="Zwischenergebnisse", bg=INPUT_BG_2)
        cancel_btn = DarkButton(text="Abbrechen", bg=DANGER)
        controls.add_widget(pause_btn)
        controls.add_widget(interim_btn)
        controls.add_widget(cancel_btn)
        progress_box.add_widget(controls)
        progress_popup = self.make_inline_page("scan_progress", progress_box, back_to="scanner")

        def stats_text(message=""):
            processed = int(state.get("current") or 0)
            total = len(scan_units)
            uncertain = sum(1 for item in results if int(item.get("confidence") or 0) < 75)
            remaining = max(0, total - processed)
            return (
                f"[b]Sammel-Scan {('pausiert' if state.get('paused') else 'läuft')}[/b]\n"
                f"Kartenflächen: {processed}/{total or '?'} • erkannt: {len(results)} • unsicher: {uncertain} • Fehler: {len(errors)} • offen: {remaining}\n"
                f"{html_escape(str(message or ''))}"
            )

        def update_progress(message=""):
            try:
                progress_label.text = stats_text(message)
            except Exception:
                pass
            persist_queue("pausiert" if state.get("paused") else ("abbruch" if state.get("cancelled") else "läuft"))

        def show_interim(*_):
            lines = [
                f"Modus: {config.get('label', 'Normal')}",
                f"Vorbereitete Kartenflächen: {len(scan_units)}",
                f"Verarbeitet: {state.get('current', 0)}",
                f"Erkannt: {len(results)}",
                f"Unsicher: {sum(1 for item in results if int(item.get('confidence') or 0) < 75)}",
                f"Fehler: {len(errors)}",
                "",
            ]
            for item in results[-15:]:
                card = item.get("card") or {}
                lines.append(f"• {card.get('name', 'Unbekannt')} – {int(item.get('confidence') or 0)} %")
            self.show_scroll_text("Zwischenergebnisse", "\n".join(lines))

        def toggle_pause(*_):
            state["paused"] = not bool(state.get("paused"))
            pause_btn.text = "Fortsetzen" if state["paused"] else "Pause"
            update_progress("Scan wurde pausiert." if state["paused"] else "Scan wird fortgesetzt.")

        def cancel_scan(*_):
            state["cancelled"] = True
            state["paused"] = False
            update_progress("Scan wird nach dem aktuellen OCR-Schritt beendet. Bisherige Ergebnisse bleiben erhalten.")

        pause_btn.bind(on_release=toggle_pause)
        interim_btn.bind(on_release=show_interim)
        cancel_btn.bind(on_release=cancel_scan)
        progress_popup.open()

        def finish_all(cancelled=False):
            if state.get("finished"):
                return
            state["finished"] = True
            try:
                self.app_db.complete_scan_queue(queue_id)
            except Exception:
                pass
            cancel_android_scan_resume_worker(queue_id)
            self.active_scan_queue_id = ""
            self._gallery_scan_active = False
            self.record_performance("bulk_scan", scan_started_at, {
                "images": len(paths),
                "regions": len(scan_units),
                "recognized": len(results),
                "errors": len(errors),
                "cancelled": bool(cancelled),
                "mode": GALLERY_SCAN_MODE,
            })
            try:
                progress_popup.dismiss()
            except Exception:
                pass
            if cancelled and not results and not errors:
                self.show_info("Sammel-Scan abgebrochen", "Der Scan wurde beendet, bevor Ergebnisse vorlagen.")
                return
            if results:
                android_haptic_feedback(35)
            self.show_bulk_gallery_review_popup(results, errors)

        def prepare_worker():
            for source_record in source_records:
                if state.get("cancelled"):
                    break
                source_index = int(source_record.get("source_index") or 0)
                source_id = str(source_record.get("source_id") or "")
                source_path = str(source_record.get("path") or "")
                preview_path = str(source_record.get("preview_path") or source_path)
                try:
                    regions = self.prepare_scan_regions(source_path, mode=GALLERY_SCAN_MODE)
                    if not regions:
                        errors.append({
                            "source_id": source_id,
                            "source_index": source_index,
                            "batch_id": queue_id,
                            "path": source_path,
                            "preview_path": preview_path,
                            "value": "",
                            "error": "Keine verwertbare Kartenfläche erkannt.",
                            "quality": self.analyze_scan_image_quality(source_path),
                        })
                    else:
                        # Jede Kartenfläche erbt ausschließlich Daten ihrer eigenen
                        # Bildquelle. Die Datensätze werden kopiert, nicht geteilt.
                        for region in regions:
                            isolated_region = copy.deepcopy(region)
                            isolated_region.update({
                                "source_id": source_id,
                                "source_index": source_index,
                                "batch_id": queue_id,
                                "source_path": source_path,
                                "source_preview_path": preview_path,
                                "preview_path": str(region.get("raw_path") or region.get("path") or preview_path),
                                "region_session_id": str(region.get("region_session_id") or stable_region_session_id(source_id, region.get("bbox"), int(region.get("region_index") or 1))),
                                "detector": str(region.get("detector") or "unknown"),
                                "detectors": list(region.get("detectors") or [region.get("detector") or "unknown"]),
                                "detection_score": float(region.get("detection_score") or 0.0),
                            })
                            scan_units.append(isolated_region)
                except Exception as exc:
                    errors.append({
                        "source_id": source_id,
                        "source_index": source_index,
                        "batch_id": queue_id,
                        "path": source_path,
                        "preview_path": preview_path,
                        "value": "",
                        "error": f"Bild konnte nicht vorbereitet werden: {exc}",
                        "quality": self.analyze_scan_image_quality(source_path),
                    })
                state["prepared_sources"] = source_index
                persist_queue("vorbereiten")
                Clock.schedule_once(
                    lambda *_args, si=source_index: update_progress(f"Bild {si}/{len(source_records)} wird vollständig und getrennt ausgewertet..."),
                    0,
                )
            Clock.schedule_once(lambda *_: process_unit(0), 0)

        def process_unit(index):
            if state.get("finished"):
                return
            if state.get("cancelled"):
                finish_all(cancelled=True)
                return
            if state.get("paused"):
                Clock.schedule_once(lambda *_: process_unit(index), 0.35)
                return
            if index >= len(scan_units):
                finish_all(cancelled=False)
                return

            state["current"] = index
            unit = scan_units[index]
            raw_path = unit.get("raw_path") or unit.get("path") or unit.get("source_path")
            rectified_path = unit.get("rectified_path") or raw_path
            original_path = raw_path
            source_path = unit.get("source_path") or original_path
            source_id = str(unit.get("source_id") or f"{queue_id}_unit_{index + 1}")
            source_index = int(unit.get("source_index") or (index + 1))
            source_preview_path = str(unit.get("source_preview_path") or source_path)
            preview_path = str(unit.get("preview_path") or raw_path)
            quality = copy.deepcopy(unit.get("quality") or self.analyze_scan_image_quality(raw_path, unit.get("coverage", 1.0)))
            # RAW zuerst, dann Rectified, danach Originalbild. Jede Kartenfläche
            # behält ihre eigene Retry-Kette und teilt keine Bildzustände.
            retry_paths = []
            for candidate_path in (raw_path, rectified_path, source_path):
                candidate_path = str(candidate_path or "")
                if candidate_path and candidate_path not in retry_paths and os.path.exists(candidate_path):
                    retry_paths.append(candidate_path)
                if len(retry_paths) >= max_attempts_total:
                    break
            if len(retry_paths) < max_attempts_total:
                try:
                    for candidate_path in self._create_ocr_retry_images(raw_path, max_extra_attempts=max_attempts_total - len(retry_paths)):
                        if candidate_path not in retry_paths:
                            retry_paths.append(candidate_path)
                except Exception:
                    pass
            retry_paths = retry_paths[:max_attempts_total] or [raw_path]
            attempt_errors = []
            last_ocr_text = ""
            unit_started_at = time.perf_counter()
            unit_deadline = ScanDeadlineV100.start(float(config.get("hard_timeout_seconds") or 10.0))
            unit_success = {"value": False}

            def isolated_result_payload(best, attempt_path, attempt_number, kind_override=None, value_override=None, alternatives=None, language_label_override=None, extra=None):
                """Baut einen unveränderlichen Ergebnisdatensatz nur für diese Bildquelle."""
                best = copy.deepcopy(best or {})
                candidate = copy.deepcopy(best.get("candidate") or {})
                card = copy.deepcopy(best.get("card") or {})
                set_item = copy.deepcopy(best.get("set_item") or {})
                alt_items = copy.deepcopy(list(alternatives if alternatives is not None else (best.get("alternatives") or [])))
                art_similarity = best.get("artwork_similarity")
                payload = {
                    "result_id": f"{source_id}_r{int(unit.get('region_index') or 1)}_a{int(attempt_number)}_{time.time_ns()}",
                    "source_id": source_id,
                    "source_index": source_index,
                    "batch_id": queue_id,
                    "region_session_id": str(unit.get("region_session_id") or stable_region_session_id(source_id, unit.get("bbox"), int(unit.get("region_index") or 1))),
                    "detector": str(unit.get("detector") or "unknown"),
                    "detectors": list(unit.get("detectors") or [unit.get("detector") or "unknown"]),
                    "detection_score": float(unit.get("detection_score") or 0.0),
                    "path": raw_path,
                    "raw_path": raw_path,
                    "rectified_path": rectified_path,
                    "source_path": source_path,
                    "source_preview_path": source_preview_path,
                    "preview_path": preview_path,
                    "scan_path": raw_path,
                    "attempt_path": attempt_path,
                    "region_index": int(unit.get("region_index") or 1),
                    "detected_regions": int(unit.get("detected_regions") or 1),
                    "attempt": int(attempt_number),
                    "value": value_override if value_override is not None else candidate.get("value", ""),
                    "kind": kind_override or candidate.get("kind", "Name"),
                    "card": card,
                    "set_item": set_item,
                    "matches": best.get("matches", 0),
                    "language": best.get("language", ""),
                    "language_label": language_label_override or best.get("language_label", scan_language_label(best.get("language", ""))),
                    "score": best.get("score", 0),
                    "confidence": int(best.get("confidence") or 0),
                    "confidence_reason": str(best.get("confidence_reason") or ""),
                    "artwork_similarity": art_similarity,
                    "artwork_identity_key": artwork_identity_key(card),
                    "artwork_verified": bool(card.get("_artwork_verified")) or (art_similarity is not None and float(art_similarity) >= 0.74),
                    "scan_metadata": copy.deepcopy(best.get("scan_metadata") or {}),
                    "metadata_score": float(best.get("metadata_score") or 0.0),
                    "metadata_matches": list(best.get("metadata_matches") or []),
                    "metadata_conflicts": list(best.get("metadata_conflicts") or []),
                    "metadata_comparable": int(best.get("metadata_comparable") or 0),
                    "search_stage": int(best.get("search_stage") if best.get("search_stage") is not None else identifier_stage(candidate.get("kind"))),
                    "alternatives": alt_items,
                    "quality": copy.deepcopy(quality),
                    "selected": True,
                }
                if extra:
                    payload.update(copy.deepcopy(extra))
                return payload

            def isolated_error_payload(message, value=""):
                return {
                    "error_id": f"{source_id}_e{int(unit.get('region_index') or 1)}_{time.time_ns()}",
                    "source_id": source_id,
                    "source_index": source_index,
                    "batch_id": queue_id,
                    "region_session_id": str(unit.get("region_session_id") or stable_region_session_id(source_id, unit.get("bbox"), int(unit.get("region_index") or 1))),
                    "detector": str(unit.get("detector") or "unknown"),
                    "detectors": list(unit.get("detectors") or [unit.get("detector") or "unknown"]),
                    "detection_score": float(unit.get("detection_score") or 0.0),
                    "path": raw_path,
                    "raw_path": raw_path,
                    "rectified_path": rectified_path,
                    "source_path": source_path,
                    "source_preview_path": source_preview_path,
                    "preview_path": preview_path,
                    "scan_path": raw_path,
                    "region_index": int(unit.get("region_index") or 1),
                    "value": value,
                    "error": str(message or "Unbekannter Scanfehler"),
                    "quality": copy.deepcopy(quality),
                }

            def complete_unit():
                self.scan_timings.record(
                    GALLERY_SCAN_MODE, time.perf_counter() - unit_started_at, bool(unit_success.get("value")),
                    source="gallery", details={"attempts": len(attempt_errors) + 1, "quality": int((quality or {}).get("score") or 0)},
                )
                state["current"] = index + 1
                persist_queue("läuft")
                Clock.schedule_once(lambda *_: process_unit(index + 1), 0)

            def process_attempt(attempt_index):
                nonlocal last_ocr_text
                if state.get("cancelled"):
                    complete_unit()
                    return
                if unit_deadline.expired():
                    attempt_errors.append("Zeitbudget erreicht; weitere Versuche wurden beendet")
                    attempt_index = len(retry_paths)
                if attempt_index >= len(retry_paths):
                    # Optionaler letzter Vision-Fallback. Er wird niemals ohne
                    # eigenen API-Key und ausdrückliche Aktivierung ausgeführt.
                    if (bool(getattr(self, "cloud_ai_scan_enabled", False))
                            and bool(getattr(self, "openai_api_key", "").strip())
                            and not bool(unit.get("_cloud_attempted"))):
                        unit["_cloud_attempted"] = True
                        cloud_path = retry_paths[-1] if retry_paths else original_path
                        update_progress("Lokale KI unsicher – optionaler Cloud-Vision-Fallback läuft …")

                        def cloud_done(payload):
                            cloud_candidates = []
                            for kind, field, priority in (
                                ("Set-Code", "set_code", 130), ("Passcode", "passcode", 128),
                                ("Name", "name", 116), ("Effect", "effect_excerpt", 78),
                            ):
                                value = str((payload or {}).get(field) or "").strip()
                                if value:
                                    cloud_candidates.append({"kind": kind, "value": value, "priority": priority, "source": "Cloud-KI"})
                            if not cloud_candidates:
                                attempt_errors.append("Cloud-KI: keine verwertbaren Identifikatoren")
                                Clock.schedule_once(lambda *_: process_attempt(len(retry_paths) + 1), 0)
                                return

                            def cloud_lookup_worker():
                                try:
                                    best, tried, alternatives = self._find_scan_matches_for_candidates(
                                        cloud_candidates, scan_path=cloud_path, quality=quality,
                                        include_artwork=True, max_alternatives=5,
                                        deadline_at=time.perf_counter() + 9.0,
                                    )
                                    if best and best.get("card"):
                                        accepted, acceptance_reason = self._isolated_scan_match_acceptance(best, cloud_candidates)
                                        if accepted:
                                            result_item = isolated_result_payload(
                                                best,
                                                cloud_path,
                                                len(retry_paths) + 1,
                                                alternatives=alternatives,
                                                language_label_override=best.get("language_label", "Cloud-KI"),
                                                extra={"cloud_payload": payload},
                                            )
                                            result_item["confidence_reason"] = "Cloud-KI-Fallback; " + str(best.get("confidence_reason") or acceptance_reason)
                                            results.append(result_item)
                                            unit_success["value"] = True
                                            Clock.schedule_once(lambda *_: complete_unit(), 0)
                                            return
                                        attempt_errors.append("Cloud-KI unsicher: " + acceptance_reason)
                                    attempt_errors.append("Cloud-KI: kein Datenbanktreffer")
                                except Exception as exc:
                                    attempt_errors.append(f"Cloud-KI-Suche: {exc}")
                                Clock.schedule_once(lambda *_: process_attempt(len(retry_paths) + 1), 0)

                            threading.Thread(target=cloud_lookup_worker, daemon=True).start()

                        def cloud_error(message):
                            attempt_errors.append("Cloud-KI: " + str(message))
                            Clock.schedule_once(lambda *_: process_attempt(len(retry_paths) + 1), 0)

                        self.call_openai_scan_vision(cloud_path, cloud_done, cloud_error)
                        return

                    reason = self.scan_failure_reason(
                        quality=quality,
                        ocr_text=last_ocr_text,
                        lookup_attempts=attempt_errors,
                        frame_fallback=bool(unit.get("fallback")),
                    )
                    detail = "; ".join(short_text(item, 150) for item in attempt_errors[-4:])
                    errors.append(isolated_error_payload(f"{reason}. {detail}".strip(" .")))
                    complete_unit()
                    return

                attempt_path = retry_paths[attempt_index]
                update_progress(
                    f"Kartenfläche {index + 1}/{len(scan_units)} • OCR-Versuch {attempt_index + 1}/{len(retry_paths)} • Quelle {os.path.basename(str(source_path))}"
                )

                def after_ocr(ocr_text, ocr_error=""):
                    nonlocal last_ocr_text
                    try:
                        if ocr_text:
                            last_ocr_text = str(ocr_text)
                        candidates = self.parse_scan_ocr_candidates(ocr_text or "")
                        if ocr_error:
                            attempt_errors.append(f"OCR {attempt_index + 1}: {ocr_error}")
                        if not candidates:
                            attempt_errors.append(f"OCR {attempt_index + 1}: Kein Name, Set-Code oder Passcode erkannt")
                            final_attempt = attempt_index >= len(retry_paths) - 1
                            if final_attempt and bool(config.get("artwork")) and not unit_deadline.expired(0.8):
                                def artwork_worker():
                                    suggestions = self._find_cached_artwork_fallback(
                                        attempt_path, max_results=5, deadline_at=unit_deadline.deadline_at
                                    )
                                    if suggestions:
                                        best = copy.deepcopy(suggestions[0])
                                        accepted, acceptance_reason = self._isolated_scan_match_acceptance(best, [])
                                        if accepted:
                                            result_item = isolated_result_payload(
                                                best,
                                                attempt_path,
                                                attempt_index + 1,
                                                kind_override="Artwork",
                                                value_override=(best.get("card") or {}).get("name", ""),
                                                alternatives=suggestions[1:5],
                                                language_label_override=best.get("language_label", "Artwork-Vergleich"),
                                            )
                                            results.append(result_item)
                                            unit_success["value"] = True
                                            Clock.schedule_once(lambda *_: complete_unit(), 0)
                                        else:
                                            attempt_errors.append("Artwork-Fallback unsicher: " + acceptance_reason)
                                            Clock.schedule_once(lambda *_: process_attempt(attempt_index + 1), 0)
                                    else:
                                        Clock.schedule_once(lambda *_: process_attempt(attempt_index + 1), 0)
                                threading.Thread(target=artwork_worker, daemon=True).start()
                                return
                            Clock.schedule_once(lambda *_: process_attempt(attempt_index + 1), 0)
                            return
                        preview = ", ".join(f"{c.get('kind')}: {short_text(c.get('value'), 32)}" for c in candidates[:3])
                        update_progress(f"Suche in allen Sprachen: {preview}")

                        def lookup_worker():
                            try:
                                best, tried, alternatives = self._find_scan_matches_for_candidates(
                                    candidates,
                                    scan_path=attempt_path,
                                    quality=quality,
                                    include_artwork=bool(config.get("artwork")),
                                    max_alternatives=4,
                                    deadline_at=unit_deadline.deadline_at,
                                )
                                if best and best.get("card"):
                                    accepted, acceptance_reason = self._isolated_scan_match_acceptance(best, candidates)
                                    if accepted:
                                        result_item = isolated_result_payload(
                                            best,
                                            attempt_path,
                                            attempt_index + 1,
                                            alternatives=alternatives,
                                        )
                                        results.append(result_item)
                                        unit_success["value"] = True
                                        Clock.schedule_once(lambda *_: complete_unit(), 0)
                                        return
                                    attempt_errors.append("Treffer nicht eindeutig: " + acceptance_reason)
                                attempt_errors.append(
                                    f"Suche {attempt_index + 1}: kein Treffer; geprüft: "
                                    + short_text(", ".join(tried[-10:] if tried else []), 360)
                                )
                            except Exception as exc:
                                attempt_errors.append(f"Suche {attempt_index + 1}: {exc}")
                            Clock.schedule_once(lambda *_: process_attempt(attempt_index + 1), 0)

                        threading.Thread(target=lookup_worker, daemon=True).start()
                    except Exception as exc:
                        attempt_errors.append(f"Interner Scanfehler {attempt_index + 1}: {exc}")
                        Clock.schedule_once(lambda *_: process_attempt(attempt_index + 1), 0)

                try:
                    guided_count = int(config.get("guided_variants") or 0)
                    if attempt_index > 0:
                        guided_count = min(guided_count, 1)
                    self.smart_ocr_scan_image(attempt_path, after_ocr, max_variant_images=guided_count, deadline_at=unit_deadline.deadline_at)
                except Exception as exc:
                    attempt_errors.append(f"OCR konnte nicht gestartet werden: {exc}")
                    Clock.schedule_once(lambda *_: process_attempt(attempt_index + 1), 0)

            process_attempt(0)

        threading.Thread(target=prepare_worker, daemon=True).start()

    def show_bulk_gallery_review_popup(self, results, errors):
        """Prüffenster für erkannte, unsichere und fehlgeschlagene Scans."""
        results = list(results or [])
        errors = list(errors or [])

        # v11.2.3: Keine Gruppierung über verschiedene Bildquellen mehr. Jeder
        # Galerie-Import bleibt als eigenständiger Prüfeintrag mit genau seinem
        # Vorschaubild, Scan-Crop, Artwork und seinen Kandidaten erhalten.
        grouped_results = []
        identity_counts = {}
        for raw_index, raw_item in enumerate(results, start=1):
            try:
                clone = copy.deepcopy(raw_item or {})
                clone["result_id"] = str(clone.get("result_id") or f"review_result_{raw_index}_{time.time_ns()}")
                clone["source_id"] = str(clone.get("source_id") or f"legacy_source_{raw_index}")
                clone["source_index"] = int(clone.get("source_index") or raw_index)
                clone["count"] = max(1, int(clone.get("count") or 1))
                clone["selected"] = bool(clone.get("selected", True))
                clone["source_results"] = [copy.deepcopy(raw_item or {})]
                clone["paths"] = [str(clone.get("path") or "")]
                clone["scan_paths"] = [str(clone.get("scan_path") or "")]
                clone["preview_paths"] = [str(clone.get("preview_path") or clone.get("path") or "")]
                clone["values"] = [str(clone.get("value") or "")]
                card = clone.get("card") or {}
                set_item = clone.get("set_item") or {}
                selected_card = apply_collection_set_to_card(card, set_item or get_collection_set_from_card(card) or {})
                identity_key = collection_key_for(selected_card) + "__scanart_" + normalize_collection_key(artwork_identity_key(card))
                clone["review_identity_key"] = identity_key
                identity_counts[identity_key] = identity_counts.get(identity_key, 0) + 1
                grouped_results.append(clone)
            except Exception as exc:
                errors.append({
                    "source_id": str((raw_item or {}).get("source_id") or f"legacy_source_{raw_index}") if isinstance(raw_item, dict) else f"legacy_source_{raw_index}",
                    "source_index": raw_index,
                    "path": (raw_item or {}).get("path", "") if isinstance(raw_item, dict) else "",
                    "preview_path": (raw_item or {}).get("preview_path", "") if isinstance(raw_item, dict) else "",
                    "value": (raw_item or {}).get("value", "") if isinstance(raw_item, dict) else "",
                    "error": f"Einzeldarstellung fehlgeschlagen: {exc}",
                })
        for item in grouped_results:
            item["duplicate_count"] = int(identity_counts.get(item.get("review_identity_key"), 1))
        results = grouped_results

        wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        uncertain_count = sum(1 for item in grouped_results if int(item.get("confidence") or 0) < 75)
        header = AutoHeightLabel(
            text=(
                f"[b]Galerie-Sammelimport prüfen[/b]\n"
                f"[color={markup_hex(MUTED)}]{len(grouped_results)} einzeln geprüfte Bild-/Kartenflächen • {uncertain_count} unsicher • {len(errors)} Fehler[/color]"
            ),
            markup=True,
            min_height=dp(58),
            height_padding=dp(14),
            font_size=ui_font_px(15, body=True),
            color=TEXT,
        )
        close_top = DarkButton(text="", size_hint=(None, None), width=0, height=0, opacity=0, disabled=True)
        wrapper.add_widget(header)

        note = AutoHeightLabel(
            text=f"[color={markup_hex(MUTED)}]Jedes ausgewählte Bild wird separat angezeigt und behält seine eigene Vorschau, OCR, Karte und Artwork-Zuordnung. Unsichere Treffer bitte kontrollieren.[/color]",
            markup=True,
            min_height=dp(48),
            height_padding=dp(12),
            font_size=ui_font_px(11.5, body=True),
            color=TEXT,
        )
        wrapper.add_widget(note)

        filter_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        filter_row.add_widget(DarkLabel(text="Prüfansicht:", color=MUTED, size_hint_x=None, width=dp(112)))
        review_filter_spinner = DarkSpinner(text="Alle", values=["Alle", "Nur unsicher", "Nur Fehler", "Nur Duplikate", "Nur deaktiviert"])
        filter_row.add_widget(review_filter_spinner)
        wrapper.add_widget(filter_row)
        review_rows = []

        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"], do_scroll_x=False)
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        if grouped_results:
            grid.add_widget(DarkLabel(text="[b]Gefundene Karten[/b]", markup=True, size_hint_y=None, height=dp(30), color=TEXT))

        for idx, item in enumerate(grouped_results, start=1):
            card = item.get("card") or {}
            set_item = item.get("set_item") or {}
            confidence = int(item.get("confidence") or 0)
            quality = item.get("quality") or {}
            row = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(390), padding=dp(8), spacing=dp(6), bg_color=CARD_BG)

            top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(116), spacing=dp(8))
            check = CheckBox(active=bool(item.get("selected", True)), size_hint_x=None, width=dp(38))
            top.add_widget(check)
            # Linke Vorschau: exakt die Kartenfläche dieser Scan-Session. Rechte
            # Vorschau: das zugeordnete Karten-Artwork. Das Quellbild bleibt
            # separat gespeichert und kann keine andere Zeile überschreiben.
            thumb_candidates = [item.get("raw_path", ""), item.get("preview_path", ""), item.get("scan_path", ""), item.get("path", "")]
            thumb_path = next((str(candidate) for candidate in thumb_candidates if candidate), "")
            preview = Image(
                source=thumb_path if thumb_path and os.path.exists(thumb_path) else (resource_find(PREVIEW_PLACEHOLDER_FILE) or ""),
                allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(68),
                size_hint_y=None, height=dp(116),
            )
            top.add_widget(preview)
            matched_artwork_preview = AsyncImage(
                source=get_image_url(card) or (resource_find(PREVIEW_PLACEHOLDER_FILE) or ""),
                allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(68),
                size_hint_y=None, height=dp(116),
            )
            top.add_widget(matched_artwork_preview)
            info_label = AutoHeightLabel(
                markup=True, color=TEXT, min_height=dp(116), height_padding=dp(8),
                font_size=ui_font_px(11.5, body=True),
            )
            top.add_widget(info_label)
            row.add_widget(top)

            edit_grid = GridLayout(cols=1, size_hint_y=None, height=self.grid_height(8, 1, dp(48), dp(6)), spacing=dp(6))

            candidate_map = {}
            current_entry = {
                "card": card,
                "set_item": set_item,
                "language": item.get("language", ""),
                "language_label": item.get("language_label", scan_language_label(item.get("language", ""))),
                "confidence": confidence,
                "confidence_reason": item.get("confidence_reason", ""),
            }
            candidate_entries = [current_entry] + list(item.get("alternatives") or [])
            candidate_values = []
            for candidate_index, candidate_entry in enumerate(candidate_entries):
                candidate_card = candidate_entry.get("card") or {}
                candidate_set = candidate_entry.get("set_item") or {}
                candidate_conf = int(candidate_entry.get("confidence") or (confidence if candidate_index == 0 else 0))
                label = f"{candidate_card.get('name', 'Unbekannt')} | {candidate_set.get('set_code', '-') or '-'} | {candidate_conf} %"
                if label in candidate_map:
                    label += f" #{candidate_index + 1}"
                candidate_map[label] = candidate_entry
                candidate_values.append(label)
            candidate_spinner = DarkSpinner(text=candidate_values[0] if candidate_values else "Keine Alternative", values=candidate_values or ["Keine Alternative"])
            edit_grid.add_widget(candidate_spinner)

            set_map = {}
            set_values = []
            for set_candidate in dedupe_card_sets_for_display(card.get("card_sets") or [], ""):
                label = f"{set_candidate.get('set_code', '-') or '-'} | {set_candidate.get('set_rarity', '-') or '-'}"
                if label not in set_map:
                    set_map[label] = set_candidate
                    set_values.append(label)
            current_set_label = f"{set_item.get('set_code', '-') or '-'} | {set_item.get('set_rarity', '-') or '-'}"
            if current_set_label not in set_map:
                set_map[current_set_label] = set_item
                set_values.insert(0, current_set_label)
            set_spinner = DarkSpinner(text=current_set_label, values=set_values or [current_set_label])
            edit_grid.add_widget(set_spinner)

            artwork_variants = expand_artwork_variants([card]) or [card]
            artwork_map = {}
            artwork_values = []
            for artwork_card in artwork_variants:
                label = artwork_label(artwork_card)
                if label not in artwork_map:
                    artwork_map[label] = artwork_card
                    artwork_values.append(label)
            current_art_label = artwork_label(card)
            artwork_spinner = DarkSpinner(text=current_art_label, values=artwork_values or [current_art_label])
            edit_grid.add_widget(artwork_spinner)

            language_values = [scan_language_label(code) for code in SCAN_SEARCH_LANGUAGE_CODES]
            language_spinner = DarkSpinner(text=item.get("language_label") or scan_language_label(item.get("language", "")), values=language_values)
            edit_grid.add_widget(language_spinner)
            condition_spinner = DarkSpinner(text=str(item.get("condition") or "Near Mint"), values=list(CARD_CONDITIONS_V104))
            edition_spinner = DarkSpinner(text=str(item.get("edition") or "Unbekannt"), values=list(EDITION_OPTIONS_V104))
            edit_grid.add_widget(condition_spinner)
            edit_grid.add_widget(edition_spinner)

            amount_input = DarkInput(text=str(max(1, int(item.get("count") or 1))), hint_text="Menge")
            amount_input.input_filter = "int"
            edit_grid.add_widget(amount_input)
            manual_btn = DarkButton(text="Karte manuell suchen", bg=ACCENT_2)
            edit_grid.add_widget(manual_btn)
            row.add_widget(edit_grid)
            self.bind_adaptive_grid(edit_grid, 8, min_item_dp=245, max_cols=2, min_cols=1, row_height=dp(48), gap_px=dp(6))

            state_label = AutoHeightLabel(
                markup=True, min_height=dp(44), height_padding=dp(10),
                font_size=ui_font_px(11, body=True), color=TEXT,
            )
            row.add_widget(state_label)
            result_review_entry = {"row": row, "kind": "result", "item": item, "default_height": row.height}

            def sync_result_card_height(*_args, _row=row, _top=top, _preview=preview, _matched=matched_artwork_preview, _info=info_label, _edit=edit_grid, _state=state_label, _entry=result_review_entry):
                try:
                    _top.height = max(float(_preview.height), float(_matched.height), float(_info.height))
                    _row.height = float(_top.height) + float(_edit.height) + float(_state.height) + dp(42)
                    if float(_row.opacity) > 0:
                        _entry["default_height"] = float(_row.height)
                except Exception:
                    pass

            info_label.bind(height=sync_result_card_height)
            edit_grid.bind(height=sync_result_card_height)
            state_label.bind(height=sync_result_card_height)
            Clock.schedule_once(sync_result_card_height, 0)

            def refresh_info(_item=item, _info=info_label, _state=state_label, _check=check, _amount=amount_input, _idx=idx, _matched=matched_artwork_preview):
                current_card = _item.get("card") or {}
                try:
                    _matched.source = get_image_url(current_card) or (resource_find(PREVIEW_PLACEHOLDER_FILE) or "")
                except Exception:
                    pass
                current_set = _item.get("set_item") or {}
                conf = int(_item.get("confidence") or 0)
                quality_data = _item.get("quality") or {}
                confidence_color = "5EDB93" if conf >= 85 else "F0C45C" if conf >= 70 else "F07A7A"
                first_value = ((_item.get("values") or []) + [_item.get("value", "")])[0]
                detected_kind = str(_item.get("kind", ""))
                display_value = "Effekttext als Zusatzsignal" if detected_kind == "Effect" else short_text(first_value, 76)
                source_no = int(_item.get("source_index") or _idx)
                region_no = int(_item.get("region_index") or 1)
                artwork_state = "bestätigt" if bool(_item.get("artwork_verified")) else "bitte prüfen"
                scan_meta = _item.get("scan_metadata") or {}
                meta_pairs = []
                for meta_key, meta_label in (("atk", "ATK"), ("def", "DEF"), ("level", "Stufe"), ("rank", "Rang"), ("link", "Link"), ("scale", "Skala"), ("attribute", "Attribut"), ("family", "Kartentyp"), ("race", "Typ")):
                    if scan_meta.get(meta_key) not in (None, ""):
                        meta_pairs.append(f"{meta_label} {scan_meta.get(meta_key)}")
                metadata_line = " • ".join(meta_pairs[:6]) or "keine sicheren Zusatzwerte"
                conflicts = list(_item.get("metadata_conflicts") or [])
                metadata_state = "bestätigt" if not conflicts and _item.get("metadata_matches") else ("Widerspruch: " + ", ".join(conflicts[:2]) if conflicts else "nicht vollständig prüfbar")
                _info.text = (
                    f"[b]Bild {source_no} • Bereich {region_no}: {escape_markup(str(current_card.get('name', 'Unbekannte Karte')))}[/b]\n"
                    f"Sicherheit: [color=#{confidence_color}]{conf} %[/color] • Artwork: {escape_markup(artwork_state)} • Bildqualität: {escape_markup(str(quality_data.get('label', '-')))} ({int(quality_data.get('score') or 0)} %)\n"
                    f"Erkannt: {escape_markup(detected_kind)} {escape_markup(str(display_value))} • Sprache: {escape_markup(str(_item.get('language_label', '-')))}\n"
                    f"Set: {escape_markup(str(current_set.get('set_code', '-') or '-'))} • Rarity: {escape_markup(str(current_set.get('set_rarity', '-') or '-'))}\n"
                    f"Gegenprüfung: {escape_markup(metadata_line)} • {escape_markup(metadata_state)}"
                )
                warnings = ", ".join(quality_data.get("warnings") or [])
                reason = _item.get("confidence_reason") or "Keine nähere Begründung"
                selected_text = "wird hinzugefügt" if _check.active else "wird übersprungen"
                try:
                    _item["count"] = max(1, int(_amount.text or 1))
                except Exception:
                    _item["count"] = 1
                _item["selected"] = bool(_check.active)
                try:
                    selected_card = apply_collection_set_to_card(current_card, current_set or {})
                    collection_key = collection_key_for(selected_card)
                    existing_count = int(self.collection.get(collection_key, {}).get("count", 0) or 0)
                except Exception:
                    existing_count = 0
                future_count = existing_count + (_item["count"] if _check.active else 0)
                breakdown = confidence_breakdown_text(_item)
                safe_reason = escape_markup(str(reason))
                safe_warnings = escape_markup(str(warnings)) if warnings else ""
                _state.text = (
                    f"[color={markup_hex(MUTED)}]{safe_reason}{(' • ' + safe_warnings) if safe_warnings else ''} • "
                    f"{escape_markup(str(selected_text))} • Bestand: {existing_count} → {future_count}[/color]"
                    + (f"\n[color={markup_hex(MUTED)}]Einzelsignale: {escape_markup(str(breakdown))}[/color]" if breakdown else "")
                )

            def on_candidate_change(spinner, value, _item=item, _set_spinner=set_spinner, _art_spinner=artwork_spinner, _language_spinner=language_spinner, _candidate_map=candidate_map, _set_map=set_map, _set_values=set_values, _artwork_map=artwork_map, _artwork_values=artwork_values, _refresh=refresh_info):
                entry = _candidate_map.get(value)
                if not entry:
                    return
                _item["card"] = copy.deepcopy(entry.get("card") or {})
                _item["set_item"] = copy.deepcopy(entry.get("set_item") or {})
                _item["language"] = entry.get("language", _item.get("language", "de"))
                _item["language_label"] = entry.get("language_label", scan_language_label(_item.get("language", "de")))
                _item["confidence"] = int(entry.get("confidence") or _item.get("confidence") or 0)
                _item["confidence_reason"] = entry.get("confidence_reason", _item.get("confidence_reason", ""))
                # Sets und Artworks des gewählten Treffers aktualisieren.
                new_card = _item.get("card") or {}
                new_sets = dedupe_card_sets_for_display(new_card.get("card_sets") or [], "")
                _set_map.clear()
                _set_values.clear()
                for sc in new_sets:
                    lbl = f"{sc.get('set_code', '-') or '-'} | {sc.get('set_rarity', '-') or '-'}"
                    _set_map[lbl] = sc
                    _set_values.append(lbl)
                selected_set = _item.get("set_item") or {}
                selected_label = f"{selected_set.get('set_code', '-') or '-'} | {selected_set.get('set_rarity', '-') or '-'}"
                if selected_label not in _set_map:
                    _set_map[selected_label] = selected_set
                    _set_values.insert(0, selected_label)
                _set_spinner.values = _set_values or [selected_label]
                _set_spinner.text = selected_label
                variants = expand_artwork_variants([new_card]) or [new_card]
                _artwork_map.clear()
                _artwork_values.clear()
                for variant in variants:
                    lbl = artwork_label(variant)
                    _artwork_map[lbl] = variant
                    _artwork_values.append(lbl)
                current_lbl = artwork_label(new_card)
                _art_spinner.values = _artwork_values or [current_lbl]
                _art_spinner.text = current_lbl
                _language_spinner.text = _item.get("language_label", "Deutsch")
                _refresh()

            def on_set_change(_spinner, value, _item=item, _set_map=set_map, _refresh=refresh_info):
                if value in _set_map:
                    _item["set_item"] = dict(_set_map[value])
                _refresh()

            def on_artwork_change(_spinner, value, _item=item, _artwork_map=artwork_map, _refresh=refresh_info):
                if value in _artwork_map:
                    _item["card"] = copy.deepcopy(_artwork_map[value])
                    _item["artwork_verified"] = True
                _refresh()

            def on_language_change(_spinner, value, _item=item, _refresh=refresh_info):
                label_to_code = {scan_language_label(code): code for code in SCAN_SEARCH_LANGUAGE_CODES}
                _item["language_label"] = value
                _item["language"] = label_to_code.get(value, _item.get("language", "de"))
                _refresh()

            def manual_for_result(*_args, _item=item):
                popup.dismiss()
                self.open_manual_scan_assignment(
                    {"path": ((_item.get("paths") or []) + [_item.get("path", "")])[0], "quality": _item.get("quality") or {}},
                    results,
                    errors,
                    replace_group=_item,
                )

            check.bind(active=lambda *_args, _refresh=refresh_info: _refresh())
            amount_input.bind(text=lambda *_args, _refresh=refresh_info: _refresh())
            candidate_spinner.bind(text=on_candidate_change)
            set_spinner.bind(text=on_set_change)
            artwork_spinner.bind(text=on_artwork_change)
            language_spinner.bind(text=on_language_change)
            condition_spinner.bind(text=lambda _spinner, value, _item=item: _item.__setitem__("condition", value))
            edition_spinner.bind(text=lambda _spinner, value, _item=item: _item.__setitem__("edition", value))
            manual_btn.bind(on_release=manual_for_result)
            refresh_info()
            sync_result_card_height()
            grid.add_widget(row)
            review_rows.append(result_review_entry)

        if errors:
            grid.add_widget(DarkLabel(text="[b]Nicht erkannte Bilder / Fehler[/b]", markup=True, size_hint_y=None, height=dp(30), color=(1, 0.72, 0.72, 1)))

        for idx, item in enumerate(list(errors), start=1):
            quality = item.get("quality") or {}
            compact = self.ui_width_below(620)
            row = SurfaceBox(
                orientation="vertical", size_hint_y=None, height=dp(280),
                padding=dp(10), spacing=dp(8), bg_color=INPUT_BG_2,
            )
            top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(132), spacing=dp(10))
            path = str(item.get("raw_path") or item.get("preview_path") or item.get("scan_path") or item.get("path") or "")
            preview = Image(
                source=path if path and os.path.exists(path) else (resource_find(PREVIEW_PLACEHOLDER_FILE) or ""),
                allow_stretch=True, keep_ratio=True, size_hint_x=None,
                width=dp(92 if compact else 104), size_hint_y=None, height=dp(132 if compact else 116),
            )
            top.add_widget(preview)
            basename = os.path.basename(str(item.get("path") or f"Bild {idx}"))
            summary = self.scan_error_display_summary(item.get("error", "Unbekannter Fehler"))
            warnings_text = ", ".join(quality.get("warnings") or []) or "Keine zusätzliche Bildwarnung"
            details = AutoHeightLabel(
                text=(
                    f"[b]{idx}. {escape_markup(str(basename))}[/b]\n"
                    f"{escape_markup(str(summary))}\n"
                    f"[color={markup_hex(MUTED)}]Qualität: {escape_markup(str(quality.get('label', '-')))} "
                    f"({int(quality.get('score') or 0)} %) • {escape_markup(str(warnings_text))}[/color]"
                ),
                markup=True,
                min_height=dp(116),
                height_padding=dp(10),
                font_size=ui_font_px(11.5, body=True),
                color=(1, 0.86, 0.86, 1),
            )
            top.add_widget(details)
            row.add_widget(top)

            action_cols = 1
            actions = GridLayout(
                cols=action_cols, size_hint_y=None,
                height=self.grid_height(4, action_cols, dp(52), dp(8)), spacing=dp(8),
            )
            retry_btn = DarkButton(text="Erneut scannen", bg=ACCENT_2)
            manual_btn = DarkButton(text="Manuell zuordnen", bg=GOLD)
            replace_btn = DarkButton(text="Bild ersetzen", bg=ACCENT)
            ignore_btn = DarkButton(text="Ignorieren", bg=INPUT_BG_2)
            actions.add_widget(retry_btn)
            actions.add_widget(manual_btn)
            actions.add_widget(replace_btn)
            actions.add_widget(ignore_btn)
            row.add_widget(actions)
            self.bind_adaptive_grid(actions, 4, min_item_dp=150, max_cols=4, min_cols=1, row_height=dp(52), gap_px=dp(8))

            error_review_entry = {"row": row, "kind": "error", "item": item, "default_height": row.height}

            def sync_error_card_height(*_args, _row=row, _top=top, _details=details, _preview=preview, _actions=actions, _entry=error_review_entry):
                try:
                    _top.height = max(float(_preview.height), float(_details.height))
                    _row.height = float(_top.height) + float(_actions.height) + dp(36)
                    if float(_row.opacity) > 0:
                        _entry["default_height"] = float(_row.height)
                except Exception:
                    pass

            details.bind(height=sync_error_card_height)
            actions.bind(height=sync_error_card_height)
            Clock.schedule_once(sync_error_card_height, 0)

            def retry_error(*_args, _item=item):
                remaining = [entry for entry in errors if entry is not _item]
                popup.dismiss()
                self.start_bulk_gallery_ocr_import([_item.get("raw_path") or _item.get("scan_path") or _item.get("path")], initial_results=results, initial_errors=remaining)

            def manual_error(*_args, _item=item):
                remaining = [entry for entry in errors if entry is not _item]
                popup.dismiss()
                self.open_manual_scan_assignment(_item, results, remaining)

            def replace_error(*_args, _item=item):
                remaining = [entry for entry in errors if entry is not _item]

                def accept_replacement(selected_path):
                    if not selected_path:
                        Clock.schedule_once(lambda *_: self.show_bulk_gallery_review_popup(results, errors), 0)
                        return
                    Clock.schedule_once(
                        lambda *_: self.start_bulk_gallery_ocr_import([selected_path], initial_results=results, initial_errors=remaining),
                        0,
                    )

                def replacement_error(message):
                    Clock.schedule_once(lambda *_: self.show_error("Bild ersetzen", message or "Kein Ersatzbild ausgewählt."), 0)
                    Clock.schedule_once(lambda *_: self.show_bulk_gallery_review_popup(results, errors), 0.1)

                popup.dismiss()
                try:
                    started = start_android_image_picker(self.user_data_dir, accept_replacement, replacement_error)
                    if not started:
                        replacement_error("Galerie konnte nicht geöffnet werden.")
                except Exception as exc:
                    replacement_error(str(exc))

            def ignore_error(*_args, _item=item):
                remaining = [entry for entry in errors if entry is not _item]
                popup.dismiss()
                self.show_bulk_gallery_review_popup(results, remaining)

            retry_btn.bind(on_release=retry_error)
            manual_btn.bind(on_release=manual_error)
            replace_btn.bind(on_release=replace_error)
            ignore_btn.bind(on_release=ignore_error)
            sync_error_card_height()
            grid.add_widget(row)
            review_rows.append(error_review_entry)

        def apply_review_filter(_spinner=None, selected="Alle"):
            selected = str(selected or "Alle")
            for entry in review_rows:
                row_widget = entry.get("row")
                item = entry.get("item") or {}
                kind = entry.get("kind")
                visible = True
                if selected == "Nur unsicher":
                    visible = kind == "result" and int(item.get("confidence") or 0) < 75
                elif selected == "Nur Fehler":
                    visible = kind == "error"
                elif selected == "Nur Duplikate":
                    visible = kind == "result" and int(item.get("duplicate_count") or 1) > 1
                elif selected == "Nur deaktiviert":
                    visible = kind == "result" and not bool(item.get("selected", True))
                row_widget.height = entry.get("default_height", dp(100)) if visible else 0
                row_widget.opacity = 1 if visible else 0
                row_widget.disabled = not visible

        review_filter_spinner.bind(text=apply_review_filter)

        if not grouped_results and not errors:
            grid.add_widget(DarkLabel(text="Keine verwertbaren Ergebnisse.", color=MUTED, size_hint_y=None, height=dp(60)))

        scroll.add_widget(grid)
        wrapper.add_widget(scroll)

        btn_cols = 1
        btn_row = GridLayout(cols=btn_cols, size_hint_y=None, height=self.grid_height(3, btn_cols, dp(52), dp(8)), spacing=dp(8))
        add_btn = DarkButton(text="Ausgewählte Karten hinzufügen", bg=SUCCESS if grouped_results else INPUT_BG_2)
        add_btn.disabled = not bool(grouped_results)
        history_btn = DarkButton(text="Scan-Historie", bg=ACCENT_2)
        cancel_btn = DarkButton(text="Abbrechen", bg=INPUT_BG_2)
        btn_row.add_widget(add_btn)
        btn_row.add_widget(history_btn)
        btn_row.add_widget(cancel_btn)
        self.bind_adaptive_grid(btn_row, 3, min_item_dp=180, max_cols=3, min_cols=1, row_height=dp(52), gap_px=dp(8))
        wrapper.add_widget(btn_row)

        popup = self.make_inline_page("scan_review", wrapper, back_to="scanner")

        def add_all(*_):
            self.push_collection_undo_snapshot("Galerie-Sammelimport")
            added = 0
            updated_variants = 0
            transaction_entries = []
            selected_groups = []
            add_errors = list(errors)
            for item in grouped_results:
                try:
                    if not bool(item.get("selected", True)):
                        continue
                    card = item.get("card") or {}
                    if not card:
                        continue
                    amount = max(1, int(item.get("count") or 1))
                    selected_card = apply_collection_set_to_card(card, item.get("set_item") or get_collection_set_from_card(card) or {})
                    cid = collection_key_for(selected_card)
                    metadata = normalized_collection_metadata({
                        "condition": item.get("condition") or "Near Mint",
                        "language": item.get("language_label") or scan_language_label(item.get("language", "de")),
                        "edition": item.get("edition") or "Unbekannt",
                    })
                    if cid not in self.collection:
                        self.collection[cid] = {"count": 0, "card": selected_card, "metadata": metadata}
                    else:
                        self.collection[cid]["card"] = {**self.collection[cid].get("card", {}), **selected_card}
                        self.collection[cid].setdefault("metadata", metadata)
                    self.collection[cid]["count"] = int(self.collection[cid].get("count", 0) or 0) + amount
                    transaction_entries.append({"key": cid, "amount": amount, "name": selected_card.get("name", "")})
                    added += amount
                    updated_variants += 1
                    selected_groups.append(item)
                except Exception as exc:
                    add_errors.append({"path": item.get("path", ""), "value": item.get("value", ""), "error": f"Konnte nicht hinzugefügt werden: {exc}"})

            if not transaction_entries:
                self.show_error("Keine Auswahl", "Es wurde keine Karte zum Hinzufügen ausgewählt.")
                return

            transaction = {
                "id": f"import_{int(time.time() * 1000)}",
                "created_at": time.strftime("%d.%m.%Y %H:%M:%S"),
                "entries": transaction_entries,
                "added_count": added,
                "added_variants": updated_variants,
            }
            self.save_last_scan_import_transaction(transaction)
            self.add_scan_history_entry(results, add_errors, added_count=added, added_variants=updated_variants)
            try:
                popup.dismiss()
            except Exception:
                pass
            self.update_collection_info()
            self.save_collection(show_popup=False)
            self.refresh_results_list()
            self.set_status(f"Sammelimport abgeschlossen: {added} Exemplar(e) in {updated_variants} Karten/Varianten hinzugefügt, {len(add_errors)} Fehler.")
            self.show_scan_import_success_popup(added, updated_variants, len(add_errors))

        close_top.bind(on_release=popup.dismiss)
        cancel_btn.bind(on_release=popup.dismiss)
        history_btn.bind(on_release=lambda *_: self.open_scan_history_popup())
        add_btn.bind(on_release=add_all)
        popup.open()

    def open_manual_scan_assignment(self, error_item, existing_results=None, existing_errors=None, replace_group=None):
        """Erlaubt die manuelle Zuordnung eines unsicheren oder fehlgeschlagenen Bildes."""
        existing_results = list(existing_results or [])
        existing_errors = list(existing_errors or [])
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        title_row.add_widget(DarkLabel(text="[b]Karte manuell zuordnen[/b]", markup=True, color=TEXT))
        close_btn = self.make_close_button(bg=INPUT_BG_2)
        title_row.add_widget(close_btn)
        content.add_widget(title_row)
        path = str((error_item or {}).get("scan_path") or (error_item or {}).get("path") or "")
        content.add_widget(Image(source=path if path and os.path.exists(path) else (resource_find(PREVIEW_PLACEHOLDER_FILE) or ""), allow_stretch=True, keep_ratio=True, size_hint_y=None, height=dp(220)))
        name_input = DarkInput(hint_text="Kartenname")
        set_input = DarkInput(hint_text="Set-Code, z. B. DABL-DE042")
        pass_input = DarkInput(hint_text="Passcode / Karten-ID")
        for widget in (name_input, set_input, pass_input):
            widget.size_hint_y = None
            widget.height = dp(50)
            content.add_widget(widget)
        search_btn = DarkButton(text="In allen Sprachen suchen", bg=GOLD, size_hint_y=None, height=dp(52))
        content.add_widget(search_btn)
        status = DarkLabel(text="Trage mindestens einen Wert ein.", color=MUTED, size_hint_y=None, height=dp(46))
        content.add_widget(status)
        popup = self.make_popup("Manuelle Scan-Zuordnung", content, size_hint=(0.94, 0.88))

        def do_search(*_):
            candidates = []
            if set_input.text.strip():
                candidates.append({"kind": "Set-Code", "value": set_input.text.strip(), "priority": 110, "source": "Manuell"})
            if pass_input.text.strip():
                candidates.append({"kind": "Passcode", "value": pass_input.text.strip(), "priority": 100, "source": "Manuell"})
            if name_input.text.strip():
                candidates.append({"kind": "Name", "value": name_input.text.strip(), "priority": 95, "source": "Manuell"})
            if not candidates:
                status.text = "Bitte Name, Set-Code oder Passcode eingeben."
                return
            status.text = "Suche läuft..."

            def worker():
                try:
                    quality = (error_item or {}).get("quality") or self.analyze_scan_image_quality(path)
                    best, tried, alternatives = self._find_scan_matches_for_candidates(candidates, scan_path=path, quality=quality, include_artwork=bool(self.scan_mode_config().get("artwork")))
                    if not best or not best.get("card"):
                        Clock.schedule_once(lambda *_: setattr(status, "text", "Keine passende Karte gefunden. Eingabe prüfen."), 0)
                        return
                    candidate = best.get("candidate") or {}
                    result = {
                        "path": (error_item or {}).get("path") or path,
                        "scan_path": path,
                        "attempt": 1,
                        "value": candidate.get("value", ""),
                        "kind": candidate.get("kind", "Name"),
                        "card": best.get("card"),
                        "set_item": best.get("set_item") or {},
                        "matches": best.get("matches", 0),
                        "language": best.get("language", "de"),
                        "language_label": best.get("language_label", "Deutsch"),
                        "score": best.get("score", 0),
                        "confidence": best.get("confidence", 0),
                        "confidence_reason": best.get("confidence_reason", "Manuell gesucht"),
                        "alternatives": alternatives,
                        "quality": quality,
                        "selected": True,
                    }
                    try:
                        learned_card = result.get("card") or {}
                        learned_set = result.get("set_item") or {}
                        target_map = {
                            "Set-Code": learned_set.get("set_code") or result.get("value") or "",
                            "Passcode": str(learned_card.get("id") or result.get("value") or ""),
                            "Name": learned_card.get("name") or result.get("value") or "",
                        }
                        for manual_candidate in candidates:
                            raw_manual = manual_candidate.get("value", "")
                            kind_manual = manual_candidate.get("kind", "Name")
                            target_manual = target_map.get(kind_manual) or target_map.get("Name") or ""
                            self.scan_learning.remember(
                                raw_manual,
                                kind_manual,
                                target_manual,
                                card_id=learned_card.get("id", ""),
                                language=result.get("language", ""),
                            )
                    except Exception:
                        pass
                    if replace_group is not None:
                        replace_group.update(result)
                        source_results = list(replace_group.get("source_results") or [])
                        if source_results:
                            for source_result in source_results:
                                if isinstance(source_result, dict):
                                    source_result.update(result)
                        elif existing_results:
                            existing_results[0].update(result)
                    else:
                        existing_results.append(result)
                    Clock.schedule_once(lambda *_: (popup.dismiss(), self.show_bulk_gallery_review_popup(existing_results, existing_errors)), 0)
                except Exception as exc:
                    Clock.schedule_once(lambda *_: setattr(status, "text", f"Suche fehlgeschlagen: {exc}"), 0)

            threading.Thread(target=worker, daemon=True).start()

        close_btn.bind(on_release=lambda *_: (popup.dismiss(), self.show_bulk_gallery_review_popup(existing_results, existing_errors)))
        search_btn.bind(on_release=do_search)
        popup.open()

    def show_scan_import_success_popup(self, added, variants, error_count):
        content = SurfaceBox(orientation="vertical", padding=dp(12), spacing=dp(10), bg_color=PANEL_BG)
        content.add_widget(AutoHeightLabel(
            text=(
                f"[b]Sammelimport abgeschlossen[/b]\n\n"
                f"Hinzugefügt: {int(added)} Exemplar(e)\n"
                f"Karten/Varianten: {int(variants)}\n"
                f"Fehler/Nicht erkannt: {int(error_count)}\n\n"
                f"Der letzte Import kann gezielt rückgängig gemacht werden."
            ),
            markup=True,
            color=TEXT,
            min_height=dp(150),
            height_padding=dp(18),
            font_size=ui_font_px(12.5, body=True),
        ))
        success_cols = 1 if self.ui_width_below(560) else 3
        buttons = GridLayout(
            cols=success_cols,
            size_hint_y=None,
            height=self.grid_height(3, success_cols, dp(52), dp(8)),
            spacing=dp(8),
        )
        undo_btn = DarkButton(text="Import rückgängig", bg=DANGER)
        history_btn = DarkButton(text="Scan-Historie", bg=ACCENT_2)
        close_btn = DarkButton(text="Schließen", bg=INPUT_BG_2)
        buttons.add_widget(undo_btn)
        buttons.add_widget(history_btn)
        buttons.add_widget(close_btn)
        content.add_widget(buttons)
        popup = self.make_popup("Sammelimport abgeschlossen", content, size_hint=(0.94, 0.62))
        undo_btn.bind(on_release=lambda *_: (popup.dismiss(), self.undo_last_scan_import()))
        history_btn.bind(on_release=lambda *_: (popup.dismiss(), self.open_scan_history_popup()))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def open_scan_history_popup(self, *_):
        self.load_scan_history()
        wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        header.add_widget(DarkLabel(text="[b]Scan-Historie[/b]", markup=True, color=TEXT))
        close_btn = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_btn)
        wrapper.add_widget(header)
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(6))
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        if not self.scan_history:
            grid.add_widget(DarkLabel(text="Noch keine Scan-Historie vorhanden.", color=MUTED, size_hint_y=None, height=dp(70)))
        for entry in self.scan_history:
            row = SurfaceBox(orientation="vertical", padding=dp(8), spacing=dp(6), size_hint_y=None, height=dp(132), bg_color=CARD_BG)
            row.add_widget(DarkLabel(
                text=(
                    f"[b]{html_escape(entry.get('created_at', '-'))}[/b] • Modus: {html_escape(str(entry.get('mode', '-')).title())}\\n"
                    f"Treffer: {int(entry.get('image_hits') or 0)} • Fehler: {int(entry.get('errors_count') or 0)} • hinzugefügt: {int(entry.get('added_count') or 0)}"
                ),
                markup=True,
                color=TEXT,
            ))
            actions = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(6))
            open_btn = DarkButton(text="Ergebnisse öffnen", bg=ACCENT_2)
            retry_btn = DarkButton(text="Fehler erneut scannen", bg=GOLD)
            actions.add_widget(open_btn)
            actions.add_widget(retry_btn)
            row.add_widget(actions)

            def open_entry(*_args, _entry=entry):
                popup.dismiss()
                self.show_bulk_gallery_review_popup(_entry.get("results") or [], _entry.get("errors") or [])

            def retry_entry(*_args, _entry=entry):
                paths = []
                for err in _entry.get("errors") or []:
                    path = err.get("path") or ""
                    if path and path not in paths:
                        paths.append(path)
                if not paths:
                    self.show_info("Keine Fehlerbilder", "Für diesen Verlauf gibt es keine erneut scanbaren Fehlerbilder.")
                    return
                popup.dismiss()
                self.start_bulk_gallery_ocr_import(paths, initial_results=_entry.get("results") or [], initial_errors=[])

            open_btn.bind(on_release=open_entry)
            retry_btn.bind(on_release=retry_entry)
            grid.add_widget(row)
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        footer = GridLayout(cols=1 if self.ui_width_below(540) else 3, size_hint_y=None, height=dp(50 if not self.ui_width_below(540) else 150), spacing=dp(8))
        undo_btn = DarkButton(text="Letzten Import rückgängig", bg=DANGER)
        clear_btn = DarkButton(text="Historie löschen", bg=INPUT_BG_2)
        close_bottom = DarkButton(text="Schließen", bg=INPUT_BG_2)
        footer.add_widget(undo_btn)
        footer.add_widget(clear_btn)
        footer.add_widget(close_bottom)
        wrapper.add_widget(footer)
        popup = self.make_popup("Scan-Historie", wrapper, size_hint=(0.96, 0.90))

        def clear_history(*_):
            self.scan_history = []
            self.save_scan_history()
            popup.dismiss()
            self.open_scan_history_popup()

        undo_btn.bind(on_release=lambda *_: self.undo_last_scan_import())
        clear_btn.bind(on_release=clear_history)
        close_btn.bind(on_release=popup.dismiss)
        close_bottom.bind(on_release=popup.dismiss)
        popup.open()


    def open_custom_card_popup(self):
        content = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(10), bg_color=PANEL_BG, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(DarkLabel(text="[b]Eigene Karte lokal hinzufügen[/b]\nBild per URL, lokalem Pfad, letztem Scannerfoto oder Galerie auswählen.", markup=True, color=TEXT, size_hint_y=None, height=dp(68)))
        grid = GridLayout(cols=1 if self.ui_width_below(560) else 2, spacing=dp(8), size_hint_y=None)
        fields = {}
        specs = [("name", "Name"), ("card_id", "Eigene ID z. B. CUSTOM-0001"), ("type", "Kartentyp z. B. Effect Monster"), ("race", "Typ/Race z. B. Dragon"), ("attribute", "Eigenschaft z. B. DARK"), ("level", "Stufe / Rank / Link"), ("atk", "ATK"), ("def", "DEF"), ("set_name", "Set-Name"), ("set_code", "Set-Code/Kürzel z. B. CSTM-DE001"), ("rarity", "Rarity"), ("image", "Bild-URL oder lokaler Bildpfad")]
        for key, hint_text in specs:
            inp = DarkInput(hint_text=hint_text)
            inp.size_hint_y = None
            inp.height = dp(50)
            fields[key] = inp
            grid.add_widget(inp)
        grid.height = self.grid_height(len(specs), grid.cols, dp(50), dp(8))
        content.add_widget(grid)
        desc = DarkInput(hint_text="Effekt/Beschreibung")
        desc.multiline = True
        desc.size_hint_y = None
        desc.height = dp(110)
        content.add_widget(desc)
        btn_cols = 1 if self.ui_width_below(430) else (2 if self.ui_width_below(720) else 4)
        btns = GridLayout(cols=btn_cols, spacing=dp(8), size_hint_y=None)
        btns.height = self.grid_height(4, btn_cols, dp(50), dp(8))
        use_last_photo = DarkButton(text="Letztes Foto", bg=GOLD)
        choose_gallery = DarkButton(text="Galerie-Bild", bg=ACCENT_2)
        save_btn = DarkButton(text="Karte speichern", bg=SUCCESS)
        close_btn = DarkButton(text="Schließen", bg=ACCENT_2)
        for b in [use_last_photo, choose_gallery, save_btn, close_btn]:
            btns.add_widget(b)
        content.add_widget(btns)
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"], do_scroll_x=False)
        scroll.add_widget(content)
        popup = self.make_popup("Eigene Karte", scroll, size_hint=(0.96, 0.92))

        def use_photo(*_):
            path = getattr(self, "last_scan_photo", "") or ""
            if path and os.path.exists(path):
                fields["image"].text = path
                self.set_status("Letztes Scannerfoto als Kartenbild eingetragen.")
            else:
                self.show_error("Kein Foto", "Bitte zuerst im Kamera-Scanner ein Foto/Galeriebild laden oder eine Bild-URL/einen lokalen Pfad eintragen.")

        def choose_gallery_image(*_):
            def accept(path):
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    fields["image"].text = path
                    self.last_scan_photo = path
                    self.set_status("Galeriebild als lokales Kartenbild eingetragen.")
                else:
                    self.show_error("Kein Bild", "Das ausgewählte Bild konnte nicht gelesen werden.")
            def fallback(message=""):
                try:
                    from plyer import filechooser
                    def _on_selection(selection):
                        selected = selection[0] if isinstance(selection, (list, tuple)) and selection else (selection or "")
                        selected = str(selected.toString()) if hasattr(selected, "toString") else str(selected)
                        if not selected:
                            return
                        if selected.startswith("content://") and platform == "android":
                            selected = copy_android_content_uri_to_file(selected, self.user_data_dir, "custom_card_image")
                        accept(selected)
                    try:
                        filechooser.open_file(on_selection=_on_selection, filters=[("Bilder", "*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff", "*.heic", "*.heif", "*.avif")])
                    except TypeError:
                        filechooser.open_file(on_selection=_on_selection)
                except Exception as exc:
                    self.show_error("Galerie", str(exc) or message or "Galerie konnte nicht geöffnet werden.")
            if platform == "android":
                started = start_android_image_picker(
                    self.user_data_dir,
                    lambda path: Clock.schedule_once(lambda *_: accept(path), 0),
                    lambda msg: Clock.schedule_once(lambda *_: fallback(msg), 0),
                )
                if started:
                    return
            fallback("Android-Bildauswahl konnte nicht gestartet werden.")

        def as_int(value):
            try:
                value = str(value or "").strip()
                return int(value) if value else None
            except Exception:
                return None

        def save_card(*_):
            name = fields["name"].text.strip()
            if not name:
                self.show_error("Name fehlt", "Bitte mindestens einen Kartennamen eingeben.")
                return
            cid = fields["card_id"].text.strip() or f"CUSTOM-{int(time.time())}"
            image_path = fields["image"].text.strip()
            card = {"id": cid, "name": name, "type": fields["type"].text.strip() or "Custom Card", "frameType": "custom", "desc": desc.text.strip(), "race": fields["race"].text.strip(), "attribute": fields["attribute"].text.strip(), "level": as_int(fields["level"].text), "atk": as_int(fields["atk"].text), "def": as_int(fields["def"].text), "custom": True, "card_images": [{"id": cid, "image_url": image_path, "image_url_small": image_path}] if image_path else [], "card_sets": [{"set_name": fields["set_name"].text.strip() or "Eigene Karten", "set_code": fields["set_code"].text.strip() or f"CSTM-{cid}", "set_rarity": fields["rarity"].text.strip() or "Custom", "set_price": "0.00"}]}
            try:
                cards = load_custom_cards()
                cards = [c for c in cards if str(c.get("id")) != str(cid)]
                cards.append(card)
                path = save_custom_cards(cards)
                self.show_info("Eigene Karte gespeichert", f"{name} wurde lokal gespeichert.\n\n{path}")
                self.set_status(f"Eigene Karte gespeichert: {name}")
                popup.dismiss()
                self.search_results = merge_card_lists(self.search_results, [card])
                self.render_current_page(reset_scroll=False)
            except Exception as exc:
                self.show_error("Speichern fehlgeschlagen", str(exc))

        use_last_photo.bind(on_release=use_photo)
        choose_gallery.bind(on_release=choose_gallery_image)
        save_btn.bind(on_release=save_card)
        close_btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def open_database_popup(self):
        profile = self.current_ui_profile()
        phone_layout = profile.get("navigation_mode") == "bottom"
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(8), bg_color=PANEL_BG)

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8))
        header.add_widget(DarkLabel(text="[b]Datenbank[/b]", markup=True, color=TEXT, font_size=ui_font_px(16, profile)))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        wrapper.add_widget(header)

        body_scroll = ScrollView(bar_width=dp(5), scroll_type=["bars", "content"], do_scroll_x=False)
        body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(dp(2), dp(2), dp(2), dp(8)))
        body.bind(minimum_height=body.setter("height"))
        body_scroll.add_widget(body)
        wrapper.add_widget(body_scroll)

        description = AutoHeightLabel(
            text=(
                "[b]Lokale Kartendatenbank[/b]\n"
                "Lädt die verfügbaren Karten der gewählten Sprache und speichert sie lokal. "
                "Set-Kürzel werden dynamisch über die API-Setliste geprüft. Mit den Optionen "
                "bestimmst du, welche Spezialfälle übernommen werden."
            ),
            markup=True,
            color=TEXT,
            min_height=dp(92),
            height_padding=dp(12),
            font_size=ui_font_px(13, profile, body=True),
        )
        body.add_widget(description)

        lang_name = self.language_spinner.text.strip() if hasattr(self, "language_spinner") else "Deutsch"
        lang_code = LANGUAGE_CODES.get(lang_name, "de")
        status = AutoHeightLabel(
            text=local_database_status_text(lang_code),
            color=GOLD,
            min_height=dp(42),
            height_padding=dp(10),
            font_size=ui_font_px(12.5, profile, body=True),
        )
        body.add_widget(status)

        options_box = SurfaceBox(
            orientation="vertical",
            padding=dp(8),
            spacing=dp(6),
            size_hint_y=None,
            bg_color=INPUT_BG_2,
        )
        options_box.bind(minimum_height=options_box.setter("height"))
        options_title = AutoHeightLabel(
            text="[b]Synchronisationsoptionen[/b]",
            markup=True,
            color=TEXT,
            min_height=dp(30),
            height_padding=dp(6),
            font_size=ui_font_px(13, profile),
        )
        options_box.add_widget(options_title)
        option_refs = {}

        def add_option(key, label, active=False):
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54), spacing=dp(8))
            cb = CheckBox(active=active, size_hint=(None, None), size=(dp(40), dp(40)))
            row.add_widget(cb)
            option_label = AutoHeightLabel(
                text=label,
                color=TEXT,
                font_size=ui_font_px(11.2 if phone_layout else 12.2, profile, body=True),
                halign="left",
                min_height=dp(46),
                height_padding=dp(8),
            )
            row.add_widget(option_label)
            option_label.bind(height=lambda instance, value, target=row: setattr(target, "height", max(dp(54), value)))
            options_box.add_widget(row)
            option_refs[key] = cb

        add_option("include_duplicates", "Doppelte Karten/Varianten behalten", False)
        add_option("include_placeholders", "Platzhalterkarten übernehmen", False)
        add_option("include_no_image", "Karten ohne Bild übernehmen", True)
        add_option("include_no_set", "Karten ohne Set übernehmen", True)
        add_option("force_full_sync", "Vollständigen Sync erzwingen", False)
        body.add_widget(options_box)

        progress = AutoHeightLabel(
            text="Bereit. Noch keine Synchronisierung gestartet.",
            color=MUTED,
            min_height=dp(58),
            height_padding=dp(12),
            font_size=ui_font_px(12, profile, body=True),
        )
        body.add_widget(progress)

        footer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8))
        sync_btn = DarkButton(
            text="Jetzt synchronisieren",
            bg=SUCCESS,
            bold=True,
            no_wrap=True,
            font_size=ui_font_px(13, profile),
        )
        footer.add_widget(sync_btn)
        wrapper.add_widget(footer)

        popup = self.make_popup("", wrapper, size_hint=(0.96 if phone_layout else 0.82, 0.92 if phone_layout else 0.82))

        def start_sync(*_):
            sync_btn.disabled = True
            sync_btn.text = "Synchronisierung läuft..."
            progress.text = "Synchronisierung startet..."
            progress._sync_auto_height()
            sync_options = {key: bool(cb.active) for key, cb in option_refs.items()}
            self.start_database_sync(
                lang_code,
                progress_label=progress,
                status_label=status,
                popup=popup,
                sync_options=sync_options,
            )

        sync_btn.bind(on_release=start_sync)
        close_top.bind(on_release=popup.dismiss)
        popup.open()

    def start_database_sync(self, language_code="de", progress_label=None, status_label=None, popup=None, sync_options=None):
        self.set_status("Lokale Kartendatenbank wird synchronisiert...")
        threading.Thread(target=self._database_sync_thread, args=(language_code, progress_label, status_label, sync_options or {}), daemon=True).start()

    def _database_sync_thread(self, language_code, progress_label=None, status_label=None, sync_options=None):
        def progress_cb(step, total, label, count=0, error=""):
            percent = int(max(0, min(100, (float(step) / float(max(1, total))) * 100)))
            msg = f"{percent}%  ({step}/{total})\n{label}"
            if count:
                msg += f"\n{count} Datensätze"
            if error:
                msg += "\nFehler/Timeout: erneuter Versuch oder späteres Überspringen."
            Clock.schedule_once(lambda *_: self._update_database_progress(progress_label, msg), 0)
            Clock.schedule_once(lambda *_: self.set_status(f"Datenbank-Sync: {percent}% - {label}"), 0)

        try:
            remote_version = fetch_primary_database_version(timeout=12)
            local_cards = load_local_card_database(language_code)
            force_full = bool((sync_options or {}).get("force_full_sync"))
            source_key = f"ygoprodeck:{language_code or 'en'}"
            if local_cards and not force_full and not self.incremental_sync.should_sync(source_key, remote_version, max_age_seconds=6 * 60 * 60):
                Clock.schedule_once(lambda *_: self._finish_database_sync(len(local_cards), local_database_file(language_code), None, status_label), 0)
                Clock.schedule_once(lambda *_: self.set_status("Datenbank ist bereits aktuell; kein unnötiger Vollsync durchgeführt."), 0)
                return
            cards = fetch_combined_card_database(language_code, progress_cb=progress_cb)
            cards = self._filter_synced_database_cards(cards, sync_options or {})
            path = save_local_card_database(cards, language_code, meta={
                "primary_source": "YGOPRODeck API v7",
                "supplemental_sources": ["YGOResources", "RockRoller/Yugipedia", "YGOJSON", "Project Ignis/BabelCDB", "Yugipedia Cargo", "Just InCard lokale Seed-/Registry-Daten"],
            })
            try:
                self.incremental_sync.mark_synced(source_key, remote_version, len(cards), {"language": language_code or "en"})
            except Exception:
                pass
            Clock.schedule_once(lambda *_: self._finish_database_sync(len(cards), path, None, status_label), 0)
        except Exception as exc:
            Clock.schedule_once(lambda *_: self._finish_database_sync(0, "", str(exc), status_label), 0)

    def _filter_synced_database_cards(self, cards, sync_options):
        """Filtert die lokale Datenbank nach den im Datenbank-Popup gewählten Optionen.
        Standard: Platzhalter und echte Duplikate entfernen, Karten ohne Bild/Set optional behalten.
        """
        include_duplicates = bool(sync_options.get("include_duplicates"))
        include_placeholders = bool(sync_options.get("include_placeholders"))
        include_no_image = bool(sync_options.get("include_no_image", True))
        include_no_set = bool(sync_options.get("include_no_set", True))
        filtered = []
        seen = set()
        for card in cards or []:
            try:
                if not isinstance(card, dict):
                    continue
                if not include_placeholders and is_sparse_placeholder_card(card):
                    continue
                if not include_no_image and not get_image_url(card):
                    continue
                if not include_no_set and not (card.get("card_sets") or []):
                    continue
                key = str(card.get("id") or "") + "|" + str(card.get("name") or "")
                if not include_duplicates:
                    variant = str(card.get("_variant_key") or card.get("_artwork_index") or "")
                    key = key + "|" + variant
                    if key in seen:
                        continue
                    seen.add(key)
                filtered.append(card)
            except Exception:
                continue
        return filtered

    def _update_database_progress(self, progress_label, message):
        try:
            if progress_label is not None:
                progress_label.text = message
        except Exception:
            pass

    def _finish_database_sync(self, count, path, error, status_label=None):
        if error:
            self.show_error("Datenbank", f"Synchronisierung fehlgeschlagen, App läuft weiter.\n\n{error}")
            self.set_status("Datenbank-Sync fehlgeschlagen. Online-Suche bleibt verfügbar.")
            return
        try:
            if status_label is not None:
                lang_name = self.language_spinner.text.strip() if hasattr(self, "language_spinner") else "Deutsch"
                lang_code = LANGUAGE_CODES.get(lang_name, "de")
                status_label.text = local_database_status_text(lang_code)
        except Exception:
            pass
        self.show_info("Datenbank gespeichert", f"{count} Karten lokal gespeichert.\n\n{path}")
        self.set_status(f"Lokale Kartendatenbank bereit: {count} Karten.")

    def open_info_popup(self):
        info_text = (
            f"[b][size=22]{APP_DISPLAY_NAME} v{APP_VERSION}[/size][/b]\n"
            f"[color={markup_hex(MUTED)}]{APP_MOTTO}[/color]\n\n"
            "[b][size=18]Kontakt & Support[/size][/b]\n"
            "Name: leenation\n"
            "E-Mail: leenation0211@gmail.com\n\n"
            "[b][size=18]1. Schnellstart[/size][/b]\n"
            "1. Suche nach Kartenname, Set-Code, Set-Kürzel oder Passcode.\n"
            "2. Kombiniere Filter wie Sprache, ATK, DEF, Eigenschaft, Typ und Kartenart.\n"
            "3. Tippe im Suchergebnis auf +. Wenn kein Set gesucht wurde, wähle Set und Rarity aus.\n"
            "4. Öffne Sammlung oder Decks über die Hauptbuttons.\n"
            "5. Datenbank, Export, Backup, Fehlerbericht, Theme und KI-Key findest du im Zahnrad.\n\n"
            "[b][size=18]2. Suche[/size][/b]\n"
            "• Leere Suche lädt alle Karten seitenweise. Das schützt vor Rucklern.\n"
            "• Set-Feld: Set-Name, Kürzel oder kompletter Code, z. B. DABL, BLMR, KICO, RA01, SBCB-DE001.\n"
            "• Exakte Setcodes und deutsche Codes werden bevorzugt behandelt.\n"
            "• Bei mehreren Filtern wird defensiv geprüft: falsche Eingaben sollen keine Abstürze verursachen.\n"
            "• Doppelte Basis-Karten werden ausgeblendet; andere Artworks bleiben als Varianten sichtbar.\n"
            "• Platzhalterkarten und leere Datensätze werden möglichst entfernt.\n\n"
            "[b][size=18]3. Kartenarten und Filter[/size][/b]\n"
            "Monster: Normal, Effekt, Pendel, Ritual, Fusion, Synchro, Xyz, Link, Toon, Spirit, Union, Gemini, Flip, Tuner und Token.\n"
            "Zauber: Normal, Schnellzauber, Ausrüstung, Spielfeld, Permanent und Ritual.\n"
            "Fallen: Normal, Permanent und Konterfalle.\n"
            "Eigenschaften: Dunkel, Licht, Erde, Wasser, Feuer, Wind und Göttlich.\n\n"
            "[b][size=18]4. Kamera & Scanner[/size][/b]\n"
            "• Live und Kamera verwenden wahlweise Schnell oder Normal.\n"
            "• Galerieimporte laufen immer im gründlichen Präzisionsmodus; eine Schnell-/Normal-Auswahl gibt es dort nicht mehr.\n"
            "• Galerie-Gründlich erkennt mehrere Karten, korrigiert Perspektive, prüft verschiedene Schriftfarben und gleicht bei Unsicherheit Effekt und Artwork ab.\n"
            "• Für beste OCR-Qualität nutze Galerie oder ein hochauflösendes Foto.\n"
            "• Priorität beim Lesen: Set-Kürzel + Kartennummer, danach Name, danach Passcode.\n"
            "• Treffer zeigen Sicherheit, Bildqualität, Alternativen und genaue Fehlergründe.\n"
            "• Vor dem Hinzufügen können Karte, Set/Rarity, Artwork, Sprache, Menge und Auswahl korrigiert werden.\n"
            "• Scan-Historie, Fehler erneut scannen und letzter Import rückgängig sind enthalten.\n"
            "• Beim Schließen wird die Kamera freigegeben, damit Android sie nicht blockiert.\n\n"
            "[b][size=18]5. Sammlung[/size][/b]\n"
            "• Karten werden mit Anzahl, Set-Code, Set-Name, Rarity und Artwork gespeichert.\n"
            "• Plus/Minus aktualisiert Menge, Zeile und Zähler direkt.\n"
            "• Sammlung kann durchsucht, sortiert und nach doppelten Karten, fehlenden Sets oder fehlenden Bildern gefiltert werden.\n"
            "• Verschiedene Artworks werden als eigene Varianten geführt.\n"
            "• Backup ZIP sichert Sammlung, Decks, Einstellungen, eigene Karten, Datenbank und Bilder.\n\n"
            "[b][size=18]6. Deckbuilder[/size][/b]\n"
            "• Bis zu 10 Decks aus deiner Sammlung.\n"
            "• Die App verhindert, dass du mehr Kopien nutzt als du besitzt.\n"
            "• + und - ändern Mengen direkt, Löschen entfernt Einträge komplett.\n"
            "• Decks können als Text exportiert werden.\n"
            "• KI-Deckhilfe funktioniert mit API-Key; ohne Key gibt es lokale Hinweise.\n\n"
            "[b][size=18]7. Lokale Datenbank[/size][/b]\n"
            "• Synchronisierung macht Suche schneller und stabiler.\n"
            "• Du kannst entscheiden, ob doppelte Karten, Platzhalter, Karten ohne Bild oder ohne Set übernommen werden.\n"
            "• Ab v8.1 wird zusätzlich eine SQLite-Spiegeldatenbank angelegt, um spätere große Datenmengen besser zu verwalten.\n"
            "• Reparatur entfernt beschädigte/ungültige Einträge und schreibt JSON + SQLite neu.\n\n"
            "[b][size=18]8. Export, Backup und Wiederherstellung[/size][/b]\n"
            "• XLSX-Export für Google Sheets.\n"
            "• Backup als ZIP für Sammlung, Decks, Einstellungen, eigene Karten, Bilder und lokale Datenbank.\n"
            "• Fehlerbericht als TXT für Support.\n\n"
            "[b][size=18]9. Themes & Barrierefreiheit[/size][/b]\n"
            "• Dark Theme, Light Theme und Farbenblind-Modus.\n"
            "• Farbenblind-Modus nutzt stärkere Kontraste und Blau/Orange statt klassischem Grün/Rot.\n"
            "• Plus/Minus bleiben zusätzlich durch Text/Symbole unterscheidbar.\n\n"
            "[b][size=18]10. Häufige Probleme[/size][/b]\n"
            "• Keine Treffer: Schreibweise, Sprache und Setcode prüfen oder Datenbank synchronisieren.\n"
            "• Scanner erkennt nichts: helleres Bild, weniger Spiegelung, Karte gerade ausrichten, Foto/Galerie statt Live nutzen.\n"
            "• GitHub Build Fehler: Docker-Buildozer-Workflow nutzen.\n"
            "• App verhält sich langsam: lokale Datenbank reparieren oder Backup erstellen und App-Daten bereinigen.\n\n"
            "[b][size=18]Was noch sinnvoll wäre[/size][/b]\n"
            "• Datenschutz-/Impressumstext, falls die App öffentlich geteilt wird.\n"
            "• Support-Link oder GitHub-Issue-Link.\n"
            "• Changelog im App-Menü.\n"
            "• Cloud-Sync, Preislisten und native CameraX-Kamera in einer späteren großen Version.\n\n"
            f"Copyright: {APP_COPYRIGHT}"
        )
        self.show_scroll_text("Hilfe, Anleitung & Support", info_text)

    def resolved_performance_mode(self):
        selected = str(getattr(self, "performance_mode", "auto") or "auto")
        if selected == "auto":
            selected = recommend_performance_mode(self.current_ui_profile())
        return PERFORMANCE_MODES_V93.get(selected, PERFORMANCE_MODES_V93["balanced"])

    def set_performance_mode(self, mode, show_popup=True):
        mode = str(mode or "auto")
        if mode not in {"auto", "eco", "balanced", "quality"}:
            mode = "auto"
        self.performance_mode = mode
        self.save_settings()
        resolved = self.resolved_performance_mode()
        if show_popup:
            label = "Automatisch → " + resolved.title if mode == "auto" else resolved.title
            self.show_info("Leistungsmodus", f"Aktiv: {label}\nMaximale Scan-Kante: {resolved.max_scan_side}px\nArtwork-Vergleich: {'Ja' if resolved.artwork_compare else 'Nein'}")

    def open_performance_mode_popup(self, *_):
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text=f"[b]Leistungsmodus[/b]\n[color={markup_hex(MUTED)}]Scanqualität und Speicherverbrauch an das Gerät anpassen.[/color]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        content.add_widget(header)
        profile = self.current_ui_profile()
        recommended = recommend_performance_mode(profile)
        popup_ref = {"popup": None}
        entries = [
            ("Automatisch", "auto", f"Empfehlung für dieses Gerät: {PERFORMANCE_MODES_V93[recommended].title}"),
            ("Energiesparend", "eco", "Weniger Speicher, kleinere Scanbilder, kein Artwork-Vergleich"),
            ("Ausgewogen", "balanced", "Gute Balance aus Erkennung und Geschwindigkeit"),
            ("Maximale Qualität", "quality", "Größere Scanbilder und Artwork-Vergleich"),
        ]
        for title, key, desc in entries:
            row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(68), spacing=dp(8), padding=dp(7), bg_color=CARD_BG)
            active = str(self.performance_mode) == key
            row.add_widget(DarkLabel(text=f"[b]{html_escape(title)}{' • aktiv' if active else ''}[/b]\n[color={markup_hex(MUTED)}]{html_escape(desc)}[/color]", markup=True))
            btn = DarkButton(text="Wählen", bg=SUCCESS if active else ACCENT, size_hint_x=None, width=dp(94))
            btn.bind(on_release=lambda *_args, m=key: (popup_ref["popup"].dismiss(), self.set_performance_mode(m)))
            row.add_widget(btn)
            content.add_widget(row)
        popup = self.make_popup("", content, size_hint=(0.94, 0.80))
        popup_ref["popup"] = popup
        close_top.bind(on_release=popup.dismiss)
        popup.open()

    def open_collection_dashboard(self, *_):
        summary = CollectionAnalyticsV93.summarize(self.collection)
        wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text=f"[b]Sammlungs-Dashboard[/b]\n[color={markup_hex(MUTED)}]Übersicht über Karten, Sets, Artworks und Datenqualität.[/color]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        stats = GridLayout(cols=2 if self.ui_width_below(720) else 4, spacing=dp(8), size_hint_y=None)
        values = [
            ("Karten gesamt", summary["total"]),
            ("Verschiedene Einträge", summary["different"]),
            ("Artworks", summary["artworks"]),
            ("Sets", summary["sets"]),
            ("Doppelte Exemplare", summary["duplicates"]),
            ("Ohne Set", summary["without_set"]),
            ("Ohne Bild", summary["without_image"]),
        ]
        rows = math.ceil(len(values) / stats.cols)
        stats.height = dp(rows * 82 + max(0, rows - 1) * 8)
        for label, value in values:
            card = SurfaceBox(orientation="vertical", padding=dp(8), bg_color=CARD_BG)
            card.add_widget(DarkLabel(text=f"[b]{html_escape(str(value))}[/b]\n[color={markup_hex(MUTED)}]{html_escape(label)}[/color]", markup=True, halign="center"))
            stats.add_widget(card)
        wrapper.add_widget(stats)
        body = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        if summary.get("top_rarities"):
            body.add_widget(DarkLabel(text="[b]Häufigste Rarities[/b]", markup=True, size_hint_y=None, height=dp(30)))
            for rarity, count in summary["top_rarities"]:
                body.add_widget(DarkLabel(text=f"{html_escape(rarity)}: {count}", size_hint_y=None, height=dp(28)))
        actions = GridLayout(cols=1 if self.ui_width_below(560) else 2, spacing=dp(8), size_hint_y=None, height=dp(50))
        set_btn = DarkButton(text="Set-Fortschritt", bg=GOLD)
        collection_btn = DarkButton(text="Sammlung öffnen", bg=ACCENT_2)
        actions.add_widget(set_btn)
        actions.add_widget(collection_btn)
        body.add_widget(actions)
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"], do_scroll_x=False)
        scroll.add_widget(body)
        wrapper.add_widget(scroll)
        popup = self.make_popup("", wrapper, size_hint=(0.96, 0.90))
        close_top.bind(on_release=popup.dismiss)
        set_btn.bind(on_release=lambda *_: (popup.dismiss(), self.open_set_progress_popup()))
        collection_btn.bind(on_release=lambda *_: (popup.dismiss(), self.open_collection_popup()))
        popup.open()

    def open_set_progress_popup(self, *_):
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text=f"[b]Set-Fortschritt[/b]\n[color={markup_hex(MUTED)}]Vergleich zwischen deiner Sammlung und der lokalen Kartendatenbank.[/color]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        content.add_widget(header)
        status = DarkLabel(text="Lokale Datenbank wird ausgewertet…", color=MUTED, size_hint_y=None, height=dp(42))
        content.add_widget(status)
        rows_ref = {"rows": []}
        controls = GridLayout(cols=1 if self.ui_width_below(560) else 2, spacing=dp(8), size_hint_y=None, height=dp(48))
        progress_filter = DarkSpinner(text="Alle Sets", values=["Alle Sets", "Nur unvollständig", "Nur vollständig", "Nur mit Duplikaten"])
        export_btn = DarkButton(text="Set-Bericht exportieren", bg=ACCENT)
        controls.add_widget(progress_filter)
        controls.add_widget(export_btn)
        content.add_widget(controls)
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"], do_scroll_x=False)
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        content.add_widget(scroll)
        popup = self.make_popup("", content, size_hint=(0.96, 0.90))
        close_top.bind(on_release=popup.dismiss)
        export_btn.bind(on_release=lambda *_: self.export_set_progress_report(rows_ref.get("rows") or []))
        popup.open()

        def worker():
            try:
                database_cards = load_local_card_database("de") or load_local_card_database("") or []
                rows = CollectionAnalyticsV93.set_progress(self.collection, database_cards)
                rows_ref["rows"] = rows
                def render(*_):
                    grid.clear_widgets()
                    selected_filter = str(progress_filter.text or "Alle Sets")
                    visible_rows = []
                    for row in rows:
                        total_known = int(row.get("total_known") or 0)
                        owned_unique = int(row.get("owned_unique") or 0)
                        complete = bool(total_known and owned_unique >= total_known)
                        if selected_filter == "Nur unvollständig" and complete:
                            continue
                        if selected_filter == "Nur vollständig" and not complete:
                            continue
                        if selected_filter == "Nur mit Duplikaten" and int(row.get("duplicates") or 0) <= 0:
                            continue
                        visible_rows.append(row)
                    status.text = f"{len(visible_rows)} von {len(rows)} Set(s) angezeigt."
                    if not visible_rows:
                        grid.add_widget(DarkLabel(text="Keine passenden Sets vorhanden oder lokale Datenbank fehlt.", color=MUTED, size_hint_y=None, height=dp(70)))
                    for row in visible_rows[:300]:
                        total = row.get("total_known") or 0
                        progress = f"{row.get('owned_unique', 0)} / {total} ({row.get('percent', 0):.1f} %)" if total else f"{row.get('owned_unique', 0)} unterschiedliche Karten"
                        card = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(86), padding=dp(8), bg_color=CARD_BG)
                        card.add_widget(DarkLabel(text=(
                            f"[b]{html_escape(row.get('prefix', ''))} – {html_escape(row.get('name', ''))}[/b]\n"
                            f"Fortschritt: {html_escape(progress)} • Exemplare: {row.get('copies', 0)} • Doppelte: {row.get('duplicates', 0)}"
                            + (f" • Fehlend: {row.get('missing', 0)}" if total else "")
                        ), markup=True))
                        grid.add_widget(card)
                progress_filter.bind(text=lambda *_: render())
                Clock.schedule_once(render, 0)
            except Exception as exc:
                Clock.schedule_once(lambda *_: setattr(status, "text", f"Auswertung fehlgeschlagen: {exc}"), 0)
        threading.Thread(target=worker, daemon=True).start()

    def export_set_progress_report(self, rows):
        rows = list(rows or [])
        if not rows:
            self.show_error("Kein Set-Bericht", "Es wurden noch keine Set-Fortschrittsdaten berechnet.")
            return
        try:
            folder = self._writable_export_dir()
            path = os.path.join(folder, f"JustInCard_Set_Fortschritt_{time.strftime('%Y%m%d_%H%M%S')}.txt")
            lines = [f"Just InCard v{APP_VERSION} – Set-Fortschritt", time.strftime("Erstellt: %d.%m.%Y %H:%M:%S"), ""]
            for row in rows:
                total = int(row.get("total_known") or 0)
                lines.append(
                    f"{row.get('prefix', '')} | {row.get('name', '')} | vorhanden {row.get('owned_unique', 0)}"
                    + (f"/{total} | {row.get('percent', 0):.1f}% | fehlend {row.get('missing', 0)}" if total else " | Gesamtzahl unbekannt")
                    + f" | Exemplare {row.get('copies', 0)} | doppelt {row.get('duplicates', 0)}"
                )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            self.present_export_file(path, "text/plain", "Set-Bericht erstellt")
        except Exception as exc:
            self.show_error("Set-Bericht fehlgeschlagen", str(exc))

    def open_scan_learning_popup(self, *_):
        stats = self.scan_learning.stats() if getattr(self, "scan_learning", None) is not None else {"entries": 0, "uses": 0}
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(10), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text="[b]Lokale Scanner-Lernfunktion[/b]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        content.add_widget(header)
        content.add_widget(DarkLabel(text=(
            f"Gespeicherte Korrekturen: {stats.get('entries', 0)}\n"
            f"Bisherige Nutzungen: {stats.get('uses', 0)}\n\n"
            "Manuell bestätigte OCR-Korrekturen werden ausschließlich lokal gespeichert und bei künftigen Scans bevorzugt."
        ), color=TEXT))
        buttons = GridLayout(cols=1 if self.ui_width_below(520) else 2, spacing=dp(8), size_hint_y=None, height=dp(48))
        clear_btn = DarkButton(text="Lernregeln löschen", bg=DANGER)
        close_btn = DarkButton(text="Schließen", bg=INPUT_BG_2)
        buttons.add_widget(clear_btn)
        buttons.add_widget(close_btn)
        content.add_widget(buttons)
        popup = self.make_popup("", content, size_hint=(0.90, 0.60))
        close_top.bind(on_release=popup.dismiss)
        close_btn.bind(on_release=popup.dismiss)
        def clear_rules(*_):
            self.scan_learning.clear()
            popup.dismiss()
            self.show_info("Scanner-Lernfunktion", "Alle lokalen OCR-Lernregeln wurden gelöscht.")
        clear_btn.bind(on_release=clear_rules)
        popup.open()

    def push_collection_delta_undo(self, key, before_item, title="Sammlungsänderung"):
        try:
            payload = {
                "key": str(key or ""),
                "before_item": json.loads(json.dumps(before_item, ensure_ascii=False)) if before_item is not None else None,
            }
            return self.undo_manager.push("collection_delta", title, payload)
        except Exception:
            return None

    def push_collection_undo_snapshot(self, title="Sammlungsänderung"):
        try:
            snapshot = json.loads(json.dumps(self.collection, ensure_ascii=False))
            return self.undo_manager.push("collection_snapshot", title, {"collection": snapshot})
        except Exception:
            return None

    def undo_last_general_action(self, *_):
        manager = getattr(self, "undo_manager", None)
        action = manager.peek() if manager is not None else None
        if not action:
            self.show_info("Nichts rückgängig", "Es ist keine allgemeine Aktion zum Rückgängigmachen gespeichert.")
            return
        action = manager.pop()
        try:
            if action.get("type") == "collection_snapshot":
                snapshot = (action.get("payload") or {}).get("collection") or {}
                if not isinstance(snapshot, dict):
                    raise ValueError("Ungültiger Sammlungssnapshot")
                self.collection = snapshot
                self.save_collection(show_popup=False)
                self.update_collection_info()
                self.refresh_results_list()
                self.show_info("Rückgängig", f"Wiederhergestellt: {action.get('title', 'Sammlungsänderung')}")
                return
            if action.get("type") == "collection_delta":
                payload = action.get("payload") or {}
                key = str(payload.get("key") or "")
                before_item = payload.get("before_item")
                if not key:
                    raise ValueError("Ungültiger Sammlungsschlüssel")
                if before_item is None:
                    self.collection.pop(key, None)
                elif isinstance(before_item, dict):
                    self.collection[key] = before_item
                else:
                    raise ValueError("Ungültiger Sammlungsstand")
                self.save_collection(show_popup=False)
                self.update_collection_info()
                self.refresh_results_list()
                self.show_info("Rückgängig", f"Wiederhergestellt: {action.get('title', 'Sammlungsänderung')}")
                return
            self.show_info("Nicht unterstützt", "Diese Aktion kann in der aktuellen Version nicht automatisch rückgängig gemacht werden.")
        except Exception as exc:
            self.show_error("Rückgängig fehlgeschlagen", str(exc))

    def open_undo_history_popup(self, *_):
        actions = list(getattr(self.undo_manager, "actions", []) or [])
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text="[b]Rückgängig-Verlauf[/b]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        content.add_widget(header)
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        if not actions:
            grid.add_widget(DarkLabel(text="Noch keine allgemeinen Rückgängig-Aktionen gespeichert.", color=MUTED, size_hint_y=None, height=dp(70)))
        for item in actions[:40]:
            grid.add_widget(DarkLabel(text=f"[b]{html_escape(item.get('title', 'Aktion'))}[/b]\n{html_escape(item.get('created_label', ''))}", markup=True, size_hint_y=None, height=dp(56)))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        content.add_widget(scroll)
        actions_row = GridLayout(cols=1 if self.ui_width_below(520) else 2, spacing=dp(8), size_hint_y=None, height=dp(48))
        undo_btn = DarkButton(text="Letzte Aktion rückgängig", bg=DANGER)
        clear_btn = DarkButton(text="Verlauf leeren", bg=INPUT_BG_2)
        actions_row.add_widget(undo_btn)
        actions_row.add_widget(clear_btn)
        content.add_widget(actions_row)
        popup = self.make_popup("", content, size_hint=(0.92, 0.82))
        close_top.bind(on_release=popup.dismiss)
        undo_btn.bind(on_release=lambda *_: (popup.dismiss(), self.undo_last_general_action()))
        clear_btn.bind(on_release=lambda *_: (self.undo_manager.clear(), popup.dismiss(), self.show_info("Rückgängig", "Verlauf wurde geleert.")))
        popup.open()

    def open_deck_statistics_popup(self, *_):
        self.load_decks()
        wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text=f"[b]Deckstatistik[/b]\n[color={markup_hex(MUTED)}]Monster, Zauber, Fallen und Extra-Deck-Kategorien.[/color]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        if not self.decks:
            grid.add_widget(DarkLabel(text="Noch kein Deck vorhanden.", color=MUTED, size_hint_y=None, height=dp(70)))
        for deck in self.decks[:MAX_DECKS]:
            counts = {"Monster": 0, "Zauber": 0, "Fallen": 0, "Extra": 0, "Side": 0}
            for entry in deck.get("cards", []):
                card = entry.get("card") or {}
                amount = max(0, int(entry.get("count") or 0))
                zone = str(entry.get("zone") or self.deck_zone_for_card(card))
                ctype = str(card.get("type") or "")
                if zone == "extra": counts["Extra"] += amount
                elif zone == "side": counts["Side"] += amount
                elif "Spell" in ctype: counts["Zauber"] += amount
                elif "Trap" in ctype: counts["Fallen"] += amount
                else: counts["Monster"] += amount
            total = sum(counts.values())
            card = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(98), padding=dp(8), bg_color=CARD_BG)
            card.add_widget(DarkLabel(text=(
                f"[b]{html_escape(deck.get('name', 'Deck'))}[/b] • {total} Karten\n"
                f"Monster {counts['Monster']} • Zauber {counts['Zauber']} • Fallen {counts['Fallen']} • Extra {counts['Extra']} • Side {counts['Side']}"
            ), markup=True))
            grid.add_widget(card)
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        popup = self.make_popup("", wrapper, size_hint=(0.94, 0.86))
        close_top.bind(on_release=popup.dismiss)
        popup.open()

    def deck_zone_for_card(self, card):
        ctype = str((card or {}).get("type") or "").lower()
        if any(token in ctype for token in ("fusion", "synchro", "xyz", "link")):
            return "extra"
        return "main"

    def open_diagnostics_popup(self, *_):
        wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(DarkLabel(text=f"[b]App-Diagnose[/b]\n[color={markup_hex(MUTED)}]Dateien, Speicher, SQLite, Netzwerk und Bildschirmprofil.[/color]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        wrapper.add_widget(header)
        status = DarkLabel(text="Diagnose läuft…", color=MUTED, size_hint_y=None, height=dp(40))
        wrapper.add_widget(status)
        grid = GridLayout(cols=1, spacing=dp(7), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        popup = self.make_popup("", wrapper, size_hint=(0.96, 0.90))
        close_top.bind(on_release=popup.dismiss)
        popup.open()

        def worker():
            runner = DiagnosticsRunnerV93(os.path.dirname(os.path.abspath(__file__)), self.user_data_dir, self.app_database_file)
            tests = runner.run()
            profile = self.current_ui_profile()
            tests.append({"name": "UI-Profil", "ok": True, "detail": f"{profile.get('device_class')} / {profile.get('window_class')} • {int(profile.get('width_dp', 0))}×{int(profile.get('height_dp', 0))} dp • {profile.get('layout_mode')}", "severity": "info"})
            tests.append({"name": "Scanner-Modus", "ok": True, "detail": f"{self.scan_mode} • {self.resolved_performance_mode().title}", "severity": "info"})
            try:
                tests.append({"name": "Kamera-Modul", "ok": Camera is not None, "detail": "Kivy Camera verfügbar" if Camera is not None else "Kivy Camera nicht verfügbar; Android-Fallback wird genutzt", "severity": "warning"})
            except Exception:
                pass
            try:
                metrics = self.app_db.recent_performance(120) if getattr(self, "app_db", None) is not None else []
                grouped = {}
                for metric in metrics:
                    duration = metric.get("duration_ms")
                    if duration is None:
                        continue
                    grouped.setdefault(metric.get("event", "Unbekannt"), []).append(float(duration))
                for event_name, values in sorted(grouped.items()):
                    average = sum(values) / max(1, len(values))
                    tests.append({"name": f"Leistung {event_name}", "ok": True, "detail": f"Ø {average:.0f} ms aus {len(values)} Messung(en)", "severity": "info"})
            except Exception:
                pass
            def render(*_):
                grid.clear_widgets()
                errors = sum(1 for item in tests if not item.get("ok") and item.get("severity") == "error")
                warnings = sum(1 for item in tests if not item.get("ok") and item.get("severity") != "error")
                success = sum(1 for item in tests if item.get("ok"))
                status.text = f"{success} erfolgreich • {warnings} Warnung(en) • {errors} Fehler"
                for item in tests:
                    ok = bool(item.get("ok"))
                    prefix = "OK" if ok else ("WARNUNG" if item.get("severity") != "error" else "FEHLER")
                    color = TEXT if ok else ((1, 0.82, 0.55, 1) if item.get("severity") != "error" else (1, 0.65, 0.65, 1))
                    row = SurfaceBox(orientation="vertical", size_hint_y=None, padding=dp(8), bg_color=CARD_BG if ok else INPUT_BG_2)
                    label = AutoHeightLabel(
                        text=f"{prefix}: {item.get('name', 'Test')}\n{short_text(item.get('detail', ''), 220)}",
                        markup=False,
                        color=color,
                        min_height=dp(64),
                        height_padding=dp(16),
                        font_size=ui_font_px(12.5, body=True),
                    )
                    row.add_widget(label)
                    label.bind(height=lambda instance, value, target=row: setattr(target, "height", max(dp(72), value + dp(4))))
                    grid.add_widget(row)
            Clock.schedule_once(render, 0)
        threading.Thread(target=worker, daemon=True).start()

    def open_collection_metadata_editor(self, card):
        card = dict(card or {})
        key = self._first_matching_collection_key(card)
        if not key or key not in self.collection:
            self.show_error("Sammlungsdetails", "Diese Kartenvariante wurde in der Sammlung nicht gefunden.")
            return
        entry = self.collection[key]
        metadata = normalized_collection_metadata(entry.get("metadata") or {})
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(10), bg_color=PANEL_BG)
        wrapper.add_widget(DarkLabel(
            text=f"[b]Sammlungsdetails[/b]\n[color={markup_hex(MUTED)}]{html_escape(card.get('name', 'Karte'))} • {html_escape(artwork_label(card))}[/color]",
            markup=True, size_hint_y=None, height=dp(54), halign="left",
        ))
        profile = self.current_ui_profile()
        cols = 1 if float(profile.get("width_dp") or 0) < 620 else 2
        grid = GridLayout(cols=cols, size_hint_y=None, spacing=dp(8))
        grid.bind(minimum_height=grid.setter("height"))
        condition = DarkSpinner(text=metadata["condition"], values=list(CARD_CONDITIONS_V104), size_hint_y=None, height=dp(50))
        language = DarkInput(text=metadata["language"], hint_text="Sprache", size_hint_y=None, height=dp(50))
        edition = DarkSpinner(text=metadata["edition"], values=list(EDITION_OPTIONS_V104), size_hint_y=None, height=dp(50))
        storage = DarkInput(text=metadata["storage_location"], hint_text="Lagerort, z. B. Ordner 1 – Seite 14", size_hint_y=None, height=dp(50))
        purchase_date = DarkInput(text=metadata["purchase_date"], hint_text="Kaufdatum", size_hint_y=None, height=dp(50))
        purchase_price = DarkInput(text=metadata["purchase_price"], hint_text="Kaufpreis (optional)", size_hint_y=None, height=dp(50))
        note = DarkInput(text=metadata["note"], hint_text="Notiz", multiline=True, size_hint_y=None, height=dp(110))
        for widget in (condition, language, edition, storage, purchase_date, purchase_price, note):
            grid.add_widget(widget)
        wrapper.add_widget(grid)
        actions = GridLayout(cols=1 if self.ui_width_below(480) else 2, size_hint_y=None, height=dp(100 if self.ui_width_below(480) else 48), spacing=dp(8))
        save_btn = DarkButton(text="Details speichern", bg=SUCCESS)
        cancel_btn = DarkButton(text="Abbrechen", bg=INPUT_BG_2)
        actions.add_widget(save_btn)
        actions.add_widget(cancel_btn)
        wrapper.add_widget(actions)
        popup = self.make_popup("Sammlungsdetails", wrapper, size_hint=(0.94, 0.86))

        def save_details(*_):
            try:
                new_meta = normalized_collection_metadata({
                    "condition": condition.text,
                    "language": language.text.strip() or "Deutsch",
                    "edition": edition.text,
                    "storage_location": storage.text.strip(),
                    "purchase_date": purchase_date.text.strip(),
                    "purchase_price": purchase_price.text.strip(),
                    "note": note.text.strip(),
                    "last_updated": time.time(),
                })
                self.collection[key]["metadata"] = new_meta
                self.save_collection(show_popup=False)
                popup.dismiss()
                self.set_status("Sammlungsdetails gespeichert.")
            except Exception as exc:
                self.show_error("Sammlungsdetails", str(exc))

        save_btn.bind(on_release=save_details)
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def open_duplicate_variant_center(self, *_):
        groups = find_duplicate_variant_groups(self.collection)
        lines = ["Duplikate und Varianten", ""]
        if not groups:
            lines.append("Keine doppelten Varianten gefunden.")
        for index, group in enumerate(groups[:120], start=1):
            entries = group.get("entries") or []
            names = []
            for _key, entry in entries:
                card = entry.get("card") or {}
                meta = normalized_collection_metadata(entry.get("metadata") or {})
                set_name, set_code, rarity = collection_set_label(card)
                names.append(f"{card.get('name', 'Karte')} • {artwork_label(card)} • {set_code} • {rarity} • {meta['language']} • {meta['edition']} • {meta['condition']} • x{entry.get('count', 0)}")
            lines.append(f"{index}. Gesamt {group.get('total', 0)}")
            lines.extend("   " + value for value in names)
            lines.append("")
        self.show_scroll_text("Duplikate & Varianten", "\n".join(lines))

    def open_scan_review_center(self, *_):
        history = list(getattr(self, "scan_history", []) or [])
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(9), bg_color=PANEL_BG)
        wrapper.add_widget(DarkLabel(
            text="[b]Scan-Prüfzentrale[/b]\n[color=%s]Unsichere, manuelle und fehlgeschlagene Scans gesammelt prüfen.[/color]" % markup_hex(MUTED),
            markup=True, size_hint_y=None, height=dp(58), halign="left",
        ))
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"])
        scroll.add_widget(grid)
        wrapper.add_widget(scroll)
        relevant = []
        for item in reversed(history):
            confidence = int(item.get("confidence") or 0)
            status = str(item.get("status") or item.get("result") or "").casefold()
            if confidence < 80 or "fehler" in status or "fail" in status or "manual" in status or "manuell" in status:
                relevant.append(item)
        if not relevant:
            empty = SurfaceBox(orientation="vertical", size_hint_y=None, height=dp(82), padding=dp(10), bg_color=INPUT_BG)
            empty.add_widget(DarkLabel(text="Keine offenen oder unsicheren Scans vorhanden.", color=MUTED))
            grid.add_widget(empty)
        for index, item in enumerate(relevant[:100], start=1):
            card = item.get("card") or {}
            path = str(item.get("preview_path") or item.get("path") or "")
            row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(118), spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
            row.add_widget(Image(source=path if path and os.path.exists(path) else (resource_find(PREVIEW_PLACEHOLDER_FILE) or ""), allow_stretch=True, keep_ratio=True, size_hint_x=None, width=dp(78)))
            info = f"[b]{index}. {html_escape(card.get('name', 'Nicht erkannt'))}[/b]\nSicherheit: {int(item.get('confidence') or 0)} %\n{html_escape(confidence_breakdown_text(item) or str(item.get('error') or item.get('status') or 'Prüfung nötig'))}"
            row.add_widget(DarkLabel(text=info, markup=True, size_hint_x=0.72, halign="left"))
            row.add_widget(DarkButton(text="Historie", bg=ACCENT_2, size_hint_x=0.22, on_release=lambda *_: self.open_scan_history_popup()))
            grid.add_widget(row)
        footer = DarkButton(text="Scan-Historie öffnen", bg=ACCENT_2, size_hint_y=None, height=dp(48), on_release=lambda *_: self.open_scan_history_popup())
        wrapper.add_widget(footer)
        page = self.make_inline_page("scan_review_center", wrapper, back_to="more")
        page.open()

    def open_scanner_statistics_v104(self, *_):
        stats = scanner_learning_statistics(getattr(self, "scan_history", []) or [], getattr(getattr(self, "scan_timings", None), "data", {}) or {})
        lines = [
            "Scanner-Lernstatistik",
            "",
            f"Ausgewertete Scans: {stats['samples']}",
            f"Sofort sicher erkannt: {stats['safe']} ({stats['safe_rate']} %)",
            f"Nach Korrektur bestätigt: {stats['corrected']}",
            f"Manuell zugeordnet: {stats['manual']}",
            f"Nicht erkannt/Fehler: {stats['failed']} ({stats['failed_rate']} %)",
            f"Durchschnittliche Laufzeit: {stats['average_seconds'] if stats['average_seconds'] is not None else '-'} s",
            "",
            "Häufige Problemursachen:",
        ]
        if stats["top_reasons"]:
            lines.extend(f"• {reason} ({count}×)" for reason, count in stats["top_reasons"])
        else:
            lines.append("• Noch keine ausreichenden Fehlerdaten vorhanden.")
        self.show_scroll_text("Scanner-Statistik", "\n".join(lines))

    def open_deck_test_hand_popup(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        result = simulate_deck_hands(deck, samples=500, hand_size=5)
        if result.get("error"):
            self.show_error("Testhand", result["error"])
            return
        lines = [
            f"Deck: {deck.get('name', 'Deck')}",
            "Simulation: 500 Starthände mit je 5 Karten",
            "",
            f"Mindestens ein erkannter Starter: {result['starter_probability']} %",
            f"Mindestens eine Interaktion: {result['interaction_probability']} %",
            f"Zwei oder mehr potenziell tote Karten: {result['dead_two_plus_probability']} %",
            "",
            "Beispielhände:",
        ]
        for idx, hand in enumerate(result.get("example_hands") or [], start=1):
            lines.append(f"{idx}. " + " | ".join(hand))
        lines.append("")
        lines.append("Hinweis: Die Rollenerkennung arbeitet lokal über Namen und Effekttexte und ersetzt kein vollständiges Turnier-Simulationssystem.")
        self.show_scroll_text("Deck-Testhände", "\n".join(lines))

    def open_deck_explanation_popup(self, deck_index):
        if not (0 <= deck_index < len(self.decks)):
            return
        deck = self.decks[deck_index]
        report = explain_deck_synergy(deck)
        lines = [f"Deckanalyse: {deck.get('name', 'Deck')}", "", report.get("summary", ""), ""]
        archetypes = report.get("archetypes") or []
        if archetypes:
            lines.append("Stärkste Archetype-Schwerpunkte:")
            lines.extend(f"• {name}: {count} Karten" for name, count in archetypes)
            lines.append("")
        for role, title in (("starter", "Starter"), ("extender", "Extender"), ("interaction", "Interaktionen"), ("restriction", "Mögliche Einschränkungen")):
            values = report.get("roles", {}).get(role) or []
            lines.append(f"{title} ({len(values)}):")
            lines.append(", ".join(values[:24]) if values else "Keine eindeutig erkannt.")
            lines.append("")
        missing = []
        deck_names = set()
        deck_archetypes = set()
        deck_attributes = set()
        for entry in deck.get("cards", []):
            card = entry.get("card") or {}
            deck_names.add(normalize_search_text(card.get("name", "")))
            if card.get("archetype"):
                deck_archetypes.add(str(card.get("archetype")))
            if card.get("attribute"):
                deck_attributes.add(str(card.get("attribute")))
            key = entry.get("collection_key")
            owned = int(self.collection.get(key, {}).get("count", 0) or 0) if key in self.collection else 0
            wanted = int(entry.get("count", 0) or 0)
            if owned < wanted:
                missing.append((card.get("name", "Karte"), wanted - owned))
        if missing:
            lines.append("Fehlende Exemplare:")
            lines.extend(f"• {name}: {amount} Exemplar(e) fehlen" for name, amount in missing)
            lines.append("")

        replacement_candidates = []
        for key, item in self.collection.items():
            card = item.get("card") or {}
            if normalize_search_text(card.get("name", "")) in deck_names:
                continue
            score = 0
            if card.get("archetype") and str(card.get("archetype")) in deck_archetypes:
                score += 6
            if card.get("attribute") and str(card.get("attribute")) in deck_attributes:
                score += 2
            role = card_role(card)
            if role in {"starter", "extender", "interaction"}:
                score += 3
            if score > 0:
                replacement_candidates.append((score, card.get("name", "Karte"), role, int(item.get("count", 0) or 0)))
        replacement_candidates.sort(key=lambda value: (-value[0], normalize_search_text(value[1])))
        if replacement_candidates:
            lines.append("Passende Alternativen aus deiner Sammlung:")
            for score, name, role, amount in replacement_candidates[:12]:
                lines.append(f"• {name} • Rolle {role} • vorhanden {amount} • Synergie {score}")
            lines.append("")
        lines.append("Die lokale Analyse nutzt nur dein Deck und deine Sammlung. Die bestehende KI-Deckfunktion kann daraus zusätzliche Deckvorschläge erzeugen.")
        self.show_scroll_text("Deck-Synergieanalyse", "\n".join(lines))

    def open_offline_status_popup(self, *_):
        status = offline_status(self.local_database_dir, self.scan_artwork_index_file, network_available=None)
        profile = self.current_ui_profile()
        lines = [
            "Offline- und Geräteprofil",
            "",
            f"Geräteklasse: {profile.get('device_class')} / {profile.get('layout_mode')}",
            f"Fenster: {int(profile.get('width_dp', 0))} × {int(profile.get('height_dp', 0))} dp",
            f"Lokale Datenbank: {'bereit' if status['database_ready'] else 'nicht bereit'} ({status['database_files']} Dateien)",
            f"Artwork-Index: {'bereit' if status['artwork_index_ready'] else 'noch nicht aufgebaut'}",
            f"OCR-Modelle: {'bereit' if status['ocr_models_ready'] else 'nicht bereit'}",
            "",
            "Offline verfügbar:",
            "• Sammlung, Decks, lokale Suche und Backups",
            "• Galerie-OCR, Effektvergleich und lokaler Artwork-Abgleich, sofern Modelle/Index vorhanden sind",
            "• Export und Diagnose",
        ]
        self.show_scroll_text("Offline-Status", "\n".join(lines))

    def open_privacy_controls_popup(self, *_):
        values = dict(DEFAULT_PRIVACY_V104)
        values.update(getattr(self, "privacy_settings_v104", {}) or {})
        wrapper = SurfaceBox(orientation="vertical", spacing=dp(8), padding=dp(10), bg_color=PANEL_BG)
        wrapper.add_widget(DarkLabel(text="[b]Datenschutz & KI-Kontrolle[/b]\nLokale Verarbeitung ist Standard. Cloud-KI wird nur nach ausdrücklicher Aktivierung verwendet.", markup=True, size_hint_y=None, height=dp(64)))
        rows = []
        specs = [
            ("local_ai_enabled", "Lokale KI aktiv"),
            ("cloud_ai_enabled", "Online-KI aktiv"),
            ("allow_image_upload", "Bilder an Online-KI senden erlauben"),
            ("send_cropped_artwork_only", "Nur zugeschnittenes Artwork senden"),
            ("delete_scan_images_after_processing", "Scanbilder nach Verarbeitung löschen"),
            ("local_learning_enabled", "Lokale Lernfunktion aktiv"),
            ("include_images_in_diagnostics", "Bilder in Diagnosepaket erlauben"),
        ]
        for key, label in specs:
            row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8), padding=dp(8), bg_color=CARD_BG)
            row.add_widget(DarkLabel(text=label, halign="left"))
            check = CheckBox(active=bool(values.get(key)), size_hint_x=None, width=dp(48))
            row.add_widget(check)
            wrapper.add_widget(row)
            rows.append((key, check))
        actions = GridLayout(cols=2, size_hint_y=None, height=dp(48), spacing=dp(8))
        save_btn = DarkButton(text="Speichern", bg=SUCCESS)
        cancel_btn = DarkButton(text="Abbrechen", bg=INPUT_BG_2)
        actions.add_widget(save_btn)
        actions.add_widget(cancel_btn)
        wrapper.add_widget(actions)
        popup = self.make_popup("Datenschutz & KI", wrapper, size_hint=(0.94, 0.88))

        def save_privacy(*_):
            self.privacy_settings_v104 = {key: bool(check.active) for key, check in rows}
            self.cloud_ai_scan_enabled = bool(self.privacy_settings_v104.get("cloud_ai_enabled") and self.privacy_settings_v104.get("allow_image_upload"))
            self.save_settings()
            popup.dismiss()
            self.set_status("Datenschutz- und KI-Einstellungen gespeichert.")

        save_btn.bind(on_release=save_privacy)
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def open_automatic_backups_popup(self, *_):
        backups = self.auto_backup_manager.list_backups()
        lines = [
            "Automatische Sicherungen",
            "",
            f"Status: {'aktiv' if self.auto_backup_enabled else 'deaktiviert'}",
            "Intervall: höchstens einmal pro 24 Stunden",
            "Aufbewahrung: 5 Sicherungen",
            "",
        ]
        if backups:
            for path in backups:
                lines.append(f"• {time.strftime('%d.%m.%Y %H:%M', time.localtime(path.stat().st_mtime))} • {path.name} • {path.stat().st_size // 1024} KB")
        else:
            lines.append("Noch keine automatische Sicherung vorhanden.")
        lines.append("")
        lines.append("Eine automatische Sicherung wird beim Speichern der Sammlung erstellt, wenn das 24-Stunden-Intervall abgelaufen ist.")
        self.show_scroll_text("Automatische Backups", "\n".join(lines))

    def open_device_layout_info(self, *_):
        profile = self.current_ui_profile()
        is_tablet = bool(profile.get("is_tablet"))
        lines = [
            "Automatische Geräteerkennung",
            "",
            f"Erkannt: {'Tablet' if is_tablet else 'Smartphone'}",
            f"Geräteklasse: {profile.get('device_class')}",
            f"Layoutmodus: {profile.get('layout_mode')}",
            f"Breite/Höhe: {int(profile.get('width_dp', 0))} × {int(profile.get('height_dp', 0))} dp",
            f"Navigation: {'Seitenleiste' if profile.get('use_tablet_rail') else 'untere Navigationsleiste'}",
            "",
            "Tablet-Unterschiede:",
            "• mehrspaltige Suche und breitere Ergebnis-/Vorschauaufteilung",
            "• Seitenleiste ab geeigneter Breite statt Bottom-Navigation",
            "• größere Touchflächen und Karten",
            "• zwei- oder dreispaltige Einstellungen, Decks und Scannerbereiche",
            "• Querformat nutzt den verfügbaren Platz ohne gestreckte Smartphone-Ansicht",
            "",
            "Smartphone-Unterschiede:",
            "• einspaltige, scrollbare Seiten",
            "• Bottom-Navigation",
            "• kompaktere Abstände, Buttons und Vorschauflächen",
        ]
        self.show_scroll_text("Geräte-Layout", "\n".join(lines))

    def export_diagnostics_package_v104(self, *_):
        try:
            os.makedirs(self.diagnostics_dir, exist_ok=True)
            target = os.path.join(self.diagnostics_dir, time.strftime("JustInCard_Diagnose_%Y%m%d_%H%M%S.zip"))
            profile = self.current_ui_profile()
            payload = redact_diagnostics({
                "app_version": APP_VERSION,
                "app_build": APP_BUILD,
                "developer": APP_DEVELOPER,
                "admin": APP_ADMIN,
                "android_platform": platform,
                "ui_profile": profile,
                "settings": self.save_settings() if False else {
                    "theme": self.theme_name,
                    "performance_mode": self.performance_mode,
                    "privacy_v104": self.privacy_settings_v104,
                },
                "database_dir": self.local_database_dir,
                "collection_entries": len(self.collection),
                "deck_count": len(self.decks),
                "scan_history_entries": len(self.scan_history),
                "scanner_stats": scanner_learning_statistics(self.scan_history, getattr(self.scan_timings, "data", {}) or {}),
            })
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr("diagnostics_v104.json", json.dumps(payload, ensure_ascii=False, indent=2))
                for path in (self.crash_log_file, self.scan_timing_file, self.scan_learning_file):
                    try:
                        if path and os.path.exists(path) and os.path.getsize(path) > 0:
                            archive.write(path, arcname=os.path.basename(path))
                    except Exception:
                        pass
            self.show_info("Diagnosepaket erstellt", f"Persönliche Schlüssel und Notizen wurden entfernt.\n\n{target}")
        except Exception as exc:
            self.show_error("Diagnosepaket", str(exc))


    def open_settings_popup(self):
        wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        header.add_widget(DarkLabel(text=f"[b]Einstellungen[/b]  [color={markup_hex(MUTED)}]Darstellung, Daten, Export, Wartung • Entwickler: leenation[/color]", markup=True))
        close_top = self.make_close_button(bg=INPUT_BG_2)
        header.add_widget(close_top)
        wrapper.add_widget(header)

        scroll = ScrollView(bar_width=dp(6), scroll_type=["bars", "content"], do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))

        popup_ref = {"popup": None}
        def run_and_close(fn, close=True):
            def _run(*args):
                if close and popup_ref.get("popup"):
                    popup_ref["popup"].dismiss()
                fn(*args)
            return _run

        def section(title, subtitle, entries):
            card = SurfaceBox(orientation="vertical", padding=dp(8), spacing=dp(7), size_hint_y=None, bg_color=CARD_BG)
            card.bind(minimum_height=card.setter("height"))
            card.add_widget(DarkLabel(text=f"[b]{html_escape(title)}[/b]\n[color={markup_hex(MUTED)}]{html_escape(subtitle)}[/color]", markup=True, size_hint_y=None, height=dp(48)))
            cols = 1 if self.ui_width_below(560) else 2
            grid = GridLayout(cols=cols, spacing=dp(7), size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            for label, bg, fn, close in entries:
                grid.add_widget(DarkButton(text=label, bg=bg, size_hint_y=None, height=dp(50), on_release=run_and_close(fn, close)))
            card.add_widget(grid)
            body.add_widget(card)

        section("Darstellung & Hilfe", "Theme, Geräteprofil, Barrierefreiheit, Leistung und Unterstützung", [
            ("Theme wechseln / Farbenblind", ACCENT_2, lambda *_: self.toggle_theme(), True),
            ("Barrierefreiheit & WLAN", ACCENT_2, lambda *_: self.open_accessibility_popup(), True),
            ("Leistungsmodus", ACCENT_2, lambda *_: self.open_performance_mode_popup(), True),
            ("Hilfe & Support", ACCENT_2, lambda *_: self.open_info_popup(), True),
            ("App-Diagnose / Geräteprofil", ACCENT_2, lambda *_: self.open_diagnostics_popup(), True),
            ("Smartphone-/Tablet-Layout", ACCENT_2, lambda *_: self.open_device_layout_info(), True),
            ("Cache verwalten", ACCENT_2, lambda *_: self.open_cache_management_popup(), True),
        ])
        section("Scanner", "Live/Kamera-Modus, Galerie-Präzisionsscan, Lernfunktion und Historie", [
            ("Scanmodus: Schnell", ACCENT_2, lambda *_: self.set_scan_mode("schnell"), True),
            ("Scanmodus: Normal", ACCENT_2, lambda *_: self.set_scan_mode("normal"), True),
            ("Galerie: immer gründlich", ACCENT_2, lambda *_: self.show_info("Galerie-Präzisionsscan", "Galeriebilder werden automatisch gründlich mit Farbkanal-, Effekt- und Artwork-Abgleich verarbeitet."), True),
            ("Scanner-Zeiten", ACCENT_2, lambda *_: self.open_scan_timing_popup(), True),
            ("Scanner-Lernfunktion", ACCENT_2, lambda *_: self.open_scan_learning_popup(), True),
            ("Scan-Prüfzentrale", ACCENT_2, lambda *_: self.open_scan_review_center(), True),
            ("Scanner-Lernstatistik", ACCENT_2, lambda *_: self.open_scanner_statistics_v104(), True),
            ("Datenschutz & KI", ACCENT_2, lambda *_: self.open_privacy_controls_popup(), True),
            ("Scan-Historie", ACCENT_2, lambda *_: self.open_scan_history_popup(), True),
            ("Letzten Scan-Import rückgängig", DANGER, lambda *_: self.undo_last_scan_import(), True),
        ])
        section("Sammlung & Decks", "Dashboard, Set-Fortschritt, Rückgängig, Backup und Deckstatistik", [
            ("Sammlungs-Dashboard", ACCENT_2, lambda *_: self.open_collection_dashboard(), True),
            ("Set-Fortschritt", ACCENT_2, lambda *_: self.open_set_progress_popup(), True),
            ("Rückgängig-Verlauf", ACCENT_2, lambda *_: self.open_undo_history_popup(), True),
            ("Duplikate & Varianten", ACCENT_2, lambda *_: self.open_duplicate_variant_center(), True),
            ("Deckstatistik", ACCENT_2, lambda *_: self.open_deck_statistics_popup(), True),
            ("Sammlung speichern", ACCENT_2, lambda *_: self.save_collection(show_popup=True), True),
            ("Sammlung laden", ACCENT_2, lambda *_: self.load_collection(show_popup=True), True),
            ("Backup ZIP erstellen", ACCENT_2, lambda *_: self.export_backup_zip(), True),
            ("Backup ZIP wiederherstellen", ACCENT_2, lambda *_: self.import_backup_zip(), True),
            ("Automatische Backups", ACCENT_2, lambda *_: self.open_automatic_backups_popup(), True),
            ("App-Zustand speichern", ACCENT_2, lambda *_: self.save_session_state(show_popup=True), True),
            ("App-Zustand zurücksetzen", DANGER, lambda *_: self.clear_session_state(), True),
            ("Deck als TXT exportieren", ACCENT_2, lambda *_: self.export_current_deck_text(), True),
        ])
        section("Datenbank", "Offline-Daten, Reparatur und Web-Quellen", [
            ("Datenbank synchronisieren", ACCENT_2, lambda *_: self.open_database_popup(), True),
            ("Datenbank reparieren", ACCENT_2, lambda *_: self.repair_database(), True),
            ("Web-Quellen", ACCENT_2, lambda *_: self.open_external_sources_popup(), True),
            ("Karte lokal +", ACCENT_2, lambda *_: self.open_custom_card_popup(), True),
            ("Offline-Status", ACCENT_2, lambda *_: self.open_offline_status_popup(), True),
        ])
        section("Export & Fehler", "XLSX, Fehlerbericht und KI-Zugang", [
            ("Export XLSX", ACCENT_2, lambda *_: self.export_collection(), True),
            ("Fehlerbericht exportieren", ACCENT_2, lambda *_: self.export_error_report(), True),
            ("Diagnosepaket exportieren", ACCENT_2, lambda *_: self.export_diagnostics_package_v104(), True),
            ("KI-Key", ACCENT_2, lambda *_: self.open_ai_settings_popup(), True),
        ])

        scroll.add_widget(body)
        wrapper.add_widget(scroll)
        popup = self.make_inline_page("more", wrapper, back_to="search")
        popup_ref["popup"] = popup
        close_top.bind(on_release=popup.dismiss)
        popup.open()

    def export_collection(self):
        if not self.collection:
            self.show_error("Keine Karten", "Deine Sammlung ist leer.")
            return

        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        content.add_widget(DarkLabel(
            text="[b]XLSX-Export sortieren[/b]\nWähle, wie die Google-Sheets-Datei aufgebaut werden soll.",
            markup=True,
            color=TEXT,
            size_hint_y=None,
            height=dp(62),
        ))
        options = [
            ("Kategorie", "category", "Monster, Zauber, Fallen usw. in eigenen Tabellen"),
            ("Name A-Z", "name", "Eine Tabelle, alphabetisch nach Kartenname"),
            ("Anzahl", "count", "Eine Tabelle, höchste Anzahl zuerst"),
            ("Set/Code", "set", "Eine Tabelle, nach erstem Set-Code/Set-Namen"),
            ("Rarity", "rarity", "Eine Tabelle, nach erster bekannter Seltenheit"),
        ]
        popup_ref = {"popup": None}

        def choose_sort(label, mode):
            if popup_ref.get("popup"):
                popup_ref["popup"].dismiss()
            self.export_collection_with_sort(mode, label)

        for label, mode, desc in options:
            row = SurfaceBox(orientation="horizontal", size_hint_y=None, height=dp(58), spacing=dp(8), padding=dp(6), bg_color=CARD_BG)
            row.add_widget(DarkLabel(text=f"[b]{label}[/b]\n[color={markup_hex(MUTED)}]{desc}[/color]", markup=True))
            row.add_widget(DarkButton(text="Wählen", size_hint_x=None, width=dp(96), bg=ACCENT, on_release=lambda *_ , l=label, m=mode: choose_sort(l, m)))
            content.add_widget(row)

        cancel = DarkButton(text="Abbrechen", size_hint_y=None, height=dp(50), bg=INPUT_BG_2)
        content.add_widget(cancel)
        popup = self.make_popup("Export sortieren", content, size_hint=(0.94, 0.78))
        popup_ref["popup"] = popup
        cancel.bind(on_release=popup.dismiss)
        popup.open()

    def append_crash_log(self, exc, context=""):
        """Schreibt Fehler inklusive UI-/Geräteprofil in eine lokale Logdatei."""
        try:
            path = os.path.join(self.user_data_dir, "just_incard_crash.log")
            profile = getattr(self, "ui_profile", {}) or {}
            metrics = getattr(self, "screen_metrics", {}) or {}
            details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if isinstance(exc, BaseException) else str(exc)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("\n" + "=" * 72 + "\n")
                handle.write(time.strftime("%Y-%m-%d %H:%M:%S") + f" | Just InCard {APP_VERSION}\n")
                if context:
                    handle.write(f"Kontext: {context}\n")
                handle.write(f"Plattform: {platform}\n")
                handle.write(f"UI-Profil: {json.dumps(profile, ensure_ascii=False)}\n")
                handle.write(f"Display-Metriken: {json.dumps(metrics, ensure_ascii=False)}\n")
                handle.write(details + "\n")
            return path
        except Exception:
            return ""

    def _writable_export_dir(self):
        candidates = [
            "/storage/emulated/0/Download",
            os.path.join(os.path.expanduser("~"), "storage", "downloads"),
            self.user_data_dir,
        ]
        for folder in candidates:
            try:
                os.makedirs(folder, exist_ok=True)
                marker = os.path.join(folder, ".just_incard_write_test")
                with open(marker, "w", encoding="utf-8") as handle:
                    handle.write("ok")
                os.remove(marker)
                return folder
            except Exception:
                continue
        return self.user_data_dir

    def present_export_file(self, path, mime_type="application/octet-stream", title="Export fertig"):
        """Bietet unter Android den systemeigenen Speicherort-Dialog an."""
        if not path or not os.path.exists(path):
            self.show_error("Export fehlt", "Die erzeugte Datei wurde nicht gefunden.")
            return
        if platform != "android":
            self.show_info(title, f"Datei erstellt:\n{path}")
            return

        def done(uri):
            self.show_info(title, f"Datei wurde über Android gespeichert.\nZiel: {uri}")

        def failed(message):
            # Der lokale Export bleibt erhalten, auch wenn der Android-Dialog abgebrochen wird.
            self.show_info(title, f"Lokale Datei bleibt erhalten:\n{path}\n\nAndroid-Speicherdialog: {message}")

        started = start_android_create_document(
            path,
            mime_type,
            os.path.basename(path),
            lambda uri: Clock.schedule_once(lambda *_: done(uri), 0),
            lambda message: Clock.schedule_once(lambda *_: failed(message), 0),
        )
        if not started:
            self.show_info(title, f"Datei erstellt:\n{path}")

    def export_error_report(self, *_):
        """Exportiert einen technischen Bericht ohne den OpenAI-Schlüssel offenzulegen."""
        try:
            folder = self._writable_export_dir()
            stamp = str(time.time_ns())
            path = os.path.join(folder, f"JustInCard_Fehlerbericht_{stamp}.txt")
            crash_path = os.path.join(self.user_data_dir, "just_incard_crash.log")
            crash_tail = "Keine Crash-Logdatei vorhanden."
            try:
                if os.path.exists(crash_path):
                    with open(crash_path, "r", encoding="utf-8", errors="replace") as handle:
                        crash_tail = handle.read()[-12000:]
            except Exception:
                pass
            total_cards = sum(int(item.get("count", 0) or 0) for item in self.collection.values())
            lines = [
                f"Just InCard Fehlerbericht - Version {APP_VERSION}",
                time.strftime("Erstellt: %Y-%m-%d %H:%M:%S"),
                f"Plattform: {platform}",
                f"Kivy-Fenster: {int(Window.width)} x {int(Window.height)}",
                "UI-Profil: " + json.dumps(getattr(self, "ui_profile", {}) or {}, ensure_ascii=False, indent=2),
                "Display-Metriken: " + json.dumps(getattr(self, "screen_metrics", {}) or {}, ensure_ascii=False, indent=2),
                "Leistungsdaten: " + json.dumps(self.app_db.recent_performance(40) if getattr(self, "app_db", None) else [], ensure_ascii=False, indent=2),
                f"Theme: {self.theme_name}",
                f"Scanmodus: {self.scan_mode}",
                f"Sammlung: {total_cards} Karten / {len(self.collection)} Varianten",
                f"Decks: {len(self.decks)}",
                f"Letztes Scannerbild: {getattr(self, 'last_scan_photo', '') or '-'}",
                "",
                "Letzte Fehler:",
                crash_tail,
            ]
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            self.show_info("Fehlerbericht erstellt", f"Datei gespeichert:\n{path}")
        except Exception as exc:
            self.append_crash_log(exc, "Fehlerbericht exportieren")
            self.show_error("Fehlerbericht fehlgeschlagen", str(exc))

    def export_backup_zip(self, *_):
        """Erstellt ein konsistentes ZIP-Backup der wichtigen Nutzerdaten."""
        try:
            self.save_collection(show_popup=False)
            self.save_decks()
            self.save_settings()
            self.save_scan_history()
            self.save_session_state(show_popup=False)
            folder = self._writable_export_dir()
            stamp = str(time.time_ns())
            output = os.path.join(folder, f"{BACKUP_PREFIX}_{stamp}.zip")
            candidates = [
                self.collection_file,
                self.settings_file,
                self.decks_file,
                self.custom_cards_file,
                self.scan_history_file,
                self.scan_undo_file,
                getattr(self, "scan_learning_file", ""),
                getattr(self, "undo_history_file", ""),
                getattr(self, "incremental_sync_file", ""),
                getattr(self, "session_state_file", ""),
                getattr(self, "app_database_file", ""),
                os.path.join(self.user_data_dir, "just_incard_crash.log"),
            ]
            if os.path.isdir(self.local_database_dir):
                for name in os.listdir(self.local_database_dir):
                    path = os.path.join(self.local_database_dir, name)
                    if os.path.isfile(path):
                        candidates.append(path)
            added = 0
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                manifest = {
                    "app": APP_DISPLAY_NAME,
                    "version": APP_VERSION,
                    "build": APP_BUILD,
                    "backup_schema": BACKUP_SCHEMA_VERSION,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "collection_entries": len(self.collection),
                    "decks": len(self.decks),
                }
                archive.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                for source in candidates:
                    try:
                        if source and os.path.isfile(source):
                            if os.path.commonpath([os.path.abspath(source), os.path.abspath(self.local_database_dir)]) == os.path.abspath(self.local_database_dir):
                                arcname = os.path.join("card_database", os.path.basename(source))
                            else:
                                arcname = os.path.basename(source)
                            archive.write(source, arcname)
                            added += 1
                    except Exception:
                        continue
            self.show_info("Backup erstellt", f"{added} Datendateien wurden gesichert:\n{output}")
        except Exception as exc:
            self.append_crash_log(exc, "Backup ZIP")
            self.show_error("Backup fehlgeschlagen", str(exc))

    def repair_database(self, *_):
        """Repariert alle vorhandenen Sprachdatenbanken in einem Hintergrund-Thread."""
        self.set_status("Datenbank-Reparatur läuft...")

        def worker():
            repaired = []
            failures = []
            for lang in ["de", "", "fr", "it", "pt", "es", "ja", "ko"]:
                code = lang or "en"
                json_path = local_database_file(lang)
                sqlite_path = local_sqlite_database_file(lang)
                if not os.path.exists(json_path) and not os.path.exists(sqlite_path):
                    continue
                try:
                    path, count = repair_card_database_file(lang)
                    repaired.append(f"{scan_language_label(lang)}: {count} Karten")
                except Exception as exc:
                    failures.append(f"{code}: {exc}")
            def finish(*_):
                if repaired:
                    msg = "Repariert:\n" + "\n".join(repaired)
                    if failures:
                        msg += "\n\nFehler:\n" + "\n".join(failures)
                    self.set_status("Datenbank-Reparatur abgeschlossen.")
                    self.show_info("Datenbank repariert", msg)
                else:
                    self.set_status("Keine lokale Datenbank zum Reparieren gefunden.")
                    self.show_info("Keine Datenbank", "Es wurde keine lokale JSON- oder SQLite-Datenbank gefunden.")
            Clock.schedule_once(finish, 0)
        threading.Thread(target=worker, daemon=True).start()

    def export_current_deck_text(self, deck_index=None, *_):
        """Exportiert ein ausgewähltes Deck als gut lesbare TXT-Datei."""
        if not self.decks:
            self.show_error("Kein Deck", "Es ist noch kein Deck vorhanden.")
            return
        if deck_index is None and len(self.decks) > 1:
            content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
            content.add_widget(DarkLabel(text="[b]Deck für TXT-Export auswählen[/b]", markup=True, size_hint_y=None, height=dp(40)))
            grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            scroll = ScrollView(do_scroll_x=False)
            scroll.add_widget(grid)
            content.add_widget(scroll)
            popup = self.make_popup("Deck exportieren", content, size_hint=(0.90, 0.76))
            for idx, deck in enumerate(self.decks[:MAX_DECKS]):
                btn = DarkButton(text=f"{deck.get('name', f'Deck {idx + 1}')} ({self.deck_card_total(deck)} Karten)", size_hint_y=None, height=dp(48), bg=INPUT_BG_2)
                btn.bind(on_release=lambda _btn, i=idx: (popup.dismiss(), self.export_current_deck_text(i)))
                grid.add_widget(btn)
            popup.open()
            return
        try:
            index = int(deck_index if deck_index is not None else 0)
            if not (0 <= index < len(self.decks)):
                raise ValueError("Ungültiges Deck")
            deck = self.decks[index]
            folder = self._writable_export_dir()
            safe_name = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß _-]+", "_", str(deck.get("name") or f"Deck_{index + 1}")).strip() or f"Deck_{index + 1}"
            path = os.path.join(folder, f"{safe_name}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
            rows = []
            for item in deck.get("cards", []):
                card = item.get("card") or {}
                count = int(item.get("count", 0) or 0)
                if count <= 0:
                    continue
                set_name, set_code, rarity = collection_set_label(card)
                rows.append((normalize_search_text(card.get("name", "")), count, card.get("name", "Unbekannte Karte"), set_code, rarity))
            rows.sort(key=lambda row: row[0])
            lines = [
                str(deck.get("name") or f"Deck {index + 1}"),
                f"Gesamt: {sum(row[1] for row in rows)} Karten",
                "=" * 48,
            ]
            for _, count, name, set_code, rarity in rows:
                suffix = " | ".join(part for part in [set_code, rarity] if part)
                lines.append(f"{count}x {name}" + (f" | {suffix}" if suffix else ""))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            self.show_info("Deck exportiert", f"TXT-Datei gespeichert:\n{path}")
        except Exception as exc:
            self.append_crash_log(exc, "Deck-TXT-Export")
            self.show_error("Deck-Export fehlgeschlagen", str(exc))

    def export_collection_with_sort(self, sort_mode="category", sort_label="Kategorie"):
        try:
            path = self.make_export_path()
            export_xlsx(self.collection, path, sort_mode=sort_mode)
            self.show_info("Export fertig", f"Sortierung: {sort_label}\nDatei erstellt:\n{path}\n\nDu kannst diese XLSX-Datei in Google Sheets öffnen oder importieren.")
        except Exception as exc:
            self.show_error("Export fehlgeschlagen", str(exc))

    def make_export_path(self):
        stamp = str(time.time_ns())
        filename = f"yugioh_sammlung_google_sheets_{stamp}.xlsx"
        candidates = [
            "/storage/emulated/0/Download",
            os.path.join(os.path.expanduser("~"), "storage", "downloads"),
            self.user_data_dir,
        ]
        for folder in candidates:
            try:
                os.makedirs(folder, exist_ok=True)
                test = os.path.join(folder, ".write_test")
                with open(test, "w", encoding="utf-8") as f:
                    f.write("ok")
                try:
                    os.remove(test)
                except Exception:
                    pass
                return os.path.join(folder, filename)
            except Exception:
                continue
        return os.path.join(self.user_data_dir, filename)

    def make_close_button(self, bg=None):
        """Kompatibilitätsplatzhalter für alte Dialoglayouts.

        Sichtbare X-Schaltflächen sind seit v9.6 vollständig entfernt. Dialoge
        werden über Android-Zurück, die Zurück-Geste oder ihre fachlichen
        Aktionsbuttons geschlossen.
        """
        button = DarkButton(
            text="",
            bg=(0, 0, 0, 0),
            size_hint=(None, None),
            width=0,
            height=0,
            opacity=0,
            disabled=True,
            no_wrap=True,
        )
        return button

    def _popup_content_has_close_button(self, content):
        return False

    def make_popup(self, title, content, size_hint=(0.86, 0.5)):
        """Erzeugt einen Android-gerechten Dialog ohne sichtbare X-Schaltfläche."""
        title_text = str(title or "").strip()
        popup_content = content
        if title_text:
            wrapper = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
            header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
            header.add_widget(AutoHeightLabel(
                text=title_text,
                markup=False,
                color=TEXT,
                font_size=ui_font_px(15, body=True),
                min_height=dp(42),
                height_padding=dp(8),
            ))
            wrapper.add_widget(header)
            wrapper.add_widget(content)
            popup_content = wrapper

        popup = AdaptivePopup(
            app_ref=self,
            requested_size_hint=size_hint,
            title="",
            content=popup_content,
            separator_color=(0, 0, 0, 0),
            title_color=TEXT,
            title_align="left",
            background="atlas://data/images/defaulttheme/modalview-background",
            background_color=POPUP_BG,
            auto_dismiss=True,
        )
        try:
            popup.title_size = 0
            popup.separator_height = 0
            popup.title_padding = (0, 0)
            popup.padding = 0
        except Exception:
            pass
        try:
            self._open_popups.append(popup)
            def _remove_popup(*_):
                try:
                    while popup in self._open_popups:
                        self._open_popups.remove(popup)
                except Exception:
                    pass
            popup.bind(on_dismiss=_remove_popup)
        except Exception:
            pass
        return popup

    def show_info(self, title, msg):
        self.show_popup(title, msg, False)

    def show_error(self, title, msg):
        self.show_popup(title, msg, True)

    def show_popup(self, title, msg, is_error=False):
        content = SurfaceBox(orientation="vertical", padding=dp(10), spacing=dp(8), bg_color=PANEL_BG)
        scroll = ScrollView(bar_width=dp(5), scroll_type=["bars", "content"], do_scroll_x=False)
        message_label = AutoHeightLabel(
            text=msg,
            color=TEXT if not is_error else (1, 0.75, 0.75, 1),
            min_height=dp(70),
            height_padding=dp(14),
            font_size=ui_font_px(13, body=True),
        )
        scroll.add_widget(message_label)
        content.add_widget(scroll)
        btn = DarkButton(text="OK", size_hint_y=None, height=dp(48), bg=DANGER if is_error else ACCENT, no_wrap=True)
        content.add_widget(btn)
        profile = self.current_ui_profile()
        compact = profile.get("device_class") == "compact_phone"
        estimated_lines = max(3, str(msg or "").count("\n") + int(math.ceil(len(str(msg or "")) / float(42 if compact else 58))))
        target_h = min(0.88, max(0.34, 0.24 + estimated_lines * (0.037 if compact else 0.030)))
        popup = self.make_popup(title, content, size_hint=(0.96 if compact else 0.90, target_h))
        btn.bind(on_release=popup.dismiss)
        popup.open()


# ---------------- XLSX Export ohne openpyxl ----------------

def sheet_name(name):
    name = re.sub(r"[\\/*?:\[\]]", "-", name)
    return name[:31] or "Tabelle"


def xml_cell(value, row_idx, col_idx):
    col = ""
    n = col_idx
    while n:
        n, rem = divmod(n - 1, 26)
        col = chr(65 + rem) + col
    ref = f"{col}{row_idx}"
    if value is None:
        value = ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    value = xml_escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'


def build_sheet_xml(rows):
    xml_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = [xml_cell(value, r_idx, c_idx) for c_idx, value in enumerate(row, start=1)]
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetData>' + "".join(xml_rows) + '</sheetData></worksheet>'
    )


def export_xlsx(collection, output_path, sort_mode="category"):
    headers = ["Anzahl", "Name", "Stufe", "Pendelskala", "Eigenschaft", "Typ", "DEF", "ATK", "Set", "Set-Code", "Rarity", "Artwork", "Effekt"]

    def first_set(card):
        selected = get_collection_set_from_card(card)
        if selected:
            return selected
        sets = card.get("card_sets") or []
        return sets[0] if sets else {}

    def row_for(card, count):
        set_item = first_set(card)
        return [
            count,
            card.get("name", ""),
            get_level_value(card),
            pendulum_text(card),
            card.get("attribute", ""),
            card.get("race", ""),
            card.get("def", ""),
            card.get("atk", ""),
            set_item.get("set_name", ""),
            set_item.get("set_code", ""),
            set_item.get("set_rarity", ""),
            artwork_label(card),
            card.get("desc", ""),
        ]

    entries_all = []
    for item in collection.values():
        count = int(item.get("count", 0))
        card = item.get("card", {})
        entries_all.append((card, count))

    sheets = []
    if sort_mode == "category":
        grouped = {cat: [] for cat in CATEGORY_ORDER}
        for card, count in entries_all:
            cat = category_for(card)
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append((card, count))
        for cat in CATEGORY_ORDER:
            entries = grouped.get(cat, [])
            if not entries:
                continue
            entries.sort(key=lambda pair: category_sort_key(pair[0]))
            rows = [headers] + [row_for(card, count) for card, count in entries]
            sheets.append((sheet_name(cat), rows))
    else:
        def sort_key(pair):
            card, count = pair
            set_item = first_set(card)
            if sort_mode == "name":
                return ((card.get("name") or "").lower(), category_sort_key(card))
            if sort_mode == "count":
                return (-count, (card.get("name") or "").lower())
            if sort_mode == "set":
                return ((set_item.get("set_code") or "").lower(), (set_item.get("set_name") or "").lower(), (card.get("name") or "").lower())
            if sort_mode == "rarity":
                return ((set_item.get("set_rarity") or "").lower(), (card.get("name") or "").lower())
            return category_sort_key(card)
        entries_all.sort(key=sort_key)
        rows = [headers] + [row_for(card, count) for card, count in entries_all]
        sheet_titles = {"name": "Nach Name", "count": "Nach Anzahl", "set": "Nach Set", "rarity": "Nach Rarity"}
        sheets.append((sheet_name(sheet_titles.get(sort_mode, "Sammlung")), rows))

    if not sheets:
        sheets.append(("Sammlung", [headers]))

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
    ]
    for idx in range(1, len(sheets) + 1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append('</Types>')

    workbook_sheets = []
    workbook_rels = []
    for idx, (name, _) in enumerate(sheets, start=1):
        workbook_sheets.append(f'<sheet name="{xml_escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>')
        workbook_rels.append(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>' + "".join(workbook_sheets) + '</sheets></workbook>'
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(workbook_rels) + '</Relationships>'
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(content_types))
        z.writestr("_rels/.rels", rels_xml)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        for idx, (_, rows) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{idx}.xml", build_sheet_xml(rows))


if __name__ == "__main__":
    try:
        YuGiOhApp().run()
    except Exception as exc:
        # Letzte Sicherheitsleine: Fehler protokollieren, statt einen stillen Crash zu erzeugen.
        try:
            with open(os.path.join(os.path.expanduser("~"), "just_incard_crash.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(exc) + "\n")
        except Exception:
            pass
        raise
