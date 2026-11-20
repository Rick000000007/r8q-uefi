# Project R8Q UEFI: Phased Implementation Schedule

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Evidence-gated plan. Durations are indicative, not commitments.

---

## 1. Rules

- A milestone is complete only when its exit criteria are met and recorded.
- Hardware milestones require explicit user authorization before any device write.
- No milestone may claim a hardware subsystem works without a driver, a protocol, and a test record.
- A failed safety gate stops the schedule; it is not bypassed to keep a date.
- Documentation and verification ledger updates are part of every milestone.

---

## 2. Milestone summary

| Milestone | Goal | Device writes | Exit criteria |
|---|---|---|---|
| **M1** | Research baseline | None | Corrected docs, verification ledger, manifest, sanitized FDT, host checks. |
| **M2** | EDK II build + QEMU | None | Pinned EDK II builds a minimal AArch64 image; QEMU boot log recorded. |
| **M3** | Handoff instrumentation | None (read-only) | Live FDT, memory map, partition map, and handoff state captured; restore plan documented. |
| **M4** | First hardware payload | `BOOT` only, authorized | Custom payload boots to a console; stock restore tested. |
| **M5** | Storage + variables | `BOOT` only | UFS read-only enumeration, partition/FAT, file-backed variables. |
| **M6** | Shell + diagnostics | `BOOT` only | Shell runs; safe diagnostic subset works. |
| **M7** | Linux boot | `BOOT` only | Linux kernel reaches userspace; display/serial console works. |
| **M8** | Recovery integration | `BOOT` only | Recovery path and rollback tested. |
| **M9** | Windows research | None | ACPI/driver gap analysis; no install claim. |
| **M10** | Optional GUI + hardening | `BOOT` only | GUI, stress tests, reproducible release. |

---

## 3. Milestone details

### M1 — Research baseline (complete)

**Objective:** Replace the unsupported "approved" claims with an evidence-graded baseline.

**Deliverables:**

- `docs/RESEARCH_BASELINE.md`;
- `docs/VERIFICATION_LEDGER.md`;
- corrected architecture, dependency, driver, platform, shell, Linux, Windows, recovery, build, and schedule documents;
- sanitized downstream FDT and provenance note;
- updated `config/platform.env`, `R8QPkg.dec`, scripts, and manifest.

**Exit criteria:**

- all prior fabricated claims are removed or downgraded;
- every hardware value is tagged V/I/U with a source;
- no device write or firmware build is claimed;
- manifest regenerated and committed;
- `scripts/verify_environment.sh` passes on the host.

**Status:** Complete when this commit is made.

---

### M2 — EDK II build and QEMU foundation

**Objective:** Prove that a minimal ARM64 EDK II image can be built and booted in QEMU.

**Work:**

- initialize the pinned EDK II submodules;
- build BaseTools;
- create a minimal `R8QPkg.dsc`/`.fdf` with SEC/PrePi and a null console;
- build for AARCH64 with a supported toolchain;
- boot in `qemu-system-aarch64` (virt or a minimal platform);
- record the exact commands, versions, image hash, and QEMU log.

**Exit criteria:**

- build completes without errors;
- image boots in QEMU to a known point;
- memory map and entry code do not overlap;
- no hardware claim is made.

**Risks:** EDK II version/toolchain incompatibility; missing submodules; QEMU platform mismatch.

---

### M3 — Read-only handoff instrumentation

**Objective:** Measure the real device before writing anything.

**Work:**

- capture the live FDT, `/memory`, `/reserved-memory`, and partition map read-only;
- record the stock `BOOT` image hash and bootloader/recovery versions;
- determine the ABL payload format and load address from the stock image and public documentation;
- document the handoff state as far as possible without modifying the device;
- write and test the restore plan on a disposable unit or with a verified path.

**Exit criteria:**

- live map matches or explains the differences from `r8q-live.dts`;
- partition map and stock image hashes are recorded;
- restore plan is documented and, if possible, tested;
- user authorization checklist is ready.

**Device writes:** None.

---

### M4 — First hardware payload

**Objective:** Boot a minimal R8Q UEFI payload on the target unit.

**Preconditions:** M3 complete; verified stock backup; explicit user authorization; tested restore path.

**Work:**

- package the minimal payload in the format required by ABL;
- write only the `BOOT` partition;
- boot to a console (inherited framebuffer or serial);
- record the exact output and any faults;
- restore the stock `BOOT` image and verify it.

**Exit criteria:**

- payload boots to a known banner or shell prompt;
- no bootloader/calibration/recovery partition is touched;
- restore is tested;
- the test record includes the image hash and commands.

**Risks:** unknown load address, display state, memory map, or ABL verification behavior.

---

### M5 — Storage and variables

**Objective:** Read internal storage safely and provide a variable store.

**Work:**

- UFS host initialization, read-only LUN enumeration;
- partition table parsing;
- FAT driver on an external/disposable ESP;
- file-backed variable store;
- no internal partition writes.

**Exit criteria:**

- UFS LUNs and partitions are enumerated read-only;
- the ESP is readable;
- variables persist across a reboot on the test medium;
- no internal `uefivarstore` write occurs.

---

### M6 — Shell and diagnostics

**Objective:** Provide a usable shell and a safe diagnostic subset.

**Work:**

- integrate UEFI Shell 2.2;
- implement `sysinfo`, `memmap`, `cpuinfo`, `display`, `fdtinfo`, `keys`;
- add storage/PCIe/USB/telemetry commands only as drivers become available;
- label every output with its source and confidence.

**Exit criteria:**

- shell runs on the target console;
- safe commands produce measured or `UNKNOWN` values, never fabricated ones;
- no command writes to a protected partition.

---

### M7 — Linux boot

**Objective:** Boot a Linux ARM64 kernel to userspace.

**Work:**

- EFI-stub path with DTB/initrd;
- direct-boot fallback;
- memory reservation preservation;
- console/display handoff;
- root filesystem and initrd validation.

**Exit criteria:**

- kernel reaches userspace;
- the DTB reserved map matches the live map;
- display or serial console works;
- the test record includes the kernel, DTB, initrd, and firmware hashes.

---

### M8 — Recovery integration

**Objective:** Make recovery a first-class, tested path.

**Work:**

- recovery image or maintenance shell on the ESP;
- boot menu entry;
- rollback to stock `BOOT`;
- hardware-key safe mode;
- incident-response documentation.

**Exit criteria:**

- recovery boots;
- stock restore is tested;
- a failed boot returns to the menu/shell without writing internal storage.

---

### M9 — Windows ARM64 research

**Objective:** Determine whether Windows is feasible, without claiming it is.

**Work:**

- ACPI table requirements and prototypes;
- storage/USB/display driver gap analysis;
- runtime-services validation;
- licensed Windows PE test only if the prerequisites exist.

**Exit criteria:**

- a documented blocker matrix with evidence;
- no installability or functionality claim unless a PE boot is recorded;
- a tested restore path remains available.

---

### M10 — Optional GUI and hardening

**Objective:** Improve usability and reliability after the core platform works.

**Work:**

- optional graphical boot menu/dashboard;
- touch/pointer support if the controller is identified;
- stress/reboot testing;
- reproducible release build and signed manifest.

**Exit criteria:**

- GUI is optional and falls back to text;
- stress test results are recorded;
- release artifacts are reproducible and hashed;
- documentation matches the tested build.

---

## 4. Indicative sequencing

The milestones are dependency-ordered, not date-ordered. A realistic sequence is:

```text
M1 → M2 → M3 → [authorization gate] → M4 → M5 → M6 → M7 → M8 → M9 → M10
```

M9 can run in parallel with M5–M8 as a research task, but it must not block the Linux/recovery path and must not justify device writes.

---

## 5. Schedule risks

| Risk | Effect | Mitigation |
|---|---|---|
| No device access | M3/M4 cannot start | Continue M2/QEMU and host-side work. |
| Unknown ABL format | Payload may not boot | Inspect stock images and public documentation; instrument read-only first. |
| UFS driver complexity | Storage/variables delayed | Start with ESP/MicroSD; keep internal storage read-only. |
| Display handoff failure | No visual console | Validate serial/headless fallback. |
| USB host unverified | No keyboard | Use hardware keys or serial. |
| Windows driver gap | M9 stalls | Keep Windows research-only; do not promise a date. |
| Safety incident | Project stops | Backup, restore test, authorization gate. |

---

## 6. Definition of done

A milestone is done when:

- the code/docs are committed;
- the verification ledger is updated;
- the test commands and outputs are recorded;
- the manifest is regenerated;
- the next milestone's preconditions are met;
- no unsupported claim remains in the documentation.
