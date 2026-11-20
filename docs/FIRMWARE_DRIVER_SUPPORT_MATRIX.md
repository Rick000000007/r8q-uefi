# Project R8Q UEFI: Firmware Driver Support Matrix

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Driver plan. No driver in this table is implemented or hardware-validated unless explicitly stated.

---

## 1. Status definitions

| Status | Meaning |
|---|---|
| **Not started** | No code. |
| **Planned** | Design exists; no code or only a stub. |
| **Blocked** | Depends on an unknown hardware fact, a missing driver, or authorization. |
| **Reference only** | Behavior is known from upstream/public code, but not adopted for this platform. |
| **Implemented** | Code exists and builds. |
| **Hardware-validated** | Code runs on the target unit and has a recorded test result. |

No row in this matrix is **Implemented** or **Hardware-validated** at Milestone 1. The matrix is a plan, not a support claim.

---

## 2. Priority order

1. SEC/PrePi entry, CPU state, live memory map, safe stack.
2. GICv3, architectural timer, exception handling.
3. Serial console (if a debug UART is accessible) and/or inherited framebuffer GOP.
4. UEFI variable store (file-backed on ESP).
5. UFS read-only enumeration, partition discovery, FAT.
6. UEFI Shell and boot manager.
7. Linux EFI-stub handoff.
8. MicroSD, USB host/HID, PCIe.
9. Power/thermal/input telemetry.
10. ACPI/Windows research.

The order is dependency-driven. A later item must not be used to justify skipping an earlier safety gate.

---

## 3. Driver matrix

| Subsystem | Controller / interface | Candidate EDK II component | Protocols | Status | Dependencies / notes |
|---|---|---|---|---|---|
| CPU | ARMv8.2-A, 8 cores | `ArmPkg/CpuDxe` | `EFI_CPU_ARCH_PROTOCOL` | Planned | PSCI state unknown; bring up boot CPU first. |
| Exception handling | AArch64 vectors | platform SEC/DXE | — | Planned | Must not disturb secure world. |
| Timer | ARM generic timer, 19.2 MHz | `ArmPkg/TimerDxe`, `ArmArchTimerLib` | `EFI_TIMER_ARCH_PROTOCOL` | Planned | Validate PPI/INTID mapping. |
| Interrupts | GICv3 `0x17A00000`/`0x17A60000` | `ArmPkg/ArmGicDxe` | `EFI_HARDWARE_INTERRUPT_PROTOCOL` | Planned | Preserve secure interrupts. |
| Serial debug | QUP UART `0x988000` | platform `SerialPortLib` | `EFI_SERIAL_IO_PROTOCOL` | Blocked | Pin mux, clock, and physical access are unverified. |
| Display GOP | Inherited framebuffer `0x9C000000` | platform `SimpleFbDxe` | `EFI_GRAPHICS_OUTPUT_PROTOCOL` | Planned | Probe scanout/format first; do not reinit DPU/DSI. |
| Text console | GOP + ConSplitter | `MdeModulePkg/ConSplitterDxe` | `EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL` | Planned | Depends on GOP. |
| UEFI variables | ESP file store | platform `FileVariableDxe` | `EFI_VARIABLE_ARCH_PROTOCOL` services | Planned | No internal partition writes; runtime persistence unresolved. |
| UFS host | `0x1D84000`, ICE `0x1D90000` | platform `UfsDxe` | `EFI_BLOCK_IO_PROTOCOL`, `EFI_DISK_IO_PROTOCOL` | Blocked | LUN map, device model, and handoff state unknown. |
| Partitioning | GPT/MBR | `MdeModulePkg/PartitionDxe` | block I/O child handles | Planned | Depends on UFS/SD block I/O. |
| FAT | FAT12/16/32 | `FatPkg/EnhancedFatDxe` | `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL` | Planned | Depends on partition driver. |
| MicroSD | SDHCI `0x8804000` | platform `SdMmcDxe` | `EFI_BLOCK_IO_PROTOCOL` | Blocked | Card detect, UHS tuning, and slot wiring unverified. |
| USB host | DWC3 `0xA600000` | platform `XhciDxe` | `EFI_USB2_HC_PROTOCOL` | Blocked | Host mode/Type-C role unverified; upstream is peripheral/high-speed. |
| USB HID | USB keyboard/mouse | `MdeModulePkg/UsbKbDxe`, `UsbMouseDxe` | `EFI_SIMPLE_TEXT_INPUT_PROTOCOL` | Blocked | Depends on USB host. |
| Hardware keys | GPIO volume-up; power/volume-down unknown | platform `ButtonDxe` | `EFI_SIMPLE_TEXT_INPUT_PROTOCOL` | Planned | Only volume-up is described in the downstream FDT. |
| Touch | STM/Zinitix/Melfas/A96T3X6 candidates | platform `TouchDxe` | `EFI_ABSOLUTE_POINTER_PROTOCOL` | Blocked | Installed controller unknown; firmware files are vendor-specific. |
| PCIe | 3 root complexes | platform `PciHostBridgeDxe` | `EFI_PCI_ROOT_BRIDGE_IO_PROTOCOL` | Blocked | Endpoint population and resource windows unverified. |
| WLAN | QCA6490 node on PCIe RC0; BT node lists QCA6390/QCA6490 | platform/OS driver | — | Blocked | No UEFI Wi-Fi driver; module identity and firmware loading unverified. |
| PMIC telemetry | PM8150 family via SPMI | platform `PmicDxe` | platform protocol | Blocked | Safe register access and regulator ownership unknown. |
| Charger | MAX77705/PCA9468 | platform `ChargerDxe` | platform protocol | Blocked | Active path unknown; do not control charging early. |
| Fuel gauge | Unknown | platform `BatteryDxe` | platform protocol | Blocked | No MAX17042 node; identify hardware first. |
| Thermal | TSENS `0xC222000`/`0xC263000`, `0xC223000`/`0xC265000` | platform `ThermalDxe` | platform protocol | Blocked | Driver and calibration unknown. |
| Device tree | Inherited FDT / ESP DTB | platform `FdtDxe` | `EFI_DEVICE_TREE_PROTOCOL`, config table | Planned | Must preserve vendor carveouts. |
| ACPI | ACPI 6.x tables | platform `AcpiPlatformDxe` | `EFI_ACPI_TABLE_PROTOCOL` | Not started | Windows research only; no tables yet. |
| Boot manager | ESP / UEFI apps | `MdeModulePkg/BdsDxe` + platform app | boot manager protocols | Planned | Depends on storage, console, variables. |
| Shell | UEFI Shell 2.2 | `ShellPkg` | shell | Planned | Depends on console, input, storage. |
| Diagnostics | Custom commands | platform app | shell commands | Planned | Most commands depend on drivers above; no "verified telemetry" claim. |

---

## 4. Reference components worth studying

These are **not** adopted as-is:

- `edk2-msm` PrePi entry and platform memory-map library — useful for understanding Qualcomm EDK II boot flow.
- `edk2-msm` `SimpleFbDxe`/GOP patterns — useful for inherited framebuffer handling.
- `edk2-msm` BootShim — useful for understanding Android boot-image wrapping.
- Linux `sm8250.dtsi` and `sm8250-samsung-common.dtsi` — SoC-level addresses and reserved-memory semantics.
- Downstream `r8q-live.dts` — device-specific evidence, not a build input.

Any code borrowed or adapted later must be license-reviewed and attributed. The project does not import a complete third-party `r8q` firmware implementation.

---

## 5. Protocol design notes

### 5.1 GOP

The GOP driver must report the actual inherited framebuffer geometry, not a fabricated mode list. If the scanout probe fails, it must not publish a GOP that points at an inactive buffer.

Candidate values (to be verified at runtime):

- base `0x9C000000`;
- size `0x2300000`;
- width 1080;
- height 2400;
- stride 4320;
- format `PixelBlueGreenRedReserved8BitPerColor` or the format actually observed.

### 5.2 Battery/thermal

Custom protocols may be defined later, but only after the underlying I2C/SPMI/TSENS access is safe. The Milestone 1 DEC file defines GUIDs for planning; that does not mean the protocols are implemented.

### 5.3 Variables

The file-backed variable driver must:

- validate magic, version, length, and CRC;
- bound the total store and each variable;
- never write outside the ESP file;
- fail closed on corruption (preserve the corrupt file, create a new default store);
- document that runtime `SetVariable()` persistence is not solved by a boot-services-only FAT driver.

---

## 6. What would change a status

A row moves from **Planned/Blocked** to **Implemented** only when:

1. the code is in the repository and builds in CI or on the host;
2. the required hardware fact is recorded in the verification ledger;
3. the driver has a QEMU or hardware test;
4. the test result is committed with the code.

A row moves to **Hardware-validated** only with a recorded target-unit test, including the exact firmware build hash and the observed output.
