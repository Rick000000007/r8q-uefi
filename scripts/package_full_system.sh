#!/usr/bin/env bash
# Project R8Q — Complete Full System Packaging Driver
# Packages R8Q-Debian12-Full-System.tar.gz containing all operating system components.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="$PROJECT_ROOT/R8Q-DEBIAN12-RELEASE"
OUT_TAR="$RELEASE_DIR/R8Q-Debian12-Full-System.tar.gz"
STAGE_DIR="/tmp/r8q_full_system_stage/R8Q-Debian12-Full-System"

echo "=========================================================="
echo "   PROJECT R8Q: FULL SYSTEM PACKAGING DRIVER"
echo "=========================================================="

rm -rf "/tmp/r8q_full_system_stage"
mkdir -p "$STAGE_DIR"
mkdir -p "$STAGE_DIR/boot"
mkdir -p "$STAGE_DIR/firmware"
mkdir -p "$STAGE_DIR/kernel"
mkdir -p "$STAGE_DIR/rootfs"

echo "[1/5] Copying release documentation and manifests..."
cp -a "$RELEASE_DIR"/*.md "$STAGE_DIR/"
cp -a "$RELEASE_DIR"/SHA256SUMS* "$STAGE_DIR/" 2>/dev/null || true

echo "[2/5] Copying recovery installer..."
if [ -f "$RELEASE_DIR/R8Q-Debian12-Recovery.zip" ]; then
    cp -a "$RELEASE_DIR/R8Q-Debian12-Recovery.zip" "$STAGE_DIR/"
fi

echo "[3/5] Copying bootloader, kernel, DTB and ESP payloads..."
cp -a "$RELEASE_DIR/boot/r8q-uefi-boot-complete.img" "$STAGE_DIR/boot/"
cp -a "$RELEASE_DIR/boot/esp.img" "$STAGE_DIR/boot/"
cp -a "$RELEASE_DIR/firmware/R8Q_EFI.fd" "$STAGE_DIR/firmware/"
cp -a "$RELEASE_DIR/kernel/Image" "$STAGE_DIR/kernel/"
cp -a "$RELEASE_DIR/kernel/sm8250-samsung-r8q.dtb" "$STAGE_DIR/kernel/"
cp -a "$RELEASE_DIR/kernel/initramfs.img" "$STAGE_DIR/kernel/"

echo "[4/5] Copying Debian 12 Bookworm ARM64 root filesystem..."
cp -a "$RELEASE_DIR/rootfs/r8q-rootfs.ext4.gz" "$STAGE_DIR/rootfs/"
if [ -f "$RELEASE_DIR/rootfs/r8q-rootfs.tar.gz" ]; then
    cp -a "$RELEASE_DIR/rootfs/r8q-rootfs.tar.gz" "$STAGE_DIR/rootfs/"
elif [ -f "$PROJECT_ROOT/artifacts/r8q-rootfs.tar.gz" ]; then
    cp -a "$PROJECT_ROOT/artifacts/r8q-rootfs.tar.gz" "$STAGE_DIR/rootfs/"
fi

echo "[5/5] Compressing full system package ($OUT_TAR)..."
cd "/tmp/r8q_full_system_stage"
tar -czf "$OUT_TAR" R8Q-Debian12-Full-System

rm -rf "/tmp/r8q_full_system_stage"

TAR_SIZE="$(stat -c %s "$OUT_TAR")"
TAR_SHA="$(sha256sum "$OUT_TAR" | awk '{print $1}')"

echo "=========================================================="
echo "   FULL SYSTEM PACKAGE CREATION SUCCESSFUL"
echo "   Package:  $OUT_TAR"
echo "   Size:     $TAR_SIZE bytes"
echo "   SHA256:   $TAR_SHA"
echo "=========================================================="
