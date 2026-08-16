#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bereitet optionale lokale KI-Modellpakete für Just InCard v12.0.0 vor.

Der stabile APK-Core benötigt keinen erfolgreichen Download. Ohne Zusatzpaket
bleiben ML Kit, OpenCV, die bestehende Bildvorverarbeitung und die lokale
Datenbanksuche aktiv. ``--extended`` ergänzt YOLO, PaddleOCR und MiniLM.
``--strict`` lässt Download- oder Prüffehler den Aufruf abbrechen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"

CORE_ASSETS: List[Dict[str, Any]] = [
    {
        "id": "mobilenet_v3_embedder",
        "url": "https://storage.googleapis.com/mediapipe-tasks/image_embedder/mobilenet_v3_small_075_224_embedder.tflite",
        "path": "mobilenet_v3_small_075_224_embedder.tflite",
        "min_size": 3_500_000,
        "required": False,
    },
]

EXTENDED_ASSETS: List[Dict[str, Any]] = [
    {
        "id": "yolo_card_detector",
        "url": "https://huggingface.co/Adrihp06/TCGscanner-detector/resolve/main/riftbound_regions.onnx?download=true",
        "path": "yolo_card_detector.onnx",
        "sha256": "8566d3c8556183c780eab0937f65d9862bdfc57697bfd3c33135218f28230f41",
        "required": False,
        "license_note": "Externes TCG-Modell; Lizenz vor öffentlicher Weiterverteilung separat prüfen.",
    },
    {
        "id": "paddle_det",
        "url": "https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx/resolve/main/inference.onnx?download=true",
        "path": "paddleocr/det/inference.onnx",
        "sha256": "a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d",
        "required": False,
    },
    {
        "id": "paddle_latin_rec",
        "url": "https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec_onnx/resolve/main/inference.onnx?download=true",
        "path": "paddleocr/rec_latin/inference.onnx",
        "sha256": "7888113072263cb471b93f66dd5e2ad70548dc526fa1ace760d0d973dd121498",
        "required": False,
    },
    {
        "id": "paddle_latin_dict",
        "url": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/dict/ppocrv5_latin_dict.txt",
        "path": "paddleocr/rec_latin/ppocrv5_latin_dict.vocab",
        "min_size": 2000,
        "required": False,
    },
    {
        "id": "minilm_quantized",
        "url": "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx?download=true",
        "path": "minilm/model_quantized.onnx",
        "sha256": "afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1",
        "required": False,
    },
    {
        "id": "minilm_vocab",
        "url": "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/vocab.txt?download=true",
        "path": "minilm/minilm.vocab",
        "min_size": 100_000,
        "required": False,
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_asset(path: Path, asset: Dict[str, Any]) -> bool:
    if not path.is_file():
        return False
    expected = str(asset.get("sha256") or "").lower().strip()
    if expected:
        return sha256(path).lower() == expected
    minimum = int(asset.get("min_size") or 1)
    return path.stat().st_size >= minimum


def download(asset: Dict[str, Any], *, strict: bool = False) -> Dict[str, Any]:
    target = MODELS / str(asset["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if validate_asset(target, asset):
        return {
            "id": asset["id"],
            "status": "cached",
            "path": str(target.relative_to(ROOT)),
            "sha256": sha256(target),
        }

    temporary = target.with_suffix(target.suffix + ".download")
    try:
        request = urllib.request.Request(
            str(asset["url"]),
            headers={"User-Agent": "JustInCard/12.0.0 (leenation)"},
        )
        with urllib.request.urlopen(request, timeout=240) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if not validate_asset(temporary, asset):
            raise RuntimeError("Größe oder SHA-256 des Modells stimmt nicht")
        temporary.replace(target)
        return {
            "id": asset["id"],
            "status": "downloaded",
            "path": str(target.relative_to(ROOT)),
            "sha256": sha256(target),
        }
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if strict or bool(asset.get("required")):
            raise
        return {
            "id": asset["id"],
            "status": "failed",
            "error": str(exc),
            "optional": True,
        }


def prepare(assets: Iterable[Dict[str, Any]], *, strict: bool = False) -> List[Dict[str, Any]]:
    return [download(asset, strict=strict) for asset in assets]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extended", action="store_true", help="YOLO, PaddleOCR und MiniLM zusätzlich laden")
    parser.add_argument("--strict", action="store_true", help="Bei einem fehlgeschlagenen Modell abbrechen")
    args = parser.parse_args()

    MODELS.mkdir(parents=True, exist_ok=True)
    selected = list(CORE_ASSETS)
    if args.extended:
        selected.extend(EXTENDED_ASSETS)
    results = prepare(selected, strict=args.strict)
    report = {
        "version": "12.0.0",
        "developer": "leenation",
        "extended": bool(args.extended),
        "results": results,
    }
    report_path = MODELS / "model_prepare_report_v109.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failed = [item for item in results if item.get("status") == "failed"]
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
