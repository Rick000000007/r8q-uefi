# Project R8Q UEFI: Verification Ledger

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1
**Status:** Working evidence ledger for the corrected Milestone 1 baseline.
**Evidence date:** 2026-11-20

This ledger records the status of each claim used by the Milestone 1 documents. Status codes are defined in `docs/RESEARCH_BASELINE.md`:

- **D** — device-observed in this session (none).
- **V** — directly present in a pinned source.
- **I** — inferred from verified sources or a published specification.
- **U** — unknown, conflicting, or variant-dependent.

No claim below is **D**. Every hardware statement must be re-checked against the target unit before it is promoted to **D**.

---

## 1. Device identity and variants

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| DEV-01 | Marketing name is Samsung Galaxy S20 FE 5G, model `SM-G781B`. | V | Downstream bootargs `androidboot.em.model=SM-G781B`; public Samsung model data. | The `/DS` dual-SIM variant may share the `r8q` codename. |
| DEV-02 | Codename is `r8q`; SoC family is SM8250/Kona. | V | Upstream `sm8250-samsung-r8q.dts` compatible `samsung,r8q`, `qcom,sm8250`; downstream model string. | — |
| DEV-03 | SoC ID is 356. | I | Public SM8250 identification; not read from this unit. | Read `soc_id` at runtime; do not hardcode. |
| DEV-04 | Captured unit is board revision 8 (`R8 REV04`, `board-id 0x08 0x08`). | V | Downstream model, `qcom,board-id`, `androidboot.revision=8`. | Applies to the captured FDT only. Other revisions may differ. |
| DEV-05 | Captured unit is an 8 GB class unit. | V | Downstream `/memory` ranges total ~7.93 GiB; bootarg `androidboot.dram_info=01,08,00,8G`. | 6 GB variants are possible; runtime detection required. |
| DEV-06 | Captured unit was bootloader-unlocked at capture time. | V | Downstream bootargs `androidboot.verifiedbootstate=orange`, `androidboot.warranty_bit=1`. | Does not describe a retail-locked unit. |
| DEV-07 | Installed panel is `S6E3FC3_AMS646YD01_FHD`. | V | Downstream bootarg `msm_drm.dsi_display0=...S6E3FC3...` and `lcd_id=0x805081`. | Captured unit only; other panels are present in the FDT. |
| DEV-08 | Installed touch controller is STM FT5. | U | Downstream has STM, Zinitix, Melfas, and A96T3X6 nodes. | Identify at runtime by probe/ID. |
| DEV-09 | Installed charger/fuel gauge is MAX77705 + MAX17042. | U | Downstream has MAX77705 and PCA9468; no MAX17042 node. | Active charging path and fuel gauge are unknown. |
| DEV-10 | Installed WLAN is QCA6490. | I | Downstream `qcom,cnss-qca6490@b0000000`; a separate BT node is compatible with both `qca,qca6390` and `qca,qca6490`. | Endpoint, module identity, and firmware behavior unverified. |
| DEV-11 | Storage capacity is 128 GB. | U | No storage model/capacity in the downstream FDT. | Read UFS device data at runtime. |

---

## 2. Boot chain and integration

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| BOOT-01 | Normal boot chain is PBL → XBL → ABL → boot payload. | V | Public Qualcomm/Samsung boot-chain documentation; `EDK2-MSM` platform structure. | Exact XBL/ABL partition locations are not asserted. |
| BOOT-02 | XBL, ABL, TrustZone, and hypervisor are signed and boot-critical. | V | Public Qualcomm secure-boot documentation; Samsung ABL research. | Never replace or modify them. |
| BOOT-03 | Samsung ABL is EDK II/UEFI-based. | V | Public Samsung ABL research; `EDK2-MSM` targets Samsung ABL. | Does not imply that ABL exposes a standard UEFI shell. |
| BOOT-04 | A custom UEFI payload can be installed in the `BOOT` partition as an Android boot image. | I | Public community reports; `EDK2-MSM` boot-image packaging practice. | Not verified on this unit. Requires explicit authorization and a tested restore path. |
| BOOT-05 | `fastboot boot` works on retail Samsung ABL. | U | Conflicting community reports; Samsung `fastbootd` limitations. | Do not rely on it. |
| BOOT-06 | Download Mode remains available if ABL/XBL are untouched. | I | Download Mode is implemented by the stock boot chain. | Must be validated on the unit before any write. No absolute guarantee. |
| BOOT-07 | ABL enters the payload at `0x80008000` or `0x80080000`. | U | No direct evidence. Values come from generic ARM64 Linux boot assumptions. | Measure the actual load address and `text_offset`. |
| BOOT-08 | ABL passes the DTB pointer in `x0`. | I | ARM64 Linux boot protocol; `EDK2-MSM` PrePi stores `x0`. | Verify on the unit. |
| BOOT-09 | ABL enters at EL2. | U | `EDK2-MSM` handles both EL2 and EL1. | Detect `CurrentEL` at entry. |
| BOOT-10 | MMU and caches are off at entry. | U | Generic boot protocol expectation; not verified for Samsung ABL. | Entry code must handle either state safely. |
| BOOT-11 | Continuous splash scanout is active at entry. | U | Framebuffer is reserved and described, but ABL behavior is not observed. | Validate before using GOP. |
| BOOT-12 | The stock recovery partition is preserved by a `BOOT`-only change. | I | Recovery is a separate partition in the downstream `vbmeta` list. | Verify partition layout and boot behavior; do not assume. |
| BOOT-13 | The exact `BOOT` partition LUN/index is known. | U | Downstream only gives controller `1d84000.ufshc` and partition names. | Enumerate at runtime; do not hardcode. |

---

## 3. Memory map

### 3.1 `/memory`

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| MEM-01 | Captured unit has RAM at `0x80000000` + `0x3BB00000` and `0xC0000000` + `0x1C0000000`. | V | Downstream `/memory` node. | Captured unit only. |
| MEM-02 | The gap `0xBBB00000`–`0xC0000000` is not described as RAM. | V | Downstream `/memory` node. | Treat as reserved/unknown until mapped. |
| MEM-03 | Total described RAM is ~7.93 GiB. | I | Sum of the two ranges. | Do not hardcode; read the live FDT/memory map. |
| MEM-04 | All `r8q` units have 8 GB. | U | Only one downstream capture. | 6 GB variants may exist. |

### 3.2 Fixed downstream carveouts

The following are `V-R8Q-FDT` for the captured unit. Addresses and sizes must be re-read from the live FDT. `no-map`/reserved semantics must be honored.

| Region | Start | Size | Notes |
|---|---:|---:|---|
| `hyp_region` | `0x80000000` | `0x00600000` | Hypervisor; never touch. |
| `xbl_aop_region` | `0x80603000` | `0x0025D000` | XBL/AOP; downstream differs from upstream. |
| `cmd_db` | `0x80860000` | `0x00020000` | Qualcomm command DB. |
| `res_xbl_uefi_log_region` | `0x80880000` | `0x00014000` | XBL UEFI log. |
| `smem_region` | `0x80900000` | `0x00200000` | Qualcomm shared memory. |
| `removed_region` | `0x80B00000` | `0x07900000` | Large vendor-reserved region. |
| `pil_slpi_region` | `0x89200000` | `0x01500000` | SLPI firmware. |
| `pil_adsp_region` | `0x8A700000` | `0x02C00000` | ADSP firmware. |
| `pil_spss_region` | `0x8D300000` | `0x00100000` | SPSS firmware. |
| `pil_npu_region` | `0x8D400000` | `0x00500000` | NPU firmware. |
| `pil_video_region` | `0x8D900000` | `0x00500000` | Video firmware. |
| `pil_cvp_region` | `0x8DE00000` | `0x00500000` | CVP firmware. |
| `pil_cdsp_region` | `0x8E300000` | `0x01A00000` | CDSP firmware. |
| `pil_camera_region` | `0x8FD00000` | `0x00500000` | Camera firmware. |
| `pil_wlan_fw_region` | `0x90200000` | `0x00100000` | WLAN firmware. |
| `pil_ipa_fw_region` | `0x90300000` | `0x00010000` | IPA firmware. |
| `pil_ipa_gsi_region` | `0x90310000` | `0x0000A000` | IPA GSI. |
| `pil_gpu_region` | `0x9031A000` | `0x00002000` | GPU firmware. |
| `cdsp_secure_heap` | `0x90400000` | `0x00600000` | CDSP secure heap. |
| `cont_splash_region` | `0x9C000000` | `0x02300000` | Continuous splash framebuffer. |
| `disp_rdump_region` | `0x9C000000` | `0x01200000` | Display ramdump; overlaps splash. |
| `dfps_data_region` | `0x9E300000` | `0x00100000` | Display dynamic frame-rate data. |
| `sec_debug_region` | `0x9F000000` | `0x00800000` | Samsung security debug. |
| `ss_plog_region` | `0x9F800000` | `0x00200000` | Samsung persistent log. |
| `ramoops` | `0x9FA00000` | `0x00100000` | Pstore/ramoops. |
| `kaslr_region` | `0xA0001000` | `0x00001000` | KASLR seed/data. |
| `sec_debug_rdx_bootdev` | `0x100000000` | `0x0AD00000` | Samsung debug/RDX buffer. |
| `tima_region` | `0xB0100000` | `0x00100000` | Samsung TIMA/Knox. |
| `uh_heap_region` | `0xB0400000` | `0x01800000` | Vendor heap; purpose not documented. |

### 3.3 Dynamic downstream pools

These are `V-R8Q-FDT` size declarations, not fixed addresses. The kernel/vendor allocator chooses addresses at runtime. A UEFI memory map must reserve them if the inherited FDT declares them reserved or if the platform uses them.

| Pool | Size | Notes |
|---|---:|---|
| `adsp_region` | `0x00C00000` | Shared DMA pool. |
| `sdsp_region` | `0x00800000` | Shared DMA pool. |
| `cdsp_region` | `0x00400000` | Shared DMA pool. |
| `mem_dump_region` | `0x02800000` | Dump pool. |
| `sp_region` | `0x01000000` | Secure processor pool. |
| `user_contig_region` | `0x01000000` | Contiguous user memory. |
| `qseecom_region` | `0x01C00000` | QSEECom. |
| `qseecom_ta_region` | `0x03000000` | QSEECom TA. |
| `secure_display_region` | `0x0D800000` | Secure display. |
| `cnss_wlan_region` | `0x01C00000` | WLAN. |
| `mailbox_region` | `0x00020000` | Mailbox. |
| `camera_mem_region` | `0x40000000` | Camera; very large dynamic pool. |

### 3.4 Upstream differences

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| MEM-05 | Upstream `xbl_aop` is `0x80700000` + `0x160000`. | V | `L6.18` `sm8250.dtsi`. | Different from downstream. Do not mix maps. |
| MEM-06 | Upstream `removed` is `0x80B00000` + `0x5300000`. | V | `L6.18` `sm8250.dtsi`. | Downstream is larger. |
| MEM-07 | Upstream camera/WLAN/IPA/NPU/video/CVP carveouts are at `0x86200000`–`0x87800000`. | V | `L6.18` `sm8250.dtsi`. | Downstream relocates them; do not use upstream addresses for this device. |
| MEM-08 | Upstream `cdsp`/`slpi`/`adsp` are at `0x87800000`/`0x88C00000`/`0x8A100000`. | V | `L6.18` `sm8250.dtsi`. | Downstream uses different addresses. |
| MEM-09 | The upstream map is sufficient for the `r8q` target. | U | It omits Samsung-specific carveouts and uses different PIL addresses. | Use the live downstream FDT. |

### 3.5 Candidate firmware window

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| MEM-10 | `0x9E400000`–`0x9F000000` is a 12 MiB free window in the downstream map. | I | Follows `dfps_data` end `0x9E400000` and precedes `sec_debug` `0x9F000000`. | Candidate only; validate against the live map. |
| MEM-11 | A 4 MiB FD can be placed at `0x9E400000`. | I | Same window; FD size is a design choice. | Not verified; do not flash. |
| MEM-12 | `0xCE000000` + 7 MiB is a valid alternative FD window. | I | `EDK2-MSM` reference values. | Reference only; may conflict with OS load or unknown carveouts. |
| MEM-13 | `0x80650000` is a safe device-tree store address. | I | `EDK2-MSM` uses it. | It lies inside the downstream `xbl_aop` region (`0x80603000`–`0x80860000`); **do not reuse it without validation**. |
| MEM-14 | The UEFI memory map must be derived from the live FDT, not a static table. | I | The downstream map is variant-specific and has dynamic pools. | Mandatory design rule. |

---

## 4. CPU, GIC, and timer

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| CPU-01 | 8 cores in 3 clusters (4+3+1). | V | `L6.18` `sm8250.dtsi` CPU nodes. | — |
| CPU-02 | PSCI is the enable method. | V | `L6.18` `sm8250.dtsi`. | — |
| CPU-03 | Exact CPU frequencies are 1.80/2.42/2.84 GHz. | U | OPP tables vary by bin; not read from this unit. | Read from hardware/OPP tables. |
| CPU-04 | GICD is `0x17A00000` + `0x10000`. | V | `L6.18` `sm8250.dtsi`. | — |
| CPU-05 | GICR is `0x17A60000` + `0x100000`. | V | `L6.18` `sm8250.dtsi`. | 8 × 128 KiB. |
| CPU-06 | Generic timer frequency is 19.2 MHz. | V | `L6.18` `sm8250.dtsi` `clock-frequency`. | — |
| CPU-07 | Timer frame is `0x17C20000`. | V | `L6.18` `sm8250.dtsi`. | Frame 0 at `0x17C21000`/`0x17C22000`. |
| CPU-08 | NS physical timer is PPI 30 / INTID 14. | I | ARM GICv3/architected timer conventions. | Validate against the GIC configuration. |

---

## 5. Display

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| DISP-01 | MDSS/DPU base is `0xAE00000`. | V | `R8Q-FDT`, `L6.18`. | — |
| DISP-02 | DSI PHY0/1 are `0xAE94400`/`0xAE96400`. | V | `R8Q-FDT`. | — |
| DISP-03 | DSI PLL0/1 are `0xAE94900`/`0xAE96900`. | V | `R8Q-FDT`. | — |
| DISP-04 | Framebuffer is `0x9C000000` + `0x2300000`, 1080×2400, stride 4320, `a8r8g8b8`. | V | `L6.18` `sm8250-samsung-common.dtsi`, `R8Q-FDT`. | Reserved; scanout state at handoff is U. |
| DISP-05 | Captured unit uses `S6E3FC3_AMS646YD01_FHD`. | V | `R8Q-FDT` bootargs and panel node. | Captured unit only. |
| DISP-06 | Captured unit's panel node is 1080×2400 with 60 Hz and 120 Hz timing entries and DCS backlight max 486. | V | `R8Q-FDT` S6E3FC3 node. | Timing tables include `0x3C` and `0x78`; active mode is not established. |
| DISP-07 | Alternate panels `EA8076A` and `EA8079B` exist with 60 Hz and 120 Hz timing entries. | V | `R8Q-FDT`. | Detect at runtime; do not infer the active mode from the node alone. |
| DISP-08 | GOP can safely reuse the inherited framebuffer. | I | Framebuffer is reserved and described. | Must validate scanout and format on hardware. |
| DISP-09 | Reinitializing the DPU/DSI is safe. | U | Complex clock/PHY/panel sequencing; vendor code not available. | Avoid in early bring-up. |

---

## 6. Storage

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| STOR-01 | UFS HC is `0x1D84000` + `0x3000`. | V | `R8Q-FDT`, `L6.18`. | — |
| STOR-02 | UFS ICE is `0x1D90000` + `0x8000`. | V | `R8Q-FDT`. | Upstream mainline does not describe this second range. |
| STOR-03 | UFS PHY is `0x1D87000`. | V | `L6.18`. | — |
| STOR-04 | UFS IRQ is SPI 265. | V | `L6.18`, `R8Q-FDT`. | — |
| STOR-05 | UFS device is 128 GB Samsung `KLUDG4UHDB-B2D1`. | U | Not in the downstream FDT. | Read at runtime. |
| STOR-06 | UFS has 4 LUNs with fixed sizes. | U | Not in the downstream FDT. | Enumerate at runtime. |
| STOR-07 | `sda`/`sdb`/`sdc`/`sdd` mapping is known. | U | Linux block naming depends on enumeration order. | Do not hardcode. |
| STOR-08 | SDHCI is `0x8804000` + `0x1000`, 4-bit. | V | `R8Q-FDT`. | — |
| STOR-09 | MicroSD hotplug/UHS-I works. | U | Controller node exists; card detect and tuning not verified. | Validate on hardware. |
| STOR-10 | FAT12/16/32 can be provided by EDK II `FatPkg`. | V | `EDK2-202411` source tree. | Build/runtime validation pending. |

---

## 7. USB, PCIe, and wireless

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| USB-01 | USB controller is `ssusb@a600000` with DWC3 at `0xA600000`. | V | `R8Q-FDT`. | — |
| USB-02 | Downstream advertises DRD and super-speed. | V | `R8Q-FDT` `dwc3@a600000`. | — |
| USB-03 | Upstream mainline uses peripheral/high-speed only. | V | `L6.18` `sm8250-samsung-common.dtsi`. | Shows the mainline state, not the hardware limit. |
| USB-04 | USB host/XHCI and keyboard work in UEFI. | U | No driver or hardware evidence. | Major bring-up task. |
| PCIE-01 | PCIe0/1/2 are at `0x1C00000`/`0x1C08000`/`0x1C10000`. | V | `R8Q-FDT`, `L6.18`. | — |
| PCIE-02 | WLAN is described as QCA6490 on PCIe root complex 0. | I | `R8Q-FDT` `qcom,cnss-qca6490@b0000000`, `qcom,wlan-rc-num=0`; BT node lists QCA6390/QCA6490. | Endpoint/module identity and firmware unverified. |
| PCIE-03 | Wi-Fi/BT work in UEFI. | U | No driver evidence. | Not a Milestone 1 claim. |

---

## 8. Power, thermal, and input

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| PWR-01 | PMIC family is PM8150/PM8150B/PM8150L (plus PM8150A regulators). | V | `R8Q-FDT` SPMI nodes. | — |
| PWR-02 | Charger nodes are MAX77705 at `0x66` and PCA9468 at `0x57`. | V | `R8Q-FDT`. | Active path unknown. |
| PWR-03 | SMB5 node is disabled. | V | `R8Q-FDT` `status = "disabled"`. | Do not assume SMB5 is active. |
| PWR-04 | Fuel gauge is MAX17042. | U | No MAX17042 node found. | Identify at runtime. |
| PWR-05 | TSENS is at `0xC222000`/`0xC263000` and `0xC223000`/`0xC265000`. | V | `R8Q-FDT`. | Compatible `qcom,tsens24xx`. |
| PWR-06 | Volume-up is a GPIO key. | V | `R8Q-FDT` `gpio-keys`. | Power/volume-down handling unknown. |
| PWR-07 | Touch is STM FT5 at `0x49`. | U | Multiple touch nodes exist. | Probe at runtime. |
| PWR-08 | Battery/thermal telemetry is available in UEFI. | U | Requires I2C/SPMI/TSENS drivers that do not exist yet. | Planned, not implemented. |

---

## 9. Firmware variables

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| VAR-01 | `uefivarstore` partition exists. | U | Downstream `vbmeta` list does not include it; no partition table. | Do not assume. |
| VAR-02 | Internal variable store is `sdd31`. | U | No evidence. | Do not hardcode. |
| VAR-03 | File-backed variables on an ESP are the safest early path. | I | Avoids internal partition writes. | Implement in a later milestone. |
| VAR-04 | Runtime variable persistence after `ExitBootServices()` is straightforward. | U | File I/O drivers are not runtime-safe by default. | Needs a runtime-safe design or an OS helper. |

---

## 10. OS boot

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| OS-01 | Linux ARM64 EFI stub can be loaded with `LoadImage`/`StartImage`. | V | UEFI specification; Linux arm64 EFI stub. | Kernel/DTB/initrd packaging must be validated. |
| OS-02 | Direct boot uses `x0` = DTB and `x1`–`x3` = 0. | V | ARM64 Linux boot protocol. | Exact load address is U. |
| OS-03 | The inherited DTB can be patched for `/chosen` and reserved memory. | I | Standard FDT manipulation. | Must preserve vendor carveouts. |
| OS-04 | Linux boots to userspace on this firmware. | U | No firmware or hardware run. | Milestone 6+ goal. |
| OS-05 | Windows ARM64 can boot. | U | No ACPI tables, drivers, or boot evidence. | Research only. |
| OS-06 | Windows installer can see internal UFS. | U | No UFS Windows driver. | Blocker. |
| OS-07 | Windows can use the UEFI GOP framebuffer. | I | MSBDD can use GOP in some configurations. | Not validated; ACPI/display requirements unknown. |

---

## 11. Build and toolchain

| ID | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| BUILD-01 | Host is Kali ARM64 with 6 cores and ~7.4 GiB RAM. | V | `HOST` inspection. | Re-check before builds. |
| BUILD-02 | GCC 16.2.0, Clang 21.1.8, Make 4.4.1, DTC 1.8.1, iASL 20260408, Python 3.14.10, Git 2.53.0. | V | `HOST` inspection. | Record exact versions in build logs. |
| BUILD-03 | `aarch64-linux-gnu-gcc` is available. | V | `HOST` inspection. | Useful for BootShim/reference experiments. |
| BUILD-04 | `qemu-system-aarch64` is available. | U | Not installed. | Must be installed for software-only tests. |
| BUILD-05 | `adb`/`fastboot` are available. | U | Not installed. | Not needed until authorized device work. |
| BUILD-06 | EDK II `edk2-stable202411` is checked out. | V | Local `edk2/` shallow clone at `0f3867fa...`. | Submodules are not initialized. |
| BUILD-07 | EDK II builds successfully. | U | No build performed. | Milestone 2 exit criterion. |
| BUILD-08 | The build is reproducible. | U | No build, no manifest of artifacts. | Design goal, not a claim. |

---

## 12. Ledger maintenance

- Add a **D** row only when a command and output from the target unit are recorded in the repository (with identifiers redacted).
- When a **V** value is used in code, cite the source tag in a comment and add a runtime sanity check where possible.
- When an **I** value becomes a **D** value, update this ledger and the affected document in the same commit.
- Never silently promote an **I** or **U** value to **V** because it appears in a public firmware project.
