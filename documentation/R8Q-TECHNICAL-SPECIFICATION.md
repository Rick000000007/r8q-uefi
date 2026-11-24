# Project R8Q — Master Technical Specification

**Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 5G (`SM8250` / Kona)  
**Platform Architecture:** ARM64 / AArch64 (ARMv8.2-A)  
**Document Revision:** 3.0.0 (Terminal-First Operating Architecture)  
**Status:** Authoritative Architectural Standard  

---

## 1. System Vision & Objective

Project R8Q transforms the Samsung Galaxy S20 FE 5G smartphone into an independent, standalone ARM64 pocket computer. It supersedes traditional mobile chroot/proot containers, Android emulation, and Termux layers by deploying genuine UEFI firmware, a BIOS-style hardware configuration interface, an independent multi-OS boot manager, and a native ARM64 Linux operating environment.

### Core Architectural Principle: Terminal-First Operation
The primary user experience is a **native ARM64 Linux terminal environment**.
- The system boots directly to a high-resolution Linux text console on the phone's AMOLED display.
- GNOME, GDM, and graphical display managers are strictly disabled in the default boot sequence.
- The default boot target is `multi-user.target`.
- The user interacts directly with a native Bash shell, utilizing standard Debian package management (`apt`/`dpkg`), development compilers (`gcc`, `clang`, `make`, `cmake`), scripting engines (`python3`), networking services (`NetworkManager`, `sshd`), and storage management tools.
- **GNOME Desktop is an optional, independent layer** that can be installed and launched on demand without making the core operating system dependent on graphical subsystems.

---

## 2. Six-Layer Platform Architecture

```
+-------------------------------------------------------------------------+
|                       LAYER 6: OPERATING SYSTEMS                        |
|   +---------------------------------+  +----------------------------+   |
|   |  Debian 12 ARM64 Terminal-First |  |  Optional GNOME Desktop    |   |
|   |  (Bash, APT, SSH, Dev Tools)    |  |  (Wayland, Mutter, GDM)    |   |
|   +---------------------------------+  +----------------------------+   |
|   |  Secondary OS (Kali ARM64 / Ubuntu ARM64 / Live USB OS)         |   |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                     LAYER 5: LINUX HARDWARE PLATFORM                    |
|   Linux 6.x ARM64 EFI Stub Kernel  |  Flattened Device Tree (DTB)       |
|   Early-Userspace Initramfs        |  Freedreno / SimpleFB Display      |
|   Qualcomm GENI Serial Drivers     |  UFS 3.0 & USB OTG Storage Drivers |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                       LAYER 4: R8Q BOOT MANAGER                         |
|   Multi-Boot Discovery (Internal UFS, MicroSD, USB OTG)                 |
|   Configuration Parser (boot.cfg, entries/*.conf)                       |
|   Linux EFI Stub Handoff (LoadImage / StartImage / LoadFile2)           |
|   Timeout, Boot Priority & Automated Recovery Fallback                  |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                   LAYER 3: BIOS-STYLE SETUP UTILITY                     |
|   Graphical / Text Setup UI (Main, Boot, Devices, Config, Security)     |
|   Hardware Status, Memory Inspector & Diagnostic Suite                  |
|   UEFI Interactive Shell Integration                                    |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                      LAYER 2: R8Q UEFI FIRMWARE                         |
|   EDK II AArch64 (R8QPkg) | PrePi Early Initialization                  |
|   GOP SimpleFbDxe (0x9C000000) | FileVariableDxe (ESP Persistence)      |
|   StorageProtectionDxe (Strict sda25 Write Blocker)                     |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                LAYER 1: SAMSUNG / QUALCOMM BOOT CHAIN                   |
|   PBL -> XBL -> Samsung ABL -> sda24 (Recovery Slot Android Boot v2)    |
|   Preserved Primary Android Boot (sda23) & LineageOS Recovery           |
+-------------------------------------------------------------------------+
```

---

## 3. Detailed Subsystem Specifications

### 3.1 Layer 1: Boot Chain & Execution Vector
- **Qualcomm Primary Boot Loader (PBL):** Initializes early clocks, reads eFuses, authenticates and loads XBL.
- **eXtensible Boot Loader (XBL):** Configures LPDDR5 SDRAM controller, clocks, and power management IC (PMIC).
- **Samsung Application Boot Loader (ABL):**
  - Evaluates hardware key combinations during power-on.
  - Normal Power-On: Boots primary Android OS from `sda23` (`boot`).
  - Power + Volume Up (with USB tether): Boots recovery slot from `sda24` (`recovery`).
  - R8Q firmware is staged inside `sda24` within an Android Boot Image Header v2 container.
- **Strict Safety Isolation:** Primary boot partition `sda23` remains 100% untouched. If R8Q firmware requires servicing or uninstallation, normal boot to LineageOS / Android remains immediately available.

### 3.2 Layer 2: R8Q UEFI Firmware
- **Base Framework:** EDK II (AArch64).
- **Firmware Volume Base:** `0x9E400000` (Size: 4.00 MiB / `0x00400000`).
- **PrePi Early Stack:** `0x9E890000` (descending 64 KiB buffer `0x9E880000 - 0x9E890000`), positioned safely within the unreserved 12.0 MiB System RAM gap (`0x9E400000 - 0x9EFFFFFF`).
- **GOP Framebuffer Driver (`SimpleFbDxe`):** Binds to continuous splash buffer at physical address `0x9C000000` (2400 × 1080 @ 32 bpp, 32.00 MiB buffer).
- **Non-Volatile Storage Driver (`FileVariableDxe`):** Stores UEFI environment variables persistently in `EFI/R8Q/nvram.bin` on the FAT32 ESP.
- **Hardware Protection Filter (`StorageProtectionDxe`):** Intercepts all block I/O requests; immediately aborts write transactions targeting cryptographic keystore `sda25`.

### 3.3 Layer 3: BIOS-Style Setup Utility
- **Execution:** Launched automatically on dedicated hotkey (Volume Down) during UEFI startup, or selected from Boot Manager.
- **Interface Structure:**
  - **MAIN:** SoC (SM8250), CPU architecture (ARMv8.2-A, 8 cores), total installed RAM (6 GB / 8 GB), firmware build date, commit SHA.
  - **BOOT:** Boot order priority (Internal UFS -> USB OTG -> MicroSD), default OS selection, boot timeout (default 3s).
  - **DEVICES:** Detected UFS LUNs, attached USB storage devices, SD cards, partition tables.
  - **CONFIGURATION:** Console font size, screen orientation, serial debug baud rate (115200 bps on GENI UART).
  - **SECURITY:** Secure boot status, firmware integrity digest, hardware protection flags.
  - **DIAGNOSTICS:** Memory test, display color bars, thermal sensor telemetry, battery fuel gauge.
  - **SHELL:** Drop into full EDK II interactive command shell (`Shell.efi`).

### 3.4 Layer 4: Independent R8Q Boot Manager
- **Format:** Independent EFI Application (`BOOTAA64.EFI` / `BootManager.efi`).
- **Configuration Format:** Human-readable, versioned `.conf` files:
  - Path: `EFI/R8Q/Config/boot.cfg`
  - Per-OS entries: `EFI/R8Q/Config/entries/<os-name>.conf`
- **Entry Structure:**
  ```ini
  title Debian 12 ARM64 Terminal
  version 1.0
  linux /EFI/R8Q/Kernels/vmlinuz-debian
  initrd /EFI/R8Q/Kernels/initramfs-debian.img
  dtb /EFI/R8Q/Kernels/sm8250-samsung-r8q.dtb
  options root=LABEL=r8q-rootfs rw console=tty0 console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0xa90000 systemd.unified_cgroup_hierarchy=1
  ```
- **Handoff Protocol:**
  - Verifies Linux ARM64 PE/COFF header (`ARM\x64` magic at offset 0x38).
  - Registers Flattened Device Tree via `gEfiDtbTableGuid` (`b1b626ec-2ac2-41a8-8548-c424911d5e6e`).
  - Installs `LoadFile2` protocol for Initrd handoff using `gLinuxEfiInitrdMediaGuid` (`5568e427-68fc-4f3d-ac74-640e80382041`).
  - Executes kernel via standard UEFI `LoadImage()` and `StartImage()`.

### 3.5 Layer 5: Linux Hardware Platform
- **Kernel:** Linux 6.x ARM64 with EFI Stub support and Qualcomm SM8250 Kona driver set.
- **Display Subsystem:** Framebuffer continuous splash handoff (`simplefb`) transitioning to DRM/KMS Mesa Freedreno driver for Adreno 650.
- **Console:** DRM/KMS console (`fbcon`) on the phone's AMOLED screen; secondary Qualcomm GENI UART console (`ttyMSM0`) active simultaneously.
- **Initramfs:** Self-contained BusyBox early userspace providing UUID/LABEL probing, loopback image mounting, and non-destructive fallback rescue shell.

### 3.6 Layer 6: Terminal-First Operating Environment & Optional Desktop
- **Base OS:** Debian GNU/Linux 12 (Bookworm) ARM64.
- **Default Target:** `multi-user.target` (No X11, No Wayland, No GDM).
- **Core Package Suite:**
  - Shell & Core Utilities: Bash, coreutils, util-linux, procps, iproute2, curl, wget, nano, vim, tmux, htop.
  - Package Management: `apt`, `dpkg` with official Debian Bookworm ARM64 repositories.
  - Networking & Remote Access: `NetworkManager`, `wpasupplicant`, OpenSSH client & hardened server (`sshd`).
  - Development Toolchain: GCC, Clang, GNU Binutils, Make, CMake, Python 3, Git, pkg-config.
  - Hardware Telemetry: `lm-sensors`, `usbutils`, `pciutils`, `dmidecode`.
- **Optional GNOME Layer:**
  - GNOME 43+ ARM64 suite (`gnome-shell`, `mutter`, `gdm3`, `gnome-terminal`, `wayland`).
  - Managed via `systemctl set-default graphical.target` or explicit `systemctl start gdm3`.
  - Can be fully disabled via `systemctl set-default multi-user.target` without touching core terminal functionality.

---

## 4. Protected Storage & Cryptographic Boundaries

| Storage Node | Role / Label | Safety Directive | Enforcement Mechanism |
|---|---|---|---|
| `/dev/block/sda25` | `keyrefuge` (Keystore) | **STRICTLY BLACKLISTED** | Pre-Pi write filter + `StorageProtectionDxe` + installer script guard |
| `/dev/block/sda23` | `boot` (LineageOS / Magisk) | **PRESERVED READ-ONLY** | Zero writes; R8Q boots solely from `sda24` |
| `/dev/block/sda24` | `recovery` (R8Q Boot Slot) | **DESIGNATED FIRMWARE SLOT** | Exact capacity bounds check (82,694,144 B) + SHA-256 pre-verification |
| Internal UFS / SD / USB | `r8q-rootfs` (Root Filesystem) | **DEDICATED LINUX STORAGE** | Ext4 filesystem identified exclusively by `LABEL` or `UUID` |
| Internal UFS / SD / USB | `R8Q_BOOT` (ESP FAT32) | **DEDICATED EFI PARTITION** | FAT32 filesystem containing EFI binaries, kernels, and configurations |
