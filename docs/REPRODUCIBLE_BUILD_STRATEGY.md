# Project R8Q UEFI: Reproducible Build Strategy

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Build strategy. No EDK II firmware build has been produced yet.

---

## 1. Host baseline

The current host was inspected on 2026-11-20:

| Item | Value |
|---|---|
| OS | Kali GNU/Linux Rolling 2026.3, AArch64 |
| Kernel | `4.19.325-cip136-st20-perf-g50cffe6c51d9` |
| CPU | 6 cores |
| RAM | ~7.4 GiB total (≈2.6 GiB available at inspection) |
| Free space | ~89 GiB on the working filesystem |
| GCC | 16.2.0 (`aarch64-linux-gnu-gcc` 16.2.0) |
| Clang/LLD | 21.1.8 |
| Make | 4.4.1 |
| DTC | 1.8.1 |
| iASL | 20260408 |
| Python | 3.14.10 |
| Git | 2.53.0 |
| QEMU AArch64 | Not installed |
| `adb` / `fastboot` | Not installed |

The host is ARM64-native, so EDK II can be built natively. The absence of QEMU and device tools is a Milestone 2 prerequisite, not a blocker for documentation.

---

## 2. Pinned sources

### 2.1 EDK II

| Item | Value |
|---|---|
| Repository | `https://github.com/tianocore/edk2.git` |
| Tag | `edk2-stable202411` |
| Commit | `0f3867fa6ef0553e26c42f7d71ff6bdb98429742` |
| Fallback tag | `edk2-stable202408.01` |
| Fallback commit | `4dfdca63a93497203f197ec98ba20e2327e4afe4` |

The local `edk2/` checkout is at the `202411` tag, shallow, with submodules not initialized. No build has been performed. The pin is an evaluation baseline; it becomes a verified build baseline only after a successful build and test.

### 2.2 EDK II platforms

`edk2-platforms` is not yet pinned or cloned. It will be added only if the platform needs upstream packages that are not in `edk2`. Record the exact commit when it is introduced.

### 2.3 Device tree sources

| Source | Use |
|---|---|
| Linux `v6.18` (`f7b88edb52c8dd01b7e576390d658ae6eef0e134`) | SoC-level addresses and upstream `r8q` support. |
| `devicetree/r8q-live.dts` | Device-specific evidence for the captured unit; not a build input. |
| `edk2-msm` `e1952621f419f8db60ed28271264e1b5184c571d` | Reference only. |

The downstream FDT is sanitized before publication. Its hash is recorded in the manifest.

---

## 3. Build prerequisites

- `edk2` at the pinned commit.
- Initialized submodules for the packages used by the build.
- `BaseTools` built natively for AArch64.
- `iasl` for ACPI tables (when ACPI work begins).
- `dtc` for DTS/DTB validation.
- `qemu-system-aarch64` for software-only tests.
- A cross/native GCC or Clang toolchain supported by the selected EDK II tag.
- Python 3 with the modules required by BaseTools.

The exact EDK II toolchain tag (`GCC5`, `CLANGDWARF`, etc.) will be chosen after a build attempt. Do not claim a toolchain works until `build` completes and the image boots in QEMU.

---

## 4. Build workflow (planned)

```text
1. Verify host tools and versions.
2. Check out the pinned EDK II commit and initialize only the required submodules.
3. Build BaseTools.
4. Set up the R8QPkg workspace (packages path, PCDs, FDF).
5. Build a minimal SEC/DXE image for AARCH64.
6. Run static checks (headers, sizes, memory-map overlap).
7. Boot the image in QEMU AArch64.
8. Record the build hash, tool versions, and QEMU log.
9. Only after the QEMU test passes, consider a hardware test with explicit authorization.
```

Milestone 1's `scripts/build.sh` stops at step 1 and the source manifest. It does not build firmware.

---

## 5. Reproducibility rules

1. Pin every source to a commit, not a branch.
2. Record submodule commits.
3. Set `SOURCE_DATE_EPOCH` for deterministic timestamps.
4. Sort manifest entries and avoid absolute paths.
5. Record the exact compiler, linker, Python, iASL, and DTC versions.
6. Avoid network access during the build step.
7. Hash the source tree and the output image.
8. Keep a build log with the command line and environment.
9. Rebuild from a clean tree and compare hashes before claiming reproducibility.
10. Do not embed personal identifiers, device serials, or build-host paths in the firmware.

The manifest generator supports a deterministic timestamp when `SOURCE_DATE_EPOCH` is set. A reproducible build is a goal, not a current claim.

---

## 6. Artifact policy

| Artifact | Committed? | Notes |
|---|---|---|
| Source, docs, manifests | Yes | Text only. |
| `edk2/` clone | No | Ignored; pinned by commit. |
| `build/`, `artifacts/`, `logs/` | No | Generated; ignored. |
| Firmware FD / boot image | No (until a release) | Hash and release notes committed. |
| Raw downstream FDT | Sanitized only | See `devicetree/README.md`. |
| Personal identifiers | Never | Redact serials, IMEI, MAC, device IDs. |

---

## 7. Verification commands

The Milestone 1 baseline can be checked with:

```bash
./scripts/verify_environment.sh
./scripts/build.sh
python3 scripts/gen_manifest.py
```

`build.sh` validates the documentation baseline and regenerates the manifest; it does not produce a firmware image. The output must say so explicitly.

---

## 8. Open build questions

1. Which EDK II toolchain tag builds cleanly on this host?
2. Which submodules are actually required for a minimal AArch64 SEC/DXE image?
3. How large is the resulting FD, and does it fit the candidate window?
4. Does the image boot in QEMU AArch64?
5. Can the build be reproduced byte-for-byte?
6. What is the minimum QEMU platform that exercises the R8Q code paths?

These are Milestone 2 exit criteria, not Milestone 1 claims.
