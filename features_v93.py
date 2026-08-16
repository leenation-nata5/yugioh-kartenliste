# -*- coding: utf-8 -*-
"""Erweiterte, Kivy-unabhängige Funktionen für Just InCard v10.0.

Das Modul bündelt persistente Scan-Lernregeln, ein begrenztes Rückgängig-System,
Leistungsprofile, inkrementelle Sync-Metadaten, Sammlungsstatistiken und
Diagnosehilfen. Es enthält bewusst keine Kivy-Widgets und kann daher auch in
GitHub-Preflight-Tests importiert werden.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import ssl
import importlib.util
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app_version import APP_VERSION


def _atomic_write_json(path: str, payload: Any) -> str:
    target = os.path.abspath(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except Exception:
            pass
    os.replace(tmp, target)
    return target


def _safe_read_json(path: str, fallback: Any) -> Any:
    try:
        if not path or not os.path.exists(path) or os.path.getsize(path) <= 0:
            return fallback
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return fallback


def normalize_learning_key(value: Any) -> str:
    text = str(value or "").upper().strip()
    text = " ".join(text.split())
    return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", " "})


class ScanLearningStoreV93:
    """Lokaler, datensparsamer Lernspeicher für manuell bestätigte OCR-Korrekturen."""

    def __init__(self, path: str, max_entries: int = 500):
        self.path = os.path.abspath(path)
        self.max_entries = max(50, int(max_entries or 500))
        self._lock = threading.RLock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            data = _safe_read_json(self.path, {})
            self._data = data if isinstance(data, dict) else {}

    def save(self) -> None:
        with self._lock:
            items = sorted(
                self._data.items(),
                key=lambda item: float((item[1] or {}).get("updated_at") or 0),
                reverse=True,
            )[: self.max_entries]
            self._data = dict(items)
            _atomic_write_json(self.path, self._data)

    def remember(self, raw_value: str, kind: str, target_value: str, card_id: Any = "", language: str = "") -> bool:
        key = normalize_learning_key(raw_value)
        target = str(target_value or "").strip()
        if not key or not target:
            return False
        with self._lock:
            current = self._data.get(key, {})
            self._data[key] = {
                "raw": str(raw_value or ""),
                "kind": str(kind or "Name"),
                "target": target,
                "card_id": str(card_id or ""),
                "language": str(language or ""),
                "count": int(current.get("count") or 0) + 1,
                "updated_at": time.time(),
            }
            self.save()
        return True

    def lookup(self, raw_value: str, kind: str = "") -> Optional[Dict[str, Any]]:
        key = normalize_learning_key(raw_value)
        if not key:
            return None
        with self._lock:
            item = self._data.get(key)
            if not isinstance(item, dict):
                return None
            if kind and item.get("kind") and str(item.get("kind")) != str(kind):
                return None
            return dict(item)

    def expand_candidates(self, candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates or []:
            if not isinstance(candidate, dict):
                continue
            signature = (str(candidate.get("kind") or ""), normalize_learning_key(candidate.get("value")))
            if signature not in seen:
                seen.add(signature)
                result.append(dict(candidate))
            learned = self.lookup(candidate.get("value", ""), candidate.get("kind", ""))
            if learned:
                learned_candidate = {
                    "kind": learned.get("kind") or candidate.get("kind") or "Name",
                    "value": learned.get("target") or candidate.get("value") or "",
                    "priority": max(118, int(candidate.get("priority") or 0) + 20),
                    "source": "Lokale Scan-Lernregel",
                    "learned_card_id": learned.get("card_id") or "",
                    "learned_language": learned.get("language") or "",
                }
                learned_signature = (
                    learned_candidate["kind"],
                    normalize_learning_key(learned_candidate["value"]),
                )
                if learned_signature not in seen:
                    seen.add(learned_signature)
                    result.insert(0, learned_candidate)
        return result

    def clear(self) -> None:
        with self._lock:
            self._data = {}
            self.save()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            entries = list(self._data.values())
        return {
            "entries": len(entries),
            "uses": sum(int(item.get("count") or 0) for item in entries if isinstance(item, dict)),
            "latest": max((float(item.get("updated_at") or 0) for item in entries if isinstance(item, dict)), default=0),
        }


class UndoManagerV93:
    """Persistenter Undo-Stapel für reversible Sammlungs- und Deckaktionen."""

    def __init__(self, path: str, max_actions: int = 40):
        self.path = os.path.abspath(path)
        self.max_actions = max(10, int(max_actions or 40))
        self._lock = threading.RLock()
        self.actions: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        data = _safe_read_json(self.path, [])
        self.actions = data[: self.max_actions] if isinstance(data, list) else []

    def save(self) -> None:
        with self._lock:
            self.actions = self.actions[: self.max_actions]
            _atomic_write_json(self.path, self.actions)

    def push(self, action_type: str, title: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = {
            "id": f"undo_{int(time.time() * 1000)}",
            "type": str(action_type or "generic"),
            "title": str(title or "Aktion"),
            "payload": payload if isinstance(payload, dict) else {},
            "created_at": time.time(),
            "created_label": time.strftime("%d.%m.%Y %H:%M:%S"),
        }
        with self._lock:
            self.actions.insert(0, action)
            self.save()
        return action

    def peek(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self.actions[0]) if self.actions else None

    def pop(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            action = self.actions.pop(0) if self.actions else None
            self.save()
            return action

    def clear(self) -> None:
        with self._lock:
            self.actions = []
            self.save()


@dataclass(frozen=True)
class PerformanceModeV93:
    key: str
    title: str
    max_scan_side: int
    concurrent_preparation: int
    artwork_compare: bool
    animations: bool
    preview_cache_items: int


PERFORMANCE_MODES_V93: Dict[str, PerformanceModeV93] = {
    "eco": PerformanceModeV93("eco", "Energiesparend", 1280, 1, False, False, 60),
    "balanced": PerformanceModeV93("balanced", "Ausgewogen", 1800, 2, True, True, 120),
    "quality": PerformanceModeV93("quality", "Maximale Qualität", 2400, 3, True, True, 220),
}


def recommend_performance_mode(profile: Dict[str, Any], total_memory_mb: Optional[int] = None) -> str:
    device_class = str((profile or {}).get("device_class") or "phone")
    if total_memory_mb is not None and total_memory_mb < 3000:
        return "eco"
    if device_class in {"tablet", "large_tablet"}:
        return "quality" if total_memory_mb is None or total_memory_mb >= 5000 else "balanced"
    if device_class == "compact_phone":
        return "eco"
    return "balanced"


class IncrementalSyncStateV93:
    """Speichert Datenquellen-Versionen und entscheidet, ob ein Vollsync nötig ist."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.state = _safe_read_json(self.path, {})
        if not isinstance(self.state, dict):
            self.state = {}

    def get_source(self, source: str) -> Dict[str, Any]:
        item = self.state.get(str(source), {})
        return dict(item) if isinstance(item, dict) else {}

    def should_sync(self, source: str, remote_version: str = "", max_age_seconds: int = 86400) -> bool:
        item = self.get_source(source)
        if not item:
            return True
        if remote_version and str(item.get("version") or "") != str(remote_version):
            return True
        return time.time() - float(item.get("updated_at") or 0) >= max(60, int(max_age_seconds or 86400))

    def mark_synced(self, source: str, version: str = "", item_count: int = 0, details: Optional[Dict[str, Any]] = None) -> None:
        self.state[str(source)] = {
            "version": str(version or ""),
            "item_count": int(item_count or 0),
            "details": details or {},
            "updated_at": time.time(),
        }
        _atomic_write_json(self.path, self.state)


class CollectionAnalyticsV93:
    @staticmethod
    def summarize(collection: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        total = 0
        cards = 0
        artworks = set()
        sets = set()
        rarities: Dict[str, int] = {}
        without_set = 0
        without_image = 0
        duplicates = 0
        recent: List[Tuple[float, str, int]] = []
        for item in (collection or {}).values():
            if not isinstance(item, dict):
                continue
            count = max(0, int(item.get("count") or 0))
            card = item.get("card") if isinstance(item.get("card"), dict) else {}
            if count <= 0 or not card:
                continue
            total += count
            cards += 1
            if count > 1:
                duplicates += count - 1
            card_id = str(card.get("id") or card.get("name") or "")
            artwork = str(card.get("_variant_key") or card.get("_artwork_index") or card.get("_collection_image_url") or "0")
            artworks.add((card_id, artwork))
            set_code = str(card.get("_collection_set_code") or "").strip()
            set_name = str(card.get("_collection_set_name") or "").strip()
            if set_code or set_name:
                sets.add(set_code or set_name)
            else:
                without_set += count
            rarity = str(card.get("_collection_set_rarity") or "Unbekannt").strip() or "Unbekannt"
            rarities[rarity] = rarities.get(rarity, 0) + count
            images = card.get("card_images") or []
            has_image = bool(card.get("_collection_image_url")) or bool(images)
            if not has_image:
                without_image += count
            updated = float(item.get("updated_at") or card.get("_collection_updated_at") or 0)
            recent.append((updated, str(card.get("name") or "Unbekannte Karte"), count))
        top_rarities = sorted(rarities.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
        recent.sort(reverse=True)
        return {
            "total": total,
            "different": cards,
            "artworks": len(artworks),
            "sets": len(sets),
            "duplicates": duplicates,
            "without_set": without_set,
            "without_image": without_image,
            "top_rarities": top_rarities,
            "recent": recent[:8],
        }

    @staticmethod
    def set_progress(collection: Dict[str, Dict[str, Any]], database_cards: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        owned: Dict[str, Dict[str, Any]] = {}
        available: Dict[str, set] = {}

        def prefix(code: str) -> str:
            value = str(code or "").upper().strip()
            value = value.split("-", 1)[0]
            return value if 2 <= len(value) <= 12 else ""

        for card in database_cards or []:
            if not isinstance(card, dict):
                continue
            cid = str(card.get("id") or card.get("name") or "")
            for set_item in card.get("card_sets") or []:
                if not isinstance(set_item, dict):
                    continue
                p = prefix(set_item.get("set_code"))
                if p:
                    available.setdefault(p, set()).add(cid)

        for item in (collection or {}).values():
            if not isinstance(item, dict):
                continue
            count = max(0, int(item.get("count") or 0))
            card = item.get("card") if isinstance(item.get("card"), dict) else {}
            p = prefix(card.get("_collection_set_code"))
            if not p or count <= 0:
                continue
            entry = owned.setdefault(p, {"ids": set(), "copies": 0, "duplicates": 0, "name": card.get("_collection_set_name") or p})
            cid = str(card.get("id") or card.get("name") or "")
            if cid in entry["ids"]:
                entry["duplicates"] += count
            else:
                entry["ids"].add(cid)
                entry["duplicates"] += max(0, count - 1)
            entry["copies"] += count

        rows: List[Dict[str, Any]] = []
        for p, entry in owned.items():
            total_known = len(available.get(p, set()))
            owned_unique = len(entry["ids"])
            percent = round((owned_unique / total_known * 100.0), 1) if total_known else 0.0
            rows.append({
                "prefix": p,
                "name": str(entry.get("name") or p),
                "owned_unique": owned_unique,
                "copies": int(entry.get("copies") or 0),
                "duplicates": int(entry.get("duplicates") or 0),
                "total_known": total_known,
                "missing": max(0, total_known - owned_unique) if total_known else 0,
                "percent": percent,
            })
        rows.sort(key=lambda row: (-row["percent"], -row["owned_unique"], row["prefix"]))
        return rows


class DiagnosticsRunnerV93:
    """Lokale Laufzeitdiagnose ohne falsche Quellcode-Fehler in der APK."""

    def __init__(self, project_dir: str, user_data_dir: str, database_path: str):
        self.project_dir = os.path.abspath(project_dir)
        self.user_data_dir = os.path.abspath(user_data_dir)
        self.database_path = os.path.abspath(database_path)

    def run(self, network_url: str = "https://db.ygoprodeck.com/api/v7/checkDBVer.php") -> List[Dict[str, Any]]:
        tests: List[Dict[str, Any]] = []

        def add(name: str, ok: bool, detail: str, severity: str = "error") -> None:
            tests.append({"name": name, "ok": bool(ok), "detail": str(detail), "severity": severity})

        # In einer Buildozer-APK liegen Python-Module teilweise kompiliert/gebündelt
        # vor. Deshalb wird die Importfähigkeit geprüft und nicht die Existenz der
        # ursprünglichen .py- oder buildozer.spec-Datei im App-Speicher.
        add("App-Kern", True, "Hauptanwendung läuft")
        for module_name in ("storage_v91", "features_v93"):
            try:
                spec = importlib.util.find_spec(module_name)
                add(f"Modul {module_name}", spec is not None, "Import verfügbar" if spec is not None else "Import nicht gefunden")
            except Exception as exc:
                add(f"Modul {module_name}", False, str(exc))

        required_assets = ["app_logo_transparent.png", "preview_placeholder.png", "presplash.png"]
        for filename in required_assets:
            candidates = [
                os.path.join(self.project_dir, filename),
                os.path.join(os.getcwd(), filename),
            ]
            existing = next((item for item in candidates if os.path.isfile(item) and os.path.getsize(item) > 0), "")
            add(f"App-Ressource {filename}", bool(existing), existing or "Nicht im Laufzeitpaket gefunden")

        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            probe = os.path.join(self.user_data_dir, ".write_probe")
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(probe)
            add("Schreibzugriff", True, self.user_data_dir)
        except Exception as exc:
            add("Schreibzugriff", False, str(exc))

        try:
            conn = sqlite3.connect(self.database_path, timeout=10)
            row = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            ok = bool(row and str(row[0]).lower() == "ok")
            add("SQLite-Integrität", ok, str(row[0] if row else "keine Antwort"))
        except Exception as exc:
            add("SQLite-Integrität", False, str(exc))

        try:
            usage = shutil.disk_usage(self.user_data_dir)
            free_mb = usage.free / (1024 * 1024)
            add("Freier Speicher", free_mb >= 250, f"{free_mb:.0f} MB frei", severity="warning")
        except Exception as exc:
            add("Freier Speicher", False, str(exc), severity="warning")

        try:
            try:
                import certifi
                verified_context = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                verified_context = ssl.create_default_context()
            request = urllib.request.Request(network_url, headers={"User-Agent": f"JustInCard-Diagnostics/{APP_VERSION}"})
            try:
                with urllib.request.urlopen(request, timeout=8, context=verified_context) as response:
                    status = int(getattr(response, "status", 200) or 200)
                    add("YGOPRODeck erreichbar", 200 <= status < 400, f"HTTPS {status}")
            except Exception as verified_exc:
                # Derselbe defensive Android-Fallback wie in der App. Er verhindert,
                # dass ein unvollständiger Hersteller-Zertifikatsspeicher fälschlich
                # als Netzwerkausfall gemeldet wird.
                insecure_context = ssl._create_unverified_context()
                with urllib.request.urlopen(request, timeout=8, context=insecure_context) as response:
                    status = int(getattr(response, "status", 200) or 200)
                    add(
                        "YGOPRODeck erreichbar",
                        200 <= status < 400,
                        f"HTTPS {status}; Android-Zertifikat-Fallback aktiv",
                        severity="warning",
                    )
        except Exception as exc:
            add("YGOPRODeck erreichbar", False, str(exc), severity="warning")

        return tests

