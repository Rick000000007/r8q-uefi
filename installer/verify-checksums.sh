#!/usr/bin/env bash
# Project R8Q — Unified Package Cryptographic Checksum & Payload Completeness Verifier
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_JSON="$SCRIPT_DIR/manifests/MANIFEST.json"
CHECKSUM_FILE="$SCRIPT_DIR/manifests/SHA256SUMS"

if [ ! -f "$MANIFEST_JSON" ]; then
    echo "[ERROR] Missing manifest file: $MANIFEST_JSON" >&2
    exit 1
fi
if [ ! -f "$CHECKSUM_FILE" ]; then
    echo "[ERROR] Missing checksum manifest: $CHECKSUM_FILE" >&2
    exit 1
fi

echo "[VERIFY-CHECKSUMS] Checking every payload and manifest entry in $SCRIPT_DIR..."

python3 -B - "$SCRIPT_DIR" "$MANIFEST_JSON" "$CHECKSUM_FILE" << 'PYEOF'
import hashlib
import json
import os
import sys

root_dir, manifest_path, sha_path = sys.argv[1:4]

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

declared = {item["path"]: item for item in manifest.get("files", [])}
if not declared:
    print("[ERROR] MANIFEST.json has no declared files", file=sys.stderr)
    sys.exit(1)

checksum_entries = {}
with open(sha_path, "r", encoding="utf-8") as f:
    for line_no, raw in enumerate(f, start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            print(f"[ERROR] Malformed SHA256SUMS line {line_no}: {raw!r}", file=sys.stderr)
            sys.exit(1)
        checksum_entries[parts[1].lstrip("*").strip()] = parts[0].lower()

required_groups = [
    "install.sh",
    "uninstall-or-rollback.sh",
    "verify-device.sh",
    "verify-checksums.sh",
    "config/device.conf",
    "config/partition-map.conf",
    "config/boot.conf",
    "payload/firmware/R8Q_EFI.fd",
    "payload/firmware/r8q-uefi-boot-complete.img",
    "payload/boot-manager/BootManager.efi",
    "payload/setup/Setup.efi",
    "payload/uefi/Shell.efi",
    "payload/uefi/LinuxBoot.efi",
    "payload/esp/esp.img",
    "payload/esp/startup.nsh",
    "payload/kernel/Image",
    "payload/dtb/sm8250-samsung-r8q.dtb",
    "payload/dtb/r8q.dtb",
    "payload/initramfs/initramfs.img",
    "payload/debian-rootfs/r8q-rootfs.ext4.gz",
    "payload/debian-rootfs/r8q-rootfs.tar.gz",
    "manifests/MANIFEST.json",
    "INSTALL.md",
    "VERSION",
]
for i in range(1, 12):
    matches = [p for p in declared if p.startswith(f"scripts/{i:02d}-")]
    if len(matches) != 1:
        print(f"[ERROR] Missing or ambiguous step script {i:02d} in MANIFEST.json: {matches}", file=sys.stderr)
        sys.exit(1)

for req in required_groups:
    if req not in checksum_entries:
        print(f"[ERROR] Missing mandatory package file in SHA256SUMS: {req}", file=sys.stderr)
        sys.exit(1)
    if req != "manifests/MANIFEST.json" and req not in declared:
        print(f"[ERROR] Missing mandatory package file in MANIFEST.json: {req}", file=sys.stderr)
        sys.exit(1)

missing = sorted(set(declared.keys()) - set(checksum_entries.keys()))
if missing:
    print(f"[ERROR] Files in MANIFEST.json missing from SHA256SUMS: {missing}", file=sys.stderr)
    sys.exit(1)

verified = 0
for rel, expected_sha in sorted(checksum_entries.items()):
    full_path = os.path.join(root_dir, rel)
    if not os.path.isfile(full_path):
        print(f"[ERROR] Missing payload file: {rel}", file=sys.stderr)
        sys.exit(1)
    size = os.path.getsize(full_path)
    if size == 0:
        print(f"[ERROR] Zero-byte file detected: {rel}", file=sys.stderr)
        sys.exit(1)
    h = hashlib.sha256()
    with open(full_path, "rb") as fh:
        while chunk := fh.read(65536):
            h.update(chunk)
    actual_sha = h.hexdigest()
    if actual_sha != expected_sha:
        print(f"[ERROR] Checksum mismatch for {rel}: expected {expected_sha}, got {actual_sha}", file=sys.stderr)
        sys.exit(1)
    if rel in declared:
        if declared[rel]["sha256"] != actual_sha or declared[rel]["size_bytes"] != size:
            print(f"[ERROR] MANIFEST.json metadata mismatch for {rel}", file=sys.stderr)
            sys.exit(1)
    verified += 1

print(f"[PASS] Verified SHA-256 digests and sizes for all {verified} files in package.")
PYEOF
