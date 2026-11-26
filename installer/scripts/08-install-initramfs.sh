#!/bin/sh
# Stage 08 [Step 13]: Verify and stage early-userspace initramfs & kernel modules
set -eu

[ "${R8Q_STAGE_DONE_07:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 07-install-kernel.sh must complete before 08-install-initramfs.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"

INITRAMFS="$ROOT/payload/initramfs/initramfs.img"
echo "[STAGE 08/11] [STEP 13/19] Validating initramfs CPIO archive, ARM64 glibc, and kernel modules..."

CPIO_MAGIC="$(gzip -dc "$INITRAMFS" 2>/dev/null | dd bs=1 count=6 2>/dev/null | od -An -tx1 -v | tr -d ' \t\r\n')"
[ "$CPIO_MAGIC" = "303730373031" ] || {
    echo "[ERROR] Invalid CPIO newc magic (expected 070701, got 0x$CPIO_MAGIC)" >&2
    exit 44
}

CPIO_BYTES="$(gzip -dc "$INITRAMFS" | wc -c | tr -d ' \t\r\n')"
[ "$CPIO_BYTES" -gt 1048576 ] || {
    echo "[ERROR] Initramfs CPIO unexpectedly small: $CPIO_BYTES bytes" >&2
    exit 44
}

TMP_LIST="$(mktemp "${TMPDIR:-/tmp}/r8q_cpio_XXXXXX")"
trap 'rm -f "$TMP_LIST"' EXIT INT TERM
gzip -dc "$INITRAMFS" | cpio -t 2>/dev/null | sed 's|^\./||' > "$TMP_LIST"

for req in \
    init \
    bin/busybox \
    lib/ld-linux-aarch64.so.1 \
    lib/libc.so.6 \
    lib/modules/virtio_blk.ko \
    lib/modules/ext4.ko \
    lib/modules/jbd2.ko \
    lib/modules/mbcache.ko \
    lib/modules/crc16.ko; do
    grep -Fxq "$req" "$TMP_LIST" || {
        echo "[ERROR] Initramfs missing required member: $req" >&2
        exit 44
    }
done

echo "  [VERIFIED] initramfs.img ($CPIO_BYTES B uncompressed CPIO, glibc + 5+ storage/fs modules)"
echo "  [$MODE] Initramfs staging plan verified."
echo "[STAGE 08/11] Initramfs stage PASSED."
