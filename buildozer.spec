[app]
title = Just InCard
package.name = yugiohkartenliste
package.domain = org.yugioh.kartenliste

source.dir = .
source.include_exts = py,pyc,json,png,jpg,jpeg,webp,kv,tflite,task,onnx,vocab
source.exclude_dirs = .git,.github,.buildozer,bin,__pycache__,logs,tests,scripts,docs,ci
source.exclude_patterns = preflight_check.py,apk_validate.py,prepare_release_hardening.py,prepare_ai_models_v109.py

version = 12.0.1
# p4a v2026.05.09 löst charset-normalizer 3.5.x als PEP-738-Android-Wheel
# auf, installiert Python-Module anschließend aber noch mit einem Host-pip ohne
# Android-Plattformargument. Build #7 brach deshalb mit "not a supported wheel"
# ab. 3.4.9 ist die letzte geprüfte universelle py3-none-any-Ausgabe und bleibt
# mit requests kompatibel. Die Unterstrich-Schreibweise ist absichtlich gewählt,
# damit p4a die direkte Anforderung und den normalisierten Metadaten-Namen gleich
# behandelt und nicht zusätzlich die neueste Android-Wheel-URL anhängt.
requirements = python3,kivy,openssl,certifi,charset_normalizer==3.4.9,pyjnius,plyer,pillow,qrcode

# Hoch- und Querformat; die App wählt beim Start und bei Größenänderungen
# automatisch Smartphone-/Tablet-Layout.
orientation = all
fullscreen = 1

icon.filename = app_icon.png
presplash.filename = presplash.png
android.presplash_color = #020512

android.permissions = INTERNET,CAMERA,FLASHLIGHT,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VISUAL_USER_SELECTED,POST_NOTIFICATIONS
android.api = 35
android.minapi = 24
android.ndk = 27c
android.ndk_api = 24
android.accept_sdk_license = True
# v12.0.1: bewusst nur 64-Bit ARM. Der vollständige GitHub-Log zeigte einen
# defekten, zwischen zwei ABI-Durchläufen wiederverwendeten pip-Venv.
# Ein einzelnes ABI beseitigt diesen Fehler und unterstützt aktuelle Android-Geräte.
android.archs = arm64-v8a
android.debug_artifact = apk
android.release_artifact = apk
android.allow_backup = False
android.enable_androidx = True
android.private_storage = True

# KI-Scanner-Build: ML Kit, MediaPipe/LiteRT, OpenCV und ONNX Runtime.
# Große optionale Modelle werden im Workflow vorbereitet; fehlende Zusatzmodelle
# blockieren den stabilen ML-Kit-/OpenCV-/Datenbank-Fallback nicht.
android.gradle_dependencies = com.google.mlkit:text-recognition:16.0.1,com.google.mlkit:text-recognition-chinese:16.0.1,com.google.mlkit:text-recognition-devanagari:16.0.1,com.google.mlkit:text-recognition-japanese:16.0.1,com.google.mlkit:text-recognition-korean:16.0.1,com.google.mediapipe:tasks-vision:0.10.35,org.opencv:opencv:4.12.0,com.microsoft.onnxruntime:onnxruntime-android:1.21.1,androidx.appcompat:appcompat:1.7.1,androidx.camera:camera-core:1.4.2,androidx.camera:camera-camera2:1.4.2,androidx.camera:camera-lifecycle:1.4.2,androidx.camera:camera-view:1.4.2,androidx.work:work-runtime:2.10.1


# Gradle-Kompatibilität für große native KI-AARs. MediaPipe bringt die
# benötigte LiteRT-Laufzeit bereits transitiv mit; die zusätzliche alte
# tensorflow-lite-task-vision-Abhängigkeit wurde entfernt, um doppelte Klassen
# und native Bibliotheken zu vermeiden.
android.add_compile_options = "sourceCompatibility = 1.8", "targetCompatibility = 1.8"
android.add_packaging_options = "pickFirst 'lib/**/libc++_shared.so'", "exclude 'META-INF/DEPENDENCIES'", "exclude 'META-INF/LICENSE*'", "exclude 'META-INF/NOTICE*'", "exclude 'META-INF/*.kotlin_module'", "exclude 'META-INF/INDEX.LIST'"
android.add_gradle_repositories = "google()", "mavenCentral()"
android.numeric_version = 1201

# Native KI-Bridges (ML Kit, OpenCV, ONNX/YOLO).
android.add_src = android_src
android.extra_manifest_xml = android_manifest_extra.xml
p4a.hook = p4a_manifest_hook.py
# Reproduzierbarer, offizieller p4a-Release statt beweglichem develop-Branch.
p4a.branch = v2026.05.09

[buildozer]
log_level = 2
warn_on_root = 1
