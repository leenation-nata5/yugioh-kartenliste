# Just InCard v12.0.1 – Responsive UI

## Ziel

Die Oberfläche wird aus der aktuell verfügbaren Fenstergröße aufgebaut, nicht aus einer festen Geräteauflösung. Dadurch funktionieren auch Split-Screen, Foldables, große Android-Systemschrift und ein Wechsel zwischen Hoch- und Querformat.

## Fensterklassen

- **Narrow:** unter 360 dp
- **Compact:** 360 bis 599 dp
- **Medium:** 600 bis 839 dp
- **Expanded:** 840 bis 1199 dp
- **Large:** 1200 bis 1599 dp
- **Extra Large:** ab 1600 dp

Die kleinste Gerätebreite entscheidet zusätzlich, ob das Gerät als Smartphone oder Tablet gilt. Eine Seitenleiste wird erst ab mindestens 720 dp Fensterbreite verwendet. Im schmalen Tablet-Split-Screen wechselt die App automatisch zurück zur Bottom-Navigation.

Bereits geöffnete Start-, Sammlungs- und Deckseiten registrieren einen entprellten Seiten-Reflow. Damit wechseln auch dynamisch erzeugte Zeilen nach Rotation, Fold-/Unfold- oder Split-Screen-Änderungen in die neue Fensterklasse, ohne dass die App neu gestartet werden muss.

## Typografie und Touchflächen

- zentrale Rollen für Display-, Überschriften-, Abschnitts-, Fließ- und Navigationstext
- begrenzte Skalierung von Bedienelementen, damit große Systemschrift keine Schaltflächen zerlegt
- stärkere Skalierung von Fließtext in scrollbaren Bereichen
- mindestens 48 dp für interaktive Aktionsflächen
- texturbasierte Höhe für mehrzeilige Hinweise und Beschreibungen
- Laufzeitprüfung nach Größen-, Orientierungs- und Schriftwechsel

## Suche und Karten

- einspaltige Suche auf Smartphones
- zwei bis drei Suchspalten auf größeren Fenstern
- bildgestützte Ergebniskarten mit getrennten Informations- und Aktionsbereichen
- Ergebnisaktionen erhalten je nach Breite eine oder mehrere Zeilen mit mindestens 48 dp Höhe
- Kartendetails stehen auf Smartphones unter der Ergebnisliste und auf Tablets daneben

## Scanner

- Kamera-Viewport wird aus der tatsächlichen Fensterhöhe berechnet
- Quelle, Status und Gerätename liegen in Layout-Zeilen statt an absoluten Bildschirmkoordinaten
- Livebild wird ausschließlich innerhalb des Kartenrahmens geclippt
- Cover-Fit verwendet das native Textur-Seitenverhältnis und verzerrt das Kamerabild nicht
- Kartenrahmen besitzt auf jeder Fenstergröße dasselbe Seitenverhältnis
- das Bubble-Menü bleibt innerhalb des Scanner-Viewports und wechselt bei niedrigen Querformatfenstern horizontal bzw. bei extrem schmalen Split-Screen-Fenstern in ein kompaktes 2×2-Raster
- geschlossene Bubble-Aktionen besitzen Größe und Deckkraft 0 und können keine Berührungen abfangen
- Tipp außerhalb, Android-Zurück und die Schließen-Schaltfläche beenden den Menümodus
- der für OCR exportierte Livebereich enthält nur die sichtbare Kartenfläche

## Leistung

- UI-Profile werden bis zur nächsten echten Fenster-/Inset-Änderung wiederverwendet
- Such- und Sammlungskarten entstehen in kleinen Frame-Batches
- Sammlung und Decks werden bei schnellen Änderungen gebündelt im Hintergrund gespeichert
- Pause, Stop und Backup erzwingen immer einen abschließenden synchronen Speicherstand
- unveränderte Scannertexturen lösen keinen vollständigen Geometrie-Neuaufbau aus

## Automatische Prüfung

`tests/test_v110_responsive_contract.py` simuliert elf typische Fensterprofile, darunter kleine Smartphones, maximale Systemschrift, große Smartphones, Tablets, Querformat und Tablet-Split-Screen. `tests/test_v113_ui_performance_contract.py` ergänzt Kollisions-, Safe-Area-, Bubble-Menü- und Leistungsregeln. Die Tests validieren Touchziele, Navigation, Suchspalten, Kartenrahmen, Kamera-Cover-Fit und vollständig sichtbare Scannersteuerungen.
