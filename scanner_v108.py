# -*- coding: utf-8 -*-
"""Strenge Scan-Identifikation für Just InCard v11.2.2.

Kivy-unabhängige Hilfen für:
- feste Suchreihenfolge Set-Code -> Passcode -> Name/Effekt/Artwork
- sprachneutrale Set-Code-Auswertung
- OCR-Metadaten (ATK, DEF, Level, Rang, Link, Pendelskala, Typ, Attribut)
- Gegenprüfung von OCR-Merkmalen mit Kartendaten
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

SET_LANGUAGE_TO_DB = {
    "DE": "de",
    "EN": "",
    "FR": "fr",
    "IT": "it",
    "PT": "pt",
    "ES": "es",
    "SP": "es",
    "JP": "ja",
    "JA": "ja",
    "KR": "ko",
    "KO": "ko",
    "CN": "zh",
    "SC": "zh",
    "TC": "zh-tw",
    "AE": "",
    "EU": "",
    "NA": "",
}

DB_LANGUAGE_LABELS = {
    "de": "Deutsch",
    "": "Englisch",
    "fr": "Französisch",
    "it": "Italienisch",
    "pt": "Portugiesisch",
    "es": "Spanisch",
    "ja": "Japanisch",
    "ko": "Koreanisch",
    "zh": "Chinesisch (vereinfacht)",
    "zh-tw": "Chinesisch (traditionell)",
}

ATTRIBUTE_ALIASES = {
    "DARK": {"dark", "finsternis", "tenebres", "oscuridad", "oscurita", "trevas", "闇", "어둠"},
    "LIGHT": {"light", "licht", "lumiere", "luz", "luce", "光", "빛"},
    "EARTH": {"earth", "erde", "terre", "tierra", "terra", "地", "땅"},
    "WATER": {"water", "wasser", "eau", "agua", "acqua", "水", "물"},
    "FIRE": {"fire", "feuer", "feu", "fuego", "fuoco", "fogo", "炎", "불"},
    "WIND": {"wind", "wind", "vent", "viento", "vento", "風", "바람"},
    "DIVINE": {"divine", "gottlich", "goettlich", "divin", "divino", "神", "신"},
}

FAMILY_ALIASES = {
    "spell": {"spell", "spell card", "zauber", "zauberkarte", "magie", "carta magia", "magia", "魔法", "마법"},
    "trap": {"trap", "trap card", "falle", "fallenkarte", "piege", "trampa", "armadilha", "罠", "함정"},
    "fusion": {"fusion", "fusionsmonster", "fusione", "融合", "융합"},
    "synchro": {"synchro", "synchromonster", "同步", "싱크로"},
    "xyz": {"xyz", "exceed", "エクシーズ", "엑시즈"},
    "link": {"link", "linkmonster", "lien", "enlace", "链接", "リンク", "링크"},
    "ritual": {"ritual", "ritualmonster", "rituel", "rituale", "仪式", "儀式", "의식"},
    "pendulum": {"pendulum", "pendel", "pendule", "pendulo", "pendolo", "灵摆", "ペンデュラム", "펜듈럼"},
    "normal_monster": {"normal monster", "normalmonster", "monstre normal", "monstruo normal", "mostro normale", "通常", "일반 몬스터"},
    "effect_monster": {"effect monster", "effektmonster", "monstre a effet", "monstruo de efecto", "mostro con effetto", "效果", "効果", "효과 몬스터"},
    "monster": {"monster", "monstre", "monstruo", "mostro", "monstro", "モンスター", "怪兽", "몬스터"},
}

RACE_ALIASES = {
    "Dragon": {"dragon", "drache", "ドラゴン", "龙", "龍", "드래곤"},
    "Spellcaster": {"spellcaster", "hexer", "magicien", "lanzador de conjuros", "incantatore", "魔法使い", "魔法师", "마법사"},
    "Warrior": {"warrior", "krieger", "guerrier", "guerrero", "guerriero", "戦士", "战士", "전사"},
    "Machine": {"machine", "maschine", "macchina", "机械", "機械", "기계"},
    "Fiend": {"fiend", "unterweltler", "demon", "demonio", "恶魔", "悪魔", "악마"},
    "Fairy": {"fairy", "fee", "elfe", "hada", "fata", "天使", "천사"},
    "Zombie": {"zombie", "zombi", "アンデット", "不死", "언데드"},
    "Cyberse": {"cyberse", "サイバース", "电子界", "사이버스"},
}


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_set_code(value: Any) -> str:
    raw = re.sub(r"\s+", "", str(value or "").upper()).replace("_", "-").replace("/", "-")
    raw = re.sub(r"-+", "-", raw).strip("-")
    known_langs = "DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|AE|EU|NA"
    if "-" in raw:
        prefix, suffix = raw.split("-", 1)
        prefix = re.sub(r"[^A-Z0-9]", "", prefix)
        suffix = re.sub(r"[^A-Z0-9]", "", suffix)
        match = re.match(rf"^({known_langs})?(\d{{1,4}}[A-Z]?)$", suffix)
        if prefix and match:
            lang, number = match.groups()
            return f"{prefix}-{lang or ''}{number}"
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    # Prefer an explicit language token, which gives an unambiguous split.
    match = re.match(rf"^([A-Z0-9]{{2,10}})({known_langs})(\d{{1,4}}[A-Z]?)$", compact)
    if match:
        prefix, lang, number = match.groups()
        return f"{prefix}-{lang}{number}"
    # Without language the final 2–4 digits are the print number.
    match = re.match(r"^([A-Z0-9]{2,10}?)(\d{2,4}[A-Z]?)$", compact)
    if match:
        prefix, number = match.groups()
        return f"{prefix}-{number}"
    return compact


def set_code_parts(value: Any) -> Tuple[str, str, str]:
    canonical = canonical_set_code(value)
    match = re.match(r"^([A-Z0-9]{2,10})-([A-Z]{2})?(\d{1,4}[A-Z]?)$", canonical)
    if not match:
        return "", "", ""
    return match.group(1), match.group(2) or "", match.group(3)


def strict_set_code_equal(query: Any, actual: Any) -> bool:
    q_prefix, q_lang, q_number = set_code_parts(query)
    a_prefix, a_lang, a_number = set_code_parts(actual)
    if not q_prefix or not a_prefix:
        return False
    if q_prefix != a_prefix or q_number != a_number:
        return False
    # If OCR included a language, it must match the print language. If OCR did
    # not include one, prefix + card number are accepted across localisations.
    return not q_lang or q_lang == a_lang


def language_code_from_set_code(value: Any) -> Optional[str]:
    _prefix, lang, _number = set_code_parts(value)
    if not lang:
        return None
    return SET_LANGUAGE_TO_DB.get(lang)


def language_label(code: Optional[str]) -> str:
    if code is None:
        return "Nicht bestimmt"
    return DB_LANGUAGE_LABELS.get(code, str(code or "Englisch"))


def detect_script_language(text: Any) -> Optional[str]:
    value = str(text or "")
    if re.search(r"[\u3040-\u30ff]", value):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", value):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", value):
        return "zh"
    # Latin language hints from distinctive high-frequency card words.
    normalized = normalize_text(value)
    hints = [
        ("de", ("beschworen", "zauberkarte", "fallenkarte", "friedhof", "spielzug")),
        ("fr", ("invoquez", "cimetiere", "magie", "piege", "detruisez")),
        ("es", ("invoca", "cementerio", "hechizo", "trampa", "destruye")),
        ("it", ("evoca", "cimitero", "magia", "trappola", "distruggi")),
        ("pt", ("invoque", "cemiterio", "magia", "armadilha", "destrua")),
        ("", ("summon", "graveyard", "spell", "trap", "destroy")),
    ]
    scored = [(sum(1 for token in tokens if token in normalized), code) for code, tokens in hints]
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 2:
        return scored[0][1]
    return None


def _extract_int(patterns: Iterable[str], text: str) -> Optional[int]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            raw = str(match.group(1) or "").replace("O", "0").replace("Q", "0")
            if raw in {"?", "X", "∞"}:
                return None
            digits = re.sub(r"\D", "", raw)
            if digits:
                try:
                    return int(digits)
                except Exception:
                    pass
    return None


def extract_scan_metadata(text: Any) -> Dict[str, Any]:
    raw = str(text or "")
    upper = raw.upper()
    normalized = normalize_text(raw)
    metadata: Dict[str, Any] = {}

    metadata["atk"] = _extract_int((r"\bATK\s*[/：:\-]?\s*([0-9OQ]{1,5}|\?)",), upper)
    metadata["def"] = _extract_int((r"\bDEF\s*[/：:\-]?\s*([0-9OQ]{1,5}|\?)",), upper)
    metadata["level"] = _extract_int((
        r"\b(?:LEVEL|STUFE|NIVEAU|NIVEL|LIVELLO|NÍVEL)\s*[/：:\-]?\s*(\d{1,2})\b",
        r"(?:レベル|等级|等級|레벨)\s*(\d{1,2})",
    ), raw)
    metadata["rank"] = _extract_int((
        r"\b(?:RANK|RANG|RANGO)\s*[/：:\-]?\s*(\d{1,2})\b",
        r"(?:ランク|阶级|階級|랭크)\s*(\d{1,2})",
    ), raw)
    metadata["link"] = _extract_int((
        r"\b(?:LINK|LIEN|ENLACE)\s*[-/：:]?\s*(\d{1,2})\b",
        r"(?:リンク|连接|連結|링크)\s*[-/]?\s*(\d{1,2})",
    ), raw)
    metadata["scale"] = _extract_int((
        r"\b(?:SCALE|PENDELSKALA|ECHELLE|ESCALA|SCALA)\s*[/：:\-]?\s*(\d{1,2})\b",
        r"(?:スケール|刻度|스케일)\s*(\d{1,2})",
    ), raw)

    # Attribute and card family detection.
    for attribute, aliases in ATTRIBUTE_ALIASES.items():
        if any(normalize_text(alias) in normalized for alias in aliases):
            metadata["attribute"] = attribute
            break

    family_hits: List[str] = []
    for family, aliases in FAMILY_ALIASES.items():
        if any(normalize_text(alias) in normalized for alias in aliases):
            family_hits.append(family)
    family_priority = ["spell", "trap", "link", "xyz", "synchro", "fusion", "ritual", "pendulum", "normal_monster", "effect_monster", "monster"]
    for family in family_priority:
        if family in family_hits:
            metadata["family"] = family
            break

    for race, aliases in RACE_ALIASES.items():
        if any(normalize_text(alias) in normalized for alias in aliases):
            metadata["race"] = race
            break

    # Set-code language overrides script/text heuristics.
    set_match = re.search(r"\b[A-Z0-9]{2,10}[\s\-_/]*(DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|AE|EU|NA)[\s\-_/]*\d{1,4}\b", upper)
    if set_match:
        metadata["language_hint"] = SET_LANGUAGE_TO_DB.get(set_match.group(1))
    else:
        hint = detect_script_language(raw)
        if hint is not None:
            metadata["language_hint"] = hint

    # Remove unknown numeric fields instead of treating them as hard zeroes.
    for key in ("atk", "def", "level", "rank", "link", "scale"):
        if metadata.get(key) is None:
            metadata.pop(key, None)
    return metadata


def merge_scan_metadata(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for item in items or []:
        payload = item.get("metadata") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if value not in (None, "") and key not in merged:
                merged[key] = value
    return merged


def card_family(card: Dict[str, Any]) -> str:
    ctype = str(card.get("type") or "").lower()
    frame = str(card.get("frameType") or "").lower()
    if "spell" in ctype:
        return "spell"
    if "trap" in ctype:
        return "trap"
    if "link" in ctype:
        return "link"
    if "xyz" in ctype:
        return "xyz"
    if "synchro" in ctype:
        return "synchro"
    if "fusion" in ctype:
        return "fusion"
    if "ritual" in ctype:
        return "ritual"
    if "pendulum" in ctype or "pendulum" in frame or card.get("scale") not in (None, ""):
        return "pendulum"
    if "normal" in ctype:
        return "normal_monster"
    if "monster" in ctype:
        return "effect_monster"
    return "other"


def _numbers_equal(expected: Any, actual: Any) -> bool:
    try:
        return int(expected) == int(actual)
    except Exception:
        return str(expected).strip() == str(actual).strip()


def card_metadata_consistency(card: Dict[str, Any], metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    matches: List[str] = []
    conflicts: List[str] = []
    comparable = 0

    for key, label in (("atk", "ATK"), ("def", "DEF")):
        if key not in metadata:
            continue
        comparable += 1
        actual = card.get(key)
        if actual in (None, ""):
            conflicts.append(f"{label} im Scan, aber nicht bei der Karte")
        elif _numbers_equal(metadata[key], actual):
            matches.append(f"{label} {metadata[key]}")
        else:
            conflicts.append(f"{label} Scan {metadata[key]} ≠ Karte {actual}")

    family = card_family(card)
    numeric_checks = []
    if "link" in metadata:
        numeric_checks.append(("link", "Link", card.get("linkval")))
    if "rank" in metadata:
        numeric_checks.append(("rank", "Rang", card.get("level") if family == "xyz" else None))
    if "level" in metadata:
        numeric_checks.append(("level", "Stufe", card.get("level") if family != "xyz" else None))
    if "scale" in metadata:
        scale_actual = card.get("scale", card.get("pendulumScale", card.get("pendulum_scale")))
        numeric_checks.append(("scale", "Pendel-Skala", scale_actual))
    for key, label, actual in numeric_checks:
        comparable += 1
        if actual in (None, ""):
            conflicts.append(f"{label} im Scan, aber nicht bei der Karte")
        elif _numbers_equal(metadata[key], actual):
            matches.append(f"{label} {metadata[key]}")
        else:
            conflicts.append(f"{label} Scan {metadata[key]} ≠ Karte {actual}")

    expected_family = metadata.get("family")
    if expected_family:
        comparable += 1
        compatible = expected_family == family
        if expected_family == "monster":
            compatible = family not in {"spell", "trap", "other"}
        elif expected_family in {"normal_monster", "effect_monster"} and family == "pendulum":
            # Pendulum monsters may also be normal/effect monsters.
            ctype = str(card.get("type") or "").lower()
            compatible = (expected_family == "normal_monster" and "normal" in ctype) or (expected_family == "effect_monster" and "effect" in ctype)
        if compatible:
            matches.append(f"Kartentyp {family}")
        else:
            conflicts.append(f"Kartentyp Scan {expected_family} ≠ Karte {family}")

    expected_attribute = metadata.get("attribute")
    if expected_attribute:
        comparable += 1
        actual_attribute = str(card.get("attribute") or "").upper()
        if actual_attribute == str(expected_attribute).upper():
            matches.append(f"Attribut {expected_attribute}")
        else:
            conflicts.append(f"Attribut Scan {expected_attribute} ≠ Karte {actual_attribute or '-'}")

    expected_race = metadata.get("race")
    if expected_race:
        comparable += 1
        actual_race = normalize_text(card.get("race") or "")
        if normalize_text(expected_race) == actual_race:
            matches.append(f"Typ {expected_race}")
        else:
            conflicts.append(f"Typ Scan {expected_race} ≠ Karte {card.get('race') or '-'}")

    if comparable == 0:
        score = 0.5
    else:
        score = max(0.0, min(1.0, (len(matches) - len(conflicts) * 1.35 + comparable) / (2.0 * comparable)))
    severe = len(conflicts) >= 2 or (len(conflicts) >= 1 and comparable <= 2 and not matches)
    return {
        "score": round(score, 4),
        "matches": matches,
        "conflicts": conflicts,
        "comparable": comparable,
        "severe_conflict": severe,
    }


def exact_set_item_for_code(card: Dict[str, Any], query: Any) -> Optional[Dict[str, Any]]:
    for item in card.get("card_sets") or []:
        if isinstance(item, dict) and strict_set_code_equal(query, item.get("set_code")):
            return item
    return None


def identifier_stage(kind: Any) -> int:
    return {"Set-Code": 0, "Passcode": 1, "Name": 2, "Effect": 3, "Artwork": 4}.get(str(kind or ""), 9)
