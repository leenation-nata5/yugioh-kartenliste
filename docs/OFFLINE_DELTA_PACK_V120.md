# Offline-Delta-Pakete v12

Just InCard kann kleine, prüfsummenvalidierte Kartendaten-Updates ohne vollständige Neusynchronisierung einspielen. Importierte Pakete werden vor jeder Änderung vollständig validiert und speichern einen lokalen Rollback-Stand.

## Format

Eine `.jicpack`-Datei ist UTF-8-JSON:

```json
{
  "schema": 1,
  "pack_id": "de-2026-08-001",
  "base_version": "2026-07",
  "target_version": "2026-08",
  "language": "de",
  "operations": [
    {"op": "upsert", "card": {"id": 12345678, "name": "Beispiel"}},
    {"op": "delete", "id": 87654321}
  ],
  "checksum": "SHA256_DER_KANONISCHEN_NUTZDATEN"
}
```

Die Prüfsumme ist SHA-256 über das gesamte Objekt ohne `checksum`, serialisiert mit sortierten Schlüsseln, UTF-8 und den JSON-Trennzeichen `,` und `:`. `data_packs_v120.pack_checksum()` erzeugt exakt dieses Format. Maximal 50.000 Operationen und 64 MB Eingabedatei werden akzeptiert.

## Sicherheit und Rollback

- unbekannte Schema-Versionen und falsche Prüfsummen werden abgelehnt;
- nur `upsert` und `delete` sind erlaubt;
- die bestehende Datenbank wird erst nach vollständiger Validierung ersetzt;
- „Letztes Delta zurück“ stellt geänderte oder entfernte Karten und deren Reihenfolge wieder her;
- ein vollständiger Sync bleibt jederzeit verfügbar.
