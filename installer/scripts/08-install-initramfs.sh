#!/usr/bin/env bash
# Stage 08 [Step 13]: Verify and stage early-userspace initramfs & kernel modules
set -euo pipefail

[ "${R8Q_STAGE_DONE_07:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 07-install-kernel.sh must complete before 08-install-initramfs.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"

echo "[STAGE 08/11] [STEP 13/19] Validating initramfs CPIO archive, ARM64 glibc, and kernel modules..."
python3 -B - "$ROOT/payload/initramfs/initramfs.img" << 'PYEOF'
import gzip, sys

with gzip.open(sys.argv[1], "rb") as gz:
    cpio = gz.read()
assert len(cpio) > 1024 * 1024, f"Initramfs CPIO unexpectedly small: {len(cpio)} bytes"

names = set()
pos = 0
while pos + 110 <= len(cpio):
    assert cpio[pos:pos + 6] == b"070701", f"Invalid CPIO magic at {pos}"
    fsize = int(cpio[pos + 54:pos + 62], 16)
    nsize = int(cpio[pos + 94:pos + 102], 16)
    nstart = pos + 110
    nend = nstart + nsize
    name = cpio[nstart:nend - 1].decode("utf-8", errors="replace").lstrip("./") or "."
    if name == "TRAILER!!!":
        break
    names.add(name)
    dstart = (nend + 3) & ~3
    pos = (dstart + fsize + 3) & ~3

for req in [
    "init",
    "bin/busybox",
    "lib/ld-linux-aarch64.so.1",
    "lib/libc.so.6",
    "lib/modules/virtio_blk.ko",
    "lib/modules/ext4.ko",
    "lib/modules/jbd2.ko",
    "lib/modules/mbcache.ko",
    "lib/modules/crc16.ko",
]:
    assert req in names, f"Initramfs missing required member: {req}"
print(f"  [VERIFIED] initramfs.img ({len(cpio)} B uncompressed CPIO, glibc + 5+ storage/fs modules)")
PYEOF

echo "  [$MODE] Initramfs staging plan verified."
echo "[STAGE 08/11] Initramfs stage PASSED."
