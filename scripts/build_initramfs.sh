#!/usr/bin/env bash
# Project R8Q UEFI: Native Linux Early-Userspace & Initramfs Generator
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Platform: Qualcomm Snapdragon 865 (SM8250 / Kona)
# Architecture: ARM64 / AArch64
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
INITRAMFS_ROOT="/tmp/r8q_initramfs_root"
OUTPUT_IMG="$BUILD_DIR/initramfs.img"

echo "=========================================================="
echo "   PROJECT R8Q: NATIVE LINUX INITRAMFS GENERATOR"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:    Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "=========================================================="

mkdir -p "$BUILD_DIR"
rm -rf "$INITRAMFS_ROOT"
mkdir -p "$INITRAMFS_ROOT"/{bin,sbin,usr/bin,usr/sbin,proc,sys,dev,tmp,mnt,etc,root,newroot}

# 1. Copy busybox binary and create applet symlinks
if [ -f "/usr/bin/busybox" ]; then
    cp /usr/bin/busybox "$INITRAMFS_ROOT/bin/busybox"
elif [ -f "/bin/busybox" ]; then
    cp /bin/busybox "$INITRAMFS_ROOT/bin/busybox"
else
    echo "ERROR: busybox not found in host environment!"
    exit 1
fi
chmod +x "$INITRAMFS_ROOT/bin/busybox"

cd "$INITRAMFS_ROOT/bin"
for applet in sh bash ash ls cat echo dmesg uname mount umount mkdir rm cp mv ps kill sleep sync grep head tail cut sed awk vi clear reset mknod fdisk blkid df free switch_root readlink find xargs wc tr sort; do
    ln -sf busybox "$applet"
done
cd "$PROJECT_ROOT"

# 2. Bundle required dynamic libraries
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
    if [ -f "/lib/ld-linux-aarch64.so.1" ]; then
        cp /lib/ld-linux-aarch64.so.1 "$INITRAMFS_ROOT/lib/"
    elif [ -f "/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1" ]; then
        mkdir -p "$INITRAMFS_ROOT/lib"
        cp /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 "$INITRAMFS_ROOT/lib/ld-linux-aarch64.so.1"
    fi
fi

# 3. Create independent Native Linux init script
cat << 'EOF' > "$INITRAMFS_ROOT/init"
#!/bin/sh
# Project R8Q Native Linux Early-Userspace Init
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

# Mount virtual filesystems
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null || true
mount -t tmpfs none /tmp

clear
echo "================================================================="
echo "   PROJECT R8Q NATIVE LINUX OPERATING SYSTEM"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:    Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "   Boot:   Standards-Compliant ARM64 Linux EFI Stub"
echo "================================================================="
echo ""
echo "Kernel: $(uname -r) ($(uname -m))"
echo "Cmdline: $(cat /proc/cmdline)"
echo ""

# Parse kernel command line for root device
ROOT_DEV=""
for param in $(cat /proc/cmdline); do
    case "$param" in
        root=*)
            ROOT_DEV="${param#root=}"
            ;;
    esac
done

echo "[INIT] Scanning storage hardware for root device: ${ROOT_DEV:-'(none specified)'}..."

# Wait up to 5 seconds for block devices to settle
for i in 1 2 3 4 5; do
    if [ -n "$ROOT_DEV" ] && [ -b "$ROOT_DEV" ]; then
        echo "[INIT] Found target root device: $ROOT_DEV"
        break
    fi
    sleep 1
done

MOUNTED=0
if [ -n "$ROOT_DEV" ] && [ -b "$ROOT_DEV" ]; then
    echo "[INIT] Attempting to mount $ROOT_DEV onto /newroot..."
    if mount -o ro "$ROOT_DEV" /newroot 2>/dev/null; then
        if [ -x "/newroot/sbin/init" ] || [ -x "/newroot/lib/systemd/systemd" ] || [ -x "/newroot/bin/sh" ]; then
            echo "[INIT] Valid root filesystem detected. Transitioning via switch_root..."
            MOUNTED=1
            umount /proc
            umount /sys
            exec switch_root /newroot /sbin/init 2>/dev/null || exec switch_root /newroot /lib/systemd/systemd 2>/dev/null || exec switch_root /newroot /bin/sh
        else
            echo "[WARN] Mounted device does not contain a standard init executable."
            umount /newroot
        fi
    fi
fi

if [ "$MOUNTED" -eq 0 ]; then
    echo "================================================================="
    echo "   [FALLBACK] ROOT FILESYSTEM NOT MOUNTED -> RESCUE SHELL"
    echo "================================================================="
    echo "Available Storage Partitions:"
    cat /proc/partitions | sed 's/^/  /'
    echo ""
    echo "Dropping to emergency recovery shell. Type 'exit' to reboot."
    echo "================================================================="
    echo ""
fi

exec /bin/sh </dev/console >/dev/console 2>&1
EOF

chmod +x "$INITRAMFS_ROOT/init"

# 4. Package into reproducible CPIO gzip archive
cd "$INITRAMFS_ROOT"
find . -print0 | cpio --null -ov --format=newc | gzip -9 > "$OUTPUT_IMG"
cd "$PROJECT_ROOT"
rm -rf "$INITRAMFS_ROOT"

echo "[SUCCESS] Native Linux Initramfs generated cleanly:"
ls -lh "$OUTPUT_IMG"
