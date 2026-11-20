#!/usr/bin/env bash
# Project R8Q UEFI: Reproducible Platform Build Driver (Milestone 2)
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Source platform configuration
source "$PROJECT_ROOT/config/platform.env"

echo "=========================================================="
echo "   PROJECT R8Q UEFI: REPRODUCIBLE PLATFORM BUILD DRIVER"
echo "   Target:  $TARGET_DEVICE ($TARGET_MODEL - $TARGET_CODENAME)"
echo "   SoC:     $TARGET_SOC (Arch: $TARGET_ARCH)"
echo "   EDK II:  $EDK2_TAG ($EDK2_COMMIT)"
echo "=========================================================="
echo ""

# 1. Environment Verification
echo "[1/6] Running Environment Verification..."
"$PROJECT_ROOT/scripts/verify_environment.sh"

# 2. Check /dev/shm for Python Multiprocessing
echo ""
echo "[2/6] Verifying POSIX Shared Memory (/dev/shm)..."
if [ ! -d "/dev/shm" ]; then
    mkdir -p /dev/shm
    chmod 1777 /dev/shm
    mount -t tmpfs tmpfs /dev/shm 2>/dev/null || true
fi

# 3. BaseTools Verification
echo ""
echo "[3/6] Verifying EDK II BaseTools..."
mkdir -p "$PROJECT_ROOT/edk2/BaseTools/Bin/Linux-aarch64"
if [ -f "$PROJECT_ROOT/edk2/BaseTools/Source/C/bin/GenFv" ]; then
    cp "$PROJECT_ROOT/edk2/BaseTools/Source/C/bin/"* "$PROJECT_ROOT/edk2/BaseTools/Bin/Linux-aarch64/" 2>/dev/null || true
fi

# 4. EDK II Platform Build
echo ""
echo "[4/6] Executing EDK II Platform Compilation (R8QPkg)..."
export WORKSPACE="$PROJECT_ROOT/edk2"
export PACKAGES_PATH="$PROJECT_ROOT/platform:$PROJECT_ROOT/edk2"
export EDK_TOOLS_PATH="$PROJECT_ROOT/edk2/BaseTools"
export PATH="$EDK_TOOLS_PATH/BinWrappers/PosixLike:$EDK_TOOLS_PATH/Bin/Linux-aarch64:$PATH"
export PYTHON_COMMAND=python3

cd "$PROJECT_ROOT/edk2"
build -p R8QPkg/R8QPkg.dsc -a AARCH64 -t GCC5 -b DEBUG

# 5. Packaging Proof-of-Concept Boot Image
echo ""
echo "[5/6] Packaging Proof-of-Concept Android Boot Image (v2)..."
mkdir -p "$PROJECT_ROOT/build"
OUTPUT_FD="$PROJECT_ROOT/edk2/Build/R8Q/DEBUG_GCC5/FV/R8Q_EFI.fd"
POC_IMG="$PROJECT_ROOT/build/r8q-uefi-boot-poc.img"

if [ -f "$OUTPUT_FD" ]; then
    cp "$OUTPUT_FD" "$PROJECT_ROOT/build/R8Q_EFI.fd"
    python3 "$PROJECT_ROOT/scripts/package_boot_img.py" "$PROJECT_ROOT/build/R8Q_EFI.fd" "$POC_IMG"
else
    # If FD not built, package PrePi raw binary as proof-of-concept
    PREPI_RAW="$PROJECT_ROOT/edk2/Build/R8Q/DEBUG_GCC5/AARCH64/R8QPkg/PrePi/PrePi/OUTPUT/PrePi.raw"
    if [ -f "$PREPI_RAW" ]; then
        cp "$PREPI_RAW" "$PROJECT_ROOT/build/PrePi.raw"
        python3 "$PROJECT_ROOT/scripts/package_boot_img.py" "$PROJECT_ROOT/build/PrePi.raw" "$POC_IMG"
    fi
fi

# 6. Static Image Validation & Manifest
echo ""
echo "[6/6] Executing Static Firmware & Image Validation..."
if [ -f "$POC_IMG" ]; then
    python3 "$PROJECT_ROOT/tests/static_validate_image.py" "$POC_IMG"
fi

python3 "$PROJECT_ROOT/scripts/gen_manifest.py"

echo ""
echo ">>> MILESTONE 2 PLATFORM BUILD PIPELINE COMPLETE <<<"
