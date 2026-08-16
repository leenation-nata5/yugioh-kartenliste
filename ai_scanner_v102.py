# -*- coding: utf-8 -*-
"""Maximaler KI-Scanner-Orchestrator für Just InCard v11.2.1.

Kivy-unabhängig: Modellregister, Sprach-/Kartentypabdeckung, Artwork-Identität,
Batch-Vorschauschutz und Ensemble-Bewertung.
"""
from __future__ import annotations
import hashlib, os, re, shutil, unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

AI_MODEL_STACK_V102 = [
 {"id":"mediapipe_detector","label":"MediaPipe Tasks Vision","purpose":"Kartenfläche, Mehrkarten, Perspektive","runtime":"Android lokal","required":True},
 {"id":"litert_image_embedder","label":"LiteRT Image Embedder/Searcher","purpose":"Artwork-Embedding und Ähnlichkeit","runtime":"Android lokal","required":True},
 {"id":"mlkit_latin","label":"ML Kit Latin OCR","purpose":"DE/EN/FR/IT/PT/ES und weitere lateinische Sprachen","runtime":"Android lokal","required":True},
 {"id":"mlkit_japanese","label":"ML Kit Japanese OCR","purpose":"Japanisch","runtime":"Android lokal","required":True},
 {"id":"mlkit_korean","label":"ML Kit Korean OCR","purpose":"Koreanisch","runtime":"Android lokal","required":True},
 {"id":"mlkit_chinese","label":"ML Kit Chinese OCR","purpose":"vereinfachtes/traditionelles Chinesisch","runtime":"Android lokal","required":True},
 {"id":"mlkit_devanagari","label":"ML Kit Devanagari OCR","purpose":"zusätzlicher Schrift-Fallback","runtime":"Android lokal","required":False},
 {"id":"paddleocr","label":"PaddleOCR PP-OCR mobile","purpose":"optionaler schwerer OCR-Fallback","runtime":"optional lokal","required":False},
 {"id":"tesseract","label":"Tesseract OCR","purpose":"optionaler Offline-Sprachfallback","runtime":"optional lokal","required":False},
 {"id":"openai_vision","label":"OpenAI Vision","purpose":"optionaler Cloud-Fallback bei Unsicherheit","runtime":"optional Cloud","required":False},
]

CARD_LANGUAGE_CODES_V102 = ["de","","fr","it","pt","es","ja","ko","zh","zh-tw"]
CARD_LANGUAGE_LABELS_V102 = {"de":"Deutsch","":"Englisch","fr":"Französisch","it":"Italienisch","pt":"Portugiesisch","es":"Spanisch","ja":"Japanisch","ko":"Koreanisch","zh":"Chinesisch (vereinfacht)","zh-tw":"Chinesisch (traditionell)"}
TEXT_COLOR_PROFILES_V102 = [
 "normal-grau","invertiert","rotkanal","grünkanal","blaukanal","hellster-kanal","dunkelster-kanal",
 "gold-gelb","silber-grau","weiß-auf-dunkel","schwarz-auf-hell","holografisch-lokal"
]

EXTRA_TOKENS=("fusion","synchro","xyz","link")

def normalize(value:Any)->str:
    s=unicodedata.normalize("NFKD",str(value or "")).casefold()
    s="".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def card_family(card:Dict[str,Any])->str:
    t=str(card.get("type") or "").lower(); f=str(card.get("frameType") or "").lower()
    if "spell" in t: return "spell"
    if "trap" in t: return "trap"
    if "skill" in t: return "skill"
    if "token" in t or "token" in f: return "token"
    if "link" in t: return "link"
    if "xyz" in t: return "xyz"
    if "synchro" in t: return "synchro"
    if "fusion" in t: return "fusion"
    if "ritual" in t: return "ritual"
    if "pendulum" in t or card.get("scale") is not None or card.get("pendulumScale") is not None: return "pendulum"
    if "normal" in t: return "normal_monster"
    return "effect_monster" if "monster" in t else "other"

def artwork_identity_key(card:Dict[str,Any])->str:
    art=card.get("_artwork_image") or {}
    raw=card.get("_variant_key") or art.get("id") or art.get("image_url") or art.get("image_url_small")
    if not raw:
        images=card.get("card_images") or []
        idx=int(card.get("_artwork_index") or 0)
        if images and idx < len(images):
            image=images[idx] or {}; raw=image.get("id") or image.get("image_url") or image.get("image_url_small")
    return str(raw or card.get("id") or card.get("name") or "unknown")

def collection_artwork_suffix(card:Dict[str,Any])->str:
    key=artwork_identity_key(card)
    base=str(card.get("id") or "")
    return "" if not key or key==base else "__art_"+re.sub(r"[^a-zA-Z0-9_-]+","_",key)[-80:]

def unique_preview_copy(source_path:str, cache_dir:str, source_index:int=0)->str:
    try:
        p=Path(source_path); cache=Path(cache_dir); cache.mkdir(parents=True,exist_ok=True)
        stat=p.stat(); token=f"{p.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{source_index}".encode()
        digest=hashlib.sha1(token).hexdigest()[:14]
        ext=p.suffix.lower() or ".jpg"; out=cache/f"scan_source_{source_index:03d}_{digest}{ext}"
        if not out.exists(): shutil.copy2(p,out)
        return str(out)
    except Exception: return str(source_path or "")

def build_preview_map(paths:Iterable[str],cache_dir:str)->Dict[str,str]:
    return {str(p):unique_preview_copy(str(p),cache_dir,i) for i,p in enumerate(paths,1)}


def source_scan_session_id(path: str, source_index: int, batch_id: str = "") -> str:
    raw = f"{batch_id}|{source_index}|{Path(str(path or '')).resolve()}|{time_ns_safe(path)}".encode("utf-8", "ignore")
    return f"src_{int(source_index):04d}_{hashlib.sha1(raw).hexdigest()[:14]}"

def time_ns_safe(path: str) -> int:
    try:
        return int(Path(path).stat().st_mtime_ns)
    except Exception:
        return 0

def build_preview_records(paths: Iterable[str], cache_dir: str, batch_id: str = "") -> List[Dict[str, Any]]:
    """Erzeugt unveränderliche, eindeutige Datensätze für jedes ausgewählte Bild.

    Auch identische Dateipfade bleiben getrennte Scanquellen. Dadurch können
    Vorschau, OCR, Artwork und Fehler niemals zwischen Bildern vertauscht werden.
    """
    records: List[Dict[str, Any]] = []
    for index, raw_path in enumerate(list(paths or []), 1):
        path = str(raw_path or "")
        session_id = source_scan_session_id(path, index, batch_id=batch_id)
        preview = unique_preview_copy(path, cache_dir, source_index=index)
        records.append({
            "source_id": session_id,
            "source_index": index,
            "path": path,
            "preview_path": preview,
            "batch_id": str(batch_id or ""),
        })
    return records

@dataclass
class ScanSignalsV102:
    set_code_exact:bool=False; passcode_exact:bool=False; name_similarity:float=0.; effect_similarity:float=0.; artwork_similarity:float=0.;
    language_match:float=0.; card_type_match:float=0.; stats_match:float=0.; color_profile_match:float=0.; quality_score:float=0.; rarity_penalty:float=0.

def confidence(signals:ScanSignalsV102)->float:
    score=(0.27 if signals.set_code_exact else 0)+(0.26 if signals.passcode_exact else 0)
    score+=.13*max(0,min(1,signals.name_similarity))+.13*max(0,min(1,signals.effect_similarity))+.12*max(0,min(1,signals.artwork_similarity))
    score+=.025*max(0,min(1,signals.language_match))+.025*max(0,min(1,signals.card_type_match))+.02*max(0,min(1,signals.stats_match))
    score+=.02*max(0,min(1,signals.color_profile_match))+.02*max(0,min(1,signals.quality_score))-.03*max(0,min(1,signals.rarity_penalty))
    return round(max(0,min(1,score)),4)

def infer_type_match(ocr_text:str,card:Dict[str,Any])->float:
    text=normalize(ocr_text); fam=card_family(card)
    keys={"spell":["spell","zauber","magie","magia"],"trap":["trap","falle","piege","trampa"],"pendulum":["pendulum","pendel"],"fusion":["fusion"],"synchro":["synchro"],"xyz":["xyz"],"link":["link"],"ritual":["ritual"]}
    observed=[k for k,vals in keys.items() if any(v in text for v in vals)]
    if not observed:return .5
    return 1.0 if fam in observed else 0.0

def rank_scan_items(items:Iterable[Dict[str,Any]],quality:Optional[Dict[str,Any]]=None,ocr_text:str="")->List[Dict[str,Any]]:
    out=[]; q=max(0,min(1,float((quality or {}).get("score") or 0)/100.0))
    for raw in items:
        item=dict(raw); candidate=item.get("candidate") or {}; kind=str(candidate.get("kind") or "")
        card=item.get("card") or {}; name_sim=1.0 if kind=="Name" and item.get("exact") else float(item.get("name_similarity") or 0.55 if kind=="Name" else 0)
        stats_match=float(item.get("metadata_score") or item.get("stats_match") or 0.0)
        sig=ScanSignalsV102(set_code_exact=bool(item.get("exact") and kind=="Set-Code"),passcode_exact=bool(item.get("exact") and kind=="Passcode"),name_similarity=name_sim,effect_similarity=float(item.get("effect_similarity") or 0),artwork_similarity=float(item.get("artwork_similarity") or 0),language_match=1.0 if item.get("language") in CARD_LANGUAGE_CODES_V102 else .4,card_type_match=infer_type_match(ocr_text,card),stats_match=stats_match,quality_score=q)
        item["ai_confidence_v102"]=confidence(sig); item["artwork_identity_key"]=artwork_identity_key(card); item["card_family"]=card_family(card)
        item["score"]=float(item.get("score") or 0)+item["ai_confidence_v102"]*420
        item["score"]-=min(420.0,len(item.get("metadata_conflicts") or [])*120.0)
        out.append(item)
    out.sort(key=lambda x:(float(x.get("score") or 0),float(x.get("ai_confidence_v102") or 0),float(x.get("artwork_similarity") or 0)),reverse=True)
    return out


def _bits_similarity(a: int, b: int, bit_count: int) -> float:
    return max(0.0, min(1.0, 1.0 - int((int(a) ^ int(b)).bit_count()) / float(max(1, bit_count))))


def image_visual_signature(path: str, artwork_only: bool = True) -> Optional[Dict[str, Any]]:
    """Kombiniert dHash, aHash, Kantenhash und grobes Farbhistogramm.

    Diese Signatur ist vollständig lokal, klein und wesentlich robuster als ein
    einzelner dHash bei Hologrammreflexionen und unterschiedlichen Rarities.
    """
    try:
        from PIL import Image, ImageOps, ImageFilter, ImageStat
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            if artwork_only:
                w, h = image.size
                image = image.crop((int(w * .09), int(h * .16), int(w * .91), int(h * .62)))
            gray = ImageOps.autocontrast(ImageOps.grayscale(image))
            # dHash 16x16
            dh = gray.resize((17, 16))
            pix = list(dh.getdata())
            dhash = 0
            for y in range(16):
                row = y * 17
                for x in range(16):
                    dhash = (dhash << 1) | int(pix[row + x] > pix[row + x + 1])
            # aHash 16x16
            ah = gray.resize((16, 16))
            ap = list(ah.getdata()); avg = sum(ap) / max(1, len(ap)); ahash = 0
            for value in ap: ahash = (ahash << 1) | int(value >= avg)
            # Kantenhash
            edge = gray.resize((16, 16)).filter(ImageFilter.FIND_EDGES)
            ep = list(edge.getdata()); eavg = sum(ep) / max(1, len(ep)); ehash = 0
            for value in ep: ehash = (ehash << 1) | int(value >= eavg)
            # 4x4x4 RGB-Histogramm
            small = image.resize((64, 64))
            hist = [0] * 64
            for r, g, b in small.getdata():
                hist[(r // 64) * 16 + (g // 64) * 4 + (b // 64)] += 1
            total = float(sum(hist) or 1)
            hist = [x / total for x in hist]
            contrast = float(ImageStat.Stat(gray).stddev[0] if ImageStat.Stat(gray).stddev else 0.0)
            return {"dhash": dhash, "ahash": ahash, "ehash": ehash, "hist": hist, "contrast": contrast}
    except Exception:
        return None


def visual_similarity(path_a: str, path_b: str, artwork_only: bool = True) -> Optional[float]:
    left = image_visual_signature(path_a, artwork_only=artwork_only)
    right = image_visual_signature(path_b, artwork_only=artwork_only)
    if not left or not right:
        return None
    dh = _bits_similarity(left["dhash"], right["dhash"], 256)
    ah = _bits_similarity(left["ahash"], right["ahash"], 256)
    eh = _bits_similarity(left["ehash"], right["ehash"], 256)
    h1, h2 = left["hist"], right["hist"]
    intersection = sum(min(a, b) for a, b in zip(h1, h2))
    contrast_gap = abs(float(left["contrast"]) - float(right["contrast"])) / 128.0
    contrast_score = max(0.0, 1.0 - contrast_gap)
    return round(max(0.0, min(1.0, 0.35 * dh + 0.22 * ah + 0.20 * eh + 0.18 * intersection + 0.05 * contrast_score)), 4)
