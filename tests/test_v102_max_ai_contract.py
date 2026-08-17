# -*- coding: utf-8 -*-
"""Maximaler KI-/Deck-/Artwork-Vertrag für Just InCard v11.0."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def run():
    from app_version import APP_VERSION, APP_BUILD
    from ai_scanner_v102 import (
        AI_MODEL_STACK_V102, CARD_LANGUAGE_CODES_V102, TEXT_COLOR_PROFILES_V102,
        artwork_identity_key, collection_artwork_suffix, card_family,
        rank_scan_items, build_preview_map,
    )
    from deck_ai_v102 import build_deck_suggestions, zone
    assert APP_VERSION=='12.0.1' and APP_BUILD==1201
    ids={x['id'] for x in AI_MODEL_STACK_V102}
    for required in ('mediapipe_detector','litert_image_embedder','mlkit_latin','mlkit_japanese','mlkit_korean','mlkit_chinese','paddleocr','tesseract','openai_vision'):
        assert required in ids, required
    for code in ('de','','fr','it','pt','es','ja','ko','zh','zh-tw'):
        assert code in CARD_LANGUAGE_CODES_V102
    assert len(TEXT_COLOR_PROFILES_V102)>=12
    cards=[
      {'id':1,'name':'A','type':'Effect Monster','archetype':'Test','desc':'Add 1 Test card from your Deck to your hand.','level':4,'attribute':'DARK','race':'Spellcaster','card_images':[{'id':11,'image_url':'a'}], '_artwork_image':{'id':11}},
      {'id':1,'name':'A','type':'Effect Monster','archetype':'Test','desc':'Add 1 Test card from your Deck to your hand.','level':4,'attribute':'DARK','race':'Spellcaster','card_images':[{'id':12,'image_url':'b'}], '_artwork_image':{'id':12}},
    ]
    assert artwork_identity_key(cards[0])!=artwork_identity_key(cards[1])
    assert collection_artwork_suffix(cards[0])!=collection_artwork_suffix(cards[1])
    assert card_family({'type':'Pendulum Effect Monster'})=='pendulum'
    assert card_family({'type':'Fusion Monster'})=='fusion'
    assert card_family({'type':'Spell Card'})=='spell'
    ranked=rank_scan_items([
      {'candidate':{'kind':'Passcode','value':'12345678'},'exact':True,'card':{'id':12345678,'type':'Effect Monster'},'score':10},
      {'candidate':{'kind':'Name','value':'Falsch'},'exact':False,'card':{'id':9,'type':'Trap Card'},'score':10},
    ],quality={'score':90},ocr_text='Monster')
    assert ranked[0]['card']['id']==12345678
    # 40 Mainkarten + Extra Deck aus einer künstlichen Sammlung
    collection={}
    for i in range(20):
      collection[f'k{i}']={'count':3,'card':{'id':100+i,'name':f'Test {i}','type':'Effect Monster','archetype':'Test','desc':'Special Summon a Test monster and add a Test card.','level':4,'attribute':'DARK','race':'Spellcaster'}}
    for i in range(5):
      collection[f'e{i}']={'count':1,'card':{'id':200+i,'name':f'Extra {i}','type':'Xyz Monster','archetype':'Test','desc':'2 Level 4 monsters','rank':4}}
    suggestions=build_deck_suggestions(collection,3)
    assert suggestions and suggestions[0]['stats']['main']==40
    assert suggestions[0]['stats']['extra']<=15
    assert all(x['count']<=3 for x in suggestions[0]['cards'])
    main=(ROOT/'main.py').read_text(encoding='utf-8')
    for fragment in ('rank_scan_items','build_preview_map','collection_artwork_suffix','build_deck_suggestions','call_openai_scan_vision','cloud_ai_scan_enabled','preview_path'):
      assert fragment in main, fragment
    spec=(ROOT/'buildozer.spec').read_text(encoding='utf-8')
    assert 'com.google.mediapipe:tasks-vision:0.10.35' in spec
    assert 'org.tensorflow:tensorflow-lite-task-vision' not in spec
    workflow=(ROOT/'.github/workflows/build-android-apk.yml').read_text(encoding='utf-8')
    assert 'tests/test_v102_max_ai_contract.py' in workflow
    assert 'just-incard-v1201-arm64-api35-ndk27c' in workflow
    manifest=json.loads((ROOT/'models/ai_models_manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']=='12.0.1'
    assert sorted(p.name for p in ROOT.glob('*.txt'))==['CHANGELOG_v12_0_1.txt']
    print('v12.0.1 maximum AI scanner/deck/artwork contract tests: OK')

if __name__=='__main__': run()
