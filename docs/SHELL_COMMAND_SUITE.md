# Project R8Q UEFI: Shell Command Suite & Scripting Architecture

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Interactive UEFI Shell Specification

Project R8Q UEFI incorporates a complete, standards-compliant ARM64 UEFI Shell compliant with the UEFI Shell Specification v2.2. The Shell is launched as the central administrative and diagnostic environment of the firmware, accessible via the AMOLED display and a connected USB-C keyboard or physical volume keys.

---

## 2. R8Q Custom Diagnostic Command Suite

In accordance with Section 5.2 of the Master Specification, nineteen original diagnostic commands are engineered specifically for the SM8250 / r8q platform. Every command gathers verified real-time hardware telemetry from available UEFI protocols, SMEM tables, or memory-mapped hardware registers.

### 2.1 Complete Diagnostic Command Specifications

| Command | Category | Source Interface | Functionality & Real Telemetry Provided |
|---|---|---|---|
| `sysinfo` | System | R8Q Platform / SMEM | Reports Device Model, Board ID (Rev04), SoC ID (356), Serial Number, Memory Total (8 GB), Firmware Build Version, Boot Mode. |
| `cpuinfo` | Processor | ARM64 Regs / MPIDR | Details 8-core Kryo 585 topology: 4x Silver (Cortex-A55 @ 1.8GHz), 3x Gold (Cortex-A77 @ 2.42GHz), 1x Prime (Cortex-A77 @ 2.84GHz), Arch Timer (19.2MHz). |
| `memmap` | Memory | UEFI Boot Services | Queries `GetMemoryMap()`; prints active memory descriptors, total usable DRAM (7.4 GiB), reserved regions, and page allocations. |
| `storage` | Storage | Block I/O Protocol | Discovers and details UFS 3.1 host controller, LUNs (sda, sdb, sdc, sdd), block sizes, and MicroSD card status. |
| `partitions` | Storage | Disk I/O / GPT | Enumerates all GPT partition tables across UFS and MicroSD; prints partition names, GUIDs, starting LBAs, and capacities in MiB/GiB. |
| `display` | Video | GOP Protocol | Reports active display panel model (`S6E3FC3`), resolution (1080×2400), refresh rate mode (60/120Hz), color format (BGRX 32bpp), and framebuffer address (`0x9C000000`). |
| `gpuinfo` | Graphics | SoC HW ID / DPU | Identifies Adreno 650 GPU ID, revision, frequency limits, and Qualcomm DPU MDP version (`0x0AE00000`). |
| `battery` | Power | R8Q Battery Protocol | Reads MAX77705 / Fuel Gauge: real-time battery percentage, terminal voltage (uV), charge/discharge current (uA), and health state. |
| `powerinfo` | Power | PMIC / SPMI | Queries PM8150, PM8150L, PM8150B status, active voltage regulators, USB-C VBUS status, and wireless charger detection. |
| `thermal` | Sensors | R8Q Thermal Protocol | Polls Qualcomm TSENS sensors across SoC; displays real-time temperatures for CPU clusters, GPU, modem, and battery in °C. |
| `dtbinfo` | Firmware | Device Tree Table | Inspects device tree loaded in memory: root model string, compatible properties, node count, and reserved-memory nodes. |
| `firmware` | System | UEFI System Table | Displays EFI System Table pointers, UEFI Specification version (2.10), Firmware Vendor (`Antigravity R8Q`), and Firmware Revision. |
| `pcieinfo` | Bus | PCI Root Bridge | Enumerates PCIe controllers (PCIe Gen3 x1/x2 ports at `0x01C00000`); identifies connected endpoints (e.g., QCA6390 Wi-Fi). |
| `usbinfo` | Bus | XHCI Protocol | Inspects Qualcomm DWC3 USB controller (`0x0A600000`), port link states (USB 2.0 / 3.0), connected hubs, keyboards, and mice. |
| `inputinfo` | Input | Pointer / Text Protocols | Tests and reports status of physical buttons (`gpio-keys`), power key (`qpnp_pon`), and Samsung SEC touchscreen (`0x49` on I2C-5). |
| `bootmenu` | Boot | Boot Manager App | Launches the interactive multi-OS graphical/text boot selection menu. |
| `bootlog` | Diagnostic | R8Q Logger | Dumps internal firmware boot log, driver dispatch sequence, and initialization warnings to console or file. |
| `diagnostics`| Comprehensive | R8Q Inspector | Executes full automated hardware audit and outputs structured report (display, memory, storage, battery, thermals). |
| `recovery` | System | Boot Services | Enters the R8Q emergency recovery environment or initiates warm reboot to Samsung Odin Download Mode / Android Recovery. |

---

## 3. Shell Automation Scripts (.nsh)

Standard automation scripts are integrated directly into the firmware image in `FVAPPS` and mirrored on the EFI System Partition:

1. **`startup.nsh`**: Primary firmware startup sequence:
   - Initializes environment variables.
   - Probes for auto-boot timeout (3 seconds).
   - If not interrupted by user keypress, executes `boot-linux.nsh` or last-known-good boot entry.
2. **`hardware-audit.nsh`**: Executes a sequential hardware verification suite (`sysinfo`, `cpuinfo`, `memmap`, `storage`, `battery`, `thermal`) and exports the complete audit report to `fs0:\EFI\R8Q\audit-report.txt`.
3. **`storage-audit.nsh`**: Inspects UFS LUNs and MicroSD partitions, verifying filesystem integrity and partition boundary alignments.
4. **`boot-linux.nsh`**: Loads native Linux kernel `Image`, locates Device Tree Blob, validates initramfs, and executes kernel handoff.
5. **`boot-recovery.nsh`**: Boots into the isolated Linux emergency recovery image.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
