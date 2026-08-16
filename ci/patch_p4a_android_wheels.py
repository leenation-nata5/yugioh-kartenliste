#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hotfix for python-for-android Android-tagged wheels under host pip.

p4a resolves target-compatible wheels using --platform=android_... but later
installs the resolved wheel URLs with a host virtualenv pip without the target
platform arguments. Modern packages (for example charset-normalizer) publish
PEP 738 Android wheels, which host pip correctly rejects as unsupported unless
--platform/--python-version are passed during the --target install as well.

This script patches only that final p4a staging command and is intentionally
strict/idempotent: if upstream changes the function, CI fails here with a clear
message instead of failing much later after a long Android build.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "Just InCard Android wheel staging hotfix v11.3.0"
OLD = '''            shprint(sh.bash, '-c', (
                "venv/bin/pip " +
                "install -v --target '{0}' --no-deps -r requirements.txt"
            ).format(ctx.get_site_packages_dir(arch).replace("'", "'\\\"'\\\"'")),
                    _env=copy.copy(env))'''
NEW = '''            # Just InCard Android wheel staging hotfix v11.3.0
            # The dependency resolver above already chose Android-compatible
            # wheels.  Keep the same target platform when staging them into the
            # app's site-packages; otherwise host pip rejects PEP 738 Android
            # wheels such as cp314-cp314-android_24_arm64_v8a.
            android_platform_args = " ".join(
                "--platform={}".format(tag)
                for tag in PyProjectRecipe.get_wheel_platform_tags(arch.arch, ctx)
            )
            target_python_version = ctx.python_recipe.version
            shprint(sh.bash, '-c', (
                "venv/bin/pip " +
                "install -v --target '{0}' --no-deps --only-binary=:all: " +
                "{1} --python-version={2} -r requirements.txt"
            ).format(
                ctx.get_site_packages_dir(arch).replace("'", "'\\\"'\\\"'"),
                android_platform_args,
                target_python_version,
            ), _env=copy.copy(env))'''


def patch_text(text: str) -> tuple[str, bool]:
    if MARKER in text:
        return text, False
    if OLD not in text:
        raise RuntimeError(
            "p4a build.py does not contain the expected run_pymodules_install "
            "staging command; upstream changed and this hotfix must be reviewed."
        )
    patched = text.replace(OLD, NEW, 1)
    required = (
        MARKER,
        "--only-binary=:all:",
        "PyProjectRecipe.get_wheel_platform_tags(arch.arch, ctx)",
        "--python-version={2}",
    )
    missing = [item for item in required if item not in patched]
    if missing:
        raise RuntimeError("p4a Android-wheel patch incomplete: " + ", ".join(missing))
    return patched, True


def patch_file(path: Path) -> bool:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"python-for-android build.py not found: {path}")
    original = path.read_text(encoding="utf-8")
    patched, changed = patch_text(original)
    if changed:
        path.write_text(patched, encoding="utf-8")
    final = path.read_text(encoding="utf-8")
    if MARKER not in final:
        raise RuntimeError("p4a Android-wheel patch marker missing after patch")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    changed = patch_file(args.path)
    print(
        "p4a Android-wheel staging hotfix: "
        + ("applied" if changed else "already active")
        + f" -> {args.path}"
    )


if __name__ == "__main__":
    main()
