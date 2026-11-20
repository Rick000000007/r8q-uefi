#!/usr/bin/env bash
# Project R8Q UEFI: Minimal Native Linux Initramfs Generator
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Platform: Qualcomm Snapdragon 865 (SM8250)
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
INITRAMFS_ROOT="/tmp/r8q_initramfs_root"
OUTPUT_IMG="$BUILD_DIR/initramfs.img"

echo "=== PROJECT R8Q: GENERATING NATIVE LINUX INITRAMFS ==="

mkdir -p "$BUILD_DIR"
rm -rf "$INITRAMFS_ROOT"
mkdir -p "$INITRAMFS_ROOT"/{bin,sbin,usr/bin,usr/sbin,proc,sys,dev,tmp,mnt,etc,root}

# Copy busybox and create symlinks
cp /usr/bin/busybox "$INITRAMFS_ROOT/bin/busybox"
chmod +x "$INITRAMFS_ROOT/bin/busybox"

# Install busybox symlinks
cd "$INITRAMFS_ROOT/bin"
for applet in sh bash ash ls cat echo dmesg uname mount umount mkdir rm cp mv ps kill sleep sync grep head tail cut sed awk vi clear reset mknod fdisk blkid df free; do
    ln -sf busybox "$applet"
done
cd "$PROJECT_ROOT"

# Copy essential shared libraries if busybox is dynamically linked
if ldd "$INITRAMFS_ROOT/bin/busybox" > /dev/null 2>&1; then
    mkdir -p "$INITRAMFS_ROOT/lib" "$INITRAMFS_ROOT/lib64"
    for lib in $(ldd "$INITRAMFS_ROOT/bin/busybox" | grep -o '/lib[^ ]*'); do
        if [ -f "$lib" ]; then
            cp "$lib" "$INITRAMFS_ROOT/lib/" 2>/dev/null || true
        fi
    done
    for lib in $(ldd "$INITRAMFS_ROOT/bin/busybox" | grep -o '/usr/lib[^ ]*'); do
        if [ -f "$lib" ]; then
            mkdir -p "$INITRAMFS_ROOT/usr/lib"
            cp "$lib" "$INITRAMFS_ROOT/usr/lib/" 2>/dev/null || true
        fi
    done
    # Copy ld-linux dynamic linker
    if [ -f "/lib/ld-linux-aarch64.so.1" ]; then
        cp /lib/ld-linux-aarch64.so.1 "$INITRAMFS_ROOT/lib/"
    elif [ -f "/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1" ]; then
        mkdir -p "$INITRAMFS_ROOT/lib"
        cp /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 "$INITRAMFS_ROOT/lib/ld-linux-aarch64.so.1"
    fi
fi

# Create init script
cat << 'EOF' > "$INITRAMFS_ROOT/init"
#!/bin/sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null || true
mount -t tmpfs none /tmp

clear
echo "================================================================="
echo "   PROJECT R8Q NATIVE LINUX RESCUE ENVIRONMENT (MILESTONE 6)"
echo "   Target Device: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:           Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "   Handoff:       Native ARM64 Linux EFI Stub (R8Q UEFI Firmware)"
echo "================================================================="
echo ""
echo "Linux Kernel Release: $(uname -r) ($(uname -m))"
echo "Boot Parameters: $(cat /proc/cmdline)"
echo ""
echo "Detected CPU Cores:"
grep "processor" /proc/cpuinfo | wc -l | sed 's/^/  Total Cores: /'
echo ""
echo "Memory Status:"
grep -E "MemTotal|MemFree|MemAvailable" /proc/meminfo | sed 's/^/  /'
echo ""
echo "Active Storage Block Devices:"
cat /proc/partitions | sed 's/^/  /'
echo ""
echo "================================================================="
echo "Entering interactive recovery shell. Type 'exit' to halt/reboot."
echo "================================================================="
echo ""

# Launch interactive shell
exec /bin/sh </dev/console >/dev/console 2>&1
EOF

chmod +x "$INITRAMFS_ROOT/init"

# Package into cpio.gz
cd "$INITRAMFS_ROOT"
find . -print0 | cpio --null -ov --format=newc | gzip -9 > "$OUTPUT_IMG"
cd "$PROJECT_ROOT"

rm -rf "$INITRAMFS_ROOT"

echo "[SUCCESS] Initramfs generated cleanly:"
ls -lh "$OUTPUT_IMG"
