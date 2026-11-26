#!/usr/bin/env bash
# Stage 09 [Step 14]: Verify and stage Debian 12 ARM64 root filesystem (MicroSD / non-destructive target)
set -euo pipefail

[ "${R8Q_STAGE_DONE_08:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 08-install-initramfs.sh must complete before 09-install-rootfs.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=../config/partition-map.conf
source "$ROOT/config/partition-map.conf"

EXT4_GZ="$ROOT/payload/debian-rootfs/r8q-rootfs.ext4.gz"
ROOTFS_TAR="$ROOT/payload/debian-rootfs/r8q-rootfs.tar.gz"

echo "[STAGE 09/11] [STEP 14/19] Validating Debian 12 ARM64 rootfs ext4 & FHS tarball..."
python3 -B - "$EXT4_GZ" "$ROOTFS_TAR" << 'PYEOF'
import gzip, os, sys, tarfile

ext4_gz, rootfs_tar = sys.argv[1], sys.argv[2]
with gzip.open(ext4_gz, "rb") as gz:
    hdr = gz.read(2048)
assert len(hdr) >= 1024 + 0x3A and hdr[1024 + 0x38:1024 + 0x3A] == b"\x53\xef", "Invalid ext4 superblock magic"

assert os.path.getsize(rootfs_tar) > 30 * 1024 * 1024, "Rootfs tarball unexpectedly small"
with tarfile.open(rootfs_tar, "r:gz") as tar:
    members = {m.name.lstrip("./"): m for m in tar}
for req in ["bin/bash", "usr/bin/apt", "etc/sudoers.d/r8q"]:
    assert req in members, f"Rootfs tarball missing required member: {req}"
print("  [VERIFIED] r8q-rootfs.ext4.gz (0xEF53) and r8q-rootfs.tar.gz validated.")
PYEOF

echo "  [$MODE] Debian 12 ARM64 rootfs target policy: external MicroSD (LABEL=$DEFAULT_ROOTFS_LABEL); internal UFS preserved."
echo "[STAGE 09/11] Debian rootfs stage PASSED."
