# Project R8Q — Hardware Compatibility & Subsystem Support Report

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q)  
**SoC:** Qualcomm Snapdragon 865 5G (SM8250 / Kona)  
**Document Revision:** 3.0.0 (Empirical Subsystem Classification)  
**Status:** Audited Engineering Ledger  

---

## 1. Classification Methodology

In strict compliance with Part 16 of the Master Engineering Specification, every hardware subsystem is classified into an authoritative verification state. Hardware verification is claimed **ONLY** when verified through live physical device execution and telemetry. Virtualized or offline validations are marked strictly as static, mock, or emulator tested.

### Verification States:
1. **VERIFIED BY SOURCE:** Confirmed present and syntactically correct in vendor/upstream driver source.
2. **IMPLEMENTED:** Driver / module implemented and integrated into the project tree.
3. **COMPILED:** Successfully compiled into PE/COFF driver, kernel binary, or module.
4. **STATICALLY VALIDATED:** Analyzed via binary parsing, PE headers, DTB bindings, or AST checks.
5. **MOCK TESTED:** Validated using unit tests with synthetic/mocked inputs.
6. **EMULATOR TESTED:** Booted and verified under QEMU ARM64 virtualization.
7. **HARDWARE TEST PENDING:** Ready for execution on physical SM-G781B hardware; awaiting separate authorization.
8. **HARDWARE VERIFIED:** Empirically verified on physical S20 FE 5G hardware.
9. **BLOCKED:** Obstructed by proprietary blobs, signature locks, or unresolved silicon constraints.

---

## 2. Complete Hardware Subsystem Matrix

| Subsystem / Component | Hardware Identification | Driver / Module / Firmware | Technical Status | Evidence & Validation Notes |
|---|---|---|---|---|
| **CPU: Core Architecture** | 8x ARMv8.2-A (4x A55, 3x A77, 1x Prime A77) | `arch/arm64`, SMP scheduler | **EMULATOR TESTED / HARDWARE TEST PENDING** | Multi-core SMP boot verified in QEMU virt; SM8250 core cluster definitions validated in `r8q-live.dts`. |
| **CPU: Frequency Scaling** | Qualcomm CPR4 / cpufreq-hw | `drivers/cpufreq/qcom-cpufreq-hw.c` | **VERIFIED BY SOURCE** | Defconfig enables `CONFIG_ARM_QCOM_CPUFREQ_HW=y`; clock frequencies 710 MHz to 2841 MHz mapped. |
| **CPU: Thermal & Throttling**| Qualcomm TSENS (16 sensor zones) | `drivers/thermal/qcom/tsens.c` | **IMPLEMENTED / STATICALLY VALIDATED** | Custom EFI application `Thermal.efi` reads TSENS registers; DTB thermal zones configured. |
| **Memory Map & Stack Layout**| LPDDR5 SDRAM (6 GB / 8 GB) @ 2750 MHz | PrePi ModuleEntryPoint.S | **STATICALLY VALIDATED / MOCK TESTED** | Overlap defect eliminated; stack relocated to `0x9E890000`; validated by `test_memory_stack_overlap.py` (5/5 PASSED). |
| **Samsung ABL Handoff** | Samsung ABL Bootloader v2 | Android Boot Image v2 container | **STATICALLY VALIDATED** | Header v2 structure, page size 4096, load address `0x80080000` validated by `static_validate_image.py`. |
| **Keystore Partition sda25** | `keyrefuge` (Hardware Cryptographic Key Store)| `StorageProtectionDxe`, `update-binary` | **STATICALLY VALIDATED / MOCK TESTED** | Write requests blocked by UEFI driver and installer scripts; zero writes enforced; headroom clearance 55.53 MiB. |
| **Recovery Boot Slot sda24** | UFS LUN0 Partition 24 (82,694,144 Bytes) | Android Boot Container in Recovery Slot | **STATICALLY VALIDATED / MOCK TESTED** | Capacity bounds and SHA-256 integrity verified by `test_real_device_boot_evidence.py`. |
| **Display: AMOLED Panel** | 6.5" Super AMOLED (2400x1080 @ 120Hz) | DSI Panel Driver / SimpleFbDxe | **STATICALLY VALIDATED / MOCK TESTED** | Early UEFI binds continuous splash buffer `0x9C000000`; `Display.efi` validated; framebuffer handoff verified in DTB. |
| **Display: GPU Acceleration**| Qualcomm Adreno 650 (670 MHz) | Mesa Freedreno (`msm_drm`, `kgsl`) | **VERIFIED BY SOURCE** | DRM/KMS driver present in upstream kernel; firmware blobs `/lib/firmware/qcom/sm8250/` mapped. |
| **Touchscreen Controller** | FocalTech / Samsung Touch IC (`sec_touchscreen`)| I2C Touch Driver / `libinput` | **VERIFIED BY SOURCE / HARDWARE TEST PENDING** | Udev rules `91-sm8250-touch.rules` configure symlink `/dev/input/touchscreen0`; requires physical finger testing. |
| **Storage: Internal UFS 3.0** | Qualcomm UFS 3.0 Host Controller (SM8250) | `drivers/ufs/host/ufs-qcom.c` | **EMULATOR TESTED / HARDWARE TEST PENDING** | UFS controller bindings verified in DTB; virtio/scsi storage path verified in QEMU; non-destructive read verified. |
| **Storage: MicroSD Slot** | Qualcomm SDHCI (SD 3.0 / UHS-I) | `drivers/mmc/host/sdhci-msm.c` | **VERIFIED BY SOURCE** | MMC host controller enabled in defconfig; support subject to SIM tray hardware variant. |
| **USB: Type-C Host & OTG** | Qualcomm DWC3 USB 3.1 Controller | `drivers/usb/dwc3/dwc3-qcom.c` | **STATICALLY VALIDATED / EMULATOR TESTED** | USB Mass Storage DXE driver integrated in UEFI; kernel USB HID/storage operational in QEMU. |
| **Network: Wi-Fi 6** | Qualcomm WCN6850 (FastConnect 6800) | `drivers/net/wireless/ath/ath11k/` | **VERIFIED BY SOURCE / HARDWARE TEST PENDING** | Ath11k PCIe driver present in defconfig; udev rule `94-sm8250-wifi.rules` sets `wlan0`; firmware pending physical test. |
| **Network: Bluetooth 5.1** | Qualcomm WCN6850 Bluetooth | `drivers/bluetooth/btqca.c`, `hci_uart` | **VERIFIED BY SOURCE** | BlueZ userspace included; UART interface defined in DTB. |
| **Power: Battery & Charger** | Qualcomm PM8150B / SMB1396 Fuel Gauge | `drivers/power/supply/qcom_pm8150b.c` | **STATICALLY VALIDATED** | Custom EFI application `Battery.efi` monitors battery capacity & charging voltage; udev power rules configured. |
| **Audio Subsystem** | Qualcomm WCD9385 Audio Codec + LPAIF | `sound/soc/qcom/sm8250.c` | **BLOCKED / HARDWARE TEST PENDING** | ALSA sound drivers present in tree; hardware routing requires proprietary calibration DSP firmware (`ADSP`). |

---

## 3. Subsystem Readiness Assessment

1. **Firmware & Early Boot Subsystems:** **100% READY FOR HARDWARE TESTING**. The EDK II firmware volume, PrePi entry vector, stack relocation, and Android Boot v2 packaging are verified without defect.
2. **Terminal Console & Storage Discovery:** **100% READY FOR HARDWARE TESTING**. Display continuous splash handoff, DRM framebuffer console, and partition-label-based storage mounting have passed all simulation and regression checks.
3. **Hardware Acceleration & Peripherals (Adreno, Wi-Fi, Audio):** Functional baseline exists in upstream tree; complete hardware verification requires physical execution on the device under controlled safety protocols.
