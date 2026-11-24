# Project R8Q — Implementation Roadmap

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Document Revision:** 3.0.0 (Terminal-First Phased Architecture)  
**Status:** Authoritative Engineering Roadmap  

---

## 1. Phased Engineering Strategy

The Project R8Q implementation roadmap is structured into 10 sequential, dependency-ordered engineering phases. Each phase establishes strict deliverables, test gates, and regression proofs before advancing.

```
+-----------------------------------------------------------------------------------+
| PHASE 0: Environment & Repository Audit                                [COMPLETE] |
| - Complete audit of host environment, compilers, and repository                   |
| - Verification of all 10 existing binary release artifacts                        |
| - Master technical specification & terminal-first architectural shift             |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 1: UEFI Firmware Foundation                                      [COMPLETE] |
| - EDK II AArch64 platform (R8QPkg) compilation                                    |
| - PrePi stack relocation to 0x9E890000 (+484 MiB safety margin)                   |
| - Continuous splash GOP driver (SimpleFbDxe at 0x9C000000)                        |
| - Keystore hardware block write filter (StorageProtectionDxe)                     |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 2: BIOS-Style Setup Utility                                      [IN PROGRESS] |
| - Dedicated firmware setup interface (Main, Boot, Devices, Config, Security)      |
| - Integration of existing diagnostic applications into unified UI                 |
| - Interactive EDK II UEFI Shell integration                                       |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 3: Independent Boot Manager                                      [IN PROGRESS] |
| - Independent EFI application (BootManager.efi / BOOTAA64.EFI)                    |
| - Multi-drive OS discovery (Internal UFS, MicroSD, USB OTG)                       |
| - Configuration parser for EFI/R8Q/Config/boot.cfg & entries/*.conf               |
| - FDT table injection & LoadFile2 initrd protocol handoff                         |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 4: Linux Hardware Platform                                       [COMPLETE] |
| - 64-bit ARM64 kernel with EFI Stub & Qualcomm SM8250 Kona driver set             |
| - Flattened Device Tree Blob (sm8250-samsung-r8q.dtb) with /chosen node           |
| - Self-contained BusyBox early userspace initramfs with auto-probing              |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 5: Terminal-First Debian 12 Environment                          [COMPLETE] |
| - Native Debian 12 (Bookworm) ARM64 root filesystem (2048 MiB ext4)               |
| - multi-user.target default boot target (No X11, No Wayland by default)           |
| - High-resolution AMOLED text console on tty1 (16x32 Terminus font)               |
| - Native Bash shell, APT package management, development toolchain, OpenSSH       |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 6: Optional GNOME Desktop Layer                                  [SPECIFIED]|
| - Pluggable GNOME 43+ / Wayland / Mutter layer over base terminal system          |
| - Touchscreen gestures, mobile fractional scaling, on-screen keyboard              |
| - Independent GDM service management (systemctl start/stop/disable gdm3)          |
| - Zero dependency of core OS on graphical layer                                   |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 7: Hybrid Storage & Removable Multi-OS                           [COMPLETE] |
| - UUID / LABEL dynamic filesystem resolution                                      |
| - Secondary OS boot support (Kali ARM64, Ubuntu ARM64)                            |
| - Live USB OTG and MicroSD operating system discovery                             |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 8: Non-Destructive Installer & Recovery Packages                 [COMPLETE] |
| - LineageOS Recovery Flashable ZIP with sda25 zero-gap write guard                |
| - Self-contained Android Boot Image Header v2 container staged in sda24           |
| - Level 1 instant hardware fallback to untouched primary Android OS (sda23)       |
+-----------------------------------------------------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
| PHASE 9: Complete Platform Release & Cloud CI/CD                       [COMPLETE] |
| - Bit-exact reproducible distribution package (R8Q-Debian12-Full-System.tar.gz)   |
| - Cryptographic SHA-256 verification of all platform components                   |
| - Multi-target GitHub Actions automated build & test workflows                    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Immediate Next Engineering Tasks

1. **Phase 2 Implementation:** Implement the unified BIOS-style setup menu interface unifying the individual diagnostic applications (`platform/R8QPkg/Applications/`).
2. **Phase 3 Implementation:** Expand `LinuxBoot` into the standalone `BootManager.efi` supporting external `boot.cfg` and `entries/*.conf` parsing with interactive timeout and fallback menus.
3. **CI/CD Workflow Expansion:** Create the modular GitHub Actions workflows (`build-firmware.yml`, `build-boot-manager.yml`, `build-kernel.yml`, `build-initramfs.yml`, `build-debian-rootfs.yml`, `build-recovery.yml`, `test-platform.yml`) as requested in Part 14.
