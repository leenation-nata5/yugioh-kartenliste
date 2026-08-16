# -*- coding: utf-8 -*-
"""Gradle-/AAR-Kompatibilitätsvertrag für Just InCard v11.0."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_version import APP_VERSION, APP_BUILD
assert APP_VERSION=="12.0.0" and APP_BUILD==1200
spec=(ROOT/"buildozer.spec").read_text(encoding="utf-8")
workflow=(ROOT/".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
assert "org.tensorflow:tensorflow-lite-task-vision" not in spec
assert "com.google.mediapipe:tasks-vision:0.10.35" in spec
assert "pickFirst 'lib/**/libc++_shared.so'" in spec
assert "sourceCompatibility = 1.8" in spec
assert "targetCompatibility = 1.8" in spec
assert "android.numeric_version = 1200" in spec
assert "just-incard-v1200-arm64-api35-ndk27c" in workflow
assert "gradle_debug_stacktrace.log" in workflow
assert "./gradlew assembleDebug --stacktrace --info --no-daemon" in workflow
assert "tests/test_v1092_gradle_build_contract.py" in workflow
assert sorted(p.name for p in ROOT.glob("*.txt"))==["CHANGELOG_v12_0_0.txt"]
print("v12.0.0 Gradle/AAR build contract tests: OK")
