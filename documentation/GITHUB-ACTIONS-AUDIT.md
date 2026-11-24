# Project R8Q — GitHub Actions CI/CD Audit & Architecture Review

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / Snapdragon 865 `SM8250`)  
**Architecture:** AArch64 / ARM64  
**Audit Scope:** Continuous Integration, Build Automation, Cross-Compilation & Packaging  
**Audit Date:** November 24, 2026  
**Document Revision:** 1.0.0  
**Status:** Approved Audit Report  

---

## 1. Executive Summary

A comprehensive, non-destructive audit of Project R8Q's build infrastructure, scripts, workflows, test suites, and packaging tools was conducted to transition GitHub Actions from a packaging-only pipeline into an **authoritative, standalone, reproducible build system**.

The historical pipeline (`.github/workflows/package-release.yml`) relied on downloading pre-compiled binary payloads from GitHub Releases (`r8q-debian12-alpha1`), packaging them, and testing archive checksums. To achieve true engineering independence, GitHub Actions runners (`ubuntu-latest` x86_64) must be capable of independently cross-compiling, assembling, validating, and publishing every platform layer from clean source without requiring a local development environment.

---

## 2. Comprehensive Inventory & Findings

### 2.1 Existing Workflows & Limitations

| Workflow File | Purpose | Audit Findings & Defects |
|---|---|---|
| `package-release.yml` | Monolithic packaging & asset sync | **Defect:** Does not build components from source; uses `gh release download` to fetch prebuilts. If releases are inaccessible, CI fails. |
| `build-firmware.yml` | EDK II firmware volume build | **Finding:** Needs explicit `GCC5_AARCH64_PREFIX=aarch64-linux-gnu-` for x86_64 host cross-compilation; needs BaseTools build prior to firmware invocation. |
| `build-boot-manager.yml` | BootManager & Setup compile | **Finding:** Functional, needs unified workflow call integration and artifact synchronization. |
| `build-kernel.yml` | Kernel & DTB compile | **Finding:** Upstream kernel tree is large; needs caching strategy and fallback to pre-verified ARM64 kernel when `$KERNEL_SRC` is omitted. |
| `build-initramfs.yml` | Early userspace generator | **Defect:** Assumes `/usr/bin/busybox` is ARM64. On x86_64 GitHub runner, `/usr/bin/busybox` is x86_64 ELF. Multiarch `busybox-static:arm64` must be used. |
| `build-debian-rootfs.yml` | Native Debian 12 rootfs | **Finding:** Full debootstrap on GitHub runner requires QEMU binfmt support (`qemu-user-static`). Needs multi-tier strategy (cached clean base + delta build). |
| `build-recovery.yml` | Recovery ZIP packager | **Finding:** Fully functional; validates `sda24` bounds and `sda25` isolation. |
| `build-complete-platform.yml`| Compound boot container | **Finding:** Needs dynamic `PROJECT_ROOT` resolution to run in GitHub workspace. |
| `test-platform.yml` | Automated test suite | **Finding:** 116 tests passing; requires dynamic `PROJECT_ROOT` in test files. |

---

## 3. Critical Path & Environment Incompatibilities

### 3.1 Hardcoded Local Paths (`/root/r8q-uefi`)
Several Python scripts and test suites hardcoded `PROJECT_ROOT = "/root/r8q-uefi"`:
- `scripts/package_complete_boot_img.py` (Line 23)
- `scripts/gen_manifest.py` (Line 14)
- `tests/test_linux_efi_boot.py`, `tests/test_memory_stack_overlap.py`, `tests/test_phase3_*.py`

**Resolution:** Update all scripts and test suites to use dynamic root detection:
```python
PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT",
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
```

### 3.2 x86_64 Runner Cross-Compilation Alignment
GitHub Actions standard runners (`ubuntu-latest`) execute on x86_64 AMD64 hardware. Target binaries for R8Q are strictly AArch64 (ARM64).
- **EDK II BaseTools:** Must compile natively on x86_64 host using standard `gcc`/`make`.
- **EDK II Firmware & Applications:** Must compile using `aarch64-linux-gnu-gcc` via `export GCC5_AARCH64_PREFIX=aarch64-linux-gnu-`.
- **BusyBox for Initramfs:** Standard `apt install busybox-static` installs x86_64 BusyBox on AMD64 runners. CI must install multiarch `busybox-static:arm64` or extract verified AArch64 BusyBox binaries.
- **Rootfs Verification:** Dynamic execution of ARM64 binaries in CI requires `qemu-user-static` and `binfmt-support`.

---

## 4. Proposed Production GitHub Actions Architecture

The target CI/CD architecture implements a modular, orchestrated pipeline with independent, reusable workflows (`workflow_call`) coordinated by a master dispatcher:

```
                               .github/workflows/r8q-complete-build.yml
                                      (Master Orchestrator)
                                                │
         ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
         ▼                  ▼                   ▼                   ▼                  ▼
  build-firmware.yml  build-kernel.yml  build-initramfs.yml  build-debian-rootfs.yml  build-esp.yml
  (EDK II / R8QPkg)   (Linux / DTB)     (BusyBox / Init)     (Debian 12 ARM64)       (256MB FAT32)
         │                  │                   │                   │                  │
         └──────────────────┴─────────┬─────────┴───────────────────┴──────────────────┘
                                      │
                                      ▼
                        build-complete-platform.yml
                    (Compound Boot Container v2 Staging)
                                      │
                                      ▼
                             build-recovery.yml
                    (LineageOS Recovery Flashable ZIP)
                                      │
                                      ▼
                              test-platform.yml
                 (116+ Automated Regression & Security Tests)
                                      │
                                      ▼
                              build-release.yml
                 (Full System Tarball, SHA256SUMS, GitHub Release)
```

---

## 5. Security & Safety Boundaries

1. **Purely Non-Destructive CI:** CI workflows are strictly build, validation, and packaging tasks. Flashing tools (`fastboot`, `heimdall`, `adb`) are excluded.
2. **Automated Keystore (`sda25`) Gate:** Every pull request and release build executes static analysis asserting zero writes to `sda25` or `/dev/block/sda`.
3. **Least-Privilege Permissions:** Build workflows operate under `contents: read`; only the release publishing stage uses scoped `contents: write`.
