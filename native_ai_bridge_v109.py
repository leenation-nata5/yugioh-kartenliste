# -*- coding: utf-8 -*-
"""Sicherer Python-Adapter für die optionalen Android-KI-Bridges in v11.2.3."""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional


def _bridge():
    # Nicht von ANDROID_ARGUMENT abhängig machen: einige Android-/Kivy-Starts
    # setzen die Variable verspätet oder gar nicht, obwohl Pyjnius verfügbar ist.
    try:
        from jnius import autoclass
        return autoclass("org.yugioh.kartenliste.NativeAiScanner")
    except Exception:
        return None


def native_status() -> Dict[str, Any]:
    bridge = _bridge()
    if bridge is None:
        return {"available": False, "engines": []}
    try:
        return json.loads(str(bridge.statusJson()))
    except Exception as exc:
        return {"available": False, "engines": [], "error": str(exc)}


def mlkit_ocr(path: str, script: str = "latin") -> Optional[str]:
    bridge = _bridge()
    if bridge is None:
        return None
    try:
        return str(bridge.ocrText(str(path), str(script or "latin")))
    except Exception:
        return None


def detect_card_regions(path: str) -> List[Dict[str, Any]]:
    bridge = _bridge()
    if bridge is None:
        return []
    try:
        return list(json.loads(str(bridge.detectCardRegions(str(path)))))
    except Exception:
        return []


def orb_similarity(path_a: str, path_b: str) -> Optional[float]:
    bridge = _bridge()
    if bridge is None:
        return None
    try:
        return float(bridge.compareOrb(str(path_a), str(path_b)))
    except Exception:
        return None


def akaze_similarity(path_a: str, path_b: str) -> Optional[float]:
    bridge = _bridge()
    if bridge is None:
        return None
    try:
        return float(bridge.compareAkaze(str(path_a), str(path_b)))
    except Exception:
        return None


def yolo_regions(path: str, model_path: str) -> List[Dict[str, Any]]:
    bridge = _bridge()
    if bridge is None:
        return []
    try:
        return list(json.loads(str(bridge.detectYoloCards(str(path), str(model_path), 0.28))))
    except Exception:
        return []


def mediapipe_regions(path: str, model_path: str) -> List[Dict[str, Any]]:
    """Optionale MediaPipe-Objekterkennung; fällt ohne Modell/Bridge leer zurück."""
    bridge = _bridge()
    if bridge is None:
        return []
    try:
        return list(json.loads(str(bridge.detectMediaPipeCards(str(path), str(model_path), 0.24))))
    except Exception:
        return []


def mobilenet_similarity(path_a: str, path_b: str, model_path: str) -> Optional[float]:
    """Vergleicht zwei Artworks über den optionalen MobileNetV3-Embedder."""
    bridge = _bridge()
    if bridge is None:
        return None
    try:
        return float(bridge.compareMobileNet(str(path_a), str(path_b), str(model_path)))
    except Exception:
        return None


def paddle_ocr(path: str, det_model: str, rec_model: str, dict_path: str = "") -> Optional[str]:
    """Optionaler nativer PaddleOCR-Adapter. Gibt ohne Modell/Runtimes None zurück."""
    bridge = _bridge()
    if bridge is None:
        return None
    try:
        value = str(bridge.paddleOcrText(str(path), str(det_model), str(rec_model), str(dict_path)))
        return value or None
    except Exception:
        return None
