# -*- coding: utf-8 -*-
"""Best-Effort-Schutz für Just InCard v11.2.

Programmierer / Administrator: leenation

Wichtig: Eine Android-APK kann technisch niemals so verschlüsselt werden, dass
Code mit absoluter Sicherheit nicht analysiert werden kann. Diese Datei ergänzt
Integritätsprüfungen, Build-Metadaten und eine klare Härtungsstrategie.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

DEVELOPER_NAME = "leenation"
ADMIN_NAME = "leenation"
SECURITY_MODEL = "signed-release + integrity-manifest + stripped-symbols + best-effort-obfuscation"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_integrity_manifest(root_dir: str, manifest_path: str) -> Dict[str, Any]:
    result = {"ok": True, "checked": 0, "missing": [], "changed": [], "developer": DEVELOPER_NAME}
    try:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception as exc:
        result.update({"ok": False, "error": str(exc)})
        return result
    root = Path(root_dir)
    for relative, expected in dict(payload.get("files") or {}).items():
        path = root / relative
        if not path.is_file():
            result["missing"].append(relative)
            continue
        result["checked"] += 1
        try:
            if sha256_file(str(path)) != str(expected):
                result["changed"].append(relative)
        except Exception:
            result["changed"].append(relative)
    result["ok"] = not result["missing"] and not result["changed"]
    return result


def build_security_metadata(version: str, build: int) -> Dict[str, Any]:
    return {
        "version": str(version),
        "build": int(build),
        "developer": DEVELOPER_NAME,
        "admin": ADMIN_NAME,
        "security_model": SECURITY_MODEL,
        "limitations": "Absolute Unlesbarkeit oder vollständiger Schutz vor Reverse Engineering ist technisch nicht garantierbar.",
    }
