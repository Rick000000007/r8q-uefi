# Project R8Q UEFI

Independent ARM64 UEFI firmware research for the Samsung Galaxy S20 FE 5G
(`SM-G781B`, codename `r8q`, Qualcomm SM8250/Kona).

## Status

**Milestone 1: research baseline.** No firmware image has been built, flashed,
or executed on a phone. No device was attached during this work. Every hardware
statement is graded as device-observed (`D`), source-verified (`V`), inferred
(`I`), or unknown (`U`) in [`docs/VERIFICATION_LEDGER.md`](docs/VERIFICATION_LEDGER.md).

The previous "approved architectural baseline" claims were not supported by
device evidence. They have been corrected or removed; see
[`docs/RESEARCH_BASELINE.md`](docs/RESEARCH_BASELINE.md).

## Safety rules

- Do not replace Qualcomm PBL/XBL or Samsung ABL.
- Do not write to bootloader, TrustZone, hypervisor, calibration (`EFS`,
  `sec_efs`, `persist`), modem, or stock recovery partitions.
- Do not assume RAM size, panel, touch controller, charger, fuel gauge,
  storage capacity, LUN layout, or ABL handoff state. Detect at runtime.
- Do not claim Windows installability or functionality without driver and boot
  evidence.
- Any device write requires a verified backup, a tested restore path, and
  explicit authorization.

## Documents

| Document | Purpose |
|---|---|
| [`docs/RESEARCH_BASELINE.md`](docs/RESEARCH_BASELINE.md) | Evidence policy, verified facts, corrections, and integration hypothesis |
| [`docs/VERIFICATION_LEDGER.md`](docs/VERIFICATION_LEDGER.md) | Claim-by-claim evidence status and sources |
| [`docs/UEFI_ARCHITECTURE.md`](docs/UEFI_ARCHITECTURE.md) | Boot-chain boundary and platform architecture |
| [`docs/HARDWARE_DEPENDENCY_GRAPH.md`](docs/HARDWARE_DEPENDENCY_GRAPH.md) | Initialization ownership and dependency graph |
| [`docs/FIRMWARE_DRIVER_SUPPORT_MATRIX.md`](docs/FIRMWARE_DRIVER_SUPPORT_MATRIX.md) | Driver plan and current status |
| [`docs/EDK2_PLATFORM_DESIGN.md`](docs/EDK2_PLATFORM_DESIGN.md) | EDK II package, PCD, FD, and phase design |
| [`docs/SHELL_COMMAND_SUITE.md`](docs/SHELL_COMMAND_SUITE.md) | Shell and diagnostic command plan |
| [`docs/LINUX_BOOT_DESIGN.md`](docs/LINUX_BOOT_DESIGN.md) | Linux EFI-stub and direct-boot design |
| [`docs/WINDOWS_COMPATIBILITY_REPORT.md`](docs/WINDOWS_COMPATIBILITY_REPORT.md) | Windows ARM64 research status and blockers |
| [`docs/RECOVERY_AND_SAFETY_PLAN.md`](docs/RECOVERY_AND_SAFETY_PLAN.md) | Backup, restore, and authorization policy |
| [`docs/REPRODUCIBLE_BUILD_STRATEGY.md`](docs/REPRODUCIBLE_BUILD_STRATEGY.md) | Toolchain pins and build workflow |
| [`docs/PHASED_IMPLEMENTATION_SCHEDULE.md`](docs/PHASED_IMPLEMENTATION_SCHEDULE.md) | Evidence-gated milestones |
| [`devicetree/README.md`](devicetree/README.md) | Downstream FDT provenance and sanitization |

## Host verification

```bash
./scripts/verify_environment.sh
./scripts/build.sh
```

`build.sh` validates the documentation baseline and regenerates the source
manifest. It does **not** build firmware and does **not** touch a device.

## Repository layout

```text
config/            Platform configuration and pinned versions
devicetree/        Sanitized downstream FDT evidence
diagnostics/       Host-side read-only inspection prototype
docs/              Milestone 1 research and design documents
manifests/         Generated SHA-256 manifest
platform/R8QPkg/   EDK II package declaration (design only)
scripts/           Environment, manifest, and baseline checks
shell/scripts/     Draft UEFI Shell scripts (not validated)
```

## Pinned sources

| Source | Pin |
|---|---|
| EDK II | `edk2-stable202411`, commit `0f3867fa6ef0553e26c42f7d71ff6bdb98429742` |
| Linux DTS | `v6.18`, commit `f7b88edb52c8dd01b7e576390d658ae6eef0e134` |
| Public reference | `edk2-porting/edk2-msm` commit `e1952621f419f8db60ed28271264e1b5184c571d` (reference only) |

## Licensing

No project license has been selected. Do not redistribute the repository or
the downstream device-tree evidence until licensing and provenance have been
reviewed.
