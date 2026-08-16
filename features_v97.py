# -*- coding: utf-8 -*-
"""Stabile, Kivy-unabhängige Funktionen für Just InCard v10.0.

Dieses Modul ergänzt die v9.6-Basis um:
- automatisches Fortsetzen der letzten App-Sitzung,
- sichere Backup-Prüfung und verzögerte Wiederherstellung,
- Cache-Auswertung und gezielte Cache-Bereinigung,
- normalisierte Barrierefreiheits-/Geräteeinstellungen.

Die Funktionen enthalten bewusst keine Kivy-Imports und werden im GitHub-
Workflow vor dem Android-Build separat getestet.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app_version import APP_VERSION, BACKUP_SCHEMA_VERSION, SESSION_SCHEMA_VERSION


def _atomic_write_json(path: str, payload: Any) -> str:
    target = os.path.abspath(str(path or ""))
    if not target:
        raise ValueError("Ungültiger Zielpfad")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp = target + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except Exception:
            pass
    os.replace(temp, target)
    return target


def _safe_read_json(path: str, fallback: Any) -> Any:
    try:
        if not path or not os.path.isfile(path) or os.path.getsize(path) <= 0:
            return fallback
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return fallback


def _safe_scalar(value: Any, max_length: int = 600) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:max_length]
    return str(value)[:max_length]


def sanitize_session_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Begrenzt Sitzungsdaten auf kleine, unkritische UI-Werte."""
    payload = payload if isinstance(payload, dict) else {}
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    allowed_filters = {
        "name", "card_id", "set", "language_name", "atk", "def", "level",
        "race", "attribute_name", "group",
    }
    clean_filters = {key: _safe_scalar(filters.get(key, ""), 180) for key in allowed_filters}
    return {
        "schema": SESSION_SCHEMA_VERSION,
        "saved_at": float(payload.get("saved_at") or time.time()),
        "section": str(payload.get("section") or "search")[:40],
        "filters": clean_filters,
        "page": max(0, min(100000, int(payload.get("page") or 0))),
        "selected_card_id": str(payload.get("selected_card_id") or "")[:120],
        "main_scroll_y": max(0.0, min(1.0, float(payload.get("main_scroll_y") or 1.0))),
        "results_scroll_y": max(0.0, min(1.0, float(payload.get("results_scroll_y") or 1.0))),
        "advanced_filters": bool(payload.get("advanced_filters", False)),
        "active_deck": max(-1, min(9, int(payload.get("active_deck", -1) or -1))),
    }


class SessionStateStoreV97:
    """Atomarer Speicher für den letzten sichtbaren App-Zustand."""

    def __init__(self, path: str, max_age_days: int = 30):
        self.path = os.path.abspath(path)
        self.max_age_seconds = max(1, int(max_age_days)) * 24 * 60 * 60

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        clean = sanitize_session_payload({**(payload or {}), "saved_at": time.time()})
        _atomic_write_json(self.path, clean)
        return clean

    def load(self) -> Dict[str, Any]:
        data = _safe_read_json(self.path, {})
        if not isinstance(data, dict) or not data:
            return {}
        clean = sanitize_session_payload(data)
        if time.time() - float(clean.get("saved_at") or 0) > self.max_age_seconds:
            return {}
        return clean

    def clear(self) -> None:
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


ALLOWED_BACKUP_BASENAMES = {
    "yugioh_sammlung.json",
    "settings.json",
    "decks.json",
    "custom_cards.json",
    "scan_history.json",
    "scan_last_import.json",
    "scan_learning_v93.json",
    "undo_history_v93.json",
    "incremental_sync_v93.json",
    "just_incard_v91.sqlite3",
    "just_incard_crash.log",
    "session_state_v97.json",
}
ALLOWED_DATABASE_EXTENSIONS = {".json", ".sqlite", ".sqlite3", ".db", ".cdb"}


def _is_safe_archive_name(name: str) -> bool:
    name = str(name or "").replace("\\", "/")
    if not name or name.startswith("/") or "\x00" in name:
        return False
    parts = [part for part in name.split("/") if part not in {"", "."}]
    return bool(parts) and ".." not in parts


def _restore_target_for(name: str, user_data_dir: str) -> Optional[str]:
    normalized = str(name or "").replace("\\", "/")
    base = os.path.basename(normalized)
    if base == "backup_manifest.json":
        return None
    if normalized.startswith("card_database/") and Path(base).suffix.lower() in ALLOWED_DATABASE_EXTENSIONS:
        return os.path.join(user_data_dir, "card_database", base)
    if base in ALLOWED_BACKUP_BASENAMES:
        return os.path.join(user_data_dir, base)
    return None


class BackupInspectorV97:
    """Prüft Backups ohne unkontrolliertes Entpacken."""

    @staticmethod
    def inspect(path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "path": os.path.abspath(str(path or "")),
            "valid": False,
            "manifest": {},
            "restorable": [],
            "ignored": [],
            "warnings": [],
            "total_uncompressed": 0,
        }
        if not os.path.isfile(result["path"]):
            result["warnings"].append("Backup-Datei wurde nicht gefunden.")
            return result
        try:
            with zipfile.ZipFile(result["path"], "r") as archive:
                infos = archive.infolist()
                if len(infos) > 5000:
                    result["warnings"].append("Backup enthält ungewöhnlich viele Dateien.")
                    return result
                total = sum(max(0, int(info.file_size or 0)) for info in infos)
                result["total_uncompressed"] = total
                if total > 4 * 1024 * 1024 * 1024:
                    result["warnings"].append("Backup ist entpackt größer als 4 GB.")
                    return result
                for info in infos:
                    name = info.filename
                    if not _is_safe_archive_name(name):
                        result["warnings"].append(f"Unsicherer Archivpfad: {name}")
                        continue
                    if os.path.basename(name) == "backup_manifest.json":
                        try:
                            manifest = json.loads(archive.read(info).decode("utf-8"))
                            result["manifest"] = manifest if isinstance(manifest, dict) else {}
                        except Exception:
                            result["warnings"].append("Manifest ist beschädigt.")
                        continue
                    target = _restore_target_for(name, "USER_DATA")
                    if target:
                        result["restorable"].append(name)
                    elif not name.endswith("/"):
                        result["ignored"].append(name)
                if not result["restorable"]:
                    result["warnings"].append("Keine unterstützten Just-InCard-Datendateien gefunden.")
                result["valid"] = bool(result["restorable"]) and not any(
                    text.startswith("Unsicherer Archivpfad") for text in result["warnings"]
                )
        except zipfile.BadZipFile:
            result["warnings"].append("Datei ist kein gültiges ZIP-Backup.")
        except Exception as exc:
            result["warnings"].append(str(exc))
        return result


def schedule_backup_restore(zip_path: str, marker_path: str) -> Dict[str, Any]:
    report = BackupInspectorV97.inspect(zip_path)
    if not report.get("valid"):
        raise ValueError("Backup kann nicht wiederhergestellt werden: " + "; ".join(report.get("warnings") or []))
    marker = {
        "schema": BACKUP_SCHEMA_VERSION,
        "created_at": time.time(),
        "app_version": APP_VERSION,
        "zip_path": os.path.abspath(zip_path),
        "restorable": list(report.get("restorable") or []),
    }
    _atomic_write_json(marker_path, marker)
    return marker


def apply_pending_restore(user_data_dir: str, marker_path: str) -> Dict[str, Any]:
    """Wendet ein geplantes Backup vor dem Öffnen der SQLite-Datenbank an."""
    marker = _safe_read_json(marker_path, {})
    if not isinstance(marker, dict) or not marker.get("zip_path"):
        return {"applied": False, "files": [], "errors": []}
    zip_path = os.path.abspath(str(marker.get("zip_path") or ""))
    report = BackupInspectorV97.inspect(zip_path)
    if not report.get("valid"):
        return {"applied": False, "files": [], "errors": report.get("warnings") or ["Backup ungültig"]}

    os.makedirs(user_data_dir, exist_ok=True)
    staging = tempfile.mkdtemp(prefix="justincard_restore_", dir=user_data_dir)
    applied: List[str] = []
    errors: List[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for name in report.get("restorable") or []:
                try:
                    target = _restore_target_for(name, user_data_dir)
                    if not target:
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    staged = os.path.join(staging, os.path.basename(target) + ".restore")
                    with archive.open(name, "r") as source, open(staged, "wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                        output.flush()
                        try:
                            os.fsync(output.fileno())
                        except Exception:
                            pass
                    if os.path.getsize(staged) <= 0:
                        raise ValueError("Datei ist leer")
                    os.replace(staged, target)
                    applied.append(os.path.relpath(target, user_data_dir))
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
        if not errors:
            try:
                os.remove(marker_path)
            except Exception:
                pass
        return {"applied": bool(applied), "files": applied, "errors": errors}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def directory_size(path: str) -> Tuple[int, int]:
    total = 0
    files = 0
    if not path or not os.path.isdir(path):
        return 0, 0
    for root, _dirs, names in os.walk(path):
        for name in names:
            file_path = os.path.join(root, name)
            try:
                total += os.path.getsize(file_path)
                files += 1
            except Exception:
                continue
    return total, files


class CacheManagerV97:
    """Verwaltet ausschließlich neu erzeugbare Bild-/Scanner-Caches."""

    def __init__(self, paths: Iterable[str]):
        self.paths = [os.path.abspath(path) for path in paths if path]

    def report(self) -> Dict[str, Any]:
        entries = []
        total = 0
        files = 0
        for path in self.paths:
            size, count = directory_size(path)
            entries.append({"path": path, "bytes": size, "files": count})
            total += size
            files += count
        return {"bytes": total, "files": files, "entries": entries}

    def clear(self) -> Dict[str, Any]:
        removed_files = 0
        removed_bytes = 0
        errors: List[str] = []
        for path in self.paths:
            if not os.path.isdir(path):
                continue
            for root, dirs, names in os.walk(path, topdown=False):
                for name in names:
                    file_path = os.path.join(root, name)
                    try:
                        removed_bytes += os.path.getsize(file_path)
                        os.remove(file_path)
                        removed_files += 1
                    except Exception as exc:
                        errors.append(f"{file_path}: {exc}")
                for directory in dirs:
                    try:
                        os.rmdir(os.path.join(root, directory))
                    except Exception:
                        pass
        return {"removed_bytes": removed_bytes, "removed_files": removed_files, "errors": errors}


def normalize_accessibility_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    return {
        "reduce_motion": bool(data.get("reduce_motion", False)),
        "large_touch_targets": bool(data.get("large_touch_targets", False)),
        "high_contrast_focus": bool(data.get("high_contrast_focus", True)),
        "wifi_only_images": bool(data.get("wifi_only_images", False)),
        "cache_limit_mb": max(100, min(2000, int(data.get("cache_limit_mb") or 500))),
    }
