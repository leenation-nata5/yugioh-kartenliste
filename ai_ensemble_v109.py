# -*- coding: utf-8 -*-
"""Multi-Engine-KI-Orchestrator für Just InCard v11.2.

Die Datei bleibt importierbar, auch wenn einzelne native/optionale KI-Runtimes auf
Android nicht vorhanden sind. Der Scanner nutzt immer die verfügbaren Engines und
fällt stabil auf die bereits vorhandene ML-Kit-/Pillow-/Datenbank-Pipeline zurück.

Priorität:
1. exakter Set-Code
2. exakter Passcode
3. Metadaten-Gegenprüfung (ATK/DEF/Level/Rang/Link/Typ/Sprache)
4. visuelle Übereinstimmung (OpenCV ORB/AKAZE + MobileNetV3)
5. Kartenname
6. Effekttext / semantischer Abgleich
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ENGINE_STACK_V109: List[Dict[str, Any]] = [
    {
        "id": "yolo_card_detector",
        "label": "YOLOv8/YOLO11 Nano",
        "purpose": "Mehrkarten- und Ordnerseiten-Erkennung",
        "runtime": "ONNX Runtime Android / optionales Modellpaket",
        "priority": 10,
    },
    {
        "id": "mediapipe_object_detector",
        "label": "Google MediaPipe",
        "purpose": "schnelle lokale Karten-/Objektstruktur-Erkennung",
        "runtime": "MediaPipe Tasks Vision Android",
        "priority": 20,
    },
    {
        "id": "mlkit_ocr",
        "label": "Google ML Kit Vision OCR",
        "purpose": "schnelle native Offline-OCR für Set-Code, Passcode und Namen",
        "runtime": "Android lokal",
        "priority": 30,
    },
    {
        "id": "paddleocr",
        "label": "PaddleOCR PP-OCRv5 Mobile",
        "purpose": "schwierige Folien, Sprachen und unruhige Hintergründe",
        "runtime": "ONNX Runtime Android / optionales Modellpaket",
        "priority": 40,
    },
    {
        "id": "easyocr",
        "label": "EasyOCR",
        "purpose": "lange strukturierte Effekttexte als Zusatzsignal",
        "runtime": "optionaler Python-/Server-Fallback; nicht erzwungen im APK",
        "priority": 50,
    },
    {
        "id": "opencv_orb_akaze",
        "label": "OpenCV ORB/AKAZE",
        "purpose": "lokale Artwork-Merkmale unabhängig von OCR",
        "runtime": "OpenCV Android",
        "priority": 60,
    },
    {
        "id": "mobilenet_v3_embedder",
        "label": "MobileNetV3 Image Embedder",
        "purpose": "robuster Artwork-Fingerabdruck",
        "runtime": "MediaPipe/LiteRT Android",
        "priority": 70,
    },
    {
        "id": "sentence_transformer",
        "label": "Sentence-Transformers MiniLM",
        "purpose": "semantischer Effekttextabgleich nach OCR-Fehlern",
        "runtime": "ONNX Runtime Android / optionales Modellpaket",
        "priority": 80,
    },
]

SCRIPT_ENGINE_ORDER_V109: Dict[str, List[str]] = {
    "latin": ["mlkit_ocr", "paddleocr", "easyocr"],
    "japanese": ["mlkit_ocr", "paddleocr", "easyocr"],
    "korean": ["mlkit_ocr", "paddleocr", "easyocr"],
    "chinese": ["mlkit_ocr", "paddleocr", "easyocr"],
    "cyrillic": ["paddleocr", "easyocr", "mlkit_ocr"],
    "arabic": ["paddleocr", "easyocr", "mlkit_ocr"],
    "devanagari": ["mlkit_ocr", "paddleocr", "easyocr"],
    "unknown": ["mlkit_ocr", "paddleocr", "easyocr"],
}

IDENTIFIER_PRIORITY_V109 = {
    "Set-Code": 0,
    "Passcode": 1,
    "Metadata": 2,
    "Artwork": 3,
    "Name": 4,
    "Effect": 5,
}

MODEL_ASSET_PATHS_V109 = {
    "yolo_card_detector": "models/yolo_card_detector.onnx",
    "mobilenet_v3_embedder": "models/mobilenet_v3_small_075_224_embedder.tflite",
    "paddleocr_det": "models/paddleocr/det/inference.onnx",
    "paddleocr_rec_latin": "models/paddleocr/rec_latin/inference.onnx",
    "minilm": "models/minilm/model_quantized.onnx",
    "minilm_vocab": "models/minilm/minilm.vocab",
}


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+", " ", text).strip()


def detect_script(value: Any) -> str:
    text = str(value or "")
    if re.search(r"[\u3040-\u30ff]", text):
        return "japanese"
    if re.search(r"[\uac00-\ud7af]", text):
        return "korean"
    if re.search(r"[\u3400-\u9fff]", text):
        return "chinese"
    if re.search(r"[\u0400-\u04ff]", text):
        return "cyrillic"
    if re.search(r"[\u0600-\u06ff]", text):
        return "arabic"
    if re.search(r"[\u0900-\u097f]", text):
        return "devanagari"
    if re.search(r"[A-Za-zÀ-ž]", text):
        return "latin"
    return "unknown"


def ocr_engine_plan(text_hint: Any = "") -> List[str]:
    return list(SCRIPT_ENGINE_ORDER_V109.get(detect_script(text_hint), SCRIPT_ENGINE_ORDER_V109["unknown"]))


def engine_availability(project_root: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    root = Path(project_root or Path(__file__).resolve().parent)
    android = os.environ.get("ANDROID_ARGUMENT") is not None
    pyjnius = importlib.util.find_spec("jnius") is not None
    optional = {
        "easyocr": importlib.util.find_spec("easyocr") is not None,
        "paddleocr_python": importlib.util.find_spec("paddleocr") is not None,
        "opencv_python": importlib.util.find_spec("cv2") is not None,
        "sentence_transformers_python": importlib.util.find_spec("sentence_transformers") is not None,
    }
    out: Dict[str, Dict[str, Any]] = {}
    for spec in ENGINE_STACK_V109:
        engine_id = spec["id"]
        asset = MODEL_ASSET_PATHS_V109.get(engine_id)
        out[engine_id] = {
            "label": spec["label"],
            "runtime": spec["runtime"],
            "android": android,
            "bridge_available": bool(android and pyjnius),
            "asset": asset or "",
            "asset_available": bool(asset and (root / asset).is_file()),
            "optional_python": bool(optional.get(engine_id) or optional.get(f"{engine_id}_python")),
        }
    out["paddleocr"]["optional_python"] = optional["paddleocr_python"]
    out["opencv_orb_akaze"]["optional_python"] = optional["opencv_python"]
    out["sentence_transformer"]["optional_python"] = optional["sentence_transformers_python"]
    return out


def _token_set(text: Any) -> set[str]:
    return {token for token in _norm(text).split() if len(token) >= 3}


def _char_ngrams(text: Any, n: int = 3) -> set[str]:
    compact = re.sub(r"\s+", " ", _norm(text))
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def semantic_fallback_similarity(a: Any, b: Any) -> float:
    """Vollständig lokaler, modellfreier Fallback für verstümmelte OCR-Texte."""
    a_tokens, b_tokens = _token_set(a), _token_set(b)
    a_grams, b_grams = _char_ngrams(a), _char_ngrams(b)
    token_jaccard = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    gram_jaccard = len(a_grams & b_grams) / max(1, len(a_grams | b_grams))
    coverage = len(a_tokens & b_tokens) / max(1, min(len(a_tokens), len(b_tokens)))
    return round(max(0.0, min(1.0, token_jaccard * 0.34 + gram_jaccard * 0.42 + coverage * 0.24)), 4)


def optional_sentence_transformer_similarity(a: Any, b: Any) -> Optional[float]:
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        embeddings = model.encode([str(a or ""), str(b or "")], normalize_embeddings=True)
        score = float(sum(float(x) * float(y) for x, y in zip(embeddings[0], embeddings[1])))
        return max(0.0, min(1.0, score))
    except Exception:
        return None


def semantic_effect_similarity(a: Any, b: Any) -> float:
    model_score = optional_sentence_transformer_similarity(a, b)
    if model_score is not None:
        return round(model_score, 4)
    return semantic_fallback_similarity(a, b)


def stable_image_session_key(path: Any, source_index: int = 0, batch_id: Any = "") -> str:
    p = Path(str(path or ""))
    try:
        stat = p.stat()
        fingerprint = f"{p.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{source_index}|{batch_id}"
    except Exception:
        fingerprint = f"{p}|{source_index}|{batch_id}"
    return hashlib.sha256(fingerprint.encode("utf-8", "ignore")).hexdigest()[:24]


@dataclass
class EnsembleEvidenceV109:
    set_code_exact: bool = False
    passcode_exact: bool = False
    metadata_score: float = 0.0
    metadata_conflicts: int = 0
    artwork_orb: float = 0.0
    artwork_akaze: float = 0.0
    artwork_embedding: float = 0.0
    name_similarity: float = 0.0
    effect_similarity: float = 0.0
    semantic_similarity: float = 0.0
    language_match: float = 0.0
    quality_score: float = 0.0
    engine_votes: Dict[str, float] = field(default_factory=dict)


def ensemble_confidence(e: EnsembleEvidenceV109) -> float:
    # Exakte Identifikatoren dominieren und können nicht vom Namen überschrieben werden.
    if e.set_code_exact:
        base = 0.78
    elif e.passcode_exact:
        base = 0.76
    else:
        base = 0.0
    visual = max(e.artwork_orb, e.artwork_akaze, e.artwork_embedding)
    score = base
    score += max(0.0, min(1.0, e.metadata_score)) * 0.10
    score += visual * 0.10
    # Name/Effekt sind nur Fallback-Signale.
    if not (e.set_code_exact or e.passcode_exact):
        score += max(0.0, min(1.0, e.name_similarity)) * 0.18
        score += max(0.0, min(1.0, e.effect_similarity)) * 0.12
        score += max(0.0, min(1.0, e.semantic_similarity)) * 0.12
        score += visual * 0.25
    else:
        score += max(0.0, min(1.0, e.effect_similarity)) * 0.03
        score += max(0.0, min(1.0, e.semantic_similarity)) * 0.02
    score += max(0.0, min(1.0, e.language_match)) * 0.025
    score += max(0.0, min(1.0, e.quality_score)) * 0.015
    score += min(0.04, sum(max(0.0, min(1.0, v)) for v in e.engine_votes.values()) * 0.01)
    score -= min(0.48, max(0, int(e.metadata_conflicts)) * 0.16)
    return round(max(0.0, min(1.0, score)), 4)


def _kind(item: Dict[str, Any]) -> str:
    return str((item.get("candidate") or {}).get("kind") or item.get("kind") or "")


def rerank_scan_results_v109(
    items: Iterable[Dict[str, Any]],
    *,
    ocr_text: str = "",
    quality: Optional[Dict[str, Any]] = None,
    scan_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Strikte, modellübergreifende Rangfolge ohne Karten-/Artwork-Vermischung."""
    out: List[Dict[str, Any]] = []
    q = max(0.0, min(1.0, float((quality or {}).get("score") or 0.0) / 100.0))
    for raw in items or []:
        item = dict(raw)
        card = item.get("card") or {}
        kind = _kind(item)
        exact = bool(item.get("exact"))
        card_desc = str(card.get("desc") or card.get("description") or "")
        semantic = float(item.get("semantic_similarity") or 0.0)
        if not semantic and ocr_text and card_desc and not (exact and kind in {"Set-Code", "Passcode"}):
            semantic = semantic_effect_similarity(ocr_text, card_desc)
        evidence = EnsembleEvidenceV109(
            set_code_exact=bool(exact and kind == "Set-Code"),
            passcode_exact=bool(exact and kind == "Passcode"),
            metadata_score=float(item.get("metadata_score") or item.get("stats_match") or 0.0),
            metadata_conflicts=len(item.get("metadata_conflicts") or []),
            artwork_orb=float(item.get("orb_similarity") or 0.0),
            artwork_akaze=float(item.get("akaze_similarity") or 0.0),
            artwork_embedding=float(item.get("artwork_similarity") or item.get("embedding_similarity") or 0.0),
            name_similarity=float(item.get("name_similarity") or (1.0 if exact and kind == "Name" else 0.0)),
            effect_similarity=float(item.get("effect_similarity") or 0.0),
            semantic_similarity=semantic,
            language_match=float(item.get("language_match") or (1.0 if item.get("language") not in (None, "") else 0.5)),
            quality_score=q,
            engine_votes=dict(item.get("engine_votes") or {}),
        )
        conf = ensemble_confidence(evidence)
        item["semantic_similarity_v109"] = semantic
        item["ensemble_confidence_v109"] = conf
        item["identifier_priority_v109"] = IDENTIFIER_PRIORITY_V109.get(kind, 99)
        item["score"] = float(item.get("score") or 0.0) + conf * 500.0
        if item.get("metadata_severe_conflict"):
            item["score"] -= 600.0
        # Artwork darf nie zwischen Bild-Sessions geteilt werden.
        source_id = item.get("source_id") or item.get("scan_source_id")
        if source_id:
            item["artwork_scope_v109"] = str(source_id)
        out.append(item)

    def _sort_key(item: Dict[str, Any]):
        priority = item.get("identifier_priority_v109")
        if priority is None:
            priority = 99
        return (
            -int(priority),
            bool(item.get("exact")),
            not bool(item.get("metadata_severe_conflict")),
            float(item.get("ensemble_confidence_v109") or 0.0),
            float(item.get("score") or 0.0),
        )

    out.sort(key=_sort_key, reverse=True)
    return out


def model_stack_summary() -> str:
    return " → ".join(spec["label"] for spec in sorted(ENGINE_STACK_V109, key=lambda x: x["priority"]))
