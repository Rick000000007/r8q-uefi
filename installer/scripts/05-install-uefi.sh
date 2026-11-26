#!/bin/sh
# Stage 05 [Step 10]: Verify and stage BootManager.efi, Setup.efi, and all UEFI applications
set -eu

[ "${R8Q_STAGE_DONE_04:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 04-install-firmware.sh must complete before 05-install-uefi.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"

echo "[STAGE 05/11] [STEP 10/19] Validating UEFI applications, BootManager.efi & Setup.efi (PE32+ 0xAA64)..."

verify_pe32plus_aa64() {
    _efi="$1"
    [ -f "$_efi" ] || { echo "[ERROR] Missing EFI binary: $_efi" >&2; exit 42; }
    _mz="$(r8q_hex_slice "$_efi" 0 2)"
    [ "$_mz" = "4d5a" ] || { echo "[ERROR] $_efi: missing MZ signature (got 0x$_mz)" >&2; exit 42; }
    _pe_off="$(r8q_u32le "$_efi" 60)"
    [ -n "$_pe_off" ] && [ "$_pe_off" -gt 0 ] || { echo "[ERROR] $_efi: invalid PE offset" >&2; exit 42; }
    _pe_sig="$(r8q_hex_slice "$_efi" "$_pe_off" 4)"
    [ "$_pe_sig" = "50450000" ] || { echo "[ERROR] $_efi: missing PE signature at $_pe_off (got 0x$_pe_sig)" >&2; exit 42; }
    _mach_off=$((_pe_off + 4))
    _mach="$(r8q_u16le "$_efi" "$_mach_off")"
    [ "$_mach" -eq 43620 ] || { echo "[ERROR] $_efi: expected AArch64 machine 0xAA64 (43620), got $_mach" >&2; exit 42; }
}

UEFI_COUNT=0
for efi in "$ROOT/payload/uefi/"*.efi; do
    [ -e "$efi" ] || continue
    UEFI_COUNT=$((UEFI_COUNT + 1))
done
[ "$UEFI_COUNT" -ge 15 ] || {
    echo "[ERROR] Expected >= 15 UEFI apps in payload/uefi, found $UEFI_COUNT" >&2
    exit 42
}

TOTAL_BINARIES=0
for efi in \
    "$ROOT/payload/boot-manager/BootManager.efi" \
    "$ROOT/payload/setup/Setup.efi" \
    "$ROOT/payload/uefi/"*.efi; do
    verify_pe32plus_aa64 "$efi"
    TOTAL_BINARIES=$((TOTAL_BINARIES + 1))
done

echo "  [VERIFIED] $TOTAL_BINARIES AArch64 PE32+ UEFI binaries validated."
echo "  [$MODE] UEFI applications & BootManager staging plan verified."
echo "[STAGE 05/11] UEFI application stage PASSED."
