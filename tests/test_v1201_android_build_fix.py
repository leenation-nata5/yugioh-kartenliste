# -*- coding: utf-8 -*-
"""Regression contract for the Build-Logs-7 Android wheel failure."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run() -> None:
    from app_version import APP_BUILD, APP_VERSION
    from ci.verify_android_python_packages import (
        EXPECTED_UNIVERSAL_WHEEL,
        PINNED_REQUIREMENT,
        verify_spec,
        verify_wheel_filename,
    )

    assert APP_VERSION == "12.0.1"
    assert APP_BUILD == 1201

    requirements = verify_spec(ROOT / "buildozer.spec")
    assert PINNED_REQUIREMENT in requirements
    verify_wheel_filename(EXPECTED_UNIVERSAL_WHEEL)

    # The exact wheel selected in Build #7 must stay rejected by our guard.
    failed_wheel = "charset_normalizer-3.5.1-cp314-cp314-android_24_arm64_v8a.whl"
    try:
        verify_wheel_filename(failed_wheel)
    except RuntimeError as exc:
        assert "not host-stageable" in str(exc) or "Expected" in str(exc)
    else:
        raise AssertionError("Build #7 Android wheel was unexpectedly accepted")

    # Missing or floating pins must fail before the long Android build begins.
    with tempfile.TemporaryDirectory() as td:
        invalid = Path(td) / "buildozer.spec"
        invalid.write_text(
            "[app]\nrequirements = python3,kivy,charset-normalizer\n",
            encoding="utf-8",
        )
        try:
            verify_spec(invalid)
        except RuntimeError as exc:
            assert PINNED_REQUIREMENT in str(exc)
        else:
            raise AssertionError("Floating charset-normalizer was accepted")

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "ci/verify_android_python_packages.py" in workflow
    assert "tests/test_v1201_android_build_fix.py" in workflow
    assert "EXPECTED_P4A_COMMIT" in workflow
    assert "58d21141f17c889bf8585f5665921d72028f8831" in workflow
    assert "ci/patch_p4a_android_wheels.py" not in workflow
    assert "Android-Wheel-Staging-Hotfix anwenden" not in workflow
    assert "just-incard-v1201-arm64-api35-ndk27c" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v12_0_1.txt"], txt_files
    print("v12.0.1 Build-Logs-7 Android dependency regression test: OK")


if __name__ == "__main__":
    run()
