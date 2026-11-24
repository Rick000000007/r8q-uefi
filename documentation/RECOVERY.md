# Project R8Q — Recovery & Failsafe Architecture

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Document Revision:** 3.0.0 (Failsafe Operation & Reversion Protocol)  
**Status:** Approved Recovery Standard  

---

## 1. Architectural Failsafe Guarantee

Project R8Q is designed so that a failure in the R8Q firmware, kernel, or root filesystem **cannot brick the device or render the primary Android operating system unbootable**.

### The Three Recovery Vectors:
1. **Level 1 (Instant Hardware Reversion):** Normal power button boot bypasses `sda24` entirely and boots Android / LineageOS from `sda23`.
2. **Level 2 (Firmware / Boot Manager Fallback):** If an OS configuration entry is damaged, R8Q Boot Manager times out and drops into the BIOS-style Setup Utility or interactive UEFI Shell (`Shell.efi`).
3. **Level 3 (Early Userspace Emergency Shell):** If the Debian root filesystem cannot be located or mounted, the initramfs drops to a self-contained BusyBox rescue shell with diagnostic tools.

---

## 2. Recovery Procedures

```
+---------------------------------------------------------------------------------+
|                               BOOT FAILURE MODES                                |
+---------------------------------------------------------------------------------+
                                         |
            +----------------------------+----------------------------+
            |                                                         |
  [Failure in R8Q UEFI / Kernel]                            [Rootfs Mount Failure]
            |                                                         |
            v                                                         v
   Simply reboot normally                                    Initramfs Rescue Shell
   (Press Power button alone)                                Spawns /bin/sh on tty1
            |                                                         |
            v                                                         v
   Boots LineageOS from sda23                                Run /sbin/emergency_rescue.sh
   (Android completely intact)                               Fix filesystem / inspect logs
```

### 2.1 Restoring LineageOS Recovery (Complete Uninstallation)
If the user wishes to remove Project R8Q from `sda24` and restore the original LineageOS recovery environment:
1. Obtain the verified original backup of `sda24` stored in the repository:
   - File: `artifacts/sda24_lineageos_recovery.img`
   - Exact Size: 82,694,144 Bytes
   - SHA-256: `189e3ec0c1a9ffae78d5272a8c38fa53896fa2b87f461fc1ea2bb09d06855118`
2. Flash the backup image back to `sda24`:
   ```bash
   # From rooted Android / LineageOS terminal:
   su
   dd if=sda24_lineageos_recovery.img of=/dev/block/bootdevice/by-name/recovery bs=4096 conv=fsync
   ```
3. Recovery mode is now 100% restored to stock LineageOS Recovery.

---

## 3. Initramfs Emergency Rescue Shell

If the Linux kernel boots but cannot locate the root filesystem (e.g., USB drive disconnected, partition UUID mismatch, corrupted filesystem table):
1. The initramfs emits diagnostic error messages to `tty1` and `ttyMSM0`.
2. The initramfs launches a rescue shell:
   ```
   ==========================================================
      PROJECT R8Q: EARLY-USERSPACE RESCUE SHELL
      Target: Samsung Galaxy S20 FE 5G (SM-G781B)
   ==========================================================
   [FAIL] Target rootfs volume not detected within 10 seconds.
   Dropping to emergency recovery shell. Type 'exit' to retry.
   / # 
   ```
3. Available rescue commands:
   - `blkid`: Display all attached storage devices and UUIDs.
   - `lsblk`: List block device topology.
   - `e2fsck -y /dev/sdX`: Check and repair ext4 filesystem errors.
   - `cat /proc/partitions`: Check kernel partition table recognition.
   - `/sbin/emergency_rescue.sh`: Run automated filesystem scan and diagnostic summary.
