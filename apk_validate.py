# -*- coding: utf-8 -*-
"""Prüft eine erzeugte Android-APK ohne zusätzliche Python-Pakete."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("apk")
    parser.add_argument("--version", default="10.0.2")
    parser.add_argument("--report-dir", default="logs")
    args = parser.parse_args()

    apk = Path(args.apk).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    warnings = []
    details = []

    if not apk.is_file() or apk.stat().st_size < 1024 * 1024:
        errors.append(f"APK fehlt oder ist ungewöhnlich klein: {apk}")
    else:
        details.append(f"APK-Größe: {apk.stat().st_size / (1024*1024):.2f} MB")

    names = []
    if not errors:
        try:
            with zipfile.ZipFile(apk) as archive:
                bad = archive.testzip()
                if bad:
                    errors.append(f"Defekter ZIP/APK-Eintrag: {bad}")
                names = archive.namelist()
        except Exception as exc:
            errors.append(f"APK kann nicht geöffnet werden: {exc}")

    required_exact = ["AndroidManifest.xml", "classes.dex"]
    for name in required_exact:
        if name not in names:
            errors.append(f"APK-Inhalt fehlt: {name}")
    if names and not any(name.startswith("lib/") and name.endswith(".so") for name in names):
        errors.append("APK enthält keine nativen Bibliotheken")
    if names and not any("main.py" in name or "main.pyc" in name or "private.mp3" in name for name in names):
        warnings.append("main.py ist nicht als Klartext sichtbar; python-for-android kann Quellen in private.tar bündeln")
    if names and not any("app_logo" in name or "presplash" in name for name in names):
        warnings.append("Logo/Presplash-Dateien sind im ZIP-Inhaltsverzeichnis nicht direkt sichtbar")

    # Optional: aapt/apkanalyzer, wenn auf dem Runner vorhanden.
    for tool in ("apkanalyzer", "aapt", "aapt2"):
        executable = shutil.which(tool)
        if not executable:
            continue
        try:
            if tool == "apkanalyzer":
                output = subprocess.check_output([executable, "manifest", "application-id", str(apk)], text=True, stderr=subprocess.STDOUT, timeout=30).strip()
                details.append(f"Application-ID: {output}")
                version = subprocess.check_output([executable, "manifest", "version-name", str(apk)], text=True, stderr=subprocess.STDOUT, timeout=30).strip()
                details.append(f"Version-Name: {version}")
                if version and version != args.version:
                    errors.append(f"APK-Version ist {version}, erwartet {args.version}")
            else:
                output = subprocess.check_output([executable, "dump", "badging", str(apk)], text=True, stderr=subprocess.STDOUT, timeout=30)
                match = re.search(r"package: name='([^']+)' versionCode='([^']*)' versionName='([^']*)'", output)
                if match:
                    details.append(f"Paket: {match.group(1)}")
                    details.append(f"Version: {match.group(3)}")
                    if match.group(3) and match.group(3) != args.version:
                        errors.append(f"APK-Version ist {match.group(3)}, erwartet {args.version}")
            break
        except Exception as exc:
            warnings.append(f"Optionale {tool}-Prüfung fehlgeschlagen: {exc}")

    result = {"apk": str(apk), "version": args.version, "details": details, "warnings": warnings, "errors": errors}
    (report_dir / "apk_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"APK-Prüfung Just InCard v{args.version}", ""] + details + [""]
    lines += ["WARNUNG: " + item for item in warnings]
    lines += ["FEHLER: " + item for item in errors]
    (report_dir / "apk_validation.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
