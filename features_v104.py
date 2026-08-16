# -*- coding: utf-8 -*-
"""Erweiterungen für Just InCard v11.2.3.

Programmierer / Administrator: leenation

Die Hilfen sind Kivy-unabhängig und können in Tests, Diagnose und UI verwendet
werden. Sie kapseln Sammlungsmetadaten, Varianten-/Duplikatprüfung,
Scannerstatistik, Decktests, Offline-Status, automatische Sicherungen und
Integritätsprüfungen.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

APP_DEVELOPER = "leenation"
APP_ADMIN = "leenation"
MAX_DECKS_V104 = 50
MAX_FAVORITE_DECKS_V104 = 5

CARD_CONDITIONS_V104 = (
    "Near Mint",
    "Excellent",
    "Good",
    "Played",
    "Poor",
    "Beschädigt",
    "Versiegelt",
)

EDITION_OPTIONS_V104 = (
    "Unbekannt",
    "1. Auflage",
    "Unlimitiert",
    "Limited Edition",
)

DEFAULT_PRIVACY_V104 = {
    "local_ai_enabled": True,
    "cloud_ai_enabled": False,
    "allow_image_upload": False,
    "send_cropped_artwork_only": True,
    "delete_scan_images_after_processing": False,
    "local_learning_enabled": True,
    "include_images_in_diagnostics": False,
}


def normalized_collection_metadata(raw: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    raw = dict(raw or {})
    condition = str(raw.get("condition") or "Near Mint")
    if condition not in CARD_CONDITIONS_V104:
        condition = "Near Mint"
    edition = str(raw.get("edition") or "Unbekannt")
    if edition not in EDITION_OPTIONS_V104:
        edition = "Unbekannt"
    return {
        "condition": condition,
        "language": str(raw.get("language") or "Deutsch"),
        "edition": edition,
        "storage_location": str(raw.get("storage_location") or ""),
        "note": str(raw.get("note") or ""),
        "purchase_date": str(raw.get("purchase_date") or ""),
        "purchase_price": str(raw.get("purchase_price") or ""),
        "last_updated": float(raw.get("last_updated") or time.time()),
    }


def artwork_identity(card: Mapping[str, Any]) -> str:
    image = dict(card.get("_artwork_image") or {})
    image_id = image.get("id") or image.get("image_id") or card.get("artwork_id") or card.get("_variant_key")
    if image_id:
        return str(image_id)
    for key in ("image_url", "image_url_small", "image_url_cropped"):
        value = image.get(key) or card.get(key)
        if value:
            return hashlib.sha1(str(value).encode("utf-8", "ignore")).hexdigest()[:16]
    return "artwork-unknown"


def card_variant_identity(card: Mapping[str, Any], metadata: Optional[Mapping[str, Any]] = None) -> str:
    metadata = normalized_collection_metadata(metadata)
    sets = list(card.get("card_sets") or [])
    selected = dict(card.get("_collection_set") or (sets[0] if sets else {}) or {})
    parts = [
        str(card.get("id") or card.get("passcode") or card.get("name") or "unknown"),
        artwork_identity(card),
        str(selected.get("set_code") or card.get("set_code") or "set-unknown"),
        str(selected.get("set_rarity") or card.get("rarity") or "rarity-unknown"),
        metadata["language"],
        metadata["edition"],
        metadata["condition"],
    ]
    return "|".join(part.strip().casefold() for part in parts)


def find_duplicate_variant_groups(collection: Mapping[str, Any]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for key, entry in (collection or {}).items():
        card = dict(entry.get("card") or {})
        metadata = normalized_collection_metadata(entry.get("metadata") or {})
        base = "|".join([
            str(card.get("id") or card.get("passcode") or card.get("name") or "unknown").casefold(),
            artwork_identity(card),
            str((card.get("_collection_set") or {}).get("set_code") or card.get("set_code") or "set-unknown").casefold(),
        ])
        groups.setdefault(base, []).append((str(key), dict(entry)))
    result = []
    for identity, entries in groups.items():
        total = sum(max(0, int(item.get("count") or 0)) for _key, item in entries)
        if total > 1 or len(entries) > 1:
            result.append({"identity": identity, "entries": entries, "total": total})
    result.sort(key=lambda group: (-int(group["total"]), group["identity"]))
    return result


def confidence_breakdown(scan_item: Mapping[str, Any]) -> Dict[str, int]:
    """Erzeugt nachvollziehbare Einzelwerte aus vorhandenen Scannersignalen."""
    raw_conf = max(0, min(100, int(scan_item.get("confidence") or 0)))
    kind = str(scan_item.get("kind") or "").casefold()
    reason = str(scan_item.get("confidence_reason") or "").casefold()
    result = {
        "Set-Code": 0,
        "Passcode": 0,
        "Name": 0,
        "Effekt": 0,
        "Artwork": 0,
        "Bildqualität": max(0, min(100, int((scan_item.get("quality") or {}).get("score") or 0))),
    }
    if "set" in kind or "set-code" in reason:
        result["Set-Code"] = raw_conf
    if "passcode" in kind or "karten-id" in reason:
        result["Passcode"] = raw_conf
    if "name" in kind or "kartenname" in reason:
        result["Name"] = raw_conf
    if "effect" in kind or "effekt" in reason:
        result["Effekt"] = max(result["Effekt"], raw_conf)
    for key, label in (("effect_similarity", "Effekt"), ("artwork_similarity", "Artwork"), ("name_similarity", "Name")):
        try:
            value = float(scan_item.get(key) or 0.0)
            if value <= 1.0:
                value *= 100.0
            result[label] = max(result[label], max(0, min(100, int(round(value)))))
        except Exception:
            pass
    if scan_item.get("set_code_exact"):
        result["Set-Code"] = 100
    if scan_item.get("passcode_exact"):
        result["Passcode"] = 100
    return result


def confidence_breakdown_text(scan_item: Mapping[str, Any]) -> str:
    parts = confidence_breakdown(scan_item)
    return " • ".join(f"{name} {value}%" for name, value in parts.items() if value > 0)


def scanner_learning_statistics(history: Sequence[Mapping[str, Any]], timing_data: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None) -> Dict[str, Any]:
    history = list(history or [])
    safe = corrected = manual = failed = 0
    reasons: Dict[str, int] = {}
    for entry in history:
        status = str(entry.get("status") or entry.get("result") or "").casefold()
        confidence = int(entry.get("confidence") or 0)
        if "fail" in status or "fehler" in status or not entry.get("card") and confidence <= 0:
            failed += 1
        elif "manual" in status or "manuell" in status:
            manual += 1
        elif "correct" in status or "korrig" in status:
            corrected += 1
        elif confidence >= 85 or "success" in status or "erkannt" in status:
            safe += 1
        reason = str(entry.get("failure_reason") or entry.get("error") or "").strip()
        if reason:
            key = reason[:80]
            reasons[key] = reasons.get(key, 0) + 1
    durations: List[float] = []
    for entries in (timing_data or {}).values():
        for item in entries or []:
            try:
                value = float(item.get("seconds") or 0.0)
                if value > 0:
                    durations.append(value)
            except Exception:
                pass
    total = max(1, safe + corrected + manual + failed)
    return {
        "samples": len(history),
        "safe": safe,
        "corrected": corrected,
        "manual": manual,
        "failed": failed,
        "safe_rate": round(100.0 * safe / total, 1),
        "failed_rate": round(100.0 * failed / total, 1),
        "average_seconds": round(sum(durations) / len(durations), 2) if durations else None,
        "top_reasons": sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[:6],
    }


def deck_expanded_cards(deck: Mapping[str, Any]) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for entry in (deck or {}).get("cards", []):
        card = dict(entry.get("card") or {})
        zone = str(entry.get("zone") or "main")
        if zone != "main":
            continue
        for _ in range(max(0, int(entry.get("count") or 0))):
            cards.append(card)
    return cards


def card_role(card: Mapping[str, Any]) -> str:
    text = (str(card.get("name") or "") + " " + str(card.get("desc") or card.get("effect") or "")).casefold()
    if any(token in text for token in ("add 1", "füge deiner hand", "search", "suche", "deck deiner hand")):
        return "starter"
    if any(token in text for token in ("special summon", "spezialbeschw", "beschwöre diese karte")):
        return "extender"
    if any(token in text for token in ("negate", "annulliere", "verbanne", "zerstöre")):
        return "interaction"
    if any(token in text for token in ("cannot", "kann nicht", "only", "nur einmal")):
        return "restriction"
    return "other"


def simulate_deck_hands(deck: Mapping[str, Any], samples: int = 100, hand_size: int = 5, seed: Optional[int] = None) -> Dict[str, Any]:
    cards = deck_expanded_cards(deck)
    samples = max(10, min(5000, int(samples or 100)))
    if len(cards) < hand_size:
        return {"samples": 0, "error": "Main Deck enthält zu wenige Karten."}
    rng = random.Random(seed if seed is not None else 1040)
    starter = interaction = dead_two_plus = 0
    examples = []
    for index in range(samples):
        hand = rng.sample(cards, hand_size)
        roles = [card_role(card) for card in hand]
        starter += int("starter" in roles)
        interaction += int("interaction" in roles)
        dead = sum(1 for role in roles if role in {"restriction", "other"})
        dead_two_plus += int(dead >= 2)
        if index < 5:
            examples.append([str(card.get("name") or "Unbekannt") for card in hand])
    return {
        "samples": samples,
        "starter_probability": round(100.0 * starter / samples, 1),
        "interaction_probability": round(100.0 * interaction / samples, 1),
        "dead_two_plus_probability": round(100.0 * dead_two_plus / samples, 1),
        "example_hands": examples,
    }


def explain_deck_synergy(deck: Mapping[str, Any]) -> Dict[str, Any]:
    cards = deck_expanded_cards(deck)
    roles: Dict[str, List[str]] = {"starter": [], "extender": [], "interaction": [], "restriction": [], "other": []}
    archetypes: Dict[str, int] = {}
    for card in cards:
        roles[card_role(card)].append(str(card.get("name") or "Unbekannt"))
        archetype = str(card.get("archetype") or "").strip()
        if archetype:
            archetypes[archetype] = archetypes.get(archetype, 0) + 1
    main_archetypes = sorted(archetypes.items(), key=lambda item: (-item[1], item[0]))[:4]
    return {
        "roles": roles,
        "archetypes": main_archetypes,
        "summary": (
            f"{len(roles['starter'])} Starter, {len(roles['extender'])} Extender, "
            f"{len(roles['interaction'])} Interaktionen und {len(roles['restriction'])} mögliche Einschränkungen."
        ),
    }


def offline_status(database_dir: str, artwork_index_file: str, network_available: Optional[bool] = None) -> Dict[str, Any]:
    database_path = Path(database_dir or "")
    db_files = [path for path in database_path.glob("**/*") if path.is_file()] if database_path.exists() else []
    artwork_ready = bool(artwork_index_file and os.path.exists(artwork_index_file) and os.path.getsize(artwork_index_file) > 2)
    return {
        "database_ready": bool(db_files),
        "database_files": len(db_files),
        "artwork_index_ready": artwork_ready,
        "ocr_models_ready": True,
        "network_available": network_available,
    }


class AutomaticBackupManagerV104:
    def __init__(self, backup_dir: str, keep: int = 5, min_interval_seconds: int = 86400):
        self.backup_dir = Path(backup_dir)
        self.keep = max(2, int(keep or 5))
        self.min_interval_seconds = max(300, int(min_interval_seconds or 86400))
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def list_backups(self) -> List[Path]:
        return sorted(self.backup_dir.glob("JustInCard_AutoBackup_*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)

    def due(self) -> bool:
        backups = self.list_backups()
        return not backups or (time.time() - backups[0].stat().st_mtime) >= self.min_interval_seconds

    def create(self, files: Iterable[str], version: str, developer: str = APP_DEVELOPER) -> Optional[str]:
        if not self.due():
            return None
        target = self.backup_dir / time.strftime("JustInCard_AutoBackup_%Y%m%d_%H%M%S.zip")
        manifest = {"version": version, "developer": developer, "created_at": time.time(), "files": []}
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for raw in files:
                path = Path(raw)
                if path.is_file() and path.stat().st_size > 0:
                    archive.write(path, arcname=path.name)
                    manifest["files"].append(path.name)
            archive.writestr("backup_manifest_v104.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for old in self.list_backups()[self.keep:]:
            try:
                old.unlink()
            except Exception:
                pass
        return str(target)


def redact_diagnostics(payload: Any) -> Any:
    blocked = {"openai_api_key", "api_key", "token", "authorization", "password", "secret", "purchase_price", "note"}
    if isinstance(payload, dict):
        return {key: ("<redacted>" if str(key).casefold() in blocked else redact_diagnostics(value)) for key, value in payload.items()}
    if isinstance(payload, list):
        return [redact_diagnostics(value) for value in payload]
    return payload


def create_integrity_manifest(root_dir: str, output_path: str, include_exts: Sequence[str] = (".py", ".json", ".png")) -> Dict[str, Any]:
    root = Path(root_dir).resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in set(include_exts):
            continue
        if any(part in {".git", ".github", ".buildozer", "bin", "dist", "logs", "tests", "docs", "ci", "scripts", "__pycache__"} for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in {"security_integrity_manifest.json", "security_build_metadata.json", "preflight_check.py", "apk_validate.py", "prepare_release_hardening.py"}:
            continue
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {"developer": APP_DEVELOPER, "generated_at": time.time(), "files": files}
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
