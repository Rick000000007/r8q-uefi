#!/bin/sh
# Stage 07 [Step 12]: Verify and stage ARM64 EFI Stub Linux Kernel & SM8250 Device Trees
set -eu

[ "${R8Q_STAGE_DONE_06:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 06-install-esp.sh must complete before 07-install-kernel.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"

echo "[STAGE 07/11] [STEP 12/19] Validating ARM64 Linux kernel and matching SM8250 DTBs..."

IMG_PATH="$ROOT/payload/kernel/Image"
IMG_MZ="$(r8q_hex_slice "$IMG_PATH" 0 2)"
IMG_ARM64="$(r8q_hex_slice "$IMG_PATH" 56 4)"
[ "$IMG_MZ" = "4d5a" ] && [ "$IMG_ARM64" = "41524d64" ] || {
    echo "[ERROR] Invalid ARM64 EFI stub kernel Image (mz=0x$IMG_MZ, magic=0x$IMG_ARM64)" >&2
    exit 44
}

for dtb_name in sm8250-samsung-r8q.dtb r8q.dtb; do
    dtb_path="$ROOT/payload/dtb/$dtb_name"
    [ -f "$dtb_path" ] || { echo "[ERROR] Missing DTB: $dtb_path" >&2; exit 44; }
    actual_len="$(r8q_filesize "$dtb_path")"
    fdt_magic="$(r8q_hex_slice "$dtb_path" 0 4)"
    fdt_size="$(r8q_u32be "$dtb_path" 4)"
    fdt_ver="$(r8q_u32be "$dtb_path" 20)"
    [ "$fdt_magic" = "d00dfeed" ] || { echo "[ERROR] $dtb_name: invalid FDT magic 0x$fdt_magic" >&2; exit 44; }
    [ "$fdt_ver" -eq 17 ] || { echo "[ERROR] $dtb_name: expected FDT version 17, got $fdt_ver" >&2; exit 44; }
    [ "$fdt_size" -eq "$actual_len" ] || { echo "[ERROR] $dtb_name: FDT size mismatch ($fdt_size != $actual_len)" >&2; exit 44; }
done

echo '  [VERIFIED] Kernel Image (ARM\x64 EFI Stub) and SM8250 FDT v17 DTBs validated.'
echo "  [$MODE] Kernel and DTB staging plan verified."
echo "[STAGE 07/11] Kernel & DTB stage PASSED."
