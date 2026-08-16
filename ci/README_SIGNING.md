# Android-Signierung

Der Workflow baut zwei APKs:

1. **Debug-APK** – automatisch von Android/Buildozer mit dem Debug-Schlüssel signiert.
2. **Release-APK** – optimierter Release-Build.

Damit die Release-APK ohne weitere Einrichtung installierbar ist, liegt unter
`ci/justincard-ci-test.keystore` ein **öffentlicher Test-/CI-Schlüssel**. Dieser
Schlüssel ist nur für private Tests gedacht und darf nicht für Google Play oder
eine öffentliche Veröffentlichung verwendet werden.

## Sichere Produktionssignierung

Lege in GitHub unter `Settings > Secrets and variables > Actions` diese Secrets an:

- `ANDROID_KEYSTORE_BASE64` – Keystore-Datei als Base64
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Sind alle vier Secrets gesetzt, verwendet der Workflow automatisch den privaten
Produktionsschlüssel. Andernfalls wird die APK deutlich als `release-test`
benannt und mit dem mitgelieferten CI-Testschlüssel signiert.

Beispiel zum Erzeugen des Base64-Werts unter Linux:

```bash
base64 -w 0 mein-release-key.jks
```
