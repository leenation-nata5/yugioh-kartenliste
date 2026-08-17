# -*- coding: utf-8 -*-
"""python-for-android hook for Just InCard v12.0.1.

The Buildozer option ``android.extra_manifest_application_arguments`` writes
*attributes* into the opening <application ...> tag. It must not contain child
XML such as <activity>. This hook runs after p4a generated the Gradle project
and before Gradle starts, then inserts CameraXScanActivity as a real child of
<application> and validates the resulting XML.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ACTIVITY_NAME = "org.yugioh.kartenliste.CameraXScanActivity"
PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_PATH = PROJECT_ROOT / "logs" / "manifest_hook_report.json"

ET.register_namespace("android", ANDROID_NS)


def _android_attr(name: str) -> str:
    return f"{{{ANDROID_NS}}}{name}"


def _find_manifest() -> Path:
    candidates = [
        Path.cwd() / "src" / "main" / "AndroidManifest.xml",
        Path.cwd() / "AndroidManifest.xml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = sorted(Path.cwd().glob("**/src/main/AndroidManifest.xml"))
    if found:
        return found[0]
    raise FileNotFoundError(
        "Generated AndroidManifest.xml not found under " + str(Path.cwd())
    )


def _write_report(payload: dict) -> None:
    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _patch_manifest(manifest_path: Path) -> dict:
    raw_before = manifest_path.read_text(encoding="utf-8")
    if "extra_manifest_application_arguments" in raw_before:
        raise RuntimeError("Unexpected Buildozer placeholder remained in manifest")

    tree = ET.parse(manifest_path)
    root = tree.getroot()
    if root.tag != "manifest":
        raise RuntimeError(f"Unexpected manifest root: {root.tag!r}")

    application = root.find("application")
    if application is None:
        raise RuntimeError("Android manifest has no <application> element")

    removed = 0
    for activity in list(application.findall("activity")):
        name = activity.get(_android_attr("name"), "")
        if name in {ACTIVITY_NAME, ".CameraXScanActivity"}:
            application.remove(activity)
            removed += 1

    activity = ET.SubElement(application, "activity")
    activity.set(_android_attr("name"), ACTIVITY_NAME)
    activity.set(_android_attr("exported"), "false")
    activity.set(_android_attr("screenOrientation"), "fullSensor")
    activity.set(
        _android_attr("theme"),
        "@style/Theme.AppCompat.DayNight.NoActionBar",
    )

    tree.write(
        manifest_path,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )

    # Parse the final file again so malformed output fails before Gradle.
    final_tree = ET.parse(manifest_path)
    final_app = final_tree.getroot().find("application")
    matches = [] if final_app is None else [
        item for item in final_app.findall("activity")
        if item.get(_android_attr("name")) == ACTIVITY_NAME
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"CameraXScanActivity insertion failed: expected 1, got {len(matches)}"
        )

    return {
        "ok": True,
        "manifest": str(manifest_path),
        "activity": ACTIVITY_NAME,
        "removed_previous_entries": removed,
        "final_activity_count": len(matches),
        "size_bytes": manifest_path.stat().st_size,
    }



GRADLE_MEMORY_PROPERTIES = {
    "org.gradle.jvmargs": "-Xms512m -Xmx4096m -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8 -XX:+HeapDumpOnOutOfMemoryError",
    "org.gradle.workers.max": "2",
    "org.gradle.parallel": "false",
    "org.gradle.daemon": "false",
    "org.gradle.vfs.watch": "false",
    "android.useAndroidX": "true",
    "android.enableJetifier": "true",
}


def _patch_gradle_properties(dist_root: Path) -> dict:
    """Give Gradle enough memory for large Android AAR transforms.

    Build #36 showed Gradle 8.14.3 starting with only -Xmx512m and then
    failing while Jetifier read opencv-4.12.0.aar.  We patch the generated
    distribution directly because it is the project Gradle actually executes.
    Existing unrelated properties are preserved.
    """
    props_path = dist_root / "gradle.properties"
    existing_lines = []
    if props_path.is_file():
        existing_lines = props_path.read_text(encoding="utf-8").splitlines()

    managed = set(GRADLE_MEMORY_PROPERTIES)
    kept = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            kept.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key not in managed:
            kept.append(line)

    if kept and kept[-1].strip():
        kept.append("")
    kept.append("# Just InCard v12.0.1: GitHub/OpenCV Gradle memory hotfix")
    for key, value in GRADLE_MEMORY_PROPERTIES.items():
        kept.append(f"{key}={value}")
    props_path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")

    final = props_path.read_text(encoding="utf-8")
    required = [
        "-Xmx4096m",
        "-XX:MaxMetaspaceSize=1024m",
        "org.gradle.workers.max=2",
        "org.gradle.parallel=false",
        "android.useAndroidX=true",
        "android.enableJetifier=true",
    ]
    missing = [item for item in required if item not in final]
    if missing:
        raise RuntimeError("Gradle memory configuration incomplete: " + ", ".join(missing))

    return {
        "gradle_properties": str(props_path),
        "gradle_heap_mb": 4096,
        "gradle_metaspace_mb": 1024,
        "gradle_workers_max": 2,
        "gradle_parallel": False,
        "jetifier": True,
        "gradle_properties_size_bytes": props_path.stat().st_size,
    }

def after_apk_build(toolchain) -> None:
    """Called by p4a after project generation and before Gradle assembly."""
    manifest_path = _find_manifest()
    dist_root = manifest_path.parents[2]
    try:
        report = _patch_manifest(manifest_path)
        report.update(_patch_gradle_properties(dist_root))
    except Exception as exc:
        report = {
            "ok": False,
            "manifest": str(manifest_path),
            "error": f"{type(exc).__name__}: {exc}",
        }
        _write_report(report)
        raise
    _write_report(report)
    print(
        "Just InCard p4a hook: manifest valid; Gradle heap=4096 MB, "
        "metaspace=1024 MB, workers=2: " + str(dist_root)
    )
