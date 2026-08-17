# -*- coding: utf-8 -*-
"""Static Android contracts for responsive CameraX and Keystore handling."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    camera = (ROOT / "android_src/org/yugioh/kartenliste/CameraXScanActivity.java").read_text(encoding="utf-8")
    secret = (ROOT / "android_src/org/yugioh/kartenliste/SecureSecretStore.java").read_text(encoding="utf-8")
    backup = (ROOT / "android_src/org/yugioh/kartenliste/SecureBackupCipher.java").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")

    for fragment in (
        "Executors.newSingleThreadExecutor",
        "getConfiguration().screenWidthDp >= 720",
        "ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST",
        "PreviewView.ScaleType.FILL_CENTER",
        "setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)",
        "now - lastAnalysisAt < 420L",
        "RectF.intersects(roi",
        "stableFrames >= 3",
        "now - lastAutoCaptureAt > 3500L",
        "FocusMeteringAction.FLAG_AF | FocusMeteringAction.FLAG_AE",
        "enableTorch(torchEnabled)",
        "setExposureCompensationIndex(next)",
        "finishCancelled()",
        "cameraProvider.unbindAll()",
        "analysisExecutor.shutdownNow()",
        "canvas.drawRect(0, 0, width, frame.top, dimPaint)",
    ):
        assert fragment in camera, fragment
    assert camera.count("lastFingerprint = fingerprint;") == 1
    assert "analysis.setAnalyzer(analysisExecutor" in camera
    assert "analysis.setAnalyzer(mainExecutor" not in camera
    assert "smallestScreenWidthDp" not in camera

    for source in (secret, backup):
        assert 'private static final String KEYSTORE = "AndroidKeyStore"' in source
        assert "KeyStore.getInstance(KEYSTORE)" in source
        assert 'Cipher.getInstance("AES/GCM/NoPadding")' in source
        assert "KeyGenParameterSpec.Builder" in source
    assert "new File(outputPath).delete()" in backup
    assert '"openai_api_key": "" if platform == "android"' in main
    assert "android_secure_secret_get()" in main
    assert "export_device_encrypted_backup_v120" in main
    assert "import_device_encrypted_backup_v120" in main

    assert "qrcode" in re.search(r"^requirements\s*=\s*(.+)$", spec, re.M).group(1).split(",")
    assert "android.ndk = 27c" in spec
    assert "p4a.branch = v2026.05.09" in spec
    assert "android.minapi = 24" in spec
    assert "android.api = 35" in spec
    print("v12.0.1 Android CameraX/Keystore contract tests: OK")


if __name__ == "__main__":
    run()
