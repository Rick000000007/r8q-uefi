# Project R8Q — Reproducible Build Guide

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Document Revision:** 3.0.0 (Reproducible Cloud & Local Compilation)  
**Status:** Authoritative Build Manual  

---

## 1. Overview & Build Philosophy

Project R8Q provides fully automated, deterministic build scripts that support compilation both locally on ARM64 Linux systems (such as the S25 Ultra / Termux / Kali chroot) and in cloud CI/CD infrastructure (GitHub Actions).

Every build step outputs cryptographically verifiable artifacts with exact SHA-256 digests.

---

## 2. Host Build Dependencies

The following packages are required on a Debian/Ubuntu-based host:

```bash
sudo apt-get update && sudo apt-get install -y \
    build-essential \
    gcc-aarch64-linux-gnu \
    binutils-aarch64-linux-gnu \
    clang \
    cmake \
    make \
    python3 \
    python3-pip \
    device-tree-compiler \
    parted \
    mtools \
    dosfstools \
    e2fsprogs \
    cpio \
    gzip \
    tar \
    git \
    debootstrap \
    qemu-system-arm \
    qemu-efi-aarch64
```

---

## 3. End-to-End Build Sequence

```
[scripts/build.sh]                 --> Builds EDK II Firmware Volume (build/R8Q_EFI.fd)
        │
[scripts/build_kernel.sh]          --> Builds Linux ARM64 EFI Stub (build/Image)
        │
[scripts/build_initramfs.sh]       --> Builds Early-Userspace CPIO (build/initramfs.img)
        │
[scripts/build_rootfs.sh]          --> Builds Debian 12 ARM64 Rootfs (build/r8q-rootfs.ext4)
        │
[scripts/build_esp.sh]             --> Builds FAT32 EFI System Partition (build/esp.img)
        │
[scripts/package_complete_boot_img.py] --> Bundles Boot Image v2 (build/r8q-uefi-boot-complete.img)
        │
[scripts/package_recovery_zip.py]  --> Generates Flashable ZIP (R8Q-Debian12-Recovery.zip)
        │
[scripts/package_full_system.py]   --> Produces Final Tarball (R8Q-Debian12-Full-System.tar.gz)
```

### 3.1 Step 1: EDK II Firmware Volume Build
```bash
./scripts/build.sh
```
- Sets up EDK II BaseTools in `edk2/BaseTools`.
- Compiles `R8QPkg/R8QPkg.dsc` in AArch64 using `GCC5` toolchain.
- Outputs `build/R8Q_EFI.fd` (4,194,304 bytes).

### 3.2 Step 2: Linux Kernel EFI Stub Compilation
```bash
./scripts/build_kernel.sh
```
- Uses kernel configuration `config/kernel_r8q_defconfig`.
- Compiles ARM64 Image with EFI Stub and Qualcomm SM8250 drivers.
- Validates `ARM\x64` magic header signature at offset `0x38`.
- Outputs `build/Image` (17,197,568 bytes).

### 3.3 Step 3: Early-Userspace Initramfs Generation
```bash
./scripts/build_initramfs.sh
```
- Constructs BusyBox ARM64 applet tree.
- Installs partition probing and non-destructive mount script `/init`.
- Packages into gzip-compressed CPIO archive.
- Outputs `build/initramfs.img` (2,947,562 bytes).

### 3.4 Step 4: Native Debian 12 ARM64 Root Filesystem Build
```bash
./scripts/build_rootfs.sh
```
- Unpacks official Debian 12 Bookworm ARM64 package archives.
- Configures FHS 3.0 filesystem tree, users, shadow hashes, and sudoers.
- Sets default boot target to `multi-user.target` (Terminal-First).
- Configures `tty1` (AMOLED framebuffer console) and `ttyMSM0` (Qualcomm serial).
- Formats ext4 image with volume label `r8q-rootfs`.
- Outputs `build/r8q-rootfs.ext4` (2,147,483,648 bytes) and `build/r8q-rootfs.ext4.gz`.

### 3.5 Step 5: EFI System Partition (ESP) Generation
```bash
./scripts/build_esp.sh
```
- Creates 256 MiB GPT disk image formatted as FAT32 (`R8Q_BOOT`).
- Installs `EFI/BOOT/BOOTAA64.EFI`, `EFI/R8Q/Shell.efi`, `EFI/R8Q/LinuxBoot.efi`, custom diagnostic utilities, kernel, DTB, and initramfs.
- Outputs `build/esp.img` (268,435,456 bytes).

### 3.6 Step 6: Complete Boot Container Packaging
```bash
python3 scripts/package_complete_boot_img.py
```
- Bundles `R8Q_EFI.fd`, `Image`, `initramfs.img`, and patched `sm8250-samsung-r8q.dtb` into an Android Boot Image Header v2 container.
- Outputs `build/r8q-uefi-boot-complete.img` (24,461,312 bytes).

### 3.7 Step 7: LineageOS Recovery Flashable ZIP Packaging
```bash
python3 scripts/package_recovery_zip.py \
    R8Q-DEBIAN12-RELEASE/boot/r8q-uefi-boot-complete.img \
    R8Q-DEBIAN12-RELEASE/R8Q-Debian12-Recovery.zip
```
- Normalizes ZIP timestamps to `1980-01-01 00:00:00 UTC` for deterministic checksums.
- Includes `update-binary` with strict `sda25` protection.
- Outputs `R8Q-Debian12-Recovery.zip` (10,234,189 bytes).

### 3.8 Step 8: Full System Distribution Archive Packaging
```bash
python3 scripts/package_full_system.py
```
- Produces deterministic, bit-exact distribution tarball.
- Outputs `R8Q-Debian12-Full-System.tar.gz` (214,744,887 bytes).

---

## 4. Running Automated Tests

Run the complete test suite across all subsystems:
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
Verification of 108 tests takes ~85 seconds on ARM64 host hardware.
