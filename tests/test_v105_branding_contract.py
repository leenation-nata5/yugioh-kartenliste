# -*- coding: utf-8 -*-
"""Branding-Vertrag für Just InCard v11.0."""
from pathlib import Path
from PIL import Image
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD, APP_DEVELOPER
    assert APP_VERSION == "12.0.1"
    assert APP_BUILD == 1201
    assert APP_DEVELOPER == "leenation"

    expected = {
        "app_logo_transparent.png": True,
        "app_logo.png": True,
        "app_icon.png": False,
        "assets/ui/app_mark.png": True,
        "presplash.png": False,
        "branding/logo_transparent_original.png": True,
        "branding/logo_app_icon_original.png": False,
    }
    for name, should_have_transparency in expected.items():
        path = ROOT / name
        assert path.is_file() and path.stat().st_size > 0, name
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A").getextrema()
            if should_have_transparency:
                assert alpha[0] < 255, (name, alpha)
            else:
                assert alpha[0] == 255, (name, alpha)

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert re.search(r"^version\s*=\s*12\.0\.1\s*$", spec, re.M)
    assert re.search(r"^icon\.filename\s*=\s*app_icon\.png\s*$", spec, re.M)
    assert 'APP_LOGO_TRANSPARENT_FILE = "app_logo_transparent.png"' in main
    assert 'test_v105_branding_contract.py' in workflow
    assert 'just-incard-v1201-arm64-api35-ndk27c' in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v12_0_1.txt"], txt_files
    print("v12.0.1 branding/app-icon contract tests: OK")


if __name__ == "__main__":
    run()
