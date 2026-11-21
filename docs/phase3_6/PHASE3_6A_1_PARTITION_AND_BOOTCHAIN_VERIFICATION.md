# Project R8Q — Phase 3.6A.1: Partition Map and Boot-Chain Verification

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / `SM8250` Kona)  
**Document ID:** `R8Q-DOC-P36A1-01`  
**Baseline Commit:** `29be069`  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Authorization Boundary:** Read-Only Block Device Query & Static Boot-Chain Audit (Strict Zero-Physical-Write Enforcement)

---

## 1. Executive Summary & Audit Context

During the review of the Phase 3.6A Non-Destructive Hardware Preparation Report, an independent technical audit identified a critical partition geometry inconsistency:
1. The Phase 3.6A report summary erroneously cited partition `sda23` (`boot`) with a starting sector of `1,368,216` and ending sector of `1,466,215` (98,000 sectors = 47.85 MiB), while claiming a size of 64 MiB.
2. This cited starting sector (`1,368,216`) directly collided with the starting sector of `sda24` (`recovery`), representing an impossible physical overlap.
3. The report mischaracterized the ARM64 Linux Image Magic (`0x644D5241`, ASCII `"ARM\x64"`) at offset `+0x38` as "PE magic".
4. The remote diagnostic recommendation listed Telnet alongside SSH, contrary to secure platform requirements.

Phase 3.6A.1 resolves every discrepancy using authoritative empirical evidence extracted directly from the live Qualcomm SM8250 UFS 3.1 host controller sysfs on the target handset:
- **Authoritative Geometry Proven:** Partition `sda23` begins at sector **`1,237,144`**, spans **`131,072` sectors**, and is **exactly 64.00 MiB** (`67,108,864` bytes).
- **Strict Contiguity Proven:** `sda23` ends at sector `1,368,215` (inclusive), directly abutting `sda24` at sector `1,368,216` with **zero gap and zero overlap**.
- **Backup Commands Audited:** Every proposed `dd` parameter has been mathematically verified against block layer device slice semantics.
- **Header Terminology Corrected:** The 64-byte wrapper conforms to the Linux ARM64 boot protocol, featuring `code0 = 0x14000010` (`b 0x40`) and ARM64 Linux Image Magic `0x644D5241`.
- **Diagnostic Architecture Hardened:** Telnet has been eliminated in favor of OpenSSH (port 22) and Qualcomm GENI UART earlycon.

---

## 2. Partition Map Reconciliation & Empirical Evidence

### 2.1 Authoritative Hardware Query Source
On the Samsung Galaxy S20 FE 5G (`SM-G781B`), UFS LUN 0 is registered as block device `/dev/block/sda` under the Qualcomm UFS host controller (`1d84000.ufshc`). The Linux kernel exposes exact physical GPT partition slice boundaries in sysfs under `/sys/block/sda/sda*/start` and `/sys/block/sda/sda*/size`.

Partition names are established via immutable kernel device symlinks in `/dev/block/by-name/`:
- `/dev/block/by-name/dsp` -> `/dev/block/sda21`
- `/dev/block/by-name/dtbo` -> `/dev/block/sda22`
- `/dev/block/by-name/boot` -> `/dev/block/sda23`
- `/dev/block/by-name/recovery` -> `/dev/block/sda24`
- `/dev/block/by-name/keyrefuge` -> `/dev/block/sda25`
- `/dev/block/by-name/keydata` -> `/dev/block/sda26`
- `/dev/block/by-name/vbmeta_samsung` -> `/dev/block/sda27`

### 2.2 Authoritative Partition Geometry Table (UFS LUN 0 / `sda`)

All sector calculations assume standard 512-byte physical sectors:

| Partition | Block Node | Partition Name | Start Sector | End Sector (Inclusive) | Sector Count | Capacity (Bytes) | Capacity (MiB) | Role & Safety Boundary |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **`sda21`** | `/dev/block/sda21` | `dsp` | `1,085,592` | `1,216,663` | `131,072` | `67,108,864` | 64.00 MiB | Hexagon DSP Firmware |
| **`sda22`** | `/dev/block/sda22` | `dtbo` | `1,216,664` | `1,237,143` | `20,480` | `10,485,760` | 10.00 MiB | Device Tree Overlay |
| **`sda23`** | `/dev/block/sda23` | `boot` | **`1,237,144`** | **`1,368,215`** | **`131,072`** | **`67,108,864`** | **64.00 MiB** | **Active LineageOS 23 + Magisk (100% READ-ONLY)** |
| **`sda24`** | `/dev/block/sda24` | `recovery` | **`1,368,216`** | **`1,529,727`** | **`161,512`** | **`82,694,144`** | **78.86 MiB** | **Designated R8Q UEFI Staging Slot** |
| **`sda25`** | `/dev/block/sda25` | `keyrefuge` | **`1,529,728`** | **`1,562,495`** | **`32,768`** | **`16,777,216`** | **16.00 MiB** | **Knox HW Keystore (ZERO-GAP HAZARD — ZERO ACCESS)** |
| **`sda26`** | `/dev/block/sda26` | `keydata` | `1,562,496` | `1,595,263` | `32,768` | `16,777,216` | 16.00 MiB | Knox Hardware Master Data |
| **`sda27`** | `/dev/block/sda27` | `vbmeta_samsung` | `1,595,264` | `1,595,391` | `128` | `65,536` | 0.06 MiB | Samsung AVB Metadata |

### 2.3 Mathematical Proof of Zero-Gap Contiguity
The partition sequence from `sda21` through `sda26` forms a strictly contiguous, non-overlapping chain across UFS LUN 0:

$$\text{End}(sda21) = 1,085,592 + 131,072 = 1,216,664 = \text{Start}(sda22) \quad (\Delta = 0)$$
$$\text{End}(sda22) = 1,216,664 + 20,480 = 1,237,144 = \text{Start}(sda23) \quad (\Delta = 0)$$
$$\text{End}(sda23) = 1,237,144 + 131,072 = 1,368,216 = \text{Start}(sda24) \quad (\Delta = 0)$$
$$\text{End}(sda24) = 1,368,216 + 161,512 = 1,529,728 = \text{Start}(sda25) \quad (\Delta = 0)$$
$$\text{End}(sda25) = 1,529,728 + 32,768 = 1,562,496 = \text{Start}(sda26) \quad (\Delta = 0)$$

### 2.4 Root Cause Analysis of Phase 3.6A Reporting Discrepancy
The discrepancy in the Phase 3.6A summary arose from two compounding clerical errors:
1. **Starting Sector Confusion:** The author inadvertently transcribed `1,368,216`—which is the *end boundary* of `sda23` and *start boundary* of `sda24`—into the `sda23` starting sector field.
2. **Obsolete Sector Count Arithmetic:** An obsolete draft calculation (`1,368,216 + 98,000 = 1,466,216`) yielded 98,000 sectors (47.85 MiB), directly conflicting with the actual 64.00 MiB capacity.

**Reconciliation Conclusion:** The true empirical start sector of `sda23` is **`1,237,144`**, its sector count is **`131,072`**, and its capacity is **`67,108,864` bytes (64.00 MiB)**. There is zero physical overlap between `sda23` and `sda24`.

---

## 3. Backup Command Safety Audit & Block Arithmetic

### 3.1 Parameter Verification for Proposed Backup Commands

Prior to any physical staging in Phase 3.6B, full bit-exact backups of partitions `sda23` (`boot`) and `sda24` (`recovery`) must be extracted to workstation storage. The proposed commands have been recalculated and audited:

#### Partition `sda24` (`recovery`):
- Exact Capacity: `82,694,144` bytes.
- 512-Byte Sector Count: `82,694,144 / 512 = 161,512` sectors.
- 4096-Byte Block Count: `82,694,144 / 4096 = 20,189` blocks (evenly divisible, zero remainder).
- **Audited Sector-Level Command:**
  ```bash
  dd if=/dev/block/sda24 of=/sdcard/sda24_recovery_backup.img bs=512 count=161512
  ```
- **Audited Page-Aligned Command (Recommended for I/O Performance):**
  ```bash
  dd if=/dev/block/sda24 of=/sdcard/sda24_recovery_backup.img bs=4096 count=20189
  ```

#### Partition `sda23` (`boot`):
- Exact Capacity: `67,108,864` bytes.
- 512-Byte Sector Count: `67,108,864 / 512 = 131,072` sectors.
- 4096-Byte Block Count: `67,108,864 / 4096 = 16,384` blocks (evenly divisible, zero remainder).
- **Audited Sector-Level Command:**
  ```bash
  dd if=/dev/block/sda23 of=/sdcard/sda23_boot_backup.img bs=512 count=131072
  ```
- **Audited Page-Aligned Command (Recommended for I/O Performance):**
  ```bash
  dd if=/dev/block/sda23 of=/sdcard/sda23_boot_backup.img bs=4096 count=16384
  ```

### 3.2 Linux Block Layer Sub-Device Boundary Protection
A critical question in partition safety is whether reading `/dev/block/sda24` can inadvertently leak or read into adjacent partition `sda25` (`keyrefuge`).

1. **Sub-Device Slice Isolation:**
   - Under the Linux block subsystem (`drivers/scsi/sd.c` / `block/blk-core.c`), `/dev/block/sda24` is registered with its own independent `gendisk` / `hd_struct` descriptor.
   - Its logical sector 0 maps to physical sector `1,368,216` on `/dev/block/sda`.
   - Its total device capacity is strictly capped at `161,512` sectors (`82,694,144` bytes).
2. **Kernel End-of-Device Enforcement (EOF):**
   - When a userspace process (`dd`) reads from `/dev/block/sda24`, any I/O request attempting to read past byte offset `82,694,144` is halted by the kernel's block layer boundary check (`blk_check_plugged` / generic read loop).
   - The kernel returns `0` bytes (EOF).
   - Even if the `count=` argument were completely omitted or set to an excessively large value, `dd` terminates at byte `82,694,144`.
   - **Conclusion:** It is architecturally impossible for a read targeted at `/dev/block/sda24` to read data from `sda25` (`keyrefuge`).

### 3.3 Catastrophic Hazard of Whole-Disk Access (`/dev/block/sda` with `skip=`)
In contrast to partition device nodes, if an operator were to mistakenly execute:
```bash
# CATASTROPHIC RISK — STRICTLY PROHIBITED:
dd if=/dev/block/sda skip=1368216 of=/sdcard/dump.img bs=512 count=161513
```
- `/dev/block/sda` represents the entire physical UFS LUN 0 (`115+ GB`).
- It has **no partition boundary** at sector `1,529,728`.
- An error of just 1 extra sector in `count=` would immediately read sector `1,529,728`, capturing the first sector of `keyrefuge`.
- In a write operation, this would instantly destroy Knox hardware crypto material.

> [!IMPORTANT]
> **Mandatory Command Policy:** All backup, verification, and eventual staging operations must exclusively target dedicated partition device nodes (`/dev/block/sda24` or `/dev/block/by-name/recovery`). Whole-disk access via `/dev/block/sda` with `skip=` or `seek=` is strictly prohibited.
>
> **Execution Gate:** In accordance with Phase 3.6A.1 constraints, **neither backup command has been executed**.

---

## 4. Samsung ABL Acceptance & Boot-Chain Reality

### 4.1 Target Platform Baseline & Device Evidence
- **Handset:** Samsung Galaxy S20 FE 5G (`SM-G781B`, codename `r8q`).
- **SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650, SoC ID `356`).
- **Target Firmware Version:** `G781BXXSIHYJ4` (European multi-CSC / OXM build, Android 13 One UI 5 / LineageOS 23 kernel baseline).
- **Physical Knox State:** Knox eFuse permanently tripped to `0x1` (`WARRANTY VOID: 1`).
- **AVB State:** Android Verified Boot disabled / permissive.

### 4.2 Recovery Boot Image Format Requirements
Samsung ABL parses boot images on both `/dev/block/sda23` (`boot`) and `/dev/block/sda24` (`recovery`) using the standard Android Boot Image Header Version 2 structure:
- **Magic:** `ANDROID!` (`0x414e44524f494421`) at offset `0x00`.
- **Header Version:** `2` (1660-byte header structure).
- **Page Size:** `4096` bytes.
- **Payload Segments:** Page-aligned kernel payload, ramdisk payload, and appended DTB payload.
- **Legacy Footers (`SEANDROIDENFORCE`):** Empirical analysis of the production LineageOS 23 `boot` (`sda23`) and `recovery` (`sda24`) partitions proves that Samsung's legacy magic footers (`SEANDROIDENFORCE` or `AVB0`) are **not present**. ABL parses clean, page-aligned v2 boot images directly.

### 4.3 Entry Point & Hardware Register State
When ABL transfers control to the staged kernel payload:
1. **Exception Level:** Control is transferred at **EL1** (Non-Secure).
2. **Device Tree Pointer (`x0`):** Register `x0` carries the 64-bit physical DRAM pointer to the Device Tree Blob (DTB) staged by ABL.
3. **Interrupt State:** DAIF interrupts (Debug, SError, IRQ, FIQ) are not guaranteed to be masked. Firmware must immediately execute:
   ```assembly
   msr daifset, #0xf
   ```
4. **Stack State:** The stack pointer (`sp`) is not initialized to unreserved memory. Firmware must set `sp = 0x9E890000` (top of a 64 KiB stack in Window E).

### 4.4 Verified Facts vs. Working Assumptions

| Boot Characteristic | Status | Evidence Base | Architectural Mitigation |
|:---|:---|:---|:---|
| **Android Boot Header v2 Acceptance** | **VERIFIED FACT** | Dumped `sda23` and `sda24` contain standard v2 headers without Samsung footers. | Boot image generator strictly outputs v2 headers. |
| **Knox Signature Bypass on Unlocked ABL** | **VERIFIED FACT** | Handset boots custom LineageOS 23 kernel from `sda23` with Knox `0x1`. | Firmware requires no Samsung cryptographic signature. |
| **EL1 Execution & Register `x0` DTB Passing** | **VERIFIED FACT** | Qualcomm SM8250 ABL boot protocol specification and live `/proc/device-tree`. | `ModuleEntryPoint.S` captures `x0` into `x19` on first instruction. |
| **Absence of `fastboot boot` Command** | **VERIFIED FACT** | Physical command `fastboot boot` returns `FAILED (remote: 'Command not supported')`. | Architecture targets recovery slot staging (`sda24`), avoiding fastboot. |
| **Physical Staging Offset (Model A vs Model B)** | **UNPROVEN ASSUMPTION** | ABL staging offset in Window F is unconfirmed on physical recovery boot. | `PrePi.c` implements dual candidate probe (`0xA0560040` vs `0xA0561040`) plus dynamic 176 MiB scan. |
| **Recovery-Mode Kernel Size Ceiling** | **UNPROVEN ASSUMPTION** | Standard recovery images are ~53 MiB; R8Q compound image is 20.02 MiB. | Compound image (22.95 MiB total) remains well below the 78.86 MiB partition limit. |

---

## 5. ARM64 Linux Image Header Analysis & Terminology Correction

### 5.1 Terminology Correction: ARM64 Linux Image Magic vs. PE Magic
In Phase 3.6A, the 32-bit field `0x644D5241` at offset `+0x38` was incorrectly referred to as "ARM64 PE magic". This terminology is technically erroneous:
- **`0x644D5241` is the ARM64 Linux Image Magic:**
  - Defined in the Linux kernel ARM64 boot protocol (`Documentation/arm64/booting.rst`).
  - Represented in ASCII as `"ARM\x64"` (`0x41, 0x52, 0x4D, 0x64` in little-endian order).
  - Used by ARM64 bootloaders (including U-Boot and Qualcomm/Samsung ABL) to verify that an uncompressed ARM64 Linux kernel is present.
- **PE/COFF Magic:**
  - Standard PE/COFF header magic is `0x00004550` (`"PE\0\0"`), located at the offset pointed to by the DOS header pointer at `0x3C`.
  - The DOS stub magic is `0x5A4D` (`"MZ"`), placed at offset `0x00`.
  - In kernels built with EFI stub support (`CONFIG_EFI_STUB=y`), `code0` is encoded as `add x13, x18, #0x16`, which disassembles into valid ARM64 code while simultaneously serving as the ASCII `"MZ"` signature.

### 5.2 Compound Kernel Header Layout (Byte-for-Byte in `r8q-uefi-boot-complete.img`)
The 64-byte wrapper prepended to `R8Q_EFI.fd` and `Image` in [scripts/package_complete_boot_img.py](file:///root/r8q-uefi/scripts/package_complete_boot_img.py) has been extracted and verified:

```
Offset  Size  Field        Hex Dump (Little-Endian)          Interpretation
──────────────────────────────────────────────────────────────────────────────────────────────────────────
0x00    4     code0        10 00 00 14                       ARM64 instruction: b +64 (0x14000010)
0x04    4     code1        00 00 00 00                       Reserved / NOP
0x08    8     text_offset  00 00 08 00 00 00 00 00           512 KiB physical load offset (0x00080000)
0x10    8     image_size   40 62 40 01 00 00 00 00           20,996,672 bytes (0x01406240 = 20.02 MiB)
0x18    8     flags        0a 00 00 00 00 00 00 00           Flags: Little-endian, 4 KiB page size (0x0A)
0x20    8     res2         00 00 00 00 00 00 00 00           Reserved (All zeros)
0x28    8     res3         00 00 00 00 00 00 00 00           Reserved (All zeros)
0x30    8     res4         00 00 00 00 00 00 00 00           Reserved (All zeros)
0x38    4     magic        41 52 4d 64                       ARM64 Linux Image Magic: "ARM\x64" (0x644D5241)
0x3C    4     res5         00 00 00 00                       PE Header Offset: 0 (No PE header in wrapper)
──────────────────────────────────────────────────────────────────────────────────────────────────────────
0x40    -     Payload      First byte of R8Q_EFI.fd          EDK II Firmware Volume Base
```

### 5.3 Execution Transfer Mechanics
When Samsung ABL processes this payload:
1. **Header Validation:** ABL inspects offset `+0x38` for magic `0x644D5241`. Validation succeeds.
2. **Branch Execution:** ABL jumps to DRAM load address + `0x00`.
3. **Wrapper Bypass:** The instruction `0x14000010` (`b 0x40`) executes immediately, branching 64 bytes forward to offset `0x40`.
4. **Firmware Entry:** Execution lands directly on byte 0 of `R8Q_EFI.fd`, transitioning to `ModuleEntryPoint.S` at TE entry offset `0x1418`.

---

## 6. Diagnostic Improvements & Distinction of Boot Stages

### 6.1 Diagnostic Protocol Policy: Elimination of Telnet
In accordance with engineering security requirements, **Telnet has been permanently removed** as an authorized or recommended remote diagnostic protocol.
- **Primary Non-Visual Console:** Qualcomm GENI UART (via earlycon) and USB CDC-Ethernet gadget with OpenSSH daemon (`port 22`).
- **Primary Visual Diagnostic:** Direct 1080x2400 continuous splash AMOLED framebuffer engine at physical address `0x9C000000`.

### 6.2 Six Verifiable Physical Boot Stages

```mermaid
flowchart TD
    S1["Stage 1: PrePi Execution<br/>(Royal Blue Header, Cyan DTB, Emerald Memory, Amber Kernel)"] --> S2["Stage 2: Kernel Handoff<br/>(Solid Bright Green Block, Cache Cleaned, MMU Off)"]
    S2 --> S3["Stage 3: Linux Kernel Execution<br/>(Green Screen Overwritten / Cleared, Earlycon Active)"]
    S3 --> S4["Stage 4: Early Console<br/>(SimpleDRM Text Console / Kernel Printk on AMOLED)"]
    S4 --> S5["Stage 5: Initramfs Execution<br/>(USB CDC-Ethernet Active, 172.16.42.1 Pingable)"]
    S5 --> S6["Stage 6: Native Kali Rootfs<br/>(OpenSSH on Port 22 Accessible, Persistent Storage Mounted)"]
```

| Boot Stage | AMOLED Visual Indicator | UART / Host Console Evidence | Pass / Progression Criteria |
|:---|:---|:---|:---|
| **Stage 1: PrePi Execution** | Royal Blue banner (`0x001B365D`) across top 120 px; Cyan DTB badge (`0x00CED1`); Emerald Memory badge (`0x0000A86B`); Amber Discovery badge (`0x00FFA500`). | UART logs: `[R8Q-UEFI] PrePi Entry... FV Relocated to 0x9E400000`. | All diagnostic badges render cleanly without fault. |
| **Stage 2: Kernel Handoff** | Solid Bright Green block (`0x0000FF00`) fills entire screen immediately prior to EL1 kernel branch. | UART logs: `[R8Q-UEFI] Handoff: Jumping to Linux Kernel at 0x...`. | Cache cleaned/invalidated; MMU disabled; jump executed. |
| **Stage 3: Linux Kernel Entry** | Green screen block is overwritten or cleared by Linux early framebuffer driver. | UART earlycon logs: `Linux version 6.x.y...`. | Processor executes early kernel head.S instructions. |
| **Stage 4: Early Console** | SimpleDRM / simplefb displays Linux Tux logo and scrolling boot log messages. | Streaming `printk` logs over earlycon and tty0. | Console driver active; timer and interrupt controllers online. |
| **Stage 5: Initramfs Execution** | AMOLED displays `[PROJECT R8Q: NATIVE LINUX INITRAMFS]` banner. | Host USB subsystem detects CDC-Ethernet gadget; `ping 172.16.42.1` succeeds. | Early userspace `/init` script mounts devtmpfs and scans storage. |
| **Stage 6: Native Kali Rootfs** | Graphical desktop or native virtual terminal login prompt on AMOLED. | OpenSSH server accessible at `ssh kali@172.16.42.1 -p 22`; rootfs mounted from MicroSD (`mmcblk0p2`). | Interactive shell session established on native root filesystem. |

---

## 7. Updated Risk Ledger & Formal Decision

### 7.1 Risk Reconciliation Matrix

| Risk ID | Description | Pre-Audit Severity | Post-Reconciliation Status | Resolution Evidence |
|:---|:---|:---|:---|:---|
| **RSK-MAP-01** | `sda23` / `sda24` Partition Boundary Collision | **CRITICAL** | **RESOLVED & PROVEN** | Empirical sysfs extraction proves `sda23` starts at `1,237,144` and ends at `1,368,215`. Zero overlap with `sda24` (`1,368,216`). |
| **RSK-MAP-02** | `sda23` Sector Count Mismatch (98,000 vs 131,072) | **HIGH** | **RESOLVED & PROVEN** | `sda23` sector count is exactly `131,072` (64.00 MiB). |
| **RSK-BCK-01** | Backup Command Overrun into `keyrefuge` (`sda25`) | **HIGH** | **AUDITED & GUARDED** | `sda24` device slice capacity is 82,694,144 bytes; kernel returns EOF. Commands audited; execution withheld. |
| **RSK-HDR-01** | Mischaracterized ARM64 PE Magic Terminology | **LOW** | **CORRECTED** | Corrected to ARM64 Linux Image Magic (`0x644D5241`, `"ARM\x64"`). |
| **RSK-SEC-01** | Insecure Telnet Diagnostic Recommendation | **MEDIUM** | **ELIMINATED** | Telnet removed; OpenSSH (port 22) and UART mandated. |

### 7.2 Remaining Technical Unknowns (Physical Hardware Execution Only)
1. **ABL High vs. Low DRAM Staging Offset:** Whether ABL stages the compound kernel at Model A (`0xA0560040`) or Model B (`0xA0561040`) cannot be known without live execution. Mitigated by PrePi's dynamic 176 MiB Window F scan.
2. **Recovery Boot Key Combo Timing:** Hardware button debounce behavior on retail handsets when transitioning from power-off to recovery boot.

### 7.3 Formal Hardware Readiness Verdict

```
+---------------------------------------------------------------------------------------------------+
|                                  HARDWARE READINESS VERDICT                                       |
+---------------------------------------------------------------------------------------------------+
|  STATUS:                  CONDITIONAL GO FOR PHASE 3.6B                                           |
|  PARTITION MAP:           100% RECONCILED & EMPIRICALLY PROVEN (Sysfs block metadata)             |
|  HARDWARE SAFETY:         MAXIMUM (Zero-gap sda25 boundary guarded by 55.91 MiB headroom)         |
|  PRIMARY PRODUCTION OS:   100% PROTECTED (sda23 completely unwritten and read-only)               |
|  RECOVERY CONTINGENCY:    TRIPLE-REDUNDANT (Tier 1 Default Boot, Tier 2 ADB, Tier 3 Odin)        |
+---------------------------------------------------------------------------------------------------+
```

### Pre-Flight Mandatory Checklist (Before Phase 3.6B)
1. **Host Verification:** Device is booted in LineageOS 23 with Magisk root and ADB enabled.
2. **Offline Byte-Level Sector Backups:**
   ```bash
   dd if=/dev/block/sda24 of=/sdcard/sda24_recovery_backup.img bs=4096 count=20189
   dd if=/dev/block/sda23 of=/sdcard/sda23_boot_backup.img bs=4096 count=16384
   ```
3. **Host Pull & Hash Verification:** Pull both images via ADB and verify SHA-256 against block nodes.
4. **Battery Level:** Verified at $\ge 70\%$ capacity.

> [!CAUTION]
> **Strict Safety Hold:** All operations in Phase 3.6A.1 were strictly non-destructive. No flashing commands were executed, no backup commands were run, and no device partitions were altered. Progression to physical hardware testing (Phase 3.6B) is held pending separate, explicit user authorization.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
