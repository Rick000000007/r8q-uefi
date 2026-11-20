# Project R8Q UEFI: Recovery and Safety Plan

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Policy and plan. No device modification has been performed.

---

## 1. Principles

1. **Stock boot chain first.** PBL, XBL, ABL, TrustZone, hypervisor, and the secure world are not modified.
2. **No boot-critical writes during research.** Milestone 1 is read-only.
3. **Backup before change.** A verified stock image and partition map must exist before any `BOOT` partition write.
4. **Explicit authorization.** Every device write requires a separate, explicit user decision.
5. **Test the restore path.** A backup that has never been restored is not a recovery plan.
6. **No absolute guarantees.** "Always recoverable" and "100% safe" are not claims this project makes.

---

## 2. Protected data and partitions

The following categories must never be written by R8Q UEFI or its diagnostics:

| Category | Examples | Reason |
|---|---|---|
| Boot chain | `xbl`, `xbl_config`, `abl`, `tz`, `hyp`, `aop`, `devcfg`, `keymaster`, `cmnlib`, `cmnlib64` | Signed boot/security components; corruption can brick or break verified boot. |
| Calibration/NVRAM | `efs`, `sec_efs`, `persist`, `modemst1`, `modemst2`, `fsg`, `fsc` | IMEI, RF calibration, sensors, Wi-Fi/BT MAC, and factory data. |
| Stock recovery | `recovery` | Recovery/restore path. |
| User data | `userdata`, internal storage | Privacy and data loss. |
| Vendor security | `tima`, `sec_debug`, `ss_plog`, `ramoops` (unless explicitly used as a read-only log) | Samsung security/debug state. |

The exact partition names and indices must be enumerated from the unit. The downstream FDT's `vbmeta` node lists some names, but that is not a partition table. Do not hardcode LUNs or indices.

### 2.1 Read-only policy

- Diagnostics may read partition tables and partition contents only after the user explicitly requests it.
- Any command that could write must require a confirmation phrase and, ideally, a hardware-key gate.
- The firmware must not automatically mount or repair internal filesystems.
- The firmware must not write UEFI variables to an internal `uefivarstore` partition during early bring-up.

---

## 3. Backup plan (before any device write)

The following must be captured read-only and stored offline:

1. **Partition map** — GPT/MBR tables, LUN layout, partition names, start/size, and GUIDs.
2. **Stock `BOOT` image** — exact bytes and SHA-256.
3. **Stock `recovery` image** — exact bytes and SHA-256 (if readable).
4. **Bootloader/security partition metadata** — names, sizes, and hashes only; do not attempt to modify.
5. **Device identity and firmware version** — model, board revision, build fingerprint, bootloader version, active slot, and unlock state.
6. **Live FDT** — `/proc/device-tree` or equivalent, with personal identifiers redacted.
7. **Restore instructions** — exact tool, command, and expected output, tested on a disposable unit or with a verified recovery path.

The backup must be reproducible: record the command, tool version, and hash. A backup that cannot be verified is not sufficient.

---

## 4. Restore plan

A restore procedure must be written and tested before a custom `BOOT` payload is installed. At minimum:

1. Enter Download Mode using the stock key combination.
2. Confirm the device is detected by the host tool.
3. Flash the verified stock `BOOT` image (and only that image).
4. Reboot and confirm the stock OS/recovery boots.
5. Verify the hashes of the restored partition.
6. Record the result.

Do not rely on `fastboot boot` as the only test path. Do not assume that a custom `BOOT` image can be removed by erasing a partition without a stock image.

---

## 5. Download Mode and recovery

Samsung Download Mode (Odin/Loke) is implemented by the stock boot chain. Because R8Q UEFI does not modify ABL/XBL, Download Mode is **expected** to remain available, but this is an inference until tested.

Stock recovery is a separate partition. A `BOOT`-only change is **expected** to preserve it, but the actual partition layout and boot selection must be verified.

If a custom payload hangs:

- hold the documented key combination for Download Mode;
- if that fails, use the documented hardware reset/EDL path for the device;
- do not repeatedly power-cycle in a way that could corrupt storage.

No "unbrickable" claim is made.

---

## 6. Safe development ladder

| Stage | Device writes | Test medium | Exit criterion |
|---|---|---|---|
| 0. Documentation | None | Host only | Baseline committed. |
| 1. QEMU | None | Virtual platform | EDK II image boots in QEMU. |
| 2. Read-only hardware probe | None | Stock OS + live FDT | Handoff state, memory map, and partition map captured. |
| 3. Authorized `BOOT` test | `BOOT` only | Verified stock backup | Custom payload boots; restore tested. |
| 4. Storage/console bring-up | `BOOT` only | ESP/MicroSD | UFS/SD read-only, GOP/serial console. |
| 5. Linux boot | `BOOT` only | ESP/MicroSD | Kernel reaches userspace. |
| 6. Recovery integration | `BOOT` only | ESP/MicroSD | Recovery path tested. |
| 7. Windows research | None until proven | External media | PE boot evidence, then review. |

Each stage requires the previous stage's evidence. A later stage must not be used to bypass a failed safety check.

---

## 7. Incident response

If a device write fails or the device does not boot:

1. Stop. Do not attempt random flashes.
2. Record the exact state, last command, and output.
3. Try Download Mode with the documented key combination.
4. If Download Mode works, restore the verified stock image.
5. If it does not, document the failure and seek hardware-specific recovery assistance.
6. Do not publish a "fix" that has not been tested.

---

## 8. User authorization checklist

Before any device write, the user must confirm:

- [ ] The exact device model and codename.
- [ ] Bootloader unlock state and Knox/warranty implications.
- [ ] A verified stock backup exists and its hashes are recorded.
- [ ] The restore procedure has been tested or is considered acceptable risk.
- [ ] The exact partition to be written (expected: `BOOT` only).
- [ ] The exact image hash.
- [ ] The expected boot behavior and rollback plan.
- [ ] That no bootloader, calibration, or recovery partition will be touched.

No write proceeds without this checklist.

---

## 9. Non-claims

- No device has been flashed in this project.
- No restore procedure has been tested on this unit.
- Download Mode and stock recovery are expected to remain available, but this is not proven.
- The project does not guarantee recovery from hardware failure, secure-boot fuse changes, or user error.
