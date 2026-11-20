#!/usr/bin/env python3
"""
Project R8Q UEFI: SHA256 Manifest Generator
Generates reproducible SHA256 checksums and metadata for all project artifacts.
Enforces Security Policy: Excludes private keys and security-sensitive credentials.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone

PROJECT_ROOT = "/root/r8q-uefi"
MANIFEST_DIR = os.path.join(PROJECT_ROOT, "manifests")

# Security cleanup policy: Never include private cryptographic keys or credentials in release manifests
EXCLUDED_PATTERNS = [
    "_id_ed25519",
    "_id_rsa",
    "_id_ecdsa",
    ".priv",
    ".key",
    "id_ed25519",
    "id_rsa"
]

def is_excluded(filename):
    for pat in EXCLUDED_PATTERNS:
        if pat in filename and not filename.endswith(".pub"):
            return True
    return False

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
        "security_policy": "Strict zero-private-key credential isolation",
        "files": []
    }

    scan_dirs = ["docs", "config", "shell/scripts", "scripts", "tests", "platform", "devicetree", "build"]
    for d in scan_dirs:
        dirpath = os.path.join(PROJECT_ROOT, d)
        if not os.path.exists(dirpath):
            continue
        for root, _, files in os.walk(dirpath):
            for file in sorted(files):
                if is_excluded(file):
                    continue
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, PROJECT_ROOT)
                size = os.path.getsize(filepath)
                sha256 = compute_sha256(filepath)
                manifest["files"].append({
                    "path": relpath,
                    "size_bytes": size,
                    "sha256": sha256
                })

    target_name = sys.argv[1] if len(sys.argv) > 1 else "phase3_manifest.json"
    if not target_name.endswith(".json"):
        target_name += ".json"

    out_file = os.path.join(MANIFEST_DIR, target_name)
    with open(out_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest generated successfully with {len(manifest['files'])} files (private keys excluded).")
    print(f"Saved to: {out_file}")

if __name__ == "__main__":
    main()

