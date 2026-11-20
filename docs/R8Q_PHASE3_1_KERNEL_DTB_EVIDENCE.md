# Project R8Q — Phase 3.1: Kernel & Device-Tree Evidence Audit
**Document ID:** `R8Q-DOC-AUD-003`  
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Binary Kernel:** [build/Image](file:///root/r8q-uefi/build/Image) (`48,269,824` bytes, SHA-256: `a02004e6...`)  
**Binary DTB:** [build/r8q.dtb](file:///root/r8q-uefi/build/r8q.dtb) (`821,231` bytes, SHA-256: `75244696...`)  
**Defconfig:** [config/kernel_r8q_defconfig](file:///root/r8q-uefi/config/kernel_r8q_defconfig)  
**Audit Status:** COMPLETE ADVERSARIAL AUDIT (Discrepancies & Dependencies Exposed)  

---

## 1. Executive Summary & Build Provenance

This independent audit evaluated the provenance of the kernel binary [build/Image](file:///root/r8q-uefi/build/Image), the device tree blob [build/r8q.dtb](file:///root/r8q-uefi/build/r8q.dtb), and the validity of the 42-driver support matrix.

### 1.1 Kernel Provenance Finding: Pre-Built Distribution Binary vs. Custom Defconfig
In previous documentation, it was stated that `build/Image` corresponds to `config/kernel_r8q_defconfig`.

> [!IMPORTANT]
> **AUDIT FINDING ON KERNEL PROVENANCE [FACT]:**  
> 1. Binary comparison and SHA-256 hash matching (`a02004e609206bd34ecf496c7a52c92c11400a19733f42d9e2b063b122e7c05a`) proves that [build/Image](file:///root/r8q-uefi/build/Image) is **identical to `/usr/lib/modules/7.2.15+kali-arm64/vmlinuz`** extracted from the upstream Kali package `linux-binary-7.2.15+kali-arm64_7.2.15-1kali1_arm64.deb`.  
> 2. `build/Image` was **NOT compiled from `config/kernel_r8q_defconfig`**.  
> 3. `kernel_r8q_defconfig` serves as an engineering specification for a future custom kernel build, whereas `build/Image` is a generic Debian/Kali distribution ARM64 kernel.

---

## 2. Device Tree Audit: `build/r8q.dtb` vs. Live Hardware Evidence

Decompilation of [build/r8q.dtb](file:///root/r8q-uefi/build/r8q.dtb) using `dtc -I dtb -O dts` and comparison against live hardware at `/sys/firmware/devicetree/base`:

```
+-------------------------------------------------------------------------------------------------+
|                        DEVICE TREE BLOB vs. LIVE HARDWARE COMPARISON                            |
+-------------------------------------------------------------------------------------------------+
|  PROPERTY / NODE              |  BUILD/R8Q.DTB (COMPILED)           |  LIVE HARDWARE (/SYS/FIRMWARE)    |
+-------------------------------+-------------------------------------+-----------------------------------+
|  model                        |  Samsung R8Q EUR PROJECT - R8 REV04 |  Samsung R8Q EUR PROJECT - R8 REV04|
|  compatible                   |  qcom,kona-mtp, qcom,kona, qcom,mtp |  qcom,kona-mtp, qcom,kona, qcom,mtp|
|  qcom,msm-id                  |  <0x164 0x20001> (SM8250 v2.1)      |  <0x164 0x20001> (SM8250 v2.1)     |
|  qcom,board-id                |  <0x08 0x08>                        |  <0x08 0x08>                       |
|  /memory reg                  |  0x80000000 (955MB) + 0xC0000000(7G)|  0x80000000 (955MB) + 0xC0000000(7G|
|  cont_splash_region           |  0x9C000000, 35 MiB (0x02300000)    |  0x9C000000, 35 MiB (0x02300000)   |
|  GICv3 @ 17a00000             |  Present                            |  Present                          |
|  UFS @ 1d84000                |  Present                            |  Present                          |
|  SDHCI @ 8804000              |  Present                            |  Present                          |
|  simple-framebuffer           |  MISSING                            |  MISSING                          |
|  samsung,ss_touch             |  Vendor Node (Non-Upstream)         |  Vendor Node (Non-Upstream)        |
+-------------------------------+-------------------------------------+-----------------------------------+
```

### 2.1 Critical Device Tree Defect: Missing Simple-Framebuffer
- **Audit Finding [FAILED CHECK]:** `build/r8q.dtb` does **NOT** contain a `simple-framebuffer` node in `/chosen`.
- **Engineering Consequence:** When native Linux boots without proprietary vendor display drivers, it relies entirely on `simple-framebuffer` (or EFI GOP table) to locate the display buffer. Since `build/r8q.dtb` has no `simple-framebuffer` node, and since `R8Q_EFI.fd` does not install UEFI runtime GOP tables into the kernel, the native kernel will boot with **completely blank / dark display output**.

### 2.2 Downstream Vendor Bindings vs. Upstream Linux Drivers
`build/r8q.dtb` is a decompiled downstream Android vendor tree. It uses proprietary vendor node names that upstream Linux drivers will **NOT** bind to:
- Touchscreen: declared as `samsung,ss_touch` rather than upstream `focaltech,fts` or `edt,edt-ft5x06`.
- Audio: declared as `samsung,q6audio-adaptation` and vendor Bolero macros rather than upstream SoundWire / LPASS bindings.
- Display: declared as `qcom,mdss_dsi_ctrl0@ae94000` with Samsung command-mode panel properties that upstream `msm_drm` cannot parse without upstream panel driver bindings (`panel-samsung-s6e3ha9`).

---

## 3. Independent Audit of the 42-Driver Matrix

In previous reports, drivers were marked as "Physically Tested" when they were merely loaded in the Android vendor kernel. This audit establishes the true status for all 42 drivers:

### 3.1 Driver Classification Breakdown
- **Pure Generic / Upstream Compatible (No Vendor Blob Needed):**  
  ARM64 Core, PSCI, GICv3, Arch Timer, EXT4, VFAT, Cgroups, VirtIO. (8 drivers).
- **SoC Register Compatible (Standard Qualcomm SM8250 IP):**  
  GCC clocks, DISPCC, GPUCC, NoC Interconnect, CPUFreq HW, RPMh/PDC, SPMI arbiter, UFS 3.1 host, SDHCI host, DWC3 USB, TSENS. (11 drivers).  
  *Limitation:* Tested only in Android 4.19; native Linux 7.2.15 requires correct regulator sequencing.
- **Hardware Dependent on Proprietary Firmware Blobs:**  
  1. *Adreno 650 GPU (`drm/msm`):* Requires `a650_zap.mbn` (TrustZone), `a650_gmu.bin`, and `a650_sqe.fw`.
  2. *QCA6390 Wi-Fi 6 (`ath11k_pci`):* Requires `board-2.bin`, `m3.bin`, `amss.bin`.
  3. *SDX55 5G Modem (`mhi`):* Requires `modem.mbn` and `mba.mbn`.
  4. *LPASS Audio (`snd-soc-sm8250`):* Requires Hexagon DSP firmware `adsp.mbn`.
- **Downstream Vendor Dependent (Non-Standard Bindings):**  
  FocalTech Touchscreen (`samsung,ss_touch`), MAX77705 Fuel Gauge/Charger, AMOLED Panel DSI.

### 3.2 The Strict Evidence Ledger (Selected Critical Drivers)

| Subsystem / Driver | In Defconfig? | In Binary? | Android Host? | QEMU Guest? | Native r8q Verified? | Critical Dependencies / Blockers |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **GICv3 Interrupts** | YES | YES | YES | YES | **NO** | Standard ARMv8.2 IP; register verified |
| **UFS 3.1 Host** | YES | YES | YES | NO (VirtIO) | **NO** | Must enforce Read-Only; ICE disabled |
| **SDHCI MicroSD** | YES | YES | YES | NO (VirtIO) | **NO** | Target rootfs device `/dev/mmcblk0` |
| **SimpleDRM Display** | YES | YES | NO (Android) | YES | **NO** | **BLOCKED:** Missing `simple-framebuffer` node in DTB |
| **Adreno 650 DRM** | YES | Module | YES (KGSL) | NO | **NO** | **BLOCKED:** Missing `/lib/firmware/qcom/sm8250/` blobs |
| **QCA6390 Wi-Fi 6** | YES | Module | YES (wlan) | NO | **NO** | **BLOCKED:** Missing `ath11k` firmware files |
| **Touchscreen** | YES | YES | YES (vendor) | NO | **NO** | **BLOCKED:** DTB compatible mismatch (`samsung,ss_touch`) |
| **Audio (LPASS)** | YES | Module | YES (Q6) | NO | **NO** | **BLOCKED:** Missing `adsp.mbn` firmware |

---

## 4. Device-Specific Dependency Inventory

To transition any driver from "Expected" to "Functional" on native r8q Linux, the following physical dependencies must be resolved:

1. **Power Regulators (SPMI + MAX77705):**  
   - Panel power: `dsi_panel_pwr_supply` via PM8150L LDOs.
   - Touch power: `tsp_ldo_en` rail via PM8150B.
   - MicroSD power: `vmmc-supply` (L12A) and `vqmmc-supply` (L13A) via PM8150.
2. **Clocks & Interconnect:**  
   - Qualcomm GCC clock branch enables for UFS (`gcc_ufs_phy_axi_clk`) and SDHCI (`gcc_sdcc2_apps_clk`).
   - RPMh bandwidth voting via Command DB (`0x0c3f000c`).
3. **GPIOs & Interrupt Lines:**  
   - Touchscreen IRQ: GPIO pin `e, B` on PM8150 TLMM.
   - Volume buttons: Power-on key on PM8150 PON peripheral.

---

## 5. Audit Verdict

| Evaluation Aspect | Finding | Verdict |
| :--- | :--- | :--- |
| **Kernel Build Provenance** | `build/Image` is a generic distribution package, not custom-built from defconfig | **FACT EXPOSED** |
| **DTB Simple-Framebuffer** | Missing from `build/r8q.dtb`; will cause dark display on native boot | **MATERIAL DEFECT** |
| **DTB Driver Bindings** | Vendor bindings in DTB will not bind to upstream Linux drivers | **BLOCKER** |
| **Firmware Dependencies** | Proprietary blobs (Adreno, QCA6390, Audio) missing from target rootfs | **BLOCKER** |
| **Native Device Testing** | Exactly 0 of 42 drivers have run under native Linux on physical hardware | **STRICT FACT** |
