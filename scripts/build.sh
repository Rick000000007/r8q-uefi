#!/usr/bin/env bash
# Project R8Q UEFI: Reproducible Build Script
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Source platform configuration
source "$PROJECT_ROOT/config/platform.env"

echo "=========================================================="
echo "   PROJECT R8Q UEFI: REPRODUCIBLE BUILD DRIVER"
echo "   Target: $TARGET_DEVICE ($TARGET_MODEL - $TARGET_CODENAME)"
echo "   SoC:    $TARGET_SOC (Arch: $TARGET_ARCH)"
echo "=========================================================="
echo ""

# 1. Environment Verification
echo "[1/4] Running Environment Verification..."
"$PROJECT_ROOT/scripts/verify_environment.sh"

# 2. Check Directories
echo ""
echo "[2/4] Ensuring Build Directories..."
mkdir -p "$PROJECT_ROOT/build"
mkdir -p "$PROJECT_ROOT/artifacts"
mkdir -p "$PROJECT_ROOT/logs"

# 3. Generate SHA256 Checksum Manifest
echo ""
echo "[3/4] Generating Source & Artifact Manifest..."
python3 "$PROJECT_ROOT/scripts/gen_manifest.py"

# 4. Summary
echo ""
echo "[4/4] Milestone 1 Baseline Build Verification Complete!"
echo ">>> PROJECT R8Q UEFI FOUNDATION IS FULLY ESTABLISHED <<<"
