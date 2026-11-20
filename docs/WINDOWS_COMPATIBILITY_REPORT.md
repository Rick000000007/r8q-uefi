# Project R8Q UEFI: Windows ARM64 Compatibility Report

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Research only. Windows is not installable or bootable on this firmware today.

---

## 1. Executive summary

Windows on ARM64 is an experimental, long-term research target. It is **not** part of the Milestone 1 deliverable and no Windows boot, installation, driver, or usability claim is made.

The previous revision of this document claimed that "UEFI-compatible" was achieved and that Windows PE boot was "in design." Those claims were not supported by any build, ACPI table, driver, or hardware test. They have been removed.

Current status:

| Item | Status |
|---|---|
| Windows ARM64 boots on R8Q UEFI | Not achieved |
| Windows installer runs | Not achieved |
| Windows PE boots | Not achieved |
| ACPI tables exist | No |
| UFS storage driver for Windows | No |
| USB host/keyboard for Windows | No |
| Display driver / GOP handoff validated | No |
| Power/thermal/charger drivers | No |
| Secure Boot / measured boot design | No |

---

## 2. Why Windows is harder than Linux

Linux can consume a device tree and a small set of drivers. Windows ARM64 expects:

- ACPI tables (MADT, GTDT, FADT, DSDT/SSDT, DBG2, PPTT, IORT, etc.);
- a UEFI runtime services implementation that survives `SetVirtualAddressMap()`;
- storage, USB, display, power, and thermal drivers;
- firmware/ACPI device descriptions that match the actual hardware;
- a boot path that the Windows Boot Manager and `winload.efi` accept;
- driver signing and Secure Boot policy, if Secure Boot is enabled.

None of these are present. A GOP framebuffer alone is not enough to install or boot Windows.

---

## 3. Blocker matrix

| Blocker | Why it matters | Current status | Evidence needed |
|---|---|---|---|
| ACPI MADT/GTDT/FADT | Windows needs interrupt/timer/platform descriptions | Not started | ACPI tables that pass Microsoft/ACPICA validation |
| DSDT/SSDT | Device enumeration (UFS, USB, PCIe, PMIC, etc.) | Not started | Device-specific ASL and hardware validation |
| UEFI runtime services | Windows calls runtime services after boot | Not validated | `SetVirtualAddressMap`, runtime variable/console behavior |
| UFS storage driver | Windows installer must see internal storage | No driver | A working Windows UFS miniport or a supported alternate boot medium |
| USB host/XHCI | Installer and keyboard input | Unverified | DWC3 host mode + XHCI + HID on hardware |
| Display | Installer/desktop output | Unverified | GOP handoff and/or Windows display driver |
| Power/PMIC | Battery, charging, thermal, sleep | No driver | PMIC/charger/TSENS drivers and ACPI descriptions |
| Secure Boot | Windows may require a trusted boot chain | Not designed | Key management and interaction with Samsung verified boot |
| Windows image/licensing | Installation media and activation | Not addressed | Legal, licensed test image |
| Restore path | A failed install can brick the boot flow | Not tested | Verified stock backup and restore procedure |

---

## 4. ACPI research plan (later milestone)

If Windows research continues, the minimum table set is:

1. **MADT** — GICv3 distributor/redistributors and CPU interrupts.
2. **GTDT** — generic timer frequency and timer interrupts.
3. **FADT** — hardware-reduced ACPI, 64-bit boot, power management flags.
4. **DSDT/SSDT** — CPU containers, UFS, USB, PCIe, PMIC, display, and platform devices.
5. **DBG2** — debug UART, if a physically accessible UART exists.
6. **PPTT** — CPU topology and caches.
7. **IORT** — IOMMU/SMMU description, if Windows drivers need it.

The tables must describe the actual hardware, not a generic SM8250 template. The downstream FDT is a useful source of addresses and interrupt numbers, but ACPI is not a mechanical translation of FDT.

---

## 5. Storage and boot-media strategy

Windows setup normally needs to see a supported disk. The internal UFS path requires a Windows-compatible UFS driver that does not exist in this project. Possible research directions, none validated:

- boot Windows PE from a USB mass-storage device and install to an external drive;
- use a Windows-compatible NVMe/UFS bridge, if the hardware exposes one;
- develop a minimal UFS miniport with Qualcomm/Samsung documentation, which is a large project;
- use a virtual disk image for early bring-up, which does not prove internal storage support.

No installation path is recommended until the storage and restore story is credible.

---

## 6. Safety and legal constraints

- Do not overwrite the stock `BOOT`, `recovery`, `EFS`, `persist`, or bootloader partitions to test Windows.
- Do not disable Secure Boot or verified boot without a documented, reversible procedure and user authorization.
- Do not distribute Microsoft binaries or product keys.
- Do not claim "Windows ready" or "Windows compatible" based on a UEFI shell or a GOP framebuffer.

---

## 7. Exit criteria for a future Windows milestone

A future milestone may claim "Windows PE boots" only when:

1. A licensed Windows PE image is loaded by R8Q UEFI.
2. The firmware provides the ACPI tables and runtime services it needs.
3. The PE environment reaches a shell or setup screen on the target unit.
4. Storage, input, and display are usable enough to attempt an install.
5. A tested restore path returns the device to its stock boot flow.
6. The exact firmware build, ACPI tables, and test output are committed.

Until then, Windows remains a research note, not a deliverable.
