# Project R8Q UEFI: Milestone 1 Research Baseline

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, codename `r8q`, Qualcomm SM8250/Kona)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Research baseline. This document supersedes the unsupported "Approved Architectural Baseline" claims in commit `07b1882`.
**Evidence date:** 2026-11-20
**Device access:** No target device was attached during this work. No firmware was built, flashed, erased, or executed on hardware.

---

## 1. Purpose and scope

Milestone 1 establishes a defensible, evidence-graded description of the platform before any firmware code or device modification. It answers four questions:

1. What is actually known about the `r8q` hardware and Samsung/Qualcomm boot chain?
2. Which values are source-verified, which are inferred, and which remain unknown?
3. What is a safe, reversible integration hypothesis that preserves the stock boot chain?
4. What must be measured on the target unit before Milestone 2 can make hardware claims?

This baseline is intentionally conservative. A value appearing in a public reference implementation is **not** treated as a fact about this phone. A value is only "verified" when it is directly present in a pinned source and the source is identified. No value in this baseline is "device-observed" because no device was connected.

---

## 2. Evidence policy

Every hardware or boot-chain statement is tagged with one of these levels:

| Tag | Meaning | How it may be used |
|---|---|---|
| **D** | **Device-observed.** Reproduced on the target unit in this session with a recorded command and output. | May be used as a platform fact for that unit. |
| **V** | **Source-verified.** Directly present in a pinned upstream or downstream source. | May be used as a design input, with the source named. Does not prove the value on every variant. |
| **I** | **Inferred.** Derived by combining verified sources or by applying a documented specification. | Must be validated at runtime or on hardware before being treated as fact. |
| **U** | **Unknown.** No reliable source; conflicting sources; or variant-dependent. | Must not be hardcoded. Must be discovered at runtime or measured. |

Source tags used in the ledger:

- `L6.18` — Linux `v6.18`, commit `f7b88edb52c8dd01b7e576390d658ae6eef0e134`, files under `arch/arm64/boot/dts/qcom/`.
- `R8Q-FDT` — the supplied downstream Samsung/vendor FDT in `devicetree/r8q-live.dts`. Provenance is not established; see `devicetree/README.md`. It is evidence, not a build input.
- `EDK2-202411` — TianoCore EDK II `edk2-stable202411`, commit `0f3867fa6ef0553e26c42f7d71ff6bdb98429742`.
- `EDK2-MSM` — public `edk2-porting/edk2-msm` reference at commit `e1952621f419f8db60ed28271264e1b5184c571d`. Used only as a technical reference; no code or complete platform implementation is imported.
- `UEFI` / `PI` / `ACPI` / `ARM64` — published specifications.
- `HOST` — the build host inspected in this session.

Rules applied throughout the project:

- Do not replace Qualcomm PBL/XBL or Samsung ABL.
- Do not hardcode RAM size, panel model, touch controller, charger, fuel gauge, storage capacity, LUN layout, or partition indices.
- Do not claim Windows installability or functionality without real driver and boot evidence.
- Do not write to boot-critical partitions during Milestone 1 or early bring-up.
- Treat any address that is not present in a pinned source as a candidate, not a constant.

---

## 3. Pinned sources and provenance

### 3.1 Upstream Linux device tree

The upstream mainline `r8q` support is minimal but useful for SoC-level facts:

| File | SHA-256 |
|---|---|
| `sm8250.dtsi` | `d1b48075aa25dccc3ff3413bca62b7b013a72d41200f07ebf88594609cb0aef7` |
| `sm8250-samsung-common.dtsi` | `2fb16a9ce78223b67d0cfbd7f6f019a4e14c0d4b76e408a3ae0f787c8608c5c9` |
| `sm8250-samsung-r8q.dts` | `763fc9c9c1ee7862ca993ebf6c8e67ef84b6056f9c4da5a8d49aa88356d2c71a` |

The upstream `sm8250-samsung-r8q.dts` only adds firmware names for ADSP/CDSP/SLPI and sets the model to "Samsung Galaxy S20 FE". It does **not** describe the panel, touch controller, charger, UFS LUN layout, or the full Samsung memory map. Those must come from the downstream FDT or runtime discovery.

### 3.2 Downstream Samsung/vendor FDT

`devicetree/r8q-live.dts` is a 35,733-line downstream FDT with:

- model `Samsung R8Q EUR PROJECT - R8 REV04 (board-id,08)`;
- `qcom,msm-id = <0x164 0x20001>` and `qcom,board-id = <0x08 0x08>`;
- a two-range `/memory` node;
- a detailed `/reserved-memory` map;
- Samsung panel, touch, charger, PMIC, UFS, SDHCI, USB, PCIe, WLAN, and TSENS nodes.

Provenance is **not** documented. The file appears to have been captured from a booted device, but the capture method, date, firmware version, and chain of custody are unknown. It contains device-specific identifiers in `/chosen/bootargs`; those have been redacted in this repository. It must not be published or redistributed as a clean vendor source without a provenance review.

The downstream FDT is used as **device-specific evidence** for the captured unit. It is not assumed to describe every `r8q` variant.

### 3.3 EDK II

The build baseline is `edk2-stable202411` at commit `0f3867fa6ef0553e26c42f7d71ff6bdb98429742`. The host has a shallow checkout of that tag, but its submodules are not initialized and no EDK II build has been performed. `edk2-stable202408.01` at `4dfdca63a93497203f197ec98ba20e2327e4afe4` is retained as a fallback pin. The choice is an evaluation pin, not a claim that the tree has been build-validated.

### 3.4 Public reference implementation

`edk2-msm` is consulted for boot-chain mechanics, EDK II platform structure, and memory-map examples. Its values (for example, `FD_BASE=0xCE000000`, `FD_SIZE=0x00700000`, UEFI pool `0xC0000000` + `0x0E000000`, stack `0x9FF90000`, device-tree store `0x80650000`) are **reference values**, not verified `r8q` facts. They are useful for designing experiments and for understanding how a Qualcomm EDK II port is normally assembled.

---

## 4. What is established

### 4.1 SoC and CPU

- SM8250/Kona, ARMv8.2-A, 8 cores in three clusters: 4× Kryo 485 Silver (Cortex-A55-class), 3× Kryo 485 Gold (Cortex-A77-class), 1× Kryo 485 Prime (Cortex-A77-class). `V-L6.18`
- The exact OPP frequencies are not part of the upstream DTS and must not be hardcoded. `U`
- PSCI is used for secondary-core bring-up. `V-L6.18`

### 4.2 Interrupts and timer

- GICv3 distributor: `0x17A00000`, size `0x10000`. `V-L6.18`
- GICv3 redistributors: `0x17A60000`, size `0x100000` (8 × 128 KiB). `V-L6.18`
- ARM generic timer frequency: `19,200,000 Hz`. `V-L6.18`
- MMIO timer frame: `0x17C20000`, with frame 0 at `0x17C21000`/`0x17C22000`. `V-L6.18`
- The architectural timer PPI/INTID mapping must be validated against the GIC and the exception level at handoff. `I`

### 4.3 Memory

The captured unit's downstream `/memory` node describes:

| Range | Size |
|---|---|
| `0x80000000`–`0xBBB00000` | `0x3BB00000` (~954.7 MiB) |
| `0xC0000000`–`0x280000000` | `0x1C0000000` (7,168 MiB) |

The gap `0xBBB00000`–`0xC0000000` is `0x4500000` (~69 MiB). The total described RAM is approximately 7.93 GiB, consistent with an 8 GB class unit. `V-R8Q-FDT` for the captured unit. Other units may be 6 GB or have a different carveout layout. `U`

The downstream `/reserved-memory` map is materially different from the upstream mainline map. In particular:

- downstream `xbl_aop` is `0x80603000` + `0x25D000`, while upstream uses `0x80700000` + `0x160000`;
- downstream `removed` is `0x80B00000` + `0x7900000` (121 MiB), while upstream uses `0x80B00000` + `0x5300000` (83 MiB);
- downstream PIL regions (`pil_slpi`, `pil_adsp`, `pil_cdsp`, camera, WLAN, IPA, NPU, video, CVP) are at different addresses than the upstream mainline carveouts.

The downstream map is the better starting point for this device, but it still must be parsed from the live FDT at runtime. See `docs/VERIFICATION_LEDGER.md` for the full table.

### 4.4 Display

- MDSS/DPU: `0xAE00000`. `V-R8Q-FDT`, `V-L6.18`
- DSI PHY 0: `0xAE94400`; DSI PHY 1: `0xAE96400`; DSI PLL 0: `0xAE94900`; DSI PLL 1: `0xAE96900`. `V-R8Q-FDT`
- Continuous-splash framebuffer: `0x9C000000`, size `0x2300000` (35 MiB), 1080×2400, stride 4320, format `a8r8g8b8`. `V-L6.18`, `V-R8Q-FDT`
- The captured unit's bootargs select `ss_dsi_panel_S6E3FC3_AMS646YD01_FHD`, with `lcd_id=0x805081`. `V-R8Q-FDT` for the captured unit.
- The downstream FDT also contains panel definitions for `EA8076A_AMS646UJ10_FHD` and `EA8079B_AMS646YB01_FHD`. These are variants, not alternate names for the same panel. `V-R8Q-FDT`
- Whether ABL leaves the DPU/DSI scanout active at the UEFI handoff is **not** verified. `U`

### 4.5 Storage controllers

- UFS host controller: `0x1D84000`, size `0x3000`; UFS ICE: `0x1D90000`, size `0x8000`; IRQ SPI 265. `V-R8Q-FDT`, `V-L6.18`
- UFS PHY: `0x1D87000`. `V-L6.18`
- SDHCI: `0x8804000`, size `0x1000`; 4-bit bus; IRQs `0xCC` and `0xDE`. `V-R8Q-FDT`
- The UFS device model, capacity, LUN count, LUN sizes, and partition indices are **not** verified. `U`
- The downstream `vbmeta` node lists partition names (`vbmeta`, `boot`, `system`, `vendor`, `product`, `odm`, `prism`, `optics`, `vbmeta_samsung`, `recovery`, `dtbo`, `abl`, `xbl`, `tz`, `hyp`) but does not establish their LUN or index. `V-R8Q-FDT` for names only.
- MicroSD card detect, hotplug, and UHS support are **not** verified. `U`

### 4.6 USB, PCIe, and wireless

- USB DWC3/SSUSB: `0xA600000`; downstream advertises `dr_mode = "drd"` and `maximum-speed = "super-speed"`. `V-R8Q-FDT`
- Upstream mainline currently restricts `usb_1_dwc3` to `dr_mode = "peripheral"` and `maximum-speed = "high-speed"`, and removes the USB3 PHY. `V-L6.18`
- USB host mode, XHCI, Type-C role switching, and USB keyboard support are **not** verified. `U`
- PCIe controllers: `0x1C00000`, `0x1C08000`, `0x1C10000`. `V-R8Q-FDT`, `V-L6.18`
- Downstream WLAN node: `qcom,cnss-qca6490@b0000000`, `qcom,wlan-rc-num = <0>`. A separate Bluetooth node is compatible with both `qca,qca6390` and `qca,qca6490`, so the exact combo module is not established. `V-R8Q-FDT` for the nodes; module identity `I`/`U`.
- PCIe endpoint enumeration, WLAN firmware loading, and Wi-Fi/BT functionality are **not** verified. `U`

### 4.7 Power, thermal, and input

- PMIC family: PM8150, PM8150B, PM8150L (and PM8150A regulator nodes). `V-R8Q-FDT`
- Charger nodes: `maxim,max77705` at I2C `0x66`, `nxp,pca9468` at `0x57`, and a `qcom,qpnp-smb5` node marked `status = "disabled"`. `V-R8Q-FDT`
- No `max17042` fuel-gauge node was found in the downstream FDT. The active fuel-gauge path is **unknown**. `U`
- TSENS: `0xC222000`/`0xC263000` and `0xC223000`/`0xC265000`, compatible `qcom,tsens24xx`. `V-R8Q-FDT`
- Volume-up is described as a `gpio-keys` key. Power-key and volume-down handling are **not** confirmed in the downstream FDT. `U`
- Touch candidates: STM `stm,fts_touch` at `0x49`, Zinitix `zinitix,zt_ts_device` at `0x20`, Melfas `melfas,mms_ts` at `0x48` (disabled), and `a96t3x6` at `0x20`. The installed controller is **unknown**. `U`

### 4.8 Boot chain and integration

- The normal chain is Qualcomm PBL → XBL → Samsung ABL → boot payload. `V-PUBLIC`, `V-EDK2-MSM`
- XBL, ABL, TrustZone, and the hypervisor are signed and must not be replaced or modified. `V-PUBLIC`
- Public community research describes installing a custom UEFI payload in Samsung's `BOOT` partition, packaged as an Android boot image, while leaving ABL/XBL/recovery intact. This is a **hypothesis for a later, explicitly authorized phase**, not a verified procedure for this unit. `I`
- `fastboot boot` is not reliably supported by retail Samsung ABL; `fastbootd` may reject it. The exact behavior of this unit is **unknown**. `U`
- The ABL handoff state (exception level, MMU/caches, secondary cores, `x0` DTB pointer, display scanout, memory map) is **unknown**. The design must detect it rather than assume it. `U`

---

## 5. What is not established

The following items are deliberately marked unknown and must not appear as fixed constants in code or documentation:

- exact ABL entry address, load address, and `text_offset`;
- exact exception level and MMU/cache state at handoff;
- exact UEFI memory map provided by ABL, if any;
- exact UFS LUN layout, partition indices, sizes, and storage capacity;
- exact RAM size and variant (6 GB vs 8 GB);
- installed panel, touch controller, charger, fuel gauge, and wireless module;
- USB host/OTG capability and Type-C role behavior;
- PCIe endpoint population and WLAN firmware loading;
- whether continuous splash scanout remains active at handoff;
- whether the stock recovery and Download Mode remain reachable after a custom `BOOT` payload;
- Windows ARM64 bootability, driver availability, and ACPI requirements;
- EDK II build success, image size, and runtime behavior on hardware.

---

## 6. Corrections to the prior baseline

The following claims in the previous Milestone 1 documents were unsupported and have been removed or downgraded:

| Prior claim | Corrected status |
|---|---|
| Fixed 8 GB LPDDR5 and fixed `0x80000000`–`0x27FFFFFFF` range | Captured unit is 8 GB class; runtime detection required; variants unknown. |
| Fixed FD base `0x9E400000` and 4 MiB layout | Candidate only; must be validated against the live reserved-memory map. |
| Fixed handoff address `0x80008000` | Unknown; ARM64 boot protocol and ABL behavior must be measured. |
| Exact XBL/ABL/TZ/hyp partition names and LUN indices (`sdb1`, `sdd5`, etc.) | Not verified; enumerate at runtime. |
| UFS model `KLUDG4UHDB-B2D1`, 128 GB, 36/37 partitions | Not verified; read from the device. |
| Panel fixed to `S6E3FC3` | Captured unit selects it; other variants use `EA8076A`/`EA8079B`; detect at runtime. |
| Charger/fuel gauge `MAX77705`/`MAX17042` | MAX77705 and PCA9468 nodes exist; no MAX17042 node; active path unknown. |
| USB 3.0 XHCI host and USB keyboard assumed | Downstream advertises DRD/super-speed; upstream is peripheral/high-speed; host mode unverified. |
| Wi-Fi `QCA6390` | Downstream WLAN node identifies `QCA6490`; the BT node lists both QCA6390 and QCA6490; endpoint/module identity and firmware behavior unverified. |
| Windows Level 1 "ACHIEVED" and Level 2 "IN DESIGN" | No Windows boot evidence; all levels are research-only and blocked. |
| `fastboot boot` as a safe test path | Not verified on retail Samsung; do not rely on it. |
| "100% safe" / "always recoverable" guarantees | Replaced with a tested-backup and explicit-authorization policy; no absolute guarantee. |
| "19 commands return verified live telemetry" | Commands are planned; most depend on drivers that do not exist yet. |

---

## 7. Safe integration hypothesis (not authorized for execution)

The only integration path considered for later work is:

1. Keep PBL, XBL, ABL, TrustZone, hypervisor, `EFS`, `sec_efs`, `persist`, modem calibration, and stock recovery untouched.
2. Build a self-contained UEFI payload with a Linux-kernel-compatible ARM64 header or an Android boot-image wrapper, as required by the bootloader behavior measured on the unit.
3. Install it only in the `BOOT` partition, or boot it through a chainloader, after a verified stock-image backup and a tested restore path.
4. Keep a physical Download Mode path and a known-good stock `BOOT` image available offline.
5. Require explicit user authorization before any write to the device.

No step in this hypothesis has been executed. It is a plan for a later milestone.

---

## 8. Milestone 2 entry criteria

Milestone 2 may begin only when:

- this baseline is committed and the manifest is regenerated;
- the target unit's stock `BOOT` image and partition layout have been captured read-only, with hashes;
- the ABL handoff state has been measured (or a safe instrumentation plan exists);
- the live FDT and reserved-memory map have been captured and compared with `r8q-live.dts`;
- a QEMU AArch64 test path exists for software-only validation;
- the user has authorized any device-facing experiment.

Until then, work is limited to documentation, host-side build setup, static validation, and QEMU.

---

## 9. Document index

| Document | Purpose |
|---|---|
| `docs/RESEARCH_BASELINE.md` | This evidence policy and summary. |
| `docs/VERIFICATION_LEDGER.md` | Claim-by-claim status and sources. |
| `docs/UEFI_ARCHITECTURE.md` | Platform architecture and boot-chain boundaries. |
| `docs/HARDWARE_DEPENDENCY_GRAPH.md` | Initialization ownership and dependencies. |
| `docs/FIRMWARE_DRIVER_SUPPORT_MATRIX.md` | Driver plan, dependencies, and status. |
| `docs/EDK2_PLATFORM_DESIGN.md` | EDK II package, FDF, PCD, and phase design. |
| `docs/SHELL_COMMAND_SUITE.md` | Shell and diagnostic command plan. |
| `docs/LINUX_BOOT_DESIGN.md` | Linux EFI-stub and direct-boot handoff design. |
| `docs/WINDOWS_COMPATIBILITY_REPORT.md` | Windows ARM64 research status and blockers. |
| `docs/RECOVERY_AND_SAFETY_PLAN.md` | Partition protection, backup, and authorization gates. |
| `docs/REPRODUCIBLE_BUILD_STRATEGY.md` | Toolchain, pins, and build workflow. |
| `docs/PHASED_IMPLEMENTATION_SCHEDULE.md` | Evidence-gated milestone plan. |
| `devicetree/README.md` | Provenance and sanitization notes for the downstream FDT. |
