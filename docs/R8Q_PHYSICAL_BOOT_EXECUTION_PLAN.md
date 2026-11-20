# Project R8Q — Physical First-Boot Execution Plan & Safety Protocol
**Document ID:** `R8Q-DOC-PBP-001`  
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Target Boot Partition:** `sda24` (`/dev/block/by-name/recovery`, 80.00 MiB)  
**Protected Normal Partition:** `sda23` (`/dev/block/by-name/boot`, 80.00 MiB)  
**Compound Boot Image:** [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img)  
**Image SHA-256:** `dbc59dc0c3447c53a68ea7669e0c4446ef5fd9812ccb73d192d593549836f206`  
**Authorization Status:** STRICTLY NON-EXECUTING (Dry-Run & Planning Only)  

---

## 1. Safety Boundary & Authorization Warning

> [!CAUTION]
> **STRICT EXECUTION BOUNDARY:**  
> This document is an offline engineering execution plan and safety protocol ONLY.  
> **IT DOES NOT AUTHORIZE PHYSICAL EXECUTION.**  
> - No writing to `sda23` or `sda24`.  
> - No writing to any internal UFS partition (`sda` through `sdf`).  
> - No staging, flashing, or dd operations.  
> - No physical reboots, power cycles, or hardware triggers.  
> Physical execution remains strictly prohibited until explicit, independent user authorization is granted.

---

## 2. Partition Geometry & Staging Target Verification

### 2.1 Hardware Partition Audit
The Samsung Galaxy S20 FE 5G (`SM-G781B`) uses a Qualcomm UFS 3.1 storage controller (`1d84000.ufshc`) divided into multiple LUNs:
- **LUN 0 (`sda`):** Userdata, System, Vendor, Boot, Recovery.
- **Active Boot Slot (`sda23`):** Contains the primary LineageOS 23.2 Linux kernel and Magisk root payload.
- **Test Staging Slot (`sda24`):** Contains the LineageOS Recovery ramdisk and kernel.

```
+-------------------------------------------------------------------------------------------------+
|                                 UFS LUN 0 PARTITION ISOLATION TOPOLOGY                          |
+-------------------------------------------------------------------------------------------------+
|  PARTITION | BLOCK DEV | START SECTOR | END SECTOR | SIZE (BYTES) | SIZE (MiB) | ROLE & POLICY      |
+------------+-----------+--------------+------------+--------------+------------+--------------------+
|  boot      | sda23     | 3,407,872    | 3,428,351  | 83,886,080   | 80.00 MiB  | Active LineageOS   |
|            |           |              |            |              |            | [STRICT READ-ONLY] |
+------------+-----------+--------------+------------+--------------+------------+--------------------+
|  recovery  | sda24     | 3,428,352    | 3,448,831  | 83,886,080   | 80.00 MiB  | Temporary R8Q Test |
|            |           |              |            |              |            | [STAGING TARGET]   |
+------------+-----------+--------------+------------+--------------+------------+--------------------+
```

### 2.2 Capacity Verification
- **Target Partition Size (`sda24`):** `83,886,080` bytes (80.00 MiB, exactly 20,480 blocks of 4096 bytes).
- **Staging Artifact (`build/r8q-uefi-boot-complete.img`):** `55,554,048` bytes (52.98 MiB).
- **Free Headroom Margin:** `28,332,032` bytes (27.02 MiB / 33.8% free space).
- **Safety Assertion:** The compound boot container fits within the recovery partition with ample safety margin, preventing truncation or partition spillover.

---

## 3. Bit-for-Bit Backup & Restoration Protocol

### 3.1 Mandatory Dual Backup Procedure
Before any write to `sda24` is ever performed under future authorization, the existing LineageOS Recovery partition must be backed up to two distinct storage mediums:

1. **Local Persistent Storage Backup:**
   ```bash
   mkdir -p /root/r8q-uefi/backups
   dd if=/dev/block/by-name/recovery of=/root/r8q-uefi/backups/recovery_lineageos_backup.img bs=4096 status=progress conv=fsync
   ```
2. **External MicroSD Card Backup (Cold Standby):**
   ```bash
   dd if=/dev/block/by-name/recovery of=/mnt/storage/recovery_lineageos_backup.img bs=4096 status=progress conv=fsync
   ```

### 3.2 Backup Integrity Verification (Three-Way Checksum)
Both backup copies must be hashed and compared against the live partition block device:
```bash
sha256sum /dev/block/by-name/recovery \
          /root/r8q-uefi/backups/recovery_lineageos_backup.img \
          /mnt/storage/recovery_lineageos_backup.img
```
> [!IMPORTANT]
> **STOP CONDITION:** If all three SHA-256 hashes are not 100% identical, the staging sequence is **ABORTED IMMEDIATELY**.

### 3.3 Emergency Restoration Procedure
In the event of an unexpected boot loop, visual freeze, or when restoring standard LineageOS recovery functionality, the backup image is restored bit-for-bit:
```bash
dd if=/root/r8q-uefi/backups/recovery_lineageos_backup.img of=/dev/block/by-name/recovery bs=4096 status=progress conv=fsync
sync
```
Integrity check after restoration:
```bash
sha256sum /dev/block/by-name/recovery /root/r8q-uefi/backups/recovery_lineageos_backup.img
```

---

## 4. Pre-Boot Preconditions Checklist

All items below must be physically verified prior to initiating any future physical boot attempt:

- [ ] **Battery State of Charge:** Verified `>= 80%` (or connected to external power delivering `>= 15W`).
- [ ] **Host Workstation Connectivity:** USB-C cable connected between phone and Linux development PC.
- [ ] **Host Toolchain Ready:** `adb` and `fastboot` (or `heimdall`) installed and responsive on host workstation.
- [ ] **Unmolested Boot Partition:** `sda23` SHA-256 verified against active LineageOS boot hash.
- [ ] **Dual Backups Generated & Verified:** Both local and MicroSD backups of `sda24` match `sha256sum`.
- [ ] **MicroSD Rootfs Staged:** External MicroSD card formatted with GPT, ESP on partition 1, Ext4 rootfs on partition 2 (`/dev/mmcblk0p2`).
- [ ] **Samsung Download Mode Accessible:** Verified key combination (`Volume Up` + `Volume Down` while plugging in USB-C) enters Odin Download Mode for emergency firmware unbrick.

---

## 5. Expected Physical Hardware Behaviors & Diagnostics

### 5.1 Visual Display Progression (AMOLED Panel)
1. **0 to 2 seconds:** Samsung Knox unlocked bootloader warning screen appears.
2. **2 to 5 seconds:** ABL processes recovery boot trigger; continuous splash maintained at `0x9C000000`.
3. **5 to 8 seconds:** ARM64 wrapper relocates PrePi to `0x9E400000`. EDK II GOP initializes continuous splash framebuffer.
4. **8 to 15 seconds:** EDK II boot logo renders on AMOLED panel at native 1080x2400 resolution.
5. **15 to 25 seconds:** Linux ARM64 EFI Stub executes; SimpleDRM framebuffer console displays kernel boot logs (`[    0.000000] Linux version 7.2.15+kali-arm64`).
6. **25 to 40 seconds:** Systemd reaches `multi-user.target`. Virtual terminal login prompt displayed (`r8q-linux login:`).

### 5.2 Serial Debug Output (GENI UART 8 @ 115200 8N1)
```text
[PrePi] Samsung SM-G781B (r8q) EDK II Starting...
[PrePi] CPU: Qualcomm Snapdragon 865 (SM8250 / Kona)
[PrePi] DRAM Base: 0x80000000, Size: 8192 MB
[PrePi] Firmware Relocated to: 0x9E400000 - 0x9E800000
[PrePi] Stack Base: 0x9E880000, Limit: 0x9E800000 (Safe Non-Overlap Confirmed)
[PrePi] Continuous Splash Framebuffer detected at 0x9C000000 (1080x2400)
[DXE] Loading Drivers: SerialDxe, GopDxe, TimerDxe, CpuDxe, PartitionDxe...
[BDS] Launching Linux ARM64 EFI Stub...
[Linux] EFI stub: Booting Linux Kernel...
[Linux] EFI stub: Using DTB from configuration table
[Linux] EFI stub: Exiting boot services and installing virtual address map...
[    0.000000] Booting Linux on physical CPU 0x0000000000 [0x510f805e]
[    0.000000] Linux version 7.2.15+kali-arm64
[    2.150000] ufs-qcom 1d84000.ufshc: Qualcomm UFS host controller initialized (RO policy)
[    2.820000] mmc0: Qualcomm SDHCI controller initialized, detected 64GB MicroSD card
[    4.200000] systemd 262-1 running in system mode
[    8.500000] Welcome to Debian GNU/Linux 12 (bookworm) / Kali Linux ARM64!
r8q-linux login: 
```

---

## 6. Success Criteria, Timeout Boundaries & Stop Conditions

### 6.1 Success Criteria
- **Tier 1 (Firmware Boot):** EDK II PrePi prints banner over GENI UART 8 and GOP displays on AMOLED.
- **Tier 2 (Kernel Handoff):** Linux ARM64 EFI Stub transitions execution from UEFI to Linux kernel.
- **Tier 3 (Userspace Init):** Systemd mounts root filesystem from MicroSD card and initializes user services.
- **Tier 4 (Interactive Access):** Serial console or USB network SSH login shell accessible.

### 6.2 Failure Boundaries & Watchdog Timeouts
- **Hard Timeout Boundary:** 60 seconds from power-on / reboot trigger.
- **Visual Stagnation Threshold:** If screen remains unlit or black for `> 15 seconds`, trigger Recovery Protocol.
- **Continuous Reboot Loop:** If device reboots into Samsung splash more than twice, trigger Recovery Protocol.

### 6.3 Hard Stop Conditions
The physical staging sequence must be **ABORTED IMMEDIATELY** if any of the following occur:
1. `sda24` backup checksum mismatch.
2. Battery state drops below 80%.
3. Host USB disconnection during staging.
4. Device bootloader flags indicate locked state (`SECURE BOOT: ENABLE`).
5. UFS write access errors.

---

## 7. Emergency Recovery Procedures

### Level 1: Standard Cold Reboot (Preserve LineageOS)
If the device hangs in early PrePi or kernel execution:
1. Press and hold `Power` + `Volume Down` simultaneously for exactly 7 seconds.
2. Release both buttons the moment the phone vibrates.
3. Allow the device to boot normally into LineageOS 23.2 from `sda23`.

### Level 2: Emergency Samsung Download Mode (Odin / Heimdall)
If the device bootloops and fails to reach normal boot:
1. Power down the device (hold `Power` + `Volume Down` for 10 seconds).
2. Hold `Volume Up` + `Volume Down` simultaneously.
3. While holding both volume buttons, insert the USB-C cable connected to the PC host.
4. The teal Samsung Download Mode screen will appear.
5. Press `Volume Up` once to confirm download mode.
6. Using `heimdall` or `Odin` on the host PC, flash the stock Samsung/LineageOS recovery image to `sda24` (`RECOVERY`):
   ```bash
   heimdall flash --RECOVERY /root/r8q-uefi/backups/recovery_lineageos_backup.img
   ```

---

## 8. Honest Engineering Caveats

> [!WARNING]
> While this plan implements comprehensive defense-in-depth safety measures—including dual bit-for-bit backups, isolated recovery-slot staging, and non-overlapping memory layouts—**PHYSICAL HARDWARE FLASHING AND BOOTING CAN NEVER BE 100% RISK-FREE**.  
> Hardware anomalies, power loss during flash writes, or undocumented Knox bootloader behaviors can result in bootloader corruption.  
> Proceeding to physical staging requires complete user acknowledgment of these physical hardware realities.
