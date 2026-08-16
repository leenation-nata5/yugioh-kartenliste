# -*- coding: utf-8 -*-
"""Vertrag für den nahtlosen Android/Kivy-Startübergang in v11.0."""
from pathlib import Path
from PIL import Image
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_version import APP_VERSION, APP_BUILD

assert APP_VERSION == "12.0.0"
assert APP_BUILD == 1200

main = (ROOT / "main.py").read_text(encoding="utf-8")
spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")

assert 'PRESPLASH_FILE = "presplash.png"' in main
assert 'STARTUP_BG_HEX = "#020512"' in main
assert 'Window.clearcolor = STARTUP_BG' in main
assert 'source=presplash_source' in main
assert 'branded_screen.fit_mode = "contain"' in main
assert 'self._splash_bg_color = Color(*STARTUP_BG)' in main
assert 'Clock.schedule_once(lambda *_: self.finish_start_loading_screen(), 0.95)' in main
assert 'android.presplash_color = #020512' in spec
assert re.search(r'^version\s*=\s*12\.0\.0\s*$', spec, re.M)
assert 'just-incard-v1200-arm64-api35-ndk27c' in workflow
assert 'tests/test_v1081_startup_transition_contract.py' in workflow

im = Image.open(ROOT / "presplash.png").convert("RGB")
assert im.size == (1080, 1920)
corner = im.getpixel((0, 0))
assert all(abs(a-b) <= 2 for a,b in zip(corner, (2,5,18))), corner

assert sorted(p.name for p in ROOT.glob("*.txt")) == ["CHANGELOG_v12_0_0.txt"]
print("v12.0.0 seamless startup transition contract tests: OK")
