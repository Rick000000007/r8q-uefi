# Project R8Q UEFI: Hardware Initialization Dependency Graph

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. System Hardware Initialization Dependency Flow

The following graph illustrates the exact chain of hardware initialization from cold reset through operating-system handoff. It delineates which components are initialized by Qualcomm firmware, Samsung ABL, R8Q UEFI, and the booted operating system.

```mermaid
flowchart TD
    subgraph SoC_Reset ["SoC Cold Reset (PBL)"]
        ColdBoot["Power-on / Warm Reset"] --> PBL["Qualcomm Primary Boot Loader (ROM)"]
        PBL -->|Verify Fuses & Signature| LoadXBL["Read XBL from UFS LUN 1 (sdb1)"]
    end

    subgraph Early_Boot ["Early Platform Boot (XBL / AOP / TZ)"]
        LoadXBL --> XBL["Qualcomm eXtensible Boot Loader (XBL)"]
        XBL --> TrainDDR["Train LPDDR5 Memory Channels (8 GB Active)"]
        XBL --> InitClocks["Initialize Core Clock Trees (GCC / RPMh)"]
        XBL --> InitPMIC["Initialize PM8150/L/B Power Rails"]
        XBL --> LoadTZ["Load TrustZone (tz sdd5) -> EL3 Secure"]
        XBL --> LoadHYP["Load Hypervisor (hyp sdd35) -> EL2"]
        XBL --> LoadAOP["Load Always-On Processor (aop sdd7)"]
        XBL --> LoadABL["Load Samsung ABL (abl sdd8) into DRAM"]
    end

    subgraph Samsung_Stage ["Samsung Boot Stage (ABL)"]
        LoadABL --> ABL["Samsung Android Boot Loader (ABL)"]
        ABL --> InitDisplay["Init DPU (MDSS) & S6E3FC3 AMOLED Panel"]
        InitDisplay --> SetupSplash["Establish Continuous Splash Framebuffer @ 0x9C000000"]
        ABL --> InitUFS["Initialize UFS 3.1 Host Controller @ 0x01D84000"]
        ABL --> CheckKeys["Evaluate Hardware Keys (Vol-Down -> Odin Mode)"]
        ABL -->|Normal Boot Flow| VerifyBoot["Inspect boot.img header @ sda23"]
        VerifyBoot --> LoadPayload["Load Kernel Payload to DRAM @ 0x80008000"]
        LoadPayload --> HandoffUEFI["Jump to R8Q UEFI (AArch64 Non-Secure EL2/EL1)"]
    end

    subgraph R8Q_UEFI_Stage ["Project R8Q UEFI Platform Engine"]
        HandoffUEFI --> R8Q_SEC["R8Q SEC / Pre-Pi Entry Point"]
        R8Q_SEC --> SetupStack["Establish ARM64 Stack & Identity Page Tables"]
        SetupStack --> R8Q_DXE["DXE Core Dispatcher"]
        
        R8Q_DXE --> ArchTimer["ArmArchTimerLib (19.2 MHz Generic Timer)"]
        R8Q_DXE --> GICDriver["GICv3 Interrupt Protocol (0x17A00000)"]
        R8Q_DXE --> GOPDriver["R8Q Framebuffer GOP Driver (0x9C000000)"]
        R8Q_DXE --> UFSDriver["R8Q Block I/O Driver (UFS 3.1 / sda, sdd)"]
        R8Q_DXE --> SDDriver["R8Q SDHCI Driver (MicroSD @ 0x08804000)"]
        R8Q_DXE --> VariableService["R8Q NVRAM Variable Protocol (ESP File Store)"]
        R8Q_DXE --> USBDriver["Qualcomm DWC3 USB Host & HID Protocol"]
        
        GOPDriver --> ConOut["Simple Text Output Protocol (AMOLED Console)"]
        USBDriver --> ConIn["Simple Text Input Protocol (USB Keyboard / Buttons)"]
        
        ConOut --> R8Q_Shell["Interactive UEFI Shell (2.2 Specification)"]
        ConIn --> R8Q_Shell
        R8Q_Shell --> R8Q_Diag["R8Q Hardware Diagnostic Suite (19 Commands)"]
        R8Q_Shell --> MultiBoot["R8Q Multi-OS Boot Manager"]
    end

    subgraph OS_Targets ["Target Operating Systems"]
        MultiBoot -->|Boot Target 1| LinuxBoot["Native Linux Kernel (EFI Stub / Image)"]
        MultiBoot -->|Boot Target 2| WinBoot["Experimental Windows 11 ARM64 (ACPI)"]
        MultiBoot -->|Boot Target 3| RecoveryBoot["R8Q Linux Emergency Recovery"]
        
        LinuxBoot --> ExitBootServices1["ExitBootServices() -> Linux Swapper"]
        WinBoot --> ExitBootServices2["ExitBootServices() -> Windows BootMgr / winload.efi"]
    end
```

---

## 2. Hardware Resource Ownership Matrix

The following matrix categorizes all primary hardware subsystems, identifying which entity owns initialization and runtime management.

| Subsystem | Hardware Controller | Initialized By | Owned By (UEFI) | Handed Off To |
|---|---|---|---|---|
| **CPU Cores** | Kryo 585 (Cortex-A77 + A55) | PBL / XBL | Core 0 active; 1-7 idle | Linux / Windows SMP |
| **System RAM** | 8 GB LPDDR5 (4 channels) | XBL | R8Q UEFI Page Tables | OS Memory Manager |
| **Interrupts** | ARM GICv3 (`0x17A00000`) | XBL / ABL | R8Q GIC Driver | OS Interrupt Subsystem |
| **System Timer** | ARMv8 Arch Timer (19.2 MHz) | XBL | R8Q Timer Driver | OS Scheduler Timer |
| **Display Panel** | Samsung S6E3FC3 AMOLED | ABL | GOP (Continuous Splash) | DRM KMS / Win Display |
| **Display DPU** | Qualcomm MDSS (`0x0AE00000`) | ABL | Inherited (Scanout active) | DPU driver in OS |
| **UFS Storage** | Qualcomm UFSHC (`0x01D84000`) | ABL / XBL | R8Q Block I/O Driver | OS UFS SCSI stack |
| **MicroSD Slot** | Qualcomm SDHCI (`0x08804000`) | R8Q UEFI | R8Q SDHCI Driver | OS MMC/SD subsystem |
| **USB Controller** | Synopsys DWC3 (`0x0A600000`) | R8Q UEFI | R8Q XHCI Driver | OS USB 3.0 stack |
| **PMIC / Power** | PM8150, PM8150L, PM8150B | AOP / XBL | Telemetry via SPMI | OS PMIC driver |
| **Fuel Gauge** | MAX77705 / MAX17042 | ABL | Telemetry via I2C | OS Power Supply driver |
| **Hardware Keys** | Vol-Up/Down (`gpio-keys`), Power | ABL / PMIC | R8Q Key Handler | OS Input subsystem |
| **Touchscreen** | Samsung SEC TS (`0x49` on I2C-5) | R8Q UEFI | R8Q Touch Pointer Protocol | OS Evdev / HID |
| **PCIe Controllers**| 3 × PCIe Gen3 Root Ports | XBL (partial) | Optional discovery | OS PCIe Bus Driver |

---

## 3. Critical Pre-Conditions & Constraints

1. **Non-destructive Operation:** At no point does R8Q UEFI re-initialize DDR controllers or reset power management arbiters. Doing so while running from DRAM would result in immediate CPU brownout or crash.
2. **Display Continuity:** Display DPU clocks must remain untouched during UEFI execution to maintain frame buffer scanout without panel desynchronization.
3. **Interrupt Routing:** GICv3 redistributor configurations must ensure non-secure PPIs are routed to the active exception level without disturbing secure SGIs reserved for TrustZone.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
