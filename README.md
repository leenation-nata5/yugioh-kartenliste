Programmierer / Administrator: leenation

# Just InCard v11.2.1

Vollständiges Android-/Kivy-Projekt mit KI-Scanner, Sammlung, Deckverwaltung und automatischer Smartphone-/Tablet-Anpassung.

## GitHub-Build

1. Den Inhalt dieses Ordners in die oberste Ebene des GitHub-Repositorys kopieren.
2. Prüfen, dass `main.py`, `buildozer.spec` und `.github/workflows/build-android-apk.yml` direkt im Repository liegen.
3. Commit erstellen und unter **Actions → Build Android APKs → Run workflow** starten.
4. Unter Artifacts stehen Debug-APK, optionale Release-APK, Security-Metadaten und vollständige Logs bereit.

## Scanner

- Live/Kamera: Schnell oder Normal.
- Galerie: immer Gründlich.
- Galerie-Gründlich kombiniert Set-Code, Passcode, Kartenname, farbunabhängige OCR, Effekttext und lokalen Artwork-Abgleich.
- Unsichere Ergebnisse werden mit transparenter Einzelbewertung und Alternativen geprüft.
- Die Scan-Prüfzentrale sammelt unsichere und fehlgeschlagene Scans.

## Sammlung

- Sammlungs-Vorschau mit Bild, Effekt, Set/Rarity und Reprints.
- Zustände, Sprache, Auflage, Lagerort, Notiz, Kaufdatum und Kaufpreis pro Kartenvariante.
- Duplikat- und Variantenprüfung.

## Decks

- Bis zu 50 Decks, davon bis zu fünf Favoriten mit Vorschau.
- Testhand-Simulation und lokale Synergieanalyse.
- KI-Deckvorschläge nutzen ausschließlich vorhandene Karten aus der Sammlung.

## Smartphone und Tablet

Die App nutzt eine gemeinsame APK und erkennt das Gerät automatisch anhand der verfügbaren dp-Breite, Pixeldichte, Ausrichtung, Schriftgröße und sicheren Systemränder. Smartphones verwenden Bottom-Navigation und einspaltige Seiten. Tablets verwenden bei ausreichender Breite Seitenleiste, mehr Spalten und größere Vorschau-/Scannerflächen.

## Oberfläche v11.2.1

- zentrales responsives Designsystem in `ui_v110.py`
- moderne Startseite, Suche, Ergebniskarten, Kartendetails, Scanner, Sammlung und Deckansichten
- Mindest-Touchflächen und eine defensive Laufzeitprüfung gegen Textüberlagerungen
- automatische Fensterklassen für kleine Smartphones, Tablets, Querformat und Split-Screen
- technische Details stehen in `UI_V110_RESPONSIVE.md`

## Sicherheit

Die Release-Konfiguration nutzt Signierung, Zipalign, SHA-256, privaten App-Speicher, deaktiviertes Android-Backup, Integritätsmanifest und einen optimierten Python-Release-Build. Eine absolute Unlesbarkeit oder vollständiger Schutz vor Reverse Engineering kann bei keiner Android-APK garantiert werden.

## Aktuelle Dokumentation

Nur `CHANGELOG_v11_2_1.txt` enthält die Änderungen der aktuellen Version.

## Galerie-Multi-Engine-Pipeline in v11.2.1

- YOLO, MediaPipe, OpenCV und Pillow liefern getrennte Kartenrahmen-Kandidaten.
- Überlappende Erkennungen werden per gewichteter Box-Fusion zu einer Kartenfläche zusammengeführt.
- Pro Ausgangsbild werden bis zu 64 Kartenflächen als getrennte Sessions verarbeitet.
- Jede Session besitzt ein eigenes Crop, eine eigene OCR, eigene Kandidaten, ein eigenes Artwork und eine eigene Fehlerquelle.
- ML Kit, PaddleOCR/EasyOCR (wenn verfügbar), ORB/AKAZE, MobileNetV3 und MiniLM liefern unabhängige Signale.
- Set-Code und Passcode bleiben harte Primäridentifikatoren; Name und Effekt sind nur Fallbacks.
