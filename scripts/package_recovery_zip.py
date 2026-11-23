#!/usr/bin/env python3
"""
Project R8Q — Reproducible Recovery ZIP Packaging Utility
Packages R8Q-Debian12-Recovery.zip using r8q-uefi-boot-complete.img and recovery-installer template.
Zero block writes, zero physical device interaction.
"""

import os
import sys
import hashlib
import zipfile
import time

EXPECTED_BOOT_SHA256 = "b2d6f721fe52633e4bee4e1a626514fc5cbe166102803d8b6f0a5c581c5cb100"
EXPECTED_BOOT_SIZE = 24461312

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    boot_img = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo_root, "R8Q-DEBIAN12-RELEASE", "boot", "r8q-uefi-boot-complete.img")
    out_zip = sys.argv[2] if len(sys.argv) > 2 else os.path.join(repo_root, "R8Q-DEBIAN12-RELEASE", "R8Q-Debian12-Recovery.zip")
    template_dir = os.path.join(repo_root, "recovery-installer")

    if not os.path.isfile(boot_img):
        # Fallback to build/ if release dir not populated
        alt = os.path.join(repo_root, "build", "r8q-uefi-boot-complete.img")
        if os.path.isfile(alt):
            boot_img = alt
        else:
            print(f"Error: Boot image not found at {boot_img}", file=sys.stderr)
            sys.exit(1)

    print(f"Auditing boot container: {boot_img}")
    size = os.path.getsize(boot_img)
    if size != EXPECTED_BOOT_SIZE:
        print(f"Error: Size mismatch: {size} != {EXPECTED_BOOT_SIZE}", file=sys.stderr)
        sys.exit(1)

    csum = sha256_file(boot_img)
    if csum != EXPECTED_BOOT_SHA256:
        print(f"Error: SHA256 mismatch: {csum} != {EXPECTED_BOOT_SHA256}", file=sys.stderr)
        sys.exit(1)
    print(f"Boot container verified: SHA256={csum} (PASSED)")

    # Create reproducible zip archive
    print(f"Packaging {out_zip}...")
    fixed_time = (1980, 1, 1, 0, 0, 0)

    # Prepare files to add
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        # Add boot container
        info = zipfile.ZipInfo("r8q-uefi-boot-complete.img", date_time=fixed_time)
        info.external_attr = 0o644 << 16
        with open(boot_img, 'rb') as f:
            z.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED)

        # Add sha256 sum file
        info = zipfile.ZipInfo("r8q-uefi-boot-complete.img.sha256", date_time=fixed_time)
        info.external_attr = 0o644 << 16
        z.writestr(info, f"{EXPECTED_BOOT_SHA256}  r8q-uefi-boot-complete.img\n".encode('utf-8'), compress_type=zipfile.ZIP_DEFLATED)

        # Add template files
        template_files = [
            ("META-INF/com/google/android/update-binary", 0o755),
            ("META-INF/com/google/android/updater-script", 0o644),
            ("META-INF/com/android/metadata", 0o644),
        ]
        for rel_path, mode in template_files:
            full_path = os.path.join(template_dir, rel_path)
            info = zipfile.ZipInfo(rel_path, date_time=fixed_time)
            info.external_attr = mode << 16
            with open(full_path, 'rb') as f:
                z.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED)

    zip_csum = sha256_file(out_zip)
    zip_size = os.path.getsize(out_zip)
    print(f"Successfully packaged {out_zip}: size={zip_size} bytes, SHA256={zip_csum}")

if __name__ == "__main__":
    main()
