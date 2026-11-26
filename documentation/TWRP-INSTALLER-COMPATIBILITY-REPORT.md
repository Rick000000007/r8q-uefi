# Project R8Q — TWRP Compatibility Audit & Implementation Report

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / Qualcomm Snapdragon 865 `SM8250` / `ARM64` `aarch64`)  
**Audited Baseline Package:** `R8Q-Debian12-ARM64-Installer.zip` (Master CI run `45862494147`, commit `ffd2543f87d17e9e39365448fab146081b5a0a00`)  
**Corrected Deliverable:** `R8Q-Debian12-ARM64-TWRP-Installer.zip` (commit `10670bbd3c98d091c105da1ff7a2bef6f2955146`)  
**Execution Status:** Simulated TWRP dry-run and GitHub Actions verification only. **Zero physical flashes or partition writes were performed.**

---

## 1. Existing ZIP Compatibility Verdict

**Verdict: INCOMPATIBLE with TWRP as originally packaged.**

Inspection of the actual CI-generated `R8Q-Debian12-ARM64-Installer.zip` (`371,924,232` bytes / `354.69 MiB`, SHA-256 `2a2785531970e1ab9b8f1c551a4b8dc495ed6e8a0a2391e9b2008b03e17d56c0`, GitHub artifact wrapper `362,288,337` bytes) confirmed that **all OS payloads inside the ZIP are complete and verified**:
- Debian 12.15 ARM64 root filesystem (`r8q-rootfs.ext4.gz` `172,047,353` B, `r8q-rootfs.tar.gz` `158,123,670` B)
- EDK II UEFI firmware (`R8Q_EFI.fd` `4,194,304` B) and compound boot image (`r8q-uefi-boot-complete.img` `24,461,312` B)
- All 17 `.efi` applications (`BootManager.efi`, `Setup.efi`, and 15 UEFI apps in `payload/uefi/` totaling `1,236,992` B)
- ARM64 EFI Stub Linux kernel (`Image` `17,197,568` B) and matching DTBs (`sm8250-samsung-r8q.dtb` `112,421` B, `r8q.dtb` `821,466` B)
- Initramfs (`initramfs.img` `2,947,562` B)
- 256 MiB FAT32 ESP (`esp.img` `268,435,456` B + 5 `.nsh` scripts)
- Master installer, 11 subordinate stage scripts (`01`..`11`), configs (`device.conf`, `partition-map.conf`, `boot.conf`), and SHA-256 manifests (`MANIFEST.json`, `SHA256SUMS`)

However, TWRP recovery on `SM-G781B` (`r8q`) cannot install `R8Q-Debian12-ARM64-Installer.zip` directly due to six structural and runtime incompatibilities documented below.

---

## 2. TWRP Version & Environment Requirements (`r8q` / `SM-G781B`)

Verified from the official TWRP device tree [`TeamWin/android_device_samsung_r8q`](https://github.com/TeamWin/android_device_samsung_r8q/tree/android-12.1) (`android-12.1`), [`TeamWin/android_bootable_recovery`](https://github.com/TeamWin/android_bootable_recovery/tree/android-12.1) (`twrp-3.7.x` / `android-12.1`), and read-only inspection of the live `r8q` hardware metadata and recovery environment:

| Property | Verified TWRP `r8q` / Hardware Value |
| :--- | :--- |
| TWRP Device Tree / Branch | `twrp_r8q-eng` (`android-12.1` / TWRP 3.7.x recovery base) |
| Architecture & ABI | `arm64-v8a`, `CORE_64_BIT_ONLY`, VNDK 30, shipping API level `29`, Recovery API v`3` |
| SoC / Platform | Qualcomm Snapdragon 865 (`kona` / `SM8250`; live DTB compatible: `qcom,kona-mtp qcom,kona qcom,mtp`) |
| Live Hardware Identity (`/proc/device-tree/model`) | `Samsung R8Q EUR PROJECT - R8 REV04 (board-id,08)` |
| Shell & PATH (`etc/init.rc`, `postrecoveryboot.sh`) | `/sbin/sh` (BusyBox `ash`) and `/system/bin/sh`; `PATH=/sbin:/system/bin` (no `/usr/bin/env`, no GNU `bash`, no `python3`) |
| Python Support (`TW_INCLUDE_PYTHON`) | Unset / **Not present** in `twrp_r8q` |
| Recovery Protocol (`twrpinstall/twinstall.cpp`) | Requires `META-INF/com/google/android/update-binary` at ZIP root, invoked via `execve("/tmp/update_binary", [path, api_ver("3"), pipe_fd, zip_path, [retry]])` |
| Partition Mounts (`recovery.fstab` / `twrp.flags`) | `/boot`=`sda23` (`67,108,864` B), `/recovery`=`sda24` (`82,694,144` B), `/keyrefuge`=`sda25` (`16,777,216` B), `/data`=`userdata` (`sda36`, `TW_INCLUDE_CRYPTO := false`), `/external_sd`=`mmcblk0p1` (`124,833,792` 1K-blocks) |
| Temp / Staging Space (`/tmp`) | RAM `tmpfs` (50% of 6/8 GB RAM ~ 2.8–3.8 GiB); `TW_UNMOUNT_SYSTEM = 1` unmounts `/system` before launching `update-binary` |
| ZIP Signature Verification (`twinstall.cpp` / `data.cpp`) | `TW_SIGNED_ZIP_VERIFY_VAR` defaults to `"0"` (disabled by default in TWRP). When enabled in TWRP settings, verifies AOSP `SignApk` v1 WholeFileSignature EOCD footer against `/system/etc/security/otacerts.zip` (`verify_file`). Also supports `<zip>.sha256` / `.md5` sidecars via `twrpDigestDriver`. |

---

## 3. Exact Missing or Incompatible Components Identified

1. **Missing TWRP Entry Point at ZIP Root:** `R8Q-Debian12-ARM64-Installer.zip` placed all files inside `R8Q-Debian12-ARM64-Installer/` with no `META-INF/com/google/android/update-binary` (or `updater-script`) at ZIP root. `TWinstall_zip()` returns `INSTALL_CORRUPT` (`Invalid zip file format!`).
2. **GNU Bash & `/usr/bin/env` Dependencies:** All 15 scripts (`install.sh`, `verify-checksums.sh`, `verify-device.sh`, `uninstall-or-rollback.sh`, and `scripts/01..11`) declared `#!/usr/bin/env bash`, used `set -euo pipefail`, `${BASH_SOURCE[0]}`, and Bash arrays (`ARGS+=(...)`). TWRP lacks both `/usr/bin/env` and GNU `bash`.
3. **Mandatory `python3` Dependency:** `verify-checksums.sh`, `verify-device.sh --partition-map`, and stages `04` through `10` invoked `python3 -B -`, plus `01-preflight.sh` aborted if `bash` or `python3` was missing from `PATH`. `twrp_r8q` does not build `python3_twrp`.
4. **GNU Coreutils `df -PB1` & tmpfs Storage Check:** `verify-device.sh` used `df -PB1` (rejected by BusyBox/Toybox `df`) and checked `MIN_TOTAL_INSTALL_FREE_BYTES` (`3,221,225,472` B / 3 GiB) exclusively on `$SCRIPT_DIR`, which fails inside a 6 GB device's RAM `/tmp` tmpfs even when `/external_sd` or `/data` has > 100 GiB free.
5. **Model String Handling in Recovery:** Unified `r8q` builds frequently report `SAMSUNG_r8q` or `SM-G780G` via `ro.product.model` / `ro.product.system.model`, whereas hardware bootloader/DTB (`/proc/device-tree/model` / `ro.bootloader`) positively identifies `Samsung R8Q EUR` / `G781B*`.
6. **ZIP64 Headers:** `scripts/build_unified_installer.py` built archives with `allowZip64=True`; switching to `allowZip64=False` enforces clean 32-bit EOCD headers for `minzip`, `libziparchive`, and WholeFileSignature compatibility on a `< 4 GiB` archive.

---

## 4. Implementation & Entry-Point Design

### 4.1 TWRP Entry Point (`META-INF/com/google/android/update-binary` & `updater-script`)

Added to ZIP root from [installer/twrp/META-INF/com/google/android/update-binary](file:///root/r8q-uefi/installer/twrp/META-INF/com/google/android/update-binary) (`0755`, `#!/sbin/sh`) and [installer/twrp/META-INF/com/google/android/updater-script](file:///root/r8q-uefi/installer/twrp/META-INF/com/google/android/updater-script) (`0644`):

1. **Argument Validation:** Validates `$# >= 3`, numeric Recovery API version (`$1 >= 1`), numeric `OUTFD` (`$2`), open `/proc/self/fd/$OUTFD` when `OUTFD > 2`, and readable non-empty ZIP archive (`$3`).
2. **Storage & Package Discovery:** Resolves BusyBox/system `sh` and `unzip`, verifies extraction headroom (`>= 681,574,400` B in `$R8Q_STAGE_BASE` / `/tmp`), confirms `R8Q-Debian12-ARM64-Installer/install.sh` exists inside `$ZIP_PATH`, and extracts the package to an isolated temporary directory (`chmod 700`) with an `EXIT`/`INT`/`TERM` cleanup trap.
3. **Environment & Storage Media Selection:** Restores `.sh` executable permissions after BusyBox extraction and selects mounted target storage (`/external_sd`, `/storage/sdcard1`, `/data`, or ZIP directory) for the 3 GiB capacity check when `R8Q_SPACE_CHECK_DIR` is not manually overridden, without bypassing `--min-space-bytes` checks.
4. **Master Installer Execution & Progress Protocol:** Reads `PHYSICAL_WRITES_ENABLED` from `config/device.conf` (defaulting to `--dry-run` while `PHYSICAL_WRITES_ENABLED=0`), streams stdout/stderr via `ui_print <line>\nui_print\n` to `$OUTFD`, advances `set_progress` monotonically (`0.02 -> 0.08 -> 0.14..0.97 -> 1.00`), halts immediately on any stage failure, preserves the exact non-zero exit code via `.master_install.rc`, and returns it cleanly to TWRP.

### 4.2 Pure POSIX `/bin/sh` + BusyBox Portability Refactor

Converted all installer scripts (`install.sh`, `verify-checksums.sh`, `verify-device.sh`, `uninstall-or-rollback.sh`, and `scripts/01..11`) plus shared helper [installer/scripts/lib-common.sh](file:///root/r8q-uefi/installer/scripts/lib-common.sh) to POSIX `sh` using only BusyBox/Toybox utilities (`sh`, `sha256sum`, `gzip`, `tar`, `cpio`, `dd`, `od`, `wc`, `awk`, `df`), completely eliminating `python3`, GNU `bash`, `/usr/bin/env`, and `df -PB1`.

---

## 5. Orchestrated 19-Step Installation Sequence & Critical Partition Protection

[installer/install.sh](file:///root/r8q-uefi/installer/install.sh) strictly enforces stage dependencies (`01 -> 02 -> ... -> 11`) mapping to all 19 required installation steps:

| Stage | Steps | Script & Function |
| :--- | :--- | :--- |
| Stage 01 | Steps 1–5 | [01-preflight.sh](file:///root/r8q-uefi/installer/scripts/01-preflight.sh): Execution env/UID check, POSIX/BusyBox tool check, `SM-G781B`/`r8q`/`aarch64`/`SM8250` hardware & storage validation ([verify-device.sh](file:///root/r8q-uefi/installer/verify-device.sh)), firmware/BootManager prerequisite check |
| Stage 02 | Step 6 | [02-verify-payloads.sh](file:///root/r8q-uefi/installer/scripts/02-verify-payloads.sh): Full SHA-256 & byte-size audit against `MANIFEST.json` & `SHA256SUMS` ([verify-checksums.sh](file:///root/r8q-uefi/installer/verify-checksums.sh)) |
| Stage 03 | Steps 7–8 | [03-prepare-target.sh](file:///root/r8q-uefi/installer/scripts/03-prepare-target.sh): Partition map boundary verification (`sda24` `1368216+161512`), `sda25` Knox Keyrefuge lock, `sda23` protection, and `PHYSICAL_WRITES_ENABLED=0` gate |
| Stage 04 | Step 9 | [04-install-firmware.sh](file:///root/r8q-uefi/installer/scripts/04-install-firmware.sh): Validates `R8Q_EFI.fd` (`4,194,304` B, `_FVH`) & `r8q-uefi-boot-complete.img` (`<= 82,694,144` B, `ANDROID!` v2) |
| Stage 05 | Step 10 | [05-install-uefi.sh](file:///root/r8q-uefi/installer/scripts/05-install-uefi.sh): Validates `BootManager.efi`, `Setup.efi`, and 15 UEFI apps (`MZ` / `PE\0\0` / machine `0xAA64`) |
| Stage 06 | Step 11 | [06-install-esp.sh](file:///root/r8q-uefi/installer/scripts/06-install-esp.sh): Validates `esp.img` (`268,435,456` B, `0x55AA` + `EFI PART`) and 5 `.nsh` scripts |
| Stage 07 | Step 12 | [07-install-kernel.sh](file:///root/r8q-uefi/installer/scripts/07-install-kernel.sh): Validates kernel `Image` (`MZ` + `ARM\x64`) & FDT v17 DTBs (`0xD00DFEED`, length match) |
| Stage 08 | Step 13 | [08-install-initramfs.sh](file:///root/r8q-uefi/installer/scripts/08-install-initramfs.sh): Validates gzip CPIO `070701`, uncompressed size > 1 MiB, `init`, `bin/busybox`, ARM64 glibc, and 5 storage/FS kernel modules |
| Stage 09 | Step 14 | [09-install-rootfs.sh](file:///root/r8q-uefi/installer/scripts/09-install-rootfs.sh): Validates `r8q-rootfs.ext4.gz` (`0x53ef`) & `r8q-rootfs.tar.gz` (`> 30 MiB`, `bin/bash`, `usr/bin/apt`, `etc/sudoers.d/r8q`) for non-destructive MicroSD target (`LABEL=r8q-rootfs`) |
| Stage 10 | Steps 15–17 | [10-configure-boot.sh](file:///root/r8q-uefi/installer/scripts/10-configure-boot.sh): Verifies terminal-first `default.target -> multi-user.target`, `getty@tty1`, `serial-getty@ttyMSM0`, no `graphical.target` / `display-manager.service` autostart, and `boot.cfg` + `debian/kali/ubuntu.conf` |
| Stage 11 | Steps 18–19 | [11-post-install-validation.sh](file:///root/r8q-uefi/installer/scripts/11-post-install-validation.sh): Verifies unbroken `01,02,03,04,05,06,07,08,09,10` token chain and emits final execution report |

**Critical Partition Protection:** `verify-device.sh` and `partition-map.conf` unconditionally block `/dev/block/sda25`, `keyrefuge`, `sda26`, `keydata`, `sda27`, `vbmeta_samsung`, `sda23`, `by-name/boot`, `sda21`, `sda22`, and `/dev/block/sda` with `[SECURITY-ABORT]` (exit `14`), require matching `SM8250` geometry or an independent `--partition-map`, and enforce `PHYSICAL_WRITES_ENABLED=0` / `PHYSICAL_FLASH_AUDIT_APPROVED=0` / `ALLOW_ANDROID_OR_RECOVERY_ERASE=0` (aborting `--install` at Stage 03 with exit `42`).

---

## 6. Payload Integrity & ZIP Signature Verification Analysis

- **Internal Payload Integrity:** `verify-checksums.sh` cross-checks `manifests/MANIFEST.json` (`files[]` size & digest) against `manifests/SHA256SUMS` (58 verified package entries across scripts, configs, manifests, firmware, UEFI apps, ESP, kernel, DTBs, initramfs, and rootfs + `manifests/SHA256SUMS` itself = 59 files inside `R8Q-Debian12-ARM64-Installer/`, plus 2 TWRP files under root `META-INF/` = **61 file entries total** in the ZIP).
- **Signature Verification Findings:**
  - TWRP builds based on `TeamWin/android_bootable_recovery` (`android-12.1`) set `TW_SIGNED_ZIP_VERIFY_VAR = "0"` by default, allowing properly structured `META-INF/com/google/android/update-binary` ZIPs without requiring a maintainer key.
  - When a user explicitly enables **Zip signature verification** in TWRP Settings, `twinstall.cpp` enforces AOSP `SignApk` v1 WholeFileSignature (6-byte EOCD `0xFFFF` footer + DER PKCS#7/CMS SignedData covering bytes `[0 .. eocd_offset + 20)`) verified against keys in `/system/etc/security/otacerts.zip` (AOSP `testkey` on standard builds, or maintainer-specific keys on custom recovery builds; no private signing key is stored or exposed in this repository, CI logs, or artifacts).
  - [scripts/build_unified_installer.py](file:///root/r8q-uefi/scripts/build_unified_installer.py) implements optional `sign_zip_whole_file()` (`--sign-cert` / `--sign-key`) via OpenSSL CMS (`-binary -outform DER -noattr -md sha256`) matching `twrpinstall/verifier.cpp`, and writes `<zip>.sha256` alongside every generated archive for TWRP Digest Verification (`twrpDigestDriver::Check_File_Digest`).

---

## 7. Verified Test Results

All checks passed after final code edits with zero skipped or relaxed assertions:

1. **Local Execution (ARM64 Host, Sterile BusyBox Recovery PATH):**
   - `python3 -B -m unittest tests/test_twrp_installer.py tests/test_unified_installer.py -v`: **12 / 12 PASSED** (`53.404s`):
     - `TestTwrpInstallerCompatibility` (**5 / 5 OK**): ZIP root `META-INF` permissions (`0755`/`0644`) & strict non-ZIP64 EOCD; full 19-step `--dry-run` under BusyBox `ash` with `bash` and `python3` absent from `PATH` verifying monotonic `set_progress` (`0.02..1.00`) and `ui_print` over an `os.pipe()` `OUTFD`; invalid argument & missing-master rejection; abort exit code propagation on `sda25`, wrong model (`SM-S918B`), wrong arch (`x86_64`), insufficient space, `--install` lock, and tampered kernel byte; WholeFileSignature EOCD CMS verification using an ephemeral temp-only RSA-2048 key.
     - `TestUnifiedInstallerPackage` (**7 / 7 OK**): archive completeness, `--help`/`--verify`/`--dry-run` strict order, out-of-order rejection, missing payload halt, bit-flip tamper halt, device/arch/space rejection, protected partition & safety lock checks.
2. **GitHub Actions CI on Final Code Commit (`10670bbd3c98d091c105da1ff7a2bef6f2955146`):**
   - **Reused Verified-Payload Package Build** ([Run `45891483009`](https://github.com/Rick000000007/r8q-uefi/actions/runs/45891483009), reusing verified upstream OS payloads from Master run `45862494147`): **PASSED** in `2m18s`:
     - Real-ZIP CLI dry-run + checksum audit: **58/58 verified**, **11/11 stages OK** (`Physical Writes Done: 0 bytes`).
     - `tests/test_unified_installer.py` on CI ZIP: **7 / 7 OK** (`10.839s`).
     - `tests/test_twrp_installer.py` on CI ZIP under Ubuntu `busybox`: **5 / 5 OK** (`24.814s`).
   - **Full Regression & Acceptance Suite** (`test-platform.yml`, [Run `45891474208`](https://github.com/Rick000000007/r8q-uefi/actions/runs/45891474208)): **128 / 128 PASSED** (`118.848s`), plus hardware safety scan passed.
   - **Master End-to-End Pipeline** (`r8q-complete-build.yml`, [Run `45891474173`](https://github.com/Rick000000007/r8q-uefi/actions/runs/45891474173)): **12 / 12 jobs PASSED** (`GitHub Release Publication` properly skipped):
     - QA Acceptance & Regression Suite (job `140156090792`): **128 / 128 OK** (`114.680s`).
     - Unified Installer job `140157722167`: Real-ZIP CLI dry-run passed, `test_unified_installer.py` **7 / 7 OK** (`13.515s`), `test_twrp_installer.py` **5 / 5 OK** (`20.887s`).

---

## 8. Final Package Details & GitHub Actions Artifact URLs

| Build Run | Workflow | Package Filename | Inner ZIP Size | Inner ZIP SHA-256 | Artifact Wrapper Size | Downloadable GitHub Actions Artifact URL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`45891483009`](https://github.com/Rick000000007/r8q-uefi/actions/runs/45891483009) (preserved payloads from `45862494147`) | `Build Unified One-Click Installer Package` | `R8Q-Debian12-ARM64-TWRP-Installer.zip` | `371,930,623` bytes (`354.70 MiB`) | `5fb848e817f5d92396479ca04aeb2f2bdcdb080ab0ec34cb33aff8cb0cd14fe8` | `362,297,191` bytes | https://github.com/Rick000000007/r8q-uefi/actions/runs/45891483009/artifacts/15152096291 |
| [`45891474173`](https://github.com/Rick000000007/r8q-uefi/actions/runs/45891474173) (Master CI on `10670bb`) | `R8Q Complete Platform Build Pipeline (Master)` | `R8Q-Debian12-ARM64-TWRP-Installer.zip` | `371,930,621` bytes (`354.70 MiB`) | `d6708bbbd04fbb4d1c82bcc1ee0d1699d8ffbbe8a3a914209b4edc4a174400bc` | `362,297,443` bytes | https://github.com/Rick000000007/r8q-uefi/actions/runs/45891474173/artifacts/15152022360 |

*(Note: GitHub Actions wraps uploaded files inside a downloadable artifact ZIP container; extract once after downloading to obtain `R8Q-Debian12-ARM64-TWRP-Installer.zip` ready for TWRP **Install** or `adb sideload`.)*
