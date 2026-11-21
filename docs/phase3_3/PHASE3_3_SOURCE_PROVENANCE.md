# Project R8Q — Phase 3.3: Repository & Source Provenance Audit

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P33-02-PROV`  
**Baseline Commit:** [`4e62ec4`](file:///root/r8q-uefi) (*"feat(phase3.2): architecture remediation, memory decoupling, native kernel 7.2.15 & full validation suite"*)  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Workstream Verdict:** **CONDITIONAL PASS**  

---

## 1. Executive Summary

This audit independently verified the source code history, build toolchains, compiler versions, configuration integrity, and binary provenance of baseline commit `4e62ec4`.

The inspection confirms that:
1. The repository working tree is completely clean on branch `master` at commit `4e62ec4`.
2. The native ARM64 Linux kernel is genuinely compiled from official upstream `linux-source-7.2` (`7.2.15-1kali1`) unpacked in `/usr/src/linux`.
3. The EDK II firmware volume was compiled using official EDK II BaseTools and `GCC5` AArch64 cross-toolchain (`gcc 16.2.0`).
4. Build scripts are self-contained and reproducible.

However, an audit finding was identified regarding stale intermediate artifacts in `build/` and a checksum discrepancy between the Phase 3.2 markdown documentation table and the actual recompiled kernel binary recorded in `manifests/phase3_2_manifest.json`.

---

## 2. Git Repository & Working Tree Audit

### 2.1 Commit Verification
* **Target Commit:** `4e62ec426e0eda6dbf37cc8e06e8d881f1865921`
* **Author:** Antigravity Engineer `<antigravity@r8q-uefi.local>`
* **Date:** Sat Nov 21 00:15:39 2026 +0000
* **Working Tree State:** `Clean` (`nothing to commit, working tree clean`)
* **Branch:** `master` (tracking local development repository)

### 2.2 Commit Hierarchy
```
* 4e62ec4 (HEAD -> master) feat(phase3.2): architecture remediation, memory decoupling, native kernel 7.2.15 & full validation suite
* a24e4a5 Phase 3.1 independent evidence audit and pre-execution safety review
* 7f06138 feat(phase3): physical boot readiness, device tree audit, 6-state driver matrix, and boot plan
* e8e99bc feat(phase2): QEMU ARM64 virtual integration and boot validation
* 47ee746 Phase 1: Native ARM64 Linux Root Filesystem, Driver Audit & Initramfs Validation
```

### 2.3 Phase 3.2 Changeset Analysis
The changeset in `4e62ec4` touched 21 files with 2,629 insertions and 1,141 deletions:
- Core assembly rewrite: `platform/R8QPkg/PrePi/ModuleEntryPoint.S`
- C PrePi rewrite: `platform/R8QPkg/PrePi/PrePi.c`
- Kernel defconfig: `config/kernel_r8q_defconfig` (added `CONFIG_PCI_HOST_GENERIC=y`, `CONFIG_VIRTIO_MMIO=y`, `CONFIG_ACPI=y`)
- Live devicetree: `devicetree/r8q-live.dts` (added `simple-framebuffer` node)
- Packaging: `scripts/package_complete_boot_img.py` (decoupled `Image` from kernel slot)
- Validation suites: `tests/test_phase3_hardware_readiness.py`, `tests/test_qemu_phase2_validation.py`, `tests/test_rootfs_validation.py`
- Release manifest: `manifests/phase3_2_manifest.json`

---

## 3. Upstream Linux Kernel Provenance & Toolchain

### 3.1 Kernel Source Verification
* **Source Location:** `/usr/src/linux`
* **Package Origin:** `linux-source-7.2` (Debian/Kali package `7.2.15-1kali1`)
* **Upstream Version Header:**
  ```makefile
  VERSION = 7
  PATCHLEVEL = 2
  SUBLEVEL = 15
  EXTRAVERSION =
  NAME = Hurr durr I'ma ninja sloth
  ```
* **Patch Modifications:**
  - One low-level Kconfig fix was introduced in `drivers/mfd/Kconfig`: added `select REGMAP_IRQ` under `config MFD_MAX77705` to satisfy unresolved linker symbols in the MAX77705 PMIC fuel-gauge driver.
  - Zero out-of-tree binary blobs or unverified vendor patches were injected into `/usr/src/linux`.

### 3.2 Toolchain & Compiler
* **Cross Compiler:** `aarch64-linux-gnu-gcc` (Debian 16.2.0-1) 16.2.0
* **Host Toolchain:** GCC 16.2.0, GNU Make 4.4.1, GNU Binutils 2.45
* **Compilation Command:**
  ```bash
  make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- KCONFIG_CONFIG=/root/r8q-uefi/config/kernel_r8q_defconfig -j8 Image
  ```
* **Compilation Result:** [build/Image](file:///root/r8q-uefi/build/Image) (16,802,304 bytes / 16.02 MiB). Validated ARM64 header magic (`ARM\x64`) and PE/COFF EFI Stub signature (`PE\0\0`).

---

## 4. Stale and Untracked Artifact Analysis

Inspection of the `build/` directory revealed two legacy / stale artifacts:
1. `build/r8q-uefi-boot-poc.img` (4,261,888 bytes / 4.06 MiB, timestamped Nov 20 13:24):
   This was the Milestone 5 proof-of-concept image that used the legacy PrePi unconditional halt loop. While not referenced by the Phase 3.2 manifest, its continued presence in `build/` creates potential operator confusion during manual staging.
2. `build/r8q-rootfs.tar.gz` (157,698,048 bytes / 150.39 MiB, timestamped Nov 20 23:35):
   Intermediate tarball produced during the debootstrap / rootfs creation pipeline.

---

## 5. Audit Finding

### Finding P33-DOC-DISCREPANCY-01: Documentation Checksum Mismatch for Native Kernel Image
* **Finding ID:** `P33-DOC-DISCREPANCY-01`
* **Severity:** **MEDIUM**
* **Affected Component:** [docs/R8Q_PHASE3_2_MASTER_REPORT.md](file:///root/r8q-uefi/docs/R8Q_PHASE3_2_MASTER_REPORT.md#L121)
* **Evidence:**
  - Documentation table in `R8Q_PHASE3_2_MASTER_REPORT.md` states:
    `build/Image`: SHA-256 = `935c179c09c15ffc1936c507a75908b9b8b9356396c561b369ec237cbe113b24`
  - Disk file [build/Image](file:///root/r8q-uefi/build/Image) and [manifests/phase3_2_manifest.json](file:///root/r8q-uefi/manifests/phase3_2_manifest.json):
    `build/Image`: SHA-256 = `411f9062ff29324e57c4afd08c6c228c777c2d6eae60d5b075c988b29c19c3c1`
* **Reproduction Procedure:**
  ```bash
  sha256sum /root/r8q-uefi/build/Image
  grep "build/Image" /root/r8q-uefi/manifests/phase3_2_manifest.json
  grep "935c179c" /root/r8q-uefi/docs/R8Q_PHASE3_2_MASTER_REPORT.md
  ```
* **Engineering Impact:**
  The discrepancy was caused by an intermediate kernel recompilation that added `CONFIG_ACPI=y` to support QEMU EDK2 virtual testing. `manifests/phase3_2_manifest.json` correctly captured the updated hash `411f9062...`, but the Phase 3.2 documentation report retained the pre-ACPI hash `935c179c...`. This creates confusion during artifact verification.
* **Recommended Remediation:**
  Update documentation tables in Phase 3.3 to reflect the true cryptographic hash `411f9062ff29324e57c4afd08c6c228c777c2d6eae60d5b075c988b29c19c3c1`.
* **Verification Result:**
  Verified via [test_phase3_3_independent_audit.py](file:///root/r8q-uefi/tests/test_phase3_3_independent_audit.py) test 07: disk file and manifest match bit-for-bit.
