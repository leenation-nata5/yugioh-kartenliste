# -*- coding: utf-8 -*-
"""Funktions-/Sicherheitsvertrag für Just InCard v11.0."""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD, APP_DEVELOPER, APP_ADMIN
    from features_v104 import (
        APP_DEVELOPER as FEATURE_DEVELOPER,
        APP_ADMIN as FEATURE_ADMIN,
        AutomaticBackupManagerV104,
        confidence_breakdown_text,
        find_duplicate_variant_groups,
        normalized_collection_metadata,
        simulate_deck_hands,
    )
    from security_v104 import DEVELOPER_NAME, ADMIN_NAME

    assert APP_VERSION == "11.2.3"
    assert APP_BUILD == 1123
    assert APP_DEVELOPER == APP_ADMIN == "leenation"
    assert FEATURE_DEVELOPER == FEATURE_ADMIN == "leenation"
    assert DEVELOPER_NAME == ADMIN_NAME == "leenation"

    metadata = normalized_collection_metadata({"condition": "Near Mint", "storage_location": "Ordner 1"})
    assert metadata["condition"] == "Near Mint"
    assert metadata["storage_location"] == "Ordner 1"

    collection = {
        "a": {"count": 1, "card": {"id": 1, "name": "Test", "_collection_set": {"set_code": "ABC-DE001"}}},
        "b": {"count": 2, "card": {"id": 1, "name": "Test", "_collection_set": {"set_code": "ABC-DE001"}}},
    }
    assert find_duplicate_variant_groups(collection)
    assert "Set-Code 100%" in confidence_breakdown_text({"confidence": 80, "kind": "Set-Code", "set_code_exact": True})

    starter = {"name": "Starter", "type": "Effect Monster", "desc": "Füge 1 Karte von deinem Deck deiner Hand hinzu."}
    interaction = {"name": "Interaktion", "type": "Trap Card", "desc": "Annulliere den Effekt und zerstöre die Karte."}
    filler = {"name": "Füller", "type": "Effect Monster", "desc": "Keine besondere Funktion."}
    deck = {"cards": [
        {"card": starter, "count": 20, "zone": "main"},
        {"card": interaction, "count": 10, "zone": "main"},
        {"card": filler, "count": 10, "zone": "main"},
    ]}
    simulation = simulate_deck_hands(deck, samples=100)
    assert simulation["samples"] == 100
    assert simulation["starter_probability"] > 0

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        data = root / "collection.json"
        data.write_text("{}", encoding="utf-8")
        manager = AutomaticBackupManagerV104(str(root / "backups"), keep=2, min_interval_seconds=1)
        target = manager.create([str(data)], APP_VERSION)
        assert target and Path(target).is_file()

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")

    assert "MAX_DECKS = 50" in main
    assert "open_collection_metadata_editor" in main
    assert "open_scan_review_center" in main
    assert "open_scanner_statistics_v104" in main
    assert "open_deck_test_hand_popup" in main
    assert "open_deck_explanation_popup" in main
    assert "choose_deck_cover_popup" in main
    assert "duplicate_deck_v104" in main
    assert "toggle_deck_archive_v104" in main
    assert "open_privacy_controls_popup" in main
    assert "open_offline_status_popup" in main
    assert "open_device_layout_info" in main
    assert "AutomaticBackupManagerV104" in main
    assert r"Programmierer/Admin: \`leenation\`" in workflow
    assert "prepare_release_hardening.py" in workflow
    assert "PYTHONOPTIMIZE=2" in workflow
    assert "android.allow_backup = False" in spec
    assert "android.private_storage = True" in spec
    assert "txt,md" not in spec

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_2_3.txt"], txt_files
    print("v11.2.3 features/security/tablet contract tests: OK")


if __name__ == "__main__":
    run()
