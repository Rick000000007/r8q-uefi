# Project R8Q UEFI: Milestone 5 — Diagnostic Suite Specification

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Architecture:** ARM64 / AArch64 (ARMv8.2-A)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona)  
**Diagnostic Suite:** Modular Independent Applications & Master Orchestrator  

---

## 1. Architecture Overview

Project R8Q UEFI implements a modular diagnostic architecture where each hardware subsystem is probed by a dedicated, standalone UEFI application. Each application adheres to standard UEFI application conventions (`UefiMain`), uses standard UEFI protocols where possible, detects uninitialized or unavailable hardware gracefully without hangs or panics, and returns meaningful `EFI_STATUS` return codes.

All 10 applications are integrated into the primary firmware volume (`FVMAIN_COMPACT`) and can be executed either directly from the UEFI Shell prompt, invoked via automation scripts (`hardware-audit.nsh`), or run sequentially by the master test runner (`diagnostics.efi`).

```
platform/R8QPkg/Applications/
├── SysInfo/        --> sysinfo.efi       (Platform, SoC ID, Board Rev, UEFI Tables)
├── CpuInfo/        --> cpuinfo.efi       (Kryo 585 Topology, MIDR/MPIDR, Arch Timer)
├── MemMap/         --> memmap.efi        (8 GB LPDDR5 Memory Map & Carveouts)
├── Display/        --> display.efi       (GOP 1080x2400 @ 32bpp, Blt, Text Console)
├── FdtInfo/        --> fdtinfo.efi       (Device Tree Blob, Root Model, Compatibles)
├── Storage/        --> storage.efi       (UFS 3.1 KLUDG4UHDB-B2D1, SDHCI, Read-Only Audit)
├── Battery/        --> battery.efi       (MAX77705 / PM8150B Fuel Gauge Subsystem)
├── Thermal/        --> thermal.efi       (TSENS v2 16 Sensor Channels & Trip Policies)
├── Firmware/       --> firmware.efi      (Firmware Volume, Option A File NVRAM Audit)
├── Diagnostics/    --> diagnostics.efi   (Master Diagnostic Orchestrator)
└── ShellTest/      --> ShellTest.efi     (Shell 2.2 Acceptance & Invariant Test Suite)
```

---

## 2. Diagnostic Application Specifications

### 2.1 `sysinfo.efi` (System Information)
- **Primary Function:** Verifies device model identity, board revision, Qualcomm SoC ID, and UEFI System / Runtime Services table integrity.
- **Hardware Profile:**
  - Device: Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)
  - Board Revision: `R8 REV04` (Board ID: 0x08)
  - SoC: Qualcomm Snapdragon 865 (SM8250 Kona, Part ID: 356)
- **Table Pointers:** Validates BootServices, RuntimeServices, and ConfigurationTable pointers and CRC32 header signatures.

### 2.2 `cpuinfo.efi` (CPU Topology & Architectural Timer)
- **Primary Function:** Probes ARMv8.2-A Kryo 585 CPU cluster topology, execution level, and generic timer frequency.
- **Topology Breakdown:**
  - Cluster 0 (Silver): 4x Cortex-A55 @ 1.80 GHz (`0xD05`)
  - Cluster 1 (Gold): 3x Cortex-A77 @ 2.42 GHz (`0xD0D`)
  - Cluster 2 (Gold+ Prime): 1x Cortex-X1 @ 2.84 GHz (`0xD0D`)
- **Registers Read:** Inline assembly queries `CurrentEL` (reports EL2/EL1), `MIDR_EL1`, `MPIDR_EL1`, `CNTFRQ_EL0` (19.2 MHz), and `CNTVCT_EL0`.

### 2.3 `memmap.efi` (Physical Memory Map & Carveouts)
- **Primary Function:** Queries `gBS->GetMemoryMap()` to enumerate all memory descriptors and categorize physical RAM.
- **Physical DRAM Layout:**
  - Bank 0 (Low DRAM): `0x80000000` - `0x9FFFFFFF` (512 MiB)
  - Bank 1 (High DRAM): `0x100000000` - `0x27FFFFFFF` (6.0 GiB)
  - Total Physical DRAM: 8.0 GiB LPDDR5
- **Carveouts Audited:** Continuous splash framebuffer (`0x9C000000`, 35 MiB), EDK II Firmware Volume (`0x9E400000`, 4 MiB), TrustZone/QSEE (`0x86000000`), Modem RF / MPSS.

### 2.4 `display.efi` (Graphics Output Protocol & Dual-Mode Console)
- **Primary Function:** Queries `EFI_GRAPHICS_OUTPUT_PROTOCOL` and `EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL`.
- **Display Parameters:**
  - Resolution: 1080 × 2400 pixels
  - Color Format: `PixelBlueGreenRedReserved8BitPerColor` (32-bpp BGRX)
  - Stride: 1080 pixels (4320 bytes/scanline)
  - Framebuffer Base: `0x9C000000`
  - Text Modes: Mode 0 (135×126, 1× standard glyphs) and Mode 1 (67×63, 2× readability glyphs).

### 2.5 `fdtinfo.efi` (Device Tree Blob)
- **Primary Function:** Inspects the flattened device tree (FDT) passed from the bootloader or registered in the EFI Configuration Table.
- **Validation:** Verifies FDT magic (`0xd00dfeed`), total size, version, root model (`"Samsung R8Q EUR PROJECT - R8 REV04"`), and compatible strings (`"samsung,r8q"`, `"qcom,kona"`, `"qcom,sm8250"`).

### 2.6 `storage.efi` (Storage Subsystems & Protection Audit)
- **Primary Function:** Locates all `EFI_BLOCK_IO_PROTOCOL` handles and verifies the Centralized Storage Protection Policy.
- **Hardware Verified:**
  - UFS 3.1 Host Controller at `0x01D84000` (Samsung KLUDG4UHDB-B2D1, LUNs 0-3).
  - SDHCI MicroSD Controller at `0x08804000`.
  - Synopsys DWC3 USB3 Controller at `0x0A600000`.
- **Policy Invariant:** Guarantees `Media->ReadOnly == TRUE` for all internal UFS LUNs.

### 2.7 `battery.efi` (Battery & Power Subsystem)
- **Primary Function:** Evaluates power subsystem hardware profile and reports battery status.
- **Hardware Architecture:**
  - Battery: 4500 mAh (Typical) Li-Ion, 3.85V nominal / 4.40V max.
  - PMICs: Qualcomm PM8150/PM8150B and Maxim Integrated MAX77705 companion PMIC (ModelGauge m5 fuel gauge).
- **Safety Policy:** Non-intrusive probe; dynamic SPMI/I2C fuel-gauge polling safely deferred to OS to prevent retail bus collisions.

### 2.8 `thermal.efi` (TSENS Subsystem)
- **Primary Function:** Verifies Qualcomm SM8250 TSENS v2 hardware register base (`0x01DF8000`) and 16 on-die thermal sensor diodes.
- **Sensors Covered:** 4 Silver CPU, 3 Gold CPU, 1 Gold+ CPU, 4 Adreno 650 GPU, DSP/NPU, Modem/DDR.
- **Safety Trip Points:** Reports emergency reset trip point (110.0°C) and frequency throttle trip point (85.0°C).

### 2.9 `firmware.efi` (Firmware Volume & NVRAM Audit)
- **Primary Function:** Inspects firmware volume allocation and audits Option A File-Backed NVRAM persistence.
- **NVRAM Audit:**
  - Path: `EFI/R8Q/VARS.BIN` on authorized external media.
  - Commit Protocol: Two-Phase Atomic Commit (`VARS.NEW` -> CRC32 -> `VARS.BAK` -> `VARS.BIN`).
  - Quarantine: `EFI/R8Q/VARS_CORRUPT.BIN`.
  - Invariant: Zero writes or access to internal partition `sdd31` (`uefivarstore`).

### 2.10 `diagnostics.efi` (Master Orchestrator)
- **Primary Function:** Automated master runner executing all 9 diagnostic modules in sequence, compiling results into a unified ANSI summary matrix, and returning global platform health status.

### 2.11 `ShellTest.efi` (Shell 2.2 Acceptance Test Suite)
- **Primary Function:** Automated verification of Milestone 5 acceptance invariants:
  - Test 1: HII Database protocol verification.
  - Test 2: Unicode Collation 2 protocol verification.
  - Test 3: Shell 2.2 Profile PCD configuration (`PcdShellSupportLevel=3`, `PcdShellProfileMask=0xFF`).
  - Test 4: 3-Second Startup countdown PCD (`PcdShellDefaultDelay=3`).
  - Test 5: Interactive console input protocols (`SimpleTextInput`).
  - Test 6: Centralized UFS storage protection invariant in Shell execution context.
