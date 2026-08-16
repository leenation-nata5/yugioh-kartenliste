# -*- coding: utf-8 -*-
"""Dependency-free v12 domain, migration and offline-pack regression tests."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_packs_v120 import apply_delta_pack, pack_checksum, rollback_delta_pack, validate_pack
from features_v120 import (
    FrameSignal,
    ScanStabilityGate,
    benchmark_scan_records,
    collection_market_summary,
    compact_deck_share_payload,
    export_ydk,
    parse_deck_share_payload,
    parse_ydk,
    price_trend,
    validate_deck,
)
from storage_v91 import AppDatabaseV91


def sample_deck() -> dict:
    return {
        "name": "Contract Deck",
        "cards": [
            {"card": {"id": 10_000_000 + index, "name": f"Karte {index}"}, "count": 1, "zone": "main"}
            for index in range(40)
        ],
    }


def run() -> None:
    deck = sample_deck()
    ydk = export_ydk(deck)
    assert ydk.startswith("#created by Just InCard v12\n#main\n")
    imported = parse_ydk(ydk)
    assert sum(item["count"] for item in imported["cards"]) == 40
    assert validate_deck(deck, "TCG")["valid"] is True
    forbidden = validate_deck(deck, "TCG", {"10000000": 0})
    assert forbidden["valid"] is False
    assert any("0 laut TCG" in item for item in forbidden["errors"])

    share = compact_deck_share_payload(deck, "TCG")
    restored = parse_deck_share_payload(share)
    assert restored["name"] == deck["name"]
    assert restored["format"] == "TCG"
    assert sum(item["count"] for item in restored["cards"]) == 40

    fingerprint = ScanStabilityGate.fingerprint("SBCB-DE001 89631139")
    gate = ScanStabilityGate(required_frames=3, duplicate_seconds=3.5)
    signal = FrameSignal(0.55, 0.35, 0.60, 0.03, 0.72, fingerprint)
    assert gate.push(signal, now=1.0)["ready"] is False
    assert gate.push(signal, now=2.0)["ready"] is False
    assert gate.push(signal, now=3.0)["ready"] is True
    duplicate = gate.push(signal, now=4.0)
    assert duplicate["duplicate"] is True and duplicate["ready"] is False

    market = collection_market_summary(
        {"owned": {"count": 2, "card": {"name": "A"}, "metadata": {"market_price": 3.25}}},
        {
            "owned": {"wishlist": True, "trade": True},
            "wish:unowned": {"wishlist": True, "trade": False},
        },
    )
    assert market == {
        "copies": 2,
        "duplicates": 1,
        "priced_copies": 2,
        "estimated_value": 6.5,
        "wishlist_items": 2,
        "trade_copies": 2,
    }
    trend = price_trend([
        {"observed_at": 1, "price": 4.0},
        {"observed_at": 2, "price": 5.0},
    ])
    assert trend["direction"] == "up" and trend["change_percent"] == 25.0

    pack = {
        "schema": 1,
        "pack_id": "de-contract-001",
        "base_version": "1",
        "target_version": "2",
        "language": "de",
        "operations": [
            {"op": "delete", "id": 1},
            {"op": "upsert", "card": {"id": 2, "name": "Neu"}},
        ],
    }
    pack["checksum"] = pack_checksum(pack)
    assert validate_pack(pack)["operations"] == 2
    base = [{"id": 1, "name": "Alt"}]
    updated, rollback = apply_delta_pack(base, pack)
    assert updated == [{"id": 2, "name": "Neu"}]
    assert rollback_delta_pack(updated, rollback) == base

    benchmark = benchmark_scan_records([
        {"correct": True, "latency_ms": 120, "device_class": "phone"},
        {"correct": False, "false_positive": True, "latency_ms": 280, "device_class": "tablet"},
    ])
    assert benchmark["total"] == 2
    assert benchmark["accuracy"] == 0.5
    assert benchmark["false_positive_rate"] == 0.5

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "legacy.sqlite3"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE collection (collection_key TEXT PRIMARY KEY, count INTEGER NOT NULL, card_json TEXT NOT NULL, updated_at REAL NOT NULL)"
            )
            conn.execute(
                "INSERT INTO collection VALUES (?,?,?,?)",
                ("legacy", 1, json.dumps({"id": 7, "name": "Legacy"}), 1.0),
            )
        database = AppDatabaseV91(str(db_path))
        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(collection)")}
        assert "metadata_json" in columns
        database.save_collection({
            "variant": {
                "count": 2,
                "card": {"id": 8, "name": "Persistiert"},
                "metadata": {"condition": "Near Mint", "market_price": 9.5},
            }
        })
        loaded = database.load_collection()
        assert loaded["variant"]["metadata"]["market_price"] == 9.5
        database.set_collection_flags("variant", wishlist=True, trade=True, desired_count=3, note="Test")
        assert database.get_collection_flags("variant")["desired_count"] == 3
        start = 1_700_000_000
        for index in range(5):
            database.add_price_point("variant", 10 + index, observed_at=start + index * 86_400)
        latest = database.recent_prices("variant", 3)
        assert [point["price"] for point in latest] == [12.0, 13.0, 14.0]
        assert database.integrity_check() is True

    print("v12.0.0 core/migration/offline-pack contract tests: OK")


if __name__ == "__main__":
    run()
