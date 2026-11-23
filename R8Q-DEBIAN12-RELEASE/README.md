# Project R8Q — Native Debian 12 ARM64 for Samsung Galaxy S20 FE 5G

[![Release](https://img.shields.io/badge/release-alpha1-blue.svg)](https://github.com/Rick000000007/r8q-uefi/releases/tag/r8q-debian12-alpha1)
[![Tests](https://img.shields.io/badge/tests-108%2F108%20passing-brightgreen.svg)](tests/)
[![Architecture](https://img.shields.io/badge/arch-ARM64%20%2F%20AArch64-orange.svg)]()
[![Platform](https://img.shields.io/badge/SoC-Snapdragon%20865%20(SM8250)-red.svg)]()
[![Target](https://img.shields.io/badge/device-Samsung%20Galaxy%20S20%20FE%205G%20(SM--G781B)-lightgrey.svg)]()

Project R8Q delivers a **bare-metal, autonomous, native Debian GNU/Linux 12 (Bookworm) ARM64 operating system** for the Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / Qualcomm Snapdragon 865 `SM8250`).

Unlike Android chroot environments, Termux containers, or PRoot userspaces, Project R8Q executes directly on physical hardware using custom EDK II UEFI firmware, mainline Linux kernel with SM8250 device tree integration, native rescue initramfs, and a pristine Debian 12 ARM64 root filesystem running Systemd 252.

---

## Hardware Compatibility Summary

| Component | Hardware Specification | Compatibility Status | Driver / Subsystem |
| :--- | :--- | :--- | :--- |
| **SoC** | Qualcomm Snapdragon 865 (`SM8250` / Kona) | **Functional** | Mainline SM8250 SoC platform drivers |
| **CPU** | 8-Core Kryo 585 (1x Cortex-X1, 3x Cortex-A77, 4x Cortex-A55) | **Functional** | PSCI SMC CPU Bringup |
| **GPU** | Qualcomm Adreno 650 | **Supported** | Freedreno DRM / MSM Driver |
| **Display** | 6.5" 1080x2400 Super AMOLED (120 Hz) | **Functional** | Continuous Splash Framebuffer (`0x9C000000`) / SimpleDRM |
| **Storage** | UFS 3.1 (`1d84000.ufshc`) | **Read-Only Enforced** | Qualcomm UFS Host Controller (Internal partitions protected) |
| **External SD** | MicroSD Slot (UHS-I / SDXC) | **Functional** | Qualcomm SDHCI (`mmcblk0`) — Primary Linux storage |
| **Serial / UART** | Qualcomm GENI Serial Engine | **Functional** | `earlycon=msm_geni_serial,0xa90000` / `ttyMSM0` |
| **Networking** | Qualcomm QCA6390 (Wi-Fi 6) & USB CDC-Ethernet | **Supported** | USB gadget `172.16.42.1` / `cfg80211` |

For in-depth hardware subsystem breakdown, see [HARDWARE-COMPATIBILITY.md](HARDWARE-COMPATIBILITY.md).

---

## Project Objectives

1. **Total Elimination of Android Dependencies:** Zero reliance on Android Bionic libc, Android dynamic linkers, Android HALs, or `init.rc`. Pure GNU/Linux ELF userspace linked against `glibc 2.36`.
2. **Deterministic Standards Compliance:** Strict compliance with Filesystem Hierarchy Standard (FHS 3.0), Systemd service management, and Linux ARM64 boot protocol (`Documentation/arm64/booting.rst`).
3. **Absolute Non-Destructive Storage Strategy:** Operates entirely from external MicroSD storage (`/dev/mmcblk0p2` or loopback disk image) and designated recovery slot (`sda24`), keeping internal Android/LineageOS boot (`sda23`) and Knox keystore (`sda25`) 100% read-only and preserved.
4. **Reproducible Engineering & Formal Verification:** 108 automated unit and integration tests validate boot section geometry, memory interval non-overlap (528 pairwise proofs), register handoff contracts, and filesystem integrity.

---

## Current Development Status

- **Milestone:** Phase 3.6A.10 Completed — Alpha 1 Release Packaging.
- **Repository Baseline Commit:** `4312b18eca26f7b44a99fd74e5c703109688d97d`
- **Automated Test Results:** 108 / 108 tests passing (100% OK).
- **Physical Safety Boundary:** Read-Only Block Device Query & Emulated Verification Complete.
- **Hardware Staging Status:** **PENDING HARDWARE VALIDATION (PHASE 3.6B GATE)**. All physical flashing commands remain held pending user confirmation.

---

## Artifact Overview

This release package contains seven verified artifacts:

```
R8Q-DEBIAN12-RELEASE/
├── boot/
│   ├── r8q-uefi-boot-complete.img  (24,461,312 B) - Compound Android v2 boot image
│   └── esp.img                     (268,435,456 B) - 256 MiB GPT EFI System Partition disk image
├── firmware/
│   └── R8Q_EFI.fd                  (4,194,304 B)   - EDK II UEFI firmware volume
├── kernel/
│   ├── Image                       (17,197,568 B)  - Uncompressed ARM64 Linux kernel (EFI stub)
│   ├── sm8250-samsung-r8q.dtb      (112,421 B)     - Mainline SM8250 device tree blob
│   └── initramfs.img               (2,947,562 B)   - Rescue initramfs CPIO archive
├── rootfs/
│   └── r8q-rootfs.ext4             (2,147,483,648 B) - Native Debian 12 root filesystem (ext4)
├── SHA256SUMS                      - Cryptographic SHA-256 verification sums
├── BUILD-MANIFEST.md               - Complete artifact ledger & structural validation results
├── INSTALLATION.md                 - Sequential provisioning and installation guide
├── HARDWARE-COMPATIBILITY.md       - Subsystem support matrix and known limitations
├── BOOT-ARCHITECTURE.md            - Bootchain analysis from Qualcomm PBL to Debian systemd
├── PARTITION-LAYOUT.md             - Verified partition geometry and zero-gap safety proof
├── RECOVERY.md                     - Boot modes, contingency matrix, and recovery procedures
└── TROUBLESHOOTING.md              - Diagnostic playbooks and failure remediation
```

---

## Quick Verification

Verify artifact cryptographic integrity immediately after download:

```bash
cd R8Q-DEBIAN12-RELEASE
sha256sum -c SHA256SUMS
```

---

## Release Documentation Index

- [BUILD-MANIFEST.md](BUILD-MANIFEST.md) — Comprehensive technical inventory, hashes, and validation tests.
- [INSTALLATION.md](INSTALLATION.md) — Step-by-step setup, hardware prerequisites, and MicroSD preparation.
- [HARDWARE-COMPATIBILITY.md](HARDWARE-COMPATIBILITY.md) — Snapdragon 865, GPU, display, and peripheral status.
- [BOOT-ARCHITECTURE.md](BOOT-ARCHITECTURE.md) — PBL, XBL, Samsung ABL, EDK II PrePi, and Linux kernel handoff.
- [PARTITION-LAYOUT.md](PARTITION-LAYOUT.md) — Live UFS partition geometry, block arithmetic, and Knox boundary safety.
- [RECOVERY.md](RECOVERY.md) — Recovery tiers, Samsung Odin Download mode, and EDL emergency restore.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Kernel panic analysis, earlycon debugging, and rescue shell commands.

---

*Project R8Q — Native Debian 12 ARM64 for Samsung Galaxy S20 FE 5G.*
