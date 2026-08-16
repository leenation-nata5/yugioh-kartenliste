#!/usr/bin/env bash
set -euo pipefail
APK_FILE="${1:-}"
PACKAGE_NAME="${2:-org.yugioh.kartenliste.yugiohkartenliste}"
if [[ -z "$APK_FILE" || ! -f "$APK_FILE" ]]; then
  echo "Nutzung: $0 <apk-datei> [paketname]"
  exit 2
fi
adb get-state >/dev/null
adb logcat -c || true
adb install -r "$APK_FILE"
adb shell monkey -p "$PACKAGE_NAME" -c android.intent.category.LAUNCHER 1
sleep 8
adb logcat -d > adb_smoke_log.txt
if grep -Eqi 'FATAL EXCEPTION|ANR in|Process .* has died' adb_smoke_log.txt; then
  echo "Starttest fehlgeschlagen. Siehe adb_smoke_log.txt"
  exit 1
fi
echo "Starttest ohne erkannten Fatal-Fehler abgeschlossen."
