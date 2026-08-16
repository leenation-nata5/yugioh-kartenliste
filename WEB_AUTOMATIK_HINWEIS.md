Programmierer / Administrator: leenation

# Webdaten automatisch übernehmen

Eine vollautomatische Übernahme von Cardmarket/Cardcluster-Daten ohne offiziellen API-Zugang ist nicht sauber/stabil genug, weil diese Seiten keine frei nutzbare öffentliche API für diese App bereitstellen.

In Just InCard ist deshalb der sichere Weg eingebaut:

- Websuche im Browser öffnen
- gefundene Daten in der App unter „Web-Quellen speichern“ eintragen
- Bild wahlweise per URL, lokalem Pfad, letztem Scannerfoto oder Galerie-Bild übernehmen

Bei lokalen Karten ist ebenfalls ein Galerie-Bild-Button vorhanden. Das ausgewählte Bild wird in den App-Cache kopiert und danach in Suche, Sammlung, Decks und Export verwendet.

Eine automatische Übergabe wäre möglich, wenn eine Quelle eine offizielle API oder einen Export anbietet. Dann könnte die App Name, Set-Code, Rarity und Bild-URL automatisch befüllen.
