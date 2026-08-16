# -*- coding: utf-8 -*-
"""Persistente SQLite-Hilfen für Just InCard v12.

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
from typing import Any, Dict, Iterable, List, Mapping, Optional


class AppDatabaseV91:
    # Additive migration: v3 keeps every earlier table, adds indexed flags and
    # price history and persists per-variant collection metadata in SQLite.
    # Existing installations are upgraded in place without dropping user data.
    SCHEMA_VERSION = 3

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
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
                    metadata_json TEXT NOT NULL DEFAULT '{}',
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
                CREATE TABLE IF NOT EXISTS collection_flags (
                    collection_key TEXT PRIMARY KEY,
                    wishlist INTEGER NOT NULL DEFAULT 0,
                    trade INTEGER NOT NULL DEFAULT 0,
                    desired_count INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_key TEXT NOT NULL,
                    source TEXT NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'EUR',
                    price REAL NOT NULL CHECK(price >= 0),
                    observed_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS data_packs (
                    pack_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    installed_at REAL NOT NULL,
                    rollback_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_scan_queue_active
                    ON scan_queue(completed, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_performance_created
                    ON performance_metrics(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_collection_flags_wishlist
                    ON collection_flags(wishlist, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_collection_flags_trade
                    ON collection_flags(trade, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_price_history_card_time
                    ON price_history(collection_key, observed_at DESC);
                """
            )
            collection_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(collection)")
            }
            if "metadata_json" not in collection_columns:
                conn.execute(
                    "ALTER TABLE collection ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
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
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                if count <= 0:
                    continue
                rows.append((str(key), count, self._dump(card), self._dump(metadata), now))
            conn.executemany(
                "INSERT INTO collection(collection_key, count, card_json, metadata_json, updated_at) VALUES(?,?,?,?,?)",
                rows,
            )

    def load_collection(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        with self._lock, self._connect() as conn:
            for row in conn.execute(
                "SELECT collection_key, count, card_json, metadata_json FROM collection ORDER BY collection_key"
            ):
                card = self._load(row["card_json"], {})
                if isinstance(card, dict) and int(row["count"] or 0) > 0:
                    item = {
                        "count": int(row["count"]),
                        "card": card,
                    }
                    metadata = self._load(row["metadata_json"], {})
                    if isinstance(metadata, dict) and metadata:
                        item["metadata"] = metadata
                    result[str(row["collection_key"])] = item
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

    def set_collection_flags(
        self,
        collection_key: str,
        *,
        wishlist: bool = False,
        trade: bool = False,
        desired_count: int = 0,
        note: str = "",
    ) -> None:
        """Store wishlist/trade state without rewriting the full collection."""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collection_flags(collection_key, wishlist, trade, desired_count, note, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(collection_key) DO UPDATE SET
                    wishlist=excluded.wishlist,
                    trade=excluded.trade,
                    desired_count=excluded.desired_count,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (
                    str(collection_key),
                    1 if wishlist else 0,
                    1 if trade else 0,
                    max(0, int(desired_count or 0)),
                    str(note or "")[:1000],
                    time.time(),
                ),
            )

    def get_collection_flags(self, collection_key: str) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT wishlist, trade, desired_count, note, updated_at FROM collection_flags WHERE collection_key=?",
                (str(collection_key),),
            ).fetchone()
        if not row:
            return {"wishlist": False, "trade": False, "desired_count": 0, "note": ""}
        return {
            "wishlist": bool(row["wishlist"]),
            "trade": bool(row["trade"]),
            "desired_count": max(0, int(row["desired_count"] or 0)),
            "note": str(row["note"] or ""),
            "updated_at": float(row["updated_at"] or 0),
        }

    def all_collection_flags(self, *, wishlist: Optional[bool] = None, trade: Optional[bool] = None) -> Dict[str, Dict[str, Any]]:
        clauses: List[str] = []
        values: List[Any] = []
        if wishlist is not None:
            clauses.append("wishlist=?")
            values.append(1 if wishlist else 0)
        if trade is not None:
            clauses.append("trade=?")
            values.append(1 if trade else 0)
        query = "SELECT collection_key, wishlist, trade, desired_count, note, updated_at FROM collection_flags"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        result: Dict[str, Dict[str, Any]] = {}
        with self._lock, self._connect() as conn:
            for row in conn.execute(query, tuple(values)):
                result[str(row["collection_key"])] = {
                    "wishlist": bool(row["wishlist"]),
                    "trade": bool(row["trade"]),
                    "desired_count": max(0, int(row["desired_count"] or 0)),
                    "note": str(row["note"] or ""),
                    "updated_at": float(row["updated_at"] or 0),
                }
        return result

    def add_price_point(
        self,
        collection_key: str,
        price: float,
        *,
        source: str = "YGOPRODeck/Cardmarket",
        currency: str = "EUR",
        observed_at: Optional[float] = None,
    ) -> None:
        amount = max(0.0, float(price or 0))
        timestamp = float(observed_at or time.time())
        with self._lock, self._connect() as conn:
            # One point per source/card/day is enough for a useful local trend and
            # prevents unbounded growth during repeated background refreshes.
            day_start = timestamp - (timestamp % 86400)
            conn.execute(
                "DELETE FROM price_history WHERE collection_key=? AND source=? AND observed_at>=? AND observed_at<?",
                (str(collection_key), str(source), day_start, day_start + 86400),
            )
            conn.execute(
                "INSERT INTO price_history(collection_key, source, currency, price, observed_at) VALUES(?,?,?,?,?)",
                (str(collection_key), str(source), str(currency or "EUR")[:8], amount, timestamp),
            )
            conn.execute(
                """
                DELETE FROM price_history
                WHERE id IN (
                    SELECT id FROM price_history WHERE collection_key=?
                    ORDER BY observed_at DESC LIMIT -1 OFFSET 366
                )
                """,
                (str(collection_key),),
            )

    def recent_prices(self, collection_key: str, limit: int = 90) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            for row in conn.execute(
                """
                SELECT source, currency, price, observed_at FROM (
                    SELECT source, currency, price, observed_at FROM price_history
                    WHERE collection_key=? ORDER BY observed_at DESC LIMIT ?
                ) ORDER BY observed_at ASC
                """,
                (str(collection_key), max(1, min(int(limit or 90), 366))),
            ):
                result.append({
                    "source": str(row["source"]),
                    "currency": str(row["currency"]),
                    "price": float(row["price"]),
                    "observed_at": float(row["observed_at"]),
                })
        return result

    def register_data_pack(self, pack_id: str, version: str, checksum: str, rollback: Mapping[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO data_packs(pack_id, version, checksum, installed_at, rollback_json)
                VALUES(?,?,?,?,?)
                ON CONFLICT(pack_id) DO UPDATE SET version=excluded.version,
                    checksum=excluded.checksum, installed_at=excluded.installed_at,
                    rollback_json=excluded.rollback_json
                """,
                (str(pack_id), str(version), str(checksum), time.time(), self._dump(dict(rollback or {}))),
            )

    def data_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT pack_id, version, checksum, installed_at, rollback_json FROM data_packs WHERE pack_id=?",
                (str(pack_id),),
            ).fetchone()
        if not row:
            return None
        return {
            "pack_id": str(row["pack_id"]),
            "version": str(row["version"]),
            "checksum": str(row["checksum"]),
            "installed_at": float(row["installed_at"]),
            "rollback": self._load(row["rollback_json"], {}),
        }

    def latest_data_pack(self) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT pack_id FROM data_packs ORDER BY installed_at DESC LIMIT 1"
            ).fetchone()
        return self.data_pack(str(row["pack_id"])) if row else None

    def remove_data_pack(self, pack_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM data_packs WHERE pack_id=?", (str(pack_id),))

    def checkpoint(self) -> None:
        """Flush the WAL at safe lifecycle points without using FULL sync per write."""
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

    def integrity_check(self) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("PRAGMA quick_check").fetchone()
        return bool(row and str(row[0]).lower() == "ok")
