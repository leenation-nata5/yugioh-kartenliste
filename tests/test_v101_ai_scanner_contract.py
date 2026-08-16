# -*- coding: utf-8 -*-
"""Kompatibilitätsprüfung der KI-Scannerbasis in Just InCard v11.0."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def run():
    from app_version import APP_VERSION, APP_BUILD
    from ai_scanner_v102 import AI_MODEL_STACK_V102, TEXT_COLOR_PROFILES_V102, CARD_LANGUAGE_CODES_V102
    from scanner_v100 import gallery_scan_profile, scanner_ai_summary, scanner_text_color_profiles, gallery_ai_runtime_hint
    assert APP_VERSION=='11.2' and APP_BUILD==1120
    assert len(AI_MODEL_STACK_V102)>=9
    assert len(TEXT_COLOR_PROFILES_V102)>=12
    assert all(code in CARD_LANGUAGE_CODES_V102 for code in ('de','','fr','it','pt','es','ja','ko','zh','zh-tw'))
    gallery=gallery_scan_profile()
    assert gallery['ai_models'] and gallery['effect_matching'] is True
    assert gallery['color_ocr_variants']>=12
    assert len(scanner_text_color_profiles())>=12
    assert 'MediaPipe' in scanner_ai_summary()
    assert gallery_ai_runtime_hint(2)['avg_seconds']>gallery_ai_runtime_hint(1)['avg_seconds']
    print('v11.2 AI scanner compatibility tests: OK')

if __name__=='__main__': run()
