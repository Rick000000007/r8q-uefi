#!/usr/bin/env bash
# Project R8Q UEFI: EFI System Partition (ESP) Disk Generator
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q) & QEMU virt
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
OUTPUT_ESP="$BUILD_DIR/esp.img"
EDK2_BIN_DIR="$PROJECT_ROOT/edk2/Build/R8Q/DEBUG_GCC5/AARCH64"
ESP_SIZE_MB=256

echo "================================================================="
echo "   PROJECT R8Q: EFI SYSTEM PARTITION (ESP) DISK GENERATOR"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B) & QEMU virt"
echo "================================================================="

mkdir -p "$BUILD_DIR"
rm -f "$OUTPUT_ESP"

# 1. Allocate raw zero-filled image
echo "[ESP] Allocating ${ESP_SIZE_MB} MiB disk image..."
dd if=/dev/zero of="$OUTPUT_ESP" bs=1M count="$ESP_SIZE_MB" status=none

# 2. Format with GPT partition table and FAT32 filesystem
echo "[ESP] Creating GPT partition table and formatting FAT32 ESP..."
parted -s "$OUTPUT_ESP" mklabel gpt mkpart ESP fat32 1MiB 100% set 1 esp on
mkfs.vfat --offset=2048 -F 32 -n "R8Q_BOOT" "$OUTPUT_ESP"

TARGET_PART="$OUTPUT_ESP@@1M"

# 3. Create directory structure using mtools
echo "[ESP] Creating EFI directory structure..."
mmd -i "$TARGET_PART" ::EFI
mmd -i "$TARGET_PART" ::EFI/BOOT
mmd -i "$TARGET_PART" ::EFI/R8Q
mmd -i "$TARGET_PART" ::EFI/R8Q/Config
mmd -i "$TARGET_PART" ::EFI/R8Q/Config/entries
mmd -i "$TARGET_PART" ::EFI/R8Q/Kernels
mmd -i "$TARGET_PART" ::EFI/tools

# 4. Install R8Q Boot Manager & Fallback Shell (BOOTAA64.EFI)
if [ -f "$EDK2_BIN_DIR/BootManager.efi" ]; then
    echo "[ESP] Installing R8Q Boot Manager to ::EFI/BOOT/BOOTAA64.EFI and ::EFI/R8Q/BootManager.efi..."
    mcopy -i "$TARGET_PART" "$EDK2_BIN_DIR/BootManager.efi" ::EFI/BOOT/BOOTAA64.EFI
    mcopy -i "$TARGET_PART" "$EDK2_BIN_DIR/BootManager.efi" ::EFI/R8Q/BootManager.efi
elif [ -f "$EDK2_BIN_DIR/Shell.efi" ]; then
    echo "[ESP] Installing UEFI Shell to ::EFI/BOOT/BOOTAA64.EFI..."
    mcopy -i "$TARGET_PART" "$EDK2_BIN_DIR/Shell.efi" ::EFI/BOOT/BOOTAA64.EFI
fi

if [ -f "$EDK2_BIN_DIR/Shell.efi" ]; then
    mcopy -i "$TARGET_PART" "$EDK2_BIN_DIR/Shell.efi" ::EFI/R8Q/Shell.efi
fi

# 5. Copy custom R8Q EFI applications and Setup Utility
echo "[ESP] Installing custom R8Q EFI applications..."
for app in Setup BootManager sysinfo cpuinfo memmap diagnostics LinuxBoot storage display battery thermal fdtinfo firmware CoreTest StorageTest; do
    if [ -f "$EDK2_BIN_DIR/${app}.efi" ]; then
        mcopy -i "$TARGET_PART" "$EDK2_BIN_DIR/${app}.efi" "::EFI/R8Q/${app}.efi"
        mcopy -i "$TARGET_PART" "$EDK2_BIN_DIR/${app}.efi" "::EFI/tools/${app}.efi"
    fi
done

# Copy Boot Manager Configurations
if [ -d "$PROJECT_ROOT/boot-manager/Config" ]; then
    echo "[ESP] Installing R8Q Boot Manager configuration files..."
    mcopy -i "$TARGET_PART" "$PROJECT_ROOT/boot-manager/Config/boot.cfg" ::EFI/R8Q/Config/boot.cfg || true
    for conf in "$PROJECT_ROOT/boot-manager/Config/entries"/*.conf; do
        [ -f "$conf" ] && mcopy -i "$TARGET_PART" "$conf" "::EFI/R8Q/Config/entries/$(basename "$conf")" || true
    done
fi

# 6. Copy Kernel, Initramfs, and Device Tree
echo "[ESP] Installing Linux Kernel, Initramfs, and DTB..."
if [ -f "$BUILD_DIR/Image" ]; then
    mcopy -i "$TARGET_PART" "$BUILD_DIR/Image" ::EFI/R8Q/Image
    mcopy -i "$TARGET_PART" "$BUILD_DIR/Image" ::Image
fi

if [ -f "$BUILD_DIR/initramfs.img" ]; then
    mcopy -i "$TARGET_PART" "$BUILD_DIR/initramfs.img" ::EFI/R8Q/initramfs.img
    mcopy -i "$TARGET_PART" "$BUILD_DIR/initramfs.img" ::initramfs.img
fi

if [ -f "$BUILD_DIR/r8q.dtb" ]; then
    mcopy -i "$TARGET_PART" "$BUILD_DIR/r8q.dtb" ::EFI/R8Q/r8q.dtb
    mcopy -i "$TARGET_PART" "$BUILD_DIR/r8q.dtb" ::r8q.dtb
fi

# 7. Write automated startup.nsh script
echo "[ESP] Writing startup.nsh automated test script..."
TEMP_NSH="/tmp/r8q_startup.nsh"
cat << 'EOF' > "$TEMP_NSH"
@echo -off
echo =================================================================
echo   PROJECT R8Q: UEFI SHELL AUTOMATED PLATFORM VALIDATION
echo   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
echo   Virt:   QEMU ARM64 Virt Environment
echo =================================================================
echo.
echo [UEFI-SHELL] Inspecting mapped filesystems:
map -r
echo.
echo [UEFI-SHELL] Dumping memory map...
memmap
echo.
echo [UEFI-SHELL] Querying system info...
fs0:\EFI\R8Q\sysinfo.efi
echo.
echo [UEFI-SHELL] Querying CPU info...
fs0:\EFI\R8Q\cpuinfo.efi
echo.
echo [UEFI-SHELL] Running platform diagnostics...
fs0:\EFI\R8Q\diagnostics.efi
echo.
echo [UEFI-SHELL] Executing LinuxBoot validation...
fs0:\EFI\R8Q\LinuxBoot.efi
echo.
echo [UEFI-SHELL] Booting ARM64 Linux Kernel via EFI Stub...
fs0:\Image initrd=\initramfs.img console=ttyAMA0 root=/dev/vda rw
EOF

mcopy -i "$TARGET_PART" "$TEMP_NSH" ::startup.nsh
mcopy -i "$TARGET_PART" "$TEMP_NSH" ::EFI/BOOT/startup.nsh
rm -f "$TEMP_NSH"

echo "================================================================="
echo "   ESP IMAGE BUILD COMPLETE: $OUTPUT_ESP"
echo "================================================================="
ls -lh "$OUTPUT_ESP"
mdir -i "$TARGET_PART" ::
mdir -i "$TARGET_PART" ::EFI/R8Q
echo "================================================================="
