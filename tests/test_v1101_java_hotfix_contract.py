# -*- coding: utf-8 -*-
"""Regressionstest für den Java-Compiler-Hotfix in Just InCard v11.2.2."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD

    assert APP_VERSION == "11.2.2"
    assert APP_BUILD == 1122

    java_path = ROOT / "android_src/org/yugioh/kartenliste/NativeAiScanner.java"
    java = java_path.read_text(encoding="utf-8")

    # Der echte GitHub-Fehler aus Build #13: OpenCV Rect.area() ist double.
    assert "Collections.sort(boxes, (a, b) -> Double.compare(b.area(), a.area()));" in java
    assert "Integer.compare(b.area(), a.area())" not in java
    assert not re.search(r"Integer\.compare\([^\n;]*\.area\(\)[^\n;]*\)", java)

    # Andere Comparatoren müssen zu ihren Typen passen.
    assert "Float.compare(b[4], a[4])" in java

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert re.search(r"^version\s*=\s*11\.2\.2\s*$", spec, re.M)
    assert "android.numeric_version = 1122" in spec
    assert "just-incard-v1122-arm64-api35-ndk25b" in workflow
    assert "tests/test_v1101_java_hotfix_contract.py" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_2_2.txt"], txt_files

    print("v11.2.2 Java compiler hotfix contract tests: OK")


if __name__ == "__main__":
    run()
