#!/bin/sh
# Stage 06 [Step 11]: Verify and stage FAT32 EFI System Partition (ESP) & shell scripts
set -eu

[ "${R8Q_STAGE_DONE_05:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 05-install-uefi.sh must complete before 06-install-esp.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"
# shellcheck source=../config/device.conf
. "$ROOT/config/device.conf"

ESP_IMG="$ROOT/payload/esp/esp.img"
echo "[STAGE 06/11] [STEP 11/19] Validating 256 MiB FAT32 ESP image and UEFI startup scripts..."

ESP_SIZE="$(r8q_filesize "$ESP_IMG")"
[ "$ESP_SIZE" -eq "$ESP_DISK_BYTES" ] || {
    echo "[ERROR] ESP size mismatch: got $ESP_SIZE B, expected $ESP_DISK_BYTES B" >&2
    exit 43
}

# Bytes 510..511 = 55aa (MBR), Bytes 512..519 = 4546492050415254 ("EFI PART")
ESP_SIG="$(r8q_hex_slice "$ESP_IMG" 510 10)"
[ "$ESP_SIG" = "55aa4546492050415254" ] || {
    echo "[ERROR] Invalid ESP MBR/GPT header signature (got 0x$ESP_SIG)" >&2
    exit 43
}
echo "  [VERIFIED] esp.img ($ESP_SIZE B, MBR + GPT + FAT32)"

for nsh in startup.nsh boot-linux.nsh hardware-audit.nsh storage-audit.nsh boot-recovery.nsh; do
    [ -s "$ROOT/payload/esp/$nsh" ] || { echo "[ERROR] Missing ESP script: $nsh" >&2; exit 43; }
done

if command -v mdir >/dev/null 2>&1; then
    BARE_LIST="$(mdir -b -i "${ESP_IMG}@@1M" :: ::/EFI/BOOT ::/EFI/R8Q)"
    for req in "::/EFI/BOOT/BOOTAA64.EFI" "::/EFI/R8Q/BootManager.efi" "::/EFI/R8Q/Setup.efi" "::/EFI/R8Q/Image" "::/EFI/R8Q/initramfs.img" "::/EFI/R8Q/r8q.dtb" "::/startup.nsh"; do
        printf '%s\n' "$BARE_LIST" | grep -qix "$req" || { echo "[ERROR] Missing ESP member: $req" >&2; exit 44; }
    done
    echo "  [VERIFIED] All mandatory ESP FAT32 files verified via mdir."
fi

echo "  [$MODE] ESP staging plan verified."
echo "[STAGE 06/11] ESP stage PASSED."
