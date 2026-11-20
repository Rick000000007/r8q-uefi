# Project R8Q UEFI: Shell and Diagnostic Command Suite

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Design and scripting plan. No custom command is implemented or hardware-validated.

---

## 1. Shell strategy

Milestone 1 does not ship a shell. The plan is:

1. Integrate the standard EDK II UEFI Shell 2.2 for ARM64.
2. Use standard shell commands (`map`, `ls`, `cd`, `cat`, `fs0:`, `load`, `bcfg`, `reset`, etc.) for early bring-up.
3. Add a small set of R8Q diagnostic commands only after the underlying drivers exist.
4. Keep every custom command read-only unless the user explicitly invokes a documented write operation.
5. Never expose a command that writes to `xbl`, `xbl_config`, `abl`, `tz`, `hyp`, `efs`, `sec_efs`, `persist`, modem calibration, or the stock recovery.

The shell is only useful once a console exists. On early hardware, the likely console is the inherited framebuffer GOP; if that probe fails, a validated debug UART or a headless boot path is required.

---

## 2. Command status

| Command | Purpose | Status | Dependencies |
|---|---|---|---|
| `sysinfo` | Model, board revision, SoC, firmware build, boot mode | Planned | FDT/SMBIOS-like platform info |
| `memmap` | UEFI memory map and reserved regions | Planned | `GetMemoryMap`, FDT parser |
| `cpuinfo` | CPU topology, current EL, timer frequency | Planned | `ArmPkg` CPU/timer |
| `gicinfo` | GICD/GICR bases and interrupt state | Planned | GIC driver |
| `display` | GOP mode, framebuffer base/stride/format | Planned | GOP driver |
| `ufsinfo` | UFS controller, device, LUNs, capacities | Blocked | UFS driver |
| `partinfo` | GPT/MBR partitions and names | Blocked | UFS/SD block I/O |
| `sdcard` | SDHCI card detect and capacity | Blocked | SDHCI driver |
| `usbinfo` | DWC3 mode, ports, devices | Blocked | USB host driver |
| `pcieinfo` | PCIe root complexes and endpoints | Blocked | PCIe driver |
| `battery` | Charger/fuel-gauge telemetry | Blocked | I2C/SPMI + charger driver |
| `thermal` | TSENS temperatures | Blocked | TSENS driver |
| `keys` | Volume/power key state | Planned | GPIO/PMIC input |
| `fdtinfo` | FDT model, compatible, memory, reserved nodes | Planned | FDT parser |
| `bootmenu` | Interactive boot selection | Planned | Boot manager |
| `bootlog` | Firmware log buffer | Planned | Platform logger |
| `audit` | Run a safe subset of the above and print a report | Planned | Commands above |

The names are provisional. A command is not added to the shell until its data source is safe and its output is labeled with the source and confidence.

---

## 3. Output rules

Every diagnostic command must:

- print the data source (UEFI protocol, FDT node, MMIO register, or SMEM);
- distinguish measured values from defaults;
- print `UNKNOWN` rather than a fabricated value;
- avoid exposing serial numbers, IMEI, MAC addresses, or other personal identifiers by default;
- be read-only unless the command name explicitly says otherwise;
- return a non-zero shell status on failure.

Example:

```text
r8q> ufsinfo
UFS host: 0x01D84000 (source: FDT /soc/ufshc@1d84000)
Device:   UNKNOWN (driver not initialized)
LUNs:     UNKNOWN
```

This is preferable to a plausible but invented capacity or LUN table.

---

## 4. Shell scripts

The scripts in `shell/scripts/` are drafts. They must be updated when the shell and drivers exist. Current intent:

| Script | Purpose | Current status |
|---|---|---|
| `startup.nsh` | Banner, timeout, default boot entry, fallback to shell | Draft; references commands that do not exist |
| `boot-linux.nsh` | Locate and start a Linux EFI stub | Draft; path and kernel format unverified |
| `boot-recovery.nsh` | Start a recovery image or enter maintenance shell | Draft; recovery layout unverified |
| `hardware-audit.nsh` | Run a read-only audit subset | Draft; depends on planned commands |
| `storage-audit.nsh` | Enumerate block devices and partitions | Draft; depends on storage drivers |

The scripts must not assume `fs0:`/`fs1:` mapping. They should use `map` and explicit volume labels or paths discovered at runtime.

---

## 5. Safety commands

A later milestone may add:

- `r8q-backup-boot` — read the stock `BOOT` partition to a file and verify its hash (read-only);
- `r8q-verify-backup` — compare a backup against a recorded hash;
- `r8q-restore-boot` — restore a verified stock image, with explicit confirmation and a hardware-key gate.

These are **not** part of Milestone 1. They require a validated partition map, a tested restore path, and explicit user authorization.

---

## 6. Testing

Before a command is declared usable:

1. It must compile for AARCH64.
2. It must run in QEMU or on hardware without touching protected partitions.
3. Its output must be compared with an independent source (FDT, Linux `sysfs`, or a datasheet).
4. The test record must include the firmware build hash and the exact command/output.
5. Any value that cannot be independently confirmed must be printed as `UNKNOWN`.

No command in this document currently meets those criteria.
