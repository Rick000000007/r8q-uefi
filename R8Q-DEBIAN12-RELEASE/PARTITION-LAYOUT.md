# Project R8Q — UFS Partition Layout & Block Arithmetic Specification

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / `SM8250` Kona)  
**SoC:** Qualcomm Snapdragon 865  
**Hardware Storage:** Qualcomm UFS 3.1 Host Controller (`1d84000.ufshc`), LUN 0 (`/dev/block/sda`)  
**Sector Size:** 512 Bytes (Standard physical and logical block granularity)  
**Document Classification:** Authoritative Storage Geometry  
**Baseline Commit:** `4312b18eca26f7b44a99fd74e5c703109688d97d`  

---

## 1. Authoritative Partition Geometry Table

The following partition boundaries represent **authoritative empirical evidence** extracted directly from live Qualcomm SM8250 UFS host controller sysfs on the target handset (`/sys/block/sda/sda*/start` and `/sys/block/sda/sda*/size`):

| Partition Node | Symlink (`/dev/block/by-name/`) | Partition Role | Start Sector | End Sector (Inclusive) | Total Sectors | Capacity (Bytes) | Exact Capacity (MiB) | Safety Classification & Access Boundary |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`/dev/block/sda21`** | `dsp` | Hexagon DSP Firmware | `1,085,592` | `1,216,663` | `131,072` | `67,108,864` | 64.00 MiB | Protected System Firmware (Read-Only) |
| **`/dev/block/sda22`** | `dtbo` | Device Tree Overlay | `1,216,664` | `1,237,143` | `20,480` | `10,485,760` | 10.00 MiB | OEM Device Tree Blob Overlay |
| **`/dev/block/sda23`** | `boot` | Active Production OS | **`1,237,144`** | **`1,368,215`** | **`131,072`** | **`67,108,864`** | **64.00 MiB** | **Active LineageOS 23 + Magisk (STRICT READ-ONLY)** |
| **`/dev/block/sda24`** | `recovery` | Staging Slot | **`1,368,216`** | **`1,529,727`** | **`161,512`** | **`82,694,144`** | **78.86 MiB** | **Designated R8Q UEFI Staging Target Slot** |
| **`/dev/block/sda25`** | `keyrefuge`| Knox HW Keystore | **`1,529,728`** | **`1,562,495`** | **`32,768`** | **`16,777,216`** | **16.00 MiB** | **CRITICAL ZERO-GAP HAZARD — ZERO ACCESS** |
| **`/dev/block/sda26`** | `keydata` | Knox Master Data | `1,562,496` | `1,595,263` | `32,768` | `16,777,216` | 16.00 MiB | Hardware Keystore Metadata |
| **`/dev/block/sda27`** | `vbmeta_samsung`| AVB Metadata | `1,595,264` | `1,595,391` | `128` | `65,536` | 0.06 MiB | Samsung Verified Boot Signature Metadata |

---

## 2. Mathematical Proof of Zero-Gap Contiguity

The partition sequence from `sda21` through `sda26` forms an uninterrupted, contiguous sequence of 512-byte sectors:

$$\text{End}(sda21) = 1,085,592 + 131,072 = 1,216,664 = \text{Start}(sda22) \quad (\Delta = 0)$$
$$\text{End}(sda22) = 1,216,664 + 20,480 = 1,237,144 = \text{Start}(sda23) \quad (\Delta = 0)$$
$$\text{End}(sda23) = 1,237,144 + 131,072 = 1,368,216 = \text{Start}(sda24) \quad (\Delta = 0)$$
$$\text{End}(sda24) = 1,368,216 + 161,512 = 1,529,728 = \text{Start}(sda25) \quad (\Delta = 0)$$
$$\text{End}(sda25) = 1,529,728 + 32,768 = 1,562,496 = \text{Start}(sda26) \quad (\Delta = 0)$$

There is exactly **zero sector gap and zero sector overlap** across the entire boundary chain.

---

## 3. The `keyrefuge` (`sda25`) Zero-Gap Boundary Hazard

### 3.1 Architecture of the Knox Keystore Boundary
Partition `sda25` (`keyrefuge`) houses the Samsung Knox hardware-backed keystore material, device-unique cryptographic roots, and biometric encryption master keys. 

As proven mathematically above:
- Partition `sda24` ends at physical sector `1,529,727` (inclusive).
- Partition `sda25` begins immediately at physical sector `1,529,728`.

### 3.2 Linux Block Layer Sub-Device Protection
Under the Linux SCSI/block subsystem (`drivers/scsi/sd.c`):
- `/dev/block/sda24` is registered with its own independent `hd_struct` device descriptor.
- The block layer enforces an immutable capacity ceiling of `161,512` sectors (`82,694,144` bytes).
- Any read or write operation addressing offset $\ge 82,694,144$ bytes on `/dev/block/sda24` is halted by kernel boundary checks (`EOF`).
- **Conclusion:** It is architecturally impossible for a write targeted at `/dev/block/sda24` to overrun into `sda25`.

### 3.3 Catastrophic Risk of Whole-Disk Access (`/dev/block/sda`)
In contrast to partition device nodes, `/dev/block/sda` represents the entire physical 115+ GB LUN:
```bash
# CATASTROPHIC DANGER — STRICTLY FORBIDDEN:
dd if=... of=/dev/block/sda seek=1368216 ...
```
Because `/dev/block/sda` has no partition boundary check at sector `1,529,728`, any arithmetic error exceeding `161,512` sectors immediately overwrites the first sector of `sda25` (`keyrefuge`), permanently destroying hardware crypto material and permanently bricking the phone's secure hardware.

> [!IMPORTANT]
> **MANDATORY POLICY:**  
> All backup, query, or eventual staging commands must exclusively reference partition-level block devices (`/dev/block/sda24` or `/dev/block/by-name/recovery`). Any reference to `/dev/block/sda` with `skip=` or `seek=` is strictly prohibited.

---

## 4. Audited Bit-Exact Backup Commands

Prior to any physical staging in Phase 3.6B, bit-exact sector backups of partitions `sda23` and `sda24` must be dumped to host storage:

### 4.1 Partition `sda24` (`recovery`):
- Total Capacity: `82,694,144` bytes.
- 512-byte Sector Count: `161,512` sectors.
- 4096-byte Page Count: `20,189` blocks (evenly divisible, zero remainder).
- **Audited Command (Sector Level):**
  ```bash
  dd if=/dev/block/sda24 of=/sdcard/sda24_recovery_backup.img bs=512 count=161512
  ```
- **Audited Command (4096-byte Page Aligned — Recommended):**
  ```bash
  dd if=/dev/block/sda24 of=/sdcard/sda24_recovery_backup.img bs=4096 count=20189
  ```

### 4.2 Partition `sda23` (`boot`):
- Total Capacity: `67,108,864` bytes.
- 512-byte Sector Count: `131,072` sectors.
- 4096-byte Page Count: `16,384` blocks (evenly divisible, zero remainder).
- **Audited Command (Sector Level):**
  ```bash
  dd if=/dev/block/sda23 of=/sdcard/sda23_boot_backup.img bs=512 count=131072
  ```
- **Audited Command (4096-byte Page Aligned — Recommended):**
  ```bash
  dd if=/dev/block/sda23 of=/sdcard/sda23_boot_backup.img bs=4096 count=16384
  ```

*Execution Status:* In accordance with Phase 3.6A.1 safety protocols, **neither backup command has been executed on the physical device**.

---

## 5. Staging Footprint vs. Partition Capacity

The compound boot image `r8q-uefi-boot-complete.img` has a total size of **`24,461,312` bytes (23.33 MiB)**.

Comparing against the target `sda24` capacity:
$$\text{Partition Capacity} = 82,694,144 \text{ bytes (78.86 MiB)}$$
$$\text{Staging Footprint} = 24,461,312 \text{ bytes (23.33 MiB)}$$
$$\text{Safety Headroom Margin} = 82,694,144 - 24,461,312 = \mathbf{58,232,832\ \text{bytes (55.53 MiB)}}$$

The compound image occupies only **29.58%** of the available slot capacity, leaving 55.53 MiB of untouched trailing buffer space before the partition end boundary.

---

## 6. Documented Technical Unknowns (Physical Hardware Only)

1. **ABL Staging Base Offset:** Whether Samsung ABL places the recovery container in DRAM at Model A (`0xA0560040`) or Model B (`0xA0561040`) is unknown prior to physical boot trace.  
   *Mitigation:* Custom `PrePi.c` implements dual-candidate probe logic followed by dynamic 176 MiB scanning.
2. **Physical Hardware Installation Gate:** Flashing the image into `sda24` remains unexecuted. All procedures are marked **PENDING HARDWARE VALIDATION (PHASE 3.6B GATE)**.

*Authored by Project R8Q Engineering.*
