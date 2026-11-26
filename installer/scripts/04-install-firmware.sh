#!/usr/bin/env bash
# Stage 04 [Step 9]: Verify and stage EDK II firmware components (R8Q_EFI.fd & boot container)
set -euo pipefail

[ "${R8Q_STAGE_DONE_03:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 03-prepare-target.sh must complete before 04-install-firmware.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=../config/device.conf
source "$ROOT/config/device.conf"

echo "[STAGE 04/11] [STEP 9/19] Inspecting and staging verified UEFI firmware components..."
python3 -B - "$ROOT/payload/firmware/R8Q_EFI.fd" "$ROOT/payload/firmware/r8q-uefi-boot-complete.img" "$FIRMWARE_VOLUME_BYTES" "$COMPOUND_BOOT_MAX_BYTES" << 'PYEOF'
import os, struct, sys

fd_path, boot_path, exp_fd_size, max_boot_size = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
assert os.path.getsize(fd_path) == exp_fd_size, f"Unexpected R8Q_EFI.fd size"
with open(fd_path, "rb") as f:
    hdr = f.read(64)
assert hdr[0x28:0x2C] == b"_FVH", "R8Q_EFI.fd missing EDK II _FVH signature"

boot_size = os.path.getsize(boot_path)
assert boot_size <= max_boot_size, f"Compound boot image ({boot_size} B) exceeds limit ({max_boot_size} B)"
with open(boot_path, "rb") as f:
    bhdr = f.read(1660)
assert bhdr[:8] == b"ANDROID!", "Invalid compound boot container magic"
assert struct.unpack_from("<I", bhdr, 40)[0] == 2, "Expected Android Boot Image v2"
print(f"  [VERIFIED] R8Q_EFI.fd ({exp_fd_size} B, _FVH) + r8q-uefi-boot-complete.img ({boot_size} B, ANDROID! v2)")
PYEOF

echo "  [$MODE] Firmware staging plan verified (0 raw flash writes)."
echo "[STAGE 04/11] Firmware stage PASSED."
