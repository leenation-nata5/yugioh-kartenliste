# Just InCard v11.2.3 – Responsive UI

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
- Livebild wird ausschließlich innerhalb des Kartenrahmens geclippt
- Cover-Fit verwendet das native Textur-Seitenverhältnis und verzerrt das Kamerabild nicht
- Kartenrahmen besitzt auf jeder Fenstergröße dasselbe Seitenverhältnis
- Scanquellen wechseln auf sehr schmalen Fenstern automatisch von drei Spalten in eine vertikale Liste
- der für OCR exportierte Livebereich enthält nur die sichtbare Kartenfläche

## Automatische Prüfung

`tests/test_v110_responsive_contract.py` simuliert elf typische Fensterprofile, darunter kleine Smartphones, maximale Systemschrift, große Smartphones, Tablets, Querformat und Tablet-Split-Screen. Der Test validiert Touchziele, Navigation, Suchspalten, Kartenrahmen und Kamera-Cover-Fit.
