# -*- coding: utf-8 -*-
"""Galerie-Multi-Engine-Orchestrator für Just InCard v12.0.0.

Die Galerie verarbeitet jedes Ausgangsbild und jede erkannte Kartenfläche als
separate Scan-Session. Kartenflächen aus YOLO, MediaPipe, OpenCV und dem
Pillow-Fallback werden zusammengeführt, ohne Resultate oder Artworks zwischen
Bildquellen zu teilen.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REGION_ENGINE_WEIGHTS_V1093: Dict[str, float] = {
    "yolo-onnx": 1.00,
    "yolo": 1.00,
    "mediapipe": 0.94,
    "mediapipe-object-detector": 0.94,
    "opencv-contour": 0.80,
    "opencv-python": 0.78,
    "native-ai": 0.76,
    "pillow-edge": 0.64,
    "screenshot": 0.60,
    "legacy": 0.56,
    "fallback": 0.30,
}

OCR_ENGINE_WEIGHTS_V1093: Dict[str, float] = {
    "mlkit_latin": 1.00,
    "mlkit_japanese": 0.98,
    "mlkit_korean": 0.98,
    "mlkit_chinese": 0.98,
    "mlkit_devanagari": 0.96,
    "paddleocr": 0.95,
    "easyocr": 0.84,
    "tesseract": 0.70,
}

GALLERY_MULTI_ENGINE_PLAN_V1093: List[str] = [
    "YOLOv8/YOLO11 Nano",
    "Google MediaPipe",
    "Google ML Kit Vision OCR",
    "PaddleOCR",
    "EasyOCR",
    "OpenCV ORB/AKAZE",
    "MobileNetV3",
    "Sentence-Transformers MiniLM",
]


def _bbox(value: Any) -> Optional[Tuple[float, float, float, float]]:
    if isinstance(value, dict):
        if value.get("bbox"):
            value = value.get("bbox")
        else:
            x = float(value.get("x") or 0.0)
            y = float(value.get("y") or 0.0)
            w = float(value.get("width") or 0.0)
            h = float(value.get("height") or 0.0)
            value = (x, y, x + w, y + h)
    try:
        x1, y1, x2, y2 = map(float, value)
    except Exception:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_iou(a: Any, b: Any) -> float:
    aa, bb = _bbox(a), _bbox(b)
    if aa is None or bb is None:
        return 0.0
    ax1, ay1, ax2, ay2 = aa
    bx1, by1, bx2, by2 = bb
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    return inter / max(1.0, area_a + area_b - inter)


def bbox_containment(a: Any, b: Any) -> float:
    """Anteil der kleineren Box, der von der größeren Box abgedeckt wird.

    Anders als IoU erkennt dieser Wert auch typische Innenkonturen einer Karte
    (Artwork-/Textfeld), deren IoU zur gesamten Karte trotz fast vollständiger
    Einbettung klein sein kann.
    """
    aa, bb = _bbox(a), _bbox(b)
    if aa is None or bb is None:
        return 0.0
    ax1, ay1, ax2, ay2 = aa
    bx1, by1, bx2, by2 = bb
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    return inter / max(1.0, min(area_a, area_b))


def _bbox_area(value: Any) -> float:
    box = _bbox(value)
    if box is None:
        return 0.0
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def suppress_nested_regions(regions: Iterable[Dict[str, Any]], containment_threshold: float = 0.86) -> List[Dict[str, Any]]:
    """Entfernt Innenkonturen, ohne benachbarte Karten zu verschlucken.

    Eine kleinere Region wird nur verworfen, wenn sie fast vollständig in einer
    deutlich größeren, mindestens ähnlich plausiblen Kartenregion liegt. Das ist
    entscheidend für Einzelkartenfotos, bei denen OpenCV sonst Artwork, Effekt-
    und Pendeltextfeld zusätzlich als vermeintliche Kartenflächen meldet.
    """
    items = [dict(item or {}) for item in (regions or []) if _bbox((item or {}).get("bbox")) is not None]
    if len(items) < 2:
        return items
    ranked = sorted(
        items,
        key=lambda item: (float(item.get("detection_score") or 0.0), _bbox_area(item.get("bbox"))),
        reverse=True,
    )
    kept: List[Dict[str, Any]] = []
    for candidate in ranked:
        c_area = _bbox_area(candidate.get("bbox"))
        c_score = float(candidate.get("detection_score") or 0.0)
        nested = False
        for parent in kept:
            p_area = _bbox_area(parent.get("bbox"))
            if p_area <= c_area * 1.22:
                continue
            containment = bbox_containment(candidate.get("bbox"), parent.get("bbox"))
            parent_score = float(parent.get("detection_score") or 0.0)
            # Sehr kleine Innenfelder werden aggressiver unterdrückt; bei ähnlich
            # großen Regionen verlangen wir nahezu vollständige Einbettung.
            area_ratio = c_area / max(1.0, p_area)
            required = 0.78 if area_ratio <= 0.46 else float(containment_threshold)
            if containment >= required and parent_score + 0.08 >= c_score:
                nested = True
                break
        if not nested:
            kept.append(candidate)
    return kept


def _engine_weight(engine: Any) -> float:
    name = str(engine or "legacy").strip().lower()
    for key, weight in REGION_ENGINE_WEIGHTS_V1093.items():
        if key in name:
            return weight
    return REGION_ENGINE_WEIGHTS_V1093["legacy"]


def normalize_region_detection(
    raw: Dict[str, Any],
    *,
    image_width: int,
    image_height: int,
    default_engine: str = "legacy",
) -> Optional[Dict[str, Any]]:
    box = _bbox(raw)
    if box is None:
        return None
    x1, y1, x2, y2 = box
    x1 = max(0.0, min(float(image_width), x1))
    y1 = max(0.0, min(float(image_height), y1))
    x2 = max(0.0, min(float(image_width), x2))
    y2 = max(0.0, min(float(image_height), y2))
    if x2 - x1 < 28 or y2 - y1 < 40:
        return None
    engine = str(raw.get("detector") or raw.get("engine") or default_engine)
    confidence = float(raw.get("detector_confidence") or raw.get("confidence") or 0.52)
    ratio = (x2 - x1) / max(1.0, y2 - y1)
    portrait_ratio = ratio if ratio <= 1.0 else 1.0 / ratio
    # Trading-card-like aspect ratio. Landscape cards are accepted after rotation.
    ratio_score = max(0.0, 1.0 - abs(portrait_ratio - (1.0 / 1.45)) / 0.42)
    area = (x2 - x1) * (y2 - y1)
    coverage = area / max(1.0, float(image_width * image_height))
    weighted = max(0.0, min(1.0, confidence)) * _engine_weight(engine)
    weighted = min(1.0, weighted * 0.82 + ratio_score * 0.18)
    return {
        "bbox": (int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))),
        "coverage": coverage,
        "portrait": (y2 - y1) >= (x2 - x1),
        "detector": engine,
        "detectors": [engine],
        "detector_confidence": confidence,
        "detection_score": weighted,
        "ratio_score": ratio_score,
    }


def fuse_region_detections(
    detections: Iterable[Dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    max_cards: int = 64,
    iou_threshold: float = 0.48,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in detections or []:
        item = normalize_region_detection(
            dict(raw or {}),
            image_width=image_width,
            image_height=image_height,
        )
        if item is not None:
            normalized.append(item)
    normalized.sort(key=lambda item: float(item.get("detection_score") or 0.0), reverse=True)

    clusters: List[List[Dict[str, Any]]] = []
    for item in normalized:
        matched = None
        for cluster in clusters:
            if max(bbox_iou(item["bbox"], other["bbox"]) for other in cluster) >= iou_threshold:
                matched = cluster
                break
        if matched is None:
            clusters.append([item])
        else:
            matched.append(item)

    fused: List[Dict[str, Any]] = []
    for cluster in clusters:
        weights = [max(0.05, float(item.get("detection_score") or 0.0)) for item in cluster]
        total = sum(weights) or 1.0
        coords = [item["bbox"] for item in cluster]
        x1 = sum(box[0] * weight for box, weight in zip(coords, weights)) / total
        y1 = sum(box[1] * weight for box, weight in zip(coords, weights)) / total
        x2 = sum(box[2] * weight for box, weight in zip(coords, weights)) / total
        y2 = sum(box[3] * weight for box, weight in zip(coords, weights)) / total
        engines: List[str] = []
        for item in cluster:
            for engine in item.get("detectors") or [item.get("detector")]:
                if engine and engine not in engines:
                    engines.append(str(engine))
        consensus_bonus = min(0.18, max(0, len(engines) - 1) * 0.06)
        best = max(cluster, key=lambda item: float(item.get("detection_score") or 0.0))
        box = (int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))
        coverage = ((box[2] - box[0]) * (box[3] - box[1])) / max(1.0, float(image_width * image_height))
        fused.append({
            "bbox": box,
            "coverage": coverage,
            "portrait": (box[3] - box[1]) >= (box[2] - box[0]),
            "detector": best.get("detector") or "multi-engine",
            "detectors": engines,
            "detector_confidence": max(float(item.get("detector_confidence") or 0.0) for item in cluster),
            "detection_score": min(1.0, float(best.get("detection_score") or 0.0) + consensus_bonus),
            "detector_consensus": len(engines),
        })

    fused.sort(
        key=lambda item: (
            float(item.get("detection_score") or 0.0),
            int(item.get("detector_consensus") or 0),
            float(item.get("coverage") or 0.0),
        ),
        reverse=True,
    )
    # Zweite Stufe gegen ineinanderliegende Innenkonturen. Weighted-NMS allein
    # reicht hier nicht, weil ein Artworkfeld nur eine geringe IoU mit der ganzen
    # Karte besitzt, obwohl es vollständig in ihr liegt.
    fused = suppress_nested_regions(fused, containment_threshold=0.86)
    out = fused[: max(1, int(max_cards or 64))]
    # Stable visual order: top-to-bottom, then left-to-right.
    out.sort(key=lambda item: (int(item["bbox"][1]), int(item["bbox"][0])))
    for index, item in enumerate(out, start=1):
        item["index"] = index
    return out


def stable_region_session_id(source_id: Any, bbox: Any, region_index: int = 0) -> str:
    box = _bbox(bbox) or (0.0, 0.0, 0.0, 0.0)
    payload = f"{source_id}|{region_index}|" + ",".join(str(int(round(v))) for v in box)
    return "region_" + hashlib.sha256(payload.encode("utf-8", "ignore")).hexdigest()[:24]


def merge_ocr_engine_outputs(outputs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Führt OCR-Texte zusammen und behält Engine-Provenienz pro Zeile."""
    line_scores: Dict[str, Dict[str, Any]] = {}
    engine_texts: Dict[str, str] = {}
    for raw in outputs or []:
        engine = str(raw.get("engine") or "unknown")
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        engine_texts[engine] = text
        weight = float(raw.get("weight") or OCR_ENGINE_WEIGHTS_V1093.get(engine, 0.72))
        for line in text.splitlines():
            cleaned = re.sub(r"\s+", " ", line).strip()
            if len(cleaned) < 2:
                continue
            signature = re.sub(r"[^a-z0-9]+", "", cleaned.casefold())
            if not signature:
                continue
            item = line_scores.setdefault(signature, {
                "text": cleaned,
                "score": 0.0,
                "engines": [],
            })
            item["score"] += weight
            if engine not in item["engines"]:
                item["engines"].append(engine)
            if len(cleaned) > len(item["text"]):
                item["text"] = cleaned
    lines = sorted(
        line_scores.values(),
        key=lambda item: (len(item.get("engines") or []), float(item.get("score") or 0.0), len(item.get("text") or "")),
        reverse=True,
    )
    return {
        "text": "\n".join(item["text"] for item in lines),
        "lines": lines,
        "engine_texts": engine_texts,
        "engines": list(engine_texts.keys()),
    }


def gallery_engine_summary() -> str:
    return " → ".join(GALLERY_MULTI_ENGINE_PLAN_V1093)
