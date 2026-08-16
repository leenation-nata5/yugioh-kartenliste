# -*- coding: utf-8 -*-
"""Vertrag für die strikte mehrsprachige Scanner-Suche in v10.8."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD
    from scanner_v108 import (
        card_metadata_consistency,
        extract_scan_metadata,
        language_code_from_set_code,
        strict_set_code_equal,
    )

    assert APP_VERSION == "11.3.0"
    assert APP_BUILD == 1130

    assert strict_set_code_equal("FOTB-DE043", "FOTB-DE043")
    assert not strict_set_code_equal("SDWD-DE001", "FOTB-DE043")
    assert strict_set_code_equal("FOTB-043", "FOTB-EN043")
    assert language_code_from_set_code("FOTB-DE043") == "de"
    assert language_code_from_set_code("FOTB-EN043") == ""
    assert language_code_from_set_code("ATR-400") is None

    metadata = extract_scan_metadata(
        "BLUE-EYES WHITE DRAGON LIGHT DRAGON / NORMAL MONSTER LEVEL 8 ATK/3000 DEF/2500 SDK-001"
    )
    assert metadata["atk"] == 3000
    assert metadata["def"] == 2500
    assert metadata["level"] == 8
    assert metadata["attribute"] == "LIGHT"
    assert metadata["family"] in {"normal_monster", "monster"}
    assert metadata["race"] == "Dragon"

    correct = {
        "id": 89631139,
        "name": "Blue-Eyes White Dragon",
        "type": "Normal Monster",
        "race": "Dragon",
        "attribute": "LIGHT",
        "atk": 3000,
        "def": 2500,
        "level": 8,
    }
    wrong = {
        "id": 34541863,
        "name": "A Cell Breeding Device",
        "type": "Continuous Spell Card",
        "race": "Continuous",
    }
    correct_check = card_metadata_consistency(correct, metadata)
    wrong_check = card_metadata_consistency(wrong, metadata)
    assert correct_check["score"] > 0.9
    assert not correct_check["conflicts"]
    assert wrong_check["severe_conflict"]
    assert len(wrong_check["conflicts"]) >= 2

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    required = (
        "Set-Code – ausschließlich exakt passende Druckcodes",
        "Passcode – ausschließlich exakt passende Karten-ID",
        "Kartenname erst, wenn Set-Code und Passcode nichts ergeben",
        "exact_set_item_for_code",
        "card_metadata_consistency",
        "metadata_conflicts",
        "Keine pauschale Deutsch- oder Englisch-Bevorzugung",
        "Artwork-Vergleich bleibt auf die bereits identifizierte Karte",
        '"kind": "Metadata"',
    )
    for fragment in required:
        assert fragment in main, fragment

    # Name darf erst im dritten Suchabschnitt laufen.
    set_pos = main.index("# Stufe 1: Set-Code")
    pass_pos = main.index("# Stufe 2: Passcode")
    name_pos = main.index("# Stufe 3: Kartenname")
    assert set_pos < pass_pos < name_pos

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert re.search(r"^version\s*=\s*11\.3\.0\s*$", spec, re.M)
    assert "tests/test_v108_strict_scanner_contract.py" in workflow
    assert "just-incard-v1130-arm64-api35-ndk25b" in workflow
    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v11_3_0.txt"]

    print("v11.3.0 strict multilingual scanner contract tests: OK")


if __name__ == "__main__":
    run()
