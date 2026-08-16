# -*- coding: utf-8 -*-
"""Erzeugt Build-Integritätsdaten für Just InCard.

Programmierer / Administrator: leenation

Die Härtung ist Best Effort. Sie ersetzt keine Signierung und kann Reverse
Engineering nicht absolut verhindern.
"""
from __future__ import annotations

import json
from pathlib import Path

from app_version import APP_BUILD, APP_VERSION, APP_DEVELOPER, APP_ADMIN
from features_v104 import create_integrity_manifest
from security_v104 import build_security_metadata

ROOT = Path(__file__).resolve().parent


def main() -> int:
    integrity_path = ROOT / "security_integrity_manifest.json"
    metadata_path = ROOT / "security_build_metadata.json"
    create_integrity_manifest(
        str(ROOT),
        str(integrity_path),
        include_exts=(
            ".py", ".json", ".png", ".jpg", ".jpeg", ".webp", ".kv",
            ".tflite", ".task", ".onnx", ".vocab",
        ),
    )
    metadata = build_security_metadata(APP_VERSION, APP_BUILD)
    metadata.update({"developer": APP_DEVELOPER, "admin": APP_ADMIN})
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Integritätsmanifest: {integrity_path.name}")
    print(f"Security-Metadaten: {metadata_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
