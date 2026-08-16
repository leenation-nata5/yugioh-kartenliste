Programmierer / Administrator: leenation

# KI-Deckhilfe / API-Hinweis

Die App kann Decks lokal aus der Sammlung analysieren. Eine echte externe KI-Anbindung ist technisch moeglich, sollte aber optional bleiben, weil ein API-Key benoetigt wird und Sammlung/Kartendaten an einen externen Dienst gesendet werden koennen.

Empfohlenes Konzept:
- Nutzer traegt optional einen eigenen API-Key in den App-Einstellungen ein.
- Die App sendet nur Kartennamen, Mengen, Set/Rarity und Zielidee des Decks.
- Die KI darf nur Karten vorschlagen, die in der Sammlung vorhanden sind oder klar als "nicht vorhanden" markieren.
- Decks werden nur erstellt, wenn mindestens 40 Karten aus der Sammlung vorhanden sind.
- Ohne API-Key bleibt die lokale Deckanalyse aktiv.
