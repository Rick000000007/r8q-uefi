#!/usr/bin/env bash
# Project R8Q UEFI: Native ARM64 Linux Root Filesystem Generator
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Platform: Qualcomm Snapdragon 865 (SM8250 / Kona)
# Architecture: ARM64 / AArch64 (ARMv8.2-A)
# Non-destructive Policy: Strictly offline image generation; zero physical partition writes.
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
STAGING_DIR="/tmp/r8q_rootfs_staging"
DEB_DIR_1="/tmp/r8q_test_debootstrap/var/cache/apt/archives"
DEB_DIR_2="/tmp/r8q_extra_debs"
OUTPUT_TAR="$BUILD_DIR/r8q-rootfs.tar.gz"
OUTPUT_EXT4="$BUILD_DIR/r8q-rootfs.ext4"
EXT4_SIZE_MB=2048

echo "================================================================="
echo "   PROJECT R8Q: NATIVE ARM64 LINUX ROOT FILESYSTEM BUILDER"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:    Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "   Arch:   ARM64 / AArch64 (ARMv8.2-A)"
echo "================================================================="

mkdir -p "$BUILD_DIR"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# 1. Unpack all pristine ARM64 deb packages into staging rootfs
echo "[ROOTFS] Unpacking base and extended ARM64 packages..."
PKG_COUNT=0
for deb in "$DEB_DIR_1"/*.deb "$DEB_DIR_2"/*.deb; do
    [ -f "$deb" ] || continue
    dpkg-deb -x "$deb" "$STAGING_DIR"
    PKG_COUNT=$((PKG_COUNT + 1))
done
echo "[ROOTFS] Extracted $PKG_COUNT packages into staging directory."

# 2. Establish standard FHS directories
echo "[ROOTFS] Setting up FHS 3.0 directory tree..."
mkdir -p "$STAGING_DIR"/{dev,proc,sys,mnt/storage,root,home/r8q,boot/efi,opt,media}
mkdir -p "$STAGING_DIR"/etc/{network/interfaces.d,udev/rules.d,systemd/system/getty.target.wants,systemd/network,ssh,sudoers.d,security,default}
mkdir -p "$STAGING_DIR"/var/{log,tmp,spool,mail,cache/apt/archives/partial,lib/dpkg/info,lib/systemd}
mkdir -p "$STAGING_DIR"/run/{systemd,sshd,lock,user}
mkdir -p "$STAGING_DIR"/lib/firmware/qcom/sm8250

chmod 1777 "$STAGING_DIR"/tmp "$STAGING_DIR"/var/tmp
chmod 0700 "$STAGING_DIR"/root
chmod 0750 "$STAGING_DIR"/home/r8q

# 3. Create static device nodes for early boot stage
echo "[ROOTFS] Creating static early-boot device nodes..."
mknod -m 666 "$STAGING_DIR"/dev/null c 1 3 2>/dev/null || true
mknod -m 666 "$STAGING_DIR"/dev/zero c 1 5 2>/dev/null || true
mknod -m 600 "$STAGING_DIR"/dev/console c 5 1 2>/dev/null || true
mknod -m 666 "$STAGING_DIR"/dev/tty c 5 0 2>/dev/null || true
mknod -m 620 "$STAGING_DIR"/dev/tty1 c 4 1 2>/dev/null || true
mknod -m 660 "$STAGING_DIR"/dev/ttyMSM0 c 240 0 2>/dev/null || true

# 4. Hostname and Hosts
echo "[ROOTFS] Configuring hostname and network naming..."
echo "r8q-linux" > "$STAGING_DIR"/etc/hostname
cat << 'EOF' > "$STAGING_DIR"/etc/hosts
127.0.0.1   localhost
127.0.1.1   r8q-linux

# The following lines are desirable for IPv6 capable hosts
::1         localhost ip6-localhost ip6-loopback
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters
EOF

# 5. Filesystem Table (fstab)
echo "[ROOTFS] Writing filesystem table (/etc/fstab)..."
cat << 'EOF' > "$STAGING_DIR"/etc/fstab
# Project R8Q Native Linux Filesystem Table
# Target: Samsung Galaxy S20 FE 5G (SM-G781B)
# Device-independent mounts via Volume Labels and UUIDs

# Root filesystem (ext4) on external MicroSD or loop image
LABEL=r8q-rootfs    /          ext4   errors=remount-ro,noatime,barrier=1  0 1

# EFI System Partition (FAT32)
LABEL=R8Q_BOOT      /boot/efi  vfat   umask=0077,noatime,codepage=437      0 2

# Virtual filesystems
tmpfs               /tmp       tmpfs  nosuid,nodev,mode=1777               0 0
devpts              /dev/pts   devpts gid=5,mode=620                       0 0
proc                /proc      proc   defaults                             0 0
sysfs               /sys       sysfs  defaults                             0 0
EOF

# 6. User and Group Management
echo "[ROOTFS] Establishing users, groups, and authentication..."
cat << 'EOF' > "$STAGING_DIR"/etc/passwd
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/run/ircd:/usr/sbin/nologin
_apt:x:42:65534::/nonexistent:/usr/sbin/nologin
systemd-network:x:100:102:systemd Network Management,,,:/run/systemd:/usr/sbin/nologin
systemd-resolve:x:101:103:systemd Resolver,,,:/run/systemd:/usr/sbin/nologin
messagebus:x:102:105::/nonexistent:/usr/sbin/nologin
sshd:x:103:65534::/run/sshd:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
r8q:x:1000:1000:R8Q Linux User,,,:/home/r8q:/bin/bash
EOF

# Passwords: root -> toor ; r8q -> r8q
ROOT_HASH='$6$r8qroot$j3D7mcvBMt6Co0iFTehA5j2fsV/H0zD5ASuBtJjeZoOdUtpvh9GQ7atb2f7d5oH1Hu1hYav1BMuw2v537T5oI0'
R8Q_HASH='$6$r8quser$4TicQcNKIw0njg/ZbE9OqKf48I/E8xJjNVNESFCgyfmLi3uMHnjcijhgixkHI1XuQcYtS7MbY1VthqnOmVfqp0'

cat << EOF > "$STAGING_DIR"/etc/shadow
root:${ROOT_HASH}:19712:0:99999:7:::
daemon:*:19712:0:99999:7:::
bin:*:19712:0:99999:7:::
sys:*:19712:0:99999:7:::
sync:*:19712:0:99999:7:::
games:*:19712:0:99999:7:::
man:*:19712:0:99999:7:::
lp:*:19712:0:99999:7:::
mail:*:19712:0:99999:7:::
news:*:19712:0:99999:7:::
uucp:*:19712:0:99999:7:::
proxy:*:19712:0:99999:7:::
www-data:*:19712:0:99999:7:::
backup:*:19712:0:99999:7:::
list:*:19712:0:99999:7:::
irc:*:19712:0:99999:7:::
_apt:*:19712:0:99999:7:::
systemd-network:*:19712:0:99999:7:::
systemd-resolve:*:19712:0:99999:7:::
messagebus:*:19712:0:99999:7:::
sshd:*:19712:0:99999:7:::
nobody:*:19712:0:99999:7:::
r8q:${R8Q_HASH}:19712:0:99999:7:::
EOF
chmod 0640 "$STAGING_DIR"/etc/shadow

cat << 'EOF' > "$STAGING_DIR"/etc/group
root:x:0:
daemon:x:1:
bin:x:2:
sys:x:3:
adm:x:4:r8q
tty:x:5:
disk:x:6:r8q
lp:x:7:
mail:x:8:
news:x:9:
uucp:x:10:
wheel:x:10:r8q
man:x:12:
proxy:x:13:
kmem:x:15:
dialout:x:20:r8q
fax:x:21:
voice:x:22:
cdrom:x:24:
floppy:x:25:
tape:x:26:
sudo:x:27:r8q
audio:x:29:r8q
dip:x:30:
www-data:x:33:
backup:x:34:
operator:x:37:
src:x:40:
shadow:x:42:
utmp:x:43:
video:x:44:r8q
sasl:x:45:
plugdev:x:46:r8q
staff:x:50:
games:x:60:
users:x:100:
nogroup:x:65534:
systemd-journal:x:101:r8q
systemd-network:x:102:
systemd-resolve:x:103:
input:x:104:r8q
messagebus:x:105:
netdev:x:106:r8q
r8q:x:1000:
EOF

# Sudoers configuration
echo "r8q ALL=(ALL:ALL) NOPASSWD: ALL" > "$STAGING_DIR"/etc/sudoers.d/r8q
chmod 0440 "$STAGING_DIR"/etc/sudoers.d/r8q

# 7. Hardware & Udev Rules for Snapdragon 865 (SM8250)
echo "[ROOTFS] Installing SM8250 platform udev rules..."

# Adreno 650 GPU & DRM render nodes
cat << 'EOF' > "$STAGING_DIR"/etc/udev/rules.d/90-sm8250-gpu.rules
# Qualcomm Adreno 650 (Freedreno / MSM DRM)
KERNEL=="card[0-9]*", SUBSYSTEM=="drm", GROUP="video", MODE="0660"
KERNEL=="renderD[0-9]*", SUBSYSTEM=="drm", GROUP="video", MODE="0666"
EOF

# Samsung Galaxy S20 FE 5G Touchscreen (sec_touchscreen)
cat << 'EOF' > "$STAGING_DIR"/etc/udev/rules.d/91-sm8250-touch.rules
# Samsung Galaxy S20 FE FocalTech Touchscreen
SUBSYSTEM=="input", ATTRS{name}=="sec_touchscreen*", SYMLINK+="input/touchscreen0", GROUP="input", MODE="0660"
EOF

# Maxim MAX77705 Fuel Gauge & Charger
cat << 'EOF' > "$STAGING_DIR"/etc/udev/rules.d/92-sm8250-power.rules
# Maxim MAX77705 Power Supply & Battery Subsystem
SUBSYSTEM=="power_supply", ATTR{type}=="Battery", SYMLINK+="power_supply/primary_battery"
SUBSYSTEM=="power_supply", ATTR{type}=="USB", SYMLINK+="power_supply/usb_charger"
EOF

# Qualcomm SDX55 5G Modem (MHI Bus & QRTR)
cat << 'EOF' > "$STAGING_DIR"/etc/udev/rules.d/93-sm8250-modem.rules
# Qualcomm Snapdragon X55 5G Modem (PCIe RC2)
SUBSYSTEM=="mhi", GROUP="dialout", MODE="0660"
SUBSYSTEM=="wwan", GROUP="dialout", MODE="0660"
EOF

# Qualcomm QCA6390 Wi-Fi 6 (ath11k_pci)
cat << 'EOF' > "$STAGING_DIR"/etc/udev/rules.d/94-sm8250-wifi.rules
# Qualcomm QCA6390 Wi-Fi 6 on PCIe RC0 [17cb:1101]
SUBSYSTEM=="net", ACTION=="add", ATTRS{vendor}=="0x17cb", ATTRS{device}=="0x1101", NAME="wlan0"
EOF

# 8. Modern Systemd Service Hierarchy & Console Configuration
echo "[ROOTFS] Configuring systemd services and consoles..."
# Enable serial console on Qualcomm GENI UART (ttyMSM0 @ 115200)
mkdir -p "$STAGING_DIR"/etc/systemd/system/getty.target.wants
ln -sf /lib/systemd/system/serial-getty@.service "$STAGING_DIR"/etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service
# Enable virtual terminal on framebuffer (tty1)
ln -sf /lib/systemd/system/getty@.service "$STAGING_DIR"/etc/systemd/system/getty.target.wants/getty@tty1.service
# Set default target to multi-user
ln -sf /lib/systemd/system/multi-user.target "$STAGING_DIR"/etc/systemd/system/default.target

# 9. Network Configuration
echo "[ROOTFS] Writing network configuration..."
cat << 'EOF' > "$STAGING_DIR"/etc/systemd/network/20-wired.network
[Match]
Name=eth* usb*

[Network]
DHCP=yes
EOF

cat << 'EOF' > "$STAGING_DIR"/etc/systemd/network/25-wireless.network
[Match]
Name=wlan*

[Network]
DHCP=yes
EOF

cat << 'EOF' > "$STAGING_DIR"/etc/resolv.conf
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF

# 10. OpenSSH Server Configuration
echo "[ROOTFS] Configuring OpenSSH daemon and host keys..."
mkdir -p "$STAGING_DIR"/etc/ssh
cat << 'EOF' > "$STAGING_DIR"/etc/ssh/sshd_config
# Project R8Q Native Linux OpenSSH Configuration
Port 22
AddressFamily any
ListenAddress 0.0.0.0
ListenAddress ::

# Host Keys
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key

# Authentication
PermitRootLogin yes
PubkeyAuthentication yes
PasswordAuthentication yes
PermitEmptyPasswords no
ChallengeResponseAuthentication no

# Subsystems
Subsystem sftp /usr/lib/openssh/sftp-server
EOF

# Generate standard SSH host keys if ssh-keygen is present
if which ssh-keygen >/dev/null 2>&1; then
    ssh-keygen -t rsa -b 3072 -f "$STAGING_DIR"/etc/ssh/ssh_host_rsa_key -N "" -q
    ssh-keygen -t ecdsa -b 256 -f "$STAGING_DIR"/etc/ssh/ssh_host_ecdsa_key -N "" -q
    ssh-keygen -t ed25519 -f "$STAGING_DIR"/etc/ssh/ssh_host_ed25519_key -N "" -q
fi

# 11. APT Package Manager Configuration
echo "[ROOTFS] Configuring Debian APT sources..."
cat << 'EOF' > "$STAGING_DIR"/etc/apt/sources.list
# Debian GNU/Linux 12 (Bookworm) ARM64 Repositories
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://deb.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware
EOF

# 12. Emergency Recovery Utility
cat << 'EOF' > "$STAGING_DIR"/sbin/emergency_rescue.sh
#!/bin/sh
# Project R8Q Emergency Diagnostic & Recovery Script
echo "=========================================================="
echo "   PROJECT R8Q: NATIVE LINUX RESCUE UTILITY"
echo "=========================================================="
echo "CPU Architecture: $(uname -m)"
echo "Kernel Release:   $(uname -r)"
echo "System Uptime:    $(uptime)"
echo ""
echo "Block Devices:"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT 2>/dev/null || cat /proc/partitions
echo ""
echo "Memory Status:"
free -m 2>/dev/null || cat /proc/meminfo | grep MemTotal
echo "=========================================================="
EOF
chmod +x "$STAGING_DIR"/sbin/emergency_rescue.sh

# 13. Create Standalone ext4 Raw Disk Image
echo "[ROOTFS] Generating raw ext4 disk image (${EXT4_SIZE_MB} MiB) via mke2fs..."
rm -f "$OUTPUT_EXT4"
mke2fs -t ext4 -L "r8q-rootfs" -d "$STAGING_DIR" "$OUTPUT_EXT4" "${EXT4_SIZE_MB}M"

# 14. Create Compressed Tarball Archive
echo "[ROOTFS] Packaging compressed rootfs tarball ($OUTPUT_TAR)..."
tar -czf "$OUTPUT_TAR" -C "$STAGING_DIR" .

echo "================================================================="
echo "   ROOT FILESYSTEM BUILD COMPLETED SUCCESSFULLY"
echo "================================================================="
ls -lh "$OUTPUT_EXT4" "$OUTPUT_TAR"
echo "SHA-256 Checksums:"
sha256sum "$OUTPUT_EXT4" "$OUTPUT_TAR"
echo "================================================================="
