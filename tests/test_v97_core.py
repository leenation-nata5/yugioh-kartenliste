# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features_v97 import (
    BackupInspectorV97,
    CacheManagerV97,
    SessionStateStoreV97,
    apply_pending_restore,
    normalize_accessibility_settings,
    schedule_backup_restore,
)


def run():
    with tempfile.TemporaryDirectory() as tmp:
        session_path = os.path.join(tmp, "session.json")
        store = SessionStateStoreV97(session_path)
        saved = store.save({
            "section": "search",
            "page": 3,
            "filters": {"name": "Blauäugiger", "unknown": "wird entfernt"},
            "main_scroll_y": 1.5,
        })
        assert saved["page"] == 3
        assert saved["main_scroll_y"] == 1.0
        assert "unknown" not in saved["filters"]
        assert store.load()["filters"]["name"] == "Blauäugiger"
        store.clear()
        assert store.load() == {}

        user_dir = os.path.join(tmp, "userdata")
        os.makedirs(user_dir)
        backup_path = os.path.join(tmp, "backup.zip")
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("backup_manifest.json", json.dumps({"version": "9.7"}))
            archive.writestr("yugioh_sammlung.json", json.dumps({"a": {"count": 1}}))
            archive.writestr("decks.json", "[]")
            archive.writestr("card_database/cards_de.json", "[]")
            archive.writestr("fremd.txt", "ignorieren")
        report = BackupInspectorV97.inspect(backup_path)
        assert report["valid"] is True
        assert len(report["restorable"]) == 3
        assert "fremd.txt" in report["ignored"]

        marker = os.path.join(user_dir, "pending.json")
        schedule_backup_restore(backup_path, marker)
        restored = apply_pending_restore(user_dir, marker)
        assert restored["applied"] is True
        assert os.path.isfile(os.path.join(user_dir, "yugioh_sammlung.json"))
        assert os.path.isfile(os.path.join(user_dir, "card_database", "cards_de.json"))
        assert not os.path.exists(marker)

        unsafe = os.path.join(tmp, "unsafe.zip")
        with zipfile.ZipFile(unsafe, "w") as archive:
            archive.writestr("../evil.json", "{}")
            archive.writestr("yugioh_sammlung.json", "{}")
        assert BackupInspectorV97.inspect(unsafe)["valid"] is False

        cache_a = os.path.join(tmp, "cache_a")
        cache_b = os.path.join(tmp, "cache_b")
        os.makedirs(cache_a)
        os.makedirs(cache_b)
        Path(cache_a, "a.bin").write_bytes(b"a" * 10)
        Path(cache_b, "b.bin").write_bytes(b"b" * 20)
        cache = CacheManagerV97([cache_a, cache_b])
        assert cache.report()["bytes"] == 30
        cleared = cache.clear()
        assert cleared["removed_files"] == 2
        assert cache.report()["bytes"] == 0

        settings = normalize_accessibility_settings({"cache_limit_mb": 99999, "reduce_motion": 1})
        assert settings["cache_limit_mb"] == 2000
        assert settings["reduce_motion"] is True

    print("v9.7 core compatibility under v10.0.2: OK")


if __name__ == "__main__":
    run()
