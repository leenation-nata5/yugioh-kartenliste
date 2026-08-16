# Just InCard v11.2.1 – KI-Modellarchitektur

Programmierer/Admin: **leenation**

## Stabiler Android-Core

Der Standardbuild enthält die Android-Abhängigkeiten und Brücken für:

- Google ML Kit Text Recognition
- OpenCV ORB/AKAZE und Kartenkonturen
- ONNX Runtime Android
- MediaPipe Tasks Vision
- LiteRT Task Vision
- bestehende Pillow-/Datenbank-/Artwork-Fallbacks

Der Scanner bleibt funktionsfähig, wenn ein optionales Modell nicht geladen werden kann.

## Erweiterte Modellpakete

Der GitHub-Workflow kann mit `include_extended_ai_models` zusätzlich vorbereiten:

- YOLO-Kartendetektor als ONNX-Datei
- PaddleOCR PP-OCRv5 Detektor und lateinisches Erkennungsmodell
- quantisiertes MiniLM-ONNX-Modell und Vokabular
- MobileNetV3 Image-Embedder

Die Dateien werden vor dem Build mit Mindestgröße beziehungsweise SHA-256 geprüft.

## EasyOCR und Sentence-Transformers

EasyOCR und das originale Python-Paket `sentence-transformers` setzen PyTorch und weitere große Laufzeitkomponenten voraus. Sie werden daher nicht als verpflichtende Buildozer-Abhängigkeiten erzwungen. Die App besitzt:

- optionale Python-/Server-Adapter, falls diese Komponenten installiert sind
- MiniLM-ONNX-Modellvorbereitung
- einen vollständig lokalen semantischen N-Gramm-/Token-Fallback

## Trefferlogik

1. Exakter Set-Code
2. Exakter Passcode
3. ATK/DEF/Level/Rang/Link/Typ/Sprache
4. ORB/AKAZE/MobileNet-Artwork
5. Kartenname
6. Effekttext und semantischer Vergleich

Ein Kartenname oder Artwork darf einen exakten Set-Code- oder Passcode-Treffer nicht verdrängen. Artworks werden pro Galerie-Bild isoliert verwaltet.

## Lizenzhinweis

Framework-Lizenzen und Modelllizenzen sind getrennt zu prüfen. Das optionale externe YOLO-TCG-Modell wird nur über das Vorbereitungsskript geladen; vor einer öffentlichen Weiterverteilung muss seine konkrete Modelllizenz geprüft werden.

## Galerie-Ordnerseiten in v11.2.1

Die Galerie-Erkennung fusioniert YOLO-, MediaPipe-, OpenCV- und Pillow-Boxen. Jede resultierende Kartenfläche wird danach separat mit ML Kit und optional PaddleOCR/EasyOCR gelesen. ORB, AKAZE und MobileNetV3 bestätigen das Artwork; MiniLM beziehungsweise der lokale semantische Fallback prüft Effekttexte.
