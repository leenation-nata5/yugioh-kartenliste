# -*- coding: utf-8 -*-
"""Schnelle Projektprüfung vor dem lang laufenden Android-Build."""
from __future__ import annotations

import ast
import configparser
import hashlib
import importlib.util
import json
import os
import py_compile
import re
import sys
from pathlib import Path

EXPECTED_VERSION = "11.2.3"
ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "logs"
REPORT_DIR.mkdir(exist_ok=True)

ERRORS = []
WARNINGS = []
OK = []


def ok(message):
    OK.append(str(message))


def warn(message):
    WARNINGS.append(str(message))


def error(message):
    ERRORS.append(str(message))


def check_required_files():
    required = [
        "main.py", "ui_v110.py", "app_version.py", "storage_v91.py", "features_v93.py", "features_v97.py", "features_v104.py", "security_v104.py", "prepare_release_hardening.py", "prepare_ai_models_v109.py", "scanner_v100.py", "scanner_v108.py", "ai_scanner_v102.py", "ai_ensemble_v109.py", "gallery_multiengine_v1091.py", "native_ai_bridge_v109.py", "optional_ocr_v109.py", "deck_ai_v102.py", "p4a_manifest_hook.py", "buildozer.spec",
        "app_logo.png", "app_logo_transparent.png", "app_icon.png", "preview_placeholder.png",
        "presplash.png", "just_incard_local_seed.json", "just_incard_source_registry.json",
        ".github/workflows/build-android-apk.yml",
        "tests/test_v96_ui_contract.py", "tests/test_v97_core.py", "tests/test_v97_ui_contract.py", "tests/test_v100_scanner_contract.py", "tests/test_v101_ai_scanner_contract.py", "tests/test_v102_max_ai_contract.py", "tests/test_v104_features_contract.py", "tests/test_v107_isolated_gallery_contract.py", "tests/test_v108_strict_scanner_contract.py", "tests/test_v1081_startup_transition_contract.py", "tests/test_v109_multiengine_ai_contract.py", "tests/test_v1091_gallery_multiengine_contract.py", "tests/test_v1092_gradle_build_contract.py", "tests/test_v1093_manifest_hook_contract.py", "tests/test_v110_responsive_contract.py", "tests/test_v110_ui_contract.py", "tests/test_v1101_java_hotfix_contract.py", "tests/test_v1102_gradle_memory_contract.py", "tests/test_v112_scanner_ui_contract.py", "tests/test_v1123_ci_legacy_contract_hotfix.py", "tests/test_v1123_repository_overlay_contract.py", "tests/test_v1123_p4a_android_wheel_contract.py", "models/ai_models_manifest.json", "android_src/org/yugioh/kartenliste/NativeAiScanner.java", "ci/justincard-ci-test.keystore", "ci/patch_p4a_android_wheels.py", "assets/ui/app_mark.png",
        "assets/ui/search.png", "assets/ui/scan.png", "assets/ui/cards.png",
        "assets/ui/decks.png", "assets/ui/more.png",
    ]
    for name in required:
        path = ROOT / name
        if not path.is_file():
            error(f"Pflichtdatei fehlt: {name}")
        elif path.stat().st_size <= 0:
            error(f"Pflichtdatei ist leer: {name}")
        else:
            ok(f"Datei vorhanden: {name}")


def check_python():
    python_files = sorted(ROOT.glob("*.py"))
    for path in python_files:
        try:
            py_compile.compile(str(path), doraise=True)
            ok(f"Python-Syntax: {path.name}")
        except Exception as exc:
            error(f"Python-Syntaxfehler in {path.name}: {exc}")

    for module_name in ("app_version", "storage_v91", "features_v93", "features_v97", "features_v104", "security_v104", "scanner_v100", "scanner_v108", "ai_scanner_v102", "ai_ensemble_v109", "gallery_multiengine_v1091", "native_ai_bridge_v109", "optional_ocr_v109", "deck_ai_v102", "ui_v110"):
        path = ROOT / f"{module_name}.py"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            ok(f"Modul importierbar: {module_name}")
        except Exception as exc:
            error(f"Modul kann nicht importiert werden: {module_name}: {exc}")


def check_main_ast():
    path = ROOT / "main.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        error(f"main.py konnte nicht analysiert werden: {exc}")
        return

    app_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "YuGiOhApp":
            app_class = node
            break
    if app_class is None:
        error("Klasse YuGiOhApp fehlt")
        return

    methods = {node.name for node in app_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required_methods = {
        "build", "rebuild_interface", "apply_responsive_layout", "make_popup", "show_home_page",
        "open_camera_scanner", "open_collection_popup", "open_decks_popup",
        "open_settings_popup", "open_diagnostics_popup", "open_collection_dashboard",
        "open_set_progress_popup", "start_bulk_gallery_ocr_import", "open_unified_gallery_scan",
        "save_session_state", "restore_session_state", "import_backup_zip",
        "open_cache_management_popup", "open_accessibility_popup",
        "open_collection_metadata_editor", "open_duplicate_variant_center", "open_scan_review_center",
        "open_scanner_statistics_v104", "open_deck_test_hand_popup", "open_deck_explanation_popup",
        "open_offline_status_popup", "open_privacy_controls_popup", "open_automatic_backups_popup",
        "open_device_layout_info", "export_diagnostics_package_v104", "apply_runtime_layout_guard_v110",
        "get_android_device_display_name", "ensure_first_launch_welcome_then_permissions",
    }
    for name in sorted(required_methods):
        if name not in methods:
            error(f"Erforderliche App-Methode fehlt: {name}")
        else:
            ok(f"App-Methode vorhanden: {name}")

    defined = methods | {"show_info", "show_error"}
    ignored_prefixes = {"setter", "get_running_app"}
    suspicious = set()
    for node in ast.walk(app_class):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == "self":
                name = node.func.attr
                if name.startswith("_") or name in defined or name in ignored_prefixes:
                    continue
                # Kivy/App-Basismethoden und dynamische Attribute nicht pauschal als Fehler behandeln.
                if name in {"stop", "run", "get_running_app"}:
                    continue
                suspicious.add(name)
    if suspicious:
        warn("Dynamische/ererbte self-Aufrufe geprüft: " + ", ".join(sorted(suspicious)[:80]))


def check_version_consistency():
    try:
        from app_version import APP_VERSION as central_version, APP_BUILD
    except Exception as exc:
        error(f"Zentrale Version kann nicht importiert werden: {exc}")
        return
    spec_text = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*([^\s#]+)', spec_text, re.M)
    spec_version = match.group(1) if match else ""
    if central_version != EXPECTED_VERSION:
        error(f"Versionskonflikt: app_version.py meldet {central_version!r}, erwartet {EXPECTED_VERSION}")
    else:
        ok(f"Zentrale Version korrekt: {central_version} (Build {APP_BUILD})")
    if spec_version != EXPECTED_VERSION:
        error(f"Versionskonflikt: buildozer.spec meldet {spec_version!r}, erwartet {EXPECTED_VERSION}")
    else:
        ok(f"Buildozer-Version korrekt: {spec_version}")
    required_fragments = [
        "from app_version import APP_VERSION", "actions/checkout@v4",
        "actions/cache@v4", "actions/upload-artifact@v4",
        "android debug", "android release", "apksigner", "tests/test_v100_scanner_contract.py", "tests/test_v101_ai_scanner_contract.py", "tests/test_v102_max_ai_contract.py", "tests/test_v104_features_contract.py", "tests/test_v107_isolated_gallery_contract.py", "tests/test_v108_strict_scanner_contract.py", "tests/test_v1081_startup_transition_contract.py", "tests/test_v109_multiengine_ai_contract.py", "tests/test_v1091_gallery_multiengine_contract.py", "tests/test_v1092_gradle_build_contract.py", "tests/test_v1093_manifest_hook_contract.py", "tests/test_v110_responsive_contract.py", "tests/test_v110_ui_contract.py", "tests/test_v1101_java_hotfix_contract.py", "tests/test_v1102_gradle_memory_contract.py", "tests/test_v112_scanner_ui_contract.py", "tests/test_v1123_ci_legacy_contract_hotfix.py", "tests/test_v1123_repository_overlay_contract.py", "tests/test_v1123_p4a_android_wheel_contract.py", "ci/patch_p4a_android_wheels.py", "python-for-android vorladen", "Android-Wheel-Staging-Hotfix anwenden", "not a supported wheel", "Alte Versionsdateien aus Overlay-Upload bereinigen", "prepare_ai_models_v109.py --extended",
    ]
    for fragment in required_fragments:
        if fragment not in workflow_text:
            error(f"Workflow-Bestandteil fehlt: {fragment}")
        else:
            ok(f"Workflow-Bestandteil vorhanden: {fragment}")


def check_buildozer_spec():
    text = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github/workflows/build-android-apk.yml").read_text(encoding="utf-8")
    req_match = re.search(r"^requirements\s*=\s*(.+)$", text, re.M)
    requirements = {part.strip().lower() for part in (req_match.group(1).split(",") if req_match else [])}
    required = {"python3", "kivy", "openssl", "certifi", "pyjnius", "plyer", "pillow"}
    missing = sorted(required - requirements)
    if missing:
        error("Buildozer-Abhängigkeiten fehlen: " + ", ".join(missing))
    else:
        ok("Buildozer-Abhängigkeiten vollständig")

    dependencies = (
        "com.google.mlkit:text-recognition:16.0.1",
        "com.google.mlkit:text-recognition-chinese:16.0.1",
        "com.google.mlkit:text-recognition-japanese:16.0.1",
        "com.google.mlkit:text-recognition-korean:16.0.1",
        "com.google.mlkit:text-recognition-devanagari:16.0.1",
        "com.google.mediapipe:tasks-vision:0.10.35",
        "org.opencv:opencv:4.12.0",
        "com.microsoft.onnxruntime:onnxruntime-android:1.21.1",
    )
    for dependency in dependencies:
        if dependency not in text:
            error(f"KI-Android-Abhängigkeit fehlt: {dependency}")
        else:
            ok(f"KI-Android-Abhängigkeit vorhanden: {dependency}")

    if "org.tensorflow:tensorflow-lite-task-vision" in text:
        error("Redundante TensorFlow-Lite-Task-Vision-Abhängigkeit muss entfernt sein")
    else:
        ok("Redundante TensorFlow-Lite-Task-Vision-Abhängigkeit entfernt")
    for fragment in (
        "pickFirst 'lib/**/libc++_shared.so'",
        "sourceCompatibility = 1.8",
        "targetCompatibility = 1.8",
        "android.numeric_version = 1123",
    ):
        if fragment not in text:
            error(f"Gradle-Kompatibilitätskonfiguration fehlt: {fragment}")
        else:
            ok(f"Gradle-Kompatibilitätskonfiguration vorhanden: {fragment}")

    for token in (
        "android.add_src = android_src",
        "android.extra_manifest_xml = android_manifest_extra.xml",
        "p4a.hook = p4a_manifest_hook.py",
    ):
        if token not in text:
            error(f"Native Android-Konfiguration fehlt: {token}")
        else:
            ok(f"Native Android-Konfiguration vorhanden: {token}")

    if "android.extra_manifest_application_arguments" in text:
        error("CameraX-Aktivität darf nicht als application-Attribut eingebunden werden")
    else:
        ok("Fehlerhafte extra_manifest_application_arguments-Konfiguration entfernt")
    if (ROOT / "android_application_extra.xml").exists():
        error("Veraltete android_application_extra.xml muss entfernt sein")
    else:
        ok("Veraltete android_application_extra.xml entfernt")

    hook_text = (ROOT / "p4a_manifest_hook.py").read_text(encoding="utf-8")
    for fragment in (
        "def after_apk_build",
        "CameraXScanActivity",
        "ET.parse(manifest_path)",
        "final_activity_count",
    ):
        if fragment not in hook_text:
            error(f"Manifest-Hook unvollständig: {fragment}")
        else:
            ok(f"Manifest-Hook enthält: {fragment}")

    # v11.2.3: Build #36 startete Gradle nur mit -Xmx512m und lief beim
    # JetifyTransform von opencv-4.12.0.aar in java.lang.OutOfMemoryError.
    for fragment in (
        "def _patch_gradle_properties",
        "-Xmx4096m",
        "-XX:MaxMetaspaceSize=1024m",
        '"org.gradle.workers.max": "2"',
        '"org.gradle.parallel": "false"',
        '"android.enableJetifier": "true"',
    ):
        if fragment not in hook_text:
            error(f"Gradle-Speicher-Hotfix fehlt: {fragment}")
        else:
            ok(f"Gradle-Speicher-Hotfix vorhanden: {fragment}")

    for fragment in (
        "tests/test_v1102_gradle_memory_contract.py",
        "runner_memory_before_build.log",
        "gradle_properties_effective.log",
        "just-incard-v1123-arm64-api35-ndk25b",
    ):
        if fragment not in workflow_text:
            error(f"Workflow-Speicherdiagnose fehlt: {fragment}")
        else:
            ok(f"Workflow-Speicherdiagnose vorhanden: {fragment}")

    if "android.api = 35" not in text:
        error("android.api ist nicht 35")
    else:
        ok("Android-Ziel-API ist 35")
    if "android.minapi = 24" not in text:
        error("android.minapi ist nicht 24")
    else:
        ok("Android-Mindest-API ist 24")
    arch_match = re.search(r"^android\.archs\s*=\s*(.+)$", text, re.M)
    archs = [item.strip() for item in (arch_match.group(1).split(",") if arch_match else []) if item.strip()]
    if archs != ["arm64-v8a"]:
        error(f"Android-Architekturen müssen in v11.2.3 genau arm64-v8a sein: {archs}")
    else:
        ok("Android-Architektur ist ausschließlich arm64-v8a")
    if "android.release_artifact = apk" not in text:
        error("Release-Artefakt ist nicht auf APK festgelegt")
    else:
        ok("Release-Artefakt wird als APK erzeugt")
    if "android.allow_backup = False" not in text:
        error("Android-Backup muss deaktiviert sein")
    else:
        ok("Android-Backup ist deaktiviert")
    if "android.private_storage = True" not in text:
        error("Privater Android-Speicher ist nicht erzwungen")
    else:
        ok("Privater Android-Speicher ist aktiv")

    include_match = re.search(r"^source\.include_exts\s*=\s*(.+)$", text, re.M)
    include_exts = {part.strip().lower() for part in (include_match.group(1).split(",") if include_match else [])}
    if "txt" in include_exts or "md" in include_exts:
        error("Dokumentationsdateien dürfen nicht in die APK-Quellenliste aufgenommen werden")
    else:
        ok("Dokumentationen werden nicht in die APK gepackt")
    for required_ext in ("tflite", "onnx", "vocab"):
        if required_ext not in include_exts:
            error(f"Modell-Dateiendung fehlt in source.include_exts: {required_ext}")
        else:
            ok(f"Modell-Dateiendung enthalten: {required_ext}")

    java_path = ROOT / "android_src/org/yugioh/kartenliste/NativeAiScanner.java"
    java_text = java_path.read_text(encoding="utf-8") if java_path.is_file() else ""
    for fragment in ("TextRecognition", "detectCardRegions", "compareOrb", "compareAkaze", "detectYoloCards", "detectMediaPipeCards", "compareMobileNet", "paddleOcrText", "OnnxTensor"):
        if fragment not in java_text:
            error(f"Native KI-Brücke unvollständig: {fragment}")
        else:
            ok(f"Native KI-Brücke enthält: {fragment}")

    # v11.2.3: OpenCV Rect.area() liefert double. Integer.compare() würde
    # compileDebugJavaWithJavac mit "possible lossy conversion from double to int" abbrechen.
    bad_area_compare = re.search(r"Integer\.compare\([^\n;]*\.area\(\)[^\n;]*\)", java_text)
    if bad_area_compare:
        error("Java-Typfehler: Rect.area() darf nicht mit Integer.compare verglichen werden")
    else:
        ok("Java-Typprüfung: kein Integer.compare auf Rect.area()")
    if "Double.compare(b.area(), a.area())" not in java_text:
        error("Java-Hotfix fehlt: Kartenflächen müssen mit Double.compare sortiert werden")
    else:
        ok("Java-Hotfix aktiv: Kartenflächen werden mit Double.compare sortiert")


def cleanup_stale_release_files():
    """Entfernt veraltete Versions-Changelogs aus einem GitHub-Overlay-Upload.

    Beim Hochladen einer neuen Version über die GitHub-Weboberfläche werden alte
    Dateien nicht automatisch gelöscht. Das darf den APK-Build nicht mehr stoppen.
    Bereinigt werden ausschließlich versionierte Just-InCard-Changelogs im
    Repository-Stamm; andere Dateien bleiben unangetastet.
    """
    expected = "CHANGELOG_v11_2_3.txt"
    removed = []
    for path in ROOT.glob("CHANGELOG_v*.txt"):
        if path.name == expected:
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except Exception as exc:
            warn(f"Alter Changelog konnte nicht entfernt werden: {path.name}: {exc}")
    if removed:
        ok("Alte Changelogs aus Overlay-Upload entfernt: " + ", ".join(sorted(removed)))
    else:
        ok("Keine veralteten Changelogs im Repository-Stamm gefunden")
    return removed


def check_current_text_files():
    txt_files = sorted(path.name for path in ROOT.glob("*.txt"))
    expected = ["CHANGELOG_v11_2_3.txt"]
    if txt_files != expected:
        error(f"TXT-Dateien entsprechen nach automatischer Bereinigung nicht der Nur-aktuelle-Version-Regel: {txt_files}")
    else:
        ok("Nur der aktuelle Changelog CHANGELOG_v11_2_3.txt wird ausgeliefert")



def check_developer_metadata():
    try:
        from app_version import APP_DEVELOPER, APP_ADMIN
        if APP_DEVELOPER != "leenation" or APP_ADMIN != "leenation":
            error("Programmierer/Admin-Metadaten sind nicht auf leenation gesetzt")
        else:
            ok("Programmierer/Admin: leenation")
    except Exception as exc:
        error(f"Entwicklermetadaten konnten nicht geprüft werden: {exc}")


def check_json_files():
    for name in ("just_incard_local_seed.json", "just_incard_source_registry.json"):
        try:
            data = json.loads((ROOT / name).read_text(encoding="utf-8"))
            if not isinstance(data, (dict, list)):
                error(f"JSON-Struktur ungültig: {name}")
            else:
                ok(f"JSON gültig: {name}")
        except Exception as exc:
            error(f"JSON-Fehler in {name}: {exc}")


def check_images():
    try:
        from PIL import Image
    except Exception:
        warn("Pillow auf Runner nicht verfügbar; Bildprüfung übersprungen")
        return
    for name in (
        "app_logo.png", "app_logo_transparent.png", "app_icon.png", "preview_placeholder.png", "presplash.png",
        "assets/ui/app_mark.png", "assets/ui/search.png", "assets/ui/scan.png",
        "assets/ui/cards.png", "assets/ui/decks.png", "assets/ui/more.png",
    ):
        path = ROOT / name
        if not path.exists():
            continue
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
            if width < 64 or height < 64:
                warn(f"Bild ungewöhnlich klein: {name} ({width}x{height})")
            else:
                ok(f"Bild gültig: {name} ({width}x{height})")
        except Exception as exc:
            error(f"Bild beschädigt: {name}: {exc}")


def write_report():
    payload = {
        "version": EXPECTED_VERSION,
        "ok": OK,
        "warnings": WARNINGS,
        "errors": ERRORS,
        "sha256": {},
    }
    for path in sorted(ROOT.glob("*.py")) + [ROOT / "buildozer.spec"]:
        try:
            payload["sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            pass
    (REPORT_DIR / "preflight_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"Just InCard v{EXPECTED_VERSION} Preflight", "", f"OK: {len(OK)}", f"Warnungen: {len(WARNINGS)}", f"Fehler: {len(ERRORS)}", ""]
    lines += ["[OK] " + item for item in OK]
    lines += ["[WARNUNG] " + item for item in WARNINGS]
    lines += ["[FEHLER] " + item for item in ERRORS]
    (REPORT_DIR / "preflight_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    cleanup_stale_release_files()
    check_required_files()
    check_python()
    check_main_ast()
    check_version_consistency()
    check_buildozer_spec()
    check_developer_metadata()
    check_current_text_files()
    check_json_files()
    check_images()
    write_report()
    print(f"Preflight: {len(OK)} OK, {len(WARNINGS)} Warnungen, {len(ERRORS)} Fehler")
    for item in WARNINGS:
        print("WARNUNG:", item)
    for item in ERRORS:
        print("FEHLER:", item)
    return 1 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
