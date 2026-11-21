# Project R8Q — Phase 3.3: Partition Geometry & Knox Keystore Safety Audit

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P33-06-PART`  
**Baseline Commit:** [`4e62ec4`](file:///root/r8q-uefi) (*"feat(phase3.2): architecture remediation, memory decoupling, native kernel 7.2.15 & full validation suite"*)  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Workstream Verdict:** **CONDITIONAL PASS**  

---

## 1. Executive Summary

This audit conducted a read-only hardware inspection of the GPT partition layout on physical UFS storage (`/dev/block/sda`), focusing on the boundary interactions between `sda23` (`boot`), `sda24` (`recovery`), and `sda25` (`keyrefuge`).

The audit confirms that:
1. The active LineageOS boot partition `sda23` (sector `1237144 - 1368215`) is completely separated from the recovery slot.
2. The recovery partition `sda24` has an exact physical capacity of **82,694,144 bytes (78.86 MiB)**.
3. The release boot image [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img) is **7,974,912 bytes (7.61 MiB)**, leaving **74,719,232 bytes (71.26 MiB / 90.3% free space)** of protective headroom.
4. Programmatic hard assertions embedded in [scripts/package_complete_boot_img.py](file:///root/r8q-uefi/scripts/package_complete_boot_img.py) strictly enforce this limit.

However, a high-severity safety finding was identified: **no verified raw backup of `sda24` (`sda24_recovery.img`) exists on storage.** Any future physical staging to `sda24` without creating a verified raw backup would permanently overwrite the existing LineageOS recovery environment (`P33-PARTITION-SAFETY-01`).

---

## 2. GPT Partition Geometry & Sector Layout

Read-only inspection of `/sys/block/sda/` and `/dev/block/by-name/` on the live hardware:

```
Physical UFS LUN 0 (/dev/block/sda, Sector Size = 512 Bytes)
========================================================================================================
Partition Node  Device Node      Start Sector    End Sector      Total Sectors   Capacity (Bytes / MiB)
--------------------------------------------------------------------------------------------------------
boot            /dev/block/sda23 1,237,144       1,368,215       131,072         67,108,864 B (64.0 MiB)
recovery        /dev/block/sda24 1,368,216       1,529,727       161,512         82,694,144 B (78.86 MiB)
keyrefuge       /dev/block/sda25 1,529,728       1,562,495        32,768         16,777,216 B (16.0 MiB)
...
userdata        /dev/block/sda36 24,084,480      238,284,799     214,200,320     109.67 GiB
========================================================================================================
```

---

## 3. The Zero-Sector Gap Knox Threat

### 3.1 Sector Boundary Geometry
- End of `sda24` (`recovery`): Sector **`1,529,727`**
- Start of `sda25` (`keyrefuge`): Sector **`1,529,728`**
- Sector Gap:
  $$\text{Gap} = 1529728 - 1529727 - 1 = \mathbf{0\ \text{sectors}\ (0\ \text{bytes})}$$

### 3.2 Knox Crypto Keystore Vulnerability
Partition `sda25` (`keyrefuge`) contains the hardware-bound Knox Keymaster crypto keystore, private cryptographic blobs, and full-disk encryption master keys. 

Because there is zero physical space between `sda24` and `sda25`, any partition write to `sda24` that exceeds `82,694,144` bytes by even a single sector will silently overwrite `sda25`. This triggers an irreversible hardware tamper condition that permanently bricks device storage encryption.

### 3.3 Safety Validation of Release Boot Image
```python
MAX_SDA24_CAPACITY = 82694144  # 161,512 sectors * 512 bytes
BOOT_IMAGE_SIZE    =  7974912  # build/r8q-uefi-boot-complete.img
REMAINING_HEADROOM = 74719232  # 71.26 MiB (90.35% free margin)
```
The packaging script [scripts/package_complete_boot_img.py](file:///root/r8q-uefi/scripts/package_complete_boot_img.py) incorporates a hard check:
```python
if total_bytes > MAX_SDA24_CAPACITY:
    os.remove(output_path)
    raise ValueError("CRITICAL SAFETY OVERRUN: Output boot image exceeds sda24 capacity!")
```
This mathematical invariant was verified by `test_07_compound_boot_image_v2_header`.

---

## 4. Current Contents of `sda24` (LineageOS Recovery)

Read-only inspection of sector 0 of `/dev/block/sda24` shows:
- Magic bytes: `ANDROID!`
- Format: Android Boot Image Header v2
- Kernel size: `55,767,064` bytes (53.18 MiB)
- Ramdisk size: `15,082,765` bytes (14.38 MiB)
- Status: **Active, operational LineageOS 23.2 Recovery Image**

---

## 5. Audit Finding

### Finding P33-PARTITION-SAFETY-01: Missing Verified Raw Image Backup of `sda24`
* **Finding ID:** `P33-PARTITION-SAFETY-01`
* **Severity:** **HIGH**
* **Affected Component:** [dev/block/sda24](file:///sys/block/sda/sda24) (Recovery Partition)
* **Evidence:**
  Automated search across the filesystem and repository for `*recovery*.img` and `sda24_recovery.img` confirmed that no raw block dump of `sda24` exists.
* **Reproduction Procedure:**
  Execute automated test:
  ```bash
  python3 -m unittest tests.test_phase3_3_independent_audit.TestPhase33IndependentAudit.test_audit_04_recovery_partition_backup_absence
  ```
* **Engineering Impact:**
  The Phase 3.2 documentation checklist asserted that a backup verification check should be passed, but the file was never generated. If an operator flashes `build/r8q-uefi-boot-complete.img` to `sda24` without dumping the current image, the existing working LineageOS recovery environment will be destroyed without an immediate local restoration path.
* **Recommended Remediation:**
  Before requesting any physical staging authorization, execute a read-only raw block dump of `sda24`:
  ```bash
  dd if=/dev/block/sda24 of=/root/r8q-uefi/artifacts/sda24_lineageos_recovery.img bs=4096 count=20189 status=progress
  sha256sum /root/r8q-uefi/artifacts/sda24_lineageos_recovery.img > /root/r8q-uefi/artifacts/sda24_lineageos_recovery.img.sha256
  ```
* **Verification Result:**
  Verified absence via `test_audit_04_recovery_partition_backup_absence`.
