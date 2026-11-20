# Project R8Q UEFI: EDK II Platform Design

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Package:** `R8QPkg`
**EDK II pin:** `edk2-stable202411` (`0f3867fa6ef0553e26c42f7d71ff6bdb98429742`), with `edk2-stable202408.01` as fallback.
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Design only. No EDK II platform build exists yet.

---

## 1. Design goals

1. Build a small, auditable ARM64 EDK II platform that can be tested in QEMU before hardware.
2. Keep the stock PBL/XBL/ABL and secure world untouched.
3. Treat the live FDT and memory map as the source of truth.
4. Avoid hardcoded variant data (RAM size, panel, touch, charger, storage).
5. Make every hardware address a named PCD with a source comment and a runtime sanity check.

---

## 2. Package layout

The planned package is:

```text
platform/R8QPkg/
├── R8QPkg.dec
├── R8QPkg.dsc                  # planned; not committed as a working build
├── R8QPkg.fdf                  # planned
├── Include/
│   ├── Library/
│   │   ├── R8QPlatformLib.h
│   │   └── R8QFdt.h
│   └── Protocol/
│       ├── R8QBattery.h
│       └── R8QThermal.h
├── Library/
│   ├── R8QPlatformLib/         # live memory map, reserved regions, platform info
│   ├── R8QFdtLib/              # FDT validation/patching helpers
│   ├── R8QSerialPortLib/       # QUP UART, only after pin/clock validation
│   └── R8QFramebufferLib/      # inherited framebuffer probe
├── Drivers/
│   ├── SimpleFbDxe/            # GOP over inherited framebuffer
│   ├── FileVariableDxe/        # ESP-backed variables
│   ├── ButtonDxe/              # hardware keys
│   ├── UfsDxe/                 # UFS host + LUN enumeration
│   ├── SdMmcDxe/               # SDHCI
│   ├── XhciDxe/                # DWC3 host, if validated
│   ├── PmicDxe/                # PMIC telemetry
│   └── ThermalDxe/             # TSENS
├── Applications/
│   ├── Diagnostics/            # shell commands
│   └── BootManager/            # Linux/recovery/UEFI boot menu
└── Acpi/                       # research only, no tables yet
```

`R8QPkg.dec` exists in Milestone 1 and defines the package GUID, protocol GUIDs, and a small set of candidate PCDs. The DSC/FDF and drivers are Milestone 2+ work.

---

## 3. Firmware device layout

A candidate layout, not a validated image:

```text
FD (candidate base 0x9E400000, candidate size 0x00400000)
┌──────────────────────────────────────────────────────────────┐
│ SEC/PrePi + early platform code                              │
│ - entry shim / ARM64 header (if required by ABL)             │
│ - stack and early heap in a verified free window             │
│ - live FDT validation and memory-map construction            │
├──────────────────────────────────────────────────────────────┤
│ DXE core + architectural protocols                           │
│ - CPU, timer, GIC, exception handling                        │
├──────────────────────────────────────────────────────────────┤
│ Platform drivers                                              │
│ - GOP, variables, storage, input, telemetry                   │
├──────────────────────────────────────────────────────────────┤
│ Applications                                                  │
│ - UEFI Shell, diagnostics, boot manager                      │
└──────────────────────────────────────────────────────────────┘
```

The base `0x9E400000` is an **inference** from the downstream reserved-memory map: it is the 12 MiB gap between `dfps_data` end (`0x9E400000`) and `sec_debug` start (`0x9F000000`). It is not validated. The `edk2-msm` reference uses `0xCE000000` + `0x00700000`; that is an alternative candidate, not a target fact. The final base must be a build parameter and must be checked against the live map.

The FDF must not assume that the FD is the only thing in the window. It must reserve space for:

- the FD image;
- the PrePi stack;
- the early heap;
- page tables;
- the DXE memory pool if it is placed in the same window.

If the window is too small, the platform must use a different free region rather than overlapping a carveout.

---

## 4. PCD strategy

PCDs are grouped into three classes:

### 4.1 Verified SoC constants

These are source-verified and unlikely to vary:

```ini
gArmTokenSpaceGuid.PcdArmArchTimerFreqInHz|19200000
gArmTokenSpaceGuid.PcdGicDistributorBase|0x17A00000
gArmTokenSpaceGuid.PcdGicRedistributorsBase|0x17A60000
```

### 4.2 Verified controller addresses

These are source-verified for the captured unit but must still be sanity-checked:

```ini
gR8QPkgTokenSpaceGuid.PcdFrameBufferBase|0x9C000000
gR8QPkgTokenSpaceGuid.PcdFrameBufferSize|0x02300000
gR8QPkgTokenSpaceGuid.PcdDisplayWidth|1080
gR8QPkgTokenSpaceGuid.PcdDisplayHeight|2400
gR8QPkgTokenSpaceGuid.PcdDisplayStride|4320
gR8QPkgTokenSpaceGuid.PcdUfsHostControllerBase|0x01D84000
gR8QPkgTokenSpaceGuid.PcdUfsIceBase|0x01D90000
gR8QPkgTokenSpaceGuid.PcdSdhciControllerBase|0x08804000
gR8QPkgTokenSpaceGuid.PcdUartBaseAddress|0x00988000
```

The UART address is verified as an SoC UART, but physical access and pin mux are not. The framebuffer is verified as a reserved buffer, but scanout at handoff is not.

### 4.3 Candidate / runtime values

These must not be fixed PCDs in a production build:

- RAM base/size and the memory map;
- FD base/size;
- UFS LUN/partition map;
- panel/touch/charger/fuel-gauge variant;
- USB host role;
- PCIe endpoint population;
- ACPI tables.

They belong in runtime discovery code, a generated platform description, or a build-time configuration file that is explicitly marked "candidate."

---

## 5. Boot phases

### 5.1 SEC/PrePi

1. Preserve the incoming `x0` (candidate DTB pointer) and validate the FDT header before dereferencing it.
2. Detect `CurrentEL`; handle EL1 and EL2 without assuming one.
3. Disable interrupts and reconfigure MMU/caches safely.
4. Establish a stack in a verified free region.
5. Parse `/memory` and `/reserved-memory`; build a conservative memory map.
6. Reserve the FD, stack, heap, page tables, framebuffer, and every vendor carveout.
7. Enable the MMU and caches with a flat mapping that covers DRAM and the required MMIO windows.
8. Transfer to DXE.

The entry shim must be able to present an ARM64 Linux-image-compatible header if the measured ABL path requires it. That header format is a hypothesis until the stock `BOOT` image and ABL behavior are inspected.

### 5.2 DXE

1. Dispatch CPU, timer, GIC, and exception drivers.
2. Publish GOP only if the framebuffer probe passes.
3. Publish a serial console only if the UART is validated.
4. Load the file-backed variable driver.
5. Bring up UFS read-only, then partition/FAT.
6. Bring up MicroSD, USB, PCIe, and telemetry only as dependencies allow.
7. Dispatch the shell and boot manager.

### 5.3 BDS

1. Read boot entries from the ESP.
2. If a key is held or the timeout expires, enter the shell.
3. Otherwise boot the selected Linux/recovery/UEFI target.
4. On failure, return to the menu or shell; do not automatically write to internal storage.

---

## 6. Memory map rules

- Use `EfiReservedMemoryType` for all `no-map` and vendor carveouts.
- Use `EfiMemoryMappedIO` for MMIO windows that are not RAM.
- Use `EfiBootServicesCode`/`Data` only for regions the firmware actually owns.
- Use `EfiConventionalMemory` only for regions that are free in the live FDT and not used by the firmware.
- Keep the framebuffer reserved even when GOP is active; the OS may reuse it only after its display driver takes over.
- Do not describe the 69 MiB gap between the two RAM ranges as conventional memory unless the live map says it is usable.
- Do not assume that the downstream `removed` region is free; it is explicitly reserved.

---

## 7. Build outputs (planned)

| Output | Path | Status |
|---|---|---|
| EDK II FD | `build/R8Q_EFI.fd` | Not built |
| Boot image wrapper | `build/r8q-uefi-boot.img` | Not built |
| Build manifest | `manifests/build_manifest.json` | Not generated |
| Verification log | `logs/build.log` | Not generated |
| QEMU test log | `logs/qemu.log` | Not generated |

The Milestone 1 `scripts/build.sh` intentionally does **not** build firmware. It validates the documentation baseline and regenerates the source manifest. A real build driver is Milestone 2 work.

---

## 8. QEMU strategy

Before hardware, the platform should be testable with `qemu-system-aarch64` using a virtual machine or a minimal ARM virt platform. The QEMU target does not need to emulate SM8250 peripherals; it needs to exercise:

- SEC/PrePi entry and memory-map construction;
- DXE dispatch;
- GOP on a synthetic framebuffer;
- file-backed variables on a virtual FAT disk;
- UEFI Shell startup;
- Linux EFI-stub handoff with a test kernel/DTB.

The host currently lacks `qemu-system-aarch64`; installing it is a Milestone 2 prerequisite.

---

## 9. Open design questions

1. Does ABL require an Android boot-image wrapper, an ARM64 Linux-image header, or a raw FD?
2. What is the exact load address and available free window?
3. Does ABL provide a UEFI memory map, or only an FDT?
4. Is the UFS controller usable after ABL without a full reset?
5. Can the inherited framebuffer be mapped safely with the firmware's cache attributes?
6. Which variable-store medium is available before UFS/SD drivers exist?
7. What is the minimum viable console for first hardware bring-up?

These questions are tracked in `docs/VERIFICATION_LEDGER.md` and must be resolved before the corresponding code is treated as portable.
