# Project R8Q UEFI: Recovery Architecture & Firmware Safety Plan

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Safety Principles & Partition Protection Model

In accordance with Sections 12 and 13 of the Master Engineering Specification, firmware safety and partition preservation are paramount. The device must be 100% safeguarded against accidental soft-bricks, hard-bricks, NVRAM corruption, or security fuse blowouts.

### 1.1 Strict Read-Only & Protected Partition Whitelist

The following partitions contain cryptographic calibration data, baseband NVRAM, or primary bootloader code. R8Q UEFI drivers and diagnostic tools are strictly forbidden from writing, erasing, or repartitioning any of these blocks:

| Partition Name | Block Device | Size | Critical Function | Protection Rule |
|---|---|---|---|---|
| `xbl` | `sdb1` | 4.00 MiB | Primary Qualcomm Boot Loader Stage 2 | **IMMUTABLE / READ-ONLY** |
| `xbl_config`| `sdb2` | 3.96 MiB | XBL Platform Configuration & DDR Timings | **IMMUTABLE / READ-ONLY** |
| `tz` | `sdd5` | 4.00 MiB | Qualcomm TrustZone / QSEE Monitor | **IMMUTABLE / READ-ONLY** |
| `hyp` | `sdd35` | 1.00 MiB | Qualcomm Hypervisor | **IMMUTABLE / READ-ONLY** |
| `abl` | `sdd8` | 4.00 MiB | Samsung Android Boot Loader & Odin Engine | **IMMUTABLE / READ-ONLY** |
| `efs` | `sda9` | 20.00 MiB | Samsung Radio & IMEI Calibration Data | **IMMUTABLE / READ-ONLY** |
| `sec_efs` | `sda12` | 20.00 MiB | Samsung Cryptographic EFS Mirror | **IMMUTABLE / READ-ONLY** |
| `persist` | `sda8` | 32.00 MiB | Sensor Calibration & Wi-Fi MAC Addresses | **IMMUTABLE / READ-ONLY** |
| `modemst1` | `sda1` | 2.00 MiB | Cellular Non-Volatile Memory Primary | **IMMUTABLE / READ-ONLY** |
| `modemst2` | `sda2` | 2.00 MiB | Cellular Non-Volatile Memory Secondary | **IMMUTABLE / READ-ONLY** |
| `fsg` | `sdd3` | 2.00 MiB | Golden Cellular File System Copy | **IMMUTABLE / READ-ONLY** |
| `recovery` | `sda24` | 78.86 MiB | Samsung / LineageOS Emergency Recovery | **PROTECTED / PRESERVED** |

---

## 2. Samsung Download Mode (Odin / Loke) Invariance

A core strength of the Samsung boot architecture is that **Download Mode is hosted in the immutable ABL and XBL firmware stages**.
- Because Project R8Q UEFI executes as a payload loaded *after* ABL, it never modifies ABL or XBL.
- Under any circumstance, if R8Q UEFI encounters an unhandled exception or crash:
  1. Holding **Volume Down + USB insertion to PC** immediately invokes Samsung Download Mode from ABL.
  2. The device can be restored to stock or custom LineageOS firmware using Odin or Heimdall in minutes.
  3. Holding **Volume Up + Power** jumps directly into standard Android Recovery (`sda24`).

---

## 3. Safe Development & Verification Methodology

During all development milestones:
1. **No Bootloader Partition Flashing:** Neither `abl`, `xbl`, nor `tz` will ever be overwritten.
2. **Dual-Boot / Chained Boot Testing:**
   - Test builds are packaged into an Android `boot.img` container and booted dynamically via fastboot (`fastboot boot r8q-uefi.img`) or installed strictly to an auxiliary recovery/boot slot without touching underlying storage geometry.
3. **Hardware Key Safe-Mode:**
   - If Volume Up is held down during R8Q UEFI initialization, the firmware immediately aborts all automated boot scripts and drops directly into the safe UEFI Shell with display output.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
