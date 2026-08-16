# -*- coding: utf-8 -*-
"""Optionale OCR-Adapter für Just InCard v11.2.2.

Die Adapter sind absichtlich nicht verpflichtend. Sie werden genutzt, wenn die
entsprechenden Python-Pakete in einer Desktop-/Server-Umgebung installiert sind.
Der Android-Core bleibt davon unabhängig.
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_LOCK = threading.RLock()
_EASY_READERS: Dict[Tuple[str, ...], Any] = {}
_PADDLE_READERS: Dict[str, Any] = {}


def easyocr_available() -> bool:
    return importlib.util.find_spec("easyocr") is not None


def paddleocr_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def _easy_reader(languages: Sequence[str]):
    key = tuple(languages or ("en",))
    with _LOCK:
        if key not in _EASY_READERS:
            import easyocr
            _EASY_READERS[key] = easyocr.Reader(list(key), gpu=False, verbose=False)
        return _EASY_READERS[key]


def easyocr_read(path: str, languages: Sequence[str] = ("en", "de")) -> str:
    if not easyocr_available():
        return ""
    reader = _easy_reader(languages)
    result = reader.readtext(str(path), detail=1, paragraph=False)
    lines: List[Tuple[float, str]] = []
    for item in result or []:
        try:
            text = str(item[1] or "").strip()
            confidence = float(item[2] or 0.0)
        except Exception:
            continue
        if text:
            lines.append((confidence, text))
    lines.sort(key=lambda item: item[0], reverse=True)
    return "\n".join(text for _confidence, text in lines)


def _paddle_reader(language: str = "en"):
    key = str(language or "en")
    with _LOCK:
        if key not in _PADDLE_READERS:
            from paddleocr import PaddleOCR
            try:
                reader = PaddleOCR(
                    lang=key,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=True,
                )
            except TypeError:
                reader = PaddleOCR(lang=key, use_angle_cls=True, show_log=False)
            _PADDLE_READERS[key] = reader
        return _PADDLE_READERS[key]


def paddleocr_read(path: str, language: str = "en") -> str:
    if not paddleocr_available():
        return ""
    reader = _paddle_reader(language)
    try:
        result = reader.predict(str(path))
    except Exception:
        result = reader.ocr(str(path), cls=True)
    texts: List[str] = []
    for page in result or []:
        # PaddleOCR 3.x result object
        if hasattr(page, "json"):
            try:
                payload = page.json
                if callable(payload):
                    payload = payload()
                rec_texts = (payload or {}).get("res", {}).get("rec_texts", [])
                texts.extend(str(value).strip() for value in rec_texts if str(value).strip())
                continue
            except Exception:
                pass
        # PaddleOCR 2.x nested list
        rows = page if isinstance(page, list) else []
        for row in rows:
            try:
                value = str(row[1][0] or "").strip()
            except Exception:
                continue
            if value:
                texts.append(value)
    return "\n".join(texts)


def optional_ocr_bundle(path: str, *, languages: Sequence[str] = ("en", "de")) -> Dict[str, str]:
    output: Dict[str, str] = {}
    if easyocr_available():
        try:
            output["easyocr"] = easyocr_read(path, languages=languages)
        except Exception as exc:
            output["easyocr_error"] = str(exc)
    if paddleocr_available():
        for language in languages[:3]:
            try:
                text = paddleocr_read(path, language=language)
                if text:
                    output[f"paddleocr_{language}"] = text
            except Exception as exc:
                output[f"paddleocr_{language}_error"] = str(exc)
    return output
