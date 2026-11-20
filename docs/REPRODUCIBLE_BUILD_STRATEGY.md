# Project R8Q UEFI: Reproducible Build Strategy & Toolchain Specification

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Toolchain & Host Environment Architecture

Project R8Q UEFI is engineered to build natively on ARM64 Linux hosts, specifically utilizing the rooted Kali Linux ARM64 chroot on Android / LineageOS 23.

### 1.1 Verified Host Toolchain Baseline

| Component | Pinned Version / Package | Path / Identification | Function |
|---|---|---|---|
| **Host OS** | Kali Linux ARM64 (Debian-based) | `Linux localhost 4.19.325` | Build Host Environment |
| **Native Compiler** | GCC 16.2.0 (`gcc`, `g++`) | `/usr/bin/gcc` | EDK II C/C++ compilation (`GCC5` toolchain tag) |
| **Alternative Compiler** | Clang 21.1.8 / LLD 21 | `/usr/bin/clang`, `/usr/bin/lld` | `CLANGDWARF` compilation target |
| **ACPI Compiler** | ACPICA iASL 20260408 | `/usr/bin/iasl` | ASL/AML compilation for DSDT/SSDT |
| **Device Tree** | DTC 1.8.1 | `/usr/bin/dtc` | Device Tree Blob synthesis |
| **Build Driver** | GNU Make 4.4.1 | `/usr/bin/make` | BaseTools compilation |
| **Python Engine** | Python 3.14+ | `/usr/bin/python3` | EDK II build orchestration |
| **Source Control** | Git 2.53.0 | `/usr/bin/git` | Revision tracking & submodules |

---

## 2. Upstream EDK II Pinned Dependencies

To ensure complete determinism and avoid breaking changes from upstream regressions, upstream repositories are pinned to specific releases:

```bash
# Core EDK II Framework
EDK2_REPO="https://github.com/tianocore/edk2.git"
EDK2_TAG="edk2-stable202408.01"
EDK2_COMMIT="4dfdca63a93497203f197ec98ba20e2327e4afe4"

# EDK II Platforms
EDK2_PLATFORMS_REPO="https://github.com/tianocore/edk2-platforms.git"
EDK2_PLATFORMS_COMMIT="pinned-platform-baseline"
```

---

## 3. Build Automation Workflow

The reproducible build sequence follows a 5-step automated pipeline:

```
[1. Configure Environment]
       │
       ▼
[2. Build EDK II BaseTools] (Native C/C++ tools: GenFv, GenFfs, GenSec, VfrCompile)
       │
       ▼
[3. Compile ACPI Tables & DTS] (iasl -> AML; dtc -> DTB)
       │
       ▼
[4. EDK II Platform Build] (build -p R8QPkg/R8QPkg.dsc -a AARCH64 -t GCC5 -b RELEASE)
       │
       ▼
[5. Package Payload & Manifest] (Wrap FD into Android Boot Image, generate SHA256)
```

### 3.1 Output Artifact Locations
- **Firmware Binary:** `build/R8Q_EFI.fd`
- **Bootable Android Payload:** `build/r8q-uefi-boot.img`
- **Diagnostic Manifest:** `manifests/build_manifest.json`
- **Verification Logs:** `logs/build.log`

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
