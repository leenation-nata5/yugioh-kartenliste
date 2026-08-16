# -*- coding: utf-8 -*-
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features_v93 import (
    ScanLearningStoreV93,
    UndoManagerV93,
    IncrementalSyncStateV93,
    CollectionAnalyticsV93,
    recommend_performance_mode,
)


def run():
    with tempfile.TemporaryDirectory() as tmp:
        learning = ScanLearningStoreV93(os.path.join(tmp, "learning.json"))
        assert learning.remember("DAB1-DEO42", "Set-Code", "DABL-DE042", card_id=123)
        expanded = learning.expand_candidates([{"kind": "Set-Code", "value": "DAB1-DEO42", "priority": 70}])
        assert expanded[0]["value"] == "DABL-DE042"

        undo = UndoManagerV93(os.path.join(tmp, "undo.json"))
        undo.push("collection_delta", "Test", {"key": "abc", "before_item": None})
        assert undo.peek()["title"] == "Test"
        assert undo.pop()["type"] == "collection_delta"
        assert undo.peek() is None

        sync = IncrementalSyncStateV93(os.path.join(tmp, "sync.json"))
        assert sync.should_sync("source", "1")
        sync.mark_synced("source", "1", 100)
        assert not sync.should_sync("source", "1", max_age_seconds=3600)
        assert sync.should_sync("source", "2", max_age_seconds=3600)

        collection = {
            "a": {"count": 3, "card": {"id": 1, "name": "A", "_collection_set_code": "TEST-DE001", "_collection_set_rarity": "Rare", "card_images": [{"image_url": "x"}]}},
            "b": {"count": 1, "card": {"id": 2, "name": "B", "_collection_set_code": "TEST-DE002", "_collection_set_rarity": "Common", "card_images": [{"image_url": "y"}]}},
        }
        summary = CollectionAnalyticsV93.summarize(collection)
        assert summary["total"] == 4
        assert summary["duplicates"] == 2
        db_cards = [
            {"id": 1, "name": "A", "card_sets": [{"set_code": "TEST-DE001"}]},
            {"id": 2, "name": "B", "card_sets": [{"set_code": "TEST-DE002"}]},
            {"id": 3, "name": "C", "card_sets": [{"set_code": "TEST-DE003"}]},
        ]
        progress = CollectionAnalyticsV93.set_progress(collection, db_cards)
        assert progress[0]["owned_unique"] == 2
        assert progress[0]["total_known"] == 3

        assert recommend_performance_mode({"device_class": "compact_phone"}) == "eco"
        assert recommend_performance_mode({"device_class": "large_tablet"}, 8000) == "quality"

    print("v9.3 legacy core compatibility under v10.0.2: OK")


if __name__ == "__main__":
    run()
