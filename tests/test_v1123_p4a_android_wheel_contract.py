# -*- coding: utf-8 -*-
"""Regression test for Build-Logs-4 Android wheel staging failure."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run() -> None:
    from app_version import APP_BUILD, APP_VERSION
    from ci.patch_p4a_android_wheels import MARKER, OLD, patch_file

    assert APP_VERSION == "12.0.0"
    assert APP_BUILD == 1200

    # Reproduce the relevant p4a staging source contract and verify the patch.
    fixture = "from pythonforandroid.recipe import PyProjectRecipe\n\n" + OLD + "\n"
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "build.py"
        target.write_text(fixture, encoding="utf-8")
        assert patch_file(target) is True
        patched = target.read_text(encoding="utf-8")
        assert MARKER in patched
        assert "--only-binary=:all:" in patched
        assert "--platform={}" in patched
        assert "--python-version={2}" in patched
        assert "PyProjectRecipe.get_wheel_platform_tags(arch.arch, ctx)" in patched
        assert patch_file(target) is False  # idempotent

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "python-for-android vorladen" in workflow
    assert "Android-Wheel-Staging-Hotfix anwenden" in workflow
    assert "ci/patch_p4a_android_wheels.py" in workflow
    assert "tests/test_v1123_p4a_android_wheel_contract.py" in workflow
    assert "not a supported wheel" in workflow
    assert "just-incard-v1200-arm64-api35-ndk27c" in workflow

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert "version = 12.0.0" in spec
    assert "android.numeric_version = 1200" in spec

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v12_0_0.txt"], txt_files
    print("v12.0.0 p4a Android-wheel staging contract tests: OK")


if __name__ == "__main__":
    run()
