# -*- coding: utf-8 -*-
"""Regressionstest für den GitHub-Actions-Abbruch vor dem APK-Build in v11.2.3."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD

    assert APP_VERSION == "11.2.3"
    assert APP_BUILD == 1123

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "source_menu_gallery_bubble" in main
    assert "scanner_fullscreen_layout" in main
    assert 'live_frame_ref["widget"] = camera_clip' in main

    # Diese drei älteren Kompatibilitätstests hatten in v11.2 noch Fragmente
    # der entfernten ScannerSourceTile-/Hinweistext-UI fest verdrahtet und
    # brachen GitHub Actions deshalb ab, bevor Buildozer überhaupt startete.
    v96 = (ROOT / "tests/test_v96_ui_contract.py").read_text(encoding="utf-8")
    v97 = (ROOT / "tests/test_v97_ui_contract.py").read_text(encoding="utf-8")
    v107 = (ROOT / "tests/test_v107_isolated_gallery_contract.py").read_text(encoding="utf-8")
    for source in (v96, v97):
        assert 'ScannerSourceTile("gallery", "Galerie"' not in source
        assert "source_menu_gallery_bubble" in source
    assert "Das Live-Bild wird jetzt ausschließlich im goldenen Kartenrahmen angezeigt" not in v107
    assert 'live_frame_ref[\\"widget\\"] = camera_clip' in v107
    assert "scanner_fullscreen_layout" in v107

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert re.search(r"^version\s*=\s*11\.2\.3\s*$", spec, re.M)
    assert "android.numeric_version = 1123" in spec

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "tests/test_v1123_ci_legacy_contract_hotfix.py" in workflow
    assert "just-incard-v1123-arm64-api35-ndk25b" in workflow

    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v11_2_3.txt"]
    print("v11.2.3 GitHub Actions legacy-contract hotfix tests: OK")


if __name__ == "__main__":
    run()
