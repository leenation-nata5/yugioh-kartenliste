# -*- coding: utf-8 -*-
"""Release packaging, documentation and CI contracts for v12."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    assert sorted(path.name for path in ROOT.glob("CHANGELOG_v*.txt")) == ["CHANGELOG_v12_0_0.txt"]
    required = (
        "README.md",
        "CHANGELOG_v12_0_0.txt",
        "UI_V120_DESIGN.md",
        "docs/OFFLINE_DELTA_PACK_V120.md",
        "docs/TESTMATRIX_V120.md",
        "docs/DATENSCHUTZ_V120.md",
        "tests/fixtures/scan_corpus/manifest.example.json",
        "scripts/scan_benchmark_v120.py",
        "assets/ui/scanner_surface_v120.webp",
    )
    for name in required:
        path = ROOT / name
        assert path.is_file() and path.stat().st_size > 0, name

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    for fragment in (
        "build_aab:",
        "android.release_artifact = aab",
        "jarsigner",
        "tests/test_v120_core_contract.py",
        "tests/test_v120_responsive_fuzz.py",
        "tests/test_v120_android_scanner_contract.py",
        "tests/test_v120_release_contract.py",
        "kivy/buildozer@sha256:",
        "just-incard-v1200-arm64-api35-ndk27c",
    ):
        assert fragment in workflow, fragment

    preflight = (ROOT / "preflight_check.py").read_text(encoding="utf-8")
    for fragment in (
        "ui_v120.py",
        "features_v120.py",
        "data_packs_v120.py",
        "scanner_surface_v120.webp",
        "SecureSecretStore.java",
        "SecureBackupCipher.java",
        "CHANGELOG_v12_0_0.txt",
    ):
        assert fragment in preflight, fragment
    integrity = json.loads((ROOT / "security_integrity_manifest.json").read_text(encoding="utf-8"))
    protected = set(integrity.get("files") or {})
    assert "features_v120.py" in protected
    assert "data_packs_v120.py" in protected
    assert "assets/ui/scanner_surface_v120.webp" in protected

    # Python deletes ``except ... as exc`` variables when the block ends. A
    # delayed Clock lambda must therefore capture the message in a default.
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(main_source)
    unsafe_callbacks = []
    for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler) and node.name):
        for callback in (node for node in ast.walk(handler) if isinstance(node, ast.Lambda)):
            used = {node.id for node in ast.walk(callback.body) if isinstance(node, ast.Name)}
            if handler.name in used:
                unsafe_callbacks.append((handler.lineno, callback.lineno, handler.name))
    assert unsafe_callbacks == [], unsafe_callbacks
    assert main_source.count("self.app_db.checkpoint()") >= 3
    print("v12.0.0 release/documentation/CI contract tests: OK")


if __name__ == "__main__":
    run()
