# Just InCard v12 – adaptives Designsystem

Die v12-Oberfläche übernimmt die visuelle Richtung der Referenz: sehr dunkles Navy, ruhige Graphitflächen, klares Blau für Navigation und Fokus, Gold für den Kartenrahmen sowie Grün nur für bestätigte Zustände. Der Scanner-Hintergrund `assets/ui/scanner_surface_v120.webp` ist ein eigenständiges, lizenzfreies Projektasset ohne Kartenmotiv, Markenlogo oder lesbaren Fremdtext.

## Grundregeln

- Layoutentscheidungen folgen der aktuell verfügbaren Fensterbreite in dp, nicht Modellnamen oder festen Pixelkoordinaten.
- Unter 720 dp wird die Bottom-Navigation genutzt; ab 720 dp auf Tablets bzw. breiten Querformatfenstern die Navigation Rail.
- Inhalte besitzen begrenzte Maximalbreiten, damit Tablet-Oberflächen nicht unlesbar auseinandergezogen werden.
- Touchziele sind mindestens 48 dp, im v12-Chrome 52–56 dp.
- Safe Areas, Android-Systemschrift, Rotation, Split-Screen und Fold-/Unfold-Wechsel lösen einen entprellten Reflow aus.
- Dekorative Bewegung bleibt unter 180 ms und kann vollständig deaktiviert werden.

## Scanner

- CameraX nutzt `FILL_CENTER`; der sichtbare Kartenrahmen hat immer das Seitenverhältnis 1:1,452.
- Smartphone-Header werden gestapelt, breite Tablet-Header schweben in einer kollisionsfreien Zeile.
- Das Quellenmenü ist geschlossen unsichtbar und deaktiviert. Es schließt über den eigenen Schalter, Tipp außerhalb, Android-Zurück und vor Kamera-/Galerieaktionen.
- Live-OCR läuft auf einem einzelnen Hintergrund-Executor mit `KEEP_ONLY_LATEST`, ROI-Filter, 420-ms-Drosselung und Drei-Frame-Stabilität.
- Ergebnis, Quelle und Status sind getrennte Layoutschichten; ein Treffer blendet den Quellenstarter aus.

## Listen und Medien

- Suche und Sammlung sind auf 50 Einträge je Seite begrenzt und werden in UI-Batches aufgebaut.
- Die potentiell große Sammlungsauswahl im Deckbuilder verwendet RecycleView und erzeugt nur sichtbare Zeilen.
- Listen verwenden kleine Vorschaubilder; hochauflösende Artworks werden erst für Detailansichten geladen.
- SQLite nutzt WAL, `synchronous=NORMAL`, Indizes und gebündelte Persistenz; Lebenszyklus- und Backup-Punkte erzwingen einen vollständigen Abschluss.

Die Kivy-unabhängigen Geometrieprimitive liegen in `ui_v120.py` und werden von `tests/test_v120_responsive_fuzz.py` über tausende Fensterzustände geprüft.
