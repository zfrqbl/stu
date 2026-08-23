"""Vendor Alpine.js into static/vendor for offline local-first usage."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ALPINE_VERSION = "3.14.1"
ALPINE_URL = f"https://cdn.jsdelivr.net/npm/alpinejs@{ALPINE_VERSION}/dist/cdn.min.js"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    vendor_dir = root / "static" / "vendor"
    target = vendor_dir / "alpine.min.js"

    vendor_dir.mkdir(parents=True, exist_ok=True)

    if target.exists() and "--force" not in sys.argv:
        print(f"Alpine.js already exists: {target}")
        return 0

    print(f"Downloading Alpine.js {ALPINE_VERSION}...")
    response = requests.get(ALPINE_URL, timeout=60)
    response.raise_for_status()

    target.write_bytes(response.content)
    print(f"Saved Alpine.js to: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
