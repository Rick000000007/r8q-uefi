# Project R8Q UEFI: Milestone 4 UFS Controller & LUN Architecture Report
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona, Rev 2.1)  
**Document Revision:** 1.0.0-M4  
**Status:** Hardware Verified on Device (Device-Observed `D` / Directly Present `V`)  

---

## 1. UFS 3.1 Host Controller Hardware Verification

Direct empirical verification from live sysfs (`/sys/bus/platform/devices/1d84000.ufshc`) and target device tree (`devicetree/r8q-live.dts`):
- **Controller Node:** `/soc/ufshc@1d84000` (`ufshc_mem`)
- **DTS Alias:** `ufshc1 = "/soc/ufshc@1d84000"`
- **Physical Register Base:** `0x01D84000`
- **Register Ranges:**
  - `ufs_mem`: `0x01D84000` (Size: `0x3000` / 12 KiB) - Standard UFSHCI registers.
  - `ufs_ice`: `0x01D90000` (Size: `0x8000` / 32 KiB) - Qualcomm Inline Crypto Engine (ICE).
- **Compatible String:** `"qcom,ufshc"`
- **PHY Node:** `/soc/ufsphy_mem@1d87000` (Qualcomm 7nm UFS PHY).
- **Interrupt:** `<0x00 0x109 0x04>` (GIC SPI 265).
- **Installed Flash Chip:** **`Samsung KLUDG4UHDB-B2D1`**
  - **Type:** Universal Flash Storage 3.1 (UFS 3.1)
  - **Nominal Capacity:** 128 GB
  - **Gear:** High-Speed Gear 4 (2 lanes per direction, up to 23.2 Gbps theoretical bandwidth).

---

## 2. Comprehensive UFS Logical Unit (LUN) Map

The Samsung UFS 3.1 chip is partitioned at the UFS controller firmware level into four physical standard Logical Units (LUNs) plus special Well-Known LUNs (WLUNs):

| SCSI Target | Linux Block Node | UFS LUN Index | Capacity (Bytes) | Capacity (Human) | Partition Table & Target Subsystems | Read-Only Policy |
| :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| `0:0:0:0` | `/dev/block/sda` | **LUN 0** | `127,871,746,048` | **119.09 GiB** | **GPT (36 partitions):** `boot` (sda23), `recovery` (sda24), `super` (sda29), `userdata` (sda36), `modem` (sda20), `efs` (sda9), `persist` (sda8), etc. | **PERMANENT READ-ONLY** |
| `0:0:0:1` | `/dev/block/sdb` | **LUN 1** | `8,388,608` | **8.00 MiB** | **Boot LUN A (2 partitions):** `xbl` (sdb1), `xbl_config` (sdb2). Primary bootloader stage. | **PERMANENT READ-ONLY** |
| `0:0:0:2` | `/dev/block/sdc` | **LUN 2** | `8,388,608` | **8.00 MiB** | **Boot LUN B (raw):** Secondary backup bootloader LUN. | **PERMANENT READ-ONLY** |
| `0:0:0:3` | `/dev/block/sdd` | **LUN 3** | `62,914,560` | **60.00 MiB** | **GPT (37 partitions):** `abl` (sdd8), `tz` (sdd5), `aop` (sdd7), `uefivarstore` (sdd31), `vbmeta` (sdd25), `devcfg` (sdd23), etc. | **PERMANENT READ-ONLY** |
| `0:0:0:49456` | — | **WLUN 0xC1** | Hardware Managed | — | **RPMB (Replay Protected Memory Block):** Hardware replay-protected key storage managed by TrustZone. | **BLOCKED** |
| `0:0:0:49476` | — | **WLUN 0xC4** | Hardware Managed | — | **Boot WLUN:** Directs UFS boot loading to active boot LUN. | **BLOCKED** |
| `0:0:0:49488` | — | **WLUN 0xD0** | Hardware Managed | — | **UFS Device WLUN:** Device-level descriptors and power management. | **BLOCKED** |

---

## 3. Storage Geometry & Partition Overview

1. **LUN 0 (`sda`, 119.09 GiB):**
   - Formatted with standard GUID Partition Table (GPT).
   - Logical block size: 4096 bytes.
   - Contains all operational Android and native Linux OS partitions, including the 64 MiB `boot` partition (`sda23`) and 78.86 MiB `recovery` partition (`sda24`).
2. **LUN 3 (`sdd`, 60.00 MiB):**
   - Formatted with standard GUID Partition Table (GPT).
   - Contains all secondary low-level firmware partitions:
     - `sdd8` (`abl`): Samsung Application Bootloader (EDK II based).
     - `sdd5` (`tz`): Qualcomm TrustZone / QSEE.
     - `sdd7` (`aop`): Always-On Processor firmware.
     - `sdd31` (`uefivarstore`): Samsung internal proprietary NVRAM variable store.
     - `sdd25` (`vbmeta`): Android Verified Boot metadata.

> [!CAUTION]
> Writing to or corrupting `sdd31` (`uefivarstore`), `sdd8` (`abl`), or `sdd5` (`tz`) would irreparably brick the target device. In Project R8Q UEFI, all four internal LUNs are locked behind a centralized software write blocker.
