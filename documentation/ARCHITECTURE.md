# Project R8Q — Platform Architecture

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250 Kona)  
**Document Revision:** 3.0.0 (Terminal-First Architectural Design)  
**Status:** Authoritative Platform Architecture  

---

## 1. Architectural Philosophy

Project R8Q conceives the mobile device as an open, modular ARM64 personal computer. Rather than presenting a constrained Android userspace or a containerized chroot, Project R8Q establishes:
1. An open standard UEFI firmware foundation based on EDK II.
2. A BIOS-style hardware setup utility giving the user visibility and control over platform state.
3. An independent operating system boot manager decoupled from any single OS vendor.
4. A native ARM64 Linux kernel and early userspace operating directly on the bare metal.
5. A high-performance, terminal-first operating environment optimized for local development and system administration.
6. An optional, pluggable graphical desktop layer (GNOME / Wayland) that can be installed, started, stopped, or disabled at will.

---

## 2. Global Memory Map & Early Layout

Physical memory on the SM8250 r8q starts at base `0x80000000` (2048 MiB boundary) and spans 6 GiB or 8 GiB of LPDDR5 SDRAM.

```
+-----------------------------------+ 0xFFFFFFFF (Top of 32-bit Addressable RAM / High DRAM)
|                                   |
|   Linux OS System RAM             | Available for Debian 12 userspace and kernel allocations
|   (Unreserved Dynamic Memory)     |
|                                   |
+-----------------------------------+ 0xA46D0000
|   Rescue Initramfs Buffer         | Early initramfs staging (~2.81 MiB)
+-----------------------------------+ 0xA4400000
|   Linux Kernel Image Entry        | ARM64 EFI Stub Kernel decompressed/loaded buffer
+-----------------------------------+ 0xA0000000
|   Samsung / Modem Debug Traces    | Reserved debug window
+-----------------------------------+ 0x9F000000
|   Unreserved Safety Gap           | PrePi Early Stack buffer (0x9E880000 - 0x9E890000)
+-----------------------------------+ 0x9E800000
|   R8Q EDK II Firmware Volume (FV) | R8Q_EFI.fd (4.00 MiB: 0x9E400000 - 0x9E7FFFFF)
+-----------------------------------+ 0x9E400000
|   Continuous Splash Framebuffer   | 2400 x 1080 @ 32bpp AMOLED GOP Buffer (32.00 MiB)
+-----------------------------------+ 0x9C000000
|   TrustZone / Qualcomm QSEE / AOP | Hardware Cryptographic Isolated Enclave (Secure World)
+-----------------------------------+ 0x86000000
|   Samsung ABL Entry Vector        | Physical entry for boot containers (0x80080000)
+-----------------------------------+ 0x80000000 (DRAM Base)
```

### PrePi Memory Safety Guarantees
In earlier prototypes, a flawed stack pointer placed at `0x80110000` caused memory self-corruption during early C code execution. The current architecture places the PrePi stack at `0x9E890000`:
- **+484 MiB** separation from the initial load address `0x80080000`.
- **+512 KiB** safety margin above the 4 MiB firmware volume (`0x9E400000 - 0x9E7FFFFF`).
- **Zero overlap** with the display continuous splash buffer (`0x9C000000 - 0x9E3FFFFF`) or TrustZone (`0x86000000`).

---

## 3. Subsystem Breakdown

### 3.1 Layer 1: Hardware Boot Chain Integration
- **Platform:** Qualcomm Snapdragon 865 (SM8250).
- **Execution Mechanism:** Samsung ABL boots recovery container from UFS partition `sda24` (`recovery`).
- **Container Format:** Android Boot Image Header v2 with page size 4096.
- **Safety Boundary:** Primary Android boot partition `sda23` is completely preserved. Zero risk to existing mobile workflow or emergency phone calling capabilities.

### 3.2 Layer 2: R8Q UEFI Firmware
- **Framework:** EDK II AArch64.
- **Components:**
  - `PrePi`: Assembly reset vector and early C memory initialization.
  - `SimpleFbDxe`: Binds GOP (Graphics Output Protocol) to physical buffer `0x9C000000`.
  - `FileVariableDxe`: Implements UEFI runtime variable storage backed by `EFI/R8Q/nvram.bin`.
  - `StorageProtectionDxe`: Hardened write-block filter intercepting EFI block protocol requests to protect `sda25`.
  - Core DXE drivers: Partition, FAT, Disk I/O, USB Mass Storage, HII Database.

### 3.3 Layer 3: BIOS-Style Setup Utility
- **Execution:** Launched on boot key press (Volume Down) or via Boot Manager menu.
- **Sub-pages:**
  1. Main (System summary, CPU info, RAM, firmware version).
  2. Boot (Boot priority, timeout, fallback rules).
  3. Devices (Discovered UFS, SD, USB storage, and EFI filesystems).
  4. Configuration (Display resolution, console font, UART debug).
  5. Security (Secure boot status, integrity checksums, write guards).
  6. Diagnostics (Memory integrity test, display patterns, battery & thermal telemetry).
  7. Shell (Interactive EDK II UEFI Shell).

### 3.4 Layer 4: Independent Boot Manager
- **Execution:** Installed at `EFI/BOOT/BOOTAA64.EFI` and `EFI/R8Q/BootManager.efi`.
- **Role:** Autonomous discovery of EFI operating system loaders across internal UFS, microSD, and USB OTG storage.
- **Configuration Parsing:** Evaluates versioned configuration files (`EFI/R8Q/Config/boot.cfg` and `entries/*.conf`).
- **Protocol Handoff:**
  - Injects Flattened Device Tree (FDT) into EFI Configuration Table (`gEfiDtbTableGuid`).
  - Installs Linux EFI Initrd Media protocol (`LoadFile2`).
  - Passes Linux bootargs (`console=tty0 console=ttyMSM0,115200n8 root=LABEL=r8q-rootfs rw`).
  - Executes Linux EFI Stub via `LoadImage()` / `StartImage()`.
  - Automated Recovery: On boot error or kernel failure, falls back to the Boot Manager menu or diagnostic rescue shell.

### 3.5 Layer 5: Linux Hardware Platform
- **Kernel:** 64-bit ARM64 kernel with built-in EFI stub and SM8250 platform drivers.
- **Early Userspace (Initramfs):** Self-contained BusyBox environment.
  - Scans block devices for `LABEL=r8q-rootfs` or `UUID=<uuid>`.
  - Supports booting from physical partitions or raw disk images on internal UFS, SD card, or USB flash drive.
  - Switches root using `switch_root` to `/sbin/init` (systemd).
- **Display Subsystem:** Framebuffer continuous splash transition to DRM/KMS Freedreno driver for Adreno 650.

### 3.6 Layer 6: Terminal-First Operating Environment
- **Base Distribution:** Debian GNU/Linux 12 (Bookworm) ARM64.
- **Target Mode:** `multi-user.target`.
- **Active Consoles:**
  - `tty1`: Framebuffer text console on AMOLED display (2400 × 1080) with readable font scaling (`FONTFACE="Terminus"`, `FONTSIZE="16x32"`).
  - `ttyMSM0`: Qualcomm GENI UART serial console (115200 bps).
- **Core Toolset:** Bash, APT, OpenSSH client/server, Git, GCC, Clang, Python 3, Make, CMake, NetworkManager, USB and storage utilities.
- **Optional Desktop:** GNOME 43+ desktop environment can be installed and enabled without modifying the underlying terminal-first foundation.
