# -*- coding: utf-8 -*-
"""Persistente SQLite-Hilfen für Just InCard v9.1.

Die Datei ist absichtlich unabhängig von Kivy und kann daher in Hintergrund-
Threads genutzt werden. JSON-Dateien bleiben als lesbare Sicherung erhalten,
SQLite ist jedoch die bevorzugte Laufzeitquelle für Sammlung, Decks,
Einstellungen, Scan-Warteschlange und Leistungsdaten.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional


class AppDatabaseV91:
    SCHEMA_VERSION = 1

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collection (
                    collection_key TEXT PRIMARY KEY,
                    count INTEGER NOT NULL CHECK(count >= 0),
                    card_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decks (
                    deck_index INTEGER PRIMARY KEY,
                    deck_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS key_value (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(namespace, key)
                );
                CREATE TABLE IF NOT EXISTS scan_queue (
                    queue_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    duration_ms REAL,
                    details_json TEXT,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scan_queue_active
                    ON scan_queue(completed, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_performance_created
                    ON performance_metrics(created_at DESC);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
                (str(self.SCHEMA_VERSION),),
            )

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _load(value: Optional[str], fallback: Any) -> Any:
        try:
            return json.loads(value) if value else fallback
        except Exception:
            return fallback

    def save_collection(self, collection: Dict[str, Dict[str, Any]]) -> None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM collection")
            rows = []
            for key, item in (collection or {}).items():
                if not isinstance(item, dict):
                    continue
                count = max(0, int(item.get("count", 0) or 0))
                card = item.get("card") if isinstance(item.get("card"), dict) else {}
                if count <= 0:
                    continue
                rows.append((str(key), count, self._dump(card), now))
            conn.executemany(
                "INSERT INTO collection(collection_key, count, card_json, updated_at) VALUES(?,?,?,?)",
                rows,
            )

    def load_collection(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        with self._lock, self._connect() as conn:
            for row in conn.execute(
                "SELECT collection_key, count, card_json FROM collection ORDER BY collection_key"
            ):
                card = self._load(row["card_json"], {})
                if isinstance(card, dict) and int(row["count"] or 0) > 0:
                    result[str(row["collection_key"])] = {
                        "count": int(row["count"]),
                        "card": card,
                    }
        return result

    def save_decks(self, decks: Iterable[Dict[str, Any]]) -> None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM decks")
            rows = []
            for index, deck in enumerate(list(decks or [])):
                if isinstance(deck, dict):
                    rows.append((index, self._dump(deck), now))
            conn.executemany(
                "INSERT INTO decks(deck_index, deck_json, updated_at) VALUES(?,?,?)",
                rows,
            )

    def load_decks(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            for row in conn.execute("SELECT deck_json FROM decks ORDER BY deck_index"):
                deck = self._load(row["deck_json"], {})
                if isinstance(deck, dict):
                    result.append(deck)
        return result

    def set_value(self, namespace: str, key: str, value: Any) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO key_value(namespace, key, value_json, updated_at)
                VALUES(?,?,?,?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (str(namespace), str(key), self._dump(value), time.time()),
            )

    def get_value(self, namespace: str, key: str, fallback: Any = None) -> Any:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM key_value WHERE namespace=? AND key=?",
                (str(namespace), str(key)),
            ).fetchone()
        return self._load(row["value_json"], fallback) if row else fallback

    def save_scan_queue(self, queue_id: str, state: Dict[str, Any], completed: bool = False) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scan_queue(queue_id, state_json, updated_at, completed)
                VALUES(?,?,?,?)
                ON CONFLICT(queue_id) DO UPDATE SET
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at,
                    completed=excluded.completed
                """,
                (str(queue_id), self._dump(state or {}), time.time(), 1 if completed else 0),
            )

    def latest_active_scan_queue(self) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT queue_id, state_json, updated_at FROM scan_queue WHERE completed=0 ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        state = self._load(row["state_json"], {})
        if not isinstance(state, dict):
            return None
        state["queue_id"] = row["queue_id"]
        state["updated_at"] = float(row["updated_at"] or 0)
        return state

    def complete_scan_queue(self, queue_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE scan_queue SET completed=1, updated_at=? WHERE queue_id=?",
                (time.time(), str(queue_id)),
            )

    def clear_scan_queue(self, queue_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM scan_queue WHERE queue_id=?", (str(queue_id),))

    def record_performance(self, event_name: str, duration_ms: Optional[float] = None, details: Optional[Dict[str, Any]] = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO performance_metrics(event_name, duration_ms, details_json, created_at) VALUES(?,?,?,?)",
                (
                    str(event_name),
                    None if duration_ms is None else float(duration_ms),
                    self._dump(details or {}),
                    time.time(),
                ),
            )
            conn.execute(
                "DELETE FROM performance_metrics WHERE id NOT IN (SELECT id FROM performance_metrics ORDER BY created_at DESC LIMIT 1000)"
            )

    def recent_performance(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            query = conn.execute(
                "SELECT event_name, duration_ms, details_json, created_at FROM performance_metrics ORDER BY created_at DESC LIMIT ?",
                (max(1, min(int(limit or 100), 1000)),),
            )
            for row in query:
                rows.append(
                    {
                        "event": row["event_name"],
                        "duration_ms": row["duration_ms"],
                        "details": self._load(row["details_json"], {}),
                        "created_at": row["created_at"],
                    }
                )
        return rows
