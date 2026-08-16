# Datenschutz und lokale Daten v12

Just InCard speichert Sammlung, Decks, Wunsch-/Tauschlisten, Preisverlauf, Scanner-Lernregeln und Einstellungen grundsätzlich im privaten App-Speicher des Android-Geräts.

- Der optionale OpenAI-API-Schlüssel wird auf Android mit einem nicht exportierbaren Android-Keystore-Schlüssel verschlüsselt. Er wird nicht in JSON, SQLite-Backups oder Diagnoseberichte aufgenommen.
- Standard-Backups sind portable ZIP-Dateien und sollten wie persönliche Daten behandelt werden.
- Gerätegebundene `.jicbak`-Backups verwenden AES-GCM und lassen sich nur mit dem zugehörigen Android-Keystore-Schlüssel entschlüsseln. Nach Gerätewechsel, App-Datenlöschung oder Schlüsselverlust sind sie absichtlich nicht wiederherstellbar.
- Kamera- und Galerieinhalte werden nur für den ausdrücklich gestarteten Scan verarbeitet. Temporäre Scannerbilder werden durch die Cache-Wartung begrenzt und entfernt.
- Online-Abfragen für Kartendaten, Bilder, Preisangaben oder optionale KI-Funktionen werden nur für die jeweilige Funktion ausgeführt. Vor einer öffentlichen Veröffentlichung müssen Anbieter, Rechtsgrundlage, Kontakt, Aufbewahrung und Widerruf in eine rechtlich geprüfte Datenschutzerklärung übernommen werden.

Diese Projektinformation ersetzt keine Rechtsberatung.
