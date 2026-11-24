# Project R8Q — Boot Chain Analysis

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 5G (`SM8250` / Kona)  
**Document Revision:** 3.0.0 (PrePi Relocation & Hardware Boot Realism)  
**Status:** Approved Engineering Baseline  

---

## 1. Executive Summary

This document details the exact, empirical boot sequence of the Samsung Galaxy S20 FE 5G Snapdragon platform. It establishes the precise handoff mechanism from Qualcomm and Samsung firmware down to the R8Q EDK II UEFI firmware, R8Q Boot Manager, and native Debian 12 ARM64 Linux kernel.

---

## 2. Low-Level Silicon & Bootloader Sequence

```
[POWER BUTTON PRESSED]
        |
        v
+----------------------------------------------------+
| 1. Qualcomm Primary Boot Loader (PBL)              |  Hardware ROM
|    - Initializes early system clocks               |  Executes in Secure World
|    - Reads SoC security eFuses                     |
|    - Validates & loads XBL into internal SRAM      |
+----------------------------------------------------+
        |
        v
+----------------------------------------------------+
| 2. eXtensible Boot Loader (XBL)                    |  Physical Partition: sdd1/sdd2
|    - Initializes LPDDR5 SDRAM controller           |  Qualcomm Reference Firmware
|    - Initializes PMIC, buses, and GPIOs            |
|    - Loads XBL_SEC / TrustZone (QSEE / QHEE)       |
+----------------------------------------------------+
        |
        v
+----------------------------------------------------+
| 3. Qualcomm Hypervisor & TrustZone (QHEE / QSEE)   |  Hardware Isolated (0x86000000)
|    - Configures ARM64 Exception Levels (EL3/EL2)   |  Secure World Monitor
|    - Enforces hardware memory protection (MPU/XPU) |
+----------------------------------------------------+
        |
        v
+----------------------------------------------------+
| 4. Samsung Application Boot Loader (ABL)           |  Physical Partition: sdd8 (abl)
|    - Executes in Non-Secure EL2 / EL1              |  Proprietary Samsung Implementation
|    - Evaluates hardware buttons during power-on    |
|    - Configures continuous splash AMOLED display   |
+----------------------------------------------------+
        |
        +---> [NORMAL BOOT] -----------> Boots /dev/block/sda23 (Primary Android OS / LineageOS)
        |
        +---> [VOL DOWN + USB] --------> Enters Samsung Download Mode (Odin / Loke Protocol)
        |
        +---> [VOL UP + USB] ----------> Boots /dev/block/sda24 (R8Q Boot Container)
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 5. R8Q Firmware Container (Android Boot Image v2 inside sda24)                                |
|    - ABL decompresses/loads kernel payload to DRAM base: 0x80080000                           |
|    - Jumps directly to R8Q PrePi entry point (ModuleEntryPoint.S)                             |
+-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 6. R8Q PrePi (Early Platform Initialization)                                                  |
|    - Sets up early stack at 0x9E890000 (Safe gap: +484 MiB from load, +512 KiB from FV)       |
|    - Relocates 4.00 MiB Firmware Volume (R8Q_EFI.fd) to 0x9E400000                            |
|    - Initializes memory controllers and hands off control to EDK II CEntryPoint               |
+-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 7. R8Q EDK II UEFI Firmware                                                                   |
|    - Initializes DXE Core & Dispatcher                                                        |
|    - Loads SimpleFbDxe: Binds GOP to continuous splash buffer (0x9C000000, 2400x1080 AMOLED)  |
|    - Loads FileVariableDxe: Persistent NVRAM stored in EFI/R8Q/nvram.bin                      |
|    - Loads StorageProtectionDxe: Intercepts block writes to strictly isolate sda25 (keyrefuge)|
|    - Initializes UFS and USB Mass Storage stacks                                              |
+-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 8. R8Q Boot Manager (EFI/BOOT/BOOTAA64.EFI)                                                   |
|    - Evaluates hotkeys: [Volume Down] -> Drops into BIOS Setup Utility                        |
|    - Scans Internal UFS, MicroSD, and USB OTG for compatible EFI applications and boot configs|
|    - Parses EFI/R8Q/Config/boot.cfg and entries/*.conf                                        |
|    - Displays boot selection menu (default 3s timeout)                                        |
+-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 9. Linux ARM64 EFI Stub Execution                                                             |
|    - Registers Device Tree Blob (DTB) with EFI System Table (gEfiDtbTableGuid)                |
|    - Installs LoadFile2 initrd protocol (gLinuxEfiInitrdMediaGuid)                            |
|    - Executes Kernel via LoadImage() and StartImage()                                         |
+-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 10. Native Linux Early Userspace (Initramfs)                                                  |
|     - Probes block devices for LABEL=r8q-rootfs or UUID=<uuid>                                |
|     - Handles physical partitions, SD cards, USB OTG, or loopback ext4 disk images            |
|     - Executes switch_root to /sbin/init (systemd)                                            |
+-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------+
| 11. Native Debian 12 ARM64 Terminal Environment                                               |
|     - systemd starts in multi-user.target                                                     |
|     - Spawns getty@tty1 (AMOLED DRM Console) and serial-getty@ttyMSM0 (GENI Serial)           |
|     - User logs into native Bash shell                                                        |
+-----------------------------------------------------------------------------------------------+
```

---

## 3. Ground Reality of Fastboot & Bootloader Modes on Retail Samsung

### 3.1 Why `fastboot boot` Fails on Retail Samsung Devices
A prevalent failure mode in mobile Linux development is assuming retail Qualcomm devices implement standard Android Fastboot in ABL. On the Samsung SM-G781B:
1. **Samsung Download Mode (Loke / Odin):**
   - ABL's primary recovery/flashing mode is the proprietary Odin/Loke protocol.
   - It communicates over vendor-specific USB endpoints and accepts `.tar` / `.tar.md5` archives.
2. **Userspace `fastbootd`:**
   - In Android 10+ / LineageOS, Fastboot exists only as a daemon (`fastbootd`) running inside the recovery userspace.
   - `fastbootd` supports flashing partitions (`fastboot flash recovery ...`) but explicitly rejects raw memory booting:
     `fastboot boot <image>` -> `FAILED (remote: 'Command not supported in fastbootd')`.
   - Samsung ABL does not listen on the Fastboot protocol port during early boot.

### 3.2 The Auxiliary Recovery Slot Solution (`sda24`)
Because Samsung ABL strictly boots from internal UFS partitions:
- **`sda23` (`boot`):** Preserved untouched. Contains the user's primary Android / LineageOS installation with Magisk root.
- **`sda24` (`recovery`):** Repurposed as the dedicated R8Q boot container slot.
- By staging R8Q as an Android Boot Image Header v2 container into `sda24`, the platform launches R8Q firmware seamlessly whenever the phone is powered on with `Power + Volume Up` (with USB tethered).
- Normal power button press continues to boot Android from `sda23`. This provides a zero-risk, non-destructive dual-boot hardware arrangement.

---

## 4. Boot Image Header v2 Specifications

Inspection of the primary boot architecture confirms that Samsung ABL on SM-G781B accepts Boot Image Header Version 2 containers:

| Header Field | Value on SM-G781B | R8Q Payload Alignment |
|---|---|---|
| **Magic** | `ANDROID!` (`0x414e44524f494421`) | Exact Android Boot Magic |
| **Header Version** | **v2** | Version 2 format |
| **Page Size** | **4096 bytes** | All segments 4096-byte page aligned |
| **Kernel Size** | 4,194,304 B + 64 B (or compound) | R8Q Firmware Volume + Linux EFI Stub Kernel |
| **Kernel Load Address** | `0x80080000` | Physical jump entry address |
| **Ramdisk Size** | 2,947,562 bytes | Rescue Initramfs buffer |
| **Ramdisk Load Address** | `0x81000000` / `0xA4400000` | Safe separation above firmware volume |
| **DTB Size** | 112,421 bytes | Flattened Device Tree Blob |
| **DTB Load Address** | DRAM high buffer | Passed to Linux kernel via EFI configuration table |
