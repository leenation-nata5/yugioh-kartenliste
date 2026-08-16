# Geräte- und Qualitätsmatrix v12

## Automatisierte Matrix

`tests/test_v120_responsive_fuzz.py` prüft mehr als 8.000 Zustände aus 240–2.000 dp Breite, 240–2.000 dp Höhe, Smartphone/Tablet und sichtbarem/unsichtbarem Ergebnis. Geprüft werden Viewport-Grenzen, Header-Kollisionen, Karten-Seitenverhältnis, Touchziele und Virtualisierung.

Der vollständige Preflight führt zusätzlich alle historischen Regressionsverträge sowie Scanner-, SQLite-, Backup-, Sicherheits-, Deck- und Offline-Paket-Tests aus.

## Manuelle Android-Abnahme

| Klasse | Beispiele | Ansichten | Pflichtprüfungen |
|---|---|---|---|
| Compact Phone | 320–359 dp | Hoch/Quer | große Schrift, Bottom-Navigation, Scanner-Menü schließen |
| Phone | 360–599 dp | Hoch/Quer | Livebild ohne Verzerrung, Galerie, Rotation, Android-Zurück |
| Tablet Split | 480–719 dp | Multi-Window | Wechsel auf Bottom-Navigation, keine alten Positionen |
| Tablet | 720–1.199 dp | Hoch/Quer | Navigation Rail, einzeiliger Scanner-Header, Ergebnis-Floating-Card |
| Large Tablet/Desktop | ab 1.200 dp | Quer/Fenster | begrenzte Inhaltsbreite, skalierte Raster, Fokus/Tastatur |

Zusätzlich: Android 7 (API 24), Android 10, Android 13 und Android 15; Kameraberechtigung erlaubt/abgelehnt; dunkle/helle/glänzende Karten; deutsche und internationale Setcodes; App-Pause während Livekamera; 1.000+ Sammlungsvarianten; 50 Decks.

## Leistungsbudgets

- UI-Eingaben und Filter: sichtbare Reaktion unter 100 ms;
- keine OCR-, Netzwerk- oder Datenbank-Volloperation im Renderthread;
- CameraX-Analyse: neuestes Bild, maximal etwa 2,4 Analysen/s;
- direkte Scan-Duplikate: 3,5 Sekunden Sperre;
- Bildcache: begrenzt und nach Alter bereinigt;
- Such- und Sammlungsseiten: höchstens 50 Einträge je Seite;
- große Deckauswahl: nur sichtbare RecycleView-Zeilen erzeugen.

`scripts/adb_smoke_test.sh` ist für die abschließende Prüfung einer von GitHub Actions gebauten APK vorgesehen.
