# -*- coding: utf-8 -*-
"""Regressionstest für GitHub-Web-Uploads über bestehende Repository-Dateien."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run() -> None:
    from app_version import APP_BUILD, APP_VERSION

    assert APP_VERSION == "12.0.1"
    assert APP_BUILD == 1201

    preflight = (ROOT / "preflight_check.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")

    # Preflight darf einen alten Changelog aus einem Overlay-Upload selbst heilen.
    for fragment in (
        "def cleanup_stale_release_files()",
        'ROOT.glob("CHANGELOG_v*.txt")',
        "path.unlink()",
        'expected = "CHANGELOG_v12_0_1.txt"',
        "cleanup_stale_release_files()",
    ):
        assert fragment in preflight, fragment

    # Der Workflow bereinigt schon vor Modell-Download/Tests, damit alte Dateien
    # nicht erneut einen unnötigen CI-Lauf blockieren.
    for fragment in (
        "Alte Versionsdateien aus Overlay-Upload bereinigen",
        'CURRENT_CHANGELOG="CHANGELOG_v${APP_VERSION//./_}.txt"',
        "find . -maxdepth 1 -type f -name 'CHANGELOG_v*.txt'",
        '! -name "$CURRENT_CHANGELOG" -print -delete',
        'test -f "$CURRENT_CHANGELOG"',
        "tests/test_v1123_repository_overlay_contract.py",
    ):
        assert fragment in workflow, fragment

    assert sorted(path.name for path in ROOT.glob("*.txt")) == ["CHANGELOG_v12_0_1.txt"]
    print("v12.0.1 repository overlay/upload cleanup contract tests: OK")


if __name__ == "__main__":
    run()
