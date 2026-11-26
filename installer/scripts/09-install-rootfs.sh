#!/bin/sh
# Stage 09 [Step 14]: Verify and stage Debian 12 ARM64 root filesystem (MicroSD / non-destructive target)
set -eu

[ "${R8Q_STAGE_DONE_08:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 08-install-initramfs.sh must complete before 09-install-rootfs.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"
# shellcheck source=../config/partition-map.conf
. "$ROOT/config/partition-map.conf"

EXT4_GZ="$ROOT/payload/debian-rootfs/r8q-rootfs.ext4.gz"
ROOTFS_TAR="$ROOT/payload/debian-rootfs/r8q-rootfs.tar.gz"

echo "[STAGE 09/11] [STEP 14/19] Validating Debian 12 ARM64 rootfs ext4 & FHS tarball..."

EXT4_MAGIC="$(gzip -dc "$EXT4_GZ" 2>/dev/null | dd bs=1 skip=1080 count=2 2>/dev/null | od -An -tx1 -v | tr -d ' \t\r\n')"
[ "$EXT4_MAGIC" = "53ef" ] || {
    echo "[ERROR] Invalid ext4 superblock magic (expected 53ef, got 0x$EXT4_MAGIC)" >&2
    exit 45
}

TAR_SIZE="$(r8q_filesize "$ROOTFS_TAR")"
[ "$TAR_SIZE" -gt 31457280 ] || {
    echo "[ERROR] Rootfs tarball unexpectedly small ($TAR_SIZE B)" >&2
    exit 45
}

TMP_TARLIST="$(mktemp "${TMPDIR:-/tmp}/r8q_tar_XXXXXX")"
trap 'rm -f "$TMP_TARLIST"' EXIT INT TERM
tar -ztf "$ROOTFS_TAR" | sed 's|^\./||' > "$TMP_TARLIST"

for req in bin/bash usr/bin/apt etc/sudoers.d/r8q; do
    grep -Fxq "$req" "$TMP_TARLIST" || {
        echo "[ERROR] Rootfs tarball missing required member: $req" >&2
        exit 45
    }
done

echo "  [VERIFIED] r8q-rootfs.ext4.gz (0xEF53) and r8q-rootfs.tar.gz validated."
echo "  [$MODE] Debian 12 ARM64 rootfs target policy: external MicroSD (LABEL=$DEFAULT_ROOTFS_LABEL); internal UFS preserved."
echo "[STAGE 09/11] Debian rootfs stage PASSED."
