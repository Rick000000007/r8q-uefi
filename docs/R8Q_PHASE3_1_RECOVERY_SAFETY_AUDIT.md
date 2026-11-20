# Project R8Q — Phase 3.1: Recovery Preservation & Safety Protocol Audit
**Document ID:** `R8Q-DOC-AUD-004`  
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform Storage:** Qualcomm UFS 3.1 (`1d84000.ufshc`, LUN 0 / `sda`)  
**Audited Targets:** `sda23` (`boot`), `sda24` (`recovery`), `sda25` (`keyrefuge`)  
**Audit Status:** CRITICAL GEOMETRY CORRECTION (Hardware Key Corruption Hazard Identified)  

---

## 1. Executive Summary & Critical Geometry Correction

This independent audit verified the physical partition geometry, sector bounds, backup procedures, restoration commands, and unbrick assumptions for the recovery-slot staging strategy on the Samsung Galaxy S20 FE 5G (`SM-G781B`).

> [!CAUTION]
> **CRITICAL PARTITION GEOMETRY CORRECTION [FAILED CHECK]:**  
> In all previous project milestones, `sda24` was reported as `83,886,080 bytes (80.00 MiB)`.  
> **Direct physical kernel sysfs query proves `sda24` is actually `82,694,144 bytes (78.86 MiB)`.**  
> - Reported Size: `83,886,080` bytes (`20,480` blocks of 4096B).  
> - **Actual Physical Size:** `82,694,144` bytes (`161,512` sectors of 512B / `20,189` blocks of 4096B).  
> - Discrepancy: `1,191,936` bytes (1.14 MiB) **LESS** than reported.  
> 
> **SEVERE HARDWARE RISK:**  
> The partition directly following `sda24` on UFS LUN 0 is **`sda25` (`keyrefuge`, 16.0 MiB)**, which stores Samsung Knox and Qualcomm TrustZone hardware cryptographic keys.  
> If an operator restored an assumed 80.00 MiB image or executed an 80 MiB padded write to `sda24`, `dd` would spill `1,191,936 bytes` past the partition boundary into **`sda25` (`keyrefuge`)**, permanently destroying hardware encryption keys and bricking device security.

```
+-------------------------------------------------------------------------------------------------+
|                        PHYSICAL UFS LUN 0 PARTITION GEOMETRY & HAZARD                           |
+-------------------------------------------------------------------------------------------------+
|  PARTITION | DEV   | SECTORS (512B)| EXACT BYTES  | MiB       | FUNCTION & AUDIT STATUS         |
+------------+-------+---------------+--------------+-----------+---------------------------------+
|  boot      | sda23 | 131,072       | 67,108,864   | 64.00 MiB | Active LineageOS [READ-ONLY]    |
|            |       |               |              |           | (Report misstated as 80 MiB)    |
+------------+-------+---------------+--------------+-----------+---------------------------------+
|  recovery  | sda24 | 161,512       | 82,694,144   | 78.86 MiB | Temporary R8Q Staging Target    |
|            |       |               |              |           | (Report misstated as 80 MiB)    |
+------------+-------+---------------+--------------+-----------+---------------------------------+
|  keyrefuge | sda25 | 32,768        | 16,777,216   | 16.00 MiB | Knox/TrustZone Hardware Keys    |
|            |       |               |              |           | !!! EXPOSED TO SPILLOVER !!!    |
+------------+-------+---------------+--------------+-----------+---------------------------------+
```

---

## 2. Boot Container Margin Verification on Corrected Geometry

Now that the true capacity of `sda24` is established (`82,694,144 bytes`), we re-verify the physical staging headroom for [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img):

- **Corrected Target Partition Size (`sda24`):** `82,694,144` bytes (78.86 MiB).
- **Compound Boot Container Size:** `55,554,048` bytes (52.98 MiB).
- **Actual Remaining Headroom Margin:** `27,140,096` bytes (25.88 MiB / 32.8% free space).
- **Audit Verification [FACT]:** Because `55,554,048 < 82,694,144`, writing the exact 52.98 MiB compound container directly via `dd` will terminate safely at byte offset `55,554,048`, leaving `27,140,096 bytes` untouched before the `sda25` boundary.
- **Mandatory Safety Rule:** Staging and backup scripts must **NEVER** pad images to 80 MiB, and must enforce `count=20189 bs=4096` or strict file size limits.

---

## 3. Independent Audit of Backup & Restoration Commands

### 3.1 Backup Command Review
Declared backup command:
```bash
dd if=/dev/block/by-name/recovery of=/root/r8q-uefi/backups/recovery_lineageos_backup.img bs=4096 status=progress conv=fsync
```
- **Block Device Selection [FACT]:** `/dev/block/by-name/recovery` resolves via verified udev symlink to `/dev/block/sda24`. Correct.
- **Completeness [FACT]:** In Linux, reading from a partition block device without `count=` reads until the partition EOF (`82,694,144 bytes`).
- **Data Flushing [FACT]:** `conv=fsync` forces physical sync of output file data and metadata before process termination. Correct.
- **Independent Hash Verification [FACT]:** Three-way hash comparison across `/dev/block/by-name/recovery`, local storage backup, and external MicroSD ensures complete copy fidelity.

### 3.2 Restoration Command & Safeguard Deficiencies
Declared restoration command:
```bash
dd if=/root/r8q-uefi/backups/recovery_lineageos_backup.img of=/dev/block/by-name/recovery bs=4096 status=progress conv=fsync
```
- **Audit Finding [WARNING / DEFECT]:**  
  Raw `dd` offers **zero protective safeguards**:
  1. If an operator accidentally points `of=` to `/dev/block/by-name/boot` or `/dev/block/sda23`, `dd` will execute immediately and destroy the active LineageOS boot partition.
  2. If the input image is oversized (> 78.86 MiB), `dd` will write across the partition boundary into `sda25` (`keyrefuge`).
- **Mandatory Engineering Remediation:**  
  Create an automated shell script `scripts/restore_recovery.sh` that implements programmatic safeguards:
  ```bash
  #!/bin/bash
  set -e
  IMAGE="$1"
  TARGET="/dev/block/by-name/recovery"
  REAL_TARGET="$(realpath "$TARGET")"
  
  [ "$REAL_TARGET" = "/dev/block/sda24" ] || { echo "ERROR: Target is not sda24!"; exit 1; }
  ACTUAL_SIZE="$(stat -c%s "$IMAGE")"
  [ "$ACTUAL_SIZE" -eq 82694144 ] || { echo "ERROR: Image size ($ACTUAL_SIZE) != 82694144 bytes!"; exit 1; }
  
  dd if="$IMAGE" of="$TARGET" bs=4096 count=20189 status=progress conv=fsync
  sync
  ```

---

## 4. Unproven Unbrick Assumptions: Download Mode, Odin & Heimdall

In previous planning documents, Samsung Download Mode, Odin, and Heimdall were cited as guaranteed fallback recovery mechanisms.

### 4.1 Heimdall on Linux Limitations
- **Audit Finding [INFERENCE / UNPROVEN ASSUMPTION]:**  
  1. Heimdall 1.4.2 on Linux is notorious for protocol incompatibilities with Qualcomm Snapdragon 865 UFS devices.
  2. On Galaxy S20 series devices, Heimdall frequently fails during the PIT (Partition Information Table) download handshake with error `Failed to receive session confirmation!` or `Protocol error`.
  3. Relying on Heimdall on Linux as an emergency unbrick tool is an **UNPROVEN ASSUMPTION**.
  4. The only 100% verified tool for emergency Samsung Download Mode flashing is official **Samsung Odin3 v3.14.4** running on Windows (or patched Thor utility).

### 4.2 Knox Tripping & Download Mode Accessibility
- **Audit Finding [FACT]:**  
  1. Bootloader unlocking on SM-G781B permanently trips Knox EFUSE (`0x1`).
  2. Download Mode remains physically accessible via hardware combination: power off, hold `Volume Up` + `Volume Down` simultaneously, and connect USB-C cable to host PC.
  3. However, if TrustZone (`sda25` / `keyrefuge`) or XBL is corrupted, the device cannot reach Download Mode and enters Qualcomm EDL Mode (`QUSB_BULK_CID:` / `USB ID 05c6:9008`), which requires specialized Qualcomm Sahara/Firehose emergency programmers that are cryptographically locked by Samsung OEM root keys.

---

## 5. Audit Verdict

| Verification Item | Prior Claim | Ground-Truth Finding | Verdict |
| :--- | :--- | :--- | :--- |
| **sda24 Size** | 83,886,080 bytes (80 MiB) | 82,694,144 bytes (78.86 MiB) | **CRITICAL CORRECTION** |
| **sda23 Size** | 83,886,080 bytes (80 MiB) | 67,108,864 bytes (64.00 MiB) | **CORRECTION** |
| **Keyrefuge Hazard** | Not analyzed | Overwrite hazard if 80 MiB image written | **SEVERE HAZARD IDENTIFIED** |
| **Staging Headroom** | 28.33 MiB margin | 27.14 MiB margin (Safe for 52.98 MiB container) | **PASS** |
| **Raw `dd` Safeguards**| Declared safe | Lacks identity checks and size bounds | **DEFECT** |
| **Heimdall Recovery** | Stated as unbrick path | Known UFS PIT protocol handshake failures | **UNPROVEN ASSUMPTION** |
