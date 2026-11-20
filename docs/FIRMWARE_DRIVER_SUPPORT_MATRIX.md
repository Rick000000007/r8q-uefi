# Project R8Q UEFI: Firmware Driver Support Matrix

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Overview & Prioritization Strategy

In accordance with Section 4.3 of the Master Engineering Specification, firmware drivers are developed as independent, modular UEFI DXE drivers. Components are prioritized according to boot-critical dependencies:
1. Memory and timer services
2. Display and console output (GOP / Simple Text Output)
3. UFS storage and partition discovery
4. MicroSD storage support
5. USB keyboard, mouse, and mass storage (XHCI)
6. Input devices (touchscreen and physical buttons)
7. PCIe bus enumeration
8. Battery, PMIC, and thermal telemetry
9. Hardware diagnostics and configuration protocols

---

## 2. Comprehensive Driver Support Matrix

| Hardware Block | Physical Base Address / Interface | Driver Component | Supported UEFI Protocols | Milestone | Status / Strategy |
|---|---|---|---|---|---|
| **CPU Architecture** | ARMv8.2-A (Kryo 585) | `ArmPkg/CpuDxe` | `EFI_CPU_ARCH_PROTOCOL` | M2 | Base EDK II; Core 0 init, MMU 4KB granularity |
| **System Timer** | ARM Generic Timer (19.2 MHz) | `ArmPkg/TimerDxe` | `EFI_TIMER_ARCH_PROTOCOL` | M2 | Direct architectural register access (`CNTFRQ_EL0`) |
| **Interrupt Controller** | GICv3 (`0x17A00000`, `0x17A60000`) | `ArmPkg/ArmGicDxe` | `EFI_HARDWARE_INTERRUPT_PROTOCOL` | M2 | GICD/GICR mapping; PPI timer handling |
| **Display Framebuffer** | `0x9C000000` (35 MiB contiguous) | `R8QPkg/SimpleFbDxe` | `EFI_GRAPHICS_OUTPUT_PROTOCOL` | M3 | Zero-risk continuous splash GOP; 1080×2400 @ 32bpp |
| **Text Console Out** | Display via GOP Font Renderer | `MdeModulePkg/ConSplitterDxe` | `EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL` | M3 | 8×19 glyph rendering; 135 cols × 126 rows |
| **Serial Debug UART** | QUP GENI UART (`0x00988000`) | `R8QPkg/SerialPortLib` | `EFI_SERIAL_IO_PROTOCOL` | M3 | Optional hardware debug stream (115200 8N1) |
| **UFS 3.1 Host** | Qualcomm UFSHC (`0x01D84000`) | `R8QPkg/UfsDxe` | `EFI_BLOCK_IO_PROTOCOL`, `EFI_DISK_IO_PROTOCOL` | M4 | Host controller read/write; LUN 0/1/2/3 discovery |
| **Partition Engine** | GPT / MBR on UFS & SD | `MdeModulePkg/PartitionDxe` | `EFI_BLOCK_IO_PROTOCOL` (Partition Child) | M4 | Enumerates all 36 partitions on LUN 0, 37 on LUN 3 |
| **Filesystems** | FAT12 / FAT16 / FAT32 | `FatPkg/EnhancedFatDxe` | `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL` | M4 | Reads ESP, boot directories, and script files |
| **MicroSD Host** | Qualcomm SDHCI (`0x08804000`) | `R8QPkg/SdMmcDxe` | `EFI_BLOCK_IO_PROTOCOL`, `EFI_DISK_IO_PROTOCOL` | M4 | SD 3.0 / UHS-I support; hotplug detection |
| **USB 3.0 XHCI Host** | Synopsys DWC3 (`0x0A600000`) | `R8QPkg/XhciDxe` | `EFI_USB2_HC_PROTOCOL` | M5 | Powers USB-C OTG; supports external hubs |
| **USB Keyboard / Mouse**| Standard USB HID over XHCI | `MdeModulePkg/UsbKbDxe`, `UsbMouseDxe`| `EFI_SIMPLE_TEXT_INPUT_PROTOCOL` | M5 | Enables interactive navigation in Shell & Menus |
| **Hardware Buttons** | Volume Up/Down (`gpio-keys`) | `R8QPkg/ButtonDxe` | `EFI_SIMPLE_TEXT_INPUT_PROTOCOL` | M5 | Key up/down mapped to EFI cursor up/down/enter |
| **Touchscreen** | Samsung SEC TS (`0x49` on I2C-5) | `R8QPkg/TouchDxe` | `EFI_ABSOLUTE_POINTER_PROTOCOL` | M10 | Multi-touch point tracking mapped to screen coords |
| **Battery & Charging** | MAX77705 / MAX17042 / PCA9468 | `R8QPkg/BatteryDxe` | `R8Q_BATTERY_STATUS_PROTOCOL` | M6 | Voltage, capacity, current, and charging status |
| **Thermal Telemetry** | Qualcomm TSENS (16 sensors) | `R8QPkg/ThermalDxe` | `R8Q_THERMAL_PROTOCOL` | M6 | Reads CPU gold/silver, GPU, and battery temperatures |
| **Device Tree Handoff** | Memory address passed by ABL | `R8QPkg/FdtDxe` | `EFI_DEVICE_TREE_PROTOCOL`, Config Table | M7 | Updates memory reservations, passes to Linux OS |
| **ACPI Subsystem** | Independent DSDT/SSDT Tables | `R8QPkg/AcpiPlatformDxe`| `EFI_ACPI_TABLE_PROTOCOL` | M9 | Supplies ACPI 6.3 tables for Windows ARM64 boot |
| **PCIe Host Bridge** | 3 × PCIe Gen3 (`0x01C00000`+) | `R8QPkg/PciHostBridgeDxe`| `EFI_PCI_ROOT_BRIDGE_IO_PROTOCOL` | M11 | Root bridge discovery for Wi-Fi (QCA6390) |

---

## 3. Protocol Architecture Specifications

### 3.1 Framebuffer Graphics Output Protocol (GOP)
```c
typedef struct {
    UINT32 MaxMode;
    UINT32 Mode;
    EFI_GRAPHICS_OUTPUT_MODE_INFORMATION *Info;
    UINTN SizeOfInfo;
    EFI_PHYSICAL_ADDRESS FrameBufferBase;
    UINTN FrameBufferSize;
} EFI_GRAPHICS_OUTPUT_PROTOCOL_MODE;
```
For R8Q UEFI:
- `FrameBufferBase = 0x9C000000`
- `FrameBufferSize = 1080 * 2400 * 4 = 10,368,000 bytes` (0x9E3400 max envelope: 35 MiB)
- `HorizontalResolution = 1080`
- `VerticalResolution = 2400`
- `PixelFormat = PixelBlueGreenRedReserved8BitPerColor` (or BGRX)
- `PixelsPerScanLine = 1080`

### 3.2 Diagnostic Telemetry Protocol Interfaces
Original custom protocols engineered for R8Q diagnostics:
1. `R8Q_BATTERY_PROTOCOL_GUID`: `{0xa482e811, 0x1812, 0x4f1b, {0x89, 0xc1, 0x90, 0x42, 0x77, 0x70, 0x51, 0x01}}`
   Provides `GetBatteryState(&Voltage, &Current, &Capacity, &Temperature, &IsCharging)`.
2. `R8Q_THERMAL_PROTOCOL_GUID`: `{0xb593f922, 0x2923, 0x4e2c, {0x9a, 0xd2, 0x01, 0x53, 0x88, 0x81, 0x62, 0x02}}`
   Provides `GetSensorCount(&Count)`, `GetSensorTemp(Index, &TempMilliC, &Name)`.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
