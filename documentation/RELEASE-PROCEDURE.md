# Project R8Q — Official Release Engineering Procedure

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona)  
**Operating Environment:** Terminal-First Native Debian 12 ARM64  
**Release Distribution:** `R8Q-DEBIAN12-RELEASE`  
**Document Revision:** 1.0.0  
**Status:** Approved Release Standard  

---

## 1. Release Lifecycle & Quality Gates

Every official release of Project R8Q must satisfy four mandatory engineering gates before artifact publication:

```
[ Gate 1: Code Freeze & Safety Audit ]
                 │
                 ▼
[ Gate 2: Full Automated Regression (116+ Tests Green) ]
                 │
                 ▼
[ Gate 3: Bit-Exact Reproducibility & SHA256 Verification ]
                 │
                 ▼
[ Gate 4: Keystore Isolation & +55.53 MiB Headroom Assertion ]
                 │
                 ▼
     [ Official Tag & Publish ]
```

### 1.1 Gate 1: Keystore Safety & Non-Destructive Invariants
- Zero occurrences of `dd` or raw write commands to `/dev/block/sda25`.
- Partition `/dev/block/sda25` (`keyrefuge`) must remain untouched to prevent irreversible hardware Knox bricking.
- No direct flashing commands (`fastboot flash`, `heimdall`) in release scripts.

### 1.2 Gate 2: Test Suite Clearance
- 100% passing results across all automated test suites (`python3 -m unittest discover -s tests -p "test_*.py"`).
- Terminal-first verification: `multi-user.target` default, `getty@tty1` enabled, zero display managers enabled by default.
- Boot manager standalone verification: `Setup.efi` and `BootManager.efi` PE32+ AArch64 signatures confirmed.

### 1.3 Gate 3: Bit-Exact Determinism
- Full system tarball `R8Q-Debian12-Full-System.tar.gz` matches bit-exact SHA-256 digest when built with `SOURCE_DATE_EPOCH=315532800`.
- All release artifacts verified against `R8Q-DEBIAN12-RELEASE/SHA256SUMS`.

### 1.4 Gate 4: Recovery Partition Geometry Ceiling
- Compound boot image `r8q-uefi-boot-complete.img` must not exceed `82,694,144 bytes` (exact capacity of `sda24`).
- Staged size: ~24.47 MiB; safety headroom: **+55.53 MiB** before `sda25` boundary.

---

## 2. Release Asset Checklist

An official Project R8Q release bundle must contain exactly the following verified assets:

| # | Artifact Path | Size | Description |
|---|---|---|---|
| 1 | `boot/r8q-uefi-boot-complete.img` | 25,657,344 B (24.47 MiB) | Compound Boot Container v2 (Firmware + Kernel + Initramfs + DTB) |
| 2 | `boot/esp.img` | 268,435,456 B (256.00 MiB) | FAT32 EFI System Partition (`BootManager.efi`, `Setup.efi`, configs) |
| 3 | `firmware/R8Q_EFI.fd` | 4,194,304 B (4.00 MiB) | Standalone EDK II UEFI Firmware Volume (PrePi + DXE) |
| 4 | `kernel/Image` | 16,802,304 B (16.02 MiB) | Native Linux ARM64 Kernel with EFI Stub |
| 5 | `kernel/sm8250-samsung-r8q.dtb` | 219,864 B (214.7 KiB) | Device Tree Blob for Samsung Galaxy S20 FE 5G |
| 6 | `kernel/initramfs.img` | 4,440,790 B (4.24 MiB) | Early-userspace CPIO archive with recovery shell |
| 7 | `rootfs/r8q-rootfs.ext4.gz` | ~165 MiB | Clean Debian 12 ARM64 Terminal-First root filesystem |
| 8 | `R8Q-Debian12-Recovery.zip` | 25,658,266 B (24.47 MiB) | LineageOS Recovery flashable installation ZIP |
| 9 | `R8Q-Debian12-Full-System.tar.gz` | ~215 MiB | Complete reproducible full-system distribution archive |
| 10| `SHA256SUMS` | ~1 KiB | Bit-for-bit cryptographic checksum manifest |

---

## 3. Step-by-Step Release Procedure

### Step 1: Version Bumping & Documentation
Update the version string across:
- `documentation/BUILD-MANIFEST.md`
- `R8Q-DEBIAN12-RELEASE/BUILD-MANIFEST.md`
- `platform/R8QPkg/R8QPkg.dsc` (`PcdFirmwareVersionString`)

### Step 2: Regenerate Checksum Manifests
```bash
cd R8Q-DEBIAN12-RELEASE
sha256sum \
  boot/r8q-uefi-boot-complete.img \
  boot/esp.img \
  firmware/R8Q_EFI.fd \
  kernel/Image \
  kernel/sm8250-samsung-r8q.dtb \
  kernel/initramfs.img \
  rootfs/r8q-rootfs.ext4.gz \
  R8Q-Debian12-Recovery.zip \
  R8Q-Debian12-Full-System.tar.gz \
  > SHA256SUMS
```

### Step 3: Git Tagging & Push
```bash
git add -A
git commit -m "release: prepare Project R8Q v1.0.0-terminal release distribution"
git tag -a v1.0.0-terminal -m "Project R8Q v1.0.0 Terminal-First Release"
git push origin master --tags
```

### Step 4: Automated CI Execution & Verification
Pushing the `v*` tag automatically triggers `.github/workflows/r8q-complete-build.yml`:
1. Executes `safety-pre-audit`.
2. Cross-compiles all component layers in parallel.
3. Stages and validates the compound boot container.
4. Executes the full 116-test acceptance suite.
5. Publishes release assets to GitHub Releases via `gh release upload`.

---

## 4. Emergency Revocation & Rollback Procedure

If a critical hardware defect, kernel regression, or safety violation is discovered post-release:
1. **Immediately delete GitHub Release:**
   ```bash
   gh release delete v1.0.0-terminal -y
   ```
2. **Delete Remote Git Tag:**
   ```bash
   git push --delete origin v1.0.0-terminal
   ```
3. **Issue Critical Safety Advisory:** Publish a GitHub Security Advisory detailing affected hardware, rollback steps to recovery LineageOS, and mitigations.
