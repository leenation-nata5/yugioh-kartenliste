# -*- coding: utf-8 -*-
"""Manifest-/Gradle-Hotfix-Vertrag für Just InCard v11.0."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ANDROID_NS = "http://schemas.android.com/apk/res/android"


def run():
    from app_version import APP_VERSION, APP_BUILD
    assert APP_VERSION == "11.3.0"
    assert APP_BUILD == 1130

    spec_text = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert "p4a.hook = p4a_manifest_hook.py" in spec_text
    assert "android.extra_manifest_application_arguments" not in spec_text
    assert not (ROOT / "android_application_extra.xml").exists()

    hook_path = ROOT / "p4a_manifest_hook.py"
    module_spec = importlib.util.spec_from_file_location("p4a_manifest_hook", hook_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec and module_spec.loader
    module_spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory() as temp_dir:
        manifest = Path(temp_dir) / "AndroidManifest.xml"
        manifest.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.yugioh.kartenliste.yugiohkartenliste">
  <application android:label="Just InCard">
    <activity android:name="org.kivy.android.PythonActivity" />
  </application>
</manifest>
""",
            encoding="utf-8",
        )
        report = module._patch_manifest(manifest)
        assert report["ok"] is True
        assert report["final_activity_count"] == 1

        # A second run must not create a duplicate.
        second = module._patch_manifest(manifest)
        assert second["final_activity_count"] == 1
        assert second["removed_previous_entries"] == 1

        tree = ET.parse(manifest)
        app = tree.getroot().find("application")
        assert app is not None
        activities = [
            item for item in app.findall("activity")
            if item.get(f"{{{ANDROID_NS}}}name") == module.ACTIVITY_NAME
        ]
        assert len(activities) == 1
        activity = activities[0]
        assert activity.get(f"{{{ANDROID_NS}}}exported") == "false"
        assert activity.get(f"{{{ANDROID_NS}}}screenOrientation") == "fullSensor"

    workflow = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    assert "tests/test_v1093_manifest_hook_contract.py" in workflow
    assert "gradle_failure_section.log" in workflow
    assert "manifest_hook_report.json" in workflow

    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    assert txt_files == ["CHANGELOG_v11_3_0.txt"], txt_files
    print("v11.3.0 manifest hook/Gradle build contract tests: OK")


if __name__ == "__main__":
    run()
