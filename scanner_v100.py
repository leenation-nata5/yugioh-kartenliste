# -*- coding: utf-8 -*-
"""Scanner-Kern fuer Just InCard v12.0.0.

Die Datei ist absichtlich Kivy-unabhaengig. Sie enthaelt Zeitbudgets, Messwerte,
Dateiformatregeln und kleine Bewertungs-/Normalisierungshelfer fuer den Scanner.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from ai_scanner_v102 import AI_MODEL_STACK_V102, TEXT_COLOR_PROFILES_V102

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff",
    ".heic", ".heif", ".avif",
}

SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/gif",
    "image/tiff", "image/heic", "image/heif", "image/avif",
}

# Zielwerte gelten fuer eine einzelne, gut fotografierte Karte auf einem typischen
# Mittelklasse-Androidgeraet mit bereits installierter lokaler Kartendatenbank.
SCAN_MODE_PROFILES: Dict[str, Dict[str, Any]] = {
    "schnell": {
        "label": "Schnell",
        "target_min_seconds": 2.0,
        "target_max_seconds": 4.0,
        "hard_timeout_seconds": 6.0,
        "max_attempts": 1,
        "guided_variants": 0,
        "detect_regions": False,
        "multiple_cards": False,
        "perspective": False,
        "artwork": False,
        "artwork_candidates": 0,
        "max_candidates": 3,
        "max_languages": 2,
        "max_cards_per_query": 6,
        "network_fallback_queries": 1,
        "ocr_scripts": ("latin",),
        "description": "Ein schneller OCR-Lauf, lokale Exaktsuche und nur ein kurzer Netzwerk-Fallback.",
    },
    "normal": {
        "label": "Normal",
        "target_min_seconds": 3.0,
        "target_max_seconds": 7.0,
        "hard_timeout_seconds": 10.0,
        "max_attempts": 1,
        "guided_variants": 1,
        "detect_regions": True,
        "multiple_cards": False,
        "perspective": True,
        "artwork": True,
        "artwork_candidates": 2,
        "max_candidates": 5,
        "max_languages": 3,
        "max_cards_per_query": 8,
        "network_fallback_queries": 1,
        "ocr_scripts": ("latin", "auto_fallback"),
        "description": "Kartenzuschnitt, eine Hilfsvariante und begrenzter Artwork-Abgleich aus dem Cache.",
    },
    "gründlich": {
        "label": "Gründlich",
        "target_min_seconds": 5.0,
        "target_max_seconds": 12.0,
        "hard_timeout_seconds": 16.0,
        "max_attempts": 2,
        "guided_variants": 2,
        "detect_regions": True,
        "multiple_cards": True,
        "perspective": True,
        "artwork": True,
        "artwork_candidates": 3,
        "max_candidates": 8,
        "max_languages": 4,
        "max_cards_per_query": 10,
        "network_fallback_queries": 2,
        "ocr_scripts": ("latin", "auto_fallback"),
        "description": "Galerie-Präzisionsscan mit Farbkanal-OCR, Effektabgleich, Mehrkarten-Erkennung und Artwork-Fallback.",
        "color_ocr_variants": 12,
        "effect_matching": True,
        "effect_candidate_pool": 80,
        "effect_min_similarity": 0.24,
    },
}


def scan_mode_profile(mode: str) -> Dict[str, Any]:
    key = str(mode or "normal").strip().lower()
    return dict(SCAN_MODE_PROFILES.get(key, SCAN_MODE_PROFILES["normal"]))


GALLERY_SCAN_MODE = "gründlich"


def gallery_scan_profile() -> Dict[str, Any]:
    """Festes Präzisionsprofil für Galerieimporte.

    Galerieimporte besitzen bewusst keine Schnell-/Normal-Auswahl mehr. Live- und
    Kamerascans können weiterhin Schnell oder Normal verwenden.
    """
    profile = scan_mode_profile(GALLERY_SCAN_MODE)
    profile.update({
        "label": "Galerie – Gründlich",
        "target_min_seconds": 8.0,
        "target_max_seconds": 22.0,
        "hard_timeout_seconds": 36.0,
        "max_attempts": 3,
        "guided_variants": 4,
        "color_ocr_variants": 12,
        "detect_regions": True,
        "multiple_cards": True,
        "perspective": True,
        "artwork": True,
        "artwork_candidates": 6,
        "max_candidates": 18,
        "max_languages": 10,
        "max_cards_per_query": 24,
        "network_fallback_queries": 3,
        "effect_matching": True,
        "effect_candidate_pool": 80,
        "effect_min_similarity": 0.24,
        "description": "Automatischer Galerie-Präzisionsscan mit KI-Hybridpipeline aus Kartendetektion, Artwork-Suche, OCR und Effektabgleich.",
        "ai_models": [item["id"] for item in AI_MODEL_STACK_V102],
        "text_color_profiles": list(TEXT_COLOR_PROFILES_V102),
        "ai_runtime_estimate": {"min_seconds": 8.0, "avg_seconds": 18.0, "max_seconds": 36.0},
    })
    return profile


_EFFECT_STOPWORDS = {
    # Deutsch
    "aber", "alle", "allen", "aller", "alles", "auch", "auf", "aus", "bei", "beim",
    "bis", "dann", "dass", "dein", "deine", "dem", "den", "der", "des", "die", "dies",
    "diese", "dieser", "dieses", "durch", "einer", "eines", "einen", "eine", "falls",
    "für", "gegen", "hat", "haben", "hier", "ihn", "ihre", "ihrem", "ihren", "immer",
    "ist", "kann", "karte", "karten", "kein", "keine", "mit", "musst", "nicht", "oder",
    "sein", "seine", "seinem", "seinen", "sich", "sind", "statt", "während", "wenn",
    "wird", "wurde", "wurden", "zum", "zur",
    # Englisch / romanische Sprachen – häufige Funktionswörter
    "about", "after", "also", "and", "any", "are", "avec", "card", "cards", "ce", "ces",
    "con", "cuando", "dans", "del", "des", "during", "effect", "elle", "esta", "este",
    "from", "into", "leur", "mais", "monster", "monsters", "nicht", "para", "pero", "puedes",
    "que", "questa", "questo", "son", "sont", "that", "the", "their", "then", "this",
    "those", "une", "vous", "when", "with", "your",
}


def normalize_effect_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_scan_text(value)).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'")
    # Unicode-Buchstaben/-Zahlen erhalten, damit auch japanische, koreanische und
    # chinesische Effekttexte verglichen werden können.
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def effect_tokens(value: Any, limit: int = 90) -> List[str]:
    """Robuste Effektwörter für mehrsprachigen OCR-/Datenbankabgleich."""
    normalized = normalize_effect_text(value)
    result: List[str] = []
    seen = set()
    for token in normalized.split():
        if token in _EFFECT_STOPWORDS:
            continue
        if token.isdigit():
            if not (1 <= len(token) <= 4):
                continue
        elif len(token) < 4:
            continue
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= max(1, int(limit or 90)):
            break
    return result


def effect_search_terms(value: Any, limit: int = 5) -> List[str]:
    """Wählt markante Wörter statt kompletter, fehleranfälliger OCR-Sätze."""
    tokens = effect_tokens(value, limit=120)
    tokens.sort(key=lambda token: (0 if token.isdigit() else 1, len(token), token), reverse=True)
    return tokens[: max(1, int(limit or 5))]


def effect_similarity(ocr_text: Any, card_text: Any) -> float:
    """Kombiniert Wortüberschneidung, Wortfolgen und Zeichenähnlichkeit."""
    left = effect_tokens(ocr_text, limit=140)
    right = effect_tokens(card_text, limit=180)
    if not left or not right:
        return 0.0
    left_set, right_set = set(left), set(right)
    intersection = left_set & right_set
    union = left_set | right_set
    jaccard = len(intersection) / max(1, len(union))
    coverage = len(intersection) / max(1, min(len(left_set), len(right_set)))

    # Längere, seltenere Wörter sind für Karteneffekte besonders aussagekräftig.
    weighted_total = sum(max(1, len(token) - 3) for token in left_set)
    weighted_hit = sum(max(1, len(token) - 3) for token in intersection)
    weighted = weighted_hit / max(1, weighted_total)

    left_compact = " ".join(left[:70])
    right_compact = " ".join(right[:100])
    sequence = 0.0
    try:
        from difflib import SequenceMatcher
        sequence = SequenceMatcher(None, left_compact, right_compact).ratio()
    except Exception:
        pass
    return max(0.0, min(1.0, 0.18 * jaccard + 0.34 * coverage + 0.34 * weighted + 0.14 * sequence))


@dataclass
class ScanDeadlineV100:
    started_at: float
    timeout_seconds: float

    @classmethod
    def start(cls, timeout_seconds: float) -> "ScanDeadlineV100":
        return cls(time.perf_counter(), max(0.25, float(timeout_seconds or 0.25)))

    @property
    def deadline_at(self) -> float:
        return self.started_at + self.timeout_seconds

    def elapsed(self) -> float:
        return max(0.0, time.perf_counter() - self.started_at)

    def remaining(self) -> float:
        return max(0.0, self.deadline_at - time.perf_counter())

    def expired(self, reserve_seconds: float = 0.0) -> bool:
        return self.remaining() <= max(0.0, float(reserve_seconds or 0.0))


class ScanTimingStoreV100:
    """Kleine lokale Historie realer Scannerzeiten pro Modus."""

    def __init__(self, path: str, max_entries_per_mode: int = 40):
        self.path = str(path or "")
        self.max_entries_per_mode = max(5, int(max_entries_per_mode or 40))
        self.data: Dict[str, List[Dict[str, Any]]] = {key: [] for key in SCAN_MODE_PROFILES}
        self._load()

    def _load(self) -> None:
        try:
            if not self.path or not os.path.exists(self.path):
                return
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return
            for key in self.data:
                values = payload.get(key) or []
                if isinstance(values, list):
                    self.data[key] = [item for item in values if isinstance(item, dict)][-self.max_entries_per_mode :]
        except Exception:
            pass

    def _save(self) -> None:
        try:
            if not self.path:
                return
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def record(self, mode: str, seconds: float, success: bool, source: str = "single", details: Optional[Dict[str, Any]] = None) -> None:
        key = str(mode or "normal").lower()
        if key not in self.data:
            key = "normal"
        entry = {
            "seconds": round(max(0.0, float(seconds or 0.0)), 3),
            "success": bool(success),
            "source": str(source or "single"),
            "timestamp": time.time(),
            "details": dict(details or {}),
        }
        self.data[key].append(entry)
        self.data[key] = self.data[key][-self.max_entries_per_mode :]
        self._save()

    def summary(self, mode: str) -> Dict[str, Any]:
        key = str(mode or "normal").lower()
        entries = list(self.data.get(key) or [])
        seconds = [float(item.get("seconds") or 0.0) for item in entries if float(item.get("seconds") or 0.0) > 0]
        if not seconds:
            profile = scan_mode_profile(key)
            return {
                "samples": 0,
                "average_seconds": None,
                "median_seconds": None,
                "success_rate": None,
                "target_min_seconds": profile["target_min_seconds"],
                "target_max_seconds": profile["target_max_seconds"],
            }
        successes = sum(1 for item in entries if item.get("success"))
        return {
            "samples": len(entries),
            "average_seconds": round(sum(seconds) / len(seconds), 2),
            "median_seconds": round(statistics.median(seconds), 2),
            "success_rate": round(100.0 * successes / max(1, len(entries)), 1),
            "target_min_seconds": scan_mode_profile(key)["target_min_seconds"],
            "target_max_seconds": scan_mode_profile(key)["target_max_seconds"],
        }


def normalize_scan_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_scan_text(value)).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def script_fallback_order(text: str = "") -> List[str]:
    """Waehlt hoechstens ein passendes Zusatzmodell statt alle Modelle nacheinander."""
    value = str(text or "")
    if any("\u3040" <= ch <= "\u30ff" for ch in value):
        return ["japanese"]
    if any("\uac00" <= ch <= "\ud7af" for ch in value):
        return ["korean"]
    if any("\u4e00" <= ch <= "\u9fff" for ch in value):
        return ["chinese"]
    if any("\u0900" <= ch <= "\u097f" for ch in value):
        return ["devanagari"]
    return []


def accepted_image_extension(path: str) -> bool:
    return os.path.splitext(str(path or ""))[1].lower() in SUPPORTED_IMAGE_EXTENSIONS


def fusion_bonus(kind: str, exact: bool = False, artwork_similarity: Optional[float] = None, quality_score: float = 0.0) -> float:
    kind = str(kind or "Name")
    score = 0.0
    if exact and kind == "Set-Code":
        score += 520.0
    elif exact and kind == "Passcode":
        score += 460.0
    elif exact and kind == "Name":
        score += 360.0
    if artwork_similarity is not None:
        similarity = max(0.0, min(1.0, float(artwork_similarity)))
        score += max(-35.0, (similarity - 0.45) * 180.0)
    score += max(0.0, min(25.0, float(quality_score or 0.0) * 0.25))
    return score


def mode_timing_text(mode: str, real_summary: Optional[Dict[str, Any]] = None) -> str:
    profile = scan_mode_profile(mode)
    base = f"Ziel: {profile['target_min_seconds']:.0f}–{profile['target_max_seconds']:.0f} s • Abbruchgrenze: {profile['hard_timeout_seconds']:.0f} s"
    summary = real_summary or {}
    if summary.get("samples"):
        base += f" • dein Durchschnitt: {float(summary.get('average_seconds') or 0):.1f} s ({int(summary.get('samples') or 0)} Messungen)"
    return base


def scanner_ai_summary() -> str:
    """Menschlich lesbare Kurzbeschreibung des KI-Modellstapels."""
    return " → ".join(item["label"] for item in AI_MODEL_STACK_V102)


def scanner_text_color_profiles() -> List[str]:
    """Unterstützte Text-/Rarity-Farbprofile für OCR-Vorverarbeitung."""
    return list(TEXT_COLOR_PROFILES_V102)


def gallery_ai_runtime_hint(cards: int = 1) -> Dict[str, float]:
    """Schätzt die Galerie-Laufzeit für den gründlichen KI-Scan grob ab."""
    
    count = max(1, int(cards or 1))
    return {"min_seconds": 6.0 * count, "avg_seconds": 12.0 * count, "max_seconds": 22.0 * count}
