# Project R8Q UEFI: Windows ARM64 & ACPI Compatibility Report

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Executive Summary: Windows ARM64 Feasibility

Windows on ARM (WoA / Windows 11 ARM64) is an experimental secondary target for Project R8Q UEFI. Unlike Linux, which primarily uses Device Tree (FDT), Windows ARM64 exclusively requires standard Advanced Configuration and Power Interface (ACPI 6.0+) tables, specific UEFI runtime services, and Qualcomm Power Engine Plugin (PEP) drivers.

---

## 2. Six-Level Windows Support Classification

In strict adherence to Section 10 of the Master Engineering Specification, Windows compatibility is classified across six distinct, independently verifiable tiers:

| Tier | Classification Level | Status | Requirements & Verification Gates |
|---|---|---|---|
| **Level 1** | **UEFI-Compatible** | **ACHIEVED** | Standards-compliant ARM64 UEFI environment; standard memory map, runtime services stubs, EFI system table, virtual memory mapping (`SetVirtualAddressMap`). |
| **Level 2** | **Windows PE Bootable** | **IN DESIGN (M9)** | ACPI 6.3 tables (FADT, MADT, DSDT, GTDT, DBG2, PPTT); boot-critical UFS 3.1 storage driver (`storufs.sys` / Qualcomm StorSec), Windows Boot Manager (`bootmgfw.efi`) loads WinPE kernel (`ntoskrnl.exe`). |
| **Level 3** | **Installer-Compatible** | **ROADMAP (M9-M11)** | USB host controller (XHCI) ACPI description; USB keyboard/mouse operational; basic display (MSBDD / Microsoft Basic Display Driver over GOP) functional for Windows Setup GUI. |
| **Level 4** | **Desktop-Bootable** | **ROADMAP (M11)** | Windows 11 ARM64 boots to desktop environment; internal UFS partitions accessible; power management PEP coordinates core sleep states. |
| **Level 5** | **Hardware-Accelerated** | **EXPERIMENTAL** | Qualcomm Adreno 650 DirectX 12 driver loaded; hardware video decode active; native DPU display pipeline enabled. |
| **Level 6** | **Daily-Use Capable** | **EXPERIMENTAL** | Touchscreen (I2C HID), audio, QCA6390 Wi-Fi/Bluetooth, battery charging, and telephony operational. |

---

## 3. Required ACPI Platform Description Architecture

To support Windows ARM64 boot, R8Q UEFI generates and publishes the following ACPI tables:

1. **MADT (Multiple APIC Description Table):**
   - Describes ARM GICv3 Distributor @ `0x17A00000`.
   - Describes GIC Redistributor Base @ `0x17A60000` with 8 GICR entries (Cores 0 through 7).
2. **GTDT (Generic Timer Description Table):**
   - Generic Timer physical base frequency: 19,200,000 Hz.
   - Non-secure EL1 timer interrupt: PPI 30 (INTID 14).
   - Virtual EL1 timer interrupt: PPI 27 (INTID 11).
3. **FADT (Fixed ACPI Description Table):**
   - Declares hardware-reduced ACPI (`HW_REDUCED_ACPI = 1`).
   - Feature flags: 64-bit boot architecture, low-power S0 idle state support.
4. **DSDT (Differentiated System Description Table):**
   - Device `\_SB.CPU0` through `\_SB.CPU7` with ARM processor container.
   - Device `\_SB.UFS0`: Qualcomm SM8250 UFS host controller (`QCOM0484` / `QCOM0542`) @ `0x01D84000`.
   - Device `\_SB.USB0`: Synopsys DWC3 USB 3.0 controller @ `0x0A600000`.
   - Device `\_SB.PEP0`: Qualcomm Power Engine Plugin (`QCOM0242` / `QCOM0585`).
   - Device `\_SB.GOP0`: Display engine frame buffer description (`0x9C000000`).
5. **DBG2 (Debug Port Table 2):**
   - Qualcomm GENI Serial port @ `0x00988000` for kernel debugging (`kdnet` / serial kd).
6. **PPTT (Processor Properties Topology Table):**
   - Describes 8-core CPU cluster hierarchy (Silver cluster, Gold cluster, Prime core) and L1/L2/L3 cache topology.

---

## 4. Boot-Critical Driver Dependencies & Mitigations

1. **UFS Storage:** Windows ARM64 requires a compatible storage miniport driver to access UFS partitions. On SM8250, the Qualcomm UFS driver relies on secure RPMB calls routed through `uefisecapp` (`sdd27`) in TrustZone. R8Q UEFI preserves all TrustZone SMC interfaces.
2. **Display:** Prior to the installation of Qualcomm Adreno/DPU drivers, Windows uses the Microsoft Basic Display Driver (MSBDD), which renders directly onto the UEFI GOP framebuffer established at `0x9C000000`.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
