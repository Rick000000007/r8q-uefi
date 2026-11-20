#!/usr/bin/env bash
# Project R8Q UEFI: Native Linux Early-Userspace & Initramfs Generator
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Platform: Qualcomm Snapdragon 865 (SM8250 / Kona) & Virtualized QEMU ARM64
# Architecture: ARM64 / AArch64
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
INITRAMFS_ROOT="/tmp/r8q_initramfs_root"
OUTPUT_IMG="$BUILD_DIR/initramfs.img"
MODULES_SRC="/tmp/extracted_modules/usr/lib/modules/7.2.15+kali-arm64"

echo "=========================================================="
echo "   PROJECT R8Q: NATIVE LINUX INITRAMFS GENERATOR"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:    Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "=========================================================="

mkdir -p "$BUILD_DIR"
rm -rf "$INITRAMFS_ROOT"
mkdir -p "$INITRAMFS_ROOT"/{bin,sbin,usr/bin,usr/sbin,proc,sys,dev,tmp,mnt/storage,root,newroot,etc,lib/modules}

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
for applet in sh bash ash ls cat echo dmesg uname mount umount mkdir rm cp mv ps kill sleep sync \
              grep head tail cut sed awk vi clear reset mknod fdisk blkid df free switch_root \
              readlink find xargs wc tr sort losetup findfs fsck e2fsck chroot test pwd basename \
              dirname env which seq date stat sleep true false insmod lsmod modprobe rmmod; do
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

# 3. Bundle essential loadable kernel modules for filesystem & virtualization
if [ -d "$MODULES_SRC" ]; then
    echo "[INITRAMFS] Bundling filesystem & virtualization kernel modules..."
    cp "$MODULES_SRC/kernel/lib/crc/crc16.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/fs/mbcache.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/fs/jbd2/jbd2.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/fs/ext4/ext4.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/drivers/block/virtio_blk.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/net/core/failover.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/drivers/net/net_failover.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
    cp "$MODULES_SRC/kernel/drivers/net/virtio_net.ko" "$INITRAMFS_ROOT/lib/modules/" 2>/dev/null || true
fi

# 4. Create independent Native Linux init script
cat << 'EOF' > "$INITRAMFS_ROOT/init"
#!/bin/sh
# Project R8Q Native Linux Early-Userspace Init
# Standards-compliant ARM64 Linux early userspace for Samsung Galaxy S20 FE 5G & QEMU virt
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

# Mount virtual filesystems
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null || true
mount -t tmpfs none /tmp

# Populate essential device nodes if devtmpfs was not mounted
[ -c /dev/console ] || mknod /dev/console c 5 1
[ -c /dev/null ]    || mknod /dev/null c 1 3
[ -c /dev/zero ]    || mknod /dev/zero c 1 5
[ -c /dev/tty ]     || mknod /dev/tty c 5 0
[ -c /dev/tty1 ]    || mknod /dev/tty1 c 4 1
[ -c /dev/ttyAMA0 ] || mknod /dev/ttyAMA0 c 204 64 2>/dev/null || true
[ -c /dev/ttyMSM0 ] || mknod /dev/ttyMSM0 c 240 0 2>/dev/null || true

# Load filesystem drivers
if [ -f /lib/modules/crc16.ko ]; then
    insmod /lib/modules/crc16.ko 2>/dev/null || true
    insmod /lib/modules/mbcache.ko 2>/dev/null || true
    insmod /lib/modules/jbd2.ko 2>/dev/null || true
    insmod /lib/modules/ext4.ko 2>/dev/null || true
fi

# Load virtual hardware storage and network modules if present
if [ -f /lib/modules/virtio_blk.ko ]; then
    insmod /lib/modules/virtio_blk.ko 2>/dev/null || true
fi
if [ -f /lib/modules/failover.ko ]; then
    insmod /lib/modules/failover.ko 2>/dev/null || true
    insmod /lib/modules/net_failover.ko 2>/dev/null || true
    insmod /lib/modules/virtio_net.ko 2>/dev/null || true
fi

clear 2>/dev/null || true
echo "================================================================="
echo "   PROJECT R8Q NATIVE LINUX OPERATING SYSTEM"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:    Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "   Boot:   Standards-Compliant ARM64 Linux EFI Stub"
echo "================================================================="
echo "Kernel: $(uname -r) ($(uname -m))"
echo "Cmdline: $(cat /proc/cmdline)"
echo "================================================================="
echo ""

# Parse kernel command line parameters
ROOT_PARAM=""
ROOT_IMG=""
INIT_PARAM=""
EMERGENCY=0
RW_FLAG="ro"

for param in $(cat /proc/cmdline); do
    case "$param" in
        root=*)
            ROOT_PARAM="${param#root=}"
            ;;
        root_img=*|loop_img=*)
            ROOT_IMG="${param#*=}"
            ;;
        init=*)
            INIT_PARAM="${param#init=}"
            ;;
        rw)
            RW_FLAG="rw"
            ;;
        ro)
            RW_FLAG="ro"
            ;;
        emergency|rescue|single)
            EMERGENCY=1
            ;;
    esac
done

if [ "$EMERGENCY" -eq 1 ]; then
    echo "[INIT] Emergency / rescue requested on kernel command line."
fi

# Function to resolve block device from parameter (PARTUUID, UUID, LABEL, path)
resolve_device() {
    local target="$1"
    local dev=""
    case "$target" in
        PARTUUID=*|UUID=*|LABEL=*)
            dev=$(findfs "$target" 2>/dev/null || blkid -t "$target" -o device 2>/dev/null || true)
            ;;
        /dev/*)
            if [ -b "$target" ]; then
                dev="$target"
            fi
            ;;
    esac
    echo "$dev"
}

# Allow hardware buses (UFS, SDHCI, USB, VirtIO) to settle
echo "[INIT] Scanning storage hardware for root device: ${ROOT_PARAM:-'(auto-probing)'}..."
sleep 2

TARGET_ROOT=""
LOOP_ATTACHED=0

# Check if emergency mode was requested directly
if [ "$EMERGENCY" -eq 0 ]; then
    # Strategy 1: Explicit root parameter
    if [ -n "$ROOT_PARAM" ]; then
        echo "[INIT] Resolving specified root: $ROOT_PARAM..."
        for attempt in 1 2 3 4 5; do
            TARGET_ROOT=$(resolve_device "$ROOT_PARAM")
            if [ -n "$TARGET_ROOT" ] && [ -b "$TARGET_ROOT" ]; then
                echo "[INIT] Resolved $ROOT_PARAM -> $TARGET_ROOT"
                break
            fi
            sleep 1
        done
    fi

    # Strategy 2: Explicit virtual loop image
    if [ -z "$TARGET_ROOT" ] && [ -n "$ROOT_IMG" ]; then
        echo "[INIT] Searching for virtual rootfs image: $ROOT_IMG..."
        # Scan partitions for the image file
        for part in /dev/mmcblk0p* /dev/mmcblk1p* /dev/sda* /dev/sdb* /dev/vda*; do
            [ -b "$part" ] || continue
            mkdir -p /mnt/storage
            if mount -o ro "$part" /mnt/storage 2>/dev/null; then
                if [ -f "/mnt/storage/$ROOT_IMG" ]; then
                    echo "[INIT] Found $ROOT_IMG on $part. Setting up loop device..."
                    LOOP_DEV=$(losetup -f 2>/dev/null || echo "/dev/loop0")
                    if losetup "$LOOP_DEV" "/mnt/storage/$ROOT_IMG" 2>/dev/null; then
                        TARGET_ROOT="$LOOP_DEV"
                        LOOP_ATTACHED=1
                        break
                    fi
                fi
                umount /mnt/storage 2>/dev/null || true
            fi
        done
    fi

    # Strategy 3: Auto-probing heuristics (Non-destructive external MicroSD, USB, virtio)
    if [ -z "$TARGET_ROOT" ]; then
        echo "[INIT] Auto-probing storage devices for native Linux rootfs..."

        # Probe 3a: Filesystem label 'r8q-rootfs'
        TARGET_ROOT=$(resolve_device "LABEL=r8q-rootfs")
        if [ -n "$TARGET_ROOT" ]; then
            echo "[INIT] Auto-discovered filesystem labeled 'r8q-rootfs' on $TARGET_ROOT"
        fi

        # Probe 3b: VirtIO block device /dev/vda (QEMU environment)
        if [ -z "$TARGET_ROOT" ] && [ -b "/dev/vda" ]; then
            FSTYPE=$(blkid -o value -s TYPE /dev/vda 2>/dev/null || true)
            if [ "$FSTYPE" = "ext4" ]; then
                echo "[INIT] Auto-discovered ext4 filesystem on virtio block /dev/vda"
                TARGET_ROOT="/dev/vda"
            fi
        fi

        # Probe 3c: External MicroSD partition 2 (/dev/mmcblk0p2)
        if [ -z "$TARGET_ROOT" ] && [ -b "/dev/mmcblk0p2" ]; then
            FSTYPE=$(blkid -o value -s TYPE /dev/mmcblk0p2 2>/dev/null || true)
            if [ "$FSTYPE" = "ext4" ]; then
                echo "[INIT] Auto-discovered ext4 partition on MicroSD /dev/mmcblk0p2"
                TARGET_ROOT="/dev/mmcblk0p2"
            fi
        fi

        # Probe 3d: Virtual disk image 'r8q-rootfs.ext4' or 'r8q-rootfs.img' on external card
        if [ -z "$TARGET_ROOT" ]; then
            for img_name in "r8q-rootfs.ext4" "r8q-rootfs.img"; do
                for part in /dev/mmcblk0p1 /dev/mmcblk0 /dev/sdb1 /dev/sda1 /dev/vda; do
                    [ -b "$part" ] || continue
                    mkdir -p /mnt/storage
                    if mount -o ro "$part" /mnt/storage 2>/dev/null; then
                        if [ -f "/mnt/storage/$img_name" ]; then
                            echo "[INIT] Auto-discovered virtual image $img_name on $part!"
                            LOOP_DEV=$(losetup -f 2>/dev/null || echo "/dev/loop0")
                            if losetup "$LOOP_DEV" "/mnt/storage/$img_name" 2>/dev/null; then
                                TARGET_ROOT="$LOOP_DEV"
                                LOOP_ATTACHED=1
                                break 2
                            fi
                        fi
                        umount /mnt/storage 2>/dev/null || true
                    fi
                done
            done
        fi
    fi
fi

# Attempt to mount and switch_root
MOUNT_SUCCESS=0
if [ -n "$TARGET_ROOT" ] && [ -b "$TARGET_ROOT" ]; then
    echo "[INIT] Mounting root device $TARGET_ROOT onto /newroot ($RW_FLAG)..."
    if mount -o "$RW_FLAG" "$TARGET_ROOT" /newroot 2>/dev/null || mount -o ro "$TARGET_ROOT" /newroot 2>/dev/null; then
        # Determine init executable
        TARGET_INIT=""
        if [ -n "$INIT_PARAM" ] && [ -x "/newroot/$INIT_PARAM" ]; then
            TARGET_INIT="$INIT_PARAM"
        elif [ -x "/newroot/lib/systemd/systemd" ]; then
            TARGET_INIT="/lib/systemd/systemd"
        elif [ -x "/newroot/usr/lib/systemd/systemd" ]; then
            TARGET_INIT="/usr/lib/systemd/systemd"
        elif [ -x "/newroot/sbin/init" ]; then
            TARGET_INIT="/sbin/init"
        elif [ -x "/newroot/bin/bash" ]; then
            TARGET_INIT="/bin/bash"
        elif [ -x "/newroot/bin/sh" ]; then
            TARGET_INIT="/bin/sh"
        fi

        if [ -n "$TARGET_INIT" ]; then
            echo "[INIT] Target root verified successfully. Init binary: $TARGET_INIT"
            echo "[INIT] Cleanly unmounting early virtual filesystems..."
            MOUNT_SUCCESS=1

            umount /proc 2>/dev/null || true
            umount /sys 2>/dev/null || true

            echo "[INIT] Executing switch_root to $TARGET_INIT..."
            exec switch_root /newroot "$TARGET_INIT"
        else
            echo "[WARN] /newroot mounted but no valid init executable found!"
            umount /newroot 2>/dev/null || true
        fi
    else
        echo "[ERROR] Failed to mount $TARGET_ROOT on /newroot."
    fi
fi

# Emergency / Diagnostic Fallback Rescue Shell
echo "================================================================="
echo "   [FALLBACK] ROOT FILESYSTEM NOT MOUNTED -> RESCUE SHELL"
echo "================================================================="
echo "Reason: Root filesystem could not be mounted or verified."
echo ""
echo "Detected Block Devices & Partitions:"
cat /proc/partitions 2>/dev/null | sed 's/^/  /'
echo ""
echo "Block Device Filesystem Identifiers:"
blkid 2>/dev/null | sed 's/^/  /' || echo "  (blkid not available)"
echo ""
echo "Rescue Commands Available:"
echo "  - mount -o ro /dev/<device> /newroot && exec switch_root /newroot /sbin/init"
echo "  - dmesg : inspect kernel log"
echo "  - ls -la /mnt/storage : inspect mounted partitions"
echo "  - exit : restart init or reboot"
echo "================================================================="
echo ""

exec /bin/sh </dev/console >/dev/console 2>&1
EOF

chmod +x "$INITRAMFS_ROOT/init"

# 5. Package into reproducible CPIO gzip archive
cd "$INITRAMFS_ROOT"
find . -print0 | cpio --null -ov --format=newc | gzip -9 > "$OUTPUT_IMG"
cd "$PROJECT_ROOT"
rm -rf "$INITRAMFS_ROOT"

echo "[SUCCESS] Native Linux Initramfs generated cleanly:"
ls -lh "$OUTPUT_IMG"
