# Just InCard v11.3.0

Vollständiges Android-/Kivy-Projekt mit responsiver Oberfläche, Live-/Kamera-/Galeriescanner, Sammlung, Deckverwaltung und automatischer Smartphone-/Tablet-Anpassung.

Programmierer / Administrator: leenation

## Wichtigste Änderungen in v11.3.0

- kollisionsfreie Scanner-Kopfzeile ohne feste Bildschirmpositionen
- vollständig schließbares Bubble-Menü mit Tipp-außerhalb- und Android-Zurück-Verhalten
- Kamera-/Galerieinhalt nur innerhalb des gelben Kartenrahmens
- begrenzte Android-Safe-Areas für hohe Smartphones und Hersteller-ROMs
- gebündeltes Hintergrundspeichern für Sammlung und Decks
- frameweises Rendern von 50 Suchergebnissen
- paginierte, frameweise gerenderte Sammlung mit 50 Varianten pro Seite
- weniger identische Layout-, Geometrie- und SQLite-Durchläufe

## GitHub-Build

1. Den Inhalt dieses Ordners direkt in die oberste Ebene des GitHub-Repositorys kopieren.
2. Prüfen, dass `main.py`, `buildozer.spec`, `app_version.py`, `.github` und `tests` direkt im Repository liegen.
3. Commit erstellen und unter **Actions → Build Android APKs → Run workflow** starten.
4. Debug-APK, optionale Release-APK, Security-Metadaten und vollständige Logs stehen anschließend unter **Artifacts** bereit.

Der Workflow behält den python-for-android-Hotfix für Android-Wheels, die Gradle/OpenCV-Speicherkonfiguration mit 4096 MB Heap und maximal zwei Workern sowie die native CameraX-Konfiguration bei.

## Scanner

- Live/Kamera: Schnell oder Normal.
- Galerie: immer Gründlich.
- Set-Code und Passcode sind harte Primärmerkmale.
- Kartenname und Effekttext dienen als Fallback; ATK, DEF, Level, Typ, Eigenschaft, Sprache und Artwork validieren Kandidaten zusätzlich.
- Mehrfachbilder und erkannte Kartenflächen bleiben vollständig voneinander isoliert.
- Das Livebild füllt verzerrungsfrei nur den gelben Kartenrahmen.

## Sammlung und Decks

- Mengen, Set, Set-Code, Rarity, Artwork und Sprache bleiben pro Variante erhalten.
- Sammlungsvorschau zeigt Bild, Effekt, Werte, Set/Rarity und Reprints.
- Bis zu 50 Decks; bis zu fünf Favoriten mit Vorschau.
- Deckideen verwenden ausschließlich vorhandene Sammlungskarten.

## Responsive Oberfläche

Eine APK unterstützt Smartphone, Tablet, Hochformat, Querformat und Split-Screen. Fensterbreite in dp, Dichte, Schriftfaktor und sichere Systemränder steuern Spalten, Navigation, Touchflächen, Typografie und Scannergeometrie. Smartphones verwenden Bottom-Navigation; ausreichend breite Tablets eine Navigationsleiste.

Das Kivy-unabhängige Designsystem und die Geometrietests liegen in `ui_v110.py`. Der v11.3-Vertrag befindet sich in `tests/test_v113_ui_performance_contract.py`.

## Sicherheit

Release-Signierung, Zipalign, SHA-256, privater App-Speicher, deaktiviertes Android-Backup, Integritätsmanifest und Best-Effort-Obfuskation bleiben aktiv. Ein vollständiger Schutz vor Reverse Engineering kann bei Android-Apps technisch nicht garantiert werden.

## Aktuelle Dokumentation

Nur `CHANGELOG_v11_3_0.txt` enthält die Änderungen der aktuellen Version.
