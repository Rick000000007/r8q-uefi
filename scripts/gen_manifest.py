#!/usr/bin/env python3
"""
Project R8Q UEFI: SHA256 Manifest Generator
Generates reproducible SHA256 checksums and metadata for all project artifacts.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone

PROJECT_ROOT = "/root/r8q-uefi"
MANIFEST_DIR = os.path.join(PROJECT_ROOT, "manifests")

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    manifest = {
        "project": "Project R8Q UEFI",
        "device": "Samsung Galaxy S20 FE 5G (SM-G781B)",
        "codename": "r8q",
        "soc": "Qualcomm Snapdragon 865 (SM8250)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": []
    }

    scan_dirs = ["docs", "config", "shell/scripts", "scripts", "devicetree"]
    for d in scan_dirs:
        dirpath = os.path.join(PROJECT_ROOT, d)
        if not os.path.exists(dirpath):
            continue
        for root, _, files in os.walk(dirpath):
            for file in sorted(files):
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, PROJECT_ROOT)
                size = os.path.getsize(filepath)
                sha256 = compute_sha256(filepath)
                manifest["files"].append({
                    "path": relpath,
                    "size_bytes": size,
                    "sha256": sha256
                })

    out_file = os.path.join(MANIFEST_DIR, "milestone1_manifest.json")
    with open(out_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest generated successfully with {len(manifest['files'])} files.")
    print(f"Saved to: {out_file}")

if __name__ == "__main__":
    main()
