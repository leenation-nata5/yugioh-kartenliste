# Just InCard v12.0.1

Just InCard ist eine adaptive Android-App für Kartensuche, Live-/Foto-/Galeriescan, Sammlung und Deckplanung. Version 12 ersetzt starre Bildschirmpositionen durch ein fensterbasiertes Designsystem und erweitert Scanner, Performance, Datensicherheit und Austauschformate.

Programmierer / Administrator: `leenation`

## v12 auf einen Blick

- ein Projekt und eine APK für Smartphones, Tablets, Querformat, Split-Screen und Foldables;
- Bottom-Navigation auf schmalen Fenstern, Navigation Rail auf breiten Tablet-Fenstern;
- moderne Navy-/Graphit-Flächen, blaues Fokuslicht, goldener Scannerrahmen und reduzierte Glaseffekte;
- kollisionsfreier Scannerheader und vollständig schließbares Quellen-Bubble-Menü;
- native CameraX-Vorschau mit ROI-OCR, Licht-/Bewegungsfeedback, Tipp-Fokus, Torch, EV und stabiler Autoaufnahme;
- Suche und Sammlung in 50er-Seiten, UI-Batches und virtualisierte große Deck-Auswahlliste;
- Wunsch-/Tauschlisten, lokaler Preisverlauf und Sammlungswert;
- `.ydk`-Import/-Export, Deckvalidierung sowie QR-/Teilcode;
- validierte Offline-Delta-Pakete mit Rollback;
- Android-Keystore für API-Schlüssel und optionale gerätegebundene AES-GCM-Backups;
- reproduzierbarer GitHub-Build für Debug-APK, signierte Release-APK und optionales Google-Play-AAB.

## Buildkorrektur in v12.0.1

Der bereitgestellte Build-Log 7 brach vor Gradle beim Installieren von
`charset_normalizer-3.5.1-cp314-cp314-android_24_arm64_v8a.whl` ab. Der zuvor
eingesetzte Patch an der ausgecheckten python-for-android-Datei war wirkungslos,
weil Buildozer diesen Checkout vor dem eigentlichen Build aktualisiert.

v12.0.1 löst das reproduzierbar im Projekt selbst:

- `charset_normalizer==3.4.9` bleibt beim p4a-Host-Staging ein universelles
  `py3-none-any`-Wheel;
- der veraltete p4a-Quellpatch wurde vollständig entfernt;
- Workflow und Preflight prüfen Pin, Toolchain-Commit und einen eigenen
  Build-Logs-7-Regressionstest vor dem mehrstündigen Android-Build;
- der Cache-Namensraum wurde auf Build 1201 geändert, damit keine fehlerhafte
  Zwischenablage aus Build 1200 wiederverwendet wird.

## Projekt lokal prüfen

Erforderlich ist Python 3.10 oder neuer. Die Kivy-unabhängigen Tests benötigen nur Pillow:

```bash
python3 preflight_check.py
for test_file in tests/test_*.py; do python3 "$test_file" || exit 1; done
```

Die v12-Schwerpunkte liegen in:

- `ui_v120.py`: Fensterklassen, Scannergeometrie und Virtualisierungshelfer;
- `features_v120.py`: YDK, Deckprüfung, Deckcode, Preis-/Listenlogik und Seriengate;
- `data_packs_v120.py`: Offline-Delta, Prüfsumme und Rollback;
- `android_src/.../CameraXScanActivity.java`: native Livekamera;
- `android_src/.../SecureSecretStore.java`: Android-Keystore-Schlüsselspeicher;
- `android_src/.../SecureBackupCipher.java`: gerätegebundene Backups;
- `UI_V120_DESIGN.md` und `docs/TESTMATRIX_V120.md`: Design- und Gerätevertrag.

## Android mit GitHub Actions bauen

1. Den Inhalt des Ordners `JustInCard_v12_0_1` direkt in die Wurzel eines GitHub-Repositorys kopieren.
2. Prüfen, dass `main.py`, `buildozer.spec`, `app_version.py`, `.github`, `android_src` und `tests` direkt dort liegen.
3. Commit pushen und unter **Actions → Build Android APKs und optionales AAB → Run workflow** starten.
4. Optional `build_aab` für ein Google-Play-App-Bundle aktivieren.
5. Artefakte herunterladen: Debug-APK, Release-APK, optionales AAB, SHA-256-Dateien, Security-Metadaten und vollständige Logs.

Ohne eigene GitHub-Secrets wird die Release-Ausgabe mit dem öffentlichen CI-Testschlüssel signiert und heißt `release-test`. Für produktive Updates müssen diese Secrets gesetzt werden:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Die Testsignatur darf nicht für Google Play oder produktive Updates verwendet werden. Details stehen in `ci/README_SIGNING.md`.

## Scannerlogik

Die Identifikation priorisiert:

1. exakten Set-/Printcode;
2. exakten Passcode;
3. Kartenname als Fallback.

Effekttext, Artwork, ATK, DEF, Stufe/Rang/Link, Typ, Eigenschaft und Sprache validieren den Kandidaten. Galerieimporte verwenden den gründlichen Mehrfachkartenmodus. Der Live-Serienmodus wartet drei stabile Frames ab und unterdrückt direkte Wiederholungen.

## Responsive und barrierearm

Das aktuelle Android-Fenster ist die Quelle der Wahrheit. Modellname und physische Displayauflösung entscheiden nicht über Positionen. Safe Areas, Dichte, Schriftfaktor, Rotation und Fensteränderungen invalidieren ein gecachtes Profil und lösen einen entprellten Reflow aus.

- Fenster unter 720 dp: Bottom-Navigation;
- breite Tablet-/Querformatfenster ab 720 dp: Navigation Rail;
- Touchziele mindestens 48 dp;
- reduzierte Bewegung optional vollständig aus;
- hohe Fokuskontraste und große Touchziele optional;
- Inhalte und Dialoge scrollbar statt abgeschnitten.

## Leistung

- CameraX-Analyse auf eigenem Einzelthread, `KEEP_ONLY_LATEST`, 420-ms-Drosselung;
- Netzwerk, OCR, Datenbank-Sync, Delta-Import und Bildanalyse außerhalb des Renderthreads;
- RecycleView für potentiell große Deck-Auswahl;
- Such-/Sammlungsseiten mit maximal 50 Einträgen;
- kleine Vorschaubilder in Listen, große Artworks nur in Details;
- gebündeltes Speichern, SQLite-WAL und gezielte Indizes;
- begrenzter Bild-/Scanner-Cache und maximal 366 Preispunkte je Karte.

## Daten und Sicherheit

Portable ZIP-Backups eignen sich für einen Gerätewechsel. `.jicbak` ist dagegen mit dem Android-Keystore des aktuellen Geräts gebunden. Ein API-Schlüssel verlässt den Keystore nicht und wird aus Backups und Diagnosen ausgeschlossen.

Weitere Hinweise:

- `docs/DATENSCHUTZ_V120.md`
- `docs/OFFLINE_DELTA_PACK_V120.md`
- `CHANGELOG_v12_0_1.txt`

## Unterstützungsrahmen

Der Build zielt auf Android API 24 bis 35 und `arm64-v8a`. Damit werden aktuelle 64-Bit-Android-Smartphones und -Tablets abgedeckt; sehr alte 32-Bit-Geräte sind wegen der nativen ML-/Kameraabhängigkeiten bewusst nicht Teil dieses Builds. Hersteller-ROMs können Berechtigungs- oder Energiesparverhalten verändern, weshalb die reale Matrix in `docs/TESTMATRIX_V120.md` zur Freigabe dazugehört.
