#!/bin/sh
# Stage 04 [Step 9]: Verify and stage EDK II firmware components (R8Q_EFI.fd & boot container)
set -eu

[ "${R8Q_STAGE_DONE_03:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 03-prepare-target.sh must complete before 04-install-firmware.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"
# shellcheck source=../config/device.conf
. "$ROOT/config/device.conf"

FD_PATH="$ROOT/payload/firmware/R8Q_EFI.fd"
BOOT_PATH="$ROOT/payload/firmware/r8q-uefi-boot-complete.img"

echo "[STAGE 04/11] [STEP 9/19] Inspecting and staging verified UEFI firmware components..."

FD_SIZE="$(r8q_filesize "$FD_PATH")"
[ "$FD_SIZE" -eq "$FIRMWARE_VOLUME_BYTES" ] || {
    echo "[ERROR] Unexpected R8Q_EFI.fd size: $FD_SIZE B != $FIRMWARE_VOLUME_BYTES B" >&2
    exit 41
}
FVH_HEX="$(r8q_hex_slice "$FD_PATH" 40 4)"
[ "$FVH_HEX" = "5f465648" ] || {
    echo "[ERROR] R8Q_EFI.fd missing EDK II _FVH signature (got 0x$FVH_HEX)" >&2
    exit 41
}

BOOT_SIZE="$(r8q_filesize "$BOOT_PATH")"
[ "$BOOT_SIZE" -le "$COMPOUND_BOOT_MAX_BYTES" ] || {
    echo "[ERROR] Compound boot image ($BOOT_SIZE B) exceeds limit ($COMPOUND_BOOT_MAX_BYTES B)" >&2
    exit 41
}
BOOT_MAGIC_HEX="$(r8q_hex_slice "$BOOT_PATH" 0 8)"
[ "$BOOT_MAGIC_HEX" = "414e44524f494421" ] || {
    echo "[ERROR] Invalid compound boot container magic (expected ANDROID!, got 0x$BOOT_MAGIC_HEX)" >&2
    exit 41
}
HDR_VER="$(r8q_u32le "$BOOT_PATH" 40)"
[ "$HDR_VER" -eq 2 ] || {
    echo "[ERROR] Expected Android Boot Image v2, got version $HDR_VER" >&2
    exit 41
}

echo "  [VERIFIED] R8Q_EFI.fd ($FD_SIZE B, _FVH) + r8q-uefi-boot-complete.img ($BOOT_SIZE B, ANDROID! v2)"
echo "  [$MODE] Firmware staging plan verified (0 raw flash writes)."
echo "[STAGE 04/11] Firmware stage PASSED."
