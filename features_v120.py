# -*- coding: utf-8 -*-
"""High-value, dependency-free v12 domain features for Just InCard.

The functions are intentionally independent from Kivy and Android so deck
exchange, banlist checks, price history and live-scan stability can be tested on
every commit and reused by the UI without blocking the render thread.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import statistics
import time
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


YDK_SECTION_MARKERS = {"#main": "main", "#extra": "extra", "!side": "side"}
FORMAT_LIMITS = {
    "TCG": {"main": (40, 60), "extra": (0, 15), "side": (0, 15)},
    "OCG": {"main": (40, 60), "extra": (0, 15), "side": (0, 15)},
    "GOAT": {"main": (40, 60), "extra": (0, 15), "side": (0, 15)},
    "SPEED": {"main": (20, 30), "extra": (0, 6), "side": (0, 6)},
}


def _card_id(card: Mapping[str, Any]) -> str:
    value = card.get("id") or card.get("passcode") or card.get("card_id") or ""
    digits = re.sub(r"\D", "", str(value))
    return digits[-8:].zfill(8) if digits else ""


def _zone_for(card: Mapping[str, Any], explicit: str = "") -> str:
    zone = str(explicit or card.get("zone") or "").strip().lower()
    if zone in {"main", "extra", "side"}:
        return zone
    card_type = str(card.get("type") or "").lower()
    if any(value in card_type for value in ("fusion", "synchro", "xyz", "link")):
        return "extra"
    return "main"


def normalized_deck_sections(deck: Mapping[str, Any]) -> Dict[str, List[Mapping[str, Any]]]:
    sections: Dict[str, List[Mapping[str, Any]]] = {"main": [], "extra": [], "side": []}
    if not isinstance(deck, Mapping):
        return sections
    if any(isinstance(deck.get(key), list) for key in sections):
        for zone in sections:
            for item in deck.get(zone) or []:
                if not isinstance(item, Mapping):
                    continue
                count = max(1, min(3, int(item.get("count", 1) or 1)))
                sections[zone].extend([item] * count)
        return sections
    for item in deck.get("cards") or []:
        if not isinstance(item, Mapping):
            continue
        card = item.get("card") if isinstance(item.get("card"), Mapping) else item
        zone = _zone_for(card, str(item.get("zone") or ""))
        count = max(1, min(3, int(item.get("count", 1) or 1)))
        sections[zone].extend([card] * count)
    return sections


def export_ydk(deck: Mapping[str, Any]) -> str:
    """Export a deck to the EDOPro/YGOPro ``.ydk`` text format."""
    sections = normalized_deck_sections(deck)
    lines = ["#created by Just InCard v12", "#main"]
    lines.extend(_card_id(card) for card in sections["main"] if _card_id(card))
    lines.append("#extra")
    lines.extend(_card_id(card) for card in sections["extra"] if _card_id(card))
    lines.append("!side")
    lines.extend(_card_id(card) for card in sections["side"] if _card_id(card))
    return "\n".join(lines) + "\n"


def parse_ydk(text: str, card_lookup: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Dict[str, Any]:
    """Parse a `.ydk` safely; unknown passcodes remain usable placeholders."""
    section = "main"
    sections: Dict[str, List[Mapping[str, Any]]] = {"main": [], "extra": [], "side": []}
    warnings: List[str] = []
    lookup = card_lookup or {}
    for line_no, raw in enumerate(str(text or "").replace("\r", "").split("\n"), 1):
        line = raw.strip()
        if not line or (line.startswith("#") and line not in YDK_SECTION_MARKERS):
            continue
        if line in YDK_SECTION_MARKERS:
            section = YDK_SECTION_MARKERS[line]
            continue
        if not re.fullmatch(r"\d{1,10}", line):
            warnings.append(f"Zeile {line_no}: ungültiger Passcode übersprungen")
            continue
        card_id = line[-8:].zfill(8)
        card = dict(lookup.get(card_id) or lookup.get(str(int(card_id))) or {})
        card.setdefault("id", int(card_id))
        card.setdefault("name", f"Passcode {card_id}")
        card.setdefault("_ydk_unresolved", not bool(lookup.get(card_id) or lookup.get(str(int(card_id)))))
        sections[section].append(card)
    cards: List[Dict[str, Any]] = []
    for zone, values in sections.items():
        grouped: Dict[str, Dict[str, Any]] = {}
        for card in values:
            key = _card_id(card) or str(card.get("name") or "")
            if key not in grouped:
                grouped[key] = {"card": dict(card), "count": 0, "zone": zone}
            grouped[key]["count"] += 1
        cards.extend(grouped.values())
    return {"name": "Importiertes YDK-Deck", "cards": cards, "warnings": warnings, "sections": sections}


def _ban_limit(card: Mapping[str, Any], format_name: str, overrides: Mapping[str, int]) -> int:
    card_id = _card_id(card)
    if card_id in overrides:
        return max(0, min(3, int(overrides[card_id])))
    info = card.get("banlist_info") if isinstance(card.get("banlist_info"), Mapping) else {}
    key = {"TCG": "ban_tcg", "OCG": "ban_ocg", "GOAT": "ban_goat"}.get(format_name.upper(), "ban_tcg")
    value = str(info.get(key) or "").lower()
    if "forbidden" in value or "verboten" in value:
        return 0
    if "semi" in value:
        return 2
    if "limited" in value or "limitiert" in value:
        return 1
    return 3


def validate_deck(
    deck: Mapping[str, Any],
    format_name: str = "TCG",
    banlist_overrides: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """Validate size, copy limits and embedded/updatable banlist information."""
    fmt = str(format_name or "TCG").upper()
    limits = FORMAT_LIMITS.get(fmt, FORMAT_LIMITS["TCG"])
    sections = normalized_deck_sections(deck)
    errors: List[str] = []
    warnings: List[str] = []
    counts = Counter(_card_id(card) or str(card.get("name") or "?") for values in sections.values() for card in values)
    cards_by_id = {
        _card_id(card) or str(card.get("name") or "?"): card
        for values in sections.values() for card in values
    }
    overrides = {str(key).zfill(8): int(value) for key, value in (banlist_overrides or {}).items()}
    for zone, (minimum, maximum) in limits.items():
        total = len(sections[zone])
        if total < minimum:
            errors.append(f"{zone.title()} Deck: {total}/{minimum} Karten")
        if total > maximum:
            errors.append(f"{zone.title()} Deck: {total}/{maximum} Karten")
    for card_id, count in sorted(counts.items()):
        if count > 3:
            errors.append(f"{cards_by_id[card_id].get('name', card_id)}: {count}/3 Exemplare")
        limit = _ban_limit(cards_by_id[card_id], fmt, overrides)
        if count > limit:
            errors.append(f"{cards_by_id[card_id].get('name', card_id)}: {count}/{limit} laut {fmt}-Liste")
        if not _card_id(cards_by_id[card_id]):
            warnings.append(f"Passcode fehlt: {cards_by_id[card_id].get('name', 'Unbekannt')}")
    return {
        "valid": not errors,
        "format": fmt,
        "counts": {zone: len(values) for zone, values in sections.items()},
        "errors": errors,
        "warnings": warnings,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def compact_deck_share_payload(deck: Mapping[str, Any], format_name: str = "TCG") -> str:
    """Produce a deterministic compact payload suitable for text share or QR."""
    payload = {
        "v": 1,
        "n": str(deck.get("name") or "Just InCard Deck")[:80],
        "f": str(format_name or "TCG").upper(),
        "y": export_ydk(deck),
    }
    return "JIC12:" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_deck_share_payload(value: str) -> Dict[str, Any]:
    raw = str(value or "")
    if not raw.startswith("JIC12:"):
        raise ValueError("Kein Just-InCard-v12-Deckcode")
    payload = json.loads(raw[6:])
    if not isinstance(payload, dict) or int(payload.get("v", 0) or 0) != 1:
        raise ValueError("Nicht unterstützte Deckcode-Version")
    deck = parse_ydk(str(payload.get("y") or ""))
    deck["name"] = str(payload.get("n") or deck["name"])[:80]
    deck["format"] = str(payload.get("f") or "TCG").upper()
    return deck


def collection_market_summary(
    collection: Mapping[str, Mapping[str, Any]],
    flags: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    total_value = 0.0
    priced = 0
    copies = 0
    duplicates = 0
    flag_map = flags or {}
    wishlist = sum(
        1 for value in flag_map.values()
        if isinstance(value, Mapping) and value.get("wishlist")
    )
    trade = 0
    for key, item in (collection or {}).items():
        if not isinstance(item, Mapping):
            continue
        count = max(0, int(item.get("count", 0) or 0))
        card = item.get("card") if isinstance(item.get("card"), Mapping) else {}
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        if not metadata:
            metadata = card.get("_collection_meta") if isinstance(card.get("_collection_meta"), Mapping) else {}
        price = metadata.get("market_price")
        if price is None:
            prices = card.get("card_prices") if isinstance(card.get("card_prices"), list) else []
            price = (prices[0] or {}).get("cardmarket_price") if prices and isinstance(prices[0], Mapping) else None
        try:
            amount = max(0.0, float(str(price).replace(",", ".")))
        except (TypeError, ValueError):
            amount = 0.0
        copies += count
        duplicates += max(0, count - 1)
        if amount > 0:
            priced += count
            total_value += amount * count
        entry_flags = flag_map.get(str(key), {}) if isinstance(flag_map.get(str(key), {}), Mapping) else {}
        trade += count if entry_flags.get("trade") else 0
    return {
        "copies": copies,
        "duplicates": duplicates,
        "priced_copies": priced,
        "estimated_value": round(total_value, 2),
        "wishlist_items": wishlist,
        "trade_copies": trade,
    }


def price_trend(points: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    clean: List[Tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point.get("observed_at") or 0), float(point.get("price") or 0)))
        except (TypeError, ValueError, AttributeError):
            continue
    clean = [(ts, price) for ts, price in clean if ts > 0 and price >= 0]
    clean.sort()
    if not clean:
        return {"direction": "unknown", "change": 0.0, "change_percent": 0.0, "latest": None}
    first = clean[0][1]
    latest = clean[-1][1]
    change = latest - first
    percent = (change / first * 100.0) if first > 0 else 0.0
    direction = "stable" if abs(percent) < 1.0 else ("up" if change > 0 else "down")
    return {"direction": direction, "change": round(change, 2), "change_percent": round(percent, 1), "latest": latest}


@dataclass(frozen=True)
class FrameSignal:
    brightness: float
    contrast: float
    sharpness: float
    motion: float
    card_coverage: float
    text_fingerprint: str = ""


def scan_guidance(signal: FrameSignal) -> Tuple[str, str]:
    """Return localized guidance plus semantic state for a native/Kivy overlay."""
    if signal.brightness < 0.20:
        return "Zu dunkel – Licht einschalten", "dark"
    if signal.brightness > 0.92:
        return "Blendung vermeiden", "glare"
    if signal.motion > 0.18:
        return "Ruhig halten", "motion"
    if signal.sharpness < 0.28:
        return "Fokus abwarten", "blur"
    if signal.card_coverage < 0.46:
        return "Karte näher heranführen", "far"
    if signal.card_coverage > 0.94:
        return "Etwas weiter weg", "near"
    if signal.contrast < 0.16:
        return "Kontrast erhöhen", "contrast"
    return "Karte erkannt – ruhig halten", "ready"


class ScanStabilityGate:
    """Low-allocation stability gate for automatic series capture.

    A scan becomes stable only after repeated, sufficiently similar OCR evidence.
    The same fingerprint is then suppressed for a configurable duplicate window.
    """

    def __init__(self, required_frames: int = 3, duplicate_seconds: float = 3.5, history_size: int = 6):
        self.required_frames = max(2, int(required_frames or 3))
        self.duplicate_seconds = max(0.5, float(duplicate_seconds or 3.5))
        self.history: Deque[FrameSignal] = deque(maxlen=max(self.required_frames, int(history_size or 6)))
        self.last_emitted: Dict[str, float] = {}

    @staticmethod
    def fingerprint(text: str) -> str:
        normalized = re.sub(r"[^A-Z0-9]", "", str(text or "").upper())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""

    def reset(self) -> None:
        self.history.clear()

    def push(self, signal: FrameSignal, now: Optional[float] = None) -> Dict[str, Any]:
        timestamp = float(time.monotonic() if now is None else now)
        self.history.append(signal)
        guidance, state = scan_guidance(signal)
        recent = list(self.history)[-self.required_frames :]
        stable_quality = len(recent) >= self.required_frames and all(scan_guidance(item)[1] == "ready" for item in recent)
        fingerprints = [item.text_fingerprint for item in recent if item.text_fingerprint]
        repeated = bool(fingerprints) and len(fingerprints) >= self.required_frames and len(set(fingerprints)) == 1
        stable_motion = len(recent) >= self.required_frames and statistics.fmean(item.motion for item in recent) <= 0.10
        fingerprint = fingerprints[-1] if fingerprints else ""
        duplicate = bool(fingerprint and timestamp - self.last_emitted.get(fingerprint, -1e9) < self.duplicate_seconds)
        ready = stable_quality and repeated and stable_motion and not duplicate
        if ready:
            self.last_emitted[fingerprint] = timestamp
            guidance, state = "Stabil erkannt", "stable"
        elif duplicate:
            guidance, state = "Bereits in dieser Serie erkannt", "duplicate"
        # Keep the duplicate map bounded for long-running sessions.
        cutoff = timestamp - max(60.0, self.duplicate_seconds * 4.0)
        if len(self.last_emitted) > 128:
            self.last_emitted = {key: value for key, value in self.last_emitted.items() if value >= cutoff}
        return {"ready": ready, "duplicate": duplicate, "state": state, "guidance": guidance, "fingerprint": fingerprint}


def benchmark_scan_records(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Aggregate a scanner corpus manifest without requiring images on CI."""
    total = correct = false_positive = 0
    latencies: List[float] = []
    by_device: Dict[str, Counter] = {}
    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        total += 1
        is_correct = bool(record.get("correct"))
        correct += 1 if is_correct else 0
        false_positive += 1 if record.get("false_positive") else 0
        try:
            latencies.append(max(0.0, float(record.get("latency_ms"))))
        except (TypeError, ValueError):
            pass
        device = str(record.get("device_class") or "unknown")
        by_device.setdefault(device, Counter())["total"] += 1
        by_device[device]["correct"] += 1 if is_correct else 0
    return {
        "total": total,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "false_positive_rate": round(false_positive / total, 4) if total else 0.0,
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else None,
        "latency_p95_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 1) if latencies else None,
        "devices": {key: dict(value) for key, value in by_device.items()},
    }
