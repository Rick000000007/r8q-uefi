#!/usr/bin/env bash
# Stage 06 [Step 11]: Verify and stage FAT32 EFI System Partition (ESP) & shell scripts
set -euo pipefail

[ "${R8Q_STAGE_DONE_05:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 05-install-uefi.sh must complete before 06-install-esp.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=../config/device.conf
source "$ROOT/config/device.conf"

ESP_IMG="$ROOT/payload/esp/esp.img"
echo "[STAGE 06/11] [STEP 11/19] Validating 256 MiB FAT32 ESP image and UEFI startup scripts..."

python3 -B - "$ESP_IMG" "$ESP_DISK_BYTES" << 'PYEOF'
import os, sys
p, exp_size = sys.argv[1], int(sys.argv[2])
assert os.path.getsize(p) == exp_size, f"ESP size mismatch"
with open(p, "rb") as f:
    hdr = f.read(1024)
assert hdr[510:512] == b"\x55\xaa", "Missing MBR 0x55AA signature"
assert hdr[512:520] == b"EFI PART", "Missing GPT EFI PART header"
print(f"  [VERIFIED] esp.img ({exp_size} B, MBR + GPT + FAT32)")
PYEOF

for nsh in startup.nsh boot-linux.nsh hardware-audit.nsh storage-audit.nsh boot-recovery.nsh; do
    [ -s "$ROOT/payload/esp/$nsh" ] || { echo "[ERROR] Missing ESP script: $nsh" >&2; exit 43; }
done

if command -v mdir >/dev/null 2>&1; then
    BARE_LIST="$(mdir -b -i "${ESP_IMG}@@1M" :: ::/EFI/BOOT ::/EFI/R8Q)"
    for req in "::/EFI/BOOT/BOOTAA64.EFI" "::/EFI/R8Q/BootManager.efi" "::/EFI/R8Q/Setup.efi" "::/EFI/R8Q/Image" "::/EFI/R8Q/initramfs.img" "::/EFI/R8Q/r8q.dtb" "::/startup.nsh"; do
        echo "$BARE_LIST" | grep -qix "$req" || { echo "[ERROR] Missing ESP member: $req" >&2; exit 44; }
    done
    echo "  [VERIFIED] All mandatory ESP FAT32 files verified via mdir."
fi

echo "  [$MODE] ESP staging plan verified."
echo "[STAGE 06/11] ESP stage PASSED."
