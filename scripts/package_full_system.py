#!/usr/bin/env python3
"""
Project R8Q — Reproducible Full System Distribution Packager
Packages R8Q-Debian12-Full-System.tar.gz with normalized mtime, permissions, and order
so that it produces a 100% bit-exact SHA-256 digest on any build machine.
"""

import os
import sys
import hashlib
import tarfile
import gzip

FIXED_EPOCH = 315532800  # 1980-01-01 00:00:00 UTC

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    release_dir = os.path.join(repo_root, "R8Q-DEBIAN12-RELEASE")
    out_tar = os.path.join(release_dir, "R8Q-Debian12-Full-System.tar.gz")

    print("==========================================================")
    print("   PROJECT R8Q: REPRODUCIBLE FULL SYSTEM PACKAGER")
    print("==========================================================")

    # Required files to package: relative source path -> archive relative path
    payloads = [
        ("README.md", "R8Q-Debian12-Full-System/README.md"),
        ("INSTALLATION.md", "R8Q-Debian12-Full-System/INSTALLATION.md"),
        ("INSTALLATION-USB.md", "R8Q-Debian12-Full-System/INSTALLATION-USB.md"),
        ("INSTALLER-AUDIT.md", "R8Q-Debian12-Full-System/INSTALLER-AUDIT.md"),
        ("BOOT-ARCHITECTURE.md", "R8Q-Debian12-Full-System/BOOT-ARCHITECTURE.md"),
        ("HARDWARE-COMPATIBILITY.md", "R8Q-Debian12-Full-System/HARDWARE-COMPATIBILITY.md"),
        ("PARTITION-LAYOUT.md", "R8Q-Debian12-Full-System/PARTITION-LAYOUT.md"),
        ("RECOVERY.md", "R8Q-Debian12-Full-System/RECOVERY.md"),
        ("TROUBLESHOOTING.md", "R8Q-Debian12-Full-System/TROUBLESHOOTING.md"),
        ("SHA256SUMS-RECOVERY-ZIP.txt", "R8Q-Debian12-Full-System/SHA256SUMS-RECOVERY-ZIP.txt"),
        ("R8Q-Debian12-Recovery.zip", "R8Q-Debian12-Full-System/R8Q-Debian12-Recovery.zip"),
        ("boot/r8q-uefi-boot-complete.img", "R8Q-Debian12-Full-System/boot/r8q-uefi-boot-complete.img"),
        ("boot/esp.img", "R8Q-Debian12-Full-System/boot/esp.img"),
        ("firmware/R8Q_EFI.fd", "R8Q-Debian12-Full-System/firmware/R8Q_EFI.fd"),
        ("kernel/Image", "R8Q-Debian12-Full-System/kernel/Image"),
        ("kernel/sm8250-samsung-r8q.dtb", "R8Q-Debian12-Full-System/kernel/sm8250-samsung-r8q.dtb"),
        ("kernel/initramfs.img", "R8Q-Debian12-Full-System/kernel/initramfs.img"),
        ("rootfs/r8q-rootfs.ext4.gz", "R8Q-Debian12-Full-System/rootfs/r8q-rootfs.ext4.gz"),
    ]

    # Verify all source files exist
    for src_rel, _ in payloads:
        full_src = os.path.join(release_dir, src_rel)
        if not os.path.isfile(full_src):
            print(f"Error: Missing required payload: {full_src}", file=sys.stderr)
            sys.exit(1)

    # Sort payloads alphabetically by archive path for deterministic order
    payloads.sort(key=lambda x: x[1])

    # Distinct directory entries needed
    dirs_needed = sorted(list(set(os.path.dirname(p[1]) for p in payloads if os.path.dirname(p[1]))))

    print(f"Packaging {out_tar} with normalized timestamps (1980-01-01 UTC)...")
    with open(out_tar, 'wb') as f_out:
        with gzip.GzipFile(filename='', mode='wb', fileobj=f_out, mtime=0.0) as gz_out:
            with tarfile.open(mode='w', fileobj=gz_out) as tar:
                # Add directories first
                for d in dirs_needed:
                    ti = tarfile.TarInfo(name=d)
                    ti.type = tarfile.DIRTYPE
                    ti.mode = 0o755
                    ti.mtime = FIXED_EPOCH
                    ti.uid = 0
                    ti.gid = 0
                    ti.uname = ''
                    ti.gname = ''
                    tar.addfile(ti)

                # Add files
                for src_rel, arc_path in payloads:
                    full_src = os.path.join(release_dir, src_rel)
                    size = os.path.getsize(full_src)
                    ti = tarfile.TarInfo(name=arc_path)
                    ti.type = tarfile.REGTYPE
                    ti.size = size
                    ti.mode = 0o644
                    ti.mtime = FIXED_EPOCH
                    ti.uid = 0
                    ti.gid = 0
                    ti.uname = ''
                    ti.gname = ''
                    with open(full_src, 'rb') as f_in:
                        tar.addfile(ti, f_in)
                    print(f"  Added {arc_path} ({size} bytes)")

    tar_size = os.path.getsize(out_tar)
    tar_sha = sha256_file(out_tar)
    print("==========================================================")
    print("   REPRODUCIBLE FULL SYSTEM PACKAGE READY")
    print(f"   Size:   {tar_size} bytes")
    print(f"   SHA256: {tar_sha}")
    print("==========================================================")

if __name__ == "__main__":
    main()
