# Project R8Q UEFI: EDK II Platform Design & Architecture

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Package Name:** `R8QPkg`  
**Base Framework:** EDK II (Pinned to `edk2-stable202408` / `edk2-stable202411`)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Package Directory Hierarchy

The platform package `R8QPkg` is structured in full compliance with the UEFI Platform Initialization (PI) and UEFI 2.10 specifications:

```
platform/R8QPkg/
├── R8QPkg.dec                      # Platform Package Declaration
├── R8QPkg.dsc                      # Platform Description / Build Rules
├── R8QPkg.fdf                      # Firmware Device / Flash Definition
├── Include/
│   ├── Configuration/
│   │   └── DeviceTree.h
│   ├── Library/
│   │   ├── R8QPlatformLib.h
│   │   └── SimpleFBLib.h
│   └── Protocol/
│       ├── R8QBattery.h
│       └── R8QThermal.h
├── Library/
│   ├── ArmPlatformLib/             # Pre-Pi memory mapping & core initialization
│   ├── FramebufferLib/             # Continuous splash framebuffer mapping
│   ├── PlatformPeiLib/             # Platform PEI initialization helpers
│   ├── SerialPortLib/              # Qualcomm QUP GENI UART driver
│   └── TimerLib/                   # Architectural timer library bindings
├── Drivers/
│   ├── ButtonDxe/                  # Physical volume keys input driver
│   ├── SimpleFbDxe/                # Continuous Splash Graphics Output Protocol
│   ├── BatteryDxe/                 # Fuel gauge / PMIC telemetry protocol
│   ├── ThermalDxe/                 # TSENS thermal monitoring protocol
│   └── TouchDxe/                   # SEC TS absolute pointer protocol
└── Applications/
    ├── Diagnostics/                # R8Q Hardware Inspector suite
    └── MultiBoot/                  # Multi-OS Boot Manager application
```

---

## 2. Firmware Layout & Memory Organization (FDF)

The firmware is assembled into a single relocatable Firmware Device (FD) binary image named `R8Q_EFI.fd`:

```
+-------------------------------------------------------------+ 0x00000000
| Pre-Pi / SEC Phase Entry Wrapper (64 KB)                    |
| - ABL Entry Interface (AArch64 register setup)              |
| - ARM64 Stack Establishment                                 |
| - Memory Detection & Page Table Mapping                     |
+-------------------------------------------------------------+ 0x00010000
| DXE Core & Foundation Drivers (384 KB)                      |
| - Memory Allocation Services                                |
| - Architectural Protocols (Timer, Interrupt, CPU)           |
+-------------------------------------------------------------+ 0x00070000
| Hardware Drivers FV (FVMAIN) (1536 KB)                      |
| - SimpleFbDxe (GOP Display)                                 |
| - ConSplitter & Graphics Console                            |
| - UfsDxe / PartitionDxe / FatDxe                            |
| - UsbBusDxe / XhciDxe / UsbKbDxe                            |
| - BatteryDxe / ThermalDxe / ButtonDxe                       |
+-------------------------------------------------------------+ 0x001F0000
| Shell & Diagnostic Applications FV (FVAPPS) (2048 KB)       |
| - Full UEFI Shell 2.2 Binary                                |
| - 19 R8Q Diagnostic Commands Suite                          |
| - Multi-OS Boot Manager Application                         |
+-------------------------------------------------------------+ 0x003F0000 (Total ~4 MB FD)
```

### 2.1 Memory Execution Regions
- **FD Load Base:** `0x9E400000` (safe region above continuous splash and below secure carveouts)
- **Primary Stack Base:** `0x9E3F0000` (Top of FD, descending 64 KB)
- **Early Heap Base:** `0x9E3B0000` (64 KB early heap for Pre-Pi)
- **DXE System Memory Range:** Dynamically claimed from `0xA0002000` to `0xB0000000` (255 MiB pool)

---

## 3. Platform Configuration Database (PCD) Architecture

Platform parameters are defined using EDK II PCDs in `R8QPkg.dsc`:

```ini
[PcdsFixedAtBuild.common]
  # System Architecture & Cores
  gArmTokenSpaceGuid.PcdArmArchTimerFreqInHz|19200000
  gArmTokenSpaceGuid.PcdGicDistributorBase|0x17A00000
  gArmTokenSpaceGuid.PcdGicRedistributorsBase|0x17A60000
  gArmTokenSpaceGuid.PcdArmPrimaryCore|0x00000000

  # Display Framebuffer Configuration
  gR8QPkgTokenSpaceGuid.PcdFrameBufferBase|0x9C000000
  gR8QPkgTokenSpaceGuid.PcdFrameBufferSize|0x02300000
  gR8QPkgTokenSpaceGuid.PcdDisplayWidth|1080
  gR8QPkgTokenSpaceGuid.PcdDisplayHeight|2400
  gR8QPkgTokenSpaceGuid.PcdDisplayBpp|32

  # Serial Debug Console (QUP GENI UART)
  gR8QPkgTokenSpaceGuid.PcdUartBaseAddress|0x00988000
  gR8QPkgTokenSpaceGuid.PcdUartBaudRate|115200

  # Storage Controllers
  gR8QPkgTokenSpaceGuid.PcdUfsHostControllerBase|0x01D84000
  gR8QPkgTokenSpaceGuid.PcdSdhciControllerBase|0x08804000
```

---

## 4. Boot Execution Phases

### 4.1 SEC / Pre-Pi Phase
1. Invoked by ABL at entry address with Device Tree pointer in `x0`.
2. Preserves `x0` and command line arguments.
3. Configures ARMv8 architectural system registers:
   - Sets `CPACR_EL1.FPEN = 0b11` to enable full access to FP/SIMD registers.
   - Clears pending interrupts in GIC.
4. Initializes page tables with flat 1:1 mapping:
   - DRAM (`0x80000000`–`0x27FFFFFFF`): Normal, Inner/Outer Write-Back, Non-Shareable.
   - Peripherals / MMIO (`0x00000000`–`0x7FFFFFFF`): Device-nGnRnE.
   - Continuous Splash (`0x9C000000`–`0x9E300000`): Normal Memory, Write-Combining.
5. Enables MMU and data/instruction caches.
6. Transfers control to DXE Foundation Entry Point.

### 4.2 DXE Phase (Driver Execution Environment)
1. DXE Core initializes memory management, event timers, and protocol databases.
2. Dispatches architectural protocol drivers: CPU, Timer, GIC Interrupt.
3. Loads R8Q SimpleFbDxe to provide instant visual feedback on AMOLED display.
4. Dispatches storage drivers (UFS, SDHCI, PartitionDxe, FatPkg).
5. Dispatches USB host stack and keyboard/mouse drivers.
6. Dispatches R8Q custom telemetry drivers (Battery, Thermal, Physical Buttons).

### 4.3 BDS Phase (Boot Device Selection)
1. Dispatches UEFI Boot Manager.
2. If automatic boot timeout expires or user interrupts:
   - Launches interactive UEFI Shell or R8Q Multi-OS Boot Menu.
3. Loads selected OS bootloader (`EFI/BOOT/BOOTAA64.EFI` or Linux `Image`).

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
