#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the Android-safe pure-Python dependency contract.

python-for-android v2026.05.09 resolves PEP 738 Android wheels correctly, but
its later pure-module staging command still invokes a host pip without target
platform arguments.  Build #7 therefore selected charset-normalizer 3.5.1 for
Android and then rejected the same wheel as unsupported.  We avoid modifying
the checked-out p4a source (Buildozer refreshes that checkout) and pin the last
verified universal wheel instead.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


PACKAGE = "charset-normalizer"
# The underscore spelling is intentional. p4a v2026.05.09 compares resolved
# metadata after replacing '-' with '_', but does not normalize its direct
# requirement-name list the same way. Using the PyPI-equivalent underscore form
# keeps the package classified as direct and prevents the 3.5.x Android URL from
# being appended again as a transitive module.
PINNED_REQUIREMENT = "charset_normalizer==3.4.9"
EXPECTED_UNIVERSAL_WHEEL = "charset_normalizer-3.4.9-py3-none-any.whl"


def canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value.strip().lower())


def parse_requirements(spec_text: str) -> tuple[str, ...]:
    match = re.search(r"^requirements\s*=\s*(.+)$", spec_text, re.MULTILINE)
    if not match:
        raise ValueError("buildozer.spec has no requirements line")
    items = tuple(item.strip() for item in match.group(1).split(",") if item.strip())
    if not items:
        raise ValueError("buildozer.spec requirements are empty")
    return items


def package_name(requirement: str) -> str:
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", requirement)
    if not match:
        raise ValueError(f"invalid requirement: {requirement!r}")
    return canonical_name(match.group(1))


def verify_spec(path: Path) -> tuple[str, ...]:
    path = Path(path)
    requirements = parse_requirements(path.read_text(encoding="utf-8"))
    matches = [item for item in requirements if package_name(item) == PACKAGE]
    if matches != [PINNED_REQUIREMENT]:
        raise RuntimeError(
            "Android build requires exactly "
            f"{PINNED_REQUIREMENT!r}; found {matches or 'no pin'}"
        )
    direct_name = PINNED_REQUIREMENT.split("==", 1)[0]
    p4a_metadata_name = PACKAGE.replace("-", "_")
    if direct_name != p4a_metadata_name:
        raise RuntimeError(
            "p4a direct-requirement spelling must match its metadata "
            f"normalization: {p4a_metadata_name}"
        )
    return requirements


def verify_wheel_filename(filename: str) -> None:
    """Reject the platform wheel shape that caused Build #7."""
    name = Path(filename).name
    if name != EXPECTED_UNIVERSAL_WHEEL:
        raise RuntimeError(
            "Expected the universal charset-normalizer wheel "
            f"{EXPECTED_UNIVERSAL_WHEEL!r}, got {name!r}"
        )
    if "-android_" in name or not name.endswith("-py3-none-any.whl"):
        raise RuntimeError(f"Wheel is not host-stageable: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", nargs="?", type=Path, default=Path("buildozer.spec"))
    parser.add_argument(
        "--wheel-name",
        default=EXPECTED_UNIVERSAL_WHEEL,
        help="Resolved wheel basename to validate",
    )
    args = parser.parse_args()
    requirements = verify_spec(args.spec)
    verify_wheel_filename(args.wheel_name)
    print(
        "Android Python dependency contract OK: "
        f"{PINNED_REQUIREMENT}; {len(requirements)} direct requirements"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
