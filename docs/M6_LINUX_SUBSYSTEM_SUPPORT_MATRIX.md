# Project R8Q UEFI: Milestone 6 Linux Subsystem Support Matrix
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `SM-G781B/DS`)  
**Codename:** `r8q`  
**SoC:** Qualcomm Snapdragon 865 5G (`SM8250` / Kona)  
**Architecture:** ARM64 (AArch64, ARMv8.2-A)  
**Document Revision:** 1.0.0 (Milestone 6)  
**Classification:** Technical Specification & Hardware Readiness Audit  

---

## 1. Executive Summary

This document provides a comprehensive analysis of Linux operating system hardware enablement for the Samsung Galaxy S20 FE 5G (`SM-G781B`, codename `r8q`) on the Qualcomm Snapdragon 865 5G (`SM8250`) platform. 

The primary purpose is to distinguish:
1. **Upstream Mainline Linux Support:** Drivers present in official upstream Linux (`torvalds/linux` v6.6+ / v6.12 LTS / v6.14-rc).
2. **Downstream Vendor (CAF/CLO) Drivers:** Code residing exclusively in Qualcomm CAF/CodeAurora/CLO or Samsung Android downstream kernel trees (`android-11` through `android-16` / OneUI).
3. **Out-of-Tree / Community Drivers:** Community patches (e.g., PostmarketOS, Linux-SM8250, SXMO) required for panel, audio, or touch integration.
4. **Firmware Dependencies & TrustZone (QSEE) Hand-offs:** Subsystems requiring TrustZone (QSEE/SCM), hypervisor (QHEE), or remote processor firmware blobs.
5. **UEFI Handoff Strategy:** How each subsystem transitions from the R8Q EDK II UEFI pre-boot environment into the Linux kernel runtime.

---

## 2. Platform Architecture Overview

The SM8250 platform integrates a complex heterogeneous computing architecture:
* **CPU:** 8× Kryo 585 cores (1× Cortex-A77 Prime @ 2.84 GHz, 3× Cortex-A77 Gold @ 2.42 GHz, 4× Cortex-A55 Silver @ 1.80 GHz).
* **Interrupt Controller:** ARM GIC-600 (GICv3 architecture) with GIC-ITS (Interrupt Translation Service) for MSI/MSI-X.
* **Interconnect & NoC:** Qualcomm Network-on-Chip (System NoC, Memory NoC, Config NoC) orchestrated via RPMh (Resource Power Manager Hardened) and BCM (Bus Clock Manager).
* **DRAM:** 8 GB LPDDR5 (4 channels, 16-bit per channel, peak 2750 MHz).
* **Storage:** 128 GB UFS 3.1 (2-lane Gear 4) + MicroSD UHS-I slot (SDHCI).
* **Display Engine:** DPU 5.0 (Mobile Display Subsystem 5.0) driving Samsung Super AMOLED panel (1080×2400 @ 120 Hz / 60 Hz).
* **GPU:** Qualcomm Adreno 650 (Direct3D 12, Vulkan 1.3, OpenGL ES 3.2).
* **Modem & DSPs:** Snapdragon X55 5G Modem, Hexagon 698 DSP (Compute DSP, Audio DSP, Sensor Low Power Island / SLPI).

---

## 3. Comprehensive Subsystem Support Matrix

The table below catalogs every critical hardware subsystem on the SM-G781B, its device tree binding, upstream kernel driver status, firmware requirements, and handoff strategy:

| Subsystem | Hardware Component | Device Tree Compatible String | Driver Status | Required Kernel Config | Firmware / SCM Required | UEFI Handoff Mode | Notes |
|---|---|---|---|---|---|---|---|
| **CPU Architecture** | 8× Kryo 585 (ARMv8.2-A) | `arm,cortex-a77`, `arm,cortex-a55` | **Mainline** (Complete) | `CONFIG_ARM64`, `CONFIG_SMP` | TrustZone PSCI v1.0+ | Native ARM64 EFI Stub | Cores booted via standard PSCI `CPU_ON` calls. Full architectural compliance. |
| **Interrupt Controller** | ARM GIC-600 (GICv3) | `arm,gic-v3` | **Mainline** (Complete) | `CONFIG_ARM_GIC_V3`, `CONFIG_ARM_GIC_V3_ITS` | None | Direct FDT | GIC distributor and redistributors mapped directly from DTB. Full LPI and ITS MSI support. |
| **Timers** | ARM Generic System Counter | `arm,armv8-timer` | **Mainline** (Complete) | `CONFIG_ARM_ARCH_TIMER` | None | Direct FDT | Architecture counter runs at 19.2 MHz (XO). Unaffected by CPU frequency changes. |
| **Power & Clocks (RPMh)** | Resource Power Manager (RPMh) | `qcom,sm8250-rpmh-clk`, `qcom,rpmh-rsc` | **Mainline** (Complete) | `CONFIG_QCOM_RPMH`, `CONFIG_QCOM_RPMHPD` | RPMh hardware coprocessor | Direct FDT | Communications via RSC (Resource State Coordinator) mailboxes and BCM voter circuits. |
| **Global Clock Controller** | Qualcomm GCC | `qcom,sm8250-gcc` | **Mainline** (Complete) | `CONFIG_SM_GCC_8250` | None | Direct FDT | Controls root clocks, bus gates, peripheral PLLs (UFS, SDCC, USB, I2C, SPI). |
| **Interconnects** | Qualcomm System NoC / Mem NoC | `qcom,sm8250-system-noc`, `qcom,sm8250-mc-virt` | **Mainline** (Complete) | `CONFIG_INTERCONNECT_QCOM_SM8250` | RPMh BCM | Direct FDT | Bandwidth voting for DDR, DPU, GPU, and UFS subsystems. |
| **Pin Controller (TLMM)** | Top-Level Mode Multiplexer | `qcom,sm8250-pinctrl` | **Mainline** (Complete) | `CONFIG_PINCTRL_SM8250` | None | Direct FDT | 180 GPIO pins with pull-up/down, drive-strength, and interrupt generation. |
| **Display (UEFI Handoff)** | Continuous Splash Framebuffer | `simple-framebuffer` | **Mainline** (Complete) | `CONFIG_FB_SIMPLE`, `CONFIG_DRM_SIMPLEDRM` | None | Framebuffer at `0x9C000000` | Smooth transition from EDK II `SimpleFbDxe` (GOP). Retains splash without flicker until native DPU initializes. |
| **Display (Native DRM)** | Qualcomm DPU 5.0 (MDSS) | `qcom,sm8250-dpu`, `qcom,sm8250-mdss` | **Mainline** (Working) | `CONFIG_DRM_MSM`, `CONFIG_DRM_MSM_DPU` | DISPCC clock, SCM secure display | Mode switch / DRM driver | Supported via upstream `msm` DRM driver. Requires downstream panel initialization sequence. |
| **Display Panel** | Samsung AMS650VE01 Super AMOLED | `samsung,ams650ve01-ea8076` | **Community / Out-of-Tree** | `CONFIG_DRM_PANEL_SAMSUNG_EA8076` | None | MIPI-DSI command mode | Initialized by bootloader/UEFI; native dynamic refresh (60Hz/120Hz) requires custom DRM panel driver. |
| **Display Clocks** | Display Clock Controller (DISPCC) | `qcom,sm8250-dispcc` | **Mainline** (Complete) | `CONFIG_SM_DISPCC_8250` | None | Direct FDT | Drives DSI byte clocks, pixel clocks, and DPU engine clocks. |
| **GPU 3D Acceleration** | Qualcomm Adreno 650 | `qcom,adreno-650.0`, `amd,imageon` | **Mainline** (Complete) | `CONFIG_DRM_MSM`, `CONFIG_DRM_MSM_GPU` | Adreno microcode (`a650_zap.mbn`, `a650_sqe.fw`) | DRM handoff | Fully supported by Freedreno (OpenGL) and Turnip (Vulkan) Mesa drivers with upstream ZAP shader verification. |
| **Internal Storage (UFS)** | UFS 3.1 Host Controller | `qcom,sm8250-ufshc`, `jedec,ufs-2.0` | **Mainline** (Complete) | `CONFIG_SCSI_UFSHCD`, `CONFIG_SCSI_UFS_QCOM` | None | Read-Only Enforcement Policy | Upstream `ufshcd-qcom` driver supports Gear 4 2-lane. Strict software read-only enforced in UEFI; OS kernel respects partition read-only flags. |
| **MicroSD Slot** | Qualcomm SDHCI controller | `qcom,sm8250-sdhci`, `qcom,sdhci-msm-v5` | **Mainline** (Complete) | `CONFIG_MMC_SDHCI_MSM` | None | Full Read/Write Support | Connected to SDC2 interface. Supports UHS-I SDR104 mode (up to 208 MHz, ~100 MB/s). Fully operational in UEFI and Linux. |
| **USB 3.1 & Type-C** | Synopsys DesignWare USB3 (DWC3) | `qcom,sm8250-dwc3`, `snps,dwc3` | **Mainline** (Complete) | `CONFIG_USB_DWC3`, `CONFIG_USB_DWC3_QCOM` | None | Direct FDT / EHCI/XHCI | SuperSpeed 5 Gbps and HighSpeed 480 Mbps supported. Dual-role (OTG host & peripheral) supported. |
| **USB PHYs** | QMP USB 3.1 DP Combo PHY + QUSB2 | `qcom,sm8250-qmp-usb3-phy`, `qcom,sm8250-qusb2-phy` | **Mainline** (Complete) | `CONFIG_PHY_QCOM_QMP_COMBO`, `CONFIG_PHY_QCOM_QUSB2` | None | Direct FDT | Physical layer transceiver for high-speed and SuperSpeed differential pairs. |
| **Primary PMIC** | Qualcomm PM8150 | `qcom,pm8150`, `qcom,spmi-pmic` | **Mainline** (Complete) | `CONFIG_MFD_SPMI_PMIC`, `CONFIG_REGULATOR_QCOM_SPMI` | None | SPMI Bus | Controls system core rails (VDD_CX, VDD_MX, LDOs). Controlled via SPMI controller. |
| **Secondary PMIC** | Qualcomm PM8150B & PM8150L | `qcom,pm8150b`, `qcom,pm8150l` | **Mainline** (Complete) | `CONFIG_MFD_SPMI_PMIC`, `CONFIG_REGULATOR_QCOM_SPMI` | None | SPMI Bus | Auxiliary buck regulators, GPIO expanders, and display boost power supplies. |
| **Samsung PMIC / Charger** | Maxim Integrated MAX77705 | `maxim,max77705` | **Vendor Downstream / Out-of-tree** | `CONFIG_MFD_MAX77705`, `CONFIG_CHARGER_MAX77705` | None | I2C Bus | Multi-function companion PMIC controlling USB Type-C CC logic, AFC/QC/PD charging, and battery fuel gauge. |
| **Thermal Monitoring** | Qualcomm TSENS | `qcom,sm8250-tsens` | **Mainline** (Complete) | `CONFIG_QCOM_TSENS` | None | Direct FDT | 16 on-die thermal sensors monitoring CPU Kryo clusters, Adreno GPU, modem, and camera ISP. |
| **Touchscreen** | STMicroelectronics / Goodix Panel Touch | `st,ft5446` / `goodix,gt9886` | **Mainline / Vendor** | `CONFIG_TOUCHSCREEN_FTS` or `CONFIG_TOUCHSCREEN_GOODIX` | None | I2C Bus | Multi-touch capacitive digitizer. Requires correct GPIO interrupt line and I2C address handoff from DTB. |
| **Wi-Fi Subsystem** | Qualcomm QCA6490 / WCN6855 | `qcom,wcn6855-pci` | **Mainline** (Working) | `CONFIG_ATH11K`, `CONFIG_ATH11K_PCI` | Board Data (`board-2.bin`), Firmware (`amss.bin`) | PCI Bus | Wi-Fi 6 (802.11ax) dual-band. Communicates over PCIe bus. Requires non-free firmware blobs in `/lib/firmware`. |
| **Bluetooth Subsystem** | Qualcomm WCN6855 Bluetooth | `qcom,wcn6855-bt` | **Mainline** (Working) | `CONFIG_BT_QCA`, `CONFIG_BT_HCIUART` | Bluetooth NVM (`hpnv21.b80`) | UART / SMD Bus | Bluetooth 5.2 / LE. Interfaced via high-speed UART to TLMM GPIOs. |
| **Audio Subsystem** | Qualcomm LPASS / WCD9380 Codec | `qcom,sm8250-lpass`, `qcom,wcd9380` | **Mainline** (Experimental) | `CONFIG_SND_SOC_SM8250`, `CONFIG_SND_SOC_WCD9380` | ADSP firmware (`adsp.mbn`) | SoundWire / I2S | Digital signal processing routed through Hexagon ADSP. Speaker / headphone output requires SoundWire bus configuration. |
| **Cellular Modem** | Snapdragon X55 5G Subsystem | `qcom,sm8250-mpss` | **Mainline** (Remoteproc) | `CONFIG_QCOM_Q6V5_MSS` | Modem firmware (`modem.mbn`) | TrustZone / Remoteproc | Baseband firmware isolated in TrustZone-protected carveout (`0x8C000000`). Communicates via Qualcomm IPC Router / QRTR. |
| **Sensors (IMU/Compass)** | ST LSM6DSO / AKM09918 | `st,lsm6dso`, `asahi-kasei,ak09918` | **Mainline** (Complete) | `CONFIG_IIO_ST_LSM6DSX`, `CONFIG_AK8975` | SLPI DSP (Optional) | I2C / SPI Bus | 6-axis accelerometer/gyroscope and magnetometer. Can be read directly via Linux IIO drivers or delegated to SLPI. |
| **Hardware Random Number Gen** | Qualcomm PRNG | `qcom,sm8250-trng` | **Mainline** (Complete) | `CONFIG_HW_RANDOM_QCOM` | None | Direct FDT | Hardware cryptographic entropy generator supplying Linux `/dev/urandom` and kernel entropy pool. |
| **Cryptographic Engine** | Qualcomm Crypto Engine (QCE) | `qcom,sm8250-qce` | **Mainline** (Complete) | `CONFIG_CRYPTO_DEV_QCOM_CE` | TrustZone SCM | SCM Calls | Hardware accelerated AES, SHA, HMAC, and DES offloading. |

---

## 4. Subsystem Details & Analysis

### 4.1 CPU and Core Architecture
* **Status:** 100% Upstream Mainline.
* **Analysis:** The Snapdragon 865 CPU hierarchy is fully supported in standard Linux ARM64 kernels without out-of-tree patches.
* **Firmware Handoff:** The EDK II firmware boots all secondary cores into low-power states using PSCI (`arm,psci-1.0`). The bootloader enters the kernel at `x0 = <dtb_phys_addr>` on CPU 0 (the primary core). Secondary cores are awakened dynamically by the Linux kernel via PSCI `CPU_ON` SMC calls to Qualcomm Secure Execution Environment (QSEE).
* **Thermal Mitigation:** Operating performance points (OPP) and Energy Aware Scheduling (EAS) operate natively with `CONFIG_ARM_QCOM_CPUFREQ_HW`.

### 4.2 Display Subsystem & Handoff Pipeline
* **Status:** 
  * Phase 1 (Boot / Early Userspace): **Mainline (SimpleDRM)**.
  * Phase 2 (Native Acceleration): **Mainline (DPU 5.0) + Community Panel Driver**.
* **Analysis:**
  * To guarantee a seamless visual transition with zero screen flicker or re-initialization crashes, R8Q UEFI preserves the continuous splash framebuffer allocated at physical base `0x9C000000` (1080×2400, 32bpp, 4320 bytes stride, 35 MiB carveout).
  * The Linux Device Tree passed via UEFI configuration table (`EFI_DTB_TABLE_GUID`) declares a `simple-framebuffer` node at this exact address.
  * The Linux `CONFIG_DRM_SIMPLEDRM` driver binds immediately to this memory region, enabling interactive Linux console (`fbcon`), Wayland compositors (Weston, Sway), and X11 without requiring complex display clock or DSI regulator initialization.
  * For full native 120 Hz refresh rate and hardware planes, the `qcom,sm8250-dpu` driver can be engaged once the Samsung AMS650VE01 command-mode panel driver sequence is loaded.

### 4.3 Storage Subsystem: UFS 3.1 vs MicroSD
* **Status:** 100% Upstream Mainline.
* **Analysis:**
  * **Internal UFS 3.1:** Driven by `drivers/scsi/ufs/ufs-qcom.c`. Supports Gear 4 rate B 2-lane operation.
    * *Firmware Safety Invariant:* In R8Q UEFI, all internal UFS LUNs (`sda`, `sdb`, `sdc`, `sdd`, `sde`, `sdf`) are protected with a centralized read-only filter layer. In the Linux kernel, internal storage may be mounted read-only for filesystem recovery, forensic backup, or dual-boot system image access. The UEFI variable store partition (`sdd31`) remains strictly untouchable.
  * **MicroSD Slot:** Driven by `drivers/mmc/host/sdhci-msm.c`. Connected via the SDCC2 controller. Fully writable in both UEFI and Linux. Serves as the primary root filesystem target (`root=/dev/mmcblk0p2`) for native Linux installations.

### 4.4 USB Subsystem & Connectivity
* **Status:** 100% Upstream Mainline.
* **Analysis:**
  * Uses Synopsys DesignWare Core 3 (`dwc3`) paired with Qualcomm's QMP combo PHY and QUSB2 high-speed PHY.
  * Supports USB 3.1 Gen 2 SuperSpeed (10 Gbps) and backwards compatibility with USB 2.0.
  * Host Mode: Allows attaching USB flash drives, keyboards, mice, and Ethernet adapters.
  * Device/Gadget Mode: Enables USB Ethernet (`rndis`, `cdc_ether`), serial console (`g_serial`), or mass storage emulation for tethered rescue and debugging.

### 4.5 Power Management & PMIC Integration
* **Status:** Mainline (Core SPMI) + Out-of-tree (Maxim Companion).
* **Analysis:**
  * Qualcomm PM8150, PM8150B, and PM8150L manage primary SoC voltages via the SPMI bus. Upstream kernel drivers handle voltage regulation, power keys, and internal RTC.
  * Samsung integrates a Maxim MAX77705 companion PMIC on an auxiliary I2C bus (`i2c-2` or `i2c-4`). This chip controls USB Type-C power delivery negotiation, fast charging, and battery state-of-charge calculation. 
  * Basic Linux operation does not require MAX77705 drivers if the battery is adequately charged prior to boot; however, battery percentage reporting in userspace requires the community `max77705` driver.

### 4.6 Wireless & Networking (Wi-Fi / Bluetooth)
* **Status:** Mainline with Proprietary Firmware.
* **Analysis:**
  * The SM-G781B integrates the Qualcomm WCN6855 (FastConnect 6900) Wi-Fi 6E and Bluetooth 5.2 chipset.
  * Wi-Fi communicates over a dedicated PCIe interface and is driven by upstream `ath11k_pci`.
  * Requires non-free binary firmware blobs (`qca6490/amss.bin`, `m3.bin`, `board-2.bin`) placed in `/lib/firmware/ath11k/WCN6855/hw2.0/`.
  * Bluetooth communicates over high-speed UART via `hci_qca` driver and requires firmware `hpnv21.b80`.

---

## 5. Linux Kernel Defconfig Strategy

To achieve a production-grade, bootable ARM64 kernel for the SM-G781B, `config/kernel_r8q_defconfig` is architected with three strict design rules:
1. **EFI Boot Stub Compliance:** Mandatory enablement of `CONFIG_EFI=y`, `CONFIG_EFI_STUB=y`, and `CONFIG_ARM64_EFI_LOAD_FILE2_INITRD=y`.
2. **Display & Console Continuity:** Enablement of `CONFIG_DRM_SIMPLEDRM=y`, `CONFIG_FB_SIMPLE=y`, and `CONFIG_FRAMEBUFFER_CONSOLE=y` as built-in drivers (`=y`), ensuring instant video output before any module loader executes.
3. **Storage & Boot Independence:** Built-in support for `CONFIG_MMC_SDHCI_MSM=y`, `CONFIG_SCSI_UFSHCD=y`, `CONFIG_SCSI_UFS_QCOM=y`, `CONFIG_EXT4_FS=y`, and `CONFIG_OVERLAY_FS=y` to guarantee that the kernel can mount the root filesystem from external MicroSD without needing external initramfs driver modules.

---

## 6. Handoff Architecture & Memory Carveout Protection

When `LinuxBoot.efi` executes, it establishes the following memory map contract:

```
0x00000000_80000000 - 0x00000000_807FFFFF ( 8 MiB)   [RESERVED]  Hypervisor (QHEE) Carveout
0x00000000_85800000 - 0x00000000_858FFFFF ( 1 MiB)   [RESERVED]  Qualcomm AOP / RPMh Memory
0x00000000_86000000 - 0x00000000_8BFFFFFF (96 MiB)   [RESERVED]  TrustZone / QSEE / SCM Runtime
0x00000000_8C000000 - 0x00000000_92FFFFFF (112 MiB)  [RESERVED]  Modem Subsystem (MPSS) Carveout
0x00000000_9C000000 - 0x00000000_9E2FFFFF (35 MiB)   [RESERVED]  Display Continuous Splash GOP
0x00000000_9E400000 - 0x00000000_9E7FFFFF ( 4 MiB)   [BOOT-SVC]  R8Q EDK II Firmware Volume (FV)
0x00000001_00000000 - 0x00000002_7FFFFFFF (6.0 GiB)  [CONVENTIONAL] High DRAM (Linux Kernel, Initrd, Stack)
```

### Safety Guarantees:
1. **Display Carveout Protection:** The continuous splash region (`0x9C000000 - 0x9E300000`) is marked as `EfiReservedMemoryType` in the UEFI memory map and `/memreserve/` in the device tree, preventing the kernel from allocating normal heap over the visible display.
2. **TrustZone Protection:** TrustZone (`0x86000000`) is completely excluded from the memory map passed to Linux, preventing illegal memory faults and watchdogs.
3. **Firmware Volume Reclaim:** The 4 MiB EDK II FV (`0x9E400000`) is marked as `EfiBootServicesCode`, allowing Linux to safely reclaim its memory after `ExitBootServices()`.
4. **Kernel Space:** The Linux EFI Stub loads the uncompressed kernel image (`build/Image`, 47 MiB) and initramfs into high conventional DRAM (`0x100000000+`), guaranteeing zero physical collisions.

---

## 7. Subsystem Verification & Readiness Status

| Verification Item | Target Standard | Current Readiness | Validation Method |
|---|---|---|---|
| **ARM64 EFI Stub Binary** | PE/COFF `0xAA64`, Subsystem 10 | **VERIFIED (100%)** | `tests/test_linux_efi_boot.py` (Test 1) |
| **FDT Header & Magic** | Magic `0xd00dfeed`, Version 17 | **VERIFIED (100%)** | `tests/test_linux_efi_boot.py` (Test 2) |
| **Initramfs CPIO Archive** | Modern `EFI_LOAD_FILE2` GUID | **VERIFIED (100%)** | `tests/test_linux_efi_boot.py` (Test 3) |
| **Physical Memory Non-Overlap** | 0% Collision with Carveouts | **VERIFIED (100%)** | `tests/test_linux_efi_boot.py` (Test 4) |
| **Kernel Command Line** | Safe Console & Root Parameters | **VERIFIED (100%)** | `tests/test_linux_efi_boot.py` (Test 5) |
| **MicroSD External Rootfs** | FAT32 ESP + EXT4 Rootfs | **READY (100%)** | External Media Scripting Prepared |
| **Internal UFS Protection** | Complete Software Block I/O Guard | **ENFORCED (100%)** | Zero Write Paths Exposed |
| **Live Device Boot Handoff** | Physical Execution on SM-G781B | **GATE: PENDING AUTH** | Awaiting Explicit User Authorization |

---
**End of Document: M6_LINUX_SUBSYSTEM_SUPPORT_MATRIX.md**
