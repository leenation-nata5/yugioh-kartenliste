# -*- coding: utf-8 -*-
"""Regressionstest für den Gradle/OpenCV-Speicher-Hotfix in Just InCard v11.2."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from app_version import APP_VERSION, APP_BUILD

    assert APP_VERSION == "11.2"
    assert APP_BUILD == 1120

    hook_path = ROOT / "p4a_manifest_hook.py"
    module_spec = importlib.util.spec_from_file_location("p4a_manifest_hook_v1102", hook_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec and module_spec.loader
    module_spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory() as temp_dir:
        dist = Path(temp_dir)
        # Simulate p4a defaults/other properties and verify unrelated values survive.
        (dist / "gradle.properties").write_text(
            "org.gradle.jvmargs=-Xmx512m\n"
            "org.gradle.workers.max=8\n"
            "android.useAndroidX=true\n"
            "custom.justincard.property=keep-me\n",
            encoding="utf-8",
        )
        report = module._patch_gradle_properties(dist)
        props = (dist / "gradle.properties").read_text(encoding="utf-8")
        assert report["gradle_heap_mb"] == 4096
        assert report["gradle_metaspace_mb"] == 1024
        assert report["gradle_workers_max"] == 2
        assert "-Xmx4096m" in props
        assert "-XX:MaxMetaspaceSize=1024m" in props
        assert "org.gradle.workers.max=2" in props
        assert "org.gradle.parallel=false" in props
        assert "org.gradle.daemon=false" in props
        assert "android.useAndroidX=true" in props
        assert "android.enableJetifier=true" in props
        assert "custom.justincard.property=keep-me" in props
        assert "-Xmx512m" not in props
        assert "org.gradle.workers.max=8" not in props

    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert re.search(r"^version\s*=\s*11\.2\s*$", spec, re.M)
    assert "android.numeric_version = 1120" in spec
    assert "org.opencv:opencv:4.12.0" in spec
    assert "just-incard-v112-arm64-api35-ndk25b" in workflow
    assert "tests/test_v1102_gradle_memory_contract.py" in workflow
    assert "runner_memory_before_build.log" in workflow
    assert "gradle_properties_effective.log" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_2.txt"], txt_files
    print("v11.2 Gradle/OpenCV memory hotfix contract tests: OK")


if __name__ == "__main__":
    run()
